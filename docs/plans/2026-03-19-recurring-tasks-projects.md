# Recurring Tasks & Projects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow tasks and projects to recur on a schedule (weekly, biweekly, monthly, quarterly), automatically creating fresh copies with all fields, assignees, and checklists.

**Architecture:** A `RecurrenceRule` model stores the schedule and points to a source task or project as a template. A daily management command queries due rules and clones tasks/projects. UI adds a "Repeat" toggle to task and project detail pages.

**Tech Stack:** Django models, management command, Railway cron job

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `core/models.py` | Modify | Add RecurrenceRule model |
| `core/recurrence.py` | Create | Clone logic for tasks and projects |
| `core/management/commands/create_recurring_tasks.py` | Create | Daily cron command |
| `core/views.py` | Modify | Add views for setting/removing recurrence |
| `core/urls.py` | Modify | Add recurrence URL patterns |
| `templates/core/comms/task_detail.html` | Modify | Add recurrence UI section |
| `templates/core/comms/project_detail.html` | Modify | Add recurrence UI in settings dropdown |
| `templates/core/partials/task_card.html` | Modify | Add recurring indicator icon |
| `tests/test_recurrence.py` | Create | Model, clone logic, and management command tests |

---

### Task 1: Add RecurrenceRule Model

**Files:**
- Modify: `core/models.py` (append after MessageAttachment)
- Create: migration via `makemigrations`
- Create: `tests/test_recurrence.py`

- [ ] **Step 1: Write model tests**

Create `tests/test_recurrence.py`:

```python
import pytest
from datetime import date, timedelta
from core.models import RecurrenceRule, Task, Project


@pytest.mark.django_db
def test_create_recurrence_rule_for_task(org_user_client, test_org):
    """RecurrenceRule can be linked to a Task."""
    from accounts.models import User
    user = User.objects.first()
    task = Task.objects.create(
        organization=test_org, title='Weekly Setup', created_by=user
    )
    rule = RecurrenceRule.objects.create(
        organization=test_org,
        created_by=user,
        source_task=task,
        frequency='weekly',
        day_of_week=0,  # Monday
        next_due=date.today(),
    )
    assert rule.pk is not None
    assert rule.source_task == task
    assert rule.source_project is None
    assert rule.is_active is True
    assert str(rule) == 'Weekly: Weekly Setup'


@pytest.mark.django_db
def test_create_recurrence_rule_for_project(org_user_client, test_org):
    """RecurrenceRule can be linked to a Project."""
    from accounts.models import User
    user = User.objects.first()
    project = Project.objects.create(
        organization=test_org, name='Monthly Review', owner=user
    )
    rule = RecurrenceRule.objects.create(
        organization=test_org,
        created_by=user,
        source_project=project,
        frequency='monthly',
        day_of_month=1,
        next_due=date.today(),
    )
    assert rule.source_project == project
    assert str(rule) == 'Monthly: Monthly Review'


@pytest.mark.django_db
def test_advance_next_due_weekly():
    """advance_next_due correctly calculates next weekly date."""
    rule = RecurrenceRule(frequency='weekly', next_due=date(2026, 3, 16))
    rule.advance_next_due()
    assert rule.next_due == date(2026, 3, 23)


@pytest.mark.django_db
def test_advance_next_due_biweekly():
    """advance_next_due correctly calculates next biweekly date."""
    rule = RecurrenceRule(frequency='biweekly', next_due=date(2026, 3, 16))
    rule.advance_next_due()
    assert rule.next_due == date(2026, 3, 30)


@pytest.mark.django_db
def test_advance_next_due_monthly():
    """advance_next_due correctly calculates next monthly date."""
    rule = RecurrenceRule(frequency='monthly', next_due=date(2026, 3, 1))
    rule.advance_next_due()
    assert rule.next_due == date(2026, 4, 1)


@pytest.mark.django_db
def test_advance_next_due_quarterly():
    """advance_next_due correctly calculates next quarterly date."""
    rule = RecurrenceRule(frequency='quarterly', next_due=date(2026, 1, 15))
    rule.advance_next_due()
    assert rule.next_due == date(2026, 4, 15)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_recurrence.py -v`
Expected: FAIL (RecurrenceRule not defined)

- [ ] **Step 3: Add RecurrenceRule model to core/models.py**

Append at the end of `core/models.py`:

```python
class RecurrenceRule(models.Model):
    """
    Schedule for recurring tasks or projects.
    Links to a source task/project as a template. A daily cron job
    checks for due rules and clones the source.
    """
    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('biweekly', 'Every 2 Weeks'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
    ]

    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='recurrence_rules',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )

    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    day_of_week = models.IntegerField(
        null=True, blank=True,
        help_text='0=Monday, 6=Sunday. Used for weekly/biweekly.'
    )
    day_of_month = models.IntegerField(
        null=True, blank=True,
        help_text='1-28. Used for monthly/quarterly.'
    )
    next_due = models.DateField(help_text='Next date to create an instance.')
    is_active = models.BooleanField(default=True)

    # Template source — one should be set
    source_task = models.OneToOneField(
        'Task',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurrence_rule',
    )
    source_project = models.OneToOneField(
        'Project',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurrence_rule',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_due']

    def __str__(self):
        name = ''
        if self.source_task:
            name = self.source_task.title
        elif self.source_project:
            name = self.source_project.name
        return f'{self.get_frequency_display()}: {name}'

    def advance_next_due(self):
        """Calculate and set the next due date based on frequency."""
        from dateutil.relativedelta import relativedelta

        if self.frequency == 'weekly':
            self.next_due += timedelta(days=7)
        elif self.frequency == 'biweekly':
            self.next_due += timedelta(days=14)
        elif self.frequency == 'monthly':
            self.next_due += relativedelta(months=1)
        elif self.frequency == 'quarterly':
            self.next_due += relativedelta(months=3)
```

Note: `timedelta` is already imported at the top of models.py. Add `python-dateutil` to requirements.txt (needed for `relativedelta`).

- [ ] **Step 4: Add python-dateutil to requirements.txt**

Add after the `pyotp` line:
```
# Date utilities (for recurring tasks)
python-dateutil>=2.8.0
```

- [ ] **Step 5: Create and run migration**

```bash
python3 manage.py makemigrations core
python3 manage.py migrate
```

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest tests/test_recurrence.py -v`
Expected: All 6 tests PASS

- [ ] **Step 7: Commit**

```bash
git add core/models.py core/migrations/ tests/test_recurrence.py requirements.txt
git commit -m "feat: add RecurrenceRule model for recurring tasks and projects"
```

---

### Task 2: Create Clone Logic

**Files:**
- Create: `core/recurrence.py`
- Modify: `tests/test_recurrence.py` (add clone tests)

- [ ] **Step 1: Write clone tests**

Append to `tests/test_recurrence.py`:

```python
from core.recurrence import clone_task, clone_project


@pytest.mark.django_db
def test_clone_task_copies_fields(org_user_client, test_org):
    """clone_task creates a new task with same fields but reset status."""
    from accounts.models import User
    from core.models import TaskChecklist
    user = User.objects.first()
    user2 = User.objects.create_user(username='helper@test.com', password='test')

    source = Task.objects.create(
        organization=test_org, title='Stage Setup',
        description='Set up the stage', priority='high',
        created_by=user, due_date=date(2026, 3, 20),
    )
    source.assignees.add(user, user2)
    TaskChecklist.objects.create(task=source, title='Mic check', order=0)
    TaskChecklist.objects.create(task=source, title='Lights', order=1)

    clone = clone_task(source, due_date=date(2026, 3, 27))

    assert clone.pk != source.pk
    assert clone.title == 'Stage Setup'
    assert clone.description == 'Set up the stage'
    assert clone.priority == 'high'
    assert clone.status == 'todo'
    assert clone.due_date == date(2026, 3, 27)
    assert clone.organization == test_org
    assert set(clone.assignees.all()) == {user, user2}
    assert clone.checklists.count() == 2
    assert list(clone.checklists.values_list('title', flat=True).order_by('order')) == ['Mic check', 'Lights']
    # Checklists should be unchecked
    assert clone.checklists.filter(is_completed=True).count() == 0


@pytest.mark.django_db
def test_clone_project_with_tasks(org_user_client, test_org):
    """clone_project creates a new project with all its tasks cloned."""
    from accounts.models import User
    from core.models import TaskChecklist
    user = User.objects.first()

    project = Project.objects.create(
        organization=test_org, name='Weekly Review',
        description='Team review', owner=user, priority='medium',
    )
    project.members.add(user)

    task1 = Task.objects.create(
        organization=test_org, project=project,
        title='Prepare agenda', created_by=user, priority='high',
    )
    task1.assignees.add(user)
    TaskChecklist.objects.create(task=task1, title='Gather topics', order=0)

    task2 = Task.objects.create(
        organization=test_org, project=project,
        title='Send notes', created_by=user,
    )

    clone = clone_project(project, due_date=date(2026, 4, 1))

    assert clone.pk != project.pk
    assert clone.name == 'Weekly Review'
    assert clone.status == 'planning'
    assert clone.due_date == date(2026, 4, 1)
    assert clone.owner == user
    assert user in clone.members.all()
    assert clone.tasks.count() == 2
    cloned_task = clone.tasks.get(title='Prepare agenda')
    assert cloned_task.status == 'todo'
    assert user in cloned_task.assignees.all()
    assert cloned_task.checklists.count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_recurrence.py::test_clone_task_copies_fields -v`
Expected: FAIL (cannot import clone_task)

- [ ] **Step 3: Create core/recurrence.py**

```python
"""
Clone logic for recurring tasks and projects.
"""
import logging
from datetime import date

from .models import Task, Project, TaskChecklist

logger = logging.getLogger(__name__)


def clone_task(source_task, due_date=None, project=None):
    """
    Create a fresh copy of a task with all fields, assignees, and checklists.
    Status is reset to 'todo', completion fields cleared.

    Args:
        source_task: The Task to clone.
        due_date: Due date for the new task (optional).
        project: Project to attach to (optional, for project task cloning).

    Returns:
        The newly created Task.
    """
    # Capture M2M before copying
    assignee_ids = list(source_task.assignees.values_list('pk', flat=True))
    checklist_items = list(
        source_task.checklists.values('title', 'order')
    )

    # Create the clone
    new_task = Task.objects.create(
        organization=source_task.organization,
        project=project or source_task.project,
        title=source_task.title,
        description=source_task.description,
        status='todo',
        priority=source_task.priority,
        created_by=source_task.created_by,
        due_date=due_date or source_task.due_date,
        due_time=source_task.due_time,
        order=source_task.order,
    )

    # Copy assignees
    if assignee_ids:
        new_task.assignees.set(assignee_ids)

    # Copy checklists (unchecked)
    for item in checklist_items:
        TaskChecklist.objects.create(
            task=new_task,
            title=item['title'],
            order=item['order'],
            is_completed=False,
        )

    logger.info(f"Cloned task '{source_task.title}' -> new task #{new_task.pk}")
    return new_task


def clone_project(source_project, due_date=None):
    """
    Create a fresh copy of a project with all tasks, assignees, and checklists.
    Status is reset to 'planning', all tasks reset to 'todo'.

    Args:
        source_project: The Project to clone.
        due_date: Due date for the new project (optional).

    Returns:
        The newly created Project.
    """
    # Capture M2M
    member_ids = list(source_project.members.values_list('pk', flat=True))
    source_tasks = list(source_project.tasks.all())

    # Create project clone
    new_project = Project.objects.create(
        organization=source_project.organization,
        name=source_project.name,
        description=source_project.description,
        status='planning',
        priority=source_project.priority,
        owner=source_project.owner,
        due_date=due_date or source_project.due_date,
    )

    # Copy members
    if member_ids:
        new_project.members.set(member_ids)

    # Clone each task within the project
    for task in source_tasks:
        clone_task(task, due_date=task.due_date, project=new_project)

    logger.info(f"Cloned project '{source_project.name}' -> new project #{new_project.pk} with {len(source_tasks)} tasks")
    return new_project
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_recurrence.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add core/recurrence.py tests/test_recurrence.py
git commit -m "feat: add clone logic for recurring tasks and projects"
```

---

### Task 3: Create Management Command

**Files:**
- Create: `core/management/commands/create_recurring_tasks.py`
- Modify: `tests/test_recurrence.py` (add command tests)

- [ ] **Step 1: Write command tests**

Append to `tests/test_recurrence.py`:

```python
from django.core.management import call_command


@pytest.mark.django_db
def test_management_command_creates_task(org_user_client, test_org):
    """create_recurring_tasks command clones due tasks."""
    from accounts.models import User
    user = User.objects.first()

    source = Task.objects.create(
        organization=test_org, title='Weekly Checkin',
        created_by=user, priority='medium',
    )
    rule = RecurrenceRule.objects.create(
        organization=test_org, created_by=user,
        source_task=source, frequency='weekly',
        day_of_week=0, next_due=date.today(),
    )

    initial_count = Task.objects.filter(title='Weekly Checkin').count()
    call_command('create_recurring_tasks')

    assert Task.objects.filter(title='Weekly Checkin').count() == initial_count + 1
    rule.refresh_from_db()
    assert rule.next_due == date.today() + timedelta(days=7)


@pytest.mark.django_db
def test_management_command_skips_inactive(org_user_client, test_org):
    """create_recurring_tasks skips inactive rules."""
    from accounts.models import User
    user = User.objects.first()

    source = Task.objects.create(
        organization=test_org, title='Paused Task', created_by=user,
    )
    RecurrenceRule.objects.create(
        organization=test_org, created_by=user,
        source_task=source, frequency='weekly',
        day_of_week=0, next_due=date.today(),
        is_active=False,
    )

    initial_count = Task.objects.filter(title='Paused Task').count()
    call_command('create_recurring_tasks')
    assert Task.objects.filter(title='Paused Task').count() == initial_count


@pytest.mark.django_db
def test_management_command_skips_future(org_user_client, test_org):
    """create_recurring_tasks skips rules not yet due."""
    from accounts.models import User
    user = User.objects.first()

    source = Task.objects.create(
        organization=test_org, title='Future Task', created_by=user,
    )
    RecurrenceRule.objects.create(
        organization=test_org, created_by=user,
        source_task=source, frequency='weekly',
        day_of_week=0, next_due=date.today() + timedelta(days=5),
    )

    initial_count = Task.objects.filter(title='Future Task').count()
    call_command('create_recurring_tasks')
    assert Task.objects.filter(title='Future Task').count() == initial_count
```

- [ ] **Step 2: Create the management command**

Create `core/management/commands/create_recurring_tasks.py`:

```python
"""
Daily cron command to create instances from recurring task/project rules.

Usage:
    python manage.py create_recurring_tasks

Run daily via Railway cron or similar scheduler.
"""
import logging
from datetime import date

from django.core.management.base import BaseCommand

from core.models import RecurrenceRule
from core.recurrence import clone_task, clone_project

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create task/project instances from due recurrence rules'

    def handle(self, *args, **options):
        today = date.today()
        due_rules = RecurrenceRule.objects.filter(
            is_active=True,
            next_due__lte=today,
        ).select_related('source_task', 'source_project')

        created = 0
        for rule in due_rules:
            try:
                if rule.source_task:
                    new_task = clone_task(rule.source_task, due_date=rule.next_due)
                    # Send notifications to assignees
                    try:
                        from core.notifications import notify_task_assignment
                        for assignee in new_task.assignees.all():
                            notify_task_assignment(new_task, assignee)
                    except Exception as e:
                        logger.warning(f"Failed to notify for recurring task: {e}")

                elif rule.source_project:
                    clone_project(rule.source_project, due_date=rule.next_due)

                rule.advance_next_due()
                rule.save()
                created += 1
                self.stdout.write(f"  Created: {rule}")

            except Exception as e:
                logger.error(f"Failed to process recurrence rule {rule.pk}: {e}")
                self.stderr.write(f"  ERROR: {rule} - {e}")

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created {created} recurring items.'
        ))
```

- [ ] **Step 3: Run tests**

Run: `python3 -m pytest tests/test_recurrence.py -v`
Expected: All 11 tests PASS

- [ ] **Step 4: Commit**

```bash
git add core/management/commands/create_recurring_tasks.py tests/test_recurrence.py
git commit -m "feat: add daily management command for recurring tasks/projects"
```

---

### Task 4: Add Recurrence Views and URLs

**Files:**
- Modify: `core/views.py`
- Modify: `core/urls.py`

- [ ] **Step 1: Add views for setting and removing recurrence**

Add to `core/views.py` (near the task-related views):

```python
@login_required
@require_POST
def task_set_recurrence(request, pk):
    """Set or update recurrence on a task."""
    from .models import Task, RecurrenceRule
    from datetime import date, timedelta

    org = get_org(request)
    task = get_object_or_404(Task, pk=pk)

    # Permission check
    if task.project:
        if task.project.owner != request.user and request.user not in task.project.members.all():
            return HttpResponse('Permission denied', status=403)
    elif task.created_by != request.user:
        is_admin = getattr(request, 'membership', None) and request.membership.is_admin_or_above
        if not is_admin:
            return HttpResponse('Permission denied', status=403)

    frequency = request.POST.get('frequency')
    if not frequency or frequency not in dict(RecurrenceRule.FREQUENCY_CHOICES):
        return HttpResponse('Invalid frequency', status=400)

    day_of_week = request.POST.get('day_of_week')
    day_of_month = request.POST.get('day_of_month')

    # Calculate first next_due
    today = date.today()
    if frequency in ('weekly', 'biweekly'):
        dow = int(day_of_week) if day_of_week else today.weekday()
        days_ahead = dow - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_due = today + timedelta(days=days_ahead)
    else:
        dom = int(day_of_month) if day_of_month else today.day
        dom = min(dom, 28)
        from dateutil.relativedelta import relativedelta
        next_due = today.replace(day=dom)
        if next_due <= today:
            months = 3 if frequency == 'quarterly' else 1
            next_due += relativedelta(months=months)

    # Create or update the rule
    rule, created = RecurrenceRule.objects.update_or_create(
        source_task=task,
        defaults={
            'organization': org,
            'created_by': request.user,
            'frequency': frequency,
            'day_of_week': int(day_of_week) if day_of_week and frequency in ('weekly', 'biweekly') else None,
            'day_of_month': int(day_of_month) if day_of_month and frequency in ('monthly', 'quarterly') else None,
            'next_due': next_due,
            'is_active': True,
        }
    )

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/recurrence_badge.html', {
            'rule': rule, 'task': task,
        })

    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
@require_POST
def task_remove_recurrence(request, pk):
    """Remove recurrence from a task."""
    from .models import Task, RecurrenceRule

    task = get_object_or_404(Task, pk=pk)
    RecurrenceRule.objects.filter(source_task=task).delete()

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/recurrence_badge.html', {
            'rule': None, 'task': task,
        })

    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
@require_POST
def project_set_recurrence(request, pk):
    """Set or update recurrence on a project."""
    from .models import Project, RecurrenceRule
    from datetime import date, timedelta

    org = get_org(request)
    project = get_object_or_404(Project, pk=pk)

    is_owner = project.owner == request.user
    is_admin = getattr(request, 'membership', None) and request.membership.is_admin_or_above
    if not is_owner and not is_admin:
        return HttpResponse('Permission denied', status=403)

    frequency = request.POST.get('frequency')
    if not frequency or frequency not in dict(RecurrenceRule.FREQUENCY_CHOICES):
        return HttpResponse('Invalid frequency', status=400)

    day_of_week = request.POST.get('day_of_week')
    day_of_month = request.POST.get('day_of_month')

    today = date.today()
    if frequency in ('weekly', 'biweekly'):
        dow = int(day_of_week) if day_of_week else today.weekday()
        days_ahead = dow - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        next_due = today + timedelta(days=days_ahead)
    else:
        dom = int(day_of_month) if day_of_month else today.day
        dom = min(dom, 28)
        from dateutil.relativedelta import relativedelta
        next_due = today.replace(day=dom)
        if next_due <= today:
            months = 3 if frequency == 'quarterly' else 1
            next_due += relativedelta(months=months)

    rule, created = RecurrenceRule.objects.update_or_create(
        source_project=project,
        defaults={
            'organization': org,
            'created_by': request.user,
            'frequency': frequency,
            'day_of_week': int(day_of_week) if day_of_week and frequency in ('weekly', 'biweekly') else None,
            'day_of_month': int(day_of_month) if day_of_month and frequency in ('monthly', 'quarterly') else None,
            'next_due': next_due,
            'is_active': True,
        }
    )

    if request.headers.get('HX-Request'):
        return HttpResponse('<span class="text-xs text-ch-gold">Recurring: ' + rule.get_frequency_display() + '</span>')

    return redirect(request.META.get('HTTP_REFERER', '/'))


@login_required
@require_POST
def project_remove_recurrence(request, pk):
    """Remove recurrence from a project."""
    from .models import Project, RecurrenceRule

    project = get_object_or_404(Project, pk=pk)
    RecurrenceRule.objects.filter(source_project=project).delete()

    if request.headers.get('HX-Request'):
        return HttpResponse('')

    return redirect(request.META.get('HTTP_REFERER', '/'))
```

- [ ] **Step 2: Add URL patterns to core/urls.py**

Add after the `task_delete` URL:

```python
    path('tasks/<int:pk>/recurrence/', views.task_set_recurrence, name='task_set_recurrence'),
    path('tasks/<int:pk>/recurrence/remove/', views.task_remove_recurrence, name='task_remove_recurrence'),
```

Add after the `project_delete` URL:

```python
    path('comms/projects/<int:pk>/recurrence/', views.project_set_recurrence, name='project_set_recurrence'),
    path('comms/projects/<int:pk>/recurrence/remove/', views.project_remove_recurrence, name='project_remove_recurrence'),
```

- [ ] **Step 3: Run full test suite**

Run: `python3 -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add core/views.py core/urls.py
git commit -m "feat: add views and URLs for setting/removing recurrence"
```

---

### Task 5: Add Recurrence UI to Task Detail

**Files:**
- Create: `templates/core/partials/recurrence_badge.html`
- Modify: `templates/core/comms/task_detail.html`
- Modify: `templates/core/partials/task_card.html`

- [ ] **Step 1: Create recurrence badge partial**

Create `templates/core/partials/recurrence_badge.html`:

```html
<div id="recurrence-section">
    {% if rule %}
    <div class="flex items-center gap-2">
        <svg class="w-4 h-4 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
        </svg>
        <span class="text-sm text-ch-gold">{{ rule.get_frequency_display }}</span>
        <span class="text-xs text-gray-500">Next: {{ rule.next_due|date:"M d" }}</span>
        <form hx-post="{% url 'task_remove_recurrence' task.pk %}"
              hx-target="#recurrence-section"
              hx-swap="outerHTML"
              hx-confirm="Stop recurring? This won't delete existing copies."
              class="inline">
            {% csrf_token %}
            <button type="submit" class="text-xs text-red-400 hover:text-red-300 ml-2">Remove</button>
        </form>
    </div>
    {% else %}
    <div x-data="{ open: false }">
        <button @click="open = !open" class="text-sm text-gray-400 hover:text-ch-gold flex items-center gap-1">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
            </svg>
            Make Recurring
        </button>
        <div x-show="open" @click.away="open = false" class="mt-2 p-3 bg-ch-gray rounded-lg">
            <form hx-post="{% url 'task_set_recurrence' task.pk %}"
                  hx-target="#recurrence-section"
                  hx-swap="outerHTML">
                {% csrf_token %}
                <div class="space-y-2">
                    <select name="frequency" required
                            class="w-full bg-ch-dark border border-gray-700 rounded px-3 py-2 text-sm">
                        <option value="weekly">Weekly</option>
                        <option value="biweekly">Every 2 Weeks</option>
                        <option value="monthly">Monthly</option>
                        <option value="quarterly">Quarterly</option>
                    </select>
                    <button type="submit"
                            class="w-full px-3 py-2 bg-ch-gold text-black rounded font-medium text-sm hover:bg-yellow-500 transition">
                        Set Recurrence
                    </button>
                </div>
            </form>
        </div>
    </div>
    {% endif %}
</div>
```

- [ ] **Step 2: Add recurrence section to task_detail.html**

In `templates/core/comms/task_detail.html`, find the Task Meta section (the `<div class="flex flex-wrap gap-6 text-sm">` block) and add after the Assignees div:

```html
            <div>
                <span class="text-gray-500">Repeat</span>
                {% with rule=task.recurrence_rule %}
                {% include 'core/partials/recurrence_badge.html' with task=task rule=rule %}
                {% endwith %}
            </div>
```

Note: The `task.recurrence_rule` will be `None` if no rule exists (raises RelatedObjectDoesNotExist). Use a template try/except approach — actually, since it's a OneToOneField, we need to handle this in the view. Add `recurrence_rule` to the task detail view context. In both `task_detail` and `standalone_task_detail` views, add to context:

```python
    try:
        recurrence_rule = task.recurrence_rule
    except Task.recurrence_rule.RelatedObjectDoesNotExist:
        recurrence_rule = None
```

And pass `'recurrence_rule': recurrence_rule` in the context dict. Then in the template use `rule=recurrence_rule` instead of `task.recurrence_rule`.

- [ ] **Step 3: Add recurring indicator to task_card.html partial**

Read `templates/core/partials/task_card.html` and add a small recurrence icon next to the title. Check if the task has a recurrence_rule and show a repeat icon:

```html
{% if task.recurrence_rule %}
<svg class="w-3 h-3 text-ch-gold inline ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" title="Recurring">
    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path>
</svg>
{% endif %}
```

Note: Accessing `task.recurrence_rule` on a task without one raises `RelatedObjectDoesNotExist`. To avoid this, we need a safe check. The simplest approach: add a `has_recurrence` property to the Task model or use a try/except template tag. Alternatively, use `{% if task.recurrence_rule.pk %}` wrapped in `{% with %}`. The safest Django approach is to add a simple helper. Add to the Task model:

```python
    @property
    def is_recurring(self):
        try:
            return self.recurrence_rule is not None
        except RecurrenceRule.DoesNotExist:
            return False
```

Then use `{% if task.is_recurring %}` in templates.

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add templates/core/partials/recurrence_badge.html templates/core/comms/task_detail.html templates/core/partials/task_card.html core/views.py core/models.py
git commit -m "feat: add recurrence UI to task detail and recurring indicator on task cards"
```

---

### Task 6: Add Recurrence UI to Project Detail

**Files:**
- Modify: `templates/core/comms/project_detail.html`

- [ ] **Step 1: Add recurrence option to project settings dropdown**

In `templates/core/comms/project_detail.html`, find the owner dropdown menu (the one with "Change Status" and "Delete Project"). Add a recurrence section between the status form and the delete section:

```html
                    <div class="border-t border-gray-700 p-2">
                        <p class="text-xs text-gray-500 px-2 mb-1">Recurrence</p>
                        {% if project.is_recurring %}
                        <div class="px-2 py-1 text-xs text-ch-gold mb-1">
                            {{ project.recurrence_rule.get_frequency_display }} — Next: {{ project.recurrence_rule.next_due|date:"M d" }}
                        </div>
                        <form hx-post="{% url 'project_remove_recurrence' project.pk %}"
                              hx-swap="none"
                              hx-on::after-request="location.reload()"
                              hx-confirm="Stop recurring?"
                              class="w-full">
                            {% csrf_token %}
                            <button type="submit" class="w-full text-left px-2 py-1 text-sm text-red-400 hover:bg-red-900/30 rounded">
                                Stop Recurring
                            </button>
                        </form>
                        {% else %}
                        <form hx-post="{% url 'project_set_recurrence' project.pk %}"
                              hx-swap="none"
                              hx-on::after-request="location.reload()">
                            {% csrf_token %}
                            <select name="frequency" required
                                    class="w-full bg-ch-gray border border-gray-700 rounded px-2 py-1 text-xs mb-1">
                                <option value="weekly">Weekly</option>
                                <option value="biweekly">Every 2 Weeks</option>
                                <option value="monthly">Monthly</option>
                                <option value="quarterly">Quarterly</option>
                            </select>
                            <button type="submit"
                                    class="w-full text-left px-2 py-1 text-sm hover:bg-ch-gray rounded">
                                Set Recurrence
                            </button>
                        </form>
                        {% endif %}
                    </div>
```

Also add `is_recurring` property to the Project model (same pattern as Task):

```python
    @property
    def is_recurring(self):
        try:
            return self.recurrence_rule is not None
        except RecurrenceRule.DoesNotExist:
            return False
```

- [ ] **Step 2: Run full test suite**

Run: `python3 -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add templates/core/comms/project_detail.html core/models.py
git commit -m "feat: add recurrence UI to project detail settings"
```

---

### Task 7: Configure Railway Cron Job

**Files:**
- Modify: `railway.toml` (document the cron setup)

- [ ] **Step 1: Document Railway cron setup**

Railway supports cron jobs via a separate service. Add a comment to `railway.toml`:

```toml
# Recurring tasks cron job:
# Create a separate Railway service (Cron type) with:
#   Schedule: 0 6 * * * (daily at 6:00 AM UTC)
#   Command: python manage.py create_recurring_tasks
# This checks for due recurrence rules and creates task/project instances.
```

Alternatively, the command can be added to the start command to run on each deploy (simpler but less reliable):

In `railway.toml`, add to the startCommand chain (before gunicorn):
```
python manage.py create_recurring_tasks &&
```

- [ ] **Step 2: Run full test suite one final time**

Run: `python3 -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 3: Commit and push**

```bash
git add railway.toml
git commit -m "docs: add Railway cron job setup for recurring tasks"
git push
```

---

## Post-Implementation Notes

### Railway Cron Setup

To run the recurring tasks command daily:

1. In Railway dashboard, create a new **Cron Job** service
2. Set schedule: `0 6 * * *` (6:00 AM UTC daily, adjust to your timezone)
3. Set command: `python manage.py create_recurring_tasks`
4. Use the same environment variables as the web service

### How Recurrence Works

1. User creates a task normally, then clicks "Make Recurring" and picks frequency
2. A `RecurrenceRule` is created with `next_due` set to the next occurrence
3. Daily cron runs `create_recurring_tasks` which finds rules where `next_due <= today`
4. For each due rule: clone the task/project, advance `next_due`
5. Assignees get push notifications for new task assignments
6. The source task/project stays as the template (never deleted)
