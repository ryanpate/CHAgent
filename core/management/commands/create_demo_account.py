"""
Create a demo account for App Store review.

Usage:
    python manage.py create_demo_account

Creates:
    - User: demo@aria.church / AppReview2026!
    - Organization: "Demo Community Church" with beta status
    - Membership: owner role with full permissions
    - Sample volunteers, interactions, and follow-ups
"""
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Create a demo account with sample data for App Store review'

    DEMO_EMAIL = 'demo@aria.church'
    DEMO_PASSWORD = 'AppReview2026!'
    DEMO_ORG_NAME = 'Demo Community Church'
    DEMO_ORG_SLUG = 'demo-church'

    def handle(self, *args, **options):
        from accounts.models import User
        from core.models import (
            Organization, OrganizationMembership,
            Volunteer, Interaction, FollowUp,
        )

        # Create or update demo user
        user, created = User.objects.update_or_create(
            email=self.DEMO_EMAIL,
            defaults={
                'username': self.DEMO_EMAIL,
                'display_name': 'App Reviewer',
                'first_name': 'App',
                'last_name': 'Reviewer',
                'is_active': True,
                'has_completed_onboarding': True,
            },
        )
        user.set_password(self.DEMO_PASSWORD)
        user.save()

        action = 'Created' if created else 'Updated'
        self.stdout.write(f'{action} demo user: {self.DEMO_EMAIL}')

        # Create or update demo organization
        org, created = Organization.objects.update_or_create(
            slug=self.DEMO_ORG_SLUG,
            defaults={
                'name': self.DEMO_ORG_NAME,
                'email': self.DEMO_EMAIL,
                'subscription_status': 'beta',
                'is_active': True,
                'ai_assistant_name': 'Aria',
            },
        )
        action = 'Created' if created else 'Updated'
        self.stdout.write(f'{action} demo organization: {self.DEMO_ORG_NAME}')

        # Create membership
        membership, created = OrganizationMembership.objects.update_or_create(
            user=user,
            organization=org,
            defaults={
                'role': 'owner',
                'is_active': True,
                'can_manage_users': True,
                'can_manage_settings': True,
                'can_view_analytics': True,
                'can_manage_billing': True,
                'joined_at': timezone.now(),
            },
        )

        # Set as default org
        user.default_organization = org
        user.save()

        # Create sample volunteers
        volunteers_data = [
            {'name': 'Sarah Johnson', 'team': 'vocals'},
            {'name': 'Mike Chen', 'team': 'band'},
            {'name': 'Emily Rodriguez', 'team': 'tech'},
            {'name': 'David Kim', 'team': 'vocals'},
            {'name': 'Rachel Adams', 'team': 'band'},
        ]

        volunteers = []
        for v_data in volunteers_data:
            vol, _ = Volunteer.objects.update_or_create(
                name=v_data['name'],
                organization=org,
                defaults={
                    'normalized_name': v_data['name'].lower(),
                    'team': v_data['team'],
                },
            )
            volunteers.append(vol)

        self.stdout.write(f'Created {len(volunteers)} sample volunteers')

        # Create sample interactions
        interactions_data = [
            {
                'content': 'Talked with Sarah after rehearsal. She mentioned her daughter is starting kindergarten next month. She loves gardening and her tomatoes are doing great this year.',
                'volunteer_name': 'Sarah Johnson',
            },
            {
                'content': 'Mike shared that he\'s been learning a new song arrangement for next Sunday. He also mentioned a prayer request for his mother\'s health.',
                'volunteer_name': 'Mike Chen',
            },
            {
                'content': 'Emily helped set up the new sound board configuration. She\'s interested in training other tech team members.',
                'volunteer_name': 'Emily Rodriguez',
            },
        ]

        for i_data in interactions_data:
            vol = next(v for v in volunteers if v.name == i_data['volunteer_name'])
            interaction, created = Interaction.objects.get_or_create(
                organization=org,
                user=user,
                content=i_data['content'],
                defaults={
                    'ai_summary': i_data['content'][:100],
                },
            )
            if created:
                interaction.volunteers.add(vol)

        self.stdout.write(f'Created sample interactions')

        # Create sample follow-ups
        followups_data = [
            {
                'title': 'Check in on Mike\'s mother',
                'description': 'Mike mentioned his mother is having health issues. Follow up to see how she\'s doing.',
                'category': 'prayer_request',
                'priority': 'high',
                'volunteer_name': 'Mike Chen',
            },
            {
                'title': 'Tech team training schedule',
                'description': 'Emily wants to help train new tech team members. Set up a training schedule.',
                'category': 'action_item',
                'priority': 'medium',
                'volunteer_name': 'Emily Rodriguez',
            },
        ]

        for f_data in followups_data:
            vol = next(v for v in volunteers if v.name == f_data['volunteer_name'])
            FollowUp.objects.get_or_create(
                organization=org,
                title=f_data['title'],
                defaults={
                    'created_by': user,
                    'assigned_to': user,
                    'volunteer': vol,
                    'description': f_data['description'],
                    'category': f_data['category'],
                    'priority': f_data['priority'],
                    'status': 'pending',
                    'follow_up_date': timezone.now().date(),
                },
            )

        self.stdout.write(f'Created sample follow-ups')

        self.stdout.write(self.style.SUCCESS(
            f'\nDemo account ready!\n'
            f'  Email:    {self.DEMO_EMAIL}\n'
            f'  Password: {self.DEMO_PASSWORD}\n'
            f'  Org:      {self.DEMO_ORG_NAME}\n'
            f'\nRun on Railway with:\n'
            f'  railway run python manage.py create_demo_account'
        ))
