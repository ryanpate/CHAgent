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


@pytest.mark.django_db
class TestTaskReadState:
    """Tests for per-user task read-state tracking."""

    def test_create_read_state(self, user_alpha_owner, org_alpha):
        """TaskReadState records when a user last viewed a task thread."""
        from core.models import Project, Task, TaskReadState

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
        now = timezone.now()

        state = TaskReadState.objects.create(
            user=user_alpha_owner,
            task=task,
            last_read_at=now,
        )

        assert state.user == user_alpha_owner
        assert state.task == task
        assert state.last_read_at == now

    def test_read_state_unique_per_user_task(self, user_alpha_owner, org_alpha):
        """Only one TaskReadState per (user, task) combo."""
        from django.db import IntegrityError
        from core.models import Project, Task, TaskReadState

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

        TaskReadState.objects.create(
            user=user_alpha_owner,
            task=task,
            last_read_at=timezone.now(),
        )
        with pytest.raises(IntegrityError):
            TaskReadState.objects.create(
                user=user_alpha_owner,
                task=task,
                last_read_at=timezone.now(),
            )

    def test_unread_comment_count(self, user_alpha_owner, user_alpha_member, org_alpha):
        """Unread count = comments created after user's last_read_at, excluding own."""
        from core.models import Project, Task, TaskComment, TaskReadState

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

        # User owner views task now
        read_time = timezone.now()
        TaskReadState.objects.create(
            user=user_alpha_owner,
            task=task,
            last_read_at=read_time,
        )

        # Another user posts 2 comments after that
        TaskComment.objects.create(task=task, author=user_alpha_member, content='First')
        TaskComment.objects.create(task=task, author=user_alpha_member, content='Second')
        # Owner's own comment should not count as unread for owner
        TaskComment.objects.create(task=task, author=user_alpha_owner, content='Self')

        from core.models import unread_comment_count_for
        count = unread_comment_count_for(user_alpha_owner, task)
        assert count == 2
