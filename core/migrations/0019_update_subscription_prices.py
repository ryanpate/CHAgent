# Data migration to update subscription plan prices to match Stripe

from django.db import migrations


def update_subscription_prices(apps, schema_editor):
    """
    Update subscription plan prices to match actual Stripe pricing.

    Pricing:
    - Starter: $9.99/mo, $100/yr
    - Team: $39.99/mo, $400/yr
    - Ministry: $79.99/mo, $800/yr
    """
    SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')

    price_updates = {
        'starter': {
            'price_monthly_cents': 999,    # $9.99/mo
            'price_yearly_cents': 10000,   # $100/yr
        },
        'team': {
            'price_monthly_cents': 3999,   # $39.99/mo
            'price_yearly_cents': 40000,   # $400/yr
        },
        'ministry': {
            'price_monthly_cents': 7999,   # $79.99/mo
            'price_yearly_cents': 80000,   # $800/yr
        },
    }

    for slug, prices in price_updates.items():
        updated = SubscriptionPlan.objects.filter(slug=slug).update(**prices)
        if updated:
            print(f"  Updated {slug} plan: ${prices['price_monthly_cents']/100:.2f}/mo, ${prices['price_yearly_cents']/100:.2f}/yr")


def revert_subscription_prices(apps, schema_editor):
    """
    Revert to original prices (for rollback).
    """
    SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')

    original_prices = {
        'starter': {'price_monthly_cents': 2900, 'price_yearly_cents': 29000},
        'team': {'price_monthly_cents': 7900, 'price_yearly_cents': 79000},
        'ministry': {'price_monthly_cents': 14900, 'price_yearly_cents': 149000},
    }

    for slug, prices in original_prices.items():
        SubscriptionPlan.objects.filter(slug=slug).update(**prices)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_seed_subscription_plans'),
    ]

    operations = [
        migrations.RunPython(
            update_subscription_prices,
            revert_subscription_prices
        ),
    ]
