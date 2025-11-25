"""
URL configuration for Cherry Hills Worship Arts Portal.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse


def health_check(request):
    """Health check endpoint for Railway deployment."""
    return HttpResponse('OK', content_type='text/plain')


urlpatterns = [
    path('health/', health_check, name='health_check'),  # Health check first
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('core.urls')),
]
