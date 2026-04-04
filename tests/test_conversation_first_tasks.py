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


@pytest.mark.django_db
class TestTaskWatcher:
    """Tests for task watcher subscriptions."""

    def test_create_watcher(self, user_alpha_owner, user_alpha_member, org_alpha):
        """Any user can watch a task they are not assigned to."""
        from core.models import Project, Task, TaskWatcher

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

        watcher = TaskWatcher.objects.create(user=user_alpha_member, task=task)

        assert watcher.user == user_alpha_member
        assert watcher.task == task
        assert task.watchers.count() == 1

    def test_watcher_unique_per_user_task(self, user_alpha_member, user_alpha_owner, org_alpha):
        """A user can only watch a task once."""
        from django.db import IntegrityError
        from core.models import Project, Task, TaskWatcher

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

        TaskWatcher.objects.create(user=user_alpha_member, task=task)
        with pytest.raises(IntegrityError):
            TaskWatcher.objects.create(user=user_alpha_member, task=task)

    def test_is_watched_by_method(self, user_alpha_owner, user_alpha_member, org_alpha):
        """Task.is_watched_by(user) returns True/False."""
        from core.models import Project, Task, TaskWatcher

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

        assert task.is_watched_by(user_alpha_member) is False
        TaskWatcher.objects.create(user=user_alpha_member, task=task)
        assert task.is_watched_by(user_alpha_member) is True


@pytest.mark.django_db
class TestNotificationPreferenceExtensions:
    """Tests for new task-related notification preference fields."""

    def test_task_notification_preferences_default_values(self, user_alpha_owner):
        """New preference fields default to sensible values."""
        from core.models import NotificationPreference

        prefs = NotificationPreference.get_or_create_for_user(user_alpha_owner)

        assert prefs.task_comment_on_assigned is True
        assert prefs.task_comment_on_watched is True
        assert prefs.decision_notifications is True


@pytest.mark.django_db
class TestMarkDecisionView:
    """Tests for the mark-as-decision view."""

    def _setup(self, user_owner, org):
        from core.models import Project, Task, TaskComment
        project = Project.objects.create(
            organization=org, name='P', owner=user_owner,
        )
        task = Task.objects.create(
            project=project, title='T', created_by=user_owner,
        )
        comment = TaskComment.objects.create(
            task=task, author=user_owner, content='Decision text'
        )
        return project, task, comment

    def test_mark_as_decision_sets_fields(self, client, user_alpha_owner, org_alpha):
        """POST to mark-decision view flips is_decision=True."""
        from core.models import TaskComment

        _, _, comment = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('task_comment_mark_decision', args=[comment.pk]),
        )

        assert response.status_code in (200, 302)
        comment.refresh_from_db()
        assert comment.is_decision is True
        assert comment.decision_marked_by == user_alpha_owner
        assert comment.decision_marked_at is not None

    def test_unmark_decision_clears_fields(self, client, user_alpha_owner, org_alpha):
        """POST again flips is_decision back to False."""
        from core.models import TaskComment

        _, _, comment = self._setup(user_alpha_owner, org_alpha)
        comment.is_decision = True
        comment.decision_marked_by = user_alpha_owner
        comment.decision_marked_at = timezone.now()
        comment.save()

        client.force_login(user_alpha_owner)
        response = client.post(
            reverse('task_comment_mark_decision', args=[comment.pk]),
        )

        assert response.status_code in (200, 302)
        comment.refresh_from_db()
        assert comment.is_decision is False
        assert comment.decision_marked_by is None
        assert comment.decision_marked_at is None

    def test_mark_decision_denies_non_project_members(
        self, client, user_alpha_owner, user_beta_owner, org_alpha
    ):
        """Users outside the project cannot mark decisions."""
        _, _, comment = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.post(
            reverse('task_comment_mark_decision', args=[comment.pk]),
        )

        assert response.status_code == 403
        comment.refresh_from_db()
        assert comment.is_decision is False


@pytest.mark.django_db
class TestTaskWatchToggle:
    """Tests for the toggle-watch view."""

    def _setup(self, user_owner, org, user_member):
        from core.models import Project, Task
        project = Project.objects.create(
            organization=org, name='P', owner=user_owner,
        )
        project.members.add(user_member)
        task = Task.objects.create(
            project=project, title='T', created_by=user_owner,
        )
        return project, task

    def test_watch_creates_watcher(self, client, user_alpha_owner, user_alpha_member, org_alpha):
        """POST creates a TaskWatcher record when not watching."""
        from core.models import TaskWatcher

        _, task = self._setup(user_alpha_owner, org_alpha, user_alpha_member)
        client.force_login(user_alpha_member)

        response = client.post(reverse('task_toggle_watch', args=[task.pk]))

        assert response.status_code in (200, 302)
        assert TaskWatcher.objects.filter(user=user_alpha_member, task=task).exists()

    def test_unwatch_removes_watcher(self, client, user_alpha_owner, user_alpha_member, org_alpha):
        """POST removes TaskWatcher record when already watching."""
        from core.models import TaskWatcher

        _, task = self._setup(user_alpha_owner, org_alpha, user_alpha_member)
        TaskWatcher.objects.create(user=user_alpha_member, task=task)
        client.force_login(user_alpha_member)

        response = client.post(reverse('task_toggle_watch', args=[task.pk]))

        assert response.status_code in (200, 302)
        assert not TaskWatcher.objects.filter(user=user_alpha_member, task=task).exists()

    def test_watch_denied_for_non_project_member(
        self, client, user_alpha_owner, user_beta_owner, org_alpha
    ):
        """Users outside the project cannot watch its tasks."""
        from core.models import Project, Task, TaskWatcher
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='T', created_by=user_alpha_owner,
        )
        client.force_login(user_beta_owner)

        response = client.post(reverse('task_toggle_watch', args=[task.pk]))

        assert response.status_code == 403
        assert not TaskWatcher.objects.filter(user=user_beta_owner, task=task).exists()


@pytest.mark.django_db
class TestMarkTaskRead:
    """Tests for mark-task-read view."""

    def test_mark_task_read_creates_read_state(
        self, client, user_alpha_owner, user_alpha_member, org_alpha
    ):
        """POST creates a new TaskReadState at current time."""
        from core.models import Project, Task, TaskReadState
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        project.members.add(user_alpha_member)
        task = Task.objects.create(
            project=project, title='T', created_by=user_alpha_owner,
        )
        client.force_login(user_alpha_member)

        response = client.post(reverse('task_mark_read', args=[task.pk]))

        assert response.status_code in (200, 204, 302)
        assert TaskReadState.objects.filter(user=user_alpha_member, task=task).exists()

    def test_mark_task_read_updates_existing(
        self, client, user_alpha_owner, org_alpha
    ):
        """POST updates the last_read_at on existing TaskReadState."""
        from datetime import timedelta
        from core.models import Project, Task, TaskReadState
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='T', created_by=user_alpha_owner,
        )
        old_time = timezone.now() - timedelta(days=1)
        state = TaskReadState.objects.create(
            user=user_alpha_owner, task=task, last_read_at=old_time,
        )
        client.force_login(user_alpha_owner)

        client.post(reverse('task_mark_read', args=[task.pk]))

        state.refresh_from_db()
        assert state.last_read_at > old_time


@pytest.mark.django_db
class TestTaskDetailAutoMarkRead:
    """Verify that viewing the task_detail page updates the user's read state."""

    def test_viewing_task_updates_read_state(self, client, user_alpha_owner, org_alpha):
        """GET on task_detail creates or updates TaskReadState for the viewer."""
        from core.models import Project, Task, TaskReadState
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='T', created_by=user_alpha_owner,
        )
        client.force_login(user_alpha_owner)

        # No read state initially
        assert not TaskReadState.objects.filter(
            user=user_alpha_owner, task=task
        ).exists()

        client.get(reverse('task_detail', args=[project.pk, task.pk]))

        assert TaskReadState.objects.filter(
            user=user_alpha_owner, task=task
        ).exists()

    def test_task_detail_exposes_watch_state_in_context(
        self, client, user_alpha_owner, org_alpha
    ):
        """Response context includes is_watching flag."""
        from core.models import Project, Task, TaskWatcher
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='T', created_by=user_alpha_owner,
        )
        TaskWatcher.objects.create(user=user_alpha_owner, task=task)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('task_detail', args=[project.pk, task.pk]))

        assert response.status_code == 200
        assert response.context['is_watching'] is True


@pytest.mark.django_db
class TestNotifyWatchersOnComment:
    """Verify watchers receive notifications about new comments."""

    def test_watchers_are_notified(
        self, user_alpha_owner, user_alpha_member, org_alpha, monkeypatch
    ):
        """A watcher who is not the author receives a notification."""
        from core.models import (
            Project, Task, TaskComment, TaskWatcher, NotificationPreference,
        )

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        project.members.add(user_alpha_member)
        task = Task.objects.create(
            project=project, title='T', created_by=user_alpha_owner,
        )
        TaskWatcher.objects.create(user=user_alpha_member, task=task)
        NotificationPreference.get_or_create_for_user(user_alpha_member)

        comment = TaskComment.objects.create(
            task=task, author=user_alpha_owner, content='New update'
        )

        notified_users = []

        def fake_send(user, notification_type, title, body, url, data=None, priority='normal'):
            notified_users.append(user)

        monkeypatch.setattr('core.notifications.send_notification_to_user', fake_send)

        from core.notifications import notify_task_comment
        notify_task_comment(comment)

        assert user_alpha_member in notified_users
        assert user_alpha_owner not in notified_users  # author excluded

    def test_watcher_pref_disabled_no_notification(
        self, user_alpha_owner, user_alpha_member, org_alpha, monkeypatch
    ):
        """A watcher with task_comment_on_watched=False is NOT notified."""
        from core.models import (
            Project, Task, TaskComment, TaskWatcher, NotificationPreference,
        )

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        project.members.add(user_alpha_member)
        task = Task.objects.create(
            project=project, title='T', created_by=user_alpha_owner,
        )
        TaskWatcher.objects.create(user=user_alpha_member, task=task)
        prefs = NotificationPreference.get_or_create_for_user(user_alpha_member)
        prefs.task_comment_on_watched = False
        prefs.save()

        comment = TaskComment.objects.create(
            task=task, author=user_alpha_owner, content='Update'
        )

        notified_users = []
        monkeypatch.setattr(
            'core.notifications.send_notification_to_user',
            lambda user, **kwargs: notified_users.append(user)
        )

        from core.notifications import notify_task_comment
        notify_task_comment(comment)

        assert user_alpha_member not in notified_users
