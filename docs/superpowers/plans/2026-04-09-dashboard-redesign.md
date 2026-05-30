# Dashboard & Sidebar Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the dashboard from a chat-heavy page into a command center with priority cards and notification badges, fix the mobile sidebar scroll issue, and reorganize sidebar navigation into grouped sections.

**Architecture:** The dashboard loses the embedded chat (which moves to its own `/chat/` page) and gains a compact Aria input bar, priority cards with badge counts, and an activity feed. Badge counts come from a context processor so both dashboard cards and sidebar badges share the same data. The sidebar gets grouped section labels and `overflow-y: auto`.

**Tech Stack:** Django templates, Tailwind CSS, HTMX, existing model queries (FollowUp, Task, DirectMessage, ChannelMessage)

**Spec:** `docs/superpowers/specs/2026-04-09-dashboard-redesign-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `core/context_processors.py` | Modify | Add badge counts (follow-ups, tasks, messages, interactions this week) |
| `core/views.py` | Modify | Simplify `dashboard()`, make `chat()` render template |
| `templates/core/dashboard.html` | Rewrite | Command center layout |
| `templates/core/chat.html` | Modify | Add `?q=` auto-submit support, full-height chat area |
| `templates/base.html` | Modify | Sidebar grouping, scroll fix, badge counts, Chat with Aria link |
| `tests/test_dashboard_redesign.py` | Create | Tests for badge counts, dashboard view, chat view, sidebar |

---

### Task 1: Add Badge Counts to Context Processor

**Files:**
- Modify: `core/context_processors.py`
- Create: `tests/test_dashboard_redesign.py`

- [ ] **Step 1: Write failing tests for badge counts**

Create `tests/test_dashboard_redesign.py`:

```python
"""Tests for dashboard redesign: badge counts, dashboard view, chat view."""
import pytest
from datetime import timedelta
from django.test import Client
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestBadgeCounts:
    """Test that badge counts appear in template context via context processor."""

    def test_pending_followup_count_in_context(self, org_a_client, org_a_user, org_a):
        """Pending follow-ups assigned to user appear in context."""
        from core.models import FollowUp
        FollowUp.objects.create(
            organization=org_a,
            created_by=org_a_user,
            assigned_to=org_a_user,
            title='Test followup',
            status='pending',
            follow_up_date=timezone.now().date(),
        )
        FollowUp.objects.create(
            organization=org_a,
            created_by=org_a_user,
            assigned_to=org_a_user,
            title='Completed followup',
            status='completed',
            follow_up_date=timezone.now().date(),
        )
        response = org_a_client.get('/')
        assert response.context['pending_followup_count'] == 1

    def test_pending_task_count_in_context(self, org_a_client, org_a_user, org_a):
        """To-do and in-progress tasks assigned to user appear in context."""
        from core.models import Task
        task = Task.objects.create(
            organization=org_a,
            title='Test task',
            status='todo',
            created_by=org_a_user,
        )
        task.assignees.add(org_a_user)
        done_task = Task.objects.create(
            organization=org_a,
            title='Done task',
            status='completed',
            created_by=org_a_user,
        )
        done_task.assignees.add(org_a_user)
        response = org_a_client.get('/')
        assert response.context['pending_task_count'] == 1

    def test_unread_message_count_in_context(self, org_a_client, org_a_user, org_a):
        """Unread DMs appear in context."""
        from core.models import DirectMessage
        other_user = User.objects.create_user(
            username='sender', email='sender@test.com', password='testpass123'
        )
        DirectMessage.objects.create(
            sender=other_user,
            recipient=org_a_user,
            content='Hello',
            is_read=False,
            organization=org_a,
        )
        DirectMessage.objects.create(
            sender=other_user,
            recipient=org_a_user,
            content='Read msg',
            is_read=True,
            organization=org_a,
        )
        response = org_a_client.get('/')
        assert response.context['unread_message_count'] == 1

    def test_interactions_this_week_in_context(self, org_a_client, org_a_user, org_a):
        """Interactions from the last 7 days appear in context."""
        from core.models import Interaction
        Interaction.objects.create(
            organization=org_a,
            user=org_a_user,
            content='Recent interaction',
        )
        response = org_a_client.get('/')
        assert response.context['interactions_this_week'] == 1

    def test_badge_counts_scoped_to_org(self, org_a_client, org_a_user, org_a, org_b, org_b_user):
        """Badge counts only include items from the user's organization."""
        from core.models import FollowUp
        # Create followup in org_b — should NOT appear in org_a context
        FollowUp.objects.create(
            organization=org_b,
            created_by=org_b_user,
            assigned_to=org_b_user,
            title='Other org followup',
            status='pending',
            follow_up_date=timezone.now().date(),
        )
        response = org_a_client.get('/')
        assert response.context['pending_followup_count'] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_redesign.py -v`
Expected: FAIL — `pending_followup_count` not in context

- [ ] **Step 3: Add badge counts to context processor**

In `core/context_processors.py`, add the following after the `pending_song_count` block (around line 74), inside the `if organization:` block:

```python
        # Badge counts for dashboard cards and sidebar
        from core.models import FollowUp, Task, DirectMessage
        try:
            context['pending_followup_count'] = FollowUp.objects.filter(
                organization=organization,
                assigned_to=request.user,
                status__in=['pending', 'in_progress'],
            ).count()
        except Exception:
            context['pending_followup_count'] = 0

        try:
            context['pending_task_count'] = Task.objects.filter(
                organization=organization,
                assignees=request.user,
                status__in=['todo', 'in_progress'],
            ).count()
        except Exception:
            context['pending_task_count'] = 0

        try:
            context['unread_message_count'] = DirectMessage.objects.filter(
                organization=organization,
                recipient=request.user,
                is_read=False,
            ).count()
        except Exception:
            context['unread_message_count'] = 0

        try:
            from django.utils import timezone
            from datetime import timedelta
            week_ago = timezone.now() - timedelta(days=7)
            from core.models import Interaction
            context['interactions_this_week'] = Interaction.objects.filter(
                organization=organization,
                created_at__gte=week_ago,
            ).count()
        except Exception:
            context['interactions_this_week'] = 0
```

Also add default values in the initial `context` dict (around line 30):

```python
        'pending_followup_count': 0,
        'pending_task_count': 0,
        'unread_message_count': 0,
        'interactions_this_week': 0,
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_redesign.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 452+ tests PASS, 0 failures

- [ ] **Step 6: Commit**

```bash
git add core/context_processors.py tests/test_dashboard_redesign.py
git commit -m "feat: add badge counts to context processor for dashboard cards and sidebar"
```

---

### Task 2: Update Chat View to Render Template

**Files:**
- Modify: `core/views.py:218-276` (dashboard and chat views)
- Modify: `templates/core/chat.html`

- [ ] **Step 1: Write failing test for chat view**

Add to `tests/test_dashboard_redesign.py`:

```python
@pytest.mark.django_db
class TestChatView:
    """Test that /chat/ renders the chat template instead of redirecting."""

    def test_chat_renders_template(self, org_a_client):
        """GET /chat/ renders chat.html, not a redirect."""
        response = org_a_client.get('/chat/')
        assert response.status_code == 200
        assert 'chat_messages' in response.context

    def test_chat_with_q_param_passes_initial_message(self, org_a_client):
        """GET /chat/?q=hello passes initial_message to template."""
        response = org_a_client.get('/chat/?q=hello+world')
        assert response.status_code == 200
        assert response.context['initial_message'] == 'hello world'

    def test_chat_sets_session_cookie(self, org_a_client):
        """Chat view sets session ID cookie if not present."""
        response = org_a_client.get('/chat/')
        assert response.status_code == 200
        # Session cookie should be set
        assert 'chat_session_id' in response.cookies or response.context['session_id']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_redesign.py::TestChatView -v`
Expected: FAIL — chat returns 302 redirect

- [ ] **Step 3: Update chat view in core/views.py**

Replace the `chat()` function at line 274:

```python
@login_required
def chat(request):
    """Full-page chat interface with Aria."""
    org = get_org(request)

    # Get or create session ID from cookie for chat
    session_id = request.COOKIES.get('chat_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())

    # Get chat messages for this session (scoped to user and organization)
    chat_messages = ChatMessage.objects.filter(
        user=request.user,
        session_id=session_id
    )
    if org:
        chat_messages = chat_messages.filter(organization=org)
    chat_messages = chat_messages.order_by('created_at')

    # Support ?q= param for pre-filled message from dashboard
    initial_message = request.GET.get('q', '')

    context = {
        'chat_messages': chat_messages,
        'session_id': session_id,
        'initial_message': initial_message,
    }

    response = render(request, 'core/chat.html', context)

    # Set session ID cookie if new
    if not request.COOKIES.get('chat_session_id'):
        response.set_cookie('chat_session_id', session_id, max_age=86400 * 7)

    return response
```

- [ ] **Step 4: Add auto-submit JS for ?q= param to chat.html**

Add to the bottom of the `<script>` block in `templates/core/chat.html` (before `</script>`):

```javascript
// Auto-submit if ?q= parameter is present (from dashboard redirect)
(function() {
    const params = new URLSearchParams(window.location.search);
    const initialMessage = params.get('q');
    if (initialMessage) {
        const input = document.querySelector('input[name="message"]');
        if (input) {
            input.value = initialMessage;
            // Clean URL without reloading
            window.history.replaceState({}, '', '/chat/');
            // Trigger HTMX submit after a short delay to ensure form is ready
            setTimeout(() => {
                const form = document.getElementById('chat-form');
                if (form) htmx.trigger(form, 'submit');
            }, 100);
        }
    }
})();
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_redesign.py::TestChatView -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add core/views.py templates/core/chat.html
git commit -m "feat: make /chat/ a full page instead of redirect, support ?q= auto-submit"
```

---

### Task 3: Rewrite Dashboard Template

**Files:**
- Modify: `core/views.py:218-270` (dashboard view)
- Rewrite: `templates/core/dashboard.html`

- [ ] **Step 1: Write failing test for new dashboard**

Add to `tests/test_dashboard_redesign.py`:

```python
@pytest.mark.django_db
class TestDashboardView:
    """Test the redesigned command center dashboard."""

    def test_dashboard_has_no_chat_messages(self, org_a_client):
        """Dashboard no longer includes chat_messages in context."""
        response = org_a_client.get('/')
        assert 'chat_messages' not in response.context

    def test_dashboard_has_badge_counts(self, org_a_client):
        """Dashboard context includes all badge count keys."""
        response = org_a_client.get('/')
        assert 'pending_followup_count' in response.context
        assert 'pending_task_count' in response.context
        assert 'unread_message_count' in response.context
        assert 'interactions_this_week' in response.context

    def test_dashboard_has_existing_context(self, org_a_client):
        """Dashboard still has volunteers and interactions."""
        response = org_a_client.get('/')
        assert 'total_volunteers' in response.context
        assert 'total_interactions' in response.context
        assert 'recent_interactions' in response.context
        assert 'top_volunteers' in response.context

    def test_dashboard_renders_ask_aria_section(self, org_a_client):
        """Dashboard has the compact Ask Aria bar."""
        response = org_a_client.get('/')
        content = response.content.decode()
        assert 'Ask Aria' in content
        assert 'action="/chat/"' in content or "action=\"/chat/\"" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_redesign.py::TestDashboardView -v`
Expected: FAIL — `chat_messages` still in context, no `/chat/` form action

- [ ] **Step 3: Simplify dashboard view**

Replace the `dashboard()` function in `core/views.py` (line 218):

```python
@login_required
def dashboard(request):
    """Command center dashboard with priority cards and activity feed."""
    org = get_org(request)

    # Build base querysets scoped to organization
    volunteer_qs = Volunteer.objects.all()
    interaction_qs = Interaction.objects.all()
    if org:
        volunteer_qs = volunteer_qs.filter(organization=org)
        interaction_qs = interaction_qs.filter(organization=org)

    # Check if onboarding tour should be shown
    show_onboarding = False
    try:
        if not request.user.has_completed_onboarding:
            show_onboarding = True
    except (AttributeError, Exception):
        pass

    # Follow-up summary for dashboard card
    followup_summary = ''
    if org:
        from django.utils import timezone
        today = timezone.now().date()
        due_today = FollowUp.objects.filter(
            organization=org,
            assigned_to=request.user,
            status__in=['pending', 'in_progress'],
            follow_up_date=today,
        ).count()
        overdue = FollowUp.objects.filter(
            organization=org,
            assigned_to=request.user,
            status__in=['pending', 'in_progress'],
            follow_up_date__lt=today,
        ).count()
        parts = []
        if due_today:
            parts.append(f'{due_today} due today')
        if overdue:
            parts.append(f'{overdue} overdue')
        followup_summary = ', '.join(parts) if parts else 'All caught up'

    context = {
        'total_volunteers': volunteer_qs.count(),
        'total_interactions': interaction_qs.count(),
        'recent_interactions': interaction_qs.select_related('user').prefetch_related('volunteers')[:5],
        'top_volunteers': volunteer_qs.annotate(
            interaction_count=Count('interactions')
        ).order_by('-interaction_count')[:5],
        'show_onboarding': show_onboarding,
        'followup_summary': followup_summary,
    }

    return render(request, 'core/dashboard.html', context)
```

- [ ] **Step 4: Rewrite dashboard template**

Replace `templates/core/dashboard.html` entirely with the command center layout. This is a large template — key sections:

1. **Ask Aria bar** — form with `action="/chat/"` method="GET", input named `q`, quick action chips
2. **Needs Attention cards** — 4 cards using `pending_followup_count`, `pending_task_count`, `unread_message_count`, `pending_song_count` from context processor
3. **Recent Activity** — two-column grid with recent interactions and top volunteers (reuses existing data)
4. **Quick Stats** — 3 compact stat boxes

The full template code should be written during implementation, following the mockup from the spec. Key structural elements:

```html
{% extends 'base.html' %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<div class="max-w-6xl mx-auto">

    <!-- Section 1: Ask Aria -->
    <div class="bg-ch-dark rounded-xl p-5 mb-6">
        <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-2">
                <div class="w-2 h-2 bg-ch-gold rounded-full"></div>
                <h2 class="text-lg font-bold">Ask Aria</h2>
            </div>
            <div class="flex gap-2">
                <a href="/chat/" class="px-3 py-1.5 bg-ch-gray hover:bg-gray-600 rounded-lg text-xs">History</a>
                <a href="/chat/" class="px-3 py-1.5 bg-ch-gray hover:bg-gray-600 rounded-lg text-xs">+ New</a>
            </div>
        </div>
        <form action="/chat/" method="GET" class="flex gap-3 mb-3">
            <input type="text" name="q"
                   placeholder="Log an interaction or ask a question..."
                   class="flex-1 bg-ch-gray border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-ch-gold transition"
                   autocomplete="off">
            <button type="submit"
                    class="bg-ch-gold text-black px-6 py-3 rounded-lg font-medium hover:bg-yellow-500 transition">
                Send
            </button>
        </form>
        <!-- Quick action chips -->
        <div class="flex gap-2 flex-wrap">
            <!-- Each chip is an <a> linking to /chat/?q=URL-encoded-message -->
        </div>
    </div>

    <!-- Section 2: Needs Attention -->
    <div class="mb-6">
        <h3 class="text-[10px] text-gray-500 uppercase tracking-[1.5px] font-semibold mb-3">Needs Attention</h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <!-- Follow-ups card -->
            <!-- My Tasks card -->
            <!-- Team Hub card -->
            <!-- Song Submissions card -->
        </div>
    </div>

    <!-- Section 3: Recent Activity -->
    <div class="mb-6">
        <h3 class="text-[10px] text-gray-500 uppercase tracking-[1.5px] font-semibold mb-3">Recent Activity</h3>
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <!-- Recent Interactions -->
            <!-- Top Volunteers -->
        </div>
    </div>

    <!-- Section 4: Quick Stats -->
    <div class="grid grid-cols-3 gap-3">
        <!-- Total Volunteers / Total Interactions / This Week -->
    </div>
</div>

{% include 'core/partials/onboarding_tour.html' %}
{% endblock %}
```

Each priority card follows this pattern (example for Follow-ups):

```html
<a href="{% url 'followup_list' %}"
   class="bg-ch-dark rounded-xl p-4 flex items-center justify-between hover:bg-ch-gray/50 transition
          {% if pending_followup_count %}border-l-[3px] border-ch-gold{% endif %}">
    <div class="flex items-center gap-3">
        <div class="w-9 h-9 rounded-lg bg-ch-gray flex items-center justify-center">
            <svg class="w-5 h-5 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                      d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"></path>
            </svg>
        </div>
        <div>
            <div class="font-semibold text-sm">Follow-ups</div>
            <div class="text-xs text-gray-500">{{ followup_summary }}</div>
        </div>
    </div>
    {% if pending_followup_count %}
    <div class="bg-ch-gold text-black font-bold text-xs w-6 h-6 rounded-full flex items-center justify-center">
        {{ pending_followup_count }}
    </div>
    {% endif %}
</a>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_redesign.py::TestDashboardView -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 452+ tests PASS. Some existing tests may reference `chat_messages` in dashboard context — fix any that fail.

- [ ] **Step 7: Commit**

```bash
git add core/views.py templates/core/dashboard.html
git commit -m "feat: rewrite dashboard as command center with priority cards and Aria bar"
```

---

### Task 4: Fix Sidebar Scroll and Add Grouped Sections

**Files:**
- Modify: `templates/base.html:414-551` (mobile sidebar)
- Modify: `templates/base.html:555-654` (desktop sidebar)

- [ ] **Step 1: Write failing test for sidebar**

Add to `tests/test_dashboard_redesign.py`:

```python
@pytest.mark.django_db
class TestSidebar:
    """Test sidebar changes."""

    def test_sidebar_has_chat_link(self, org_a_client):
        """Sidebar includes a Chat with Aria link."""
        response = org_a_client.get('/')
        content = response.content.decode()
        assert '/chat/' in content
        assert 'Chat with Aria' in content

    def test_sidebar_has_section_labels(self, org_a_client):
        """Sidebar includes group section labels."""
        response = org_a_client.get('/')
        content = response.content.decode()
        # Check for section label text (case-insensitive check on rendered HTML)
        assert 'Core' in content or 'CORE' in content
        assert 'Team' in content
        assert 'Insights' in content

    def test_sidebar_has_followup_badge(self, org_a_client, org_a_user, org_a):
        """Sidebar shows badge count for follow-ups."""
        from core.models import FollowUp
        FollowUp.objects.create(
            organization=org_a,
            created_by=org_a_user,
            assigned_to=org_a_user,
            title='Badge test',
            status='pending',
            follow_up_date=timezone.now().date(),
        )
        response = org_a_client.get('/')
        content = response.content.decode()
        # Badge should appear somewhere near the Follow-ups link
        assert 'pending_followup_count' not in content  # template variable should be rendered
        # The rendered badge count "1" should appear
        assert '>1</span>' in content or '>1</' in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_dashboard_redesign.py::TestSidebar -v`
Expected: FAIL — no "Chat with Aria" link, no section labels

- [ ] **Step 3: Update mobile sidebar in base.html**

In `templates/base.html`, replace the mobile sidebar `<nav>` block (lines 434-513). The new structure:

```html
<nav class="flex-1 overflow-y-auto space-y-4">
    <!-- CORE -->
    <div>
        <div class="text-[10px] text-gray-600 uppercase tracking-[1.5px] font-semibold px-3 pb-1.5">Core</div>
        <div class="space-y-1">
            <a href="{% url 'dashboard' %}" @click="sidebarOpen = false" class="nav-link {% if request.resolver_match.url_name == 'dashboard' %}active{% endif %}">
                <!-- home icon (existing) -->
                Dashboard
            </a>
            <a href="{% url 'chat' %}" @click="sidebarOpen = false" class="nav-link {% if request.resolver_match.url_name == 'chat' %}active{% endif %}">
                <!-- chat bubble icon -->
                Chat with Aria
            </a>
            <a href="{% url 'interaction_list' %}" @click="sidebarOpen = false" class="nav-link {% if 'interaction' in request.resolver_match.url_name %}active{% endif %}">
                <!-- document icon (existing) -->
                Interactions
            </a>
            <a href="{% url 'volunteer_list' %}" @click="sidebarOpen = false" class="nav-link {% if 'volunteer' in request.resolver_match.url_name %}active{% endif %}">
                <!-- people icon (existing) -->
                Volunteers
            </a>
            <a href="{% url 'followup_list' %}" @click="sidebarOpen = false" class="nav-link {% if 'followup' in request.resolver_match.url_name %}active{% endif %} flex justify-between">
                <span class="flex items-center gap-2">
                    <!-- clipboard icon (existing) -->
                    Follow-ups
                </span>
                {% if pending_followup_count %}<span class="bg-ch-gold text-black font-bold text-[10px] w-[18px] h-[18px] rounded-full flex items-center justify-center">{{ pending_followup_count }}</span>{% endif %}
            </a>
        </div>
    </div>

    <!-- TEAM -->
    <div>
        <div class="text-[10px] text-gray-600 uppercase tracking-[1.5px] font-semibold px-3 pb-1.5">Team</div>
        <div class="space-y-1">
            <a href="{% url 'comms_hub' %}" ...with badge for unread_message_count>Team Hub</a>
            <a href="{% url 'my_tasks' %}" ...with badge for pending_task_count>My Tasks</a>
            <a href="{% url 'songs:dashboard' %}" ...with badge for pending_song_count>Song Submissions</a>
        </div>
    </div>

    <!-- CREATIVE -->
    <div>
        <div class="text-[10px] text-gray-600 uppercase tracking-[1.5px] font-semibold px-3 pb-1.5">Creative</div>
        <div class="space-y-1">
            <a href="{% url 'studio_feed' %}" ...>Creative Studio</a>
            <a href="{% url 'document_list' %}" ...>Knowledge Base</a>
        </div>
    </div>

    <!-- INSIGHTS -->
    <div>
        <div class="text-[10px] text-gray-600 uppercase tracking-[1.5px] font-semibold px-3 pb-1.5">Insights</div>
        <div class="space-y-1">
            <a href="{% url 'analytics_dashboard' %}" ...>Analytics</a>
            <a href="{% url 'care_dashboard' %}" ...>Proactive Care</a>
            <a href="{% url 'feedback_dashboard' %}" ...>Feedback</a>
        </div>
    </div>

    <!-- SUPPORT -->
    <div>
        <div class="text-[10px] text-gray-600 uppercase tracking-[1.5px] font-semibold px-3 pb-1.5">Support</div>
        <div class="space-y-1">
            <a href="{% url 'user_guide' %}" ...>Help</a>
        </div>
    </div>
</nav>
```

Key changes:
- `<nav>` gets `flex-1 overflow-y-auto` — this is the scroll fix
- Section labels are `<div class="text-[10px] text-gray-600 uppercase tracking-[1.5px] font-semibold px-3 pb-1.5">`
- Badge spans use `{% if count %}<span class="bg-ch-gold text-black font-bold text-[10px] w-[18px] h-[18px] rounded-full flex items-center justify-center">{{ count }}</span>{% endif %}`
- Nav links with badges use `flex justify-between` with the label+icon in a `<span>` and badge on the right

- [ ] **Step 4: Apply same changes to desktop sidebar**

Apply the identical grouping structure to the desktop sidebar (lines 555-633). Same section labels, same badge spans, same `overflow-y-auto` on the `<nav>`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_dashboard_redesign.py::TestSidebar -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v --tb=short`
Expected: 452+ tests PASS

- [ ] **Step 7: Commit**

```bash
git add templates/base.html
git commit -m "feat: fix sidebar scroll, add grouped sections with badges, add Chat with Aria link"
```

---

### Task 5: Manual QA and Final Cleanup

**Files:**
- Potentially any of the above if issues found

- [ ] **Step 1: Test mobile dashboard in browser**

Open `http://localhost:8000/` on a mobile viewport (375px wide).
Verify:
- Ask Aria bar renders at top with input and chips
- Priority cards stack vertically with badges visible
- Recent activity and stats below
- No chat message area on dashboard

- [ ] **Step 2: Test mobile sidebar scroll**

Open hamburger menu on mobile viewport.
Verify:
- All 5 section groups visible (Core, Team, Creative, Insights, Support)
- Help link at bottom is reachable by scrolling
- Footer (user, Notifications, Settings, Logout) pinned at bottom
- Badge counts appear on Follow-ups, Team Hub, My Tasks, Song Submissions

- [ ] **Step 3: Test desktop dashboard**

Open `http://localhost:8000/` on desktop viewport.
Verify:
- Priority cards in 4-column grid
- Recent activity in 2-column layout
- Desktop sidebar has same grouped sections and badges

- [ ] **Step 4: Test chat page**

Open `http://localhost:8000/chat/`.
Verify:
- Full chat UI renders (message area, input, quick actions)
- History modal works
- Copy button works
- Thinking indicator works on send

- [ ] **Step 5: Test dashboard-to-chat flow**

Type "Who's serving this Sunday?" in the dashboard Ask Aria bar and press Send.
Verify:
- Redirects to `/chat/?q=Who%27s+serving+this+Sunday%3F`
- Chat page auto-fills and submits the message
- URL cleans up to `/chat/`

- [ ] **Step 6: Test quick action chips on dashboard**

Click "Log Interaction" chip on dashboard.
Verify: navigates to `/chat/?q=Log+interaction%3A+`

- [ ] **Step 7: Fix any issues found and commit**

```bash
git add -A
git commit -m "fix: QA fixes for dashboard redesign"
```

- [ ] **Step 8: Run full test suite one final time**

Run: `python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 9: Final commit if any test fixes needed**

```bash
git add -A
git commit -m "fix: test adjustments for dashboard redesign"
```
