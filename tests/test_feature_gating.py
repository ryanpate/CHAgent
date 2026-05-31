import pytest
from django.test import RequestFactory
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from core.middleware import require_plan_feature
from core.models import Organization, SubscriptionPlan


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
