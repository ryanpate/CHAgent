"""
Management command to create a superuser from environment variables.
Used for Railway deployment where interactive commands aren't available.
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create a superuser from environment variables if it does not exist'

    def handle(self, *args, **options):
        User = get_user_model()

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not all([username, email, password]):
            self.stdout.write(
                self.style.WARNING(
                    'Skipping superuser creation: DJANGO_SUPERUSER_USERNAME, '
                    'DJANGO_SUPERUSER_EMAIL, and DJANGO_SUPERUSER_PASSWORD '
                    'environment variables are required.'
                )
            )
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.SUCCESS(f'Superuser "{username}" already exists.')
            )
            return

        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        self.stdout.write(
            self.style.SUCCESS(f'Superuser "{username}" created successfully.')
        )
