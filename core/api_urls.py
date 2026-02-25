from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import api_views

urlpatterns = [
    path('auth/token/', api_views.EmailTokenObtainPairView.as_view(), name='api_token_obtain'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='api_token_refresh'),
]
