from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_conversationcontext'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversationcontext',
            name='pending_song_suggestions',
            field=models.JSONField(blank=True, default=list, help_text='List of song suggestions waiting for user selection'),
        ),
    ]
