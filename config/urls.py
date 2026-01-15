"""
URL configuration for Cherry Hills Worship Arts Portal.
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.http import HttpResponse, FileResponse
from django.conf import settings
import os

from core.sitemaps import StaticViewSitemap

# Sitemap configuration
sitemaps = {
    'static': StaticViewSitemap,
}


def health_check(request):
    """Health check endpoint for Railway deployment."""
    return HttpResponse('OK', content_type='text/plain')


def robots_txt(request):
    """Serve robots.txt for search engine crawlers."""
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "# Disallow authenticated areas",
        "Disallow: /dashboard/",
        "Disallow: /chat/",
        "Disallow: /interactions/",
        "Disallow: /volunteers/",
        "Disallow: /followups/",
        "Disallow: /analytics/",
        "Disallow: /care/",
        "Disallow: /comms/",
        "Disallow: /tasks/",
        "Disallow: /my-tasks/",
        "Disallow: /templates/",
        "Disallow: /notifications/",
        "Disallow: /billing/",
        "Disallow: /settings/",
        "Disallow: /feedback/",
        "Disallow: /platform-admin/",
        "Disallow: /admin/",
        "",
        "# Sitemap location",
        f"Sitemap: https://aria.church/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def service_worker(request):
    """Serve service worker from root for proper scope."""
    sw_path = os.path.join(settings.BASE_DIR, 'static', 'sw.js')
    return FileResponse(
        open(sw_path, 'rb'),
        content_type='application/javascript',
        headers={'Service-Worker-Allowed': '/'}
    )


def manifest(request):
    """Serve manifest from root for PWA."""
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'manifest.json')
    return FileResponse(
        open(manifest_path, 'rb'),
        content_type='application/manifest+json'
    )


urlpatterns = [
    path('health/', health_check, name='health_check'),  # Health check first
    path('robots.txt', robots_txt, name='robots_txt'),  # SEO robots.txt
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('sw.js', service_worker, name='service_worker'),  # Service worker at root
    path('manifest.json', manifest, name='manifest'),  # Manifest at root
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('', include('core.urls')),
]
