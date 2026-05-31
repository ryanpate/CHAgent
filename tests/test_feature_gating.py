import pytest
from django.test import RequestFactory
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.urls import reverse
from core.middleware import require_plan_feature
from core.models import Organization, SubscriptionPlan, OrganizationMembership
from accounts.models import User


def _req(rf, org):
    request = rf.get('/analytics/')
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    MessageMiddleware(lambda r: None).process_request(request)
    request.organization = org
    return request


@pytest.mark.django_db
def test_require_plan_feature_blocks_when_missing(request_factory):
    plan = SubscriptionPlan.objects.create(slug='gate-starter', name='S', tier='starter', has_analytics=False)
    org = Organization.objects.create(name='Gate Starter', email='g@x.org', subscription_plan=plan, subscription_status='active')

    @require_plan_feature('analytics')
    def view(request):
        from django.http import HttpResponse
        return HttpResponse('ok')

    resp = view(_req(request_factory, org))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_require_plan_feature_allows_when_present(request_factory):
    plan = SubscriptionPlan.objects.create(slug='gate-team', name='T', tier='team', has_analytics=True)
    org = Organization.objects.create(name='Gate Team', email='t@x.org', subscription_plan=plan, subscription_status='active')

    @require_plan_feature('analytics')
    def view(request):
        from django.http import HttpResponse
        return HttpResponse('ok')

    resp = view(_req(request_factory, org))
    assert resp.status_code == 200


def _member(org):
    u = User.objects.create_user(username=f'm{org.id}@x.org', email=f'm{org.id}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner', can_view_analytics=True)
    u.default_organization = org; u.save()
    return u


@pytest.mark.django_db
def test_starter_org_blocked_from_analytics(client):
    plan = SubscriptionPlan.objects.create(slug='s2', name='S', tier='starter', has_analytics=False)
    org = Organization.objects.create(name='S2', email='s2@x.org', slug='s2-church', subscription_plan=plan, subscription_status='active')
    client.force_login(_member(org))
    resp = client.get(reverse('analytics_dashboard'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_ministry_org_allowed_into_analytics(client):
    plan = SubscriptionPlan.objects.create(slug='m2', name='M', tier='ministry', has_analytics=True)
    org = Organization.objects.create(name='M2', email='m2@x.org', slug='m2-church', subscription_plan=plan, subscription_status='active')
    client.force_login(_member(org))
    resp = client.get(reverse('analytics_dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_starter_org_cannot_change_branding(client):
    plan = SubscriptionPlan.objects.create(slug='s4', name='S', tier='starter', has_custom_branding=False)
    org = Organization.objects.create(name='S4', email='s4@x.org', slug='s4-church', subscription_plan=plan, subscription_status='active')
    u = User.objects.create_user(username='s4o@x.org', email='s4o@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner', can_manage_settings=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    client.post(reverse('org_settings'), {'name': 'S4', 'email': 's4@x.org', 'ai_assistant_name': 'Hacked'})
    org.refresh_from_db()
    assert org.ai_assistant_name != 'Hacked'


@pytest.mark.django_db
def test_beta_org_allowed_into_analytics(client):
    # Beta orgs are grandfathered to full access even if their plan lacks the flag.
    plan = SubscriptionPlan.objects.create(slug='beta-low', name='Low', tier='starter', has_analytics=False)
    org = Organization.objects.create(name='Beta Church', email='beta@x.org', slug='beta-church-gate',
                                      subscription_plan=plan, subscription_status='beta')
    client.force_login(_member(org))
    resp = client.get(reverse('analytics_dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_starter_org_blocked_from_care(client):
    plan = SubscriptionPlan.objects.create(slug='s-care', name='S', tier='starter', has_care_insights=False)
    org = Organization.objects.create(name='SC', email='sc@x.org', slug='sc-church',
                                      subscription_plan=plan, subscription_status='active')
    client.force_login(_member(org))
    resp = client.get(reverse('care_dashboard'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_team_org_allowed_into_care(client):
    plan = SubscriptionPlan.objects.create(slug='t-care', name='T', tier='team', has_care_insights=True)
    org = Organization.objects.create(name='TC', email='tc@x.org', slug='tc-church',
                                      subscription_plan=plan, subscription_status='active')
    client.force_login(_member(org))
    resp = client.get(reverse('care_dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_entitled_org_can_change_branding(client):
    plan = SubscriptionPlan.objects.create(slug='m-brand', name='M', tier='ministry', has_custom_branding=True)
    org = Organization.objects.create(name='MB', email='mb@x.org', slug='mb-church',
                                      subscription_plan=plan, subscription_status='active')
    u = User.objects.create_user(username='mbo@x.org', email='mbo@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner', can_manage_settings=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    client.post(reverse('org_settings'), {'name': 'MB', 'email': 'mb@x.org', 'ai_assistant_name': 'Custom Bot'})
    org.refresh_from_db()
    assert org.ai_assistant_name == 'Custom Bot'
