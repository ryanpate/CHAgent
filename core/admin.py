from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import (
    Volunteer, Interaction, ChatMessage, ResponseFeedback, ReportCache, SongBPMCache,
    Announcement, AnnouncementRead, Channel, ChannelMessage, DirectMessage,
    Project, Task, TaskComment, TaskChecklist, TaskTemplate,
    Organization, OrganizationMembership, OrganizationInvitation, SubscriptionPlan
)


# =============================================================================
# Organization and Multi-Tenant Admin
# =============================================================================

class OrganizationMembershipInline(admin.TabularInline):
    """Inline admin for managing organization memberships."""
    model = OrganizationMembership
    extra = 1
    fields = ('user', 'role', 'team', 'can_manage_users', 'can_manage_settings', 'can_view_analytics', 'can_manage_billing', 'is_active')
    autocomplete_fields = ['user']


class OrganizationInvitationInline(admin.TabularInline):
    """Inline admin for managing pending invitations."""
    model = OrganizationInvitation
    extra = 0
    fields = ('email', 'role', 'team', 'status', 'created_at', 'expires_at')
    readonly_fields = ('created_at',)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    """Admin configuration for SubscriptionPlan model."""
    list_display = ('name', 'tier', 'price_monthly_display', 'price_yearly_display', 'max_users', 'max_volunteers', 'is_active')
    list_filter = ('tier', 'is_active', 'is_public')
    search_fields = ('name', 'description')
    ordering = ('sort_order', 'price_monthly_cents')
    fieldsets = (
        ('Plan Info', {
            'fields': ('name', 'slug', 'tier', 'description', 'is_active', 'is_public', 'sort_order')
        }),
        ('Pricing', {
            'fields': ('price_monthly_cents', 'price_yearly_cents')
        }),
        ('Limits', {
            'fields': ('max_users', 'max_volunteers', 'max_ai_queries_monthly')
        }),
        ('Features', {
            'fields': ('has_pco_integration', 'has_push_notifications', 'has_analytics', 'has_care_insights', 'has_api_access', 'has_custom_branding', 'has_priority_support')
        }),
    )

    def price_monthly_display(self, obj):
        """Display monthly price in dollars."""
        return f"${obj.price_monthly_cents / 100:.2f}"
    price_monthly_display.short_description = 'Monthly'
    price_monthly_display.admin_order_field = 'price_monthly_cents'

    def price_yearly_display(self, obj):
        """Display yearly price in dollars."""
        return f"${obj.price_yearly_cents / 100:.2f}"
    price_yearly_display.short_description = 'Yearly'
    price_yearly_display.admin_order_field = 'price_yearly_cents'


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    """Admin configuration for Organization model."""
    list_display = ('name', 'status_badge', 'subscription_plan', 'user_count', 'volunteer_count', 'pco_status', 'created_at')
    list_filter = ('subscription_status', 'subscription_plan', 'is_active', 'created_at')
    search_fields = ('name', 'slug', 'email')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'api_key')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [OrganizationMembershipInline, OrganizationInvitationInline]
    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'slug', 'logo', 'is_active')
        }),
        ('Contact', {
            'fields': ('email', 'phone', 'website', 'address', 'timezone')
        }),
        ('Subscription', {
            'fields': ('subscription_plan', 'subscription_status', 'trial_ends_at', 'subscription_started_at', 'subscription_ends_at')
        }),
        ('Billing (Stripe)', {
            'fields': ('stripe_customer_id', 'stripe_subscription_id'),
            'classes': ('collapse',),
        }),
        ('Planning Center', {
            'fields': ('planning_center_app_id', 'planning_center_secret', 'planning_center_connected_at'),
            'classes': ('collapse',),
        }),
        ('API Access', {
            'fields': ('api_key', 'api_enabled'),
            'classes': ('collapse',),
        }),
        ('Usage', {
            'fields': ('ai_queries_this_month', 'ai_queries_reset_at'),
            'classes': ('collapse',),
        }),
        ('Customization', {
            'fields': ('ai_assistant_name', 'primary_color'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        """Display subscription status with color badge."""
        colors = {
            'trial': '#8b5cf6',
            'active': '#22c55e',
            'past_due': '#f59e0b',
            'cancelled': '#ef4444',
            'suspended': '#6b7280',
        }
        color = colors.get(obj.subscription_status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_subscription_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'subscription_status'

    def user_count(self, obj):
        """Display user count."""
        return obj.get_user_count()
    user_count.short_description = 'Users'

    def volunteer_count(self, obj):
        """Display volunteer count."""
        return obj.get_volunteer_count()
    volunteer_count.short_description = 'Volunteers'

    def pco_status(self, obj):
        """Display Planning Center connection status."""
        if obj.has_pco_credentials():
            return format_html('<span style="color: #22c55e;">Connected</span>')
        return format_html('<span style="color: #6b7280;">Not connected</span>')
    pco_status.short_description = 'PCO'


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    """Admin configuration for OrganizationMembership model."""
    list_display = ('user', 'organization', 'role_badge', 'team', 'is_active', 'joined_at')
    list_filter = ('role', 'organization', 'is_active', 'team')
    search_fields = ('user__username', 'user__email', 'organization__name')
    ordering = ('organization', 'user')
    autocomplete_fields = ['user', 'organization']
    fieldsets = (
        ('Membership', {
            'fields': ('user', 'organization', 'role', 'team', 'is_active')
        }),
        ('Permissions', {
            'fields': ('can_manage_users', 'can_manage_settings', 'can_view_analytics', 'can_manage_billing')
        }),
        ('Invitation Details', {
            'fields': ('invited_by', 'invited_at', 'joined_at'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('invited_at',)

    def role_badge(self, obj):
        """Display role with color badge."""
        colors = {
            'owner': '#ef4444',
            'admin': '#f59e0b',
            'leader': '#3b82f6',
            'member': '#22c55e',
            'viewer': '#6b7280',
        }
        color = colors.get(obj.role, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_role_display()
        )
    role_badge.short_description = 'Role'
    role_badge.admin_order_field = 'role'


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    """Admin configuration for OrganizationInvitation model."""
    list_display = ('email', 'organization', 'role', 'status_badge', 'invited_by', 'created_at', 'expires_at')
    list_filter = ('status', 'role', 'organization', 'created_at')
    search_fields = ('email', 'organization__name')
    ordering = ('-created_at',)
    readonly_fields = ('token', 'created_at', 'accepted_at')
    fieldsets = (
        ('Invitation', {
            'fields': ('organization', 'email', 'role', 'team', 'message')
        }),
        ('Status', {
            'fields': ('status', 'token', 'expires_at', 'accepted_at')
        }),
        ('Metadata', {
            'fields': ('invited_by', 'created_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            'pending': '#f59e0b',
            'accepted': '#22c55e',
            'declined': '#ef4444',
            'expired': '#6b7280',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'


# =============================================================================
# Core Models Admin
# =============================================================================

@admin.register(Volunteer)
class VolunteerAdmin(admin.ModelAdmin):
    """Admin configuration for Volunteer model."""
    list_display = ('name', 'team', 'planning_center_id', 'created_at', 'updated_at')
    list_filter = ('team', 'created_at')
    search_fields = ('name', 'normalized_name', 'team', 'planning_center_id')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    """Admin configuration for Interaction model."""
    list_display = ('__str__', 'user', 'get_volunteers', 'created_at')
    list_filter = ('created_at', 'user')
    search_fields = ('content', 'ai_summary', 'user__username', 'volunteers__name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'ai_summary', 'ai_extracted_data')
    filter_horizontal = ('volunteers',)

    def get_volunteers(self, obj):
        """Display volunteers as a comma-separated list."""
        return ", ".join([v.name for v in obj.volunteers.all()[:3]])
    get_volunteers.short_description = 'Volunteers'


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    """Admin configuration for ChatMessage model."""
    list_display = ('user', 'role', 'short_content', 'session_id', 'created_at')
    list_filter = ('role', 'created_at', 'user')
    search_fields = ('content', 'session_id', 'user__username')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)

    def short_content(self, obj):
        """Display truncated content."""
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    short_content.short_description = 'Content'


@admin.register(ResponseFeedback)
class ResponseFeedbackAdmin(admin.ModelAdmin):
    """Admin configuration for ResponseFeedback model with issue tracking."""
    list_display = (
        'id',
        'feedback_type_badge',
        'issue_type',
        'user',
        'short_response',
        'resolved_status',
        'created_at',
    )
    list_filter = (
        'feedback_type',
        'issue_type',
        'resolved',
        'created_at',
        'user',
    )
    search_fields = (
        'chat_message__content',
        'comment',
        'expected_result',
        'resolution_notes',
        'user__username',
    )
    ordering = ('-created_at',)
    readonly_fields = (
        'chat_message',
        'user',
        'feedback_type',
        'created_at',
        'user_question',
        'ai_response_preview',
    )
    fieldsets = (
        ('Feedback Details', {
            'fields': (
                'feedback_type',
                'user',
                'created_at',
            )
        }),
        ('Conversation Context', {
            'fields': (
                'user_question',
                'ai_response_preview',
            ),
            'classes': ('collapse',),
        }),
        ('Issue Details', {
            'fields': (
                'issue_type',
                'expected_result',
                'comment',
            )
        }),
        ('Resolution', {
            'fields': (
                'resolved',
                'resolved_by',
                'resolved_at',
                'resolution_notes',
            )
        }),
    )
    actions = ['mark_resolved', 'mark_unresolved']

    def feedback_type_badge(self, obj):
        """Display feedback type with color badge."""
        if obj.feedback_type == 'positive':
            return format_html(
                '<span style="background-color: #22c55e; color: white; padding: 2px 8px; '
                'border-radius: 4px; font-size: 11px;">Helpful</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #ef4444; color: white; padding: 2px 8px; '
                'border-radius: 4px; font-size: 11px;">Not Helpful</span>'
            )
    feedback_type_badge.short_description = 'Feedback'
    feedback_type_badge.admin_order_field = 'feedback_type'

    def resolved_status(self, obj):
        """Display resolution status with icon."""
        if obj.feedback_type == 'positive':
            return format_html('<span style="color: #888;">N/A</span>')
        if obj.resolved:
            return format_html(
                '<span style="color: #22c55e;" title="Resolved">&#10003;</span>'
            )
        return format_html(
            '<span style="color: #ef4444;" title="Unresolved">&#10007;</span>'
        )
    resolved_status.short_description = 'Resolved'
    resolved_status.admin_order_field = 'resolved'

    def short_response(self, obj):
        """Display truncated AI response."""
        content = obj.chat_message.content if obj.chat_message else ''
        return content[:60] + '...' if len(content) > 60 else content
    short_response.short_description = 'AI Response'

    def user_question(self, obj):
        """Display the user's question that preceded this response."""
        if not obj.chat_message:
            return "No message"
        # Find the user message that preceded this response
        from .models import ChatMessage
        user_message = ChatMessage.objects.filter(
            user=obj.chat_message.user,
            session_id=obj.chat_message.session_id,
            role='user',
            created_at__lt=obj.chat_message.created_at
        ).order_by('-created_at').first()
        if user_message:
            return user_message.content
        return "Question not found"
    user_question.short_description = 'User Question'

    def ai_response_preview(self, obj):
        """Display the full AI response."""
        if obj.chat_message:
            return obj.chat_message.content
        return "No response"
    ai_response_preview.short_description = 'AI Response'

    @admin.action(description='Mark selected feedback as resolved')
    def mark_resolved(self, request, queryset):
        updated = queryset.filter(feedback_type='negative').update(
            resolved=True,
            resolved_by=request.user,
            resolved_at=timezone.now()
        )
        self.message_user(request, f'{updated} issue(s) marked as resolved.')

    @admin.action(description='Mark selected feedback as unresolved')
    def mark_unresolved(self, request, queryset):
        updated = queryset.update(
            resolved=False,
            resolved_by=None,
            resolved_at=None
        )
        self.message_user(request, f'{updated} feedback(s) marked as unresolved.')


@admin.register(ReportCache)
class ReportCacheAdmin(admin.ModelAdmin):
    """Admin configuration for ReportCache model."""
    list_display = ('report_type', 'created_at', 'expires_at', 'is_expired_status', 'parameters_preview')
    list_filter = ('report_type', 'created_at', 'expires_at')
    search_fields = ('report_type',)
    ordering = ('-created_at',)
    readonly_fields = ('report_type', 'parameters', 'data', 'created_at', 'expires_at')
    actions = ['clear_expired_caches', 'clear_all_caches']

    def is_expired_status(self, obj):
        """Display expiration status with icon."""
        if obj.is_expired:
            return format_html(
                '<span style="color: #ef4444;" title="Expired">Expired</span>'
            )
        return format_html(
            '<span style="color: #22c55e;" title="Valid">Valid</span>'
        )
    is_expired_status.short_description = 'Status'

    def parameters_preview(self, obj):
        """Display truncated parameters."""
        params = str(obj.parameters)
        return params[:50] + '...' if len(params) > 50 else params
    parameters_preview.short_description = 'Parameters'

    @admin.action(description='Clear expired cache entries')
    def clear_expired_caches(self, request, queryset):
        count = ReportCache.clear_expired()
        self.message_user(request, f'{count} expired cache entry(ies) deleted.')

    @admin.action(description='Clear all cache entries')
    def clear_all_caches(self, request, queryset):
        count = ReportCache.clear_all()
        self.message_user(request, f'{count} cache entry(ies) deleted.')


@admin.register(SongBPMCache)
class SongBPMCacheAdmin(admin.ModelAdmin):
    """Admin configuration for SongBPMCache model."""
    list_display = (
        'song_title',
        'bpm',
        'bpm_source_badge',
        'confidence_badge',
        'song_artist',
        'organization',
        'updated_at',
    )
    list_filter = ('bpm_source', 'confidence', 'organization', 'created_at')
    search_fields = ('song_title', 'song_artist', 'pco_song_id')
    ordering = ('-updated_at',)
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Song Information', {
            'fields': (
                'song_title',
                'song_artist',
                'pco_song_id',
                'pco_arrangement_id',
                'organization',
            )
        }),
        ('BPM Data', {
            'fields': (
                'bpm',
                'bpm_source',
                'confidence',
                'source_metadata',
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    actions = ['clear_selected_cache']

    def bpm_source_badge(self, obj):
        """Display BPM source with color badge."""
        colors = {
            'pco': '#22c55e',  # Green
            'chord_chart': '#3b82f6',  # Blue
            'audio_analysis': '#f59e0b',  # Amber
            'songbpm_api': '#8b5cf6',  # Purple
            'manual': '#6b7280',  # Gray
        }
        color = colors.get(obj.bpm_source, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_bpm_source_display()
        )
    bpm_source_badge.short_description = 'Source'
    bpm_source_badge.admin_order_field = 'bpm_source'

    def confidence_badge(self, obj):
        """Display confidence level with color badge."""
        colors = {
            'high': '#22c55e',  # Green
            'medium': '#f59e0b',  # Amber
            'low': '#ef4444',  # Red
        }
        color = colors.get(obj.confidence, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_confidence_display()
        )
    confidence_badge.short_description = 'Confidence'
    confidence_badge.admin_order_field = 'confidence'

    @admin.action(description='Clear selected BPM cache entries')
    def clear_selected_cache(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f'{count} BPM cache entry(ies) deleted.')


# =============================================================================
# Team Communication Hub Admin
# =============================================================================

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    """Admin configuration for Announcement model."""
    list_display = ('title', 'priority_badge', 'author', 'is_pinned', 'is_active', 'organization', 'created_at')
    list_filter = ('priority', 'is_pinned', 'is_active', 'organization', 'created_at')
    search_fields = ('title', 'content', 'author__username')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ()
    fieldsets = (
        ('Content', {
            'fields': ('title', 'content', 'author', 'organization')
        }),
        ('Settings', {
            'fields': ('priority', 'is_pinned', 'is_active', 'target_teams')
        }),
        ('Scheduling', {
            'fields': ('publish_at', 'expires_at'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def priority_badge(self, obj):
        """Display priority with color badge."""
        colors = {
            'normal': '#6b7280',
            'important': '#f59e0b',
            'urgent': '#ef4444',
        }
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    priority_badge.admin_order_field = 'priority'


@admin.register(AnnouncementRead)
class AnnouncementReadAdmin(admin.ModelAdmin):
    """Admin configuration for AnnouncementRead model."""
    list_display = ('announcement', 'user', 'read_at')
    list_filter = ('read_at',)
    search_fields = ('announcement__title', 'user__username')
    ordering = ('-read_at',)
    readonly_fields = ('read_at',)


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    """Admin configuration for Channel model."""
    list_display = ('name', 'channel_type', 'is_private', 'is_archived', 'organization', 'created_by', 'created_at')
    list_filter = ('channel_type', 'is_private', 'is_archived', 'organization', 'created_at')
    search_fields = ('name', 'description', 'slug')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('members',)
    prepopulated_fields = {'slug': ('name',)}
    fieldsets = (
        ('Channel Info', {
            'fields': ('name', 'slug', 'description', 'organization')
        }),
        ('Type & Settings', {
            'fields': ('channel_type', 'team_name', 'is_private', 'is_archived')
        }),
        ('Members', {
            'fields': ('members', 'created_by'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(ChannelMessage)
class ChannelMessageAdmin(admin.ModelAdmin):
    """Admin configuration for ChannelMessage model."""
    list_display = ('short_content', 'channel', 'author', 'is_edited', 'created_at')
    list_filter = ('channel', 'is_edited', 'created_at')
    search_fields = ('content', 'author__username', 'channel__name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('mentioned_users', 'mentioned_volunteers')

    def short_content(self, obj):
        """Display truncated content."""
        return obj.content[:60] + '...' if len(obj.content) > 60 else obj.content
    short_content.short_description = 'Content'


@admin.register(DirectMessage)
class DirectMessageAdmin(admin.ModelAdmin):
    """Admin configuration for DirectMessage model."""
    list_display = ('short_content', 'sender', 'recipient', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('content', 'sender__username', 'recipient__username')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'read_at')

    def short_content(self, obj):
        """Display truncated content."""
        return obj.content[:60] + '...' if len(obj.content) > 60 else obj.content
    short_content.short_description = 'Content'


# =============================================================================
# Project and Task Management Admin
# =============================================================================

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    """Admin configuration for Project model."""
    list_display = ('name', 'status_badge', 'priority_badge', 'owner', 'due_date', 'progress_display', 'organization', 'created_at')
    list_filter = ('status', 'priority', 'organization', 'created_at')
    search_fields = ('name', 'description', 'owner__username')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    filter_horizontal = ('members',)
    fieldsets = (
        ('Project Info', {
            'fields': ('name', 'description', 'organization')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority')
        }),
        ('Dates', {
            'fields': ('start_date', 'due_date', 'service_date', 'completed_at')
        }),
        ('Team', {
            'fields': ('owner', 'members', 'channel')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            'planning': '#6b7280',
            'active': '#22c55e',
            'on_hold': '#f59e0b',
            'completed': '#3b82f6',
            'archived': '#4b5563',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def priority_badge(self, obj):
        """Display priority with color badge."""
        colors = {
            'low': '#6b7280',
            'medium': '#3b82f6',
            'high': '#f59e0b',
            'urgent': '#ef4444',
        }
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    priority_badge.admin_order_field = 'priority'

    def progress_display(self, obj):
        """Display progress as a percentage bar."""
        progress = obj.progress_percent
        color = '#22c55e' if progress == 100 else '#3b82f6' if progress > 50 else '#f59e0b'
        return format_html(
            '<div style="width: 100px; background: #374151; border-radius: 4px; overflow: hidden;">'
            '<div style="width: {}%; background: {}; height: 16px; text-align: center; color: white; '
            'font-size: 10px; line-height: 16px;">{}</div></div>',
            progress, color, f'{progress}%'
        )
    progress_display.short_description = 'Progress'


class TaskChecklistInline(admin.TabularInline):
    """Inline admin for TaskChecklist items within Task."""
    model = TaskChecklist
    extra = 0
    fields = ('title', 'is_completed', 'order', 'completed_by', 'completed_at')
    readonly_fields = ('completed_by', 'completed_at')


class TaskCommentInline(admin.TabularInline):
    """Inline admin for TaskComment items within Task."""
    model = TaskComment
    extra = 0
    fields = ('content', 'author', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    """Admin configuration for Task model."""
    list_display = ('title', 'project', 'status_badge', 'priority_badge', 'get_assignees', 'due_date', 'is_overdue_display', 'created_at')
    list_filter = ('status', 'priority', 'project', 'due_date', 'created_at')
    search_fields = ('title', 'description', 'project__name')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at', 'completed_at')
    filter_horizontal = ('assignees',)
    inlines = [TaskChecklistInline, TaskCommentInline]
    fieldsets = (
        ('Task Info', {
            'fields': ('title', 'description', 'project')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'order')
        }),
        ('Assignment', {
            'fields': ('assignees', 'created_by')
        }),
        ('Dates', {
            'fields': ('due_date', 'due_time', 'completed_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        """Display status with color badge."""
        colors = {
            'todo': '#6b7280',
            'in_progress': '#3b82f6',
            'review': '#f59e0b',
            'completed': '#22c55e',
            'cancelled': '#4b5563',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def priority_badge(self, obj):
        """Display priority with color badge."""
        colors = {
            'low': '#6b7280',
            'medium': '#3b82f6',
            'high': '#f59e0b',
            'urgent': '#ef4444',
        }
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; '
            'border-radius: 4px; font-size: 11px;">{}</span>',
            color,
            obj.get_priority_display()
        )
    priority_badge.short_description = 'Priority'
    priority_badge.admin_order_field = 'priority'

    def get_assignees(self, obj):
        """Display assignees as a comma-separated list."""
        assignees = obj.assignees.all()[:3]
        names = [a.get_full_name() or a.username for a in assignees]
        if obj.assignees.count() > 3:
            names.append(f'+{obj.assignees.count() - 3} more')
        return ', '.join(names) if names else '-'
    get_assignees.short_description = 'Assignees'

    def is_overdue_display(self, obj):
        """Display overdue status with icon."""
        if obj.is_overdue:
            return format_html(
                '<span style="color: #ef4444;" title="Overdue">&#9888; Overdue</span>'
            )
        return format_html('<span style="color: #22c55e;">&#10003;</span>')
    is_overdue_display.short_description = 'On Time'


@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    """Admin configuration for TaskComment model."""
    list_display = ('short_content', 'task', 'author', 'created_at')
    list_filter = ('task__project', 'created_at')
    search_fields = ('content', 'author__username', 'task__title')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('mentioned_users',)

    def short_content(self, obj):
        """Display truncated content."""
        return obj.content[:60] + '...' if len(obj.content) > 60 else obj.content
    short_content.short_description = 'Content'


@admin.register(TaskChecklist)
class TaskChecklistAdmin(admin.ModelAdmin):
    """Admin configuration for TaskChecklist model."""
    list_display = ('title', 'task', 'is_completed', 'completed_by', 'completed_at', 'order')
    list_filter = ('is_completed', 'task__project', 'completed_at')
    search_fields = ('title', 'task__title')
    ordering = ('task', 'order')
    readonly_fields = ('completed_at', 'created_at', 'updated_at')


@admin.register(TaskTemplate)
class TaskTemplateAdmin(admin.ModelAdmin):
    """Admin configuration for TaskTemplate model."""
    list_display = ('name', 'title_template', 'project', 'recurrence_type', 'is_active', 'next_occurrence', 'created_at')
    list_filter = ('recurrence_type', 'is_active', 'project', 'created_at')
    search_fields = ('name', 'title_template', 'project__name')
    ordering = ('project', 'name')
    readonly_fields = ('last_generated_date', 'created_at', 'updated_at')
    filter_horizontal = ('default_assignees',)
    fieldsets = (
        ('Template Info', {
            'fields': ('name', 'title_template', 'description_template', 'project')
        }),
        ('Recurrence Settings', {
            'fields': ('recurrence_type', 'recurrence_days', 'weekday_occurrence', 'is_active')
        }),
        ('Default Task Settings', {
            'fields': ('default_assignees', 'default_priority', 'default_status', 'days_before_due', 'due_time')
        }),
        ('Checklist Items', {
            'fields': ('default_checklist',),
            'classes': ('collapse',),
        }),
        ('Generation Status', {
            'fields': ('last_generated_date', 'next_occurrence', 'created_by'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
