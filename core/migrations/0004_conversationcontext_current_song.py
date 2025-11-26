from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_conversationcontext_pending_song_suggestions'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversationcontext',
            name='current_song',
            field=models.JSONField(blank=True, default=dict, help_text='Current song being discussed (title, id, etc.) for context in follow-up queries'),
        ),
    ]
