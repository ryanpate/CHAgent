from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import api_views

urlpatterns = [
    path('auth/token/', api_views.EmailTokenObtainPairView.as_view(), name='api_token_obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
    path('push/register/', api_views.register_push_token, name='api_push_register'),
    path('push/unregister/', api_views.unregister_push_token, name='api_push_unregister'),
    path('push/badge-clear/', api_views.clear_badge_count, name='api_push_badge_clear'),
]
