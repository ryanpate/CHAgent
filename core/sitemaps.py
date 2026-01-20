"""
Sitemap configuration for SEO.
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Sitemap for static public pages."""
    priority = 0.8
    changefreq = 'weekly'
    protocol = 'https'

    def items(self):
        """Return list of URL names for static pages."""
        return [
            'home',
            'pricing',
            'onboarding_signup',
            'resources_list',
            'resource_volunteer_application',
            'resource_schedule_template',
            'resource_pco_guide',
        ]

    def location(self, item):
        """Return the URL path for each item."""
        return reverse(item)

    def priority(self, item):
        """Set priority based on page importance."""
        priorities = {
            'home': 1.0,
            'pricing': 0.9,
            'onboarding_signup': 0.8,
            'resources_list': 0.7,
            'resource_volunteer_application': 0.6,
            'resource_schedule_template': 0.6,
            'resource_pco_guide': 0.6,
        }
        return priorities.get(item, 0.5)

    def changefreq(self, item):
        """Set change frequency based on page type."""
        frequencies = {
            'home': 'weekly',
            'pricing': 'monthly',
            'onboarding_signup': 'monthly',
            'resources_list': 'weekly',
            'resource_volunteer_application': 'monthly',
            'resource_schedule_template': 'monthly',
            'resource_pco_guide': 'monthly',
        }
        return frequencies.get(item, 'monthly')
