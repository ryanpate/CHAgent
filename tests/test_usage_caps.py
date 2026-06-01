import pytest
from datetime import datetime, timezone as dt_tz
from django.utils import timezone
from core.models import Organization, SubscriptionPlan


def _org(monthly=500, vol=50, used=0):
    plan = SubscriptionPlan.objects.create(
        slug=f'p{monthly}-{vol}-{used}', name='P', tier='team',
        max_ai_queries_monthly=monthly, max_volunteers=vol)
    return Organization.objects.create(
        name='Cap Org', email='c@x.org', subscription_plan=plan,
        subscription_status='active', ai_queries_this_month=used,
        ai_queries_reset_at=timezone.now())


@pytest.mark.django_db
def test_reset_zeros_counter_on_new_month():
    org = _org(used=400)
    org.ai_queries_reset_at = datetime(2025, 5, 1, tzinfo=dt_tz.utc)
    org.save(update_fields=['ai_queries_reset_at'])
    org.reset_ai_usage_if_new_month()
    org.refresh_from_db()
    assert org.ai_queries_this_month == 0


@pytest.mark.django_db
def test_reset_keeps_counter_within_same_month():
    from django.utils import timezone
    org = _org(used=400)
    org.ai_queries_reset_at = timezone.now()
    org.save(update_fields=['ai_queries_reset_at'])
    org.reset_ai_usage_if_new_month()
    org.refresh_from_db()
    assert org.ai_queries_this_month == 400


@pytest.mark.django_db
def test_ai_quota_properties():
    org = _org(monthly=500, used=500)
    assert org.ai_queries_limit == 500
    assert org.ai_queries_remaining == 0
    assert org.ai_quota_exceeded is True
    assert org.ai_quota_approaching is False

    org2 = _org(monthly=500, used=400)
    assert org2.ai_query_usage_pct == 80
    assert org2.ai_quota_approaching is True
    assert org2.ai_quota_exceeded is False
    assert org2.ai_queries_remaining == 100

    org3 = _org(monthly=500, used=399)
    assert org3.ai_quota_approaching is False


@pytest.mark.django_db
def test_unlimited_and_no_plan_never_gated():
    unlimited = _org(monthly=-1, used=99999)
    assert unlimited.ai_quota_exceeded is False
    assert unlimited.ai_quota_approaching is False
    no_plan = Organization.objects.create(name='NP', email='np@x.org',
                                          subscription_status='active', ai_queries_this_month=99999)
    assert no_plan.ai_quota_exceeded is False
    assert no_plan.ai_quota_approaching is False


@pytest.mark.django_db
def test_volunteer_limit_properties():
    from core.models import Volunteer
    org = _org(vol=2)
    for i in range(3):
        Volunteer.objects.create(organization=org, name=f'V{i}')
    assert org.volunteer_limit == 2
    assert org.volunteer_limit_exceeded is True
    assert org.volunteer_usage == (3, 2)

    org_ok = _org(vol=50)
    assert org_ok.volunteer_limit_exceeded is False

    unlimited = _org(vol=-1)
    Volunteer.objects.create(organization=unlimited, name='x')
    assert unlimited.volunteer_limit_exceeded is False


from accounts.models import User

@pytest.mark.django_db
def test_query_agent_blocks_when_over_limit():
    from core.agent import query_agent
    org = _org(monthly=500, used=500)
    user = User.objects.create_user(username='q@x.org', email='q@x.org', password='supersecret1')
    before = org.ai_queries_this_month
    result = query_agent("Who is serving Sunday?", user, "sess-1", organization=org)
    assert 'limit' in result.lower()
    assert 'upgrade' in result.lower() or 'billing' in result.lower()
    org.refresh_from_db()
    assert org.ai_queries_this_month == before  # blocked before any Claude call -> no increment

@pytest.mark.django_db
def test_query_agent_guard_skipped_when_not_exceeded():
    # The guard's exact condition must be False for under-limit and unlimited orgs.
    under = _org(monthly=500, used=10)
    unlimited = _org(monthly=-1, used=99999)
    assert under.ai_quota_exceeded is False
    assert unlimited.ai_quota_exceeded is False


from django.urls import reverse
from core.models import OrganizationMembership

def _login(client, org):
    u = User.objects.create_user(username=f'm{org.id}@x.org', email=f'm{org.id}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner')
    u.default_organization = org; u.save()
    client.force_login(u)
    return u

@pytest.mark.django_db
def test_dashboard_shows_ai_and_volunteer_banners(client):
    from core.models import Volunteer
    org = _org(monthly=500, used=500, vol=2)
    org.stripe_subscription_id = 'sub_x'; org.save()
    for i in range(3):
        Volunteer.objects.create(organization=org, name=f'V{i}')
    _login(client, org)
    body = client.get(reverse('dashboard')).content.decode()
    assert 'AI queries this month' in body
    assert 'plan includes' in body

@pytest.mark.django_db
def test_dashboard_no_banners_when_within_limits(client):
    org = _org(monthly=500, used=10, vol=50)
    org.stripe_subscription_id = 'sub_x'; org.save()
    _login(client, org)
    body = client.get(reverse('dashboard')).content.decode()
    assert 'AI queries this month' not in body
    assert 'plan includes' not in body
