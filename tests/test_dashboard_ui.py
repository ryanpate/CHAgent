import pytest
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan


def _login_active_org(client, slug, *, pco=False):
    plan = SubscriptionPlan.objects.create(slug=f'plan-{slug}', name='P', tier='team',
                                            has_analytics=True, has_care_insights=True)
    org = Organization.objects.create(
        name=f'Org {slug}', email=f'{slug}@x.org', slug=f'org-{slug}',
        subscription_plan=plan, subscription_status='active', stripe_subscription_id='sub_x',
        planning_center_app_id=('app' if pco else ''),
        planning_center_secret=('sec' if pco else ''))
    u = User.objects.create_user(username=f'{slug}@x.org', email=f'{slug}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner',
                                          can_view_analytics=True, can_manage_settings=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    return org, u


@pytest.mark.django_db
def test_dashboard_context_has_pco_and_week_count(client):
    org, u = _login_active_org(client, 'ctx')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200
    assert resp.context['pco_connected'] is False
    assert resp.context['interactions_this_week'] == 0
