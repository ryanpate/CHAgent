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
