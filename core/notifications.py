"""
Push Notification Service for Cherry Hills Worship Arts Portal.

This module handles sending web push notifications to users' devices.
Requires pywebpush library and VAPID keys configured in settings.

Environment variables needed:
- VAPID_PUBLIC_KEY: Public key for VAPID authentication
- VAPID_PRIVATE_KEY: Private key for VAPID authentication
- VAPID_CLAIMS_EMAIL: Email for VAPID claims (e.g., mailto:admin@example.com)
"""
import json
import logging
from typing import Optional, List, Dict, Any

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_vapid_keys():
    """Get VAPID keys from settings/environment."""
    claims_email = getattr(settings, 'VAPID_CLAIMS_EMAIL', '') or 'mailto:wcwa@cherryhillsfamily.org'
    # Ensure it has mailto: prefix
    if claims_email and not claims_email.startswith('mailto:'):
        claims_email = f'mailto:{claims_email}'

    return {
        'public_key': getattr(settings, 'VAPID_PUBLIC_KEY', ''),
        'private_key': getattr(settings, 'VAPID_PRIVATE_KEY', ''),
        'claims_email': claims_email,
    }


def send_push_notification(
    subscription_info: Dict[str, Any],
    title: str,
    body: str,
    url: str = '/',
    icon: str = '/static/icons/icon-192x192.png',
    badge: str = '/static/icons/badge-72x72.png',
    tag: str = None,
    data: Dict[str, Any] = None,
    notification_log=None,
) -> bool:
    """
    Send a push notification to a single subscription.

    Args:
        subscription_info: Dict with endpoint and keys from PushSubscription.to_webpush_dict()
        title: Notification title
        body: Notification body text
        url: URL to open when notification is clicked
        icon: Icon URL for the notification
        badge: Badge icon URL (small icon)
        tag: Tag for notification grouping/replacement
        data: Additional data to send with the notification
        notification_log: Optional NotificationLog instance to update

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.error("pywebpush not installed. Run: pip install pywebpush")
        if notification_log:
            notification_log.status = 'failed'
            notification_log.error_message = 'pywebpush not installed'
            notification_log.save()
        return False

    vapid_keys = get_vapid_keys()

    if not vapid_keys['private_key']:
        logger.error("VAPID_PRIVATE_KEY not configured")
        if notification_log:
            notification_log.status = 'failed'
            notification_log.error_message = 'VAPID keys not configured'
            notification_log.save()
        return False

    # Build notification payload
    payload = {
        'title': title,
        'body': body,
        'icon': icon,
        'badge': badge,
        'url': url,
        'data': data or {},
    }

    if tag:
        payload['tag'] = tag

    try:
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(payload),
            vapid_private_key=vapid_keys['private_key'],
            vapid_claims={
                'sub': vapid_keys['claims_email']
            }
        )

        if notification_log:
            notification_log.status = 'sent'
            notification_log.sent_at = timezone.now()
            notification_log.save()

        logger.info(f"Push notification sent: {title}")
        return True

    except WebPushException as e:
        logger.error(f"Push notification failed: {e}")

        if notification_log:
            notification_log.status = 'failed'
            notification_log.error_message = str(e)
            notification_log.save()

        # Handle expired/invalid subscriptions
        if e.response and e.response.status_code in [404, 410]:
            # Subscription no longer valid - mark as inactive
            from .models import PushSubscription
            PushSubscription.objects.filter(
                endpoint=subscription_info.get('endpoint')
            ).update(is_active=False)
            logger.info(f"Marked subscription as inactive: {subscription_info.get('endpoint')[:50]}...")

        return False

    except Exception as e:
        logger.error(f"Unexpected error sending push notification: {e}")
        if notification_log:
            notification_log.status = 'failed'
            notification_log.error_message = str(e)
            notification_log.save()
        return False


def send_notification_to_user(
    user,
    notification_type: str,
    title: str,
    body: str,
    url: str = '/',
    data: Dict[str, Any] = None,
    respect_preferences: bool = True,
    priority: str = 'normal',
) -> int:
    """
    Send a push notification to all of a user's active subscriptions.

    Args:
        user: User instance to send notification to
        notification_type: Type of notification (announcement, dm, channel, care, followup)
        title: Notification title
        body: Notification body text
        url: URL to open when notification is clicked
        data: Additional data to send
        respect_preferences: Check user's notification preferences before sending
        priority: 'urgent', 'important', or 'normal' - for filtering

    Returns:
        Number of notifications successfully sent
    """
    from .models import PushSubscription, NotificationPreference, NotificationLog

    # Check user preferences
    if respect_preferences:
        try:
            prefs = NotificationPreference.objects.get(user=user)

            # Check quiet hours
            if not prefs.should_send_now():
                logger.info(f"Skipping notification to {user.username}: quiet hours")
                return 0

            # Check notification type preferences
            if notification_type == 'announcement':
                if not prefs.announcements:
                    return 0
                if prefs.announcements_urgent_only and priority != 'urgent':
                    return 0

            elif notification_type == 'dm':
                if not prefs.direct_messages:
                    return 0

            elif notification_type == 'channel':
                if not prefs.channel_messages:
                    return 0

            elif notification_type == 'care':
                if not prefs.care_alerts:
                    return 0
                if prefs.care_urgent_only and priority not in ['urgent', 'high']:
                    return 0

            elif notification_type == 'followup':
                if not prefs.followup_reminders:
                    return 0

        except NotificationPreference.DoesNotExist:
            # No preferences set - use defaults (send all)
            pass

    # Get user's active subscriptions
    subscriptions = PushSubscription.objects.filter(
        user=user,
        is_active=True
    )

    if not subscriptions.exists():
        logger.info(f"No active subscriptions for user {user.username}")
        return 0

    sent_count = 0

    for subscription in subscriptions:
        # Create log entry
        log = NotificationLog.objects.create(
            user=user,
            subscription=subscription,
            notification_type=notification_type,
            title=title,
            body=body,
            url=url,
            data=data or {},
            status='pending'
        )

        # Send notification
        success = send_push_notification(
            subscription_info=subscription.to_webpush_dict(),
            title=title,
            body=body,
            url=url,
            tag=f"{notification_type}-{user.id}",
            data=data,
            notification_log=log,
        )

        if success:
            sent_count += 1
            subscription.last_used_at = timezone.now()
            subscription.save(update_fields=['last_used_at'])

    return sent_count


def send_notification_to_users(
    users,
    notification_type: str,
    title: str,
    body: str,
    url: str = '/',
    data: Dict[str, Any] = None,
    priority: str = 'normal',
) -> int:
    """
    Send a push notification to multiple users.

    Args:
        users: QuerySet or list of User instances
        notification_type: Type of notification
        title: Notification title
        body: Notification body text
        url: URL to open when clicked
        data: Additional data
        priority: 'urgent', 'important', or 'normal'

    Returns:
        Total number of notifications sent
    """
    total_sent = 0
    for user in users:
        sent = send_notification_to_user(
            user=user,
            notification_type=notification_type,
            title=title,
            body=body,
            url=url,
            data=data,
            priority=priority,
        )
        total_sent += sent
    return total_sent


# =============================================================================
# Notification Helper Functions for Specific Events
# =============================================================================

def notify_new_announcement(announcement):
    """
    Send notifications for a new announcement.
    """
    from accounts.models import User

    priority = announcement.priority  # 'normal', 'important', 'urgent'

    # Get all active users (or filter by target_teams if specified)
    users = User.objects.filter(is_active=True)

    # Don't notify the author
    if announcement.author:
        users = users.exclude(pk=announcement.author.pk)

    title = f"{'🚨 ' if priority == 'urgent' else '📢 '}{announcement.title}"
    body = announcement.content[:100] + ('...' if len(announcement.content) > 100 else '')

    return send_notification_to_users(
        users=users,
        notification_type='announcement',
        title=title,
        body=body,
        url=f'/comms/announcements/{announcement.id}/',
        data={'announcement_id': announcement.id},
        priority=priority,
    )


def notify_new_dm(message):
    """
    Send notification for a new direct message.
    """
    if not message.recipient:
        return 0

    sender_name = message.sender.display_name or message.sender.username if message.sender else 'Someone'

    return send_notification_to_user(
        user=message.recipient,
        notification_type='dm',
        title=f"Message from {sender_name}",
        body=message.content[:100] + ('...' if len(message.content) > 100 else ''),
        url=f'/comms/messages/{message.sender.id}/' if message.sender else '/comms/messages/',
        data={'message_id': message.id, 'sender_id': message.sender.id if message.sender else None},
    )


def notify_channel_message(message, mentioned_users=None):
    """
    Send notifications for a channel message.

    Only notifies users who have channel notifications enabled,
    or mentioned users if channel_mentions_only is True.
    """
    from .models import NotificationPreference

    channel = message.channel
    author = message.author

    if mentioned_users:
        # Notify mentioned users
        for user in mentioned_users:
            if user != author:
                send_notification_to_user(
                    user=user,
                    notification_type='channel',
                    title=f"Mentioned in #{channel.name}",
                    body=f"{author.display_name or author.username}: {message.content[:80]}...",
                    url=f'/comms/channels/{channel.slug}/',
                    data={'channel_id': channel.id, 'message_id': message.id},
                )


def notify_care_alert(insight):
    """
    Send notification for a new proactive care alert.
    """
    from accounts.models import User

    # Notify all active team members
    users = User.objects.filter(is_active=True)

    priority = insight.priority  # 'low', 'medium', 'high', 'urgent'

    return send_notification_to_users(
        users=users,
        notification_type='care',
        title=f"Care Alert: {insight.volunteer.name}",
        body=insight.title,
        url='/care/',
        data={'insight_id': insight.id, 'volunteer_id': insight.volunteer.id},
        priority=priority,
    )


def notify_followup_due(followup):
    """
    Send notification for a follow-up that's due.
    """
    # Notify the creator and assigned user
    users_to_notify = []

    if followup.created_by:
        users_to_notify.append(followup.created_by)

    if followup.assigned_to and followup.assigned_to != followup.created_by:
        users_to_notify.append(followup.assigned_to)

    volunteer_name = followup.volunteer.name if followup.volunteer else 'General'

    total_sent = 0
    for user in users_to_notify:
        sent = send_notification_to_user(
            user=user,
            notification_type='followup',
            title=f"Follow-up Due: {followup.title}",
            body=f"For {volunteer_name}",
            url=f'/followups/{followup.id}/',
            data={'followup_id': followup.id},
        )
        total_sent += sent

    return total_sent


def send_test_notification(user):
    """
    Send a test notification to verify push is working.
    """
    return send_notification_to_user(
        user=user,
        notification_type='test',
        title='Test Notification',
        body='Push notifications are working! 🎉',
        url='/',
        respect_preferences=False,
    )


# =============================================================================
# Project and Task Notification Functions
# =============================================================================

def notify_project_assignment(project, user):
    """
    Send notification when a user is added to a project.
    """
    owner_name = project.owner.display_name or project.owner.username if project.owner else 'Someone'

    return send_notification_to_user(
        user=user,
        notification_type='announcement',  # Reuse announcement type for project notifications
        title=f"Added to project: {project.name}",
        body=f"{owner_name} added you to this project",
        url=f'/comms/projects/{project.id}/',
        data={'project_id': project.id},
        priority='normal',
    )


def notify_task_assignment(task, user):
    """
    Send notification when a user is assigned to a task.
    """
    assigner_name = 'Someone'
    if task.created_by:
        assigner_name = task.created_by.display_name or task.created_by.username

    due_info = f" (due {task.due_date.strftime('%b %d')})" if task.due_date else ""

    return send_notification_to_user(
        user=user,
        notification_type='followup',  # Reuse followup type for task notifications
        title=f"Task assigned: {task.title}",
        body=f"{assigner_name} assigned you to this task{due_info}",
        url=f'/comms/projects/{task.project.id}/tasks/{task.id}/',
        data={'task_id': task.id, 'project_id': task.project.id},
        priority='high' if task.priority in ['high', 'urgent'] else 'normal',
    )


def notify_task_due_soon(task):
    """
    Send notification for a task that's due soon (e.g., today or tomorrow).
    """
    total_sent = 0
    for user in task.assignees.all():
        sent = send_notification_to_user(
            user=user,
            notification_type='followup',
            title=f"Task due soon: {task.title}",
            body=f"Due {task.due_date.strftime('%b %d')} - {task.project.name}",
            url=f'/comms/projects/{task.project.id}/tasks/{task.id}/',
            data={'task_id': task.id, 'project_id': task.project.id},
            priority='high',
        )
        total_sent += sent
    return total_sent


def notify_task_comment(comment):
    """
    Send notification when someone comments on a task.
    """
    task = comment.task
    author = comment.author
    author_name = author.display_name or author.username if author else 'Someone'

    # Notify all assignees except the commenter
    users_to_notify = set(task.assignees.all())

    # Also notify mentioned users
    for mentioned_user in comment.mentioned_users.all():
        users_to_notify.add(mentioned_user)

    # Remove the author from notifications
    if author:
        users_to_notify.discard(author)

    total_sent = 0
    for user in users_to_notify:
        sent = send_notification_to_user(
            user=user,
            notification_type='channel',  # Reuse channel type for task comments
            title=f"Comment on: {task.title}",
            body=f"{author_name}: {comment.content[:80]}...",
            url=f'/comms/projects/{task.project.id}/tasks/{task.id}/',
            data={'task_id': task.id, 'comment_id': comment.id},
        )
        total_sent += sent
    return total_sent


def notify_user_mentioned(message, mentioned_users):
    """
    Send notifications to users mentioned in a channel message.
    """
    if not mentioned_users:
        return 0

    author = message.author
    author_name = author.display_name or author.username if author else 'Someone'
    channel = message.channel

    total_sent = 0
    for user in mentioned_users:
        if user != author:  # Don't notify the author if they mentioned themselves
            sent = send_notification_to_user(
                user=user,
                notification_type='channel',
                title=f"Mentioned in #{channel.name}",
                body=f"{author_name}: {message.content[:80]}...",
                url=f'/comms/channels/{channel.slug}/',
                data={'channel_id': channel.id, 'message_id': message.id},
            )
            total_sent += sent
    return total_sent
