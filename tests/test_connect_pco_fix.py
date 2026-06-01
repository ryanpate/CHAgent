"""Regression tests for the dashboard/settings 'Connect Planning Center' link.

Bug: onboarding_connect_pco resolved the org only from session['onboarding_org_id']
or request.user.default_organization. For an existing logged-in user (not mid-signup,
default_organization unset), neither was set, so the view redirected to onboarding_signup,
which redirects authenticated users back to the dashboard — the link appeared to do nothing.
"""
import pytest
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan


def _existing_owner(client, slug, *, set_default=False):
    plan = SubscriptionPlan.objects.create(slug=f'plan-{slug}', name='P', tier='team')
    org = Organization.objects.create(
        name=f'Org {slug}', email=f'{slug}@x.org', slug=f'org-{slug}',
        subscription_plan=plan, subscription_status='active', stripe_subscription_id='sub_x',
    )
    u = User.objects.create_user(username=f'{slug}@x.org', email=f'{slug}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner',
                                          can_manage_settings=True)
    if set_default:
        u.default_organization = org
    u.save()
    client.force_login(u)
    return org, u


@pytest.mark.django_db
def test_connect_pco_loads_for_existing_user_without_default_org(client):
    # Reproduces the bug: no onboarding session, default_organization is None.
    org, u = _existing_owner(client, 'nodefault', set_default=False)
    assert u.default_organization is None
    resp = client.get(reverse('onboarding_connect_pco'))
    assert resp.status_code == 200  # was 302 -> signup -> dashboard before the fix
    assert resp.context['organization'].id == org.id


@pytest.mark.django_db
def test_connect_pco_saves_and_returns_to_settings_for_existing_user(client):
    org, u = _existing_owner(client, 'connect', set_default=False)
    resp = client.post(reverse('onboarding_connect_pco'),
                        {'action': 'connect', 'pco_app_id': 'app123', 'pco_secret': 'sec456'})
    assert resp.status_code == 302
    assert resp.url == reverse('org_settings')  # existing user returns to settings, not the wizard
    org.refresh_from_db()
    assert org.planning_center_app_id == 'app123'
    assert org.planning_center_connected_at is not None


@pytest.mark.django_db
def test_connect_pco_continues_wizard_for_new_signup(client):
    # When mid-signup (onboarding_org_id in session), connecting continues to invite-team.
    org, u = _existing_owner(client, 'wizard', set_default=True)
    session = client.session
    session['onboarding_org_id'] = org.id
    session.save()
    resp = client.post(reverse('onboarding_connect_pco'),
                       {'action': 'connect', 'pco_app_id': 'app123', 'pco_secret': 'sec456'})
    assert resp.status_code == 302
    assert resp.url == reverse('onboarding_invite_team')
