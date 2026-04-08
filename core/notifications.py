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
    claims_email = getattr(settings, 'VAPID_CLAIMS_EMAIL', '') or 'mailto:support@aria.church'
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

            elif notification_type == 'song_submission':
                if not prefs.song_submissions:
                    return 0

            elif notification_type == 'studio':
                if not prefs.studio_new_posts:
                    return 0

        except NotificationPreference.DoesNotExist:
            # No preferences set - use defaults (send all)
            pass

    sent_count = 0

    # Send to web push subscriptions
    subscriptions = PushSubscription.objects.filter(
        user=user,
        is_active=True
    )

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

    # Send to native push tokens (iOS/Android apps)
    try:
        from .models import NativePushToken
        native_tokens = NativePushToken.objects.filter(
            user=user,
            is_active=True,
        )
        for token_obj in native_tokens:
            try:
                success = send_native_push(token_obj, title, body, url, data)
                if success:
                    sent_count += 1
            except Exception as e:
                logger.error(f"Native push failed for {token_obj}: {e}")
    except ImportError:
        pass

    if sent_count == 0:
        logger.info(f"No active subscriptions or tokens for user {user.username}")

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
# Native Push Notification Functions (iOS/Android)
# =============================================================================

def send_native_push(token_obj, title, body, url='/', data=None):
    """Send a push notification to a native iOS/Android device."""
    # Increment badge count
    token_obj.unread_badge_count += 1
    token_obj.save(update_fields=['unread_badge_count'])

    payload = {
        'title': title,
        'body': body,
        'url': url,
        'data': data or {},
        'badge': token_obj.unread_badge_count,
    }

    try:
        if token_obj.platform == 'android':
            return _send_fcm(token_obj.token, payload)
        elif token_obj.platform == 'ios':
            return _send_apns(token_obj.token, payload)
    except Exception as e:
        logger.error(f"Failed to send native push to {token_obj.platform}: {e}")
        return False
    return False


def _send_fcm(token, payload):
    """Send via Firebase Cloud Messaging."""
    try:
        import json
        import os
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            cred_json = os.environ.get('FIREBASE_CREDENTIALS_JSON')
            if cred_json:
                cred = credentials.Certificate(json.loads(cred_json))
                firebase_admin.initialize_app(cred)
            else:
                firebase_admin.initialize_app()

        badge_count = payload.get('badge', 0)

        message = messaging.Message(
            notification=messaging.Notification(
                title=payload['title'],
                body=payload['body'],
            ),
            data={
                'url': payload.get('url', '/'),
                **{k: str(v) for k, v in payload.get('data', {}).items()},
            },
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(badge=badge_count),
                ),
            ),
            token=token,
        )
        messaging.send(message)
        return True
    except Exception as e:
        logger.error(f"FCM send failed: {e}")
        return False


def _send_apns(token, payload):
    """Send via Apple Push Notification service.

    Uses FCM under the hood since the Capacitor app uses FCM SDK
    for both iOS and Android.
    """
    return _send_fcm(token, payload)


# =============================================================================
# Notification Helper Functions for Specific Events
# =============================================================================

def notify_new_announcement(announcement):
    """
    Send notifications for a new announcement.
    """
    from accounts.models import User
    from .models import PushSubscription

    priority = announcement.priority  # 'normal', 'important', 'urgent'

    # Get all active users (or filter by target_teams if specified)
    users = User.objects.filter(is_active=True)
    total_users = users.count()

    # Don't notify the author
    if announcement.author:
        users = users.exclude(pk=announcement.author.pk)

    users_to_notify = list(users)
    logger.info(
        f"Announcement notification: {total_users} active users, "
        f"{len(users_to_notify)} after excluding author"
    )

    # Check which users have push subscriptions
    users_with_subs = []
    for user in users_to_notify:
        sub_count = PushSubscription.objects.filter(user=user, is_active=True).count()
        if sub_count > 0:
            users_with_subs.append(user.username)
    logger.info(f"Users with active push subscriptions: {users_with_subs}")

    title = f"{'🚨 ' if priority == 'urgent' else '📢 '}{announcement.title}"
    body = announcement.content[:100] + ('...' if len(announcement.content) > 100 else '')

    sent = send_notification_to_users(
        users=users_to_notify,
        notification_type='announcement',
        title=title,
        body=body,
        url=f'/comms/announcements/{announcement.id}/',
        data={'announcement_id': announcement.id},
        priority=priority,
    )

    logger.info(f"Announcement notifications sent: {sent}")
    return sent


def notify_song_submission(submission):
    """Send notifications when a new song is submitted."""
    from core.models import OrganizationMembership

    memberships = OrganizationMembership.objects.filter(
        organization=submission.organization,
        is_active=True,
    ).select_related('user')

    users = [m.user for m in memberships if m.user.is_active]

    if submission.submitted_by:
        users = [u for u in users if u.pk != submission.submitted_by.pk]

    submitter = submission.submitter_name or 'Someone'
    title = '🎵 New Song Suggestion'
    body = f'{submitter} suggested {submission.title} by {submission.artist}'

    sent = send_notification_to_users(
        users=users,
        notification_type='song_submission',
        title=title,
        body=body,
        url=f'/songs/{submission.pk}/',
        data={'submission_id': submission.pk},
    )

    logger.info(f"Song submission notifications sent: {sent}")
    return sent


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

    # Handle standalone tasks vs project tasks
    if task.project:
        url = f'/comms/projects/{task.project.id}/tasks/{task.id}/'
        data = {'task_id': task.id, 'project_id': task.project.id}
    else:
        url = f'/tasks/{task.id}/'
        data = {'task_id': task.id}

    return send_notification_to_user(
        user=user,
        notification_type='followup',  # Reuse followup type for task notifications
        title=f"Task assigned: {task.title}",
        body=f"{assigner_name} assigned you to this task{due_info}",
        url=url,
        data=data,
        priority='high' if task.priority in ['high', 'urgent'] else 'normal',
    )


def notify_task_due_soon(task):
    """
    Send notification for a task that's due soon (e.g., today or tomorrow).
    """
    # Handle standalone tasks vs project tasks
    if task.project:
        url = f'/comms/projects/{task.project.id}/tasks/{task.id}/'
        data = {'task_id': task.id, 'project_id': task.project.id}
        context = task.project.name
    else:
        url = f'/tasks/{task.id}/'
        data = {'task_id': task.id}
        context = 'Personal Task'

    total_sent = 0
    for user in task.assignees.all():
        sent = send_notification_to_user(
            user=user,
            notification_type='followup',
            title=f"Task due soon: {task.title}",
            body=f"Due {task.due_date.strftime('%b %d')} - {context}",
            url=url,
            data=data,
            priority='high',
        )
        total_sent += sent
    return total_sent


def notify_task_comment(comment):
    """
    Notify assignees, mentioned users, and watchers about a new task comment.
    Respects per-user NotificationPreference toggles.
    """
    from .models import TaskWatcher, NotificationPreference

    task = comment.task
    author = comment.author

    # Collect all candidate recipients with their reason
    author_pk = author.pk if author else None
    assignee_ids = set(task.assignees.exclude(pk=author_pk).values_list('pk', flat=True))
    mentioned_ids = set(comment.mentioned_users.exclude(pk=author_pk).values_list('pk', flat=True))
    watcher_ids = set(
        TaskWatcher.objects.filter(task=task)
        .exclude(user__pk=author_pk)
        .values_list('user__pk', flat=True)
    )

    # Remove assignees from watcher set to avoid double-notifying
    watcher_only_ids = watcher_ids - assignee_ids - mentioned_ids
    # Remove mentioned users from assignee set (mentions take precedence for flag check)
    assignee_only_ids = assignee_ids - mentioned_ids

    from accounts.models import User

    project = task.project
    if project:
        url = f"/comms/projects/{project.pk}/tasks/{task.pk}/"
    else:
        url = f"/tasks/{task.pk}/"

    title = f"New comment on: {task.title}"
    body_text = comment.content[:140]

    # Always notify mentioned users (respects no special flag beyond @mention)
    for uid in mentioned_ids:
        try:
            user = User.objects.get(pk=uid)
            send_notification_to_user(
                user, 'task', title, body_text, url,
                data={'task_id': task.pk, 'reason': 'mention'},
            )
        except User.DoesNotExist:
            continue

    # Notify assignees per their preference
    for uid in assignee_only_ids:
        try:
            user = User.objects.get(pk=uid)
            prefs = NotificationPreference.get_or_create_for_user(user)
            if prefs.task_comment_on_assigned:
                send_notification_to_user(
                    user, 'task', title, body_text, url,
                    data={'task_id': task.pk, 'reason': 'assigned'},
                )
        except User.DoesNotExist:
            continue

    # Notify watchers per their preference
    for uid in watcher_only_ids:
        try:
            user = User.objects.get(pk=uid)
            prefs = NotificationPreference.get_or_create_for_user(user)
            if prefs.task_comment_on_watched:
                send_notification_to_user(
                    user, 'task', title, body_text, url,
                    data={'task_id': task.pk, 'reason': 'watching'},
                )
        except User.DoesNotExist:
            continue


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


def notify_new_studio_post(post):
    """Send notifications when a new creative studio post is published."""
    from core.models import OrganizationMembership

    memberships = OrganizationMembership.objects.filter(
        organization=post.organization,
        is_active=True,
    ).select_related('user')

    users = [m.user for m in memberships if m.user.is_active and m.user.pk != post.author_id]

    author_name = post.author.display_name or post.author.username
    title = f'🎨 New in Studio: {post.title}'
    body = f'{author_name} shared a new {post.get_post_type_display().lower()}'

    sent = send_notification_to_users(
        users=users,
        notification_type='studio',
        title=title,
        body=body,
        url=f'/studio/post/{post.pk}/',
        data={'post_id': post.pk},
    )
    logger.info(f"Studio new post notifications sent: {sent}")
    return sent


def notify_studio_comment(comment):
    """Send notification when someone comments on a studio post."""
    post = comment.post
    if comment.author_id == post.author_id:
        return 0

    commenter_name = comment.author.display_name or comment.author.username
    return send_notification_to_user(
        user=post.author,
        notification_type='studio',
        title=f'💬 Comment on {post.title}',
        body=f'{commenter_name}: {comment.content[:100]}',
        url=f'/studio/post/{post.pk}/',
        data={'post_id': post.pk, 'comment_id': comment.pk},
    )


def notify_studio_build(child_post):
    """Send notification when someone builds on a studio post."""
    parent = child_post.parent_post
    if not parent or child_post.author_id == parent.author_id:
        return 0

    builder_name = child_post.author.display_name or child_post.author.username
    return send_notification_to_user(
        user=parent.author,
        notification_type='studio',
        title=f'🔨 Build on {parent.title}',
        body=f'{builder_name} built on your post: {child_post.title}',
        url=f'/studio/post/{child_post.pk}/',
        data={'post_id': child_post.pk, 'parent_id': parent.pk},
    )


def notify_studio_spotlight(post):
    """Send notification when a post is spotlighted."""
    if not post.spotlighted_by or post.spotlighted_by_id == post.author_id:
        return 0

    spotter_name = post.spotlighted_by.display_name or post.spotlighted_by.username
    body = f'{spotter_name} spotlighted your post'
    if post.spotlight_note:
        body += f': "{post.spotlight_note}"'

    return send_notification_to_user(
        user=post.author,
        notification_type='studio',
        title=f'⭐ {post.title} was spotlighted!',
        body=body,
        url=f'/studio/post/{post.pk}/',
        data={'post_id': post.pk},
    )
