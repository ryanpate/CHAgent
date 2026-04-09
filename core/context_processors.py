"""
Context processors for multi-tenant organization context.

These make organization data available in all templates automatically.
"""
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def organization_context(request):
    """
    Add organization context to all templates.

    Provides:
    - organization: Current organization object
    - membership: User's membership in the organization
    - is_owner: Whether user is organization owner
    - is_admin: Whether user is admin or above
    - is_leader: Whether user is leader or above
    - can_manage_users: Permission flag
    - can_manage_settings: Permission flag
    - can_view_analytics: Permission flag
    - can_manage_billing: Permission flag
    - trial_days_remaining: Days left in trial (if applicable)
    - ai_assistant_name: Custom AI name for this organization
    - Subscription status flags for warning banners
    """
    # Detect native app mode (Capacitor WebView sets this cookie)
    is_app_mode = request.COOKIES.get('aria_app') == '1' or request.GET.get('app') == '1'

    context = {
        'is_app_mode': is_app_mode,
        'organization': None,
        'membership': None,
        'is_owner': False,
        'is_admin': False,
        'is_leader': False,
        'can_manage_users': False,
        'can_manage_settings': False,
        'can_view_analytics': False,
        'can_manage_billing': False,
        'trial_days_remaining': 0,
        'ai_assistant_name': getattr(settings, 'DEFAULT_AI_ASSISTANT_NAME', 'Aria'),
        # Subscription status flags
        'is_trial': False,
        'show_trial_warning': False,
        'is_past_due': False,
        'subscription_status': None,
        # Badge counts
        'pending_followup_count': 0,
        'pending_task_count': 0,
        'unread_message_count': 0,
        'interactions_this_week': 0,
    }

    # Only process for authenticated users with organization context
    if not request.user.is_authenticated:
        return context

    organization = getattr(request, 'organization', None)
    membership = getattr(request, 'membership', None)

    if organization:
        context['organization'] = organization
        context['trial_days_remaining'] = organization.trial_days_remaining
        context['ai_assistant_name'] = organization.ai_assistant_name or 'Aria'
        # Subscription status for warning banners
        context['is_trial'] = organization.is_trial
        context['show_trial_warning'] = organization.show_trial_warning
        context['is_past_due'] = organization.subscription_status == 'past_due'
        context['subscription_status'] = organization.subscription_status

        # Pending song submissions count for sidebar badge
        try:
            from songs.models import SongSubmission
            context['pending_song_count'] = SongSubmission.objects.filter(
                organization=organization, status='pending'
            ).count()
        except Exception:
            context['pending_song_count'] = 0

        # Badge counts for dashboard and sidebar
        user = request.user

        try:
            from core.models import FollowUp
            context['pending_followup_count'] = FollowUp.objects.filter(
                organization=organization,
                assigned_to=user,
                status__in=['pending', 'in_progress'],
            ).count()
        except Exception:
            pass

        try:
            from core.models import Task
            context['pending_task_count'] = Task.objects.filter(
                assignees=user,
                status__in=['todo', 'in_progress'],
            ).filter(
                models.Q(project__organization=organization) |
                models.Q(organization=organization, project__isnull=True)
            ).count()
        except Exception:
            pass

        try:
            from core.models import DirectMessage
            context['unread_message_count'] = DirectMessage.objects.filter(
                recipient=user,
                is_read=False,
            ).count()
        except Exception:
            pass

        try:
            from core.models import Interaction
            one_week_ago = timezone.now() - timedelta(days=7)
            context['interactions_this_week'] = Interaction.objects.filter(
                organization=organization,
                created_at__gte=one_week_ago,
            ).count()
        except Exception:
            pass

    if membership:
        context['membership'] = membership
        context['is_owner'] = membership.is_owner
        context['is_admin'] = membership.is_admin_or_above
        context['is_leader'] = membership.is_leader_or_above
        context['can_manage_users'] = membership.can_manage_users
        context['can_manage_settings'] = membership.can_manage_settings
        context['can_view_analytics'] = membership.can_view_analytics
        context['can_manage_billing'] = membership.can_manage_billing

    return context
