"""
Seed the user guide into all active organizations' Knowledge Bases.

Usage:
    python manage.py seed_guide
"""
from django.core.management.base import BaseCommand

from core.guide_seeder import seed_guide_document
from core.models import Organization


class Command(BaseCommand):
    help = 'Seed the Getting Started guide into all active organizations'

    def handle(self, *args, **options):
        orgs = Organization.objects.filter(is_active=True)
        created = 0
        skipped = 0

        for org in orgs:
            result = seed_guide_document(org)
            if result:
                created += 1
                self.stdout.write(f"  Created guide for: {org.name}")
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Created: {created}, Skipped (already exists): {skipped}, Total orgs: {orgs.count()}"
        ))
