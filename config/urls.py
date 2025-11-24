"""
URL configuration for Cherry Hills Worship Arts Portal.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    """Health check endpoint for Railway deployment."""
    return JsonResponse({'status': 'healthy'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('health/', health_check, name='health_check'),
    path('', include('core.urls')),
]
