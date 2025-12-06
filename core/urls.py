from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('chat/', views.chat, name='chat'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('chat/new/', views.chat_new_session, name='chat_new_session'),
    path('chat/feedback/', views.chat_feedback, name='chat_feedback'),
    path('chat/feedback/submit/', views.chat_feedback_submit, name='chat_feedback_submit'),
    # Feedback dashboard
    path('feedback/', views.feedback_dashboard, name='feedback_dashboard'),
    path('feedback/<int:pk>/resolve/', views.feedback_resolve, name='feedback_resolve'),
    path('interactions/', views.interaction_list, name='interaction_list'),
    path('interactions/new/', views.interaction_create, name='interaction_create'),
    path('interactions/<int:pk>/', views.interaction_detail, name='interaction_detail'),
    path('volunteers/', views.volunteer_list, name='volunteer_list'),
    path('volunteers/<int:pk>/', views.volunteer_detail, name='volunteer_detail'),
    # Volunteer matching endpoints (HTMX)
    path('volunteers/match/confirm/', views.volunteer_match_confirm, name='volunteer_match_confirm'),
    path('volunteers/match/create/', views.volunteer_match_create, name='volunteer_match_create'),
    path('volunteers/match/skip/', views.volunteer_match_skip, name='volunteer_match_skip'),
    # Follow-up endpoints
    path('followups/', views.followup_list, name='followup_list'),
    path('followups/<int:pk>/', views.followup_detail, name='followup_detail'),
    path('followups/create/', views.followup_create, name='followup_create'),
    path('followups/<int:pk>/complete/', views.followup_complete, name='followup_complete'),
    path('followups/<int:pk>/update/', views.followup_update, name='followup_update'),
    path('followups/<int:pk>/delete/', views.followup_delete, name='followup_delete'),
    # Analytics and Reporting
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
    path('analytics/engagement/', views.analytics_volunteer_engagement, name='analytics_volunteer_engagement'),
    path('analytics/care/', views.analytics_team_care, name='analytics_team_care'),
    path('analytics/trends/', views.analytics_interaction_trends, name='analytics_interaction_trends'),
    path('analytics/prayer/', views.analytics_prayer_requests, name='analytics_prayer_requests'),
    path('analytics/ai/', views.analytics_ai_performance, name='analytics_ai_performance'),
    path('analytics/export/<str:report_type>/', views.analytics_export, name='analytics_export'),
    path('analytics/refresh/', views.analytics_refresh_cache, name='analytics_refresh_cache'),
    # Proactive Care Dashboard
    path('care/', views.care_dashboard, name='care_dashboard'),
    path('care/dismiss/<int:pk>/', views.care_dismiss_insight, name='care_dismiss_insight'),
    path('care/followup/<int:pk>/', views.care_create_followup, name='care_create_followup'),
    path('care/refresh/', views.care_refresh_insights, name='care_refresh_insights'),
    # Team Communication Hub
    path('comms/', views.comms_hub, name='comms_hub'),
    path('comms/announcements/', views.announcements_list, name='announcements_list'),
    path('comms/announcements/<int:pk>/', views.announcement_detail, name='announcement_detail'),
    path('comms/announcements/new/', views.announcement_create, name='announcement_create'),
    path('comms/channels/', views.channel_list, name='channel_list'),
    path('comms/channels/new/', views.channel_create, name='channel_create'),
    path('comms/channels/<slug:slug>/', views.channel_detail, name='channel_detail'),
    path('comms/channels/<slug:slug>/send/', views.channel_send_message, name='channel_send_message'),
    path('comms/messages/', views.dm_list, name='dm_list'),
    path('comms/messages/new/', views.dm_new, name='dm_new'),
    path('comms/messages/<int:user_id>/', views.dm_conversation, name='dm_conversation'),
    path('comms/messages/<int:user_id>/send/', views.dm_send, name='dm_send'),
]
