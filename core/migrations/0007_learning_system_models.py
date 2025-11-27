from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0006_followup_conversationcontext_pending_followup'),
    ]

    operations = [
        # ResponseFeedback model - stores user feedback on AI responses
        migrations.CreateModel(
            name='ResponseFeedback',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feedback_type', models.CharField(choices=[('positive', 'Helpful'), ('negative', 'Not Helpful')], help_text='Whether the response was helpful or not', max_length=10)),
                ('comment', models.TextField(blank=True, help_text='Optional explanation for the feedback')),
                ('query_type', models.CharField(blank=True, help_text="Type of query (e.g., 'volunteer_info', 'setlist', 'lyrics')", max_length=50)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('chat_message', models.OneToOneField(help_text='The AI response being rated', on_delete=django.db.models.deletion.CASCADE, related_name='feedback', to='core.chatmessage')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='response_feedbacks', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Response Feedback',
                'verbose_name_plural': 'Response Feedbacks',
                'ordering': ['-created_at'],
            },
        ),
        # LearnedCorrection model - stores corrections learned from users
        migrations.CreateModel(
            name='LearnedCorrection',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('incorrect_value', models.CharField(db_index=True, help_text='The incorrect term/value that was used', max_length=500)),
                ('correct_value', models.CharField(help_text='The correct term/value to use instead', max_length=500)),
                ('correction_type', models.CharField(choices=[('spelling', 'Spelling/Name'), ('fact', 'Factual Correction'), ('preference', 'Terminology Preference'), ('context', 'Contextual Correction')], default='spelling', max_length=20)),
                ('times_applied', models.IntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('corrected_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='provided_corrections', to=settings.AUTH_USER_MODEL)),
                ('volunteer', models.ForeignKey(blank=True, help_text='The volunteer this correction is about (if applicable)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='corrections', to='core.volunteer')),
            ],
            options={
                'verbose_name': 'Learned Correction',
                'verbose_name_plural': 'Learned Corrections',
                'ordering': ['-times_applied', '-created_at'],
                'unique_together': {('incorrect_value', 'volunteer')},
            },
        ),
        # ExtractedKnowledge model - stores knowledge extracted from interactions
        migrations.CreateModel(
            name='ExtractedKnowledge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('knowledge_type', models.CharField(choices=[('hobby', 'Hobby/Interest'), ('family', 'Family Info'), ('preference', 'Preference'), ('birthday', 'Birthday'), ('anniversary', 'Anniversary'), ('prayer_request', 'Prayer Request'), ('health', 'Health Info'), ('work', 'Work/Career'), ('availability', 'Availability'), ('skill', 'Skill/Talent'), ('contact', 'Contact Info'), ('other', 'Other')], db_index=True, max_length=20)),
                ('key', models.CharField(help_text="The knowledge key (e.g., 'favorite_food', 'children_count')", max_length=100)),
                ('value', models.TextField(help_text='The knowledge value')),
                ('confidence', models.CharField(choices=[('high', 'High - Directly stated'), ('medium', 'Medium - Inferred'), ('low', 'Low - Uncertain')], default='medium', max_length=10)),
                ('is_verified', models.BooleanField(default=False, help_text='Whether this knowledge has been verified by a human')),
                ('is_current', models.BooleanField(default=True, help_text='Whether this knowledge is still current')),
                ('last_confirmed', models.DateTimeField(blank=True, help_text='When this knowledge was last confirmed as accurate', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('extracted_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='extracted_knowledge', to=settings.AUTH_USER_MODEL)),
                ('source_interaction', models.ForeignKey(blank=True, help_text='The interaction where this was learned', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='extracted_knowledge', to='core.interaction')),
                ('volunteer', models.ForeignKey(help_text='The volunteer this knowledge is about', on_delete=django.db.models.deletion.CASCADE, related_name='knowledge', to='core.volunteer')),
            ],
            options={
                'verbose_name': 'Extracted Knowledge',
                'verbose_name_plural': 'Extracted Knowledge',
                'ordering': ['-confidence', '-updated_at'],
                'unique_together': {('volunteer', 'knowledge_type', 'key')},
            },
        ),
        # QueryPattern model - stores successful query patterns
        migrations.CreateModel(
            name='QueryPattern',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query_text', models.TextField(help_text='The original query from the user')),
                ('normalized_query', models.CharField(db_index=True, help_text='Normalized version of the query for matching', max_length=500)),
                ('detected_intent', models.CharField(db_index=True, help_text="The intent that was detected (e.g., 'volunteer_info', 'setlist')", max_length=50)),
                ('extracted_entities', models.JSONField(blank=True, default=dict, help_text='Entities extracted from the query (names, dates, etc.)')),
                ('match_count', models.IntegerField(default=1)),
                ('success_count', models.IntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('validated_by_feedback', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='validated_patterns', to='core.responsefeedback')),
            ],
            options={
                'verbose_name': 'Query Pattern',
                'verbose_name_plural': 'Query Patterns',
                'ordering': ['-match_count', '-success_count'],
            },
        ),
    ]
