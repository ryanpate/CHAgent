"""
Tests for multi-tenant model isolation.

These tests verify that all tenant-scoped models properly isolate data
between organizations. Each test creates data in both organizations
and verifies that querying with organization filters returns only
the correct organization's data.

CRITICAL: If any of these tests fail, it indicates a potential data leak
between tenants - this is a security vulnerability that must be fixed
before production deployment.
"""
import pytest
from django.db.models import Q

from core.models import (
    Organization,
    OrganizationMembership,
    Volunteer,
    Interaction,
    ChatMessage,
    ConversationContext,
    FollowUp,
    ResponseFeedback,
    LearnedCorrection,
    ExtractedKnowledge,
    QueryPattern,
    ReportCache,
    VolunteerInsight,
    Announcement,
    Channel,
    ChannelMessage,
    DirectMessage,
    Project,
    Task,
    TaskComment,
    TaskChecklist,
    TaskTemplate,
)


class TestVolunteerIsolation:
    """Test that Volunteer model properly isolates by organization."""

    def test_volunteers_filtered_by_organization(self, both_orgs_data):
        """Volunteers should only be visible to their own organization."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        # Query volunteers for Alpha org
        alpha_volunteers = Volunteer.objects.filter(organization=alpha['organization'])
        assert alpha_volunteers.count() >= 1
        assert all(v.organization == alpha['organization'] for v in alpha_volunteers)

        # Query volunteers for Beta org
        beta_volunteers = Volunteer.objects.filter(organization=beta['organization'])
        assert beta_volunteers.count() >= 1
        assert all(v.organization == beta['organization'] for v in beta_volunteers)

        # Verify no overlap
        alpha_ids = set(alpha_volunteers.values_list('id', flat=True))
        beta_ids = set(beta_volunteers.values_list('id', flat=True))
        assert alpha_ids.isdisjoint(beta_ids), "Volunteer IDs should not overlap between orgs"

    def test_volunteer_cannot_be_reassigned_to_different_org(self, volunteer_alpha, org_beta):
        """
        Test that we can detect if a volunteer's org is changed.

        Note: This tests awareness, not prevention (which should be handled
        at the application layer).
        """
        original_org = volunteer_alpha.organization

        # Attempting to change org should be detectable
        volunteer_alpha.organization = org_beta
        # Don't save - just verify the change is detectable
        assert volunteer_alpha.organization != original_org

        # Restore original
        volunteer_alpha.organization = original_org

    def test_alpha_cannot_see_beta_volunteers(self, both_orgs_data):
        """Alpha organization should never see Beta's volunteers."""
        alpha_org = both_orgs_data['alpha']['organization']
        beta_volunteer = both_orgs_data['beta']['volunteer']

        # This is the CORRECT way to query - with org filter
        alpha_volunteers = Volunteer.objects.filter(organization=alpha_org)

        # Beta's volunteer should NOT appear in Alpha's query
        assert beta_volunteer not in alpha_volunteers
        assert not alpha_volunteers.filter(id=beta_volunteer.id).exists()


class TestInteractionIsolation:
    """Test that Interaction model properly isolates by organization."""

    def test_interactions_filtered_by_organization(self, both_orgs_data):
        """Interactions should only be visible to their own organization."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_interactions = Interaction.objects.filter(organization=alpha['organization'])
        beta_interactions = Interaction.objects.filter(organization=beta['organization'])

        # Each org has at least one interaction
        assert alpha_interactions.count() >= 1
        assert beta_interactions.count() >= 1

        # No overlap
        alpha_ids = set(alpha_interactions.values_list('id', flat=True))
        beta_ids = set(beta_interactions.values_list('id', flat=True))
        assert alpha_ids.isdisjoint(beta_ids)

    def test_interaction_volunteers_are_org_scoped(self, both_orgs_data):
        """Interactions should only link to volunteers in the same organization."""
        alpha_interaction = both_orgs_data['alpha']['interaction']
        beta_volunteer = both_orgs_data['beta']['volunteer']

        # Alpha's interaction should not have Beta's volunteer
        assert beta_volunteer not in alpha_interaction.volunteers.all()

        # All volunteers in the interaction should be from the same org
        for volunteer in alpha_interaction.volunteers.all():
            assert volunteer.organization == alpha_interaction.organization


class TestFollowUpIsolation:
    """Test that FollowUp model properly isolates by organization."""

    def test_followups_filtered_by_organization(self, both_orgs_data):
        """Follow-ups should only be visible to their own organization."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_followups = FollowUp.objects.filter(organization=alpha['organization'])
        beta_followups = FollowUp.objects.filter(organization=beta['organization'])

        assert alpha_followups.count() >= 1
        assert beta_followups.count() >= 1

        # No overlap
        alpha_ids = set(alpha_followups.values_list('id', flat=True))
        beta_ids = set(beta_followups.values_list('id', flat=True))
        assert alpha_ids.isdisjoint(beta_ids)

    def test_followup_volunteer_is_org_scoped(self, both_orgs_data):
        """Follow-up's volunteer should be from the same organization."""
        alpha_followup = both_orgs_data['alpha']['followup']

        # The volunteer linked to this follow-up should be from the same org
        if alpha_followup.volunteer:
            assert alpha_followup.volunteer.organization == alpha_followup.organization


class TestAnnouncementIsolation:
    """Test that Announcement model properly isolates by organization."""

    def test_announcements_filtered_by_organization(self, both_orgs_data):
        """Announcements should only be visible to their own organization."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_announcements = Announcement.objects.filter(organization=alpha['organization'])
        beta_announcements = Announcement.objects.filter(organization=beta['organization'])

        assert alpha_announcements.count() >= 1
        assert beta_announcements.count() >= 1

        # Verify content is different (sanity check)
        alpha_titles = set(alpha_announcements.values_list('title', flat=True))
        beta_titles = set(beta_announcements.values_list('title', flat=True))
        assert alpha_titles.isdisjoint(beta_titles), "Test data should have different titles"

    def test_alpha_cannot_see_beta_announcements(self, both_orgs_data):
        """Alpha organization should never see Beta's announcements."""
        alpha_org = both_orgs_data['alpha']['organization']
        beta_announcement = both_orgs_data['beta']['announcement']

        alpha_announcements = Announcement.objects.filter(organization=alpha_org)
        assert beta_announcement not in alpha_announcements


class TestChannelIsolation:
    """Test that Channel model properly isolates by organization."""

    def test_channels_filtered_by_organization(self, both_orgs_data):
        """Channels should only be visible to their own organization."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_channels = Channel.objects.filter(organization=alpha['organization'])
        beta_channels = Channel.objects.filter(organization=beta['organization'])

        assert alpha_channels.count() >= 1
        assert beta_channels.count() >= 1

        # No overlap in slugs (slugs are unique within org, but could technically
        # be same across orgs - that's fine as long as they're separate records)
        alpha_ids = set(alpha_channels.values_list('id', flat=True))
        beta_ids = set(beta_channels.values_list('id', flat=True))
        assert alpha_ids.isdisjoint(beta_ids)

    def test_alpha_cannot_access_beta_channel_by_slug(self, both_orgs_data):
        """
        Even if Alpha knows Beta's channel slug, they shouldn't see it
        when filtering by organization.
        """
        alpha_org = both_orgs_data['alpha']['organization']
        beta_channel = both_orgs_data['beta']['channel']

        # Try to access Beta's channel with Alpha's org filter
        result = Channel.objects.filter(
            organization=alpha_org,
            slug=beta_channel.slug
        )
        assert not result.exists(), "Alpha should not see Beta's channel"


class TestProjectIsolation:
    """Test that Project model properly isolates by organization."""

    def test_projects_filtered_by_organization(self, both_orgs_data):
        """Projects should only be visible to their own organization."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_projects = Project.objects.filter(organization=alpha['organization'])
        beta_projects = Project.objects.filter(organization=beta['organization'])

        assert alpha_projects.count() >= 1
        assert beta_projects.count() >= 1

        alpha_ids = set(alpha_projects.values_list('id', flat=True))
        beta_ids = set(beta_projects.values_list('id', flat=True))
        assert alpha_ids.isdisjoint(beta_ids)

    def test_project_owner_is_org_member(self, both_orgs_data):
        """Project owner should be a member of the project's organization."""
        alpha_project = both_orgs_data['alpha']['project']

        if alpha_project.owner:
            # Owner should have membership in the project's org
            membership_exists = OrganizationMembership.objects.filter(
                user=alpha_project.owner,
                organization=alpha_project.organization,
                is_active=True
            ).exists()
            assert membership_exists, "Project owner should be org member"


class TestChatMessageIsolation:
    """Test that ChatMessage model properly isolates by organization."""

    @pytest.fixture
    def chat_messages(self, both_orgs_data):
        """Create chat messages for both organizations."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_msg = ChatMessage.objects.create(
            organization=alpha['organization'],
            user=alpha['owner'],
            session_id='alpha-session-123',
            role='user',
            content='Hello from Alpha Church!'
        )

        beta_msg = ChatMessage.objects.create(
            organization=beta['organization'],
            user=beta['owner'],
            session_id='beta-session-456',
            role='user',
            content='Hello from Beta Church!'
        )

        return {'alpha': alpha_msg, 'beta': beta_msg}

    def test_chat_messages_filtered_by_organization(self, both_orgs_data, chat_messages):
        """Chat messages should only be visible to their own organization."""
        alpha_org = both_orgs_data['alpha']['organization']
        beta_org = both_orgs_data['beta']['organization']

        alpha_messages = ChatMessage.objects.filter(organization=alpha_org)
        beta_messages = ChatMessage.objects.filter(organization=beta_org)

        assert alpha_messages.count() >= 1
        assert beta_messages.count() >= 1

        # Alpha's messages should not include Beta's
        assert chat_messages['beta'] not in alpha_messages
        assert chat_messages['alpha'] not in beta_messages


class TestExtractedKnowledgeIsolation:
    """Test that ExtractedKnowledge model properly isolates by organization."""

    @pytest.fixture
    def knowledge_entries(self, both_orgs_data):
        """Create extracted knowledge for both organizations."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_knowledge = ExtractedKnowledge.objects.create(
            organization=alpha['organization'],
            volunteer=alpha['volunteer'],
            knowledge_type='hobby',
            key='favorite_activity',
            value='Playing guitar',
            confidence='high',
            is_verified=True,
            is_current=True,
        )

        beta_knowledge = ExtractedKnowledge.objects.create(
            organization=beta['organization'],
            volunteer=beta['volunteer'],
            knowledge_type='hobby',
            key='favorite_activity',
            value='Singing',
            confidence='high',
            is_verified=True,
            is_current=True,
        )

        return {'alpha': alpha_knowledge, 'beta': beta_knowledge}

    def test_knowledge_filtered_by_organization(self, both_orgs_data, knowledge_entries):
        """Extracted knowledge should only be visible to their own organization."""
        alpha_org = both_orgs_data['alpha']['organization']

        alpha_knowledge = ExtractedKnowledge.objects.filter(organization=alpha_org)

        assert knowledge_entries['alpha'] in alpha_knowledge
        assert knowledge_entries['beta'] not in alpha_knowledge


class TestVolunteerInsightIsolation:
    """Test that VolunteerInsight model properly isolates by organization."""

    @pytest.fixture
    def insights(self, both_orgs_data):
        """Create volunteer insights for both organizations."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_insight = VolunteerInsight.objects.create(
            organization=alpha['organization'],
            volunteer=alpha['volunteer'],
            insight_type='birthday_upcoming',
            priority='low',
            title='Birthday coming up',
            message='Alice has a birthday next week.',
        )

        beta_insight = VolunteerInsight.objects.create(
            organization=beta['organization'],
            volunteer=beta['volunteer'],
            insight_type='no_recent_contact',
            priority='medium',
            title='Bob has been absent',
            message='Bob missed the last 3 services.',
        )

        return {'alpha': alpha_insight, 'beta': beta_insight}

    def test_insights_filtered_by_organization(self, both_orgs_data, insights):
        """Volunteer insights should only be visible to their own organization."""
        alpha_org = both_orgs_data['alpha']['organization']

        alpha_insights = VolunteerInsight.objects.filter(organization=alpha_org)

        assert insights['alpha'] in alpha_insights
        assert insights['beta'] not in alpha_insights


class TestTaskIsolation:
    """Test that Task model properly isolates by organization."""

    @pytest.fixture
    def tasks(self, both_orgs_data):
        """Create tasks for both organizations."""
        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_task = Task.objects.create(
            project=alpha['project'],
            title='Prepare Alpha worship set',
            description='Select songs for Sunday.',
            status='todo',
            priority='high',
            created_by=alpha['owner'],
        )

        beta_task = Task.objects.create(
            project=beta['project'],
            title='Book Beta venue',
            description='Confirm venue for concert.',
            status='in_progress',
            priority='urgent',
            created_by=beta['owner'],
        )

        return {'alpha': alpha_task, 'beta': beta_task}

    def test_tasks_isolated_through_project(self, both_orgs_data, tasks):
        """Tasks should be isolated through their project's organization."""
        alpha_org = both_orgs_data['alpha']['organization']

        # Tasks are accessed through projects, which are org-scoped
        alpha_projects = Project.objects.filter(organization=alpha_org)
        alpha_tasks = Task.objects.filter(project__in=alpha_projects)

        assert tasks['alpha'] in alpha_tasks
        assert tasks['beta'] not in alpha_tasks


class TestReportCacheIsolation:
    """Test that ReportCache model properly isolates by organization."""

    @pytest.fixture
    def cached_reports(self, both_orgs_data):
        """Create cached reports for both organizations."""
        from django.utils import timezone

        alpha = both_orgs_data['alpha']
        beta = both_orgs_data['beta']

        alpha_report = ReportCache.objects.create(
            organization=alpha['organization'],
            report_type='engagement',
            parameters={'month': '2024-01'},
            data={'total_interactions': 150},
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )

        beta_report = ReportCache.objects.create(
            organization=beta['organization'],
            report_type='engagement',
            parameters={'month': '2024-01'},
            data={'total_interactions': 75},
            expires_at=timezone.now() + timezone.timedelta(hours=1),
        )

        return {'alpha': alpha_report, 'beta': beta_report}

    def test_reports_filtered_by_organization(self, both_orgs_data, cached_reports):
        """Cached reports should only be visible to their own organization."""
        alpha_org = both_orgs_data['alpha']['organization']

        alpha_reports = ReportCache.objects.filter(organization=alpha_org)

        assert cached_reports['alpha'] in alpha_reports
        assert cached_reports['beta'] not in alpha_reports

        # Even with same report_type and parameters, orgs get different data
        alpha_data = cached_reports['alpha'].data
        beta_data = cached_reports['beta'].data
        assert alpha_data != beta_data


class TestOrganizationMembershipIsolation:
    """Test that OrganizationMembership properly isolates user access."""

    def test_user_cannot_access_other_org(self, both_orgs_data):
        """A user should only have membership in organizations they belong to."""
        alpha_owner = both_orgs_data['alpha']['owner']
        beta_org = both_orgs_data['beta']['organization']

        # Alpha owner should NOT have membership in Beta org
        has_beta_membership = OrganizationMembership.objects.filter(
            user=alpha_owner,
            organization=beta_org,
            is_active=True
        ).exists()

        assert not has_beta_membership, "Alpha owner should not have Beta membership"

    def test_membership_roles_are_org_specific(self, both_orgs_data):
        """User roles are specific to each organization."""
        alpha_owner = both_orgs_data['alpha']['owner']
        alpha_org = both_orgs_data['alpha']['organization']

        # Get Alpha owner's role in Alpha org
        membership = OrganizationMembership.objects.get(
            user=alpha_owner,
            organization=alpha_org
        )

        assert membership.role == 'owner'
        assert membership.can_manage_users is True
        assert membership.can_manage_billing is True


class TestCrossOrganizationQueries:
    """
    Test that common query patterns don't accidentally leak data.

    These tests simulate real-world query patterns that might accidentally
    expose data from other organizations.
    """

    def test_unfiltered_query_returns_all_orgs(self, both_orgs_data):
        """
        DEMONSTRATION: An unfiltered query WOULD return data from all orgs.

        This test exists to show WHY filtering is critical. In production code,
        we should NEVER use unfiltered queries on tenant-scoped models.
        """
        # This is what NOT to do - it returns ALL volunteers
        all_volunteers = Volunteer.objects.all()

        alpha_volunteer = both_orgs_data['alpha']['volunteer']
        beta_volunteer = both_orgs_data['beta']['volunteer']

        # Unfiltered query includes BOTH orgs - this is the vulnerability
        assert alpha_volunteer in all_volunteers
        assert beta_volunteer in all_volunteers

    def test_pk_lookup_without_org_filter_is_dangerous(self, both_orgs_data):
        """
        DEMONSTRATION: Looking up by PK without org filter can leak data.

        This shows why views must always verify organization ownership,
        not just use object PKs from URLs.
        """
        beta_volunteer = both_orgs_data['beta']['volunteer']

        # If Alpha user knows Beta volunteer's ID, they could access it
        # without an org filter (this is the vulnerability)
        found = Volunteer.objects.filter(pk=beta_volunteer.pk).first()
        assert found is not None  # Dangerous! Alpha could see this.

        # CORRECT approach: Always include org filter
        alpha_org = both_orgs_data['alpha']['organization']
        safe_lookup = Volunteer.objects.filter(
            pk=beta_volunteer.pk,
            organization=alpha_org
        ).first()
        assert safe_lookup is None  # Safe - properly filtered

    def test_search_queries_must_be_org_scoped(self, both_orgs_data):
        """Search/filter queries must include organization scope."""
        alpha_org = both_orgs_data['alpha']['organization']

        # Searching for "Bob" (Beta's volunteer) in Alpha's org
        results = Volunteer.objects.filter(
            organization=alpha_org,
            name__icontains='Bob'
        )

        # Should find nothing - Bob is in Beta's org
        assert results.count() == 0

    def test_related_object_queries_respect_isolation(self, both_orgs_data):
        """Queries through related objects should maintain isolation."""
        alpha_interaction = both_orgs_data['alpha']['interaction']

        # Getting volunteers through interaction's M2M relationship
        volunteers = alpha_interaction.volunteers.all()

        # All volunteers should be from the same org as the interaction
        for volunteer in volunteers:
            assert volunteer.organization == alpha_interaction.organization


class TestBulkOperationIsolation:
    """Test that bulk operations respect tenant boundaries."""

    def test_bulk_update_respects_org_filter(self, both_orgs_data):
        """Bulk updates should only affect the filtered organization."""
        alpha_org = both_orgs_data['alpha']['organization']
        beta_followup = both_orgs_data['beta']['followup']

        original_beta_status = beta_followup.status

        # Bulk update only Alpha's follow-ups
        FollowUp.objects.filter(organization=alpha_org).update(
            status='in_progress'
        )

        # Refresh Beta's follow-up from DB
        beta_followup.refresh_from_db()

        # Beta's follow-up should be unchanged
        assert beta_followup.status == original_beta_status

    def test_bulk_delete_respects_org_filter(self, db, both_orgs_data):
        """Bulk deletes should only affect the filtered organization."""
        from core.models import Announcement

        alpha_org = both_orgs_data['alpha']['organization']
        beta_announcement = both_orgs_data['beta']['announcement']

        # Create a temporary announcement to delete
        temp_announcement = Announcement.objects.create(
            organization=alpha_org,
            title='Temporary Alpha Announcement',
            content='This will be deleted.',
        )

        # Delete only Alpha's temporary announcements
        Announcement.objects.filter(
            organization=alpha_org,
            title__startswith='Temporary'
        ).delete()

        # Verify Beta's announcement still exists
        assert Announcement.objects.filter(pk=beta_announcement.pk).exists()
