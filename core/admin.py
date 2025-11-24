from django.contrib import admin
from .models import Volunteer, Interaction, ChatMessage


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
