from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_add_issue_reporting_to_feedback'),
    ]

    operations = [
        migrations.AddField(
            model_name='conversationcontext',
            name='pending_disambiguation',
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text='Pending disambiguation when query is ambiguous (extracted_value, original_query)'
            ),
        ),
    ]
