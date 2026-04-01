from django.contrib import admin
from .models import SongSubmission, SongVote


@admin.register(SongSubmission)
class SongSubmissionAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist', 'organization', 'status', 'average_rating', 'vote_count', 'created_at']
    list_filter = ['status', 'organization', 'created_at']
    search_fields = ['title', 'artist', 'submitter_name']
    readonly_fields = ['average_rating', 'vote_count', 'created_at', 'updated_at']


@admin.register(SongVote)
class SongVoteAdmin(admin.ModelAdmin):
    list_display = ['submission', 'user', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
