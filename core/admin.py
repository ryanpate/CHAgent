from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from .models import Volunteer, Interaction, ChatMessage, ResponseFeedback, ReportCache


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
