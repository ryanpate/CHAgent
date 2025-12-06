# Generated migration for push notification models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0012_communication_hub'),
    ]

    operations = [
        migrations.CreateModel(
            name='PushSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('endpoint', models.TextField(unique=True)),
                ('p256dh_key', models.CharField(help_text='Public key for encryption', max_length=200)),
                ('auth_key', models.CharField(help_text='Auth secret for encryption', max_length=100)),
                ('user_agent', models.TextField(blank=True)),
                ('device_name', models.CharField(blank=True, help_text="Friendly name like 'iPhone' or 'Chrome on Mac'", max_length=100)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_used_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='push_subscriptions', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Push Subscription',
                'verbose_name_plural': 'Push Subscriptions',
            },
        ),
        migrations.CreateModel(
            name='NotificationPreference',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('announcements', models.BooleanField(default=True, help_text='New team announcements')),
                ('announcements_urgent_only', models.BooleanField(default=False, help_text='Only urgent announcements')),
                ('direct_messages', models.BooleanField(default=True, help_text='New direct messages')),
                ('channel_messages', models.BooleanField(default=False, help_text='New channel messages')),
                ('channel_mentions_only', models.BooleanField(default=True, help_text='Only when mentioned in channels')),
                ('care_alerts', models.BooleanField(default=True, help_text='Proactive care alerts')),
                ('care_urgent_only', models.BooleanField(default=False, help_text='Only urgent care alerts')),
                ('followup_reminders', models.BooleanField(default=True, help_text='Follow-up due date reminders')),
                ('quiet_hours_enabled', models.BooleanField(default=False)),
                ('quiet_hours_start', models.TimeField(blank=True, help_text='Start of quiet hours (e.g., 22:00)', null=True)),
                ('quiet_hours_end', models.TimeField(blank=True, help_text='End of quiet hours (e.g., 07:00)', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='notification_preferences', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notification Preference',
                'verbose_name_plural': 'Notification Preferences',
            },
        ),
        migrations.CreateModel(
            name='NotificationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(choices=[('announcement', 'Announcement'), ('dm', 'Direct Message'), ('channel', 'Channel Message'), ('care', 'Care Alert'), ('followup', 'Follow-up Reminder'), ('test', 'Test Notification')], max_length=20)),
                ('title', models.CharField(max_length=200)),
                ('body', models.TextField()),
                ('url', models.CharField(blank=True, help_text='URL to open when notification clicked', max_length=500)),
                ('data', models.JSONField(blank=True, default=dict, help_text='Additional data sent with notification')),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'), ('clicked', 'Clicked')], default='pending', max_length=10)),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('clicked_at', models.DateTimeField(blank=True, null=True)),
                ('subscription', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='core.pushsubscription')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='notification_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Notification Log',
                'verbose_name_plural': 'Notification Logs',
                'ordering': ['-created_at'],
            },
        ),
    ]
