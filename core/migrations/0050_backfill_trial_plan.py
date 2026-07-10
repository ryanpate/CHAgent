"""Card-free trial: trials are created with a plan from now on; backfill
existing plan-less trial orgs (features locked but AI uncapped — both wrong)."""
from django.db import migrations


def backfill_trial_plan(apps, schema_editor):
    Organization = apps.get_model('core', 'Organization')
    SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')
    plan = (
        SubscriptionPlan.objects.filter(is_active=True, tier='team').first()
        or SubscriptionPlan.objects.filter(is_active=True)
        .order_by('price_monthly_cents').first()
    )
    if plan:
        Organization.objects.filter(
            subscription_status='trial', subscription_plan__isnull=True,
        ).update(subscription_plan=plan)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_notificationpreference_studio_builds_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_trial_plan, migrations.RunPython.noop),
    ]
