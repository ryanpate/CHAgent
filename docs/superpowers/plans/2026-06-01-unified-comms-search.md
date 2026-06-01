# Unified Communication Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One search box that finds matches across task comments, project discussions, channel messages, DMs, announcements, and task/project titles — each deep-linked, with access control that never surfaces content the user can't already see.

**Architecture:** A focused `core/search.py` module (`unified_search()` + `snippet()`) holds all matching + access-control logic, kept out of the view for isolated testing. A thin `search` view renders grouped results with filter tabs; a nav search input feeds it. Matching uses `icontains` (portable across the SQLite test DB and Postgres prod).

**Tech Stack:** Django 5, pytest. Spec: `docs/superpowers/specs/2026-06-01-unified-comms-search-design.md`.

**Test command:** `python3 -m pytest tests/<file> -v`. Full suite must stay green (currently 831 passing).

**Verified anchors:**
- Models/fields: `DirectMessage(sender, recipient, content, created_at)`; `ChannelMessage(channel, author, content, created_at)`; `ProjectDiscussionMessage(discussion, author, content, created_at)`; `ProjectDiscussion(project, title)`; `Announcement(organization, title, content, created_at)`; `Task(project, title, description, created_by, created_at)`; `Project(organization, name, description, owner, members, created_at)`; `Channel(organization, is_private, members, slug, name)`; `TaskComment(task, author, content, created_at)`.
- Access filters (from list views): projects `Q(owner=user)|Q(members=user)`+org; channels `Q(is_private=False)|Q(members=user)`+org; DMs `Q(sender=user)|Q(recipient=user)`; announcements org-wide.
- Deep-link URL names: `task_detail(project_pk, pk)`, `channel_detail(slug)`, `dm_conversation(user_id)`, `announcement_detail(pk)`, `project_detail(pk)`, `discussion_detail(project_pk, pk)`.
- `core/views.py` uses `get_org(request)` (= `request.organization`) and `@login_required`. `base.html` has an authenticated sidebar nav + a mobile header (`{% if user.is_authenticated %}` at ~line 367; mobile header at ~390).

---

### Task 1: `snippet()` highlight helper

**Files:**
- Create: `core/search.py`
- Test: `tests/test_search.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_search.py
from django.utils.safestring import SafeString
from core.search import snippet


def test_snippet_highlights_match_case_insensitive():
    out = snippet("We moved the Easter set to G", "easter")
    assert '<mark>Easter</mark>' in out
    assert isinstance(out, SafeString)


def test_snippet_escapes_html():
    out = snippet("<script>alert(1)</script> easter", "easter")
    assert '<script>' not in out          # raw tag escaped
    assert '&lt;script&gt;' in out
    assert '<mark>easter</mark>' in out


def test_snippet_windows_long_text():
    text = "x" * 500 + " easter " + "y" * 500
    out = snippet(text, "easter")
    assert 'easter' in out.lower()
    assert len(out) < 500  # truncated around the match
    assert '…' in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_search.py -k snippet -v`
Expected: FAIL — `core.search` doesn't exist.

- [ ] **Step 3: Implement**

```python
# core/search.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_search.py -k snippet -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/search.py tests/test_search.py
git commit -m "feat: add snippet() highlight helper for search"
```

---

### Task 2: `unified_search()` service with access control

**Files:**
- Modify: `core/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: Write the failing tests (matching + org isolation + access control)**

```python
# append to tests/test_search.py
import pytest
from django.urls import reverse
from accounts.models import User
from core.models import (Organization, SubscriptionPlan, OrganizationMembership, Project, Task,
                         TaskComment, Channel, ChannelMessage, DirectMessage, Announcement,
                         ProjectDiscussion, ProjectDiscussionMessage)
from core.search import unified_search


@pytest.fixture
def world(db):
    plan = SubscriptionPlan.objects.create(slug='s-search', name='S', tier='team')
    org = Organization.objects.create(name='Org', email='o@x.org', slug='org-search',
                                      subscription_plan=plan, subscription_status='active')
    other_org = Organization.objects.create(name='Other', email='o2@x.org', slug='other-search',
                                            subscription_plan=plan, subscription_status='active')
    alice = User.objects.create_user(username='alice@x.org', email='alice@x.org', password='supersecret1')
    bob = User.objects.create_user(username='bob@x.org', email='bob@x.org', password='supersecret1')
    for u in (alice, bob):
        OrganizationMembership.objects.create(user=u, organization=org, role='member')
        u.default_organization = org; u.save()
    return dict(org=org, other_org=other_org, alice=alice, bob=bob)


@pytest.mark.django_db
def test_finds_matches_across_surfaces_for_member(world):
    org, alice = world['org'], world['alice']
    proj = Project.objects.create(organization=org, name='Easter project', owner=alice)
    proj.members.add(alice)
    task = Task.objects.create(organization=org, project=proj, title='Easter worship set', created_by=alice)
    TaskComment.objects.create(task=task, author=alice, content='moved easter set to G')
    chan = Channel.objects.create(organization=org, name='production', slug='production', is_private=False)
    ChannelMessage.objects.create(channel=chan, author=alice, content='easter set list ready?')
    Announcement.objects.create(organization=org, title='Easter service', content='plan')
    disc = ProjectDiscussion.objects.create(organization=org, project=proj, title='Easter service plan', created_by=alice)
    ProjectDiscussionMessage.objects.create(discussion=disc, author=alice, content='easter logistics')

    res = unified_search(org, alice, 'easter')
    assert len(res['projects']) == 1
    assert len(res['tasks']) == 1
    assert len(res['task_comments']) == 1
    assert len(res['channel_messages']) == 1
    assert len(res['announcements']) == 1
    assert len(res['discussions']) >= 1
    # result shape + deep link
    assert res['tasks'][0]['url'] == reverse('task_detail', args=[proj.id, task.id])
    assert res['channel_messages'][0]['url'] == reverse('channel_detail', args=[chan.slug])


@pytest.mark.django_db
def test_short_query_and_org_isolation(world):
    org, other_org, alice = world['org'], world['other_org'], world['alice']
    Announcement.objects.create(organization=other_org, title='Easter elsewhere', content='x')
    assert unified_search(org, alice, 'e') == {k: [] for k in unified_search(org, alice, 'e')}  # <2 chars -> empty
    res = unified_search(org, alice, 'easter')
    assert res['announcements'] == []  # other org's announcement not visible


@pytest.mark.django_db
def test_private_channel_not_leaked(world):
    org, alice, bob = world['org'], world['alice'], world['bob']
    priv = Channel.objects.create(organization=org, name='leaders', slug='leaders', is_private=True)
    priv.members.add(alice)  # bob is NOT a member
    ChannelMessage.objects.create(channel=priv, author=alice, content='easter secret')
    assert len(unified_search(org, alice, 'easter')['channel_messages']) == 1
    assert unified_search(org, bob, 'easter')['channel_messages'] == []


@pytest.mark.django_db
def test_dm_only_for_participants(world):
    org, alice, bob = world['org'], world['alice'], world['bob']
    carol = User.objects.create_user(username='carol@x.org', email='carol@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=carol, organization=org, role='member')
    DirectMessage.objects.create(sender=alice, recipient=bob, content='easter plan')
    assert len(unified_search(org, alice, 'easter')['direct_messages']) == 1
    assert len(unified_search(org, bob, 'easter')['direct_messages']) == 1
    assert unified_search(org, carol, 'easter')['direct_messages'] == []  # not a participant


@pytest.mark.django_db
def test_project_content_not_leaked_to_non_member(world):
    org, alice, bob = world['org'], world['alice'], world['bob']
    proj = Project.objects.create(organization=org, name='Private plan', owner=alice)
    proj.members.add(alice)  # bob not a member
    task = Task.objects.create(organization=org, project=proj, title='Easter rehearsal', created_by=alice)
    TaskComment.objects.create(task=task, author=alice, content='easter notes')
    a = unified_search(org, alice, 'easter')
    assert len(a['tasks']) == 1 and len(a['task_comments']) == 1
    b = unified_search(org, bob, 'easter')
    assert b['tasks'] == [] and b['task_comments'] == []
```

> Note: confirm minimal required fields for each `objects.create` by reading the models (e.g. `Channel.slug` is required; `Task.organization` and `project` both set). Adjust fixture creates if a NOT NULL field is missing.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_search.py -k "surfaces or isolation or leaked or participants or non_member" -v`
Expected: FAIL — `unified_search` not defined.

- [ ] **Step 3: Implement `unified_search`**

Append to `core/search.py`:

```python
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
            'url': reverse('announcement_detail', args=[a.id]), 'author': '', 'when': a.created_at,
        } for a in qs]

    return results
```

> If `Announcement` has an `author` field, set `'author': _name(a.author)`; otherwise leave `''` (confirm by reading the model). If `DirectMessage` has an `organization` field, you may add `organization=organization` to its filter for multi-org tidiness, but sender/recipient is the security boundary.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_search.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add core/search.py tests/test_search.py
git commit -m "feat: unified_search service across comms surfaces with access control"
```

---

### Task 3: `search` view + URL + results template

**Files:**
- Modify: `core/urls.py` (add route), `core/views.py` (add view)
- Create: `templates/core/search_results.html`
- Test: `tests/test_search.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_search.py
def _login(client, world, who='alice'):
    client.force_login(world[who])
    return world[who]

@pytest.mark.django_db
def test_search_view_groups_and_filters(client, world):
    org, alice = world['org'], world['alice']
    proj = Project.objects.create(organization=org, name='Easter project', owner=alice)
    proj.members.add(alice)
    Task.objects.create(organization=org, project=proj, title='Easter set', created_by=alice)
    _login(client, world)

    resp = client.get(reverse('search'), {'q': 'easter'})
    assert resp.status_code == 200
    body = resp.content.decode()
    assert 'Easter project' in body and 'Easter set' in body

    # type filter narrows to one surface
    resp2 = client.get(reverse('search'), {'q': 'easter', 'type': 'tasks'})
    b2 = resp2.content.decode()
    assert 'Easter set' in b2
    assert 'Easter project' not in b2  # projects surface not shown when type=tasks

@pytest.mark.django_db
def test_search_view_min_length_and_empty(client, world):
    _login(client, world)
    short = client.get(reverse('search'), {'q': 'e'}).content.decode()
    assert 'at least 2 characters' in short.lower() or 'type at least' in short.lower()
    empty = client.get(reverse('search'), {'q': 'zzzznomatch'}).content.decode()
    assert 'no results' in empty.lower() or 'nothing' in empty.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_search.py -k "view" -v`
Expected: FAIL — `NoReverseMatch: 'search'`.

- [ ] **Step 3: Add URL + view + template**

In `core/urls.py` add (near other top-level routes): `path('search/', views.search, name='search'),`

In `core/views.py` add:
```python
@login_required
def search(request):
    """Unified communication search results page."""
    from .search import unified_search, SURFACES, SURFACE_LABELS
    org = get_org(request)
    q = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '') or None
    if type_filter not in SURFACES:
        type_filter = None
    results = unified_search(org, request.user, q, type=type_filter) if org else {k: [] for k in SURFACES}
    total = sum(len(v) for v in results.values())
    return render(request, 'core/search_results.html', {
        'q': q,
        'type_filter': type_filter,
        'results': results,
        'surfaces': SURFACES,
        'surface_labels': SURFACE_LABELS,
        'total': total,
        'too_short': 0 < len(q) < 2,
    })
```

Create `templates/core/search_results.html`:
```html
{% extends 'base.html' %}
{% block title %}Search - {{ ai_assistant_name }}{% endblock %}
{% block content %}
<div class="max-w-4xl mx-auto">
  <h1 class="text-2xl font-bold text-white mb-4">Search</h1>
  <form method="get" action="{% url 'search' %}" class="mb-6">
    <input type="text" name="q" value="{{ q }}" placeholder="Search messages, comments, tasks…"
           class="w-full bg-ch-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-ch-gold">
  </form>

  {% if too_short %}
    <p class="text-gray-400">Type at least 2 characters to search.</p>
  {% elif not q %}
    <p class="text-gray-400">Search across tasks, comments, discussions, channels, messages, and announcements.</p>
  {% else %}
    <!-- Filter tabs -->
    <div class="flex flex-wrap gap-2 mb-6 text-sm">
      <a href="?q={{ q|urlencode }}" class="px-3 py-1 rounded-full {% if not type_filter %}bg-ch-gold text-ch-black{% else %}bg-ch-gray text-gray-300{% endif %}">All ({{ total }})</a>
      {% for s in surfaces %}
        {% if results|dictkey:s %}
        <a href="?q={{ q|urlencode }}&type={{ s }}" class="px-3 py-1 rounded-full {% if type_filter == s %}bg-ch-gold text-ch-black{% else %}bg-ch-gray text-gray-300{% endif %}">{{ surface_labels|dictkey:s }} ({{ results|dictkey:s|length }})</a>
        {% endif %}
      {% endfor %}
    </div>

    {% if total == 0 %}
      <p class="text-gray-400">No results for "{{ q }}".</p>
    {% else %}
      {% for s in surfaces %}
        {% with rows=results|dictkey:s %}
        {% if rows %}
        <section class="mb-8">
          <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">{{ surface_labels|dictkey:s }} ({{ rows|length }})</h2>
          <div class="space-y-3">
            {% for r in rows %}
            <a href="{{ r.url }}" class="block bg-ch-dark rounded-lg p-4 hover:bg-ch-gray transition">
              <div class="flex justify-between gap-3">
                <span class="font-medium text-white">{{ r.title }}</span>
                <span class="text-xs text-gray-500 flex-shrink-0">{{ r.when|date:"M j, Y" }}</span>
              </div>
              <p class="text-sm text-gray-400 mt-1">{{ r.snippet }}</p>
              {% if r.author %}<p class="text-xs text-gray-500 mt-1">{{ r.author }}</p>{% endif %}
            </a>
            {% endfor %}
          </div>
        </section>
        {% endif %}
        {% endwith %}
      {% endfor %}
    {% endif %}
  {% endif %}
</div>
{% endblock %}
```

The template uses a `dictkey` filter to index dicts by a variable key. Check whether one already exists: `grep -rn "def dictkey\|@register.filter" core/templatetags/ 2>/dev/null`. If not, create `core/templatetags/search_extras.py`:
```python
from django import template
register = template.Library()

@register.filter
def dictkey(d, key):
    try:
        return d.get(key)
    except AttributeError:
        return None
```
Ensure `core/templatetags/__init__.py` exists. Load it in the template by adding `{% load search_extras %}` right after `{% extends 'base.html' %}`. (If the project already has an equivalent get-item filter, use that instead and skip creating one.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_search.py -k "view" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/urls.py core/views.py templates/core/search_results.html core/templatetags/ tests/test_search.py
git commit -m "feat: search results view, route, and grouped results template"
```

---

### Task 4: Nav search input

**Files:**
- Modify: `templates/base.html`
- Test: `tests/test_search.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_search.py
@pytest.mark.django_db
def test_nav_has_search_input(client, world):
    # active org so middleware doesn't redirect
    org = world['org']; org.stripe_subscription_id = 'sub_x'; org.save()
    _login(client, world)
    body = client.get(reverse('dashboard')).content.decode()
    assert reverse('search') in body
    assert 'name="q"' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_search.py::test_nav_has_search_input -v`
Expected: FAIL — no search input in nav.

- [ ] **Step 3: Add the nav search form**

In `templates/base.html`, inside the authenticated block (`{% if user.is_authenticated %}`), add a search form to BOTH the desktop sidebar (near the top, above the nav links) and the mobile header (the `md:hidden` header ~line 390), so it's reachable on every page. Read the surrounding markup first and match styling. Example (desktop sidebar, place above the first nav section):
```html
<form method="get" action="{% url 'search' %}" class="px-4 mb-4">
  <input type="text" name="q" placeholder="Search…"
         class="w-full bg-ch-gray border border-gray-700 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-ch-gold">
</form>
```
For the mobile header, add a compact search link/icon to `{% url 'search' %}` (a full input may not fit the header row — a search icon linking to the results page is acceptable on mobile). Keep `name="q"` on any input. Ensure the test's assertions (`reverse('search')` and `name="q"` present on the dashboard) hold — the desktop sidebar form satisfies both.

- [ ] **Step 4: Run test + full suite**

Run: `python3 -m pytest tests/test_search.py::test_nav_has_search_input -v && python3 -m pytest tests/ -q 2>&1 | tail -5`
Expected: PASS; full suite 0 failures.

- [ ] **Step 5: Commit**

```bash
git add templates/base.html tests/test_search.py
git commit -m "feat: add unified search input to nav"
```

---

## Self-Review / Coverage

Spec → tasks: snippet escape+highlight (Task 1); `unified_search` across all surfaces + task/project titles with the exact access filters, org isolation, <2-char guard (Task 2); view + grouped results page + filter tabs + min-length/empty states (Task 3); nav entry on every page (Task 4). Security cases (private channel, DM non-participant, non-member project) are explicit tests in Task 2. `icontains` (portable) per spec D. Out-of-scope items (volunteers/songs/PCO/KB, command palette, FTS) are not built.

## Final Verification

- [ ] `python3 -m pytest tests/ -q` → all pass.
- [ ] Manual: as a project member, search a term in a task comment → result links to the task; as a non-member, the same search returns nothing from that project; a private-channel message is invisible to non-members; the nav search box appears on every authenticated page and submits to `/search/`.
