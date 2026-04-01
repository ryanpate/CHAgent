from django.urls import path
from . import views

app_name = 'songs'

urlpatterns = [
    path('', views.song_dashboard, name='dashboard'),
    path('<int:pk>/', views.song_detail, name='detail'),
    path('<int:pk>/vote/', views.song_vote, name='vote'),
    path('<int:pk>/status/', views.song_update_status, name='update_status'),
]
