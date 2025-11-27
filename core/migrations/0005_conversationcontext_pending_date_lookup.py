from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_conversationcontext_current_song'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversationcontext',
            name='pending_date_lookup',
            field=models.JSONField(blank=True, default=dict, help_text='Pending date lookup waiting for user confirmation (date, query_type)'),
        ),
    ]
