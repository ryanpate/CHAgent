"""Tests for the BetaRequest model and beta request flow."""
import pytest
from django.test import Client, override_settings
from core.models import BetaRequest


@pytest.mark.django_db
class TestBetaRequestModel:
    def test_create_beta_request(self):
        req = BetaRequest.objects.create(
            name='John Pastor',
            email='john@firstchurch.org',
            church_name='First Community Church',
            church_size='medium',
        )
        assert req.status == 'pending'
        assert req.name == 'John Pastor'
        assert req.email == 'john@firstchurch.org'
        assert req.church_name == 'First Community Church'
        assert req.church_size == 'medium'
        assert req.created_at is not None

    def test_email_uniqueness(self):
        BetaRequest.objects.create(
            name='John', email='john@church.org',
            church_name='Church A', church_size='small',
        )
        with pytest.raises(Exception):
            BetaRequest.objects.create(
                name='Jane', email='john@church.org',
                church_name='Church B', church_size='large',
            )

    def test_str_representation(self):
        req = BetaRequest.objects.create(
            name='John', email='john@church.org',
            church_name='First Church', church_size='small',
        )
        assert 'First Church' in str(req)
        assert 'john@church.org' in str(req)


@pytest.mark.django_db
class TestBetaRequestView:
    def test_signup_page_shows_beta_form(self):
        client = Client()
        response = client.get('/signup/')
        assert response.status_code == 200
        assert b'Request Beta Access' in response.content

    def test_submit_beta_request(self):
        from core.models import BetaRequest
        client = Client()
        response = client.post('/signup/', {
            'name': 'Sarah Pastor',
            'email': 'sarah@gracechurch.org',
            'church_name': 'Grace Community Church',
            'church_size': 'medium',
        })
        assert response.status_code == 200
        assert b'review your request' in response.content.lower()
        assert BetaRequest.objects.filter(email='sarah@gracechurch.org').exists()

    def test_submit_duplicate_email(self):
        from core.models import BetaRequest
        BetaRequest.objects.create(
            name='Existing', email='exists@church.org',
            church_name='Some Church', church_size='small',
        )
        client = Client()
        response = client.post('/signup/', {
            'name': 'New Person',
            'email': 'exists@church.org',
            'church_name': 'Another Church',
            'church_size': 'large',
        })
        assert response.status_code == 200
        assert b'already' in response.content.lower()

    def test_submit_missing_fields(self):
        from core.models import BetaRequest
        client = Client()
        response = client.post('/signup/', {
            'name': '',
            'email': 'test@church.org',
            'church_name': '',
            'church_size': 'small',
        })
        assert response.status_code == 200
        assert b'required' in response.content.lower()
        assert not BetaRequest.objects.filter(email='test@church.org').exists()


@pytest.mark.django_db
class TestBetaLandingPage:
    def test_landing_page_shows_beta_badge(self):
        client = Client()
        response = client.get('/')
        assert response.status_code == 200
        assert b'BETA' in response.content

    def test_landing_page_has_request_access_cta(self):
        client = Client()
        response = client.get('/')
        assert b'Request Beta Access' in response.content
        assert b'Start Free Trial' not in response.content

    def test_beta_banner_on_public_pages(self):
        client = Client()
        response = client.get('/')
        assert b'closed beta' in response.content.lower()


@pytest.mark.django_db
class TestBetaPricingPage:
    def test_pricing_page_shows_beta_note(self):
        from core.models import SubscriptionPlan
        SubscriptionPlan.objects.get_or_create(
            slug='test-plan',
            defaults={
                'name': 'Test Plan', 'tier': 'team',
                'price_monthly_cents': 3999, 'price_yearly_cents': 39900,
                'max_users': 15, 'max_volunteers': 200,
                'max_ai_queries_monthly': 1000, 'is_active': True,
            }
        )
        client = Client()
        response = client.get('/pricing/')
        assert response.status_code == 200
        assert b'free during beta' in response.content.lower()


class TestSecuritySettings:
    """Test security configuration values."""

    def test_session_timeout_configured(self, settings):
        assert settings.SESSION_COOKIE_AGE == 86400

    def test_session_expires_on_close(self, settings):
        assert settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True


@pytest.mark.django_db
class TestSecurityHeadersMiddleware:
    def test_csp_header_present(self):
        client = Client()
        response = client.get('/')
        assert 'Content-Security-Policy' in response

    def test_permissions_policy_header_present(self):
        client = Client()
        response = client.get('/')
        assert 'Permissions-Policy' in response

    def test_csp_contains_self(self):
        client = Client()
        response = client.get('/')
        csp = response.get('Content-Security-Policy', '')
        assert "'self'" in csp


@pytest.mark.django_db
class TestSecurityPage:
    def test_security_page_accessible(self):
        client = Client()
        response = client.get('/security/')
        assert response.status_code == 200

    def test_security_page_has_data_protection(self):
        client = Client()
        response = client.get('/security/')
        content = response.content.decode()
        assert 'Data Protection' in content

    def test_security_page_has_technical_details(self):
        client = Client()
        response = client.get('/security/')
        content = response.content.decode()
        assert 'Technical Details' in content

    def test_security_page_has_responsible_disclosure(self):
        client = Client()
        response = client.get('/security/')
        content = response.content.decode()
        assert 'security@aria.church' in content


@pytest.mark.django_db
class TestBetaAdminView:
    def test_admin_can_view_beta_requests(self):
        from accounts.models import User
        from core.models import BetaRequest
        admin = User.objects.create_user(
            username='superadmin_t7', email='admin_t7@aria.church',
            password='testpass123',
        )
        admin.is_superadmin = True
        admin.save()
        BetaRequest.objects.create(
            name='Test Church Leader', email='leader@church.org',
            church_name='Test Church', church_size='medium',
        )
        client = Client()
        client.force_login(admin)
        response = client.get('/platform-admin/beta-requests/')
        assert response.status_code == 200
        assert b'Test Church' in response.content

    def test_admin_can_approve_request(self):
        from accounts.models import User
        from core.models import BetaRequest
        admin = User.objects.create_user(
            username='superadmin_t7b', email='admin_t7b@aria.church',
            password='testpass123',
        )
        admin.is_superadmin = True
        admin.save()
        req = BetaRequest.objects.create(
            name='Approved Leader', email='approved@church.org',
            church_name='Approved Church', church_size='small',
        )
        client = Client()
        client.force_login(admin)
        response = client.post(f'/platform-admin/beta-requests/{req.id}/approve/')
        req.refresh_from_db()
        assert req.status in ('approved', 'invited')

    def test_non_admin_cannot_access(self):
        from accounts.models import User
        user = User.objects.create_user(
            username='regular_t7', email='user_t7@church.org',
            password='testpass123',
        )
        client = Client()
        client.force_login(user)
        response = client.get('/platform-admin/beta-requests/')
        assert response.status_code in (302, 403)
