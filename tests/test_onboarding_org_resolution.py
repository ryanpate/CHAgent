"""Hardening: onboarding-flow views must resolve the org for existing users too.

/onboarding/* is a TenantMiddleware PUBLIC_URL, so request.organization is not set there.
The views must fall back to the tenant-selected org / the user's primary org instead of only
session['onboarding_org_id'] or default_organization — otherwise an existing user (no wizard
session, default_organization unset) bounces to signup→dashboard (the Connect-PCO bug class).
"""
import pytest
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan


def _existing_member(client, slug):
    plan = SubscriptionPlan.objects.create(slug=f'p-{slug}', name='P', tier='team')
    org = Organization.objects.create(
        name=f'Org {slug}', email=f'{slug}@x.org', slug=f'org-{slug}',
        subscription_plan=plan, subscription_status='active', stripe_subscription_id='sub_x')
    u = User.objects.create_user(username=f'{slug}@x.org', email=f'{slug}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner', can_manage_billing=True)
    u.save()  # default_organization intentionally left None
    assert u.default_organization is None
    client.force_login(u)
    return org, u


@pytest.mark.django_db
def test_select_plan_resolves_org_for_existing_user(client):
    _existing_member(client, 'sel')
    resp = client.get(reverse('onboarding_select_plan'))
    assert resp.status_code == 200  # was 302 -> signup -> dashboard before hardening


@pytest.mark.django_db
def test_invite_team_resolves_org_for_existing_user(client):
    _existing_member(client, 'inv')
    resp = client.get(reverse('onboarding_invite_team'))
    assert resp.status_code == 200
