"""
Management command to create a superuser from environment variables.
Used for Railway deployment where interactive commands aren't available.
Also ensures the user is a platform superadmin (is_superadmin=True).
"""
import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Create a superuser from environment variables and make them a platform superadmin'

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

        # Check if user already exists
        user = None
        try:
            user = User.objects.get(username=username)
            self.stdout.write(
                self.style.SUCCESS(f'Superuser "{username}" already exists.')
            )
            # Update password in case it changed
            user.set_password(password)
            user.email = email
            user.is_staff = True
            user.is_superuser = True
        except User.DoesNotExist:
            # Create new superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            self.stdout.write(
                self.style.SUCCESS(f'Superuser "{username}" created successfully.')
            )

        # Ensure user is a platform superadmin
        if not user.is_superadmin:
            user.is_superadmin = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'Promoted "{username}" to platform superadmin. '
                    f'Can now access /platform-admin/'
                )
            )
        else:
            user.save()  # Save any other changes
            self.stdout.write(
                self.style.SUCCESS(
                    f'User "{username}" is already a platform superadmin.'
                )
            )
