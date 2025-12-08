# Generated migration for multi-tenant SaaS functionality
# This migration adds:
# - SubscriptionPlan model for pricing tiers
# - Organization model for church/team tenants
# - OrganizationMembership for user-org relationships
# - OrganizationInvitation for pending invites
# - organization FK to all tenant-scoped models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import secrets


def generate_api_key():
    """Generate a secure API key for organizations."""
    return f"aria_{secrets.token_urlsafe(32)}"


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('core', '0015_task_checklists_templates'),
    ]

    operations = [
        # =================================================================
        # Create SubscriptionPlan model
        # =================================================================
        migrations.CreateModel(
            name='SubscriptionPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('slug', models.SlugField(unique=True)),
                ('tier', models.CharField(
                    max_length=20,
                    choices=[
                        ('free', 'Free Trial'),
                        ('starter', 'Starter'),
                        ('team', 'Team'),
                        ('ministry', 'Ministry'),
                        ('enterprise', 'Enterprise'),
                    ],
                    default='starter'
                )),
                ('description', models.TextField(blank=True)),
                ('price_monthly_cents', models.IntegerField(default=0, help_text='Monthly price in cents')),
                ('price_yearly_cents', models.IntegerField(default=0, help_text='Yearly price in cents')),
                ('max_users', models.IntegerField(default=5, help_text='Maximum team members')),
                ('max_volunteers', models.IntegerField(default=50, help_text='Maximum volunteers tracked')),
                ('max_ai_queries_monthly', models.IntegerField(default=500, help_text='Monthly AI query limit')),
                ('has_pco_integration', models.BooleanField(default=True)),
                ('has_push_notifications', models.BooleanField(default=True)),
                ('has_analytics', models.BooleanField(default=False)),
                ('has_care_insights', models.BooleanField(default=False)),
                ('has_api_access', models.BooleanField(default=False)),
                ('has_custom_branding', models.BooleanField(default=False)),
                ('has_priority_support', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('is_public', models.BooleanField(default=True, help_text='Show on pricing page')),
                ('sort_order', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Subscription Plan',
                'verbose_name_plural': 'Subscription Plans',
                'ordering': ['sort_order', 'price_monthly_cents'],
            },
        ),

        # =================================================================
        # Create Organization model
        # =================================================================
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, help_text='Organization/Church name')),
                ('slug', models.SlugField(max_length=100, unique=True, help_text="URL-friendly identifier")),
                ('logo', models.URLField(blank=True, help_text='URL to organization logo')),
                ('email', models.EmailField(max_length=254, help_text='Primary contact email')),
                ('phone', models.CharField(blank=True, max_length=20)),
                ('website', models.URLField(blank=True)),
                ('address', models.TextField(blank=True)),
                ('timezone', models.CharField(default='America/Denver', max_length=50, help_text='Organization timezone')),
                ('subscription_status', models.CharField(
                    max_length=20,
                    choices=[
                        ('trial', 'Trial'),
                        ('active', 'Active'),
                        ('past_due', 'Past Due'),
                        ('cancelled', 'Cancelled'),
                        ('suspended', 'Suspended'),
                    ],
                    default='trial'
                )),
                ('trial_ends_at', models.DateTimeField(blank=True, null=True, help_text='When the trial period ends')),
                ('subscription_started_at', models.DateTimeField(blank=True, null=True)),
                ('subscription_ends_at', models.DateTimeField(blank=True, null=True)),
                ('stripe_customer_id', models.CharField(blank=True, max_length=100)),
                ('stripe_subscription_id', models.CharField(blank=True, max_length=100)),
                ('planning_center_app_id', models.CharField(blank=True, max_length=200, help_text='Planning Center App ID')),
                ('planning_center_secret', models.CharField(blank=True, max_length=200, help_text='Planning Center Secret')),
                ('planning_center_connected_at', models.DateTimeField(blank=True, null=True)),
                ('api_key', models.CharField(default=generate_api_key, max_length=100, unique=True, help_text='API key for external integrations')),
                ('api_enabled', models.BooleanField(default=False)),
                ('ai_queries_this_month', models.IntegerField(default=0)),
                ('ai_queries_reset_at', models.DateTimeField(blank=True, null=True)),
                ('ai_assistant_name', models.CharField(default='Aria', max_length=50, help_text='Custom name for the AI assistant')),
                ('primary_color', models.CharField(default='#6366f1', max_length=7, help_text='Primary brand color (hex)')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('subscription_plan', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='organizations',
                    to='core.subscriptionplan'
                )),
            ],
            options={
                'verbose_name': 'Organization',
                'verbose_name_plural': 'Organizations',
                'ordering': ['name'],
            },
        ),

        # =================================================================
        # Create OrganizationMembership model
        # =================================================================
        migrations.CreateModel(
            name='OrganizationMembership',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(
                    max_length=20,
                    choices=[
                        ('owner', 'Owner'),
                        ('admin', 'Admin'),
                        ('leader', 'Team Leader'),
                        ('member', 'Member'),
                        ('viewer', 'Viewer'),
                    ],
                    default='member'
                )),
                ('can_manage_users', models.BooleanField(default=False)),
                ('can_manage_settings', models.BooleanField(default=False)),
                ('can_view_analytics', models.BooleanField(default=False)),
                ('can_manage_billing', models.BooleanField(default=False)),
                ('team', models.CharField(blank=True, max_length=100, help_text='Team within the organization')),
                ('is_active', models.BooleanField(default=True)),
                ('invited_at', models.DateTimeField(auto_now_add=True)),
                ('joined_at', models.DateTimeField(blank=True, null=True)),
                ('invited_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='sent_invitations',
                    to=settings.AUTH_USER_MODEL
                )),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='memberships',
                    to='core.organization'
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='organization_memberships',
                    to=settings.AUTH_USER_MODEL
                )),
            ],
            options={
                'verbose_name': 'Organization Membership',
                'verbose_name_plural': 'Organization Memberships',
                'unique_together': {('user', 'organization')},
            },
        ),

        # =================================================================
        # Create OrganizationInvitation model
        # =================================================================
        migrations.CreateModel(
            name='OrganizationInvitation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(max_length=254)),
                ('role', models.CharField(
                    max_length=20,
                    choices=[
                        ('owner', 'Owner'),
                        ('admin', 'Admin'),
                        ('leader', 'Team Leader'),
                        ('member', 'Member'),
                        ('viewer', 'Viewer'),
                    ],
                    default='member'
                )),
                ('team', models.CharField(blank=True, max_length=100)),
                ('token', models.CharField(max_length=100, unique=True)),
                ('status', models.CharField(
                    max_length=20,
                    choices=[
                        ('pending', 'Pending'),
                        ('accepted', 'Accepted'),
                        ('declined', 'Declined'),
                        ('expired', 'Expired'),
                    ],
                    default='pending'
                )),
                ('message', models.TextField(blank=True, help_text='Optional personal message')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
                ('accepted_at', models.DateTimeField(blank=True, null=True)),
                ('invited_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_invitations',
                    to=settings.AUTH_USER_MODEL
                )),
                ('organization', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='invitations',
                    to='core.organization'
                )),
            ],
            options={
                'verbose_name': 'Organization Invitation',
                'verbose_name_plural': 'Organization Invitations',
                'ordering': ['-created_at'],
            },
        ),

        # =================================================================
        # Add organization FK to Volunteer
        # =================================================================
        migrations.AddField(
            model_name='volunteer',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='volunteers',
                to='core.organization'
            ),
        ),
        # Remove the unique constraint on planning_center_id and add unique_together
        migrations.AlterField(
            model_name='volunteer',
            name='planning_center_id',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddIndex(
            model_name='volunteer',
            index=models.Index(fields=['organization', 'normalized_name'], name='core_volunt_organiz_idx'),
        ),

        # =================================================================
        # Add organization FK to Interaction
        # =================================================================
        migrations.AddField(
            model_name='interaction',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='interactions',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to ChatMessage
        # =================================================================
        migrations.AddField(
            model_name='chatmessage',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='chat_messages',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to ConversationContext
        # =================================================================
        migrations.AddField(
            model_name='conversationcontext',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='conversation_contexts',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to FollowUp
        # =================================================================
        migrations.AddField(
            model_name='followup',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='followups',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to ResponseFeedback
        # =================================================================
        migrations.AddField(
            model_name='responsefeedback',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='response_feedbacks',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to LearnedCorrection
        # =================================================================
        migrations.AddField(
            model_name='learnedcorrection',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='learned_corrections',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to ExtractedKnowledge
        # =================================================================
        migrations.AddField(
            model_name='extractedknowledge',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='extracted_knowledge',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to QueryPattern
        # =================================================================
        migrations.AddField(
            model_name='querypattern',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='query_patterns',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to ReportCache
        # =================================================================
        migrations.AddField(
            model_name='reportcache',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='report_caches',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to VolunteerInsight
        # =================================================================
        migrations.AddField(
            model_name='volunteerinsight',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='volunteer_insights',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to Announcement
        # =================================================================
        migrations.AddField(
            model_name='announcement',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='announcements',
                to='core.organization'
            ),
        ),

        # =================================================================
        # Add organization FK to Channel
        # =================================================================
        migrations.AddField(
            model_name='channel',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='channels',
                to='core.organization'
            ),
        ),
        # Update Channel.slug to not be globally unique (unique within org)
        migrations.AlterField(
            model_name='channel',
            name='slug',
            field=models.SlugField(max_length=100),
        ),

        # =================================================================
        # Add organization FK to Project
        # =================================================================
        migrations.AddField(
            model_name='project',
            name='organization',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='projects',
                to='core.organization'
            ),
        ),
    ]
