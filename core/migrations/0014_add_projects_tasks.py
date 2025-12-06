# Generated migration for projects and tasks

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0013_push_notifications'),
    ]

    operations = [
        # Add mentioned_users to ChannelMessage
        migrations.AddField(
            model_name='channelmessage',
            name='mentioned_users',
            field=models.ManyToManyField(
                blank=True,
                related_name='channel_mentions_received',
                to=settings.AUTH_USER_MODEL
            ),
        ),

        # Create Project model
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[
                        ('planning', 'Planning'),
                        ('active', 'Active'),
                        ('on_hold', 'On Hold'),
                        ('completed', 'Completed'),
                        ('archived', 'Archived')
                    ],
                    default='planning',
                    max_length=20
                )),
                ('priority', models.CharField(
                    choices=[
                        ('low', 'Low'),
                        ('medium', 'Medium'),
                        ('high', 'High'),
                        ('urgent', 'Urgent')
                    ],
                    default='medium',
                    max_length=10
                )),
                ('start_date', models.DateField(blank=True, null=True)),
                ('due_date', models.DateField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('service_date', models.DateField(
                    blank=True,
                    help_text='For service-specific projects',
                    null=True
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='owned_projects',
                    to=settings.AUTH_USER_MODEL
                )),
                ('members', models.ManyToManyField(
                    blank=True,
                    related_name='projects',
                    to=settings.AUTH_USER_MODEL
                )),
                ('channel', models.OneToOneField(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='project',
                    to='core.channel'
                )),
            ],
            options={
                'verbose_name': 'Project',
                'verbose_name_plural': 'Projects',
                'ordering': ['-created_at'],
            },
        ),

        # Create Task model
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('status', models.CharField(
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
                ('priority', models.CharField(
                    choices=[
                        ('low', 'Low'),
                        ('medium', 'Medium'),
                        ('high', 'High'),
                        ('urgent', 'Urgent')
                    ],
                    default='medium',
                    max_length=10
                )),
                ('due_date', models.DateField(blank=True, null=True)),
                ('due_time', models.TimeField(
                    blank=True,
                    help_text='Optional specific time',
                    null=True
                )),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('order', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('project', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tasks',
                    to='core.project'
                )),
                ('assignees', models.ManyToManyField(
                    blank=True,
                    related_name='assigned_tasks',
                    to=settings.AUTH_USER_MODEL
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_tasks',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Task',
                'verbose_name_plural': 'Tasks',
                'ordering': ['order', '-priority', 'due_date', 'created_at'],
            },
        ),

        # Create TaskComment model
        migrations.CreateModel(
            name='TaskComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='comments',
                    to='core.task'
                )),
                ('author', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='task_comments',
                    to=settings.AUTH_USER_MODEL
                )),
                ('mentioned_users', models.ManyToManyField(
                    blank=True,
                    related_name='task_comment_mentions',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Task Comment',
                'verbose_name_plural': 'Task Comments',
                'ordering': ['created_at'],
            },
        ),
    ]
