from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0007_learning_system_models'),
    ]

    operations = [
        # Add issue tracking fields
        migrations.AddField(
            model_name='responsefeedback',
            name='issue_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('missing_info', 'Information was missing'),
                    ('wrong_info', 'Information was incorrect'),
                    ('wrong_volunteer', 'Wrong volunteer identified'),
                    ('no_response', 'No useful response'),
                    ('slow_response', 'Response was too slow'),
                    ('formatting', 'Response formatting issue'),
                    ('other', 'Other issue'),
                ],
                help_text='Category of issue (for negative feedback)',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='responsefeedback',
            name='expected_result',
            field=models.TextField(
                blank=True,
                help_text='What the user expected to see',
            ),
        ),
        # Add resolution tracking fields
        migrations.AddField(
            model_name='responsefeedback',
            name='resolved',
            field=models.BooleanField(
                default=False,
                help_text='Whether this issue has been addressed',
            ),
        ),
        migrations.AddField(
            model_name='responsefeedback',
            name='resolved_by',
            field=models.ForeignKey(
                blank=True,
                help_text='Admin who resolved this issue',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='resolved_feedbacks',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name='responsefeedback',
            name='resolved_at',
            field=models.DateTimeField(
                blank=True,
                help_text='When the issue was resolved',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='responsefeedback',
            name='resolution_notes',
            field=models.TextField(
                blank=True,
                help_text='Notes about how the issue was resolved',
            ),
        ),
    ]
