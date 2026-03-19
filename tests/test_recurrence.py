import pytest
from datetime import date, timedelta
from core.models import RecurrenceRule, Task, Project
from core.recurrence import clone_task, clone_project


@pytest.mark.django_db
def test_create_recurrence_rule_for_task(user_alpha_owner, org_alpha):
    """RecurrenceRule can be linked to a Task."""
    task = Task.objects.create(
        organization=org_alpha, title='Weekly Setup', created_by=user_alpha_owner
    )
    rule = RecurrenceRule.objects.create(
        organization=org_alpha,
        created_by=user_alpha_owner,
        source_task=task,
        frequency='weekly',
        day_of_week=0,
        next_due=date.today(),
    )
    assert rule.pk is not None
    assert rule.source_task == task
    assert rule.source_project is None
    assert rule.is_active is True
    assert str(rule) == 'Weekly: Weekly Setup'


@pytest.mark.django_db
def test_create_recurrence_rule_for_project(user_alpha_owner, org_alpha):
    """RecurrenceRule can be linked to a Project."""
    project = Project.objects.create(
        organization=org_alpha, name='Monthly Review', owner=user_alpha_owner
    )
    rule = RecurrenceRule.objects.create(
        organization=org_alpha,
        created_by=user_alpha_owner,
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


@pytest.mark.django_db
def test_clone_task_copies_fields(user_alpha_owner, org_alpha):
    """clone_task creates a new task with same fields but reset status."""
    from accounts.models import User
    from core.models import TaskChecklist
    user = user_alpha_owner
    user2 = User.objects.create_user(username='helper@test.com', password='test')

    source = Task.objects.create(
        organization=org_alpha, title='Stage Setup',
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
    assert clone.organization == org_alpha
    assert set(clone.assignees.all()) == {user, user2}
    assert clone.checklists.count() == 2
    assert list(clone.checklists.values_list('title', flat=True).order_by('order')) == ['Mic check', 'Lights']
    assert clone.checklists.filter(is_completed=True).count() == 0


@pytest.mark.django_db
def test_clone_project_with_tasks(user_alpha_owner, org_alpha):
    """clone_project creates a new project with all its tasks cloned."""
    from core.models import TaskChecklist
    user = user_alpha_owner

    project = Project.objects.create(
        organization=org_alpha, name='Weekly Review',
        description='Team review', owner=user, priority='medium',
    )
    project.members.add(user)

    task1 = Task.objects.create(
        organization=org_alpha, project=project,
        title='Prepare agenda', created_by=user, priority='high',
    )
    task1.assignees.add(user)
    TaskChecklist.objects.create(task=task1, title='Gather topics', order=0)

    task2 = Task.objects.create(
        organization=org_alpha, project=project,
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
