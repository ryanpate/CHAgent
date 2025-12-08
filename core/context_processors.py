"""
Context processors for multi-tenant organization context.

These make organization data available in all templates automatically.
"""
from django.conf import settings


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
    """
    context = {
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
