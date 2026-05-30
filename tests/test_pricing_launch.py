import pytest
from core.models import SubscriptionPlan


@pytest.mark.django_db
def test_launch_plan_prices_are_canonical():
    """Seeded plans must match the locked public-launch pricing."""
    expected = {
        'starter': (999, 10000),    # $9.99/mo, $100/yr
        'team': (3999, 40000),      # $39.99/mo, $400/yr
        'ministry': (7999, 80000),  # $79.99/mo, $800/yr
    }
    for slug, (monthly, yearly) in expected.items():
        plan = SubscriptionPlan.objects.get(slug=slug)
        assert plan.price_monthly_cents == monthly, f"{slug} monthly"
        assert plan.price_yearly_cents == yearly, f"{slug} yearly"
