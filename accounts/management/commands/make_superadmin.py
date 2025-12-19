"""
Management command to promote a user to platform superadmin.

Usage:
    python manage.py make_superadmin <username_or_email>
    python manage.py make_superadmin --username admin
    python manage.py make_superadmin --email admin@example.com
"""
from django.core.management.base import BaseCommand, CommandError
from accounts.models import User


class Command(BaseCommand):
    help = 'Promote a user to platform superadmin'

    def add_arguments(self, parser):
        parser.add_argument(
            'identifier',
            nargs='?',
            type=str,
            help='Username or email of the user to promote'
        )
        parser.add_argument(
            '--username',
            type=str,
            help='Username of the user to promote'
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Email of the user to promote'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all current superadmins'
        )
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Remove superadmin status instead of granting it'
        )

    def handle(self, *args, **options):
        # List superadmins
        if options['list']:
            superadmins = User.objects.filter(is_superadmin=True)
            if superadmins.exists():
                self.stdout.write(self.style.SUCCESS('\nCurrent Platform Superadmins:'))
                for admin in superadmins:
                    self.stdout.write(
                        f"  - {admin.username} ({admin.email}) - "
                        f"{'Active' if admin.is_active else 'Inactive'}"
                    )
            else:
                self.stdout.write(self.style.WARNING('No superadmins found.'))
            return

        # Get user identifier
        identifier = options['identifier'] or options.get('username') or options.get('email')

        if not identifier:
            raise CommandError(
                'Please provide a username or email:\n'
                '  python manage.py make_superadmin <username_or_email>\n'
                '  python manage.py make_superadmin --username admin\n'
                '  python manage.py make_superadmin --email admin@example.com\n'
                '\nOr use --list to see current superadmins'
            )

        # Find user
        user = None
        try:
            # Try username first
            user = User.objects.get(username=identifier)
        except User.DoesNotExist:
            try:
                # Try email
                user = User.objects.get(email=identifier)
            except User.DoesNotExist:
                raise CommandError(
                    f'User not found with username or email: {identifier}\n'
                    'Use --list to see all users or create the user first.'
                )

        # Update superadmin status
        if options['remove']:
            if not user.is_superadmin:
                self.stdout.write(
                    self.style.WARNING(
                        f'{user.username} is not a superadmin.'
                    )
                )
                return

            user.is_superadmin = False
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully removed superadmin status from:\n'
                    f'  Username: {user.username}\n'
                    f'  Email: {user.email}\n'
                )
            )
        else:
            if user.is_superadmin:
                self.stdout.write(
                    self.style.WARNING(
                        f'{user.username} is already a superadmin.'
                    )
                )
                return

            user.is_superadmin = True
            user.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully promoted to platform superadmin:\n'
                    f'  Username: {user.username}\n'
                    f'  Email: {user.email}\n'
                    f'\nThey can now access the admin dashboard at:\n'
                    f'  /platform-admin/\n'
                )
            )

        # Show current superadmin count
        superadmin_count = User.objects.filter(is_superadmin=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f'\nTotal platform superadmins: {superadmin_count}'
            )
        )
