# Phase 2: Project Discussions & Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add threaded project-level discussions that can link to multiple tasks, and a unified Decisions tab that aggregates every decision across task comments and discussion messages.

**Architecture:** Two new models (`ProjectDiscussion` + `ProjectDiscussionMessage`) owned by `Project`. Project detail page gets a tabs navigation (Tasks | Discussions | Decisions). Discussion messages can be marked as decisions (like TaskComments from Phase 1). Decisions tab unions both sources with deep links.

**Tech Stack:** Django 5.x, PostgreSQL, pytest, HTMX, Tailwind CSS. Multi-tenant via `organization` FK (inherited from `project.organization`).

**Related Spec:** `docs/superpowers/specs/2026-04-04-todoist-replacement-design.md` (Phase 2)

---

## File Structure

**Create:**
- `core/migrations/00XX_project_discussions.py` — ProjectDiscussion + ProjectDiscussionMessage tables (one migration)
- `templates/core/comms/discussion_list.html` — list of project discussions
- `templates/core/comms/discussion_create.html` — form to create a new discussion
- `templates/core/comms/discussion_detail.html` — thread view with replies
- `templates/core/partials/discussion_message.html` — message partial (HTMX-rendered)
- `templates/core/comms/decisions_tab.html` — aggregated decisions view
- `tests/test_project_discussions.py` — Phase 2 tests

**Modify:**
- `core/models.py` — add `ProjectDiscussion` + `ProjectDiscussionMessage` models
- `core/views.py` — add 6 new views (list, create, detail, post-message, toggle-resolved, toggle-decision, decisions-tab)
- `core/urls.py` — wire new URL routes
- `templates/core/comms/project_detail.html` — add tabs navigation row at the top

---

## Task 1: Create ProjectDiscussion model

**Files:**
- Modify: `core/models.py`
- Test: `tests/test_project_discussions.py` (new file)

- [ ] **Step 1: Create test file with failing test**

Create `tests/test_project_discussions.py`:

```python
"""
Tests for Phase 2: Project Discussions & Decisions.
"""
import pytest
from django.utils import timezone
from django.urls import reverse


@pytest.mark.django_db
class TestProjectDiscussionModel:
    """Tests for the ProjectDiscussion model."""

    def test_create_discussion(self, user_alpha_owner, org_alpha):
        """Discussion is created with title, project, creator, defaults."""
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        discussion = ProjectDiscussion.objects.create(
            organization=org_alpha,
            project=project,
            title='Stage layout change',
            created_by=user_alpha_owner,
        )

        assert discussion.organization == org_alpha
        assert discussion.project == project
        assert discussion.title == 'Stage layout change'
        assert discussion.created_by == user_alpha_owner
        assert discussion.is_resolved is False
        assert discussion.resolved_at is None
        assert discussion.resolved_by is None
        assert discussion.created_at is not None

    def test_discussion_inherits_org_from_project(self, user_alpha_owner, org_alpha):
        """If organization is not set explicitly, save pulls it from project."""
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        discussion = ProjectDiscussion(
            project=project,
            title='Test',
            created_by=user_alpha_owner,
        )
        discussion.save()
        assert discussion.organization == org_alpha
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_discussions.py::TestProjectDiscussionModel -v`
Expected: FAIL with `ImportError: cannot import name 'ProjectDiscussion'`

- [ ] **Step 3: Add ProjectDiscussion model**

Edit `core/models.py` — find the `Task` related models region and add this AFTER `TaskWatcher` (but before `TaskChecklist` is fine, or place it near `Project`). A reasonable place is right after the `Project` class. Search for `class Project(models.Model):` and add AFTER the whole Project class and its methods:

```python
class ProjectDiscussion(models.Model):
    """
    A threaded conversation at the project level. Can link to multiple tasks.
    Use for topics that span multiple tasks or are project-wide.
    """
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='project_discussions',
    )
    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='discussions',
    )
    title = models.CharField(max_length=200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_discussions',
    )
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_discussions',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project Discussion'
        verbose_name_plural = 'Project Discussions'

    def __str__(self):
        return f"{self.title} ({self.project.name})"

    def save(self, *args, **kwargs):
        """Inherit organization from project if not set."""
        if not self.organization_id and self.project_id:
            self.organization = self.project.organization
        super().save(*args, **kwargs)
```

- [ ] **Step 4: Create and apply migration**

Run: `python manage.py makemigrations core --name project_discussions`
Then: `python manage.py migrate core`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestProjectDiscussionModel -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_project_discussions.py
git commit -m "feat(discussions): add ProjectDiscussion model"
```

---

## Task 2: Create ProjectDiscussionMessage model

**Files:**
- Modify: `core/models.py`
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestProjectDiscussionMessageModel:
    """Tests for the ProjectDiscussionMessage model."""

    def _make_discussion(self, user, org):
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(
            organization=org, name='P', owner=user,
        )
        discussion = ProjectDiscussion.objects.create(
            organization=org, project=project, title='T', created_by=user,
        )
        return discussion

    def test_create_message(self, user_alpha_owner, org_alpha):
        """Message created with author, content, defaults."""
        from core.models import ProjectDiscussionMessage

        discussion = self._make_discussion(user_alpha_owner, org_alpha)
        msg = ProjectDiscussionMessage.objects.create(
            discussion=discussion,
            author=user_alpha_owner,
            content='First post',
        )
        assert msg.discussion == discussion
        assert msg.author == user_alpha_owner
        assert msg.content == 'First post'
        assert msg.parent is None
        assert msg.is_decision is False
        assert msg.decision_marked_by is None
        assert msg.decision_marked_at is None

    def test_threaded_reply(self, user_alpha_owner, org_alpha):
        """parent FK creates threaded replies."""
        from core.models import ProjectDiscussionMessage

        discussion = self._make_discussion(user_alpha_owner, org_alpha)
        root = ProjectDiscussionMessage.objects.create(
            discussion=discussion, author=user_alpha_owner, content='Root',
        )
        reply = ProjectDiscussionMessage.objects.create(
            discussion=discussion,
            author=user_alpha_owner,
            content='Reply',
            parent=root,
        )
        assert reply.parent == root
        assert list(root.replies.all()) == [reply]

    def test_link_tasks(self, user_alpha_owner, org_alpha):
        """Message can be linked to multiple tasks via M2M."""
        from core.models import Project, Task, ProjectDiscussionMessage

        discussion = self._make_discussion(user_alpha_owner, org_alpha)
        project = discussion.project
        task_a = Task.objects.create(project=project, title='A', created_by=user_alpha_owner)
        task_b = Task.objects.create(project=project, title='B', created_by=user_alpha_owner)

        msg = ProjectDiscussionMessage.objects.create(
            discussion=discussion, author=user_alpha_owner, content='Multi',
        )
        msg.linked_tasks.set([task_a, task_b])

        assert msg.linked_tasks.count() == 2
        assert task_a in msg.linked_tasks.all()

    def test_mark_as_decision(self, user_alpha_owner, org_alpha):
        """Decision fields can be set together."""
        from core.models import ProjectDiscussionMessage

        discussion = self._make_discussion(user_alpha_owner, org_alpha)
        msg = ProjectDiscussionMessage.objects.create(
            discussion=discussion, author=user_alpha_owner, content='Decide',
        )

        msg.is_decision = True
        msg.decision_marked_by = user_alpha_owner
        msg.decision_marked_at = timezone.now()
        msg.save()

        msg.refresh_from_db()
        assert msg.is_decision is True
        assert msg.decision_marked_by == user_alpha_owner
        assert msg.decision_marked_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_discussions.py::TestProjectDiscussionMessageModel -v`
Expected: FAIL with `ImportError: cannot import name 'ProjectDiscussionMessage'`

- [ ] **Step 3: Add ProjectDiscussionMessage model**

Edit `core/models.py` — add this model immediately AFTER `ProjectDiscussion`:

```python
class ProjectDiscussionMessage(models.Model):
    """
    A message in a ProjectDiscussion thread. Supports threading via parent FK,
    @mentions, task linking, and decision-marking.
    """
    discussion = models.ForeignKey(
        ProjectDiscussion,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='discussion_messages',
    )
    content = models.TextField()
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies',
    )
    mentioned_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='discussion_mentions',
    )
    linked_tasks = models.ManyToManyField(
        'Task',
        blank=True,
        related_name='linked_discussion_messages',
    )

    # Decision marking (mirrors TaskComment)
    is_decision = models.BooleanField(
        default=False,
        help_text='This message captures a decision made by the team',
    )
    decision_marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='discussion_decisions_marked',
    )
    decision_marked_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Discussion Message'
        verbose_name_plural = 'Discussion Messages'

    def __str__(self):
        author_name = self.author.username if self.author else '<deleted>'
        return f"{author_name}: {self.content[:40]}"
```

- [ ] **Step 4: Create and apply migration**

Run: `python manage.py makemigrations core`
Then: `python manage.py migrate core`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestProjectDiscussionMessageModel -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_project_discussions.py
git commit -m "feat(discussions): add ProjectDiscussionMessage model"
```

---

## Task 3: Discussions list view + template

**Files:**
- Modify: `core/views.py` (add view)
- Modify: `core/urls.py` (add URL)
- Create: `templates/core/comms/discussion_list.html`
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.django_db
class TestDiscussionListView:
    """Tests for the discussion list view."""

    def _setup(self, user, org):
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(
            organization=org, name='P', owner=user,
        )
        open_disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='Open one', created_by=user,
        )
        resolved_disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='Resolved one',
            created_by=user, is_resolved=True,
        )
        return project, open_disc, resolved_disc

    def test_list_view_renders(self, client, user_alpha_owner, org_alpha):
        """GET renders the list of discussions for a project."""
        project, open_disc, resolved_disc = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('discussion_list', args=[project.pk]))

        assert response.status_code == 200
        assert 'Open one' in response.content.decode()
        assert 'Resolved one' in response.content.decode()

    def test_list_view_denies_non_members(
        self, client, user_alpha_owner, user_beta_owner, org_alpha
    ):
        """Non-project-members cannot view the list."""
        project, _, _ = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.get(reverse('discussion_list', args=[project.pk]))

        assert response.status_code in (302, 403)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_discussions.py::TestDiscussionListView -v`
Expected: FAIL with NoReverseMatch

- [ ] **Step 3: Add the view in core/views.py**

Add this view after `project_detail` (around line 2753):

```python
@login_required
def discussion_list(request, project_pk):
    """List all discussions for a project."""
    from .models import Project, ProjectDiscussion

    org = get_org(request)
    queryset = Project.objects.all()
    if org:
        queryset = queryset.filter(organization=org)
    project = get_object_or_404(queryset, pk=project_pk)

    # Access control
    if project.owner != request.user and request.user not in project.members.all():
        return redirect('project_list')

    discussions = project.discussions.select_related('created_by').prefetch_related(
        'messages'
    ).order_by('is_resolved', '-created_at')

    context = {
        'project': project,
        'discussions': discussions,
        'active_tab': 'discussions',
    }
    return render(request, 'core/comms/discussion_list.html', context)
```

- [ ] **Step 4: Add URL route**

Edit `core/urls.py` — find the project-related URLs and add after `project_detail`:

```python
    path('comms/projects/<int:project_pk>/discussions/', views.discussion_list, name='discussion_list'),
```

- [ ] **Step 5: Create template `templates/core/comms/discussion_list.html`**

```html
{% extends 'base.html' %}

{% block title %}Discussions - {{ project.name }}{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto px-4 py-6">
  <div class="mb-4 text-sm text-[#888]">
    <a href="{% url 'project_detail' pk=project.pk %}" class="hover:text-[#c9a227]">{{ project.name }}</a>
    <span class="mx-2">/</span>
    <span>Discussions</span>
  </div>

  {% include 'core/comms/_project_tabs.html' with project=project active_tab='discussions' %}

  <div class="flex items-center justify-between mb-4">
    <h1 class="text-xl font-semibold text-[#eee]">Discussions</h1>
    <a href="{% url 'discussion_create' project.pk %}"
       class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
      + New Discussion
    </a>
  </div>

  {% if discussions %}
    <div class="space-y-3">
      {% for d in discussions %}
        <a href="{% url 'discussion_detail' project.pk d.pk %}"
           class="block bg-[#1a1a1a] border border-[#333] rounded-lg p-4 hover:border-[#c9a227]/30 transition-colors
                  {% if d.is_resolved %}opacity-60{% endif %}">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <h3 class="text-[#eee] font-medium">
                {% if d.is_resolved %}<span class="text-[#4ade80] mr-1">&#10003;</span>{% endif %}
                {{ d.title }}
              </h3>
              <p class="text-xs text-[#888] mt-1">
                Started by {{ d.created_by.display_name|default:d.created_by.username }} &middot;
                {{ d.messages.count }} message{{ d.messages.count|pluralize }} &middot;
                {{ d.created_at|timesince }} ago
              </p>
            </div>
            {% if d.is_resolved %}
              <span class="text-xs text-[#4ade80]">Resolved</span>
            {% endif %}
          </div>
        </a>
      {% endfor %}
    </div>
  {% else %}
    <div class="bg-[#1a1a1a] border border-[#333] rounded-lg p-8 text-center">
      <p class="text-[#888] mb-3">No discussions yet.</p>
      <p class="text-sm text-[#666]">Start a discussion to talk about things that span multiple tasks.</p>
    </div>
  {% endif %}
</div>
{% endblock %}
```

Note: This references a `_project_tabs.html` partial and `discussion_create` / `discussion_detail` URLs that we'll create in later tasks. The template will fail to render until those exist, but the view test doesn't actually render the template content — it just checks status code and basic title presence via includes. We need to create the tabs partial NOW so this doesn't break.

- [ ] **Step 6: Create tabs partial `templates/core/comms/_project_tabs.html`**

```html
<div class="flex border-b border-[#333] mb-6">
  <a href="{% url 'project_detail' pk=project.pk %}"
     class="px-4 py-2 text-sm {% if active_tab == 'tasks' %}text-[#c9a227] border-b-2 border-[#c9a227] font-semibold{% else %}text-[#888] hover:text-[#eee]{% endif %}">
    Tasks
  </a>
  <a href="{% url 'discussion_list' project.pk %}"
     class="px-4 py-2 text-sm {% if active_tab == 'discussions' %}text-[#c9a227] border-b-2 border-[#c9a227] font-semibold{% else %}text-[#888] hover:text-[#eee]{% endif %}">
    Discussions
  </a>
  <a href="{% url 'decisions_tab' project.pk %}"
     class="px-4 py-2 text-sm {% if active_tab == 'decisions' %}text-[#c9a227] border-b-2 border-[#c9a227] font-semibold{% else %}text-[#888] hover:text-[#eee]{% endif %}">
    Decisions
  </a>
</div>
```

**IMPORTANT:** The `decisions_tab` URL is not yet wired. Create a temporary stub route that returns a 404 for now so the template won't crash:

Edit `core/urls.py` — add AFTER the discussion_list route:

```python
    path('comms/projects/<int:project_pk>/decisions/', views.decisions_tab, name='decisions_tab'),
```

And add a stub view at the top of `core/views.py` near the imports OR at the end — search for `def discussion_list` and add just after it:

```python
@login_required
def decisions_tab(request, project_pk):
    """Stub — replaced in Task 9."""
    from .models import Project
    org = get_org(request)
    queryset = Project.objects.all()
    if org:
        queryset = queryset.filter(organization=org)
    project = get_object_or_404(queryset, pk=project_pk)
    if project.owner != request.user and request.user not in project.members.all():
        return redirect('project_list')
    return HttpResponse('Decisions tab — coming in Task 9', status=200)
```

Also add `discussion_create` and `discussion_detail` URL stubs — add these routes to urls.py after `discussion_list`:

```python
    path('comms/projects/<int:project_pk>/discussions/new/', views.discussion_create, name='discussion_create'),
    path('comms/projects/<int:project_pk>/discussions/<int:pk>/', views.discussion_detail, name='discussion_detail'),
```

And stub views (add after `decisions_tab` stub):

```python
@login_required
def discussion_create(request, project_pk):
    """Stub — replaced in Task 4."""
    return HttpResponse('New discussion form — coming in Task 4', status=200)


@login_required
def discussion_detail(request, project_pk, pk):
    """Stub — replaced in Task 5."""
    return HttpResponse('Discussion detail — coming in Task 5', status=200)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestDiscussionListView -v`
Expected: PASS (2 tests)

- [ ] **Step 8: Commit**

```bash
git add core/views.py core/urls.py templates/core/comms/
git commit -m "feat(discussions): add discussions list view with tabs nav"
```

---

## Task 4: Discussion create view

**Files:**
- Modify: `core/views.py` (replace `discussion_create` stub)
- Create: `templates/core/comms/discussion_create.html`
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestDiscussionCreateView:
    """Tests for creating new discussions."""

    def _project(self, user, org):
        from core.models import Project
        return Project.objects.create(organization=org, name='P', owner=user)

    def test_get_form(self, client, user_alpha_owner, org_alpha):
        """GET renders the new-discussion form."""
        project = self._project(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('discussion_create', args=[project.pk]))

        assert response.status_code == 200
        assert b'title' in response.content.lower()

    def test_post_creates_discussion(self, client, user_alpha_owner, org_alpha):
        """POST creates a ProjectDiscussion and redirects to it."""
        from core.models import ProjectDiscussion
        project = self._project(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('discussion_create', args=[project.pk]),
            {'title': 'New discussion topic'},
        )

        assert response.status_code == 302
        assert ProjectDiscussion.objects.filter(
            project=project, title='New discussion topic'
        ).exists()

    def test_post_empty_title_rejected(self, client, user_alpha_owner, org_alpha):
        """POST with empty title doesn't create a discussion."""
        from core.models import ProjectDiscussion
        project = self._project(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        client.post(reverse('discussion_create', args=[project.pk]), {'title': ''})

        assert not ProjectDiscussion.objects.filter(project=project).exists()

    def test_non_member_denied(self, client, user_alpha_owner, user_beta_owner, org_alpha):
        """Non-project-members cannot create discussions."""
        project = self._project(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.post(
            reverse('discussion_create', args=[project.pk]),
            {'title': 'Hack'},
        )

        assert response.status_code in (302, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_discussions.py::TestDiscussionCreateView -v`
Expected: FAIL (the stub returns 200 but does not create a discussion)

- [ ] **Step 3: Replace the `discussion_create` stub with real view**

In `core/views.py`, find the `discussion_create` stub and replace with:

```python
@login_required
def discussion_create(request, project_pk):
    """GET shows form, POST creates a new ProjectDiscussion."""
    from .models import Project, ProjectDiscussion

    org = get_org(request)
    queryset = Project.objects.all()
    if org:
        queryset = queryset.filter(organization=org)
    project = get_object_or_404(queryset, pk=project_pk)

    # Access control
    if project.owner != request.user and request.user not in project.members.all():
        return redirect('project_list')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        first_message = request.POST.get('content', '').strip()
        if title:
            discussion = ProjectDiscussion.objects.create(
                project=project,
                title=title,
                created_by=request.user,
            )
            # Optional first message
            if first_message:
                from .models import ProjectDiscussionMessage
                ProjectDiscussionMessage.objects.create(
                    discussion=discussion,
                    author=request.user,
                    content=first_message,
                )
            return redirect('discussion_detail', project_pk=project.pk, pk=discussion.pk)

    return render(request, 'core/comms/discussion_create.html', {
        'project': project,
        'active_tab': 'discussions',
    })
```

- [ ] **Step 4: Create template `templates/core/comms/discussion_create.html`**

```html
{% extends 'base.html' %}

{% block title %}New Discussion - {{ project.name }}{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto px-4 py-6">
  <div class="mb-4 text-sm text-[#888]">
    <a href="{% url 'project_detail' pk=project.pk %}" class="hover:text-[#c9a227]">{{ project.name }}</a>
    <span class="mx-2">/</span>
    <a href="{% url 'discussion_list' project.pk %}" class="hover:text-[#c9a227]">Discussions</a>
    <span class="mx-2">/</span>
    <span>New</span>
  </div>

  <h1 class="text-xl font-semibold text-[#eee] mb-5">New Discussion</h1>

  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div>
      <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Title</label>
      <input type="text" name="title" required maxlength="200" autofocus
             placeholder="What's the topic?"
             class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#eee] focus:border-[#c9a227] focus:outline-none">
    </div>
    <div>
      <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">First message (optional)</label>
      <textarea name="content" rows="4"
                placeholder="Start the conversation..."
                class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#ccc] focus:border-[#c9a227] focus:outline-none resize-none"></textarea>
    </div>
    <div class="flex items-center gap-3 pt-2">
      <button type="submit" class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
        Create Discussion
      </button>
      <a href="{% url 'discussion_list' project.pk %}" class="text-sm text-[#888] hover:text-[#eee]">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestDiscussionCreateView -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add core/views.py templates/core/comms/discussion_create.html tests/test_project_discussions.py
git commit -m "feat(discussions): add discussion create view and form"
```

---

## Task 5: Discussion detail view

**Files:**
- Modify: `core/views.py` (replace `discussion_detail` stub)
- Create: `templates/core/comms/discussion_detail.html`
- Create: `templates/core/partials/discussion_message.html`
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.django_db
class TestDiscussionDetailView:
    """Tests for the discussion detail/thread view."""

    def _setup(self, user, org):
        from core.models import Project, ProjectDiscussion, ProjectDiscussionMessage
        project = Project.objects.create(organization=org, name='P', owner=user)
        disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='Topic', created_by=user,
        )
        msg1 = ProjectDiscussionMessage.objects.create(
            discussion=disc, author=user, content='First reply',
        )
        return project, disc, msg1

    def test_detail_renders(self, client, user_alpha_owner, org_alpha):
        """GET renders discussion with its messages."""
        project, disc, msg = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('discussion_detail', args=[project.pk, disc.pk]))

        assert response.status_code == 200
        body = response.content.decode()
        assert 'Topic' in body
        assert 'First reply' in body

    def test_non_member_denied(self, client, user_alpha_owner, user_beta_owner, org_alpha):
        project, disc, _ = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.get(reverse('discussion_detail', args=[project.pk, disc.pk]))

        assert response.status_code in (302, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_discussions.py::TestDiscussionDetailView -v`
Expected: FAIL (stub returns 200 but doesn't render content)

- [ ] **Step 3: Replace `discussion_detail` stub**

Replace the stub in `core/views.py`:

```python
@login_required
def discussion_detail(request, project_pk, pk):
    """View a discussion thread with all messages."""
    from .models import Project, ProjectDiscussion

    org = get_org(request)
    queryset = Project.objects.all()
    if org:
        queryset = queryset.filter(organization=org)
    project = get_object_or_404(queryset, pk=project_pk)

    # Access control
    if project.owner != request.user and request.user not in project.members.all():
        return redirect('project_list')

    discussion = get_object_or_404(ProjectDiscussion, pk=pk, project=project)
    messages_qs = discussion.messages.select_related('author').prefetch_related(
        'mentioned_users', 'linked_tasks'
    )

    context = {
        'project': project,
        'discussion': discussion,
        'messages_list': messages_qs,
        'active_tab': 'discussions',
    }
    return render(request, 'core/comms/discussion_detail.html', context)
```

- [ ] **Step 4: Create template `templates/core/comms/discussion_detail.html`**

```html
{% extends 'base.html' %}

{% block title %}{{ discussion.title }} - {{ project.name }}{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto px-4 py-6">
  <div class="mb-4 text-sm text-[#888]">
    <a href="{% url 'project_detail' pk=project.pk %}" class="hover:text-[#c9a227]">{{ project.name }}</a>
    <span class="mx-2">/</span>
    <a href="{% url 'discussion_list' project.pk %}" class="hover:text-[#c9a227]">Discussions</a>
  </div>

  <!-- Discussion header -->
  <div class="flex items-start justify-between gap-4 mb-4">
    <h1 class="text-xl font-semibold text-[#eee] flex-1">
      {% if discussion.is_resolved %}<span class="text-[#4ade80] mr-1">&#10003;</span>{% endif %}
      {{ discussion.title }}
    </h1>
    <form method="post" action="{% url 'discussion_toggle_resolved' discussion.pk %}">
      {% csrf_token %}
      <button type="submit"
              class="px-3 py-1.5 text-sm rounded-md border
                     {% if discussion.is_resolved %}bg-[#1a2a0a] border-[#2a3a1a] text-[#4ade80]{% else %}bg-[#1a1a1a] border-[#333] text-[#888] hover:border-[#4ade80]/30 hover:text-[#4ade80]{% endif %}">
        {% if discussion.is_resolved %}Resolved &middot; Reopen{% else %}Mark Resolved{% endif %}
      </button>
    </form>
  </div>

  <div class="pb-4 mb-6 border-b border-[#333] text-xs text-[#666]">
    Started by {{ discussion.created_by.display_name|default:discussion.created_by.username }} &middot;
    {{ discussion.created_at|timesince }} ago
  </div>

  <!-- Messages -->
  <div id="discussion-messages" class="space-y-4 mb-6">
    {% for msg in messages_list %}
      {% include 'core/partials/discussion_message.html' with message=msg %}
    {% empty %}
      <p class="text-sm text-[#666] italic">No messages yet. Start the conversation below.</p>
    {% endfor %}
  </div>

  <!-- Reply form -->
  <form hx-post="{% url 'discussion_post_message' discussion.pk %}"
        hx-target="#discussion-messages"
        hx-swap="beforeend"
        hx-on::after-request="this.reset()"
        class="bg-[#1a1a1a] border border-[#333] rounded-lg p-3">
    {% csrf_token %}
    <textarea name="content" rows="3" required
              placeholder="Reply..."
              class="w-full bg-transparent text-[#ccc] placeholder-[#555] text-sm focus:outline-none resize-none"></textarea>
    <div class="flex items-center justify-end mt-2 pt-2 border-t border-[#2a2a2a]">
      <button type="submit" class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
        Reply
      </button>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Create partial `templates/core/partials/discussion_message.html`**

```html
<div id="disc-msg-{{ message.pk }}" class="flex gap-3 group">
  <!-- Avatar -->
  <div class="w-8 h-8 rounded-full bg-[#2a2a2a] flex items-center justify-center text-xs text-[#c9a227] flex-shrink-0">
    {{ message.author.display_name|default:message.author.username|slice:":1"|upper }}
  </div>

  <div class="flex-1 min-w-0">
    <!-- Author + timestamp + decision chip -->
    <div class="flex items-center gap-2 mb-1 flex-wrap">
      <span class="text-sm font-semibold text-[#c9a227]">
        {{ message.author.display_name|default:message.author.username }}
      </span>
      <span class="text-xs text-[#555]">{{ message.created_at|timesince }} ago</span>
      {% if message.is_decision %}
        <span class="px-1.5 py-0.5 text-[10px] uppercase tracking-wide bg-[#1a2a0a] text-[#4ade80] rounded border border-[#2a3a1a]">
          Decision
        </span>
      {% endif %}
    </div>

    <!-- Content (highlighted if decision) -->
    {% if message.is_decision %}
      <div class="mt-1 bg-[#1a2a0a] border border-[#2a3a1a] rounded px-3 py-2">
        <p class="text-xs uppercase tracking-wide text-[#4ade80] mb-1">Decision</p>
        <p class="text-sm text-[#ccc] whitespace-pre-wrap">{{ message.content }}</p>
      </div>
    {% else %}
      <p class="text-sm text-[#ccc] whitespace-pre-wrap">{{ message.content }}</p>
    {% endif %}

    <!-- Linked tasks -->
    {% if message.linked_tasks.exists %}
      <div class="mt-2 flex flex-wrap gap-1.5">
        {% for t in message.linked_tasks.all %}
          <a href="{% url 'task_detail' project_pk=message.discussion.project.pk pk=t.pk %}"
             class="inline-flex items-center gap-1 text-xs text-[#888] bg-[#0f0f0f] border border-[#333] rounded px-2 py-0.5 hover:border-[#c9a227]/30 hover:text-[#c9a227]">
            &#128203; {{ t.title|truncatechars:40 }}
          </a>
        {% endfor %}
      </div>
    {% endif %}

    <!-- Action row: mark decision -->
    <div class="flex items-center gap-3 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
      <button hx-post="{% url 'discussion_message_mark_decision' message.pk %}"
              hx-target="#disc-msg-{{ message.pk }}"
              hx-swap="outerHTML"
              class="text-xs text-[#555] hover:text-[#4ade80]">
        {% if message.is_decision %}Unmark decision{% else %}Mark as decision{% endif %}
      </button>
    </div>
  </div>
</div>
```

**NOTE:** This partial references URLs we'll wire in later tasks (`discussion_toggle_resolved`, `discussion_post_message`, `discussion_message_mark_decision`). Add stub URL routes now in `core/urls.py` to avoid `NoReverseMatch`:

```python
    path('discussions/<int:pk>/toggle-resolved/', views.discussion_toggle_resolved, name='discussion_toggle_resolved'),
    path('discussions/<int:pk>/messages/post/', views.discussion_post_message, name='discussion_post_message'),
    path('discussion-messages/<int:pk>/mark-decision/', views.discussion_message_mark_decision, name='discussion_message_mark_decision'),
```

And add stub views in `core/views.py`:

```python
@login_required
@require_POST
def discussion_toggle_resolved(request, pk):
    """Stub — replaced in Task 7."""
    return HttpResponse('Stub', status=200)


@login_required
@require_POST
def discussion_post_message(request, pk):
    """Stub — replaced in Task 6."""
    return HttpResponse('Stub', status=200)


@login_required
@require_POST
def discussion_message_mark_decision(request, pk):
    """Stub — replaced in Task 8."""
    return HttpResponse('Stub', status=200)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestDiscussionDetailView -v`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add core/views.py core/urls.py templates/core/comms/discussion_detail.html templates/core/partials/discussion_message.html tests/test_project_discussions.py
git commit -m "feat(discussions): add discussion detail view with message thread"
```

---

## Task 6: Post discussion message endpoint

**Files:**
- Modify: `core/views.py` (replace `discussion_post_message` stub)
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestDiscussionPostMessage:
    """Tests for posting messages to a discussion."""

    def _setup(self, user, org):
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(organization=org, name='P', owner=user)
        disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='T', created_by=user,
        )
        return project, disc

    def test_post_creates_message(self, client, user_alpha_owner, org_alpha):
        """POST creates a ProjectDiscussionMessage."""
        from core.models import ProjectDiscussionMessage

        _, disc = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('discussion_post_message', args=[disc.pk]),
            {'content': 'Hello world'},
        )

        assert response.status_code in (200, 302)
        assert ProjectDiscussionMessage.objects.filter(
            discussion=disc, content='Hello world'
        ).exists()

    def test_post_empty_rejected(self, client, user_alpha_owner, org_alpha):
        """Empty content is rejected."""
        from core.models import ProjectDiscussionMessage

        _, disc = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        client.post(
            reverse('discussion_post_message', args=[disc.pk]),
            {'content': ''},
        )

        assert not ProjectDiscussionMessage.objects.filter(discussion=disc).exists()

    def test_htmx_returns_partial(self, client, user_alpha_owner, org_alpha):
        """HTMX requests get a message partial back."""
        _, disc = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('discussion_post_message', args=[disc.pk]),
            {'content': 'Hi'},
            HTTP_HX_REQUEST='true',
        )

        assert response.status_code == 200
        assert b'Hi' in response.content

    def test_non_member_denied(
        self, client, user_alpha_owner, user_beta_owner, org_alpha
    ):
        """Non-project-members cannot post messages."""
        from core.models import ProjectDiscussionMessage

        _, disc = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.post(
            reverse('discussion_post_message', args=[disc.pk]),
            {'content': 'Hack'},
        )

        assert response.status_code == 403
        assert not ProjectDiscussionMessage.objects.filter(discussion=disc).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_discussions.py::TestDiscussionPostMessage -v`
Expected: FAIL (stub doesn't create messages)

- [ ] **Step 3: Replace the `discussion_post_message` stub**

In `core/views.py`:

```python
@login_required
@require_POST
def discussion_post_message(request, pk):
    """Add a message to a discussion. Handles @mentions and optional task linking."""
    from .models import ProjectDiscussion, ProjectDiscussionMessage, Task
    from accounts.models import User
    import re

    discussion = get_object_or_404(ProjectDiscussion, pk=pk)
    project = discussion.project

    # Access control
    if project.owner != request.user and request.user not in project.members.all():
        return HttpResponse('Access denied', status=403)

    content = request.POST.get('content', '').strip()
    if not content:
        if request.headers.get('HX-Request'):
            return HttpResponse('', status=204)
        return redirect('discussion_detail', project_pk=project.pk, pk=discussion.pk)

    parent_id = request.POST.get('parent_id')
    parent = None
    if parent_id:
        try:
            parent = ProjectDiscussionMessage.objects.get(pk=parent_id, discussion=discussion)
        except ProjectDiscussionMessage.DoesNotExist:
            pass

    msg = ProjectDiscussionMessage.objects.create(
        discussion=discussion,
        author=request.user,
        content=content,
        parent=parent,
    )

    # Parse @mentions
    mention_tokens = re.findall(r'@(\w+(?:\s+\w+)?)', content)
    if mention_tokens:
        mentioned_users = set()
        for token in mention_tokens:
            matches = User.objects.filter(
                models.Q(display_name__iexact=token) |
                models.Q(first_name__iexact=token) |
                models.Q(username__iexact=token)
            )
            mentioned_users.update(matches)
        if mentioned_users:
            msg.mentioned_users.set(mentioned_users)

    # Parse linked_tasks from form (comma-separated task IDs)
    task_ids_raw = request.POST.get('linked_task_ids', '').strip()
    if task_ids_raw:
        try:
            task_ids = [int(x) for x in task_ids_raw.split(',') if x.strip().isdigit()]
            tasks_to_link = Task.objects.filter(pk__in=task_ids, project=project)
            msg.linked_tasks.set(tasks_to_link)
        except (ValueError, TypeError):
            pass

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/discussion_message.html', {
            'message': msg,
        })

    return redirect('discussion_detail', project_pk=project.pk, pk=discussion.pk)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestDiscussionPostMessage -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_project_discussions.py
git commit -m "feat(discussions): add post-message endpoint with @mentions and task linking"
```

---

## Task 7: Toggle discussion resolved endpoint

**Files:**
- Modify: `core/views.py` (replace `discussion_toggle_resolved` stub)
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestDiscussionToggleResolved:
    """Tests for marking discussions as resolved/unresolved."""

    def _setup(self, user, org):
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(organization=org, name='P', owner=user)
        disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='T', created_by=user,
        )
        return project, disc

    def test_resolve(self, client, user_alpha_owner, org_alpha):
        """POST sets is_resolved=True with metadata."""
        from core.models import ProjectDiscussion

        _, disc = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('discussion_toggle_resolved', args=[disc.pk]),
        )

        assert response.status_code in (200, 302)
        disc.refresh_from_db()
        assert disc.is_resolved is True
        assert disc.resolved_by == user_alpha_owner
        assert disc.resolved_at is not None

    def test_unresolve(self, client, user_alpha_owner, org_alpha):
        """POST again clears resolved state."""
        from core.models import ProjectDiscussion

        _, disc = self._setup(user_alpha_owner, org_alpha)
        disc.is_resolved = True
        disc.resolved_by = user_alpha_owner
        disc.resolved_at = timezone.now()
        disc.save()

        client.force_login(user_alpha_owner)
        client.post(reverse('discussion_toggle_resolved', args=[disc.pk]))

        disc.refresh_from_db()
        assert disc.is_resolved is False
        assert disc.resolved_by is None
        assert disc.resolved_at is None

    def test_non_member_denied(self, client, user_alpha_owner, user_beta_owner, org_alpha):
        _, disc = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.post(reverse('discussion_toggle_resolved', args=[disc.pk]))

        assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_discussions.py::TestDiscussionToggleResolved -v`
Expected: FAIL (stub doesn't change state)

- [ ] **Step 3: Replace the `discussion_toggle_resolved` stub**

```python
@login_required
@require_POST
def discussion_toggle_resolved(request, pk):
    """Toggle a discussion's is_resolved flag."""
    from .models import ProjectDiscussion

    discussion = get_object_or_404(ProjectDiscussion, pk=pk)
    project = discussion.project

    # Access control
    if project.owner != request.user and request.user not in project.members.all():
        return HttpResponse('Access denied', status=403)

    if discussion.is_resolved:
        discussion.is_resolved = False
        discussion.resolved_by = None
        discussion.resolved_at = None
    else:
        discussion.is_resolved = True
        discussion.resolved_by = request.user
        discussion.resolved_at = timezone.now()
    discussion.save(update_fields=['is_resolved', 'resolved_by', 'resolved_at', 'updated_at'])

    return redirect('discussion_detail', project_pk=project.pk, pk=discussion.pk)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestDiscussionToggleResolved -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_project_discussions.py
git commit -m "feat(discussions): add toggle-resolved endpoint"
```

---

## Task 8: Mark discussion message as decision endpoint

**Files:**
- Modify: `core/views.py` (replace `discussion_message_mark_decision` stub)
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestDiscussionMessageMarkDecision:
    """Tests for marking discussion messages as decisions."""

    def _setup(self, user, org):
        from core.models import Project, ProjectDiscussion, ProjectDiscussionMessage
        project = Project.objects.create(organization=org, name='P', owner=user)
        disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='T', created_by=user,
        )
        msg = ProjectDiscussionMessage.objects.create(
            discussion=disc, author=user, content='Text',
        )
        return project, disc, msg

    def test_mark(self, client, user_alpha_owner, org_alpha):
        """POST marks message as decision."""
        _, _, msg = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('discussion_message_mark_decision', args=[msg.pk]),
        )

        assert response.status_code in (200, 302)
        msg.refresh_from_db()
        assert msg.is_decision is True
        assert msg.decision_marked_by == user_alpha_owner
        assert msg.decision_marked_at is not None

    def test_unmark(self, client, user_alpha_owner, org_alpha):
        """POST again clears decision state."""
        _, _, msg = self._setup(user_alpha_owner, org_alpha)
        msg.is_decision = True
        msg.decision_marked_by = user_alpha_owner
        msg.decision_marked_at = timezone.now()
        msg.save()

        client.force_login(user_alpha_owner)
        client.post(reverse('discussion_message_mark_decision', args=[msg.pk]))

        msg.refresh_from_db()
        assert msg.is_decision is False
        assert msg.decision_marked_by is None
        assert msg.decision_marked_at is None

    def test_non_member_denied(self, client, user_alpha_owner, user_beta_owner, org_alpha):
        _, _, msg = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.post(
            reverse('discussion_message_mark_decision', args=[msg.pk]),
        )

        assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_discussions.py::TestDiscussionMessageMarkDecision -v`
Expected: FAIL (stub doesn't change state)

- [ ] **Step 3: Replace the `discussion_message_mark_decision` stub**

```python
@login_required
@require_POST
def discussion_message_mark_decision(request, pk):
    """Toggle is_decision flag on a ProjectDiscussionMessage."""
    from .models import ProjectDiscussionMessage

    msg = get_object_or_404(ProjectDiscussionMessage, pk=pk)
    project = msg.discussion.project

    # Access control
    if project.owner != request.user and request.user not in project.members.all():
        return HttpResponse('Access denied', status=403)

    if msg.is_decision:
        msg.is_decision = False
        msg.decision_marked_by = None
        msg.decision_marked_at = None
    else:
        msg.is_decision = True
        msg.decision_marked_by = request.user
        msg.decision_marked_at = timezone.now()
    msg.save(update_fields=['is_decision', 'decision_marked_by', 'decision_marked_at', 'updated_at'])

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/discussion_message.html', {'message': msg})

    return redirect('discussion_detail', project_pk=project.pk, pk=msg.discussion.pk)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestDiscussionMessageMarkDecision -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_project_discussions.py
git commit -m "feat(discussions): add mark-decision endpoint for discussion messages"
```

---

## Task 9: Decisions tab view

**Files:**
- Modify: `core/views.py` (replace `decisions_tab` stub)
- Create: `templates/core/comms/decisions_tab.html`
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestDecisionsTab:
    """Tests for the aggregated decisions tab."""

    def _setup_decisions(self, user, org):
        from core.models import (
            Project, Task, TaskComment, ProjectDiscussion, ProjectDiscussionMessage,
        )
        project = Project.objects.create(organization=org, name='P', owner=user)
        task = Task.objects.create(project=project, title='T', created_by=user)
        # Task comment decision
        tc = TaskComment.objects.create(task=task, author=user, content='Task decision')
        tc.is_decision = True
        tc.decision_marked_by = user
        tc.decision_marked_at = timezone.now()
        tc.save()
        # Discussion message decision
        disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='D', created_by=user,
        )
        dm = ProjectDiscussionMessage.objects.create(
            discussion=disc, author=user, content='Disc decision',
        )
        dm.is_decision = True
        dm.decision_marked_by = user
        dm.decision_marked_at = timezone.now()
        dm.save()
        return project, tc, dm

    def test_tab_shows_both_sources(self, client, user_alpha_owner, org_alpha):
        """Decisions tab lists decisions from TaskComments AND discussion messages."""
        project, tc, dm = self._setup_decisions(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('decisions_tab', args=[project.pk]))

        assert response.status_code == 200
        body = response.content.decode()
        assert 'Task decision' in body
        assert 'Disc decision' in body

    def test_tab_excludes_non_decisions(self, client, user_alpha_owner, org_alpha):
        """Non-decision comments/messages don't appear."""
        from core.models import Project, Task, TaskComment
        project = Project.objects.create(organization=org_alpha, name='P', owner=user_alpha_owner)
        task = Task.objects.create(project=project, title='T', created_by=user_alpha_owner)
        TaskComment.objects.create(task=task, author=user_alpha_owner, content='Not a decision')
        client.force_login(user_alpha_owner)

        response = client.get(reverse('decisions_tab', args=[project.pk]))

        assert response.status_code == 200
        assert 'Not a decision' not in response.content.decode()

    def test_non_member_denied(self, client, user_alpha_owner, user_beta_owner, org_alpha):
        project, _, _ = self._setup_decisions(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.get(reverse('decisions_tab', args=[project.pk]))

        assert response.status_code in (302, 403)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_discussions.py::TestDecisionsTab -v`
Expected: FAIL (stub returns text, doesn't render decisions)

- [ ] **Step 3: Replace the `decisions_tab` stub**

```python
@login_required
def decisions_tab(request, project_pk):
    """Aggregated view of all decisions across task comments and discussion messages."""
    from .models import Project, TaskComment, ProjectDiscussionMessage

    org = get_org(request)
    queryset = Project.objects.all()
    if org:
        queryset = queryset.filter(organization=org)
    project = get_object_or_404(queryset, pk=project_pk)

    # Access control
    if project.owner != request.user and request.user not in project.members.all():
        return redirect('project_list')

    # Decisions from TaskComments
    task_decisions = TaskComment.objects.filter(
        task__project=project,
        is_decision=True,
    ).select_related('author', 'task', 'decision_marked_by').order_by('-decision_marked_at')

    # Decisions from ProjectDiscussionMessages
    discussion_decisions = ProjectDiscussionMessage.objects.filter(
        discussion__project=project,
        is_decision=True,
    ).select_related('author', 'discussion', 'decision_marked_by').order_by('-decision_marked_at')

    # Merge into one timeline
    combined = []
    for c in task_decisions:
        combined.append({
            'content': c.content,
            'marked_at': c.decision_marked_at,
            'marked_by': c.decision_marked_by,
            'author': c.author,
            'source_label': f'Task: {c.task.title}',
            'source_url': reverse('task_detail', kwargs={
                'project_pk': project.pk, 'pk': c.task.pk,
            }),
        })
    for m in discussion_decisions:
        combined.append({
            'content': m.content,
            'marked_at': m.decision_marked_at,
            'marked_by': m.decision_marked_by,
            'author': m.author,
            'source_label': f'Discussion: {m.discussion.title}',
            'source_url': reverse('discussion_detail', kwargs={
                'project_pk': project.pk, 'pk': m.discussion.pk,
            }),
        })

    combined.sort(key=lambda x: x['marked_at'] or timezone.now(), reverse=True)

    context = {
        'project': project,
        'decisions': combined,
        'active_tab': 'decisions',
    }
    return render(request, 'core/comms/decisions_tab.html', context)
```

- [ ] **Step 4: Create template `templates/core/comms/decisions_tab.html`**

```html
{% extends 'base.html' %}

{% block title %}Decisions - {{ project.name }}{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto px-4 py-6">
  <div class="mb-4 text-sm text-[#888]">
    <a href="{% url 'project_detail' pk=project.pk %}" class="hover:text-[#c9a227]">{{ project.name }}</a>
    <span class="mx-2">/</span>
    <span>Decisions</span>
  </div>

  {% include 'core/comms/_project_tabs.html' with project=project active_tab='decisions' %}

  <h1 class="text-xl font-semibold text-[#eee] mb-4">Decisions</h1>

  {% if decisions %}
    <div class="space-y-3">
      {% for d in decisions %}
        <div class="bg-[#1a2a0a] border border-[#2a3a1a] rounded-lg p-4">
          <p class="text-sm text-[#ccc] whitespace-pre-wrap mb-2">{{ d.content }}</p>
          <div class="flex flex-wrap items-center gap-3 text-xs text-[#666]">
            <span class="text-[#c9a227]">{{ d.author.display_name|default:d.author.username }}</span>
            {% if d.marked_at %}
              <span>{{ d.marked_at|timesince }} ago</span>
            {% endif %}
            <a href="{{ d.source_url }}" class="text-[#888] hover:text-[#c9a227] ml-auto">
              in: {{ d.source_label }}
            </a>
          </div>
        </div>
      {% endfor %}
    </div>
  {% else %}
    <div class="bg-[#1a1a1a] border border-[#333] rounded-lg p-8 text-center">
      <p class="text-[#888] mb-2">No decisions yet.</p>
      <p class="text-sm text-[#666]">Mark any task comment or discussion message as a decision to see it here.</p>
    </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_discussions.py::TestDecisionsTab -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add core/views.py templates/core/comms/decisions_tab.html tests/test_project_discussions.py
git commit -m "feat(discussions): add aggregated decisions tab"
```

---

## Task 10: Add tabs navigation to project_detail page

**Files:**
- Modify: `templates/core/comms/project_detail.html`
- Test: `tests/test_project_discussions.py` (append)

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.django_db
class TestProjectDetailTabs:
    """Verify project_detail renders the tabs navigation."""

    def test_project_detail_shows_tabs(self, client, user_alpha_owner, org_alpha):
        """Project detail page includes links to Discussions and Decisions tabs."""
        from core.models import Project
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        client.force_login(user_alpha_owner)

        response = client.get(reverse('project_detail', args=[project.pk]))

        assert response.status_code == 200
        body = response.content.decode()
        assert reverse('discussion_list', args=[project.pk]) in body
        assert reverse('decisions_tab', args=[project.pk]) in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_discussions.py::TestProjectDetailTabs -v`
Expected: FAIL (tab links not yet in template)

- [ ] **Step 3: Update project_detail.html to include the tabs partial**

Read `templates/core/comms/project_detail.html`. Find the section just AFTER the project header block (title, status chip, description) and BEFORE the main task board / content area. This is typically after the `</div>` closing the header.

Add the tabs partial include. Insert this line in the appropriate spot:

```html
{% include 'core/comms/_project_tabs.html' with project=project active_tab='tasks' %}
```

The tabs partial is already styled and was created in Task 3.

**Guidance:** Look for a natural break point in the template — e.g., right after the project header card and before the task columns/board. If the template has a wrapper `<div class="max-w-6xl mx-auto">` near the top, the tabs should go right at the top of that content area, after the header.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_project_discussions.py::TestProjectDetailTabs -v`
Expected: PASS

- [ ] **Step 5: Run full Phase 2 test suite + existing suite**

```bash
pytest tests/test_project_discussions.py -v 2>&1 | tail -40
pytest tests/ -x 2>&1 | tail -10
```

Expected: All Phase 2 tests pass (~25 tests). Existing suite passes (606 prior + ~25 new = ~631).

- [ ] **Step 6: Commit**

```bash
git add templates/core/comms/project_detail.html tests/test_project_discussions.py
git commit -m "feat(discussions): add tabs navigation to project detail page"
```

---

## Final Verification

- [ ] **Step 1: Run full suite**

Run: `pytest tests/ 2>&1 | tail -10`
Expected: All tests pass, no regressions.

- [ ] **Step 2: Manual smoke test**

Start dev server: `python manage.py runserver`

Test in browser:
1. Open a project detail page → see Tasks | Discussions | Decisions tabs
2. Click Discussions → see empty list with "+ New Discussion" button
3. Create a discussion → redirects to detail view
4. Post a reply → appears immediately via HTMX
5. Click "Mark Resolved" → button changes to "Reopen"
6. Hover over a message → "Mark as decision" appears, click it → green badge + highlight
7. Click Decisions tab → see the decision with deep link back to its source

---

## Deployment Notes

- Migrations are additive (no data loss)
- Deploy migrations first, then code
- No new environment variables
- No background jobs required for Phase 2
