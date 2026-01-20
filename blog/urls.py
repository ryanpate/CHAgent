"""
Blog URL configuration.
"""
from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('', views.blog_list, name='list'),
    path('category/<slug:slug>/', views.category_list, name='category'),
    path('tag/<slug:slug>/', views.tag_list, name='tag'),
    path('<slug:slug>/', views.post_detail, name='post_detail'),
]
