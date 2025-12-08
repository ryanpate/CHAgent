# Data migration to seed subscription plans

from django.db import migrations


def create_subscription_plans(apps, schema_editor):
    """
    Create the default subscription plans.
    """
    SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')

    plans = [
        {
            'name': 'Starter',
            'slug': 'starter',
            'tier': 'starter',
            'description': 'Perfect for small worship teams getting started',
            'price_monthly_cents': 2900,  # $29/mo
            'price_yearly_cents': 29000,  # $290/yr (2 months free)
            'max_users': 5,
            'max_volunteers': 50,
            'max_ai_queries_monthly': 500,
            'has_pco_integration': True,
            'has_push_notifications': True,
            'has_analytics': False,
            'has_care_insights': False,
            'has_api_access': False,
            'has_custom_branding': False,
            'has_priority_support': False,
            'is_active': True,
            'is_public': True,
            'sort_order': 1,
        },
        {
            'name': 'Team',
            'slug': 'team',
            'tier': 'team',
            'description': 'For growing teams that need more features',
            'price_monthly_cents': 7900,  # $79/mo
            'price_yearly_cents': 79000,  # $790/yr (2 months free)
            'max_users': 15,
            'max_volunteers': 200,
            'max_ai_queries_monthly': 2000,
            'has_pco_integration': True,
            'has_push_notifications': True,
            'has_analytics': True,
            'has_care_insights': True,
            'has_api_access': False,
            'has_custom_branding': False,
            'has_priority_support': False,
            'is_active': True,
            'is_public': True,
            'sort_order': 2,
        },
        {
            'name': 'Ministry',
            'slug': 'ministry',
            'tier': 'ministry',
            'description': 'Unlimited plan for large worship arts teams',
            'price_monthly_cents': 14900,  # $149/mo
            'price_yearly_cents': 149000,  # $1490/yr (2 months free)
            'max_users': -1,  # Unlimited
            'max_volunteers': -1,  # Unlimited
            'max_ai_queries_monthly': -1,  # Unlimited
            'has_pco_integration': True,
            'has_push_notifications': True,
            'has_analytics': True,
            'has_care_insights': True,
            'has_api_access': True,
            'has_custom_branding': True,
            'has_priority_support': True,
            'is_active': True,
            'is_public': True,
            'sort_order': 3,
        },
        {
            'name': 'Enterprise',
            'slug': 'enterprise',
            'tier': 'enterprise',
            'description': 'Custom solutions for multi-campus churches',
            'price_monthly_cents': 0,  # Contact for pricing
            'price_yearly_cents': 0,
            'max_users': -1,  # Unlimited
            'max_volunteers': -1,  # Unlimited
            'max_ai_queries_monthly': -1,  # Unlimited
            'has_pco_integration': True,
            'has_push_notifications': True,
            'has_analytics': True,
            'has_care_insights': True,
            'has_api_access': True,
            'has_custom_branding': True,
            'has_priority_support': True,
            'is_active': True,
            'is_public': False,  # Contact only
            'sort_order': 4,
        },
    ]

    for plan_data in plans:
        SubscriptionPlan.objects.get_or_create(
            slug=plan_data['slug'],
            defaults=plan_data
        )
        print(f"  Created/verified plan: {plan_data['name']}")


def remove_subscription_plans(apps, schema_editor):
    """
    Remove the seeded subscription plans.
    Note: This will fail if organizations are using these plans.
    """
    SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')
    SubscriptionPlan.objects.filter(
        slug__in=['starter', 'team', 'ministry', 'enterprise']
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0017_backfill_cherry_hills_organization'),
    ]

    operations = [
        migrations.RunPython(
            create_subscription_plans,
            remove_subscription_plans
        ),
    ]
