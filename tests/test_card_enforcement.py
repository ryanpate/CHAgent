import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan


def _login_org(client, status, stripe_sub='', trial_delta_days=10):
    plan = SubscriptionPlan.objects.create(slug=f'p-{status}-{stripe_sub or "none"}-{trial_delta_days}',
                                           name='P', tier='team',
                                           has_analytics=True, has_care_insights=True)
    org = Organization.objects.create(
        name=f'Org {status}', email=f'{status}@x.org',
        subscription_plan=plan, subscription_status=status,
        stripe_subscription_id=stripe_sub,
        trial_ends_at=timezone.now() + timedelta(days=trial_delta_days),
    )
    u = User.objects.create_user(username=f'{status}{stripe_sub}{trial_delta_days}@x.org',
                                 email=f'{status}{stripe_sub}{trial_delta_days}@x.org',
                                 password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner', can_view_analytics=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    return org


@pytest.mark.django_db
def test_trial_without_card_allowed(client):
    """Card-free trial: no card needed while the trial is active."""
    _login_org(client, 'trial', stripe_sub='')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_expired_trial_without_card_blocked(client):
    _login_org(client, 'trial', stripe_sub='', trial_delta_days=-1)
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 302
    assert reverse('subscription_required') in resp.url


@pytest.mark.django_db
def test_trial_with_card_allowed(client):
    _login_org(client, 'trial', stripe_sub='sub_123')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_active_org_allowed(client):
    _login_org(client, 'active', stripe_sub='sub_456')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_beta_org_allowed_without_card(client):
    _login_org(client, 'beta', stripe_sub='')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_cancelled_org_blocked(client):
    _login_org(client, 'cancelled', stripe_sub='sub_x')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 302
    assert reverse('subscription_required') in resp.url
