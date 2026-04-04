# Phase 1: Conversation-First Tasks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the task detail UI so comments are the primary content, and add unread tracking, decision-marking, and task-watching to eliminate the "comments get lost" pain point.

**Architecture:** Additive changes to existing `Task`, `TaskComment`, and `NotificationPreference` models. Two new models: `TaskReadState` (per-user last-read timestamp per task) and `TaskWatcher` (subscribe to tasks you're not assigned to). Task detail template redesigned to show conversation front-and-center. Notification system extended to notify watchers.

**Tech Stack:** Django 5.x, PostgreSQL, pytest, HTMX, Tailwind CSS. Multi-tenant via TenantMiddleware (all data org-scoped).

**Related Spec:** `docs/superpowers/specs/2026-04-04-todoist-replacement-design.md`

---

## File Structure

**Create:**
- `core/migrations/00XX_conversation_first_tasks.py` — single migration for all Phase 1 model changes
- `tests/test_conversation_first_tasks.py` — new test file for Phase 1 features

**Modify:**
- `core/models.py` — add fields to TaskComment + NotificationPreference, add TaskReadState + TaskWatcher models
- `core/views.py` — add decision-mark, watch-toggle, mark-read views; update task_detail context
- `core/urls.py` — wire new URL routes
- `core/notifications.py` — extend `notify_task_comment` to include watchers
- `templates/core/comms/task_detail.html` — redesign to conversation-first layout
- `templates/core/partials/task_comment.html` — add decision badge and mark-decision button
- `templates/core/comms/project_detail.html` — add unread badges to task cards

---

## Task 1: Add decision fields to TaskComment model

**Files:**
- Modify: `core/models.py:2640-2676` (TaskComment class)
- Test: `tests/test_conversation_first_tasks.py` (new file)

- [ ] **Step 1: Create test file with failing test for is_decision field**

Create `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskCommentDecision -v`
Expected: FAIL with `AttributeError: 'TaskComment' object has no attribute 'is_decision'`

- [ ] **Step 3: Add fields to TaskComment model**

Edit `core/models.py` — in the `TaskComment` class (around line 2666, after `mentioned_users` field and before `created_at`), add:

```python
    # Decision marking
    is_decision = models.BooleanField(
        default=False,
        help_text="This comment captures a decision made by the team"
    )
    decision_marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='decisions_marked',
        help_text="User who marked this comment as a decision"
    )
    decision_marked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this comment was marked as a decision"
    )
```

- [ ] **Step 4: Create and apply migration**

Run: `python manage.py makemigrations core --name conversation_first_tasks`
Then: `python manage.py migrate core`
Expected: Migration created, applied successfully.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskCommentDecision -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_conversation_first_tasks.py
git commit -m "feat(tasks): add decision-marking fields to TaskComment"
```

---

## Task 2: Create TaskReadState model

**Files:**
- Modify: `core/models.py` (add new model after TaskComment)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing tests for TaskReadState**

Append to `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskReadState -v`
Expected: FAIL with `ImportError: cannot import name 'TaskReadState'`

- [ ] **Step 3: Add TaskReadState model**

Edit `core/models.py` — add this class AFTER the `TaskComment` class (before `TaskChecklist`):

```python
class TaskReadState(models.Model):
    """
    Per-user tracking of when a user last viewed a task's comment thread.
    Used to compute unread comment counts and drive badge indicators.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='task_read_states'
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='read_states'
    )
    last_read_at = models.DateTimeField()

    class Meta:
        unique_together = ('user', 'task')
        verbose_name = 'Task Read State'
        verbose_name_plural = 'Task Read States'
        indexes = [
            models.Index(fields=['user', 'task']),
        ]

    def __str__(self):
        return f"{self.user.username} read {self.task.title} at {self.last_read_at}"


def unread_comment_count_for(user, task):
    """
    Count comments on `task` that `user` has not seen.
    A comment counts as unread if it was created after user's last_read_at
    and was not authored by user. If no read-state exists, all non-self
    comments count as unread.
    """
    try:
        state = TaskReadState.objects.get(user=user, task=task)
        last_read = state.last_read_at
    except TaskReadState.DoesNotExist:
        last_read = None

    qs = task.comments.exclude(author=user)
    if last_read is not None:
        qs = qs.filter(created_at__gt=last_read)
    return qs.count()
```

- [ ] **Step 4: Create and apply migration**

Run: `python manage.py makemigrations core`
Then: `python manage.py migrate core`
Expected: Migration adds TaskReadState table.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskReadState -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_conversation_first_tasks.py
git commit -m "feat(tasks): add TaskReadState model for unread tracking"
```

---

## Task 3: Create TaskWatcher model

**Files:**
- Modify: `core/models.py` (add model after TaskReadState)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing tests for TaskWatcher**

Append to `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskWatcher -v`
Expected: FAIL with `ImportError: cannot import name 'TaskWatcher'`

- [ ] **Step 3: Add TaskWatcher model and Task.is_watched_by method**

Edit `core/models.py` — add this class AFTER `TaskReadState` (before `TaskChecklist`):

```python
class TaskWatcher(models.Model):
    """
    Users subscribed to a task they are not assigned to.
    Watchers receive notifications for new comments and decisions.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='watched_tasks'
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='watchers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'task')
        verbose_name = 'Task Watcher'
        verbose_name_plural = 'Task Watchers'

    def __str__(self):
        return f"{self.user.username} watches {self.task.title}"
```

Then edit the `Task` class (around line 2595, after the `has_subtasks` property) and add:

```python
    def is_watched_by(self, user):
        """Check if given user is watching this task."""
        if not user or not user.is_authenticated:
            return False
        return self.watchers.filter(user=user).exists()
```

- [ ] **Step 4: Create and apply migration**

Run: `python manage.py makemigrations core`
Then: `python manage.py migrate core`
Expected: Migration adds TaskWatcher table.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskWatcher -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_conversation_first_tasks.py
git commit -m "feat(tasks): add TaskWatcher model for task subscriptions"
```

---

## Task 4: Extend NotificationPreference with task-specific toggles

**Files:**
- Modify: `core/models.py:3205-3244` (NotificationPreference class)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing test for new preference fields**

Append to `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_first_tasks.py::TestNotificationPreferenceExtensions -v`
Expected: FAIL with `AttributeError: 'NotificationPreference' object has no attribute 'task_comment_on_assigned'`

- [ ] **Step 3: Add fields to NotificationPreference model**

Edit `core/models.py` — in the `NotificationPreference` class (around line 3228, after `followup_reminders` and before `song_submissions`), add:

```python
    # Task-related notifications
    task_comment_on_assigned = models.BooleanField(
        default=True,
        help_text="Notify me about new comments on tasks I'm assigned to"
    )
    task_comment_on_watched = models.BooleanField(
        default=True,
        help_text="Notify me about new comments on tasks I'm watching"
    )
    decision_notifications = models.BooleanField(
        default=True,
        help_text="Notify me when a decision is marked in a project I'm in"
    )
```

- [ ] **Step 4: Create and apply migration**

Run: `python manage.py makemigrations core`
Then: `python manage.py migrate core`
Expected: Migration adds 3 boolean columns to notification_preference table.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_conversation_first_tasks.py::TestNotificationPreferenceExtensions -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_conversation_first_tasks.py
git commit -m "feat(notifications): add task notification preferences"
```

---

## Task 5: Add view to mark/unmark comment as decision

**Files:**
- Modify: `core/views.py` (add new view after task_comment view around line 3505)
- Modify: `core/urls.py` (add URL route)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing test for decision-marking view**

Append to `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_first_tasks.py::TestMarkDecisionView -v`
Expected: FAIL with `NoReverseMatch: Reverse for 'task_comment_mark_decision' not found`

- [ ] **Step 3: Add the view in core/views.py**

Edit `core/views.py` — add this view after the `task_comment` function (around line 3505):

```python
@login_required
@require_POST
def task_comment_mark_decision(request, pk):
    """Toggle a TaskComment's is_decision flag. Only project members can mark decisions."""
    from .models import TaskComment

    comment = get_object_or_404(TaskComment, pk=pk)
    task = comment.task
    project = task.project

    # Access control: must be project member/owner, or assignee/creator for standalone
    if project:
        if project.owner != request.user and request.user not in project.members.all():
            return HttpResponse('Access denied', status=403)
    else:
        if request.user not in task.assignees.all() and task.created_by != request.user:
            return HttpResponse('Access denied', status=403)

    if comment.is_decision:
        comment.is_decision = False
        comment.decision_marked_by = None
        comment.decision_marked_at = None
    else:
        comment.is_decision = True
        comment.decision_marked_by = request.user
        comment.decision_marked_at = timezone.now()
    comment.save(update_fields=['is_decision', 'decision_marked_by', 'decision_marked_at'])

    if request.headers.get('HX-Request'):
        from .models import MessageReaction
        comment.reaction_list = list(comment.reactions.all()) if hasattr(comment, 'reactions') else []
        return render(request, 'core/partials/task_comment.html', {
            'comment': comment,
            'reaction_emoji_choices': MessageReaction.EMOJI_CHOICES,
        })

    if project:
        return redirect('task_detail', project_pk=project.pk, pk=task.pk)
    return redirect('standalone_task_detail', pk=task.pk)
```

- [ ] **Step 4: Add URL route in core/urls.py**

Edit `core/urls.py` — find the existing `path('tasks/<int:pk>/comment/', ...)` line (around line 103) and add this line after it:

```python
    path('task-comments/<int:pk>/mark-decision/', views.task_comment_mark_decision, name='task_comment_mark_decision'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_conversation_first_tasks.py::TestMarkDecisionView -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/urls.py tests/test_conversation_first_tasks.py
git commit -m "feat(tasks): add view to mark/unmark comments as decisions"
```

---

## Task 6: Add view to toggle task watching

**Files:**
- Modify: `core/views.py` (add new view)
- Modify: `core/urls.py` (add URL route)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing tests for watch toggle**

Append to `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskWatchToggle -v`
Expected: FAIL with `NoReverseMatch`

- [ ] **Step 3: Add the view in core/views.py**

Edit `core/views.py` — add after `task_comment_mark_decision`:

```python
@login_required
@require_POST
def task_toggle_watch(request, pk):
    """Subscribe or unsubscribe the current user from a task's updates."""
    from .models import Task, TaskWatcher

    task = get_object_or_404(Task, pk=pk)
    project = task.project

    # Access control: must be project member/owner, or assignee/creator for standalone
    if project:
        if project.owner != request.user and request.user not in project.members.all():
            return HttpResponse('Access denied', status=403)
    else:
        if request.user not in task.assignees.all() and task.created_by != request.user:
            return HttpResponse('Access denied', status=403)

    watcher_qs = TaskWatcher.objects.filter(user=request.user, task=task)
    if watcher_qs.exists():
        watcher_qs.delete()
        is_watching = False
    else:
        TaskWatcher.objects.create(user=request.user, task=task)
        is_watching = True

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/watch_button.html', {
            'task': task,
            'is_watching': is_watching,
        })

    if project:
        return redirect('task_detail', project_pk=project.pk, pk=task.pk)
    return redirect('standalone_task_detail', pk=task.pk)
```

- [ ] **Step 4: Add URL route**

Edit `core/urls.py` — add after the `task_comment_mark_decision` line:

```python
    path('tasks/<int:pk>/toggle-watch/', views.task_toggle_watch, name='task_toggle_watch'),
```

- [ ] **Step 5: Create watch button partial template**

Create `templates/core/partials/watch_button.html`:

```html
<button
  hx-post="{% url 'task_toggle_watch' task.pk %}"
  hx-target="this"
  hx-swap="outerHTML"
  class="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border transition-colors
    {% if is_watching %}
      bg-[#2a1a0a] border-[#c9a227]/30 text-[#c9a227] hover:bg-[#3a2a1a]
    {% else %}
      bg-[#1a1a1a] border-[#333] text-[#888] hover:border-[#c9a227]/30 hover:text-[#c9a227]
    {% endif %}"
>
  {% if is_watching %}
    <span>&#128065;</span><span>Watching</span>
  {% else %}
    <span>&#128065;</span><span>Watch</span>
  {% endif %}
</button>
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskWatchToggle -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add core/views.py core/urls.py templates/core/partials/watch_button.html tests/test_conversation_first_tasks.py
git commit -m "feat(tasks): add watch/unwatch toggle for tasks"
```

---

## Task 7: Add view to mark task as read

**Files:**
- Modify: `core/views.py` (add new view)
- Modify: `core/urls.py` (add URL route)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing tests for mark-read**

Append to `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversation_first_tasks.py::TestMarkTaskRead -v`
Expected: FAIL with `NoReverseMatch`

- [ ] **Step 3: Add the view in core/views.py**

Edit `core/views.py` — add after `task_toggle_watch`:

```python
@login_required
@require_POST
def task_mark_read(request, pk):
    """Update the current user's TaskReadState to now."""
    from .models import Task, TaskReadState

    task = get_object_or_404(Task, pk=pk)
    project = task.project

    # Access control
    if project:
        if project.owner != request.user and request.user not in project.members.all():
            return HttpResponse('Access denied', status=403)
    else:
        if request.user not in task.assignees.all() and task.created_by != request.user:
            return HttpResponse('Access denied', status=403)

    TaskReadState.objects.update_or_create(
        user=request.user,
        task=task,
        defaults={'last_read_at': timezone.now()},
    )
    return HttpResponse(status=204)
```

- [ ] **Step 4: Add URL route**

Edit `core/urls.py` — add after the `task_toggle_watch` line:

```python
    path('tasks/<int:pk>/mark-read/', views.task_mark_read, name='task_mark_read'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_conversation_first_tasks.py::TestMarkTaskRead -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add core/views.py core/urls.py tests/test_conversation_first_tasks.py
git commit -m "feat(tasks): add mark-read endpoint for unread tracking"
```

---

## Task 8: Auto-mark task as read when task_detail view loads

**Files:**
- Modify: `core/views.py:3607` (task_detail view — and standalone_task_detail if it exists nearby)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing test for auto-mark-on-load**

Append to `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskDetailAutoMarkRead -v`
Expected: FAIL — read state not created, or `is_watching` not in context.

- [ ] **Step 3: Locate task_detail view and update it**

Read `core/views.py` around line 3607 to find the existing `task_detail` function. Add these lines inside the function, after the access check succeeds and before rendering the template:

```python
    # Mark task as read for current user
    from .models import TaskReadState, TaskWatcher
    TaskReadState.objects.update_or_create(
        user=request.user,
        task=task,
        defaults={'last_read_at': timezone.now()},
    )
    is_watching = TaskWatcher.objects.filter(user=request.user, task=task).exists()
```

Then add `'is_watching': is_watching,` to the context dict passed to `render(...)`.

Repeat the same changes in `standalone_task_detail` if it exists (search for `def standalone_task_detail` in `core/views.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_conversation_first_tasks.py::TestTaskDetailAutoMarkRead -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_conversation_first_tasks.py
git commit -m "feat(tasks): auto-mark task as read on view, expose watch state"
```

---

## Task 9: Extend notify_task_comment to include watchers and respect preferences

**Files:**
- Modify: `core/notifications.py` (find `notify_task_comment` function)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing test for watcher notifications**

Append to `tests/test_conversation_first_tasks.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_conversation_first_tasks.py::TestNotifyWatchersOnComment -v`
Expected: FAIL — watchers not notified.

- [ ] **Step 3: Read and update notify_task_comment**

Read `core/notifications.py` around the `notify_task_comment` function. Update it to also notify watchers. The updated function should:

1. Get task assignees (existing behavior)
2. Get mentioned users (existing behavior)
3. Get watchers (new)
4. For each recipient, check their NotificationPreference and respect the appropriate flag
5. Exclude the comment author from all recipients

Replace the function body with:

```python
def notify_task_comment(comment):
    """
    Notify assignees, mentioned users, and watchers about a new task comment.
    Respects per-user NotificationPreference toggles.
    """
    from .models import TaskWatcher, NotificationPreference

    task = comment.task
    author = comment.author

    # Collect all candidate recipients with their reason
    assignee_ids = set(task.assignees.exclude(pk=author.pk if author else None).values_list('pk', flat=True))
    mentioned_ids = set(comment.mentioned_users.exclude(pk=author.pk if author else None).values_list('pk', flat=True))
    watcher_ids = set(
        TaskWatcher.objects.filter(task=task)
        .exclude(user__pk=author.pk if author else None)
        .values_list('user__pk', flat=True)
    )

    # Remove assignees from watcher set to avoid double-notifying
    watcher_only_ids = watcher_ids - assignee_ids - mentioned_ids
    # Remove mentioned users from assignee set (mentions take precedence for flag check)
    assignee_only_ids = assignee_ids - mentioned_ids

    from accounts.models import User

    project = task.project
    if project:
        url = f"/comms/projects/{project.pk}/tasks/{task.pk}/"
    else:
        url = f"/tasks/{task.pk}/"

    title = f"New comment on: {task.title}"
    body_text = comment.content[:140]

    # Always notify mentioned users (respects no special flag beyond @mention)
    for uid in mentioned_ids:
        try:
            user = User.objects.get(pk=uid)
            send_notification_to_user(
                user, 'task', title, body_text, url,
                data={'task_id': task.pk, 'reason': 'mention'},
            )
        except User.DoesNotExist:
            continue

    # Notify assignees per their preference
    for uid in assignee_only_ids:
        try:
            user = User.objects.get(pk=uid)
            prefs = NotificationPreference.get_or_create_for_user(user)
            if prefs.task_comment_on_assigned:
                send_notification_to_user(
                    user, 'task', title, body_text, url,
                    data={'task_id': task.pk, 'reason': 'assigned'},
                )
        except User.DoesNotExist:
            continue

    # Notify watchers per their preference
    for uid in watcher_only_ids:
        try:
            user = User.objects.get(pk=uid)
            prefs = NotificationPreference.get_or_create_for_user(user)
            if prefs.task_comment_on_watched:
                send_notification_to_user(
                    user, 'task', title, body_text, url,
                    data={'task_id': task.pk, 'reason': 'watching'},
                )
        except User.DoesNotExist:
            continue
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_conversation_first_tasks.py::TestNotifyWatchersOnComment -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run ALL Phase 1 tests to verify nothing broke**

Run: `pytest tests/test_conversation_first_tasks.py -v`
Expected: All tests pass.

Run: `pytest tests/ -x --ignore=tests/test_conversation_first_tasks.py 2>&1 | tail -20`
Expected: Existing test suite still passes (452 tests).

- [ ] **Step 6: Commit**

```bash
git add core/notifications.py tests/test_conversation_first_tasks.py
git commit -m "feat(notifications): notify task watchers and respect preferences"
```

---

## Task 10: Redesign task_detail template to be conversation-first

**Files:**
- Modify: `templates/core/comms/task_detail.html` (full redesign)

- [ ] **Step 1: Read current task_detail.html to understand structure**

Read the file and note: current header section, status/assignee/due-date display, comment rendering, comment form, reaction buttons. Preserve all functional HTMX endpoints (comment POST URL, reaction toggle URL), but restructure the layout.

- [ ] **Step 2: Rewrite task_detail.html with conversation-first layout**

Replace the contents of `templates/core/comms/task_detail.html` with a layout structured as:

```
{% extends 'base.html' %}
{% load static %}

{% block content %}
<div class="max-w-3xl mx-auto px-4 py-6">

  <!-- Breadcrumb and back link -->
  <div class="mb-4 text-sm text-[#888]">
    <a href="{% url 'project_detail' pk=task.project.pk %}" class="hover:text-[#c9a227]">
      {{ task.project.name }}
    </a>
    <span class="mx-2">/</span>
    <span>Task</span>
  </div>

  <!-- Compact header: title + status chip + watch button -->
  <div class="flex items-start justify-between gap-4 mb-3">
    <h1 class="text-xl font-semibold text-[#eee] flex-1">{{ task.title }}</h1>
    {% include 'core/partials/watch_button.html' with is_watching=is_watching task=task %}
  </div>

  <!-- Metadata row: status, assignees, due date, priority -->
  <div class="flex flex-wrap items-center gap-3 mb-4 pb-4 border-b border-[#333]">
    <span class="px-2 py-0.5 rounded text-xs font-semibold
      {% if task.status == 'completed' %}bg-[#1a2a0a] text-[#4ade80]
      {% elif task.status == 'in_progress' %}bg-[#2a1a0a] text-[#c9a227]
      {% elif task.status == 'review' %}bg-[#1a1a2a] text-[#6366f1]
      {% else %}bg-[#1a1a1a] text-[#888]{% endif %}">
      {{ task.get_status_display }}
    </span>
    {% if task.assignees.all %}
      <span class="text-sm text-[#888]">
        {% for u in task.assignees.all %}{{ u.display_name|default:u.username }}{% if not forloop.last %}, {% endif %}{% endfor %}
      </span>
    {% endif %}
    {% if task.due_date %}
      <span class="text-sm text-[#888]">Due {{ task.due_date|date:"M j" }}{% if task.due_time %} at {{ task.due_time|time:"g:i A" }}{% endif %}</span>
    {% endif %}
    <span class="text-sm text-[#888]">{{ task.get_priority_display }} priority</span>
  </div>

  <!-- Description (collapsed if long) -->
  {% if task.description %}
    <div class="mb-5 text-sm text-[#ccc]">{{ task.description|linebreaks }}</div>
  {% endif %}

  <!-- Checklist (if any) -->
  {% if task.checklists.exists %}
    <div class="mb-6 p-4 bg-[#1a1a1a] border border-[#333] rounded-lg">
      <h3 class="text-xs uppercase tracking-wide text-[#888] mb-3">Checklist</h3>
      <ul class="space-y-2">
        {% for item in task.checklists.all %}
          <li class="flex items-center gap-2 text-sm">
            <span class="{% if item.is_completed %}text-[#4ade80]{% else %}text-[#555]{% endif %}">
              {% if item.is_completed %}&#10003;{% else %}&#9675;{% endif %}
            </span>
            <span class="{% if item.is_completed %}text-[#666] line-through{% else %}text-[#ccc]{% endif %}">{{ item.title }}</span>
          </li>
        {% endfor %}
      </ul>
    </div>
  {% endif %}

  <!-- CONVERSATION SECTION (primary content) -->
  <div class="mb-4">
    <h2 class="text-sm uppercase tracking-wide text-[#888] mb-4">Conversation</h2>

    <div id="task-comments" class="space-y-4 mb-6">
      {% for comment in task.comments.all %}
        {% include 'core/partials/task_comment.html' with comment=comment reaction_emoji_choices=reaction_emoji_choices %}
      {% empty %}
        <p class="text-sm text-[#666] italic">No conversation yet. Start the discussion below.</p>
      {% endfor %}
    </div>

    <!-- Comment form -->
    <form
      hx-post="{% url 'task_comment' task.pk %}"
      hx-target="#task-comments"
      hx-swap="beforeend"
      hx-on::after-request="this.reset()"
      enctype="multipart/form-data"
      class="bg-[#1a1a1a] border border-[#333] rounded-lg p-3"
    >
      {% csrf_token %}
      <textarea
        name="content"
        rows="2"
        placeholder="Reply or drop a file..."
        class="w-full bg-transparent text-[#ccc] placeholder-[#555] text-sm focus:outline-none resize-none"
      ></textarea>
      <div class="flex items-center justify-between mt-2 pt-2 border-t border-[#2a2a2a]">
        <label class="text-[#555] hover:text-[#c9a227] cursor-pointer text-sm">
          <input type="file" name="attachments" multiple class="hidden">
          &#128206; Attach
        </label>
        <button type="submit" class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
          Comment
        </button>
      </div>
    </form>
  </div>

</div>
{% endblock %}
```

- [ ] **Step 3: Visit a task page in dev and verify layout renders**

Run: `python manage.py runserver` (in background or separate terminal)
Navigate to any task detail URL in the browser.
Expected: Task title at top, conversation section dominant, comment form at bottom. No errors.

- [ ] **Step 4: Run the full test suite to catch regressions**

Run: `pytest tests/ --ignore=tests/test_conversation_first_tasks.py -x 2>&1 | tail -5`
Then: `pytest tests/test_conversation_first_tasks.py -v`
Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add templates/core/comms/task_detail.html
git commit -m "feat(tasks): redesign task_detail template with conversation-first layout"
```

---

## Task 11: Update task_comment partial to show decision badge and mark-decision button

**Files:**
- Modify: `templates/core/partials/task_comment.html`

- [ ] **Step 1: Read current task_comment.html partial**

Read `templates/core/partials/task_comment.html` to understand the existing comment rendering (author, content, timestamp, reaction bar).

- [ ] **Step 2: Update partial to include decision UI**

Add the decision badge and mark-decision button. Replace the contents of `templates/core/partials/task_comment.html` with:

```html
{% load static %}
<div id="comment-{{ comment.pk }}" class="flex gap-3 group">
  <!-- Avatar -->
  <div class="w-8 h-8 rounded-full bg-[#2a2a2a] flex items-center justify-center text-xs text-[#c9a227] flex-shrink-0">
    {{ comment.author.display_name|default:comment.author.username|slice:":1"|upper }}
  </div>

  <div class="flex-1 min-w-0">
    <!-- Author + timestamp + decision chip -->
    <div class="flex items-center gap-2 mb-1 flex-wrap">
      <span class="text-sm font-semibold text-[#c9a227]">
        {{ comment.author.display_name|default:comment.author.username }}
      </span>
      <span class="text-xs text-[#555]">{{ comment.created_at|timesince }} ago</span>
      {% if comment.is_decision %}
        <span class="px-1.5 py-0.5 text-[10px] uppercase tracking-wide bg-[#1a2a0a] text-[#4ade80] rounded border border-[#2a3a1a]">
          Decision
        </span>
      {% endif %}
    </div>

    <!-- Content -->
    {% if comment.is_decision %}
      <div class="mt-1 bg-[#1a2a0a] border border-[#2a3a1a] rounded px-3 py-2">
        <p class="text-xs uppercase tracking-wide text-[#4ade80] mb-1">Decision</p>
        <p class="text-sm text-[#ccc] whitespace-pre-wrap">{{ comment.content }}</p>
      </div>
    {% else %}
      <p class="text-sm text-[#ccc] whitespace-pre-wrap">{{ comment.content }}</p>
    {% endif %}

    <!-- Action row: reactions + mark decision -->
    <div class="flex items-center gap-3 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
      <button
        hx-post="{% url 'task_comment_mark_decision' comment.pk %}"
        hx-target="#comment-{{ comment.pk }}"
        hx-swap="outerHTML"
        class="text-xs text-[#555] hover:text-[#4ade80]"
      >
        {% if comment.is_decision %}Unmark decision{% else %}Mark as decision{% endif %}
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Verify in browser**

Navigate to a task in the browser. Hover over a comment — the "Mark as decision" button should appear. Click it — the comment should update with a green "Decision" chip and highlighted box.

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_conversation_first_tasks.py -v`
Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add templates/core/partials/task_comment.html
git commit -m "feat(tasks): add decision badge and mark-decision button to comment partial"
```

---

## Task 12: Add unread badges to task cards on project detail page

**Files:**
- Modify: `templates/core/comms/project_detail.html` (find task card rendering)
- Modify: `core/views.py` (project_detail view — add unread map to context)
- Test: `tests/test_conversation_first_tasks.py`

- [ ] **Step 1: Add failing test for unread count on project page**

Append to `tests/test_conversation_first_tasks.py`:

```python
@pytest.mark.django_db
class TestProjectDetailUnreadCounts:
    """Verify project_detail view provides per-task unread counts."""

    def test_project_detail_includes_unread_map(
        self, client, user_alpha_owner, user_alpha_member, org_alpha
    ):
        """project_detail context includes unread_counts dict keyed by task.pk."""
        from core.models import Project, Task, TaskComment, TaskReadState
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        project.members.add(user_alpha_member)
        task = Task.objects.create(
            project=project, title='T', created_by=user_alpha_owner,
        )
        # user_alpha_owner viewed it in the past
        past = timezone.now() - timezone.timedelta(days=1)
        TaskReadState.objects.create(
            user=user_alpha_owner, task=task, last_read_at=past,
        )
        # member posts 2 comments after
        TaskComment.objects.create(task=task, author=user_alpha_member, content='A')
        TaskComment.objects.create(task=task, author=user_alpha_member, content='B')
        client.force_login(user_alpha_owner)

        response = client.get(reverse('project_detail', args=[project.pk]))

        assert response.status_code == 200
        unread_counts = response.context['unread_counts']
        assert unread_counts[task.pk] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_conversation_first_tasks.py::TestProjectDetailUnreadCounts -v`
Expected: FAIL — `unread_counts` key not in context.

- [ ] **Step 3: Update project_detail view to build unread map**

Find `def project_detail` in `core/views.py`. Inside the function, after tasks are loaded and before the render call, add:

```python
    # Compute unread comment counts per task for current user
    from .models import unread_comment_count_for
    unread_counts = {}
    for t in tasks_queryset:  # use the existing tasks iterable variable name
        unread_counts[t.pk] = unread_comment_count_for(request.user, t)
```

Then add `'unread_counts': unread_counts,` to the render context.

**Important:** Replace `tasks_queryset` with the actual variable name used in the existing `project_detail` view — read the function to find what the tasks list is called (likely `tasks` or `project_tasks`).

- [ ] **Step 4: Update project_detail.html template to render badge**

Open `templates/core/comms/project_detail.html` and find where tasks are rendered. Inside the task card (near the title or metadata), add:

```html
{% with unread=unread_counts|get_item:task.pk %}
  {% if unread and unread > 0 %}
    <span class="inline-flex items-center gap-1 px-1.5 py-0.5 text-[11px] rounded bg-[#1a0a0a] text-[#e74c3c]">
      &#128172; {{ unread }}
    </span>
  {% endif %}
{% endwith %}
```

The `get_item` filter may not exist. If it doesn't, create it. Check first:

Run: `grep -r "def get_item" core/templatetags/ 2>/dev/null`

If no result, create `core/templatetags/task_filters.py`:

```python
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Look up a dictionary value by key in templates."""
    if dictionary is None:
        return None
    return dictionary.get(key)
```

And ensure there's an empty `core/templatetags/__init__.py` file. Then add `{% load task_filters %}` at the top of `project_detail.html`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_conversation_first_tasks.py::TestProjectDetailUnreadCounts -v`
Expected: PASS.

- [ ] **Step 6: Run full Phase 1 tests + existing suite**

Run: `pytest tests/test_conversation_first_tasks.py -v`
Expected: All Phase 1 tests pass.

Run: `pytest tests/ -x 2>&1 | tail -10`
Expected: Entire suite passes, no regressions.

- [ ] **Step 7: Commit**

```bash
git add core/views.py core/templatetags/ templates/core/comms/project_detail.html tests/test_conversation_first_tasks.py
git commit -m "feat(tasks): show unread comment badges on project task cards"
```

---

## Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v 2>&1 | tail -30`
Expected: All tests pass (452 existing + ~20 new Phase 1 tests ≈ 472 total).

- [ ] **Step 2: Manual smoke test**

Start dev server: `python manage.py runserver`

Test in browser:
1. Open any task detail page → conversation is prominent, not buried
2. Leave a comment → it appears immediately via HTMX
3. Click "Mark as decision" on any comment → green badge appears
4. Click "Watch" button → label changes to "Watching"
5. Go to project detail page → unread badge appears on tasks with unread comments
6. Log in as a different user in another browser, comment on a task → original user sees badge increment on next refresh

- [ ] **Step 3: Final commit (if any fixes needed)**

```bash
git status
# If any untracked/modified files need commits, commit them with focused messages
```

---

## Deployment Notes

- Migrations are additive (no data loss risk)
- Deploy migration first, then code
- First-time load: existing users will see all previous comments as "unread" until they view each task (acceptable — they probably already read them via existing UI)
- No Celery/background jobs required for Phase 1
- No new environment variables needed
