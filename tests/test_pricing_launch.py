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


@pytest.mark.django_db
def test_pricing_page_shows_canonical_prices(client):
    resp = client.get('/pricing/')
    assert resp.status_code == 200
    body = resp.content.decode()
    assert '9.99' in body
    assert '39.99' in body
    assert '79.99' in body
    # Visible monthly price must show the canonical .99 figures, not rounded
    assert '$9.99' in body
    assert '$39.99' in body
    assert '$79.99' in body
    # No stale prices from the old seed
    assert '$149' not in body and '149.00' not in body
    assert '$29' not in body and '$79.00' not in body  # old starter/team monthly
    # Yearly toggle shows monthly-equivalent + exact savings (Starter: ~$8.33/mo, save $19.88)
    assert '8.33' in body
    assert '19.88' in body
