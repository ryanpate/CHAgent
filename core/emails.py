"""
Email sending utilities for the Aria platform.

Handles transactional emails including:
- Team member invitations
- Welcome emails
- Follow-up reminders
- Payment notifications
"""
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    template_name: str,
    context: dict,
    reply_to: str = None,
) -> bool:
    """
    Send a templated email.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        template_name: Name of template in templates/emails/ (without .html)
        context: Template context dictionary
        reply_to: Optional reply-to address

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Add common context
        context.setdefault('site_url', getattr(settings, 'SITE_URL', 'https://aria.church'))
        context.setdefault('support_email', getattr(settings, 'EMAIL_REPLY_TO', 'support@aria.church'))

        # Render templates
        html_content = render_to_string(f'emails/{template_name}.html', context)
        text_content = strip_tags(html_content)

        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'Aria <notifications@aria.church>'),
            to=[to_email],
            reply_to=[reply_to or getattr(settings, 'EMAIL_REPLY_TO', 'support@aria.church')],
        )
        email.attach_alternative(html_content, 'text/html')

        # Send
        email.send(fail_silently=False)
        logger.info(f"Email sent to {to_email}: {subject}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def send_invitation_email(invitation) -> bool:
    """
    Send a team invitation email.

    Args:
        invitation: OrganizationInvitation instance

    Returns:
        True if sent successfully
    """
    site_url = getattr(settings, 'SITE_URL', 'https://aria.church')
    invite_url = f"{site_url}/invite/{invitation.token}/"

    # Get inviter name
    inviter = invitation.invited_by
    if inviter:
        inviter_name = inviter.get_full_name() or inviter.username
    else:
        inviter_name = 'A team member'

    context = {
        'organization_name': invitation.organization.name,
        'inviter_name': inviter_name,
        'role': invitation.get_role_display(),
        'invite_url': invite_url,
        'expires_at': invitation.expires_at,
    }

    subject = f"You're invited to join {invitation.organization.name} on Aria"

    return send_email(
        to_email=invitation.email,
        subject=subject,
        template_name='invitation',
        context=context,
    )


def send_welcome_email(user, organization) -> bool:
    """
    Send welcome email after accepting an invitation.

    Args:
        user: User instance who just joined
        organization: Organization they joined

    Returns:
        True if sent successfully
    """
    site_url = getattr(settings, 'SITE_URL', 'https://aria.church')

    context = {
        'user_name': user.get_full_name() or user.username,
        'organization_name': organization.name,
        'dashboard_url': f"{site_url}/",
    }

    subject = f"Welcome to {organization.name} on Aria!"

    return send_email(
        to_email=user.email,
        subject=subject,
        template_name='welcome',
        context=context,
    )


def send_followup_reminder(followup) -> bool:
    """
    Send a follow-up reminder email.

    Args:
        followup: FollowUp instance

    Returns:
        True if sent successfully
    """
    site_url = getattr(settings, 'SITE_URL', 'https://aria.church')

    context = {
        'followup': followup,
        'volunteer_name': followup.volunteer.name if followup.volunteer else None,
        'followup_url': f"{site_url}/followups/{followup.id}/",
    }

    subject = f"Reminder: {followup.title}"

    return send_email(
        to_email=followup.assigned_to.email,
        subject=subject,
        template_name='followup_reminder',
        context=context,
    )


def send_payment_failed_email(organization) -> bool:
    """
    Notify organization owner(s) of failed payment.

    Args:
        organization: Organization with failed payment

    Returns:
        True if all emails sent successfully
    """
    from .models import OrganizationMembership

    site_url = getattr(settings, 'SITE_URL', 'https://aria.church')

    # Get organization owner(s)
    owners = OrganizationMembership.objects.filter(
        organization=organization,
        role='owner',
        is_active=True,
    ).select_related('user')

    context = {
        'organization_name': organization.name,
        'billing_url': f"{site_url}/settings/billing/",
    }

    subject = f"Payment failed for {organization.name}"

    success = True
    for membership in owners:
        if membership.user.email:
            if not send_email(
                to_email=membership.user.email,
                subject=subject,
                template_name='payment_failed',
                context=context,
            ):
                success = False

    return success
