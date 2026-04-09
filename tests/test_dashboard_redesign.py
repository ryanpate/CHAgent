"""
Tests for dashboard redesign badge counts in the context processor.
"""
import pytest
from datetime import date, timedelta
from django.test import Client
from django.utils import timezone
from core.models import (
    FollowUp, Task, DirectMessage, Interaction, Project,
    Volunteer, Organization, OrganizationMembership, ChatMessage,
)


@pytest.mark.django_db
class TestBadgeCounts:
    """Test badge count values injected by the organization_context context processor."""

    def test_pending_followup_count_in_context(
        self, client_alpha, user_alpha_owner, org_alpha, volunteer_alpha
    ):
        """Pending followup count should only include pending/in_progress, not completed."""
        FollowUp.objects.create(
            organization=org_alpha,
            created_by=user_alpha_owner,
            assigned_to=user_alpha_owner,
            volunteer=volunteer_alpha,
            title='Pending followup',
            status='pending',
            follow_up_date=date.today() + timedelta(days=3),
        )
        FollowUp.objects.create(
            organization=org_alpha,
            created_by=user_alpha_owner,
            assigned_to=user_alpha_owner,
            volunteer=volunteer_alpha,
            title='Completed followup',
            status='completed',
            follow_up_date=date.today(),
        )

        response = client_alpha.get('/dashboard/')
        assert response.context['pending_followup_count'] == 1

    def test_pending_task_count_in_context(
        self, client_alpha, user_alpha_owner, org_alpha
    ):
        """Pending task count should only include todo/in_progress tasks assigned to user."""
        task_todo = Task.objects.create(
            organization=org_alpha,
            title='Todo task',
            status='todo',
            created_by=user_alpha_owner,
        )
        task_todo.assignees.add(user_alpha_owner)

        task_done = Task.objects.create(
            organization=org_alpha,
            title='Completed task',
            status='completed',
            created_by=user_alpha_owner,
        )
        task_done.assignees.add(user_alpha_owner)

        response = client_alpha.get('/dashboard/')
        assert response.context['pending_task_count'] == 1

    def test_unread_message_count_in_context(
        self, client_alpha, user_alpha_owner, user_alpha_member
    ):
        """Unread message count should only include unread DMs to the user."""
        DirectMessage.objects.create(
            sender=user_alpha_member,
            recipient=user_alpha_owner,
            content='Unread message',
            is_read=False,
        )
        DirectMessage.objects.create(
            sender=user_alpha_member,
            recipient=user_alpha_owner,
            content='Read message',
            is_read=True,
        )

        response = client_alpha.get('/dashboard/')
        assert response.context['unread_message_count'] == 1

    def test_interactions_this_week_in_context(
        self, client_alpha, user_alpha_owner, org_alpha
    ):
        """Interactions this week should count interactions from the last 7 days."""
        Interaction.objects.create(
            organization=org_alpha,
            user=user_alpha_owner,
            content='Recent interaction',
        )

        response = client_alpha.get('/dashboard/')
        assert response.context['interactions_this_week'] == 1

    def test_badge_counts_scoped_to_org(
        self, client_alpha, user_alpha_owner, org_alpha, org_beta,
        user_beta_owner, volunteer_beta
    ):
        """Badge counts should not include data from other organizations."""
        # Create a followup in org_beta assigned to beta owner
        FollowUp.objects.create(
            organization=org_beta,
            created_by=user_beta_owner,
            assigned_to=user_beta_owner,
            volunteer=volunteer_beta,
            title='Beta followup',
            status='pending',
            follow_up_date=date.today() + timedelta(days=3),
        )

        # Alpha user should see 0 pending followups
        response = client_alpha.get('/dashboard/')
        assert response.context['pending_followup_count'] == 0


@pytest.mark.django_db
class TestDashboardView:
    """Test the command center dashboard view at /dashboard/."""

    def test_dashboard_has_no_chat_messages(self, client_alpha):
        """Dashboard context should NOT contain chat_messages anymore."""
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        assert 'chat_messages' not in response.context

    def test_dashboard_has_badge_counts(self, client_alpha):
        """Dashboard context should include all 4 badge count keys from context processor."""
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        assert 'pending_followup_count' in response.context
        assert 'pending_task_count' in response.context
        assert 'unread_message_count' in response.context
        assert 'pending_song_count' in response.context

    def test_dashboard_has_existing_context(self, client_alpha):
        """Dashboard context should still include core stats and lists."""
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        assert 'total_volunteers' in response.context
        assert 'total_interactions' in response.context
        assert 'recent_interactions' in response.context
        assert 'top_volunteers' in response.context

    def test_dashboard_renders_ask_aria_section(self, client_alpha):
        """Dashboard should render the Ask Aria bar with form pointing to /chat/."""
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Ask Aria' in content
        assert 'action="/chat/"' in content

    def test_dashboard_has_followup_summary(self, client_alpha):
        """Dashboard context should include followup_summary string."""
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        assert 'followup_summary' in response.context
        # With no followups, should be 'All caught up'
        assert response.context['followup_summary'] == 'All caught up'

    def test_dashboard_followup_summary_with_due_today(
        self, client_alpha, user_alpha_owner, org_alpha, volunteer_alpha
    ):
        """followup_summary should report items due today."""
        from django.utils import timezone
        FollowUp.objects.create(
            organization=org_alpha,
            created_by=user_alpha_owner,
            assigned_to=user_alpha_owner,
            volunteer=volunteer_alpha,
            title='Due today',
            status='pending',
            follow_up_date=timezone.now().date(),
        )
        response = client_alpha.get('/dashboard/')
        assert '1 due today' in response.context['followup_summary']


@pytest.mark.django_db
class TestChatView:
    """Test the full-page chat view at /chat/."""

    def test_chat_renders_template(self, client_alpha):
        """GET /chat/ should return 200 and include chat_messages in context."""
        response = client_alpha.get('/chat/')
        assert response.status_code == 200
        assert 'chat_messages' in response.context

    def test_chat_with_q_param_passes_initial_message(self, client_alpha):
        """GET /chat/?q=hello+world should pass initial_message to context."""
        response = client_alpha.get('/chat/?q=hello+world')
        assert response.status_code == 200
        assert response.context['initial_message'] == 'hello world'

    def test_chat_sets_session_cookie(self, client_alpha):
        """GET /chat/ should include a session_id in the response context."""
        response = client_alpha.get('/chat/')
        assert response.status_code == 200
        assert response.context['session_id']
        # Session ID should be a non-empty string
        assert len(response.context['session_id']) > 0


@pytest.mark.django_db
class TestSidebar:
    """Test sidebar navigation structure and badges."""

    def test_sidebar_has_chat_link(self, client_alpha):
        """Sidebar should contain a Chat with Aria link pointing to /chat/."""
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        content = response.content.decode()
        assert '/chat/' in content
        assert 'Chat with Aria' in content

    def test_sidebar_has_section_labels(self, client_alpha):
        """Sidebar should have grouped section labels."""
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Core' in content
        assert 'Team' in content
        assert 'Insights' in content

    def test_sidebar_has_followup_badge(
        self, client_alpha, user_alpha_owner, org_alpha, volunteer_alpha
    ):
        """Sidebar should show a badge count for pending follow-ups."""
        FollowUp.objects.create(
            organization=org_alpha,
            created_by=user_alpha_owner,
            assigned_to=user_alpha_owner,
            volunteer=volunteer_alpha,
            title='Badge test followup',
            status='pending',
            follow_up_date=date.today() + timedelta(days=3),
        )
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        content = response.content.decode()
        # The badge should show count "1" in a rounded-full element
        assert 'pending_followup_count' in response.context or response.context.get('pending_followup_count', 0) >= 1
        # Check that the badge HTML is rendered with the count
        assert '>1</span>' in content
