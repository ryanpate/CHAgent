"""
Daily cron command to send due date reminders for tasks and milestones.

Usage:
    python manage.py send_task_reminders

Run daily via Railway cron or similar scheduler (recommended: 0 14 * * * = 6 AM MT).
"""
import logging
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import Task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send due date reminder notifications for tasks due today or tomorrow'

    def handle(self, *args, **options):
        today = date.today()
        tomorrow = today + timedelta(days=1)

        # Find tasks due today or tomorrow that haven't had reminders sent
        tasks = Task.objects.filter(
            due_date__in=[today, tomorrow],
            reminder_sent=False,
        ).exclude(
            status__in=['completed', 'cancelled']
        ).prefetch_related('assignees')

        sent = 0
        for task in tasks:
            if not task.assignees.exists():
                continue

            try:
                from core.notifications import notify_task_due_soon
                notify_task_due_soon(task)
                task.reminder_sent = True
                task.save(update_fields=['reminder_sent'])
                sent += 1
                self.stdout.write(f"  Reminder sent: {task.title} (due {task.due_date})")
            except Exception as e:
                logger.error(f"Failed to send reminder for task {task.pk}: {e}")
                self.stderr.write(f"  ERROR: {task.title} - {e}")

        self.stdout.write(self.style.SUCCESS(
            f'Done. Sent {sent} task reminders.'
        ))
