# Generated migration for task checklists and recurring task templates

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0014_add_projects_tasks'),
    ]

    operations = [
        # Create TaskChecklist model
        migrations.CreateModel(
            name='TaskChecklist',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('is_completed', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(default=0)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checklists',
                    to='core.task'
                )),
                ('completed_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='completed_checklist_items',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Task Checklist Item',
                'verbose_name_plural': 'Task Checklist Items',
                'ordering': ['order', 'created_at'],
            },
        ),

        # Create TaskTemplate model
        migrations.CreateModel(
            name='TaskTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(
                    help_text="Internal name for this template (e.g., 'Weekly Stage Set')",
                    max_length=200
                )),
                ('title_template', models.CharField(
                    help_text="Task title with placeholders. Example: 'Stage Set {month} {day}'",
                    max_length=200
                )),
                ('description_template', models.TextField(
                    blank=True,
                    help_text='Optional description with same placeholders'
                )),
                ('recurrence_type', models.CharField(
                    choices=[
                        ('daily', 'Daily'),
                        ('weekly', 'Weekly'),
                        ('biweekly', 'Every 2 Weeks'),
                        ('monthly', 'Monthly (same day)'),
                        ('monthly_weekday', 'Monthly (same weekday)'),
                        ('custom', 'Custom Days')
                    ],
                    default='weekly',
                    max_length=20
                )),
                ('recurrence_days', models.JSONField(
                    blank=True,
                    default=list,
                    help_text='For weekly: [0-6] (Mon-Sun). For monthly: [1-31]. For custom: specific dates.'
                )),
                ('weekday_occurrence', models.IntegerField(
                    blank=True,
                    help_text='For monthly weekday: 1=first, 2=second, -1=last, etc.',
                    null=True
                )),
                ('default_priority', models.CharField(
                    choices=[
                        ('low', 'Low'),
                        ('medium', 'Medium'),
                        ('high', 'High'),
                        ('urgent', 'Urgent')
                    ],
                    default='medium',
                    max_length=10
                )),
                ('default_status', models.CharField(
                    choices=[
                        ('todo', 'To Do'),
                        ('in_progress', 'In Progress'),
                        ('review', 'In Review'),
                        ('completed', 'Completed'),
                        ('cancelled', 'Cancelled')
                    ],
                    default='todo',
                    max_length=20
                )),
                ('days_before_due', models.IntegerField(
                    default=3,
                    help_text='Create task this many days before the due date'
                )),
                ('due_time', models.TimeField(
                    blank=True,
                    help_text='Default due time for generated tasks',
                    null=True
                )),
                ('default_checklist', models.JSONField(
                    blank=True,
                    default=list,
                    help_text='List of checklist item titles to create with each task'
                )),
                ('is_active', models.BooleanField(default=True)),
                ('last_generated_date', models.DateField(
                    blank=True,
                    help_text='Date of the last task generated from this template',
                    null=True
                )),
                ('next_occurrence', models.DateField(
                    blank=True,
                    help_text='Next date a task will be generated for',
                    null=True
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='task_templates',
                    to='core.project'
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_task_templates',
                    to=settings.AUTH_USER_MODEL
                )),
                ('default_assignees', models.ManyToManyField(
                    blank=True,
                    help_text='Team members automatically assigned to generated tasks',
                    related_name='task_template_assignments',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Task Template',
                'verbose_name_plural': 'Task Templates',
                'ordering': ['project', 'name'],
            },
        ),
    ]
