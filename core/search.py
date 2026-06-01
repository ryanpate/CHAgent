import re
from django.utils.html import escape
from django.utils.safestring import mark_safe


def snippet(text, query, width=160):
    """Return an HTML-safe excerpt around the first match, with the query <mark>ed.

    Escapes the source text first, then highlights, so user content cannot inject markup.
    """
    if not text:
        return mark_safe('')
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        excerpt = text[:width]
        prefix, suffix = '', ('…' if len(text) > width else '')
    else:
        start = max(0, idx - width // 3)
        end = min(len(text), idx + len(query) + width)
        excerpt = text[start:end]
        prefix = '…' if start > 0 else ''
        suffix = '…' if end < len(text) else ''
    escaped = escape(excerpt)
    pattern = re.escape(escape(query))
    highlighted = re.sub(f'({pattern})', r'<mark>\1</mark>', escaped, flags=re.IGNORECASE)
    return mark_safe(prefix + highlighted + suffix)


from django.db.models import Q
from django.urls import reverse

SURFACES = ['projects', 'tasks', 'task_comments', 'discussions',
            'channel_messages', 'direct_messages', 'announcements']

SURFACE_LABELS = {
    'projects': 'Projects', 'tasks': 'Tasks', 'task_comments': 'Comments',
    'discussions': 'Discussions', 'channel_messages': 'Channels',
    'direct_messages': 'Messages', 'announcements': 'Announcements',
}


def _name(user):
    if not user:
        return ''
    full = user.get_full_name() if hasattr(user, 'get_full_name') else ''
    return full or getattr(user, 'username', '')


def unified_search(organization, user, query, type=None, limit_per_type=20):
    """Search communication surfaces + task/project titles, access-scoped to `user`.

    Returns {surface_key: [ {type, title, snippet, url, author, when}, ... ]}.
    """
    results = {k: [] for k in SURFACES}
    q = (query or '').strip()
    if len(q) < 2 or organization is None:
        return results

    targets = [type] if type in SURFACES else SURFACES
    cap = 100 if type in SURFACES else limit_per_type
    proj_access = Q(owner=user) | Q(members=user)

    if 'projects' in targets:
        from core.models import Project
        qs = (Project.objects.filter(organization=organization)
              .filter(proj_access)
              .filter(Q(name__icontains=q) | Q(description__icontains=q))
              .distinct().select_related('owner').order_by('-created_at')[:cap])
        results['projects'] = [{
            'type': 'projects', 'title': p.name, 'snippet': snippet(p.description or p.name, q),
            'url': reverse('project_detail', args=[p.id]), 'author': _name(p.owner), 'when': p.created_at,
        } for p in qs]

    if 'tasks' in targets:
        from core.models import Task
        qs = (Task.objects.filter(project__organization=organization)
              .filter(Q(project__owner=user) | Q(project__members=user))
              .filter(Q(title__icontains=q) | Q(description__icontains=q))
              .distinct().select_related('project', 'created_by').order_by('-created_at')[:cap])
        results['tasks'] = [{
            'type': 'tasks', 'title': t.title, 'snippet': snippet(t.description or t.title, q),
            'url': reverse('task_detail', args=[t.project_id, t.id]),
            'author': _name(t.created_by), 'when': t.created_at,
        } for t in qs]

    if 'task_comments' in targets:
        from core.models import TaskComment
        qs = (TaskComment.objects.filter(task__project__organization=organization)
              .filter(Q(task__project__owner=user) | Q(task__project__members=user))
              .filter(content__icontains=q)
              .distinct().select_related('task', 'task__project', 'author').order_by('-created_at')[:cap])
        results['task_comments'] = [{
            'type': 'task_comments', 'title': c.task.title, 'snippet': snippet(c.content, q),
            'url': reverse('task_detail', args=[c.task.project_id, c.task_id]),
            'author': _name(c.author), 'when': c.created_at,
        } for c in qs]

    if 'discussions' in targets:
        from core.models import ProjectDiscussion, ProjectDiscussionMessage
        msg_qs = (ProjectDiscussionMessage.objects
                  .filter(discussion__project__organization=organization)
                  .filter(Q(discussion__project__owner=user) | Q(discussion__project__members=user))
                  .filter(content__icontains=q)
                  .distinct().select_related('discussion', 'discussion__project', 'author')
                  .order_by('-created_at')[:cap])
        title_qs = (ProjectDiscussion.objects
                    .filter(project__organization=organization)
                    .filter(Q(project__owner=user) | Q(project__members=user))
                    .filter(title__icontains=q)
                    .distinct().select_related('project', 'created_by').order_by('-created_at')[:cap])
        items = [{
            'type': 'discussions', 'title': m.discussion.title, 'snippet': snippet(m.content, q),
            'url': reverse('discussion_detail', args=[m.discussion.project_id, m.discussion_id]),
            'author': _name(m.author), 'when': m.created_at,
        } for m in msg_qs]
        items += [{
            'type': 'discussions', 'title': d.title, 'snippet': snippet(d.title, q),
            'url': reverse('discussion_detail', args=[d.project_id, d.id]),
            'author': _name(d.created_by), 'when': d.created_at,
        } for d in title_qs]
        results['discussions'] = items[:cap]

    if 'channel_messages' in targets:
        from core.models import ChannelMessage
        qs = (ChannelMessage.objects.filter(channel__organization=organization)
              .filter(Q(channel__is_private=False) | Q(channel__members=user))
              .filter(content__icontains=q)
              .distinct().select_related('channel', 'author').order_by('-created_at')[:cap])
        results['channel_messages'] = [{
            'type': 'channel_messages', 'title': '#' + m.channel.name, 'snippet': snippet(m.content, q),
            'url': reverse('channel_detail', args=[m.channel.slug]),
            'author': _name(m.author), 'when': m.created_at,
        } for m in qs]

    if 'direct_messages' in targets:
        from core.models import DirectMessage
        qs = (DirectMessage.objects.filter(Q(sender=user) | Q(recipient=user))
              .filter(content__icontains=q)
              .select_related('sender', 'recipient').order_by('-created_at')[:cap])
        items = []
        for m in qs:
            other = m.recipient if m.sender_id == user.id else m.sender
            items.append({
                'type': 'direct_messages', 'title': 'DM with ' + _name(other),
                'snippet': snippet(m.content, q),
                'url': reverse('dm_conversation', args=[other.id]),
                'author': _name(m.sender), 'when': m.created_at,
            })
        results['direct_messages'] = items

    if 'announcements' in targets:
        from core.models import Announcement
        qs = (Announcement.objects.filter(organization=organization)
              .filter(Q(title__icontains=q) | Q(content__icontains=q))
              .order_by('-created_at')[:cap])
        results['announcements'] = [{
            'type': 'announcements', 'title': a.title, 'snippet': snippet(a.content, q),
            'url': reverse('announcement_detail', args=[a.id]), 'author': _name(a.author), 'when': a.created_at,
        } for a in qs]

    return results
