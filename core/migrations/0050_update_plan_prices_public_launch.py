from django.db import migrations

NEW_PRICES = {
    'starter':  {'price_monthly_cents': 999,  'price_yearly_cents': 10000},
    'team':     {'price_monthly_cents': 3999, 'price_yearly_cents': 40000},
    'ministry': {'price_monthly_cents': 7999, 'price_yearly_cents': 80000},
}
OLD_PRICES = {
    'starter':  {'price_monthly_cents': 2900,  'price_yearly_cents': 29000},
    'team':     {'price_monthly_cents': 7900,  'price_yearly_cents': 79000},
    'ministry': {'price_monthly_cents': 14900, 'price_yearly_cents': 149000},
}


def apply_prices(prices):
    def _run(apps, schema_editor):
        SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')
        for slug, fields in prices.items():
            SubscriptionPlan.objects.filter(slug=slug).update(**fields)
    return _run


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0049_notificationpreference_studio_builds_and_more'),
    ]
    operations = [
        migrations.RunPython(apply_prices(NEW_PRICES), apply_prices(OLD_PRICES)),
    ]
