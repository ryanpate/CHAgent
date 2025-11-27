from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('chat/', views.chat, name='chat'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('chat/new/', views.chat_new_session, name='chat_new_session'),
    path('chat/feedback/', views.chat_feedback, name='chat_feedback'),
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
]
