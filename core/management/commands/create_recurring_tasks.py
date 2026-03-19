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
