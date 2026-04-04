"""
Tests for Phase 1: Conversation-First Tasks.

Covers decision-marking on comments, read-state tracking, task watchers,
and notification preference extensions.
"""
import pytest
from django.utils import timezone
from django.urls import reverse


@pytest.mark.django_db
class TestTaskCommentDecision:
    """Tests for marking TaskComments as decisions."""

    def test_task_comment_has_is_decision_field(self, user_alpha_owner, org_alpha):
        """TaskComment should have is_decision boolean defaulting to False."""
        from core.models import Project, Task, TaskComment

        project = Project.objects.create(
            organization=org_alpha,
            name='Test Project',
            owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project,
            title='Test Task',
            created_by=user_alpha_owner,
        )
        comment = TaskComment.objects.create(
            task=task,
            author=user_alpha_owner,
            content='We decided to go with option A.',
        )

        assert comment.is_decision is False
        assert comment.decision_marked_by is None
        assert comment.decision_marked_at is None

    def test_mark_comment_as_decision(self, user_alpha_owner, org_alpha):
        """Marking a comment as decision sets all three fields."""
        from core.models import Project, Task, TaskComment

        project = Project.objects.create(
            organization=org_alpha,
            name='Test Project',
            owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project,
            title='Test Task',
            created_by=user_alpha_owner,
        )
        comment = TaskComment.objects.create(
            task=task,
            author=user_alpha_owner,
            content='Decision text',
        )

        comment.is_decision = True
        comment.decision_marked_by = user_alpha_owner
        comment.decision_marked_at = timezone.now()
        comment.save()

        comment.refresh_from_db()
        assert comment.is_decision is True
        assert comment.decision_marked_by == user_alpha_owner
        assert comment.decision_marked_at is not None
