import pytest
from datetime import date, timedelta
from core.models import RecurrenceRule, Task, Project


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
