# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0011_volunteerinsight'),
    ]

    operations = [
        # Announcement model
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('content', models.TextField(help_text='Announcement content (supports markdown)')),
                ('priority', models.CharField(
                    choices=[('normal', 'Normal'), ('important', 'Important'), ('urgent', 'Urgent')],
                    default='normal',
                    max_length=10
                )),
                ('target_teams', models.JSONField(blank=True, default=list, help_text='List of team names to target, empty means all teams')),
                ('is_pinned', models.BooleanField(default=False)),
                ('publish_at', models.DateTimeField(blank=True, help_text='Schedule announcement for future (null = immediate)', null=True)),
                ('expires_at', models.DateTimeField(blank=True, help_text='Auto-hide after this date', null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='announcements',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Announcement',
                'verbose_name_plural': 'Announcements',
                'ordering': ['-is_pinned', '-priority', '-created_at'],
            },
        ),
        # AnnouncementRead model
        migrations.CreateModel(
            name='AnnouncementRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('read_at', models.DateTimeField(auto_now_add=True)),
                ('announcement', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reads',
                    to='core.announcement'
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='announcement_reads',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'unique_together': {('announcement', 'user')},
            },
        ),
        # Channel model
        migrations.CreateModel(
            name='Channel',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('description', models.TextField(blank=True)),
                ('channel_type', models.CharField(
                    choices=[('team', 'Team Channel'), ('topic', 'Topic Channel'), ('project', 'Project Channel'), ('general', 'General')],
                    default='general',
                    max_length=10
                )),
                ('team_name', models.CharField(blank=True, help_text='For team channels, the team this channel is for', max_length=100)),
                ('is_private', models.BooleanField(default=False, help_text='Private channels require membership')),
                ('is_archived', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_channels',
                    to=settings.AUTH_USER_MODEL
                )),
                ('members', models.ManyToManyField(
                    blank=True,
                    related_name='channels',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Channel',
                'verbose_name_plural': 'Channels',
                'ordering': ['name'],
            },
        ),
        # ChannelMessage model
        migrations.CreateModel(
            name='ChannelMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('is_edited', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='channel_messages',
                    to=settings.AUTH_USER_MODEL
                )),
                ('channel', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='messages',
                    to='core.channel'
                )),
                ('mentioned_volunteers', models.ManyToManyField(
                    blank=True,
                    related_name='channel_mentions',
                    to='core.volunteer'
                )),
                ('parent', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='replies',
                    to='core.channelmessage'
                )),
            ],
            options={
                'verbose_name': 'Channel Message',
                'verbose_name_plural': 'Channel Messages',
                'ordering': ['created_at'],
            },
        ),
        # DirectMessage model
        migrations.CreateModel(
            name='DirectMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('recipient', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='received_messages',
                    to=settings.AUTH_USER_MODEL
                )),
                ('sender', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_messages',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Direct Message',
                'verbose_name_plural': 'Direct Messages',
                'ordering': ['-created_at'],
            },
        ),
    ]
