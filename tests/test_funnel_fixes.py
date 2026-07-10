"""
Regression tests for signup/subscription funnel fixes (July 2026 review).

Covers:
- 500 crash on unauthenticated /onboarding/select-plan/
- Org-less authenticated users dead-ending at a 404
- Signup rate limiting keyed on the proxy IP instead of the client IP
- Re-subscribe flow relying solely on the Stripe webhook
- Webhook silently dropping events / unmapped subscription statuses
- Silent re-render on invalid plan selection
- Capacitor CSRF exemption honoring a forgeable cookie on cross-site requests
"""
import json
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

User = get_user_model()


# ---------------------------------------------------------------------------
# Fix 1: unauthenticated /onboarding/select-plan/ must redirect to login,
# not crash with a 500 (helper decorated with @login_required returned an
# HttpResponseRedirect that was treated as an Organization).
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_select_plan_unauthenticated_redirects_to_login(client):
    response = client.get(reverse('onboarding_select_plan'))
    assert response.status_code == 302
    assert '/accounts/login/' in response['Location']


# ---------------------------------------------------------------------------
# Fix 2: authenticated users with no organization were redirected to
# /onboarding/ which 404s. They should land on /signup/ and be able to
# create an organization for their existing account.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestOrglessUser:
    def _orgless_user(self):
        user = User.objects.create_user(
            username='noorg@example.org', email='noorg@example.org',
            password='testpass123',
        )
        return user

    def test_dashboard_redirects_to_signup_not_404(self, client):
        client.force_login(self._orgless_user())
        response = client.get('/', follow=True)
        assert response.status_code == 200
        assert response.request['PATH_INFO'] == reverse('onboarding_signup')

    def test_orgless_user_can_create_org_via_signup(self, client):
        from core.models import Organization, OrganizationMembership

        user = self._orgless_user()
        client.force_login(user)
        response = client.post(reverse('onboarding_signup'), {
            'church_name': 'Fresh Start Church',
        })
        assert response.status_code == 302
        assert response['Location'].endswith(reverse('onboarding_select_plan'))

        org = Organization.objects.get(name='Fresh Start Church')
        assert org.subscription_status == 'trial'
        membership = OrganizationMembership.objects.get(user=user, organization=org)
        assert membership.role == 'owner'
        assert membership.can_manage_billing

    def test_user_with_org_still_redirected_to_dashboard(self, client, user_alpha_owner):
        client.force_login(user_alpha_owner)
        response = client.get(reverse('onboarding_signup'))
        assert response.status_code == 302
        assert response['Location'] == reverse('dashboard')


# ---------------------------------------------------------------------------
# Fix 3: rate limiting must key on the real client IP (last X-Forwarded-For
# entry appended by the trusted proxy), not REMOTE_ADDR (the proxy itself,
# shared by every visitor on Railway).
# ---------------------------------------------------------------------------

class TestClientIP:
    def test_uses_last_xff_entry(self, request_factory):
        from core.ip import client_ip
        request = request_factory.get(
            '/', HTTP_X_FORWARDED_FOR='6.6.6.6, 203.0.113.9',
            REMOTE_ADDR='10.0.0.1',
        )
        assert client_ip(request) == '203.0.113.9'

    def test_falls_back_to_remote_addr(self, request_factory):
        from core.ip import client_ip
        request = request_factory.get('/', REMOTE_ADDR='198.51.100.7')
        assert client_ip(request) == '198.51.100.7'


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=True)
def test_signup_ratelimit_buckets_are_per_client_not_per_proxy(client, subscription_plan):
    cache.clear()
    payload = lambda i: {
        'first_name': 'A', 'last_name': 'B',
        'email': f'bucket{i}@x.org', 'password': 'supersecret1',
        'church_name': f'Bucket {i}',
    }
    # Client A (behind the shared proxy) exhausts its bucket.
    for i in range(6):
        last = client.post(
            reverse('onboarding_signup'), payload(i),
            HTTP_X_FORWARDED_FOR='9.9.9.9, 203.0.113.1',
        )
    assert b'too many' in last.content.lower()

    # Client B arrives through the same proxy but a different client IP:
    # it must NOT be blocked by A's bucket.
    client.cookies.clear()
    response = client.post(
        reverse('onboarding_signup'), payload(99),
        HTTP_X_FORWARDED_FOR='9.9.9.9, 203.0.113.2',
    )
    assert b'too many' not in response.content.lower()
    cache.clear()


# ---------------------------------------------------------------------------
# Fix 4: the re-subscribe success page must finalize the checkout session
# itself (like onboarding does) instead of relying solely on the webhook.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_subscription_success_finalizes_from_stripe_session(
    client, user_alpha_owner, org_alpha, settings,
):
    settings.STRIPE_SECRET_KEY = 'sk_test_x'
    org_alpha.subscription_status = 'cancelled'
    org_alpha.stripe_customer_id = 'cus_123'
    org_alpha.stripe_subscription_id = ''
    org_alpha.save()

    fake_sub = MagicMock()
    fake_sub.id = 'sub_resub_1'
    fake_sub.status = 'active'
    fake_sub.trial_end = None
    fake_session = MagicMock()
    fake_session.subscription = fake_sub
    fake_session.customer = 'cus_123'

    client.force_login(user_alpha_owner)
    with patch('stripe.checkout.Session.retrieve', return_value=fake_session):
        response = client.get(
            reverse('subscription_success') + '?session_id=cs_test_1'
        )

    assert response.status_code == 302
    org_alpha.refresh_from_db()
    assert org_alpha.stripe_subscription_id == 'sub_resub_1'
    assert org_alpha.subscription_status == 'active'


@pytest.mark.django_db
def test_finalize_checkout_rejects_session_owned_by_another_customer(
    client, user_alpha_owner, org_alpha, settings,
):
    """A checkout session for a different Stripe customer must not activate
    this org (IDOR: session_id comes from the query string)."""
    settings.STRIPE_SECRET_KEY = 'sk_test_x'
    org_alpha.subscription_status = 'cancelled'
    org_alpha.stripe_customer_id = 'cus_123'
    org_alpha.stripe_subscription_id = ''
    org_alpha.save()

    fake_sub = MagicMock()
    fake_sub.id = 'sub_stolen'
    fake_sub.status = 'active'
    fake_sub.trial_end = None
    fake_session = MagicMock()
    fake_session.subscription = fake_sub
    fake_session.customer = 'cus_someone_else'

    client.force_login(user_alpha_owner)
    with patch('stripe.checkout.Session.retrieve', return_value=fake_session):
        client.get(reverse('subscription_success') + '?session_id=cs_theirs')

    org_alpha.refresh_from_db()
    assert org_alpha.stripe_subscription_id == ''
    assert org_alpha.subscription_status == 'cancelled'


# ---------------------------------------------------------------------------
# Fix 5: webhook hardening.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestStripeWebhook:
    def _post(self, client, payload):
        return client.post(
            reverse('stripe_webhook'),
            data=json.dumps(payload),
            content_type='application/json',
        )

    def test_unconfigured_webhook_returns_503_not_silent_200(self, client, settings):
        settings.STRIPE_SECRET_KEY = ''
        settings.STRIPE_WEBHOOK_SECRET = ''
        response = self._post(client, {'type': 'invoice.paid', 'data': {'object': {}}})
        assert response.status_code == 503

    @pytest.mark.parametrize('stripe_status,expected', [
        ('incomplete', 'past_due'),
        ('incomplete_expired', 'cancelled'),
        ('paused', 'cancelled'),
    ])
    def test_maps_additional_subscription_statuses(
        self, client, org_alpha, settings, stripe_status, expected,
    ):
        settings.STRIPE_SECRET_KEY = 'sk_test_x'
        settings.STRIPE_WEBHOOK_SECRET = ''
        org_alpha.stripe_subscription_id = 'sub_map_1'
        org_alpha.save()

        response = self._post(client, {
            'type': 'customer.subscription.updated',
            'data': {'object': {'id': 'sub_map_1', 'status': stripe_status}},
        })
        assert response.status_code == 200
        org_alpha.refresh_from_db()
        assert org_alpha.subscription_status == expected


# ---------------------------------------------------------------------------
# Fix 6a: invalid plan selection must show an error, not silently re-render.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_select_plan_invalid_plan_shows_error(client, user_alpha_owner, org_alpha):
    client.force_login(user_alpha_owner)
    session = client.session
    session['onboarding_org_id'] = org_alpha.id
    session.save()

    response = client.post(reverse('onboarding_select_plan'), {'plan_id': '999999'})
    assert response.status_code == 200
    assert b'no longer available' in response.content.lower()


# ---------------------------------------------------------------------------
# Fix 6b: the aria_app cookie alone must not disable CSRF when the request
# carries a cross-site Origin header (cookie is settable via ?app=1 by anyone).
# ---------------------------------------------------------------------------

class TestCapacitorCsrfExemption:
    def _mw(self):
        from core.middleware import CapacitorCsrfExemptMiddleware
        return CapacitorCsrfExemptMiddleware(lambda r: None)

    def test_cookie_with_cross_site_origin_is_not_exempt(self, request_factory):
        request = request_factory.post('/chat/send/', HTTP_ORIGIN='https://evil.example')
        request.COOKIES['aria_app'] = '1'
        self._mw().process_request(request)
        assert not getattr(request, '_dont_enforce_csrf_checks', False)

    def test_capacitor_origin_is_exempt(self, request_factory):
        request = request_factory.post('/chat/send/', HTTP_ORIGIN='capacitor://localhost')
        self._mw().process_request(request)
        assert getattr(request, '_dont_enforce_csrf_checks', False)

    def test_cookie_without_origin_is_exempt(self, request_factory):
        request = request_factory.post('/chat/send/')
        request.COOKIES['aria_app'] = '1'
        self._mw().process_request(request)
        assert getattr(request, '_dont_enforce_csrf_checks', False)

    def test_cookie_with_null_origin_is_exempt(self, request_factory):
        request = request_factory.post('/chat/send/', HTTP_ORIGIN='null')
        request.COOKIES['aria_app'] = '1'
        self._mw().process_request(request)
        assert getattr(request, '_dont_enforce_csrf_checks', False)
