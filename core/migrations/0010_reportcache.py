from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_conversationcontext_pending_disambiguation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('report_type', models.CharField(
                    choices=[
                        ('volunteer_engagement', 'Volunteer Engagement'),
                        ('team_care', 'Team Care'),
                        ('interaction_trends', 'Interaction Trends'),
                        ('prayer_summary', 'Prayer Request Summary'),
                        ('ai_performance', 'AI Performance'),
                        ('service_participation', 'Service Participation'),
                        ('dashboard_summary', 'Dashboard Summary'),
                    ],
                    db_index=True,
                    max_length=50
                )),
                ('parameters', models.JSONField(
                    blank=True,
                    default=dict,
                    help_text='Parameters used to generate this report (date range, filters, etc.)'
                )),
                ('data', models.JSONField(
                    help_text='The generated report data'
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField(
                    help_text='When this cache entry expires'
                )),
            ],
            options={
                'verbose_name': 'Report Cache',
                'verbose_name_plural': 'Report Caches',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='reportcache',
            index=models.Index(fields=['report_type', 'expires_at'], name='core_report_report__3e8f61_idx'),
        ),
    ]
