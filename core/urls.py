from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('chat/', views.chat, name='chat'),
    path('chat/send/', views.chat_send, name='chat_send'),
    path('chat/new/', views.chat_new_session, name='chat_new_session'),
    path('interactions/', views.interaction_list, name='interaction_list'),
    path('interactions/new/', views.interaction_create, name='interaction_create'),
    path('interactions/<int:pk>/', views.interaction_detail, name='interaction_detail'),
    path('volunteers/', views.volunteer_list, name='volunteer_list'),
    path('volunteers/<int:pk>/', views.volunteer_detail, name='volunteer_detail'),
    # Volunteer matching endpoints (HTMX)
    path('volunteers/match/confirm/', views.volunteer_match_confirm, name='volunteer_match_confirm'),
    path('volunteers/match/create/', views.volunteer_match_create, name='volunteer_match_create'),
    path('volunteers/match/skip/', views.volunteer_match_skip, name='volunteer_match_skip'),
]
