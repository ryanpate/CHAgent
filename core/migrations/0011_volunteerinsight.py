# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0010_reportcache'),
    ]

    operations = [
        migrations.CreateModel(
            name='VolunteerInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('insight_type', models.CharField(
                    choices=[
                        ('engagement_drop', 'Engagement Drop'),
                        ('no_recent_contact', 'No Recent Contact'),
                        ('prayer_need', 'Prayer Need'),
                        ('birthday_upcoming', 'Birthday Upcoming'),
                        ('anniversary_upcoming', 'Anniversary Upcoming'),
                        ('new_volunteer', 'New Volunteer Check-in'),
                        ('returning', 'Returning After Absence'),
                        ('overdue_followup', 'Overdue Follow-up'),
                        ('frequent_declines', 'Frequent Schedule Declines'),
                        ('milestone', 'Service Milestone'),
                    ],
                    db_index=True,
                    help_text='Type of care insight',
                    max_length=30
                )),
                ('priority', models.CharField(
                    choices=[
                        ('low', 'Low'),
                        ('medium', 'Medium'),
                        ('high', 'High'),
                        ('urgent', 'Urgent'),
                    ],
                    db_index=True,
                    default='medium',
                    max_length=10
                )),
                ('title', models.CharField(help_text='Short title for the insight', max_length=200)),
                ('message', models.TextField(help_text='Detailed description of the insight')),
                ('suggested_action', models.TextField(blank=True, help_text='Recommended action to take')),
                ('context_data', models.JSONField(blank=True, default=dict, help_text='Additional context (days since contact, dates, etc.)')),
                ('status', models.CharField(
                    choices=[
                        ('active', 'Active'),
                        ('acknowledged', 'Acknowledged'),
                        ('actioned', 'Actioned'),
                        ('dismissed', 'Dismissed'),
                    ],
                    db_index=True,
                    default='active',
                    max_length=15
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('acknowledged_at', models.DateTimeField(blank=True, null=True)),
                ('acknowledged_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='acknowledged_insights',
                    to=settings.AUTH_USER_MODEL
                )),
                ('volunteer', models.ForeignKey(
                    help_text='The volunteer this insight is about',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='insights',
                    to='core.volunteer'
                )),
            ],
            options={
                'verbose_name': 'Volunteer Insight',
                'verbose_name_plural': 'Volunteer Insights',
                'ordering': ['-priority', '-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='volunteerinsight',
            index=models.Index(fields=['status', 'priority'], name='core_volunt_status_7c5e48_idx'),
        ),
        migrations.AddIndex(
            model_name='volunteerinsight',
            index=models.Index(fields=['insight_type', 'status'], name='core_volunt_insight_d8e9e2_idx'),
        ),
    ]
