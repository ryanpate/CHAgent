import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConversationContext',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(db_index=True, max_length=100, unique=True)),
                ('shown_interaction_ids', models.JSONField(blank=True, default=list, help_text='List of Interaction IDs already shown in this conversation')),
                ('discussed_volunteer_ids', models.JSONField(blank=True, default=list, help_text='List of Volunteer IDs mentioned/discussed in this conversation')),
                ('conversation_summary', models.TextField(blank=True, help_text='AI-generated summary of conversation so far (for long conversations)')),
                ('current_topic', models.CharField(blank=True, help_text='The current topic or volunteer being discussed', max_length=500)),
                ('message_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversation_contexts', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
    ]
