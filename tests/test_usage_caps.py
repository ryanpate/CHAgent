import pytest
from datetime import datetime, timezone as dt_tz
from core.models import Organization, SubscriptionPlan


def _org(monthly=500, vol=50, used=0):
    plan = SubscriptionPlan.objects.create(
        slug=f'p{monthly}-{vol}-{used}', name='P', tier='team',
        max_ai_queries_monthly=monthly, max_volunteers=vol)
    return Organization.objects.create(
        name='Cap Org', email='c@x.org', subscription_plan=plan,
        subscription_status='active', ai_queries_this_month=used)


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
