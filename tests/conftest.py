"""
Pytest fixtures for multi-tenant testing.

These fixtures create isolated test data for two organizations,
allowing us to verify that data doesn't leak between tenants.
"""
import pytest
from django.test import Client, RequestFactory, override_settings
from django.contrib.auth import get_user_model

User = get_user_model()


# Disable SSL redirect and other production security settings for tests
@pytest.fixture(autouse=True)
def disable_ssl_redirect(settings):
    """Disable SSL redirect for all tests."""
    settings.SECURE_SSL_REDIRECT = False
    settings.SECURE_PROXY_SSL_HEADER = None
    settings.SESSION_COOKIE_SECURE = False
    settings.CSRF_COOKIE_SECURE = False


@pytest.fixture
def request_factory():
    """Django RequestFactory for creating test requests."""
    return RequestFactory()


@pytest.fixture
def subscription_plan(db):
    """Create a basic subscription plan for testing."""
    from core.models import SubscriptionPlan

    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug='test-plan',
        defaults={
            'name': 'Test Plan',
            'tier': 'team',
            'price_monthly_cents': 3999,
            'price_yearly_cents': 39900,
            'max_users': 15,
            'max_volunteers': 200,
            'max_ai_queries_monthly': 1000,
            'has_pco_integration': True,
            'has_push_notifications': True,
            'has_analytics': True,
            'has_care_insights': True,
            'is_active': True,
        }
    )
    return plan


@pytest.fixture
def org_alpha(db, subscription_plan):
    """
    Create Organization Alpha - first test tenant.

    This organization represents "First Church" and will have its own
    set of users, volunteers, and data.
    """
    from core.models import Organization

    org, _ = Organization.objects.get_or_create(
        slug='alpha-church',
        defaults={
            'name': 'Alpha Church',
            'email': 'admin@alphachurch.org',
            'subscription_plan': subscription_plan,
            'subscription_status': 'active',
            'ai_assistant_name': 'Aria',
            'is_active': True,
        }
    )
    return org


@pytest.fixture
def org_beta(db, subscription_plan):
    """
    Create Organization Beta - second test tenant.

    This organization represents "Second Church" and should have
    completely isolated data from Alpha.
    """
    from core.models import Organization

    org, _ = Organization.objects.get_or_create(
        slug='beta-church',
        defaults={
            'name': 'Beta Church',
            'email': 'admin@betachurch.org',
            'subscription_plan': subscription_plan,
            'subscription_status': 'active',
            'ai_assistant_name': 'Helper',
            'is_active': True,
        }
    )
    return org


@pytest.fixture
def user_alpha_owner(db, org_alpha):
    """Create the owner user for Organization Alpha."""
    from core.models import OrganizationMembership

    user, _ = User.objects.get_or_create(
        username='alpha_owner',
        defaults={
            'email': 'owner@alphachurch.org',
            'display_name': 'Alpha Owner',
        }
    )
    user.set_password('testpass123')
    user.save()

    OrganizationMembership.objects.get_or_create(
        user=user,
        organization=org_alpha,
        defaults={
            'role': 'owner',
            'is_active': True,
            'can_manage_users': True,
            'can_manage_settings': True,
            'can_view_analytics': True,
            'can_manage_billing': True,
        }
    )
    return user


@pytest.fixture
def user_alpha_member(db, org_alpha):
    """Create a regular member user for Organization Alpha."""
    from core.models import OrganizationMembership

    user, _ = User.objects.get_or_create(
        username='alpha_member',
        defaults={
            'email': 'member@alphachurch.org',
            'display_name': 'Alpha Member',
        }
    )
    user.set_password('testpass123')
    user.save()

    OrganizationMembership.objects.get_or_create(
        user=user,
        organization=org_alpha,
        defaults={
            'role': 'member',
            'is_active': True,
            'can_manage_users': False,
            'can_manage_settings': False,
            'can_view_analytics': False,
            'can_manage_billing': False,
        }
    )
    return user


@pytest.fixture
def user_beta_owner(db, org_beta):
    """Create the owner user for Organization Beta."""
    from core.models import OrganizationMembership

    user, _ = User.objects.get_or_create(
        username='beta_owner',
        defaults={
            'email': 'owner@betachurch.org',
            'display_name': 'Beta Owner',
        }
    )
    user.set_password('testpass123')
    user.save()

    OrganizationMembership.objects.get_or_create(
        user=user,
        organization=org_beta,
        defaults={
            'role': 'owner',
            'is_active': True,
            'can_manage_users': True,
            'can_manage_settings': True,
            'can_view_analytics': True,
            'can_manage_billing': True,
        }
    )
    return user


@pytest.fixture
def user_beta_member(db, org_beta):
    """Create a regular member user for Organization Beta."""
    from core.models import OrganizationMembership

    user, _ = User.objects.get_or_create(
        username='beta_member',
        defaults={
            'email': 'member@betachurch.org',
            'display_name': 'Beta Member',
        }
    )
    user.set_password('testpass123')
    user.save()

    OrganizationMembership.objects.get_or_create(
        user=user,
        organization=org_beta,
        defaults={
            'role': 'member',
            'is_active': True,
            'can_manage_users': False,
            'can_manage_settings': False,
            'can_view_analytics': False,
            'can_manage_billing': False,
        }
    )
    return user


@pytest.fixture
def volunteer_alpha(db, org_alpha):
    """Create a volunteer for Organization Alpha."""
    from core.models import Volunteer

    volunteer, _ = Volunteer.objects.get_or_create(
        organization=org_alpha,
        name='Alice Alpha',
        defaults={
            'normalized_name': 'alice alpha',
            'team': 'vocals',
            'planning_center_id': 'pco_alice_alpha',
        }
    )
    return volunteer


@pytest.fixture
def volunteer_beta(db, org_beta):
    """Create a volunteer for Organization Beta."""
    from core.models import Volunteer

    volunteer, _ = Volunteer.objects.get_or_create(
        organization=org_beta,
        name='Bob Beta',
        defaults={
            'normalized_name': 'bob beta',
            'team': 'band',
            'planning_center_id': 'pco_bob_beta',
        }
    )
    return volunteer


@pytest.fixture
def interaction_alpha(db, org_alpha, user_alpha_owner, volunteer_alpha):
    """Create an interaction for Organization Alpha."""
    from core.models import Interaction

    interaction = Interaction.objects.create(
        organization=org_alpha,
        user=user_alpha_owner,
        content='Had a great conversation with Alice about worship.',
        ai_summary='Discussed worship involvement.',
    )
    interaction.volunteers.add(volunteer_alpha)
    return interaction


@pytest.fixture
def interaction_beta(db, org_beta, user_beta_owner, volunteer_beta):
    """Create an interaction for Organization Beta."""
    from core.models import Interaction

    interaction = Interaction.objects.create(
        organization=org_beta,
        user=user_beta_owner,
        content='Talked with Bob about joining the band.',
        ai_summary='Discussed band involvement.',
    )
    interaction.volunteers.add(volunteer_beta)
    return interaction


@pytest.fixture
def followup_alpha(db, org_alpha, user_alpha_owner, volunteer_alpha):
    """Create a follow-up for Organization Alpha."""
    from core.models import FollowUp
    from datetime import date, timedelta

    followup, _ = FollowUp.objects.get_or_create(
        organization=org_alpha,
        volunteer=volunteer_alpha,
        title='Check in with Alice',
        defaults={
            'created_by': user_alpha_owner,
            'assigned_to': user_alpha_owner,
            'description': 'Follow up about worship team interest.',
            'category': 'action_item',
            'priority': 'medium',
            'status': 'pending',
            'follow_up_date': date.today() + timedelta(days=7),
        }
    )
    return followup


@pytest.fixture
def followup_beta(db, org_beta, user_beta_owner, volunteer_beta):
    """Create a follow-up for Organization Beta."""
    from core.models import FollowUp
    from datetime import date, timedelta

    followup, _ = FollowUp.objects.get_or_create(
        organization=org_beta,
        volunteer=volunteer_beta,
        title='Check in with Bob',
        defaults={
            'created_by': user_beta_owner,
            'assigned_to': user_beta_owner,
            'description': 'Follow up about band involvement.',
            'category': 'action_item',
            'priority': 'high',
            'status': 'pending',
            'follow_up_date': date.today() + timedelta(days=3),
        }
    )
    return followup


@pytest.fixture
def announcement_alpha(db, org_alpha, user_alpha_owner):
    """Create an announcement for Organization Alpha."""
    from core.models import Announcement

    announcement, _ = Announcement.objects.get_or_create(
        organization=org_alpha,
        title='Alpha Team Meeting',
        defaults={
            'content': 'Team meeting this Sunday after service.',
            'author': user_alpha_owner,
            'priority': 'normal',
        }
    )
    return announcement


@pytest.fixture
def announcement_beta(db, org_beta, user_beta_owner):
    """Create an announcement for Organization Beta."""
    from core.models import Announcement

    announcement, _ = Announcement.objects.get_or_create(
        organization=org_beta,
        title='Beta Worship Night',
        defaults={
            'content': 'Special worship night next Friday.',
            'author': user_beta_owner,
            'priority': 'important',
        }
    )
    return announcement


@pytest.fixture
def channel_alpha(db, org_alpha, user_alpha_owner):
    """Create a channel for Organization Alpha."""
    from core.models import Channel

    channel, _ = Channel.objects.get_or_create(
        organization=org_alpha,
        slug='alpha-general',
        defaults={
            'name': 'Alpha General',
            'description': 'General discussion for Alpha Church.',
            'is_private': False,
            'created_by': user_alpha_owner,
        }
    )
    return channel


@pytest.fixture
def channel_beta(db, org_beta, user_beta_owner):
    """Create a channel for Organization Beta."""
    from core.models import Channel

    channel, _ = Channel.objects.get_or_create(
        organization=org_beta,
        slug='beta-general',
        defaults={
            'name': 'Beta General',
            'description': 'General discussion for Beta Church.',
            'is_private': False,
            'created_by': user_beta_owner,
        }
    )
    return channel


@pytest.fixture
def project_alpha(db, org_alpha, user_alpha_owner):
    """Create a project for Organization Alpha."""
    from core.models import Project

    project, _ = Project.objects.get_or_create(
        organization=org_alpha,
        name='Alpha Easter Service',
        defaults={
            'description': 'Planning for Easter service at Alpha.',
            'status': 'active',
            'priority': 'high',
            'owner': user_alpha_owner,
        }
    )
    return project


@pytest.fixture
def project_beta(db, org_beta, user_beta_owner):
    """Create a project for Organization Beta."""
    from core.models import Project

    project, _ = Project.objects.get_or_create(
        organization=org_beta,
        name='Beta Christmas Concert',
        defaults={
            'description': 'Planning for Christmas concert at Beta.',
            'status': 'planning',
            'priority': 'medium',
            'owner': user_beta_owner,
        }
    )
    return project


@pytest.fixture
def client_alpha(db, user_alpha_owner, org_alpha):
    """
    Create an authenticated Django test client for Alpha organization.

    This client has the organization set in the session.
    """
    from core.models import OrganizationMembership

    client = Client()
    client.login(username='alpha_owner', password='testpass123')

    # Set organization in session
    session = client.session
    session['organization_id'] = org_alpha.id
    session.save()

    return client


@pytest.fixture
def client_beta(db, user_beta_owner, org_beta):
    """
    Create an authenticated Django test client for Beta organization.

    This client has the organization set in the session.
    """
    client = Client()
    client.login(username='beta_owner', password='testpass123')

    # Set organization in session
    session = client.session
    session['organization_id'] = org_beta.id
    session.save()

    return client


@pytest.fixture
def mock_request_alpha(request_factory, user_alpha_owner, org_alpha):
    """
    Create a mock request object with Alpha organization context.

    Useful for testing views directly without going through the full
    request/response cycle.
    """
    from core.models import OrganizationMembership

    request = request_factory.get('/')
    request.user = user_alpha_owner
    request.organization = org_alpha
    request.membership = OrganizationMembership.objects.get(
        user=user_alpha_owner,
        organization=org_alpha
    )
    request.session = {}
    return request


@pytest.fixture
def mock_request_beta(request_factory, user_beta_owner, org_beta):
    """
    Create a mock request object with Beta organization context.

    Useful for testing views directly without going through the full
    request/response cycle.
    """
    from core.models import OrganizationMembership

    request = request_factory.get('/')
    request.user = user_beta_owner
    request.organization = org_beta
    request.membership = OrganizationMembership.objects.get(
        user=user_beta_owner,
        organization=org_beta
    )
    request.session = {}
    return request


# =============================================================================
# Data Setup Fixtures - Create complete test data for both organizations
# =============================================================================

@pytest.fixture
def full_alpha_data(
    org_alpha,
    user_alpha_owner,
    user_alpha_member,
    volunteer_alpha,
    interaction_alpha,
    followup_alpha,
    announcement_alpha,
    channel_alpha,
    project_alpha,
):
    """
    Fixture that creates a complete set of data for Organization Alpha.

    Returns a dict with all the created objects for easy access in tests.
    """
    return {
        'organization': org_alpha,
        'owner': user_alpha_owner,
        'member': user_alpha_member,
        'volunteer': volunteer_alpha,
        'interaction': interaction_alpha,
        'followup': followup_alpha,
        'announcement': announcement_alpha,
        'channel': channel_alpha,
        'project': project_alpha,
    }


@pytest.fixture
def full_beta_data(
    org_beta,
    user_beta_owner,
    user_beta_member,
    volunteer_beta,
    interaction_beta,
    followup_beta,
    announcement_beta,
    channel_beta,
    project_beta,
):
    """
    Fixture that creates a complete set of data for Organization Beta.

    Returns a dict with all the created objects for easy access in tests.
    """
    return {
        'organization': org_beta,
        'owner': user_beta_owner,
        'member': user_beta_member,
        'volunteer': volunteer_beta,
        'interaction': interaction_beta,
        'followup': followup_beta,
        'announcement': announcement_beta,
        'channel': channel_beta,
        'project': project_beta,
    }


@pytest.fixture
def both_orgs_data(full_alpha_data, full_beta_data):
    """
    Fixture that creates complete data for BOTH organizations.

    This is the primary fixture for isolation tests - it ensures both
    orgs have data, then tests verify they can't see each other's data.
    """
    return {
        'alpha': full_alpha_data,
        'beta': full_beta_data,
    }
