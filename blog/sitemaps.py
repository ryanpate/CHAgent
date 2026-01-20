"""
Sitemap configuration for blog posts.
"""
from django.contrib.sitemaps import Sitemap
from django.utils import timezone

from .models import BlogPost, BlogCategory


class BlogSitemap(Sitemap):
    """Sitemap for published blog posts."""
    changefreq = 'weekly'
    priority = 0.7
    protocol = 'https'

    def items(self):
        """Return all published blog posts."""
        return BlogPost.objects.filter(
            status='published',
            published_at__lte=timezone.now()
        ).order_by('-published_at')

    def lastmod(self, obj):
        """Return the last modified date."""
        return obj.updated_at

    def location(self, obj):
        """Return the absolute URL."""
        return obj.get_absolute_url()


class BlogCategorySitemap(Sitemap):
    """Sitemap for blog categories."""
    changefreq = 'weekly'
    priority = 0.5
    protocol = 'https'

    def items(self):
        """Return all categories that have published posts."""
        return BlogCategory.objects.filter(
            posts__status='published',
            posts__published_at__lte=timezone.now()
        ).distinct()

    def location(self, obj):
        """Return the absolute URL."""
        return obj.get_absolute_url()
