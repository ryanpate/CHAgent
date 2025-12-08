# Data migration to create default Cherry Hills organization
# and backfill all existing data

from django.db import migrations
from django.conf import settings


def create_default_organization_and_backfill(apps, schema_editor):
    """
    Create the default Cherry Hills organization and backfill all existing data.
    """
    Organization = apps.get_model('core', 'Organization')
    OrganizationMembership = apps.get_model('core', 'OrganizationMembership')
    SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')
    User = apps.get_model('accounts', 'User')

    # Models to backfill
    Volunteer = apps.get_model('core', 'Volunteer')
    Interaction = apps.get_model('core', 'Interaction')
    ChatMessage = apps.get_model('core', 'ChatMessage')
    ConversationContext = apps.get_model('core', 'ConversationContext')
    FollowUp = apps.get_model('core', 'FollowUp')
    ResponseFeedback = apps.get_model('core', 'ResponseFeedback')
    LearnedCorrection = apps.get_model('core', 'LearnedCorrection')
    ExtractedKnowledge = apps.get_model('core', 'ExtractedKnowledge')
    QueryPattern = apps.get_model('core', 'QueryPattern')
    ReportCache = apps.get_model('core', 'ReportCache')
    VolunteerInsight = apps.get_model('core', 'VolunteerInsight')
    Announcement = apps.get_model('core', 'Announcement')
    Channel = apps.get_model('core', 'Channel')
    Project = apps.get_model('core', 'Project')

    # Check if there's any existing data to migrate
    has_data = (
        Volunteer.objects.exists() or
        Interaction.objects.exists() or
        User.objects.exists()
    )

    if not has_data:
        print("No existing data to migrate. Skipping organization creation.")
        return

    # Create the Ministry plan (unlimited for existing org)
    ministry_plan, _ = SubscriptionPlan.objects.get_or_create(
        slug='ministry',
        defaults={
            'name': 'Ministry',
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
        }
    )

    # Create the default organization for existing Cherry Hills data
    org, created = Organization.objects.get_or_create(
        slug='cherry-hills',
        defaults={
            'name': 'Cherry Hills Church',
            'email': 'worship@cherryhills.org',
            'timezone': 'America/Denver',
            'subscription_plan': ministry_plan,
            'subscription_status': 'active',
            'ai_assistant_name': 'Aria',
            'is_active': True,
        }
    )

    if created:
        print(f"Created organization: {org.name}")
    else:
        print(f"Using existing organization: {org.name}")

    # Create memberships for all existing users
    users = User.objects.all()
    for user in users:
        membership, mem_created = OrganizationMembership.objects.get_or_create(
            user=user,
            organization=org,
            defaults={
                'role': 'admin' if user.is_staff else 'member',
                'can_manage_users': user.is_staff,
                'can_manage_settings': user.is_staff,
                'can_view_analytics': True,
                'can_manage_billing': user.is_superuser,
                'is_active': True,
            }
        )
        if mem_created:
            print(f"  Created membership for user: {user.username}")

    # Backfill all existing data with the organization
    models_to_backfill = [
        (Volunteer, 'volunteers'),
        (Interaction, 'interactions'),
        (ChatMessage, 'chat messages'),
        (ConversationContext, 'conversation contexts'),
        (FollowUp, 'follow-ups'),
        (ResponseFeedback, 'response feedbacks'),
        (LearnedCorrection, 'learned corrections'),
        (ExtractedKnowledge, 'extracted knowledge'),
        (QueryPattern, 'query patterns'),
        (ReportCache, 'report caches'),
        (VolunteerInsight, 'volunteer insights'),
        (Announcement, 'announcements'),
        (Channel, 'channels'),
        (Project, 'projects'),
    ]

    for Model, name in models_to_backfill:
        count = Model.objects.filter(organization__isnull=True).update(organization=org)
        if count > 0:
            print(f"  Backfilled {count} {name}")

    print(f"Migration complete! All data assigned to '{org.name}'")


def reverse_backfill(apps, schema_editor):
    """
    Reverse the backfill - set organization to NULL on all records.
    Note: This does not delete the organization or memberships.
    """
    Organization = apps.get_model('core', 'Organization')

    try:
        org = Organization.objects.get(slug='cherry-hills')
    except Organization.DoesNotExist:
        return

    # Models to clear organization from
    Volunteer = apps.get_model('core', 'Volunteer')
    Interaction = apps.get_model('core', 'Interaction')
    ChatMessage = apps.get_model('core', 'ChatMessage')
    ConversationContext = apps.get_model('core', 'ConversationContext')
    FollowUp = apps.get_model('core', 'FollowUp')
    ResponseFeedback = apps.get_model('core', 'ResponseFeedback')
    LearnedCorrection = apps.get_model('core', 'LearnedCorrection')
    ExtractedKnowledge = apps.get_model('core', 'ExtractedKnowledge')
    QueryPattern = apps.get_model('core', 'QueryPattern')
    ReportCache = apps.get_model('core', 'ReportCache')
    VolunteerInsight = apps.get_model('core', 'VolunteerInsight')
    Announcement = apps.get_model('core', 'Announcement')
    Channel = apps.get_model('core', 'Channel')
    Project = apps.get_model('core', 'Project')

    models = [
        Volunteer, Interaction, ChatMessage, ConversationContext,
        FollowUp, ResponseFeedback, LearnedCorrection, ExtractedKnowledge,
        QueryPattern, ReportCache, VolunteerInsight, Announcement,
        Channel, Project
    ]

    for Model in models:
        Model.objects.filter(organization=org).update(organization=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_multi_tenant_saas'),
        ('accounts', '0002_user_default_organization'),
    ]

    operations = [
        migrations.RunPython(
            create_default_organization_and_backfill,
            reverse_backfill
        ),
    ]
