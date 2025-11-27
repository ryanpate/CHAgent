from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0005_conversationcontext_pending_date_lookup'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversationcontext',
            name='pending_followup',
            field=models.JSONField(blank=True, default=dict, help_text='Pending follow-up item waiting for date (title, description, volunteer_name, category)'),
        ),
        migrations.CreateModel(
            name='FollowUp',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(help_text='Brief title/summary of the follow-up', max_length=200)),
                ('description', models.TextField(blank=True, help_text='Detailed description of what needs to be followed up on')),
                ('category', models.CharField(blank=True, help_text="Category (e.g., 'prayer_request', 'concern', 'action_item', 'feedback')", max_length=50)),
                ('follow_up_date', models.DateField(blank=True, help_text='When to follow up', null=True)),
                ('reminder_sent', models.BooleanField(default=False, help_text='Whether a reminder has been sent for this follow-up')),
                ('priority', models.CharField(choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High'), ('urgent', 'Urgent')], default='medium', max_length=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')], default='pending', max_length=15)),
                ('completed_at', models.DateTimeField(blank=True, help_text='When this follow-up was completed', null=True)),
                ('completion_notes', models.TextField(blank=True, help_text='Notes about how this was resolved')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('assigned_to', models.ForeignKey(blank=True, help_text='Team member assigned to handle this follow-up', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assigned_followups', to=settings.AUTH_USER_MODEL)),
                ('created_by', models.ForeignKey(help_text='Team member who created this follow-up', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_followups', to=settings.AUTH_USER_MODEL)),
                ('source_interaction', models.ForeignKey(blank=True, help_text='The interaction that triggered this follow-up', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='followups', to='core.interaction')),
                ('volunteer', models.ForeignKey(blank=True, help_text='Volunteer this follow-up is about', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='followups', to='core.volunteer')),
            ],
            options={
                'verbose_name': 'Follow-up',
                'verbose_name_plural': 'Follow-ups',
                'ordering': ['follow_up_date', '-priority', '-created_at'],
            },
        ),
    ]
