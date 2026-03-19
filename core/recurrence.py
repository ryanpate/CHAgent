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
    """
    assignee_ids = list(source_task.assignees.values_list('pk', flat=True))
    checklist_items = list(source_task.checklists.values('title', 'order'))

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

    if assignee_ids:
        new_task.assignees.set(assignee_ids)

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
    """
    member_ids = list(source_project.members.values_list('pk', flat=True))
    source_tasks = list(source_project.tasks.all())

    new_project = Project.objects.create(
        organization=source_project.organization,
        name=source_project.name,
        description=source_project.description,
        status='planning',
        priority=source_project.priority,
        owner=source_project.owner,
        due_date=due_date or source_project.due_date,
    )

    if member_ids:
        new_project.members.set(member_ids)

    for task in source_tasks:
        clone_task(task, due_date=task.due_date, project=new_project)

    logger.info(f"Cloned project '{source_project.name}' -> #{new_project.pk} with {len(source_tasks)} tasks")
    return new_project
