# Phase 3: Project Templates + PCO-Linked Recurrence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add ProjectTemplate (blueprints that spawn a new project with N pre-defined tasks on an event date) AND add PCO-service-linked recurrence to the existing TaskTemplate (auto-generate tasks tied to actual PCO service plan dates).

**Architecture:** Two independent features shipped together.
1. **ProjectTemplate**: New models (`ProjectTemplate` + `ProjectTemplateTask`) with a "create project from template" flow that takes an event date and produces a real `Project` + `Task` records with relative due dates.
2. **PCO recurrence**: New `recurrence_type='pco_service'` on existing `TaskTemplate` + two new fields (`pco_service_type_id`, `pco_days_before_service`). `get_next_occurrences` queries PCO for upcoming service plan dates.

**Tech Stack:** Django 5.x, PostgreSQL, pytest, HTMX, Tailwind, existing PCO API in `core/planning_center.py`.

**Related Spec:** `docs/superpowers/specs/2026-04-04-todoist-replacement-design.md` (Phase 3 + part of Phase 4)

---

## File Structure

**Create:**
- `core/migrations/00XX_project_templates.py` — new models
- `core/migrations/00YY_tasktemplate_pco_fields.py` — new fields on existing TaskTemplate
- `templates/core/comms/project_template_list.html`
- `templates/core/comms/project_template_create.html`
- `templates/core/comms/project_template_detail.html`
- `templates/core/comms/project_template_apply.html` — form to spawn project from template
- `tests/test_project_templates.py`
- `tests/test_pco_recurrence.py`

**Modify:**
- `core/models.py` — add ProjectTemplate + ProjectTemplateTask models, add PCO fields + branch to TaskTemplate
- `core/views.py` — add 6 ProjectTemplate views, update template_create/template_detail to handle PCO fields
- `core/urls.py` — wire new routes
- `templates/core/comms/hub.html` — add "Project Templates" nav card
- `templates/core/comms/template_create.html` — add PCO fields to TaskTemplate form
- `templates/core/comms/template_detail.html` — show PCO config

---

## Task 1: ProjectTemplate + ProjectTemplateTask models

**Files:**
- Modify: `core/models.py`
- Test: `tests/test_project_templates.py` (new file)

- [ ] **Step 1: Create test file**

Create `tests/test_project_templates.py`:

```python
"""Tests for Phase 3: Project Templates."""
import pytest
from django.utils import timezone
from django.urls import reverse


@pytest.mark.django_db
class TestProjectTemplateModel:
    """Tests for ProjectTemplate + ProjectTemplateTask models."""

    def test_create_project_template(self, user_alpha_owner, org_alpha):
        """ProjectTemplate created with required fields."""
        from core.models import ProjectTemplate
        t = ProjectTemplate.objects.create(
            organization=org_alpha,
            name='Sunday Service Prep',
            description='Standard tasks for a Sunday service',
            created_by=user_alpha_owner,
        )
        assert t.organization == org_alpha
        assert t.name == 'Sunday Service Prep'
        assert t.is_shared is False
        assert t.created_at is not None

    def test_template_task_relative_due(self, user_alpha_owner, org_alpha):
        """ProjectTemplateTask stores relative offset and ordering."""
        from core.models import ProjectTemplate, ProjectTemplateTask
        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='T', created_by=user_alpha_owner,
        )
        tt = ProjectTemplateTask.objects.create(
            template=t,
            title='Stage setup',
            description='Set up the stage',
            relative_due_offset_days=-3,
            role_placeholder='tech_lead',
            order=0,
            checklist_items=['Monitors', 'Cables', 'Mics'],
        )
        assert tt.template == t
        assert tt.relative_due_offset_days == -3
        assert tt.role_placeholder == 'tech_lead'
        assert tt.checklist_items == ['Monitors', 'Cables', 'Mics']
        assert tt.order == 0

    def test_template_has_many_tasks(self, user_alpha_owner, org_alpha):
        """Template can have multiple ordered tasks."""
        from core.models import ProjectTemplate, ProjectTemplateTask
        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='T', created_by=user_alpha_owner,
        )
        ProjectTemplateTask.objects.create(
            template=t, title='A', relative_due_offset_days=-3, order=0,
        )
        ProjectTemplateTask.objects.create(
            template=t, title='B', relative_due_offset_days=-1, order=1,
        )
        assert t.template_tasks.count() == 2
        assert list(t.template_tasks.values_list('title', flat=True)) == ['A', 'B']
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateModel -v`
Expected: FAIL with `ImportError: cannot import name 'ProjectTemplate'`

- [ ] **Step 3: Add models to core/models.py**

Place these models after the `TaskTemplate` class (around line 3365, before the push notification section). Add:

```python
class ProjectTemplate(models.Model):
    """
    Blueprint for creating a new Project with pre-defined tasks.
    Distinct from TaskTemplate (recurring task generator).
    """
    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='project_templates',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    is_shared = models.BooleanField(
        default=False,
        help_text="Visible to all org members (vs private to creator)",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_project_templates',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Project Template'
        verbose_name_plural = 'Project Templates'

    def __str__(self):
        return self.name


class ProjectTemplateTask(models.Model):
    """
    A task inside a ProjectTemplate with a relative due-date offset
    from the event date.
    """
    template = models.ForeignKey(
        ProjectTemplate,
        on_delete=models.CASCADE,
        related_name='template_tasks',
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    role_placeholder = models.CharField(
        max_length=100,
        blank=True,
        help_text="Free-text role hint (e.g., 'tech_lead'); not auto-resolved in v1",
    )
    relative_due_offset_days = models.IntegerField(
        default=0,
        help_text="Days from event date. Negative = before, positive = after.",
    )
    priority = models.CharField(
        max_length=10,
        choices=Task.PRIORITY_CHOICES,
        default='medium',
    )
    checklist_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Checklist item titles to create with the task",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Project Template Task'
        verbose_name_plural = 'Project Template Tasks'

    def __str__(self):
        return f"{self.title} ({self.template.name})"
```

- [ ] **Step 4: Create migration**

Run: `python manage.py makemigrations core --name project_templates`
Then: `python manage.py migrate core`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateModel -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_project_templates.py
git commit -m "feat(templates): add ProjectTemplate and ProjectTemplateTask models"
```

---

## Task 2: apply_template helper function

**Files:**
- Modify: `core/models.py` (add method to ProjectTemplate)
- Test: `tests/test_project_templates.py` (append)

- [ ] **Step 1: Append failing test**

```python
@pytest.mark.django_db
class TestApplyTemplate:
    """Tests for creating a project from a template."""

    def test_apply_creates_project_with_tasks(self, user_alpha_owner, org_alpha):
        """apply() spawns a new Project and resolves relative dates."""
        from datetime import date, timedelta
        from core.models import ProjectTemplate, ProjectTemplateTask

        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='Easter', created_by=user_alpha_owner,
        )
        ProjectTemplateTask.objects.create(
            template=t, title='Stage', relative_due_offset_days=-3, order=0,
            checklist_items=['Monitors', 'Cables'],
        )
        ProjectTemplateTask.objects.create(
            template=t, title='Rehearsal', relative_due_offset_days=-1, order=1,
        )

        event_date = date(2026, 4, 5)
        project = t.apply(event_date=event_date, project_name='Easter 2026', user=user_alpha_owner)

        assert project.organization == org_alpha
        assert project.name == 'Easter 2026'
        assert project.owner == user_alpha_owner
        assert project.tasks.count() == 2

        stage = project.tasks.get(title='Stage')
        assert stage.due_date == date(2026, 4, 2)  # event_date - 3 days
        assert stage.checklists.count() == 2
        assert set(stage.checklists.values_list('title', flat=True)) == {'Monitors', 'Cables'}

        rehearsal = project.tasks.get(title='Rehearsal')
        assert rehearsal.due_date == date(2026, 4, 4)

    def test_apply_positive_offset(self, user_alpha_owner, org_alpha):
        """Positive offset creates task dated AFTER the event."""
        from datetime import date
        from core.models import ProjectTemplate, ProjectTemplateTask

        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='T', created_by=user_alpha_owner,
        )
        ProjectTemplateTask.objects.create(
            template=t, title='Debrief', relative_due_offset_days=1,
        )
        event = date(2026, 4, 5)
        project = t.apply(event_date=event, project_name='P', user=user_alpha_owner)
        assert project.tasks.get(title='Debrief').due_date == date(2026, 4, 6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_templates.py::TestApplyTemplate -v`
Expected: FAIL with `AttributeError: 'ProjectTemplate' object has no attribute 'apply'`

- [ ] **Step 3: Add apply() method to ProjectTemplate**

Append to the `ProjectTemplate` class in `core/models.py`:

```python
    def apply(self, event_date, project_name, user, project_description=''):
        """
        Create a new Project populated with tasks from this template.
        Each template task's due_date is event_date + relative_due_offset_days.
        """
        from datetime import timedelta

        project = Project.objects.create(
            organization=self.organization,
            name=project_name,
            description=project_description,
            owner=user,
            service_date=event_date if hasattr(Project, 'service_date') else None,
        )

        for tt in self.template_tasks.all():
            due_date = event_date + timedelta(days=tt.relative_due_offset_days)
            task = Task.objects.create(
                project=project,
                title=tt.title,
                description=tt.description,
                priority=tt.priority,
                due_date=due_date,
                created_by=user,
                order=tt.order,
            )
            for i, item_title in enumerate(tt.checklist_items):
                TaskChecklist.objects.create(
                    task=task, title=item_title, order=i,
                )

        return project
```

Note: The `service_date` kwarg uses a hasattr guard since not all Project instances may have that field. If the Project model has a `service_date` field, it gets set to the event date.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_project_templates.py::TestApplyTemplate -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_project_templates.py
git commit -m "feat(templates): add apply() method to create Project from template"
```

---

## Task 3: ProjectTemplate list view + nav entry

**Files:**
- Modify: `core/views.py` (add view)
- Modify: `core/urls.py` (add URL)
- Modify: `templates/core/comms/hub.html` (add nav card)
- Create: `templates/core/comms/project_template_list.html`
- Test: `tests/test_project_templates.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestProjectTemplateListView:
    """Tests for the ProjectTemplate list view."""

    def test_list_renders(self, client, user_alpha_owner, org_alpha):
        """GET shows template list."""
        from core.models import ProjectTemplate
        ProjectTemplate.objects.create(
            organization=org_alpha, name='Sunday Prep', created_by=user_alpha_owner,
        )
        client.force_login(user_alpha_owner)

        response = client.get(reverse('project_template_list'))

        assert response.status_code == 200
        assert 'Sunday Prep' in response.content.decode()

    def test_list_shows_only_own_org(self, client, user_alpha_owner, org_alpha, org_beta, user_beta_owner):
        """Templates from other orgs are not visible."""
        from core.models import ProjectTemplate
        ProjectTemplate.objects.create(
            organization=org_beta, name='Beta Template', created_by=user_beta_owner,
        )
        ProjectTemplate.objects.create(
            organization=org_alpha, name='Alpha Template', created_by=user_alpha_owner,
        )
        client.force_login(user_alpha_owner)

        response = client.get(reverse('project_template_list'))

        body = response.content.decode()
        assert 'Alpha Template' in body
        assert 'Beta Template' not in body

    def test_list_shows_shared_and_own(self, client, user_alpha_owner, user_alpha_member, org_alpha):
        """Member sees own templates + shared ones in their org."""
        from core.models import ProjectTemplate
        # Shared by owner
        ProjectTemplate.objects.create(
            organization=org_alpha, name='Shared',
            created_by=user_alpha_owner, is_shared=True,
        )
        # Private by owner — member should NOT see
        ProjectTemplate.objects.create(
            organization=org_alpha, name='Private owner',
            created_by=user_alpha_owner, is_shared=False,
        )
        # Member's own private
        ProjectTemplate.objects.create(
            organization=org_alpha, name='My private',
            created_by=user_alpha_member, is_shared=False,
        )
        client.force_login(user_alpha_member)

        response = client.get(reverse('project_template_list'))

        body = response.content.decode()
        assert 'Shared' in body
        assert 'My private' in body
        assert 'Private owner' not in body
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateListView -v`
Expected: FAIL with NoReverseMatch

- [ ] **Step 3: Add view in core/views.py**

Place after the `template_list` view (the existing TaskTemplate list view, around line 4330):

```python
@login_required
def project_template_list(request):
    """List ProjectTemplates the current user can see (own + shared in org)."""
    from .models import ProjectTemplate
    from django.db.models import Q

    org = get_org(request)
    queryset = ProjectTemplate.objects.filter(organization=org) if org else ProjectTemplate.objects.none()
    # Show: templates owned by user OR templates with is_shared=True
    queryset = queryset.filter(Q(created_by=request.user) | Q(is_shared=True))
    queryset = queryset.select_related('created_by').order_by('name')

    return render(request, 'core/comms/project_template_list.html', {
        'templates': queryset,
    })
```

- [ ] **Step 4: Add URL routes**

In `core/urls.py`, add alongside the existing template URLs:

```python
    path('project-templates/', views.project_template_list, name='project_template_list'),
    path('project-templates/new/', views.project_template_create, name='project_template_create'),
    path('project-templates/<int:pk>/', views.project_template_detail, name='project_template_detail'),
    path('project-templates/<int:pk>/delete/', views.project_template_delete, name='project_template_delete'),
    path('project-templates/<int:pk>/apply/', views.project_template_apply, name='project_template_apply'),
```

- [ ] **Step 5: Add stub views for the other 4 routes**

In `core/views.py` after `project_template_list`:

```python
@login_required
def project_template_create(request):
    """Stub — replaced in Task 4."""
    return HttpResponse('Create form — Task 4', status=200)


@login_required
def project_template_detail(request, pk):
    """Stub — replaced in Task 5."""
    return HttpResponse('Detail — Task 5', status=200)


@login_required
@require_POST
def project_template_delete(request, pk):
    """Stub — replaced in Task 6."""
    return HttpResponse('Delete — Task 6', status=200)


@login_required
def project_template_apply(request, pk):
    """Stub — replaced in Task 7."""
    return HttpResponse('Apply — Task 7', status=200)
```

- [ ] **Step 6: Create template `templates/core/comms/project_template_list.html`**

```html
{% extends 'base.html' %}

{% block title %}Project Templates{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto px-4 py-6">
  <div class="flex items-center justify-between mb-5">
    <div>
      <h1 class="text-xl font-semibold text-[#eee]">Project Templates</h1>
      <p class="text-sm text-[#888] mt-1">Reusable blueprints for creating projects with predefined tasks.</p>
    </div>
    <a href="{% url 'project_template_create' %}"
       class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
      + New Template
    </a>
  </div>

  {% if templates %}
    <div class="space-y-3">
      {% for t in templates %}
        <div class="bg-[#1a1a1a] border border-[#333] rounded-lg p-4 hover:border-[#c9a227]/30 transition-colors">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <a href="{% url 'project_template_detail' t.pk %}" class="block">
                <h3 class="text-[#eee] font-medium">{{ t.name }}</h3>
                {% if t.description %}
                  <p class="text-sm text-[#888] mt-1">{{ t.description|truncatechars:120 }}</p>
                {% endif %}
                <p class="text-xs text-[#666] mt-2">
                  {{ t.template_tasks.count }} task{{ t.template_tasks.count|pluralize }} &middot;
                  by {{ t.created_by.display_name|default:t.created_by.username }}
                  {% if t.is_shared %}
                    <span class="ml-2 px-1.5 py-0.5 text-[10px] bg-[#2a1a0a] text-[#c9a227] rounded">Shared</span>
                  {% endif %}
                </p>
              </a>
            </div>
            <a href="{% url 'project_template_apply' t.pk %}"
               class="px-3 py-1.5 text-sm bg-[#1a1a1a] border border-[#c9a227]/30 text-[#c9a227] rounded hover:bg-[#2a1a0a]">
              Use
            </a>
          </div>
        </div>
      {% endfor %}
    </div>
  {% else %}
    <div class="bg-[#1a1a1a] border border-[#333] rounded-lg p-8 text-center">
      <p class="text-[#888] mb-2">No project templates yet.</p>
      <p class="text-sm text-[#666]">Create a template to speed up setting up recurring event projects.</p>
    </div>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 7: Add nav link to hub**

Read `templates/core/comms/hub.html` and find where nav cards or links are listed. Add a new link/card to "Project Templates" pointing to `{% url 'project_template_list' %}`. Match the existing card styling.

**Guidance:** Search for an existing link like "My Tasks" or "Projects" in hub.html and add a similar entry near it.

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateListView -v`
Expected: PASS (3 tests)

- [ ] **Step 9: Commit**

```bash
git add core/views.py core/urls.py templates/core/comms/
git commit -m "feat(templates): add ProjectTemplate list view and hub nav link"
```

---

## Task 4: ProjectTemplate create view

**Files:**
- Modify: `core/views.py` (replace `project_template_create` stub)
- Create: `templates/core/comms/project_template_create.html`
- Test: `tests/test_project_templates.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestProjectTemplateCreateView:
    """Tests for creating a new ProjectTemplate."""

    def test_get_form(self, client, user_alpha_owner, org_alpha):
        """GET renders the new-template form."""
        client.force_login(user_alpha_owner)
        response = client.get(reverse('project_template_create'))
        assert response.status_code == 200
        body = response.content.decode().lower()
        assert 'name' in body
        assert 'task' in body

    def test_post_creates_template_with_tasks(self, client, user_alpha_owner, org_alpha):
        """POST creates ProjectTemplate + tasks from repeated form fields."""
        from core.models import ProjectTemplate
        client.force_login(user_alpha_owner)

        response = client.post(reverse('project_template_create'), {
            'name': 'Sunday Prep',
            'description': 'Standard Sunday',
            'is_shared': 'on',
            'task_title': ['Stage setup', 'Rehearsal'],
            'task_offset': ['-3', '-1'],
            'task_role': ['tech_lead', ''],
        })

        assert response.status_code == 302
        t = ProjectTemplate.objects.get(name='Sunday Prep')
        assert t.is_shared is True
        assert t.template_tasks.count() == 2
        assert t.template_tasks.filter(title='Stage setup', relative_due_offset_days=-3).exists()
        assert t.template_tasks.filter(title='Rehearsal', relative_due_offset_days=-1).exists()

    def test_post_empty_name_rejected(self, client, user_alpha_owner, org_alpha):
        """POST with empty name doesn't create template."""
        from core.models import ProjectTemplate
        client.force_login(user_alpha_owner)

        client.post(reverse('project_template_create'), {
            'name': '',
            'task_title': ['A'],
            'task_offset': ['-1'],
            'task_role': [''],
        })

        assert not ProjectTemplate.objects.filter(organization=org_alpha).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateCreateView -v`
Expected: FAIL (stub returns 200 but doesn't create)

- [ ] **Step 3: Replace the stub view**

In `core/views.py`, replace `project_template_create`:

```python
@login_required
def project_template_create(request):
    """GET shows form, POST creates a ProjectTemplate + its ProjectTemplateTasks."""
    from .models import ProjectTemplate, ProjectTemplateTask

    org = get_org(request)
    if not org:
        return redirect('project_template_list')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            return render(request, 'core/comms/project_template_create.html', {
                'error': 'Name is required',
                'form': request.POST,
            })

        template = ProjectTemplate.objects.create(
            organization=org,
            name=name,
            description=request.POST.get('description', '').strip(),
            is_shared=request.POST.get('is_shared') == 'on',
            created_by=request.user,
        )

        # Parse repeated form fields for tasks
        titles = request.POST.getlist('task_title')
        offsets = request.POST.getlist('task_offset')
        roles = request.POST.getlist('task_role')

        for i, title in enumerate(titles):
            title = title.strip()
            if not title:
                continue
            try:
                offset = int(offsets[i]) if i < len(offsets) and offsets[i] else 0
            except (ValueError, IndexError):
                offset = 0
            role = roles[i].strip() if i < len(roles) else ''
            ProjectTemplateTask.objects.create(
                template=template,
                title=title,
                relative_due_offset_days=offset,
                role_placeholder=role,
                order=i,
            )

        return redirect('project_template_detail', pk=template.pk)

    return render(request, 'core/comms/project_template_create.html', {})
```

- [ ] **Step 4: Create template `templates/core/comms/project_template_create.html`**

```html
{% extends 'base.html' %}

{% block title %}New Project Template{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto px-4 py-6">
  <div class="mb-4 text-sm text-[#888]">
    <a href="{% url 'project_template_list' %}" class="hover:text-[#c9a227]">Project Templates</a>
    <span class="mx-2">/</span>
    <span>New</span>
  </div>

  <h1 class="text-xl font-semibold text-[#eee] mb-5">New Project Template</h1>

  {% if error %}
    <div class="mb-4 p-3 bg-[#2a0a0a] border border-[#e74c3c]/30 text-[#e74c3c] rounded text-sm">{{ error }}</div>
  {% endif %}

  <form method="post" class="space-y-4" x-data='{ tasks: [{ title: "", offset: 0, role: "" }] }'>
    {% csrf_token %}
    <div>
      <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Template Name</label>
      <input type="text" name="name" required maxlength="200"
             value="{{ form.name|default:'' }}"
             placeholder="e.g. Sunday Service Prep"
             class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#eee] focus:border-[#c9a227] focus:outline-none">
    </div>
    <div>
      <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Description</label>
      <textarea name="description" rows="2"
                placeholder="Optional description"
                class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#ccc] focus:border-[#c9a227] focus:outline-none resize-none">{{ form.description|default:'' }}</textarea>
    </div>
    <div class="flex items-center gap-2">
      <input type="checkbox" name="is_shared" id="is_shared" class="accent-[#c9a227]">
      <label for="is_shared" class="text-sm text-[#ccc]">Share with other members of this organization</label>
    </div>

    <div class="pt-4 border-t border-[#333]">
      <div class="flex items-center justify-between mb-3">
        <label class="block text-xs uppercase tracking-wide text-[#888]">Tasks</label>
        <button type="button" @click="tasks.push({ title: '', offset: 0, role: '' })"
                class="text-xs text-[#c9a227] hover:underline">+ Add Task</button>
      </div>

      <template x-for="(task, idx) in tasks" :key="idx">
        <div class="flex flex-wrap items-center gap-2 mb-2 bg-[#1a1a1a] border border-[#333] rounded-md p-2">
          <input type="text" name="task_title" x-model="task.title"
                 placeholder="Task title"
                 class="flex-1 min-w-[200px] bg-transparent border border-[#333] rounded px-2 py-1 text-sm text-[#eee] focus:border-[#c9a227] focus:outline-none">
          <input type="number" name="task_offset" x-model="task.offset"
                 placeholder="Offset days"
                 class="w-24 bg-transparent border border-[#333] rounded px-2 py-1 text-sm text-[#eee] focus:border-[#c9a227] focus:outline-none">
          <input type="text" name="task_role" x-model="task.role"
                 placeholder="Role (optional)"
                 class="w-32 bg-transparent border border-[#333] rounded px-2 py-1 text-sm text-[#eee] focus:border-[#c9a227] focus:outline-none">
          <button type="button" @click="tasks.splice(idx, 1)" x-show="tasks.length > 1"
                  class="text-[#888] hover:text-[#e74c3c] text-sm px-2">&times;</button>
        </div>
      </template>

      <p class="text-xs text-[#666] mt-2">Offset days: negative = before event date, positive = after. E.g., -3 means task is due 3 days before the event.</p>
    </div>

    <div class="flex items-center gap-3 pt-4">
      <button type="submit" class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
        Create Template
      </button>
      <a href="{% url 'project_template_list' %}" class="text-sm text-[#888] hover:text-[#eee]">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateCreateView -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add core/views.py templates/core/comms/project_template_create.html tests/test_project_templates.py
git commit -m "feat(templates): add ProjectTemplate create view"
```

---

## Task 5: ProjectTemplate detail/edit view

**Files:**
- Modify: `core/views.py` (replace `project_template_detail` stub)
- Create: `templates/core/comms/project_template_detail.html`
- Test: `tests/test_project_templates.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestProjectTemplateDetailView:
    """Tests for viewing/editing a ProjectTemplate."""

    def test_detail_renders(self, client, user_alpha_owner, org_alpha):
        """GET shows template with its tasks."""
        from core.models import ProjectTemplate, ProjectTemplateTask
        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='Sunday', created_by=user_alpha_owner,
        )
        ProjectTemplateTask.objects.create(
            template=t, title='Stage setup', relative_due_offset_days=-3, order=0,
        )
        client.force_login(user_alpha_owner)

        response = client.get(reverse('project_template_detail', args=[t.pk]))

        assert response.status_code == 200
        body = response.content.decode()
        assert 'Sunday' in body
        assert 'Stage setup' in body

    def test_detail_denies_other_org(
        self, client, user_alpha_owner, user_beta_owner, org_alpha
    ):
        """Users from other orgs cannot view a template."""
        from core.models import ProjectTemplate
        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='T', created_by=user_alpha_owner,
        )
        client.force_login(user_beta_owner)
        response = client.get(reverse('project_template_detail', args=[t.pk]))
        assert response.status_code in (302, 403, 404)

    def test_post_updates_template(self, client, user_alpha_owner, org_alpha):
        """POST replaces tasks and updates name/description."""
        from core.models import ProjectTemplate, ProjectTemplateTask
        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='Old', created_by=user_alpha_owner,
        )
        ProjectTemplateTask.objects.create(
            template=t, title='Old task', relative_due_offset_days=0, order=0,
        )
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('project_template_detail', args=[t.pk]),
            {
                'name': 'New Name',
                'description': 'Updated',
                'task_title': ['Fresh task'],
                'task_offset': ['-2'],
                'task_role': [''],
            },
        )

        assert response.status_code == 302
        t.refresh_from_db()
        assert t.name == 'New Name'
        assert t.template_tasks.count() == 1
        assert t.template_tasks.first().title == 'Fresh task'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateDetailView -v`
Expected: FAIL (stub returns 200 but doesn't render/update)

- [ ] **Step 3: Replace the stub view**

In `core/views.py`:

```python
@login_required
def project_template_detail(request, pk):
    """View + edit a ProjectTemplate."""
    from .models import ProjectTemplate, ProjectTemplateTask

    org = get_org(request)
    queryset = ProjectTemplate.objects.all()
    if org:
        queryset = queryset.filter(organization=org)
    template = get_object_or_404(queryset, pk=pk)

    # Visibility: own template or shared in same org
    if template.created_by != request.user and not template.is_shared:
        return redirect('project_template_list')

    if request.method == 'POST':
        # Only creator can edit
        if template.created_by != request.user:
            return redirect('project_template_detail', pk=template.pk)

        name = request.POST.get('name', '').strip()
        if name:
            template.name = name
            template.description = request.POST.get('description', '').strip()
            template.is_shared = request.POST.get('is_shared') == 'on'
            template.save()

            # Replace all template tasks
            template.template_tasks.all().delete()
            titles = request.POST.getlist('task_title')
            offsets = request.POST.getlist('task_offset')
            roles = request.POST.getlist('task_role')
            for i, title in enumerate(titles):
                title = title.strip()
                if not title:
                    continue
                try:
                    offset = int(offsets[i]) if i < len(offsets) and offsets[i] else 0
                except (ValueError, IndexError):
                    offset = 0
                role = roles[i].strip() if i < len(roles) else ''
                ProjectTemplateTask.objects.create(
                    template=template, title=title,
                    relative_due_offset_days=offset, role_placeholder=role,
                    order=i,
                )

        return redirect('project_template_detail', pk=template.pk)

    return render(request, 'core/comms/project_template_detail.html', {
        'template': template,
        'template_tasks': template.template_tasks.all(),
        'can_edit': template.created_by == request.user,
    })
```

- [ ] **Step 4: Create template `templates/core/comms/project_template_detail.html`**

```html
{% extends 'base.html' %}

{% block title %}{{ template.name }} - Template{% endblock %}

{% block content %}
<div class="max-w-3xl mx-auto px-4 py-6">
  <div class="mb-4 text-sm text-[#888]">
    <a href="{% url 'project_template_list' %}" class="hover:text-[#c9a227]">Project Templates</a>
    <span class="mx-2">/</span>
    <span>{{ template.name }}</span>
  </div>

  <div class="flex items-center justify-between mb-5">
    <h1 class="text-xl font-semibold text-[#eee]">{{ template.name }}</h1>
    <div class="flex items-center gap-2">
      <a href="{% url 'project_template_apply' template.pk %}"
         class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
        Use This Template
      </a>
      {% if can_edit %}
        <form method="post" action="{% url 'project_template_delete' template.pk %}" class="inline"
              onsubmit="return confirm('Delete this template?');">
          {% csrf_token %}
          <button type="submit" class="px-3 py-1.5 text-sm bg-[#1a1a1a] border border-[#333] text-[#888] rounded hover:border-[#e74c3c]/30 hover:text-[#e74c3c]">
            Delete
          </button>
        </form>
      {% endif %}
    </div>
  </div>

  {% if can_edit %}
    <form method="post" class="space-y-4" x-data='{
      tasks: [{% for tt in template_tasks %}{ title: "{{ tt.title|escapejs }}", offset: {{ tt.relative_due_offset_days }}, role: "{{ tt.role_placeholder|escapejs }}" }{% if not forloop.last %},{% endif %}{% endfor %}{% if not template_tasks %}{ title: "", offset: 0, role: "" }{% endif %}]
    }'>
      {% csrf_token %}
      <div>
        <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Name</label>
        <input type="text" name="name" required maxlength="200" value="{{ template.name }}"
               class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#eee] focus:border-[#c9a227] focus:outline-none">
      </div>
      <div>
        <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Description</label>
        <textarea name="description" rows="2"
                  class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#ccc] focus:border-[#c9a227] focus:outline-none resize-none">{{ template.description }}</textarea>
      </div>
      <div class="flex items-center gap-2">
        <input type="checkbox" name="is_shared" id="is_shared" class="accent-[#c9a227]" {% if template.is_shared %}checked{% endif %}>
        <label for="is_shared" class="text-sm text-[#ccc]">Share with other members of this organization</label>
      </div>

      <div class="pt-4 border-t border-[#333]">
        <div class="flex items-center justify-between mb-3">
          <label class="block text-xs uppercase tracking-wide text-[#888]">Tasks</label>
          <button type="button" @click="tasks.push({ title: '', offset: 0, role: '' })"
                  class="text-xs text-[#c9a227] hover:underline">+ Add Task</button>
        </div>
        <template x-for="(task, idx) in tasks" :key="idx">
          <div class="flex flex-wrap items-center gap-2 mb-2 bg-[#1a1a1a] border border-[#333] rounded-md p-2">
            <input type="text" name="task_title" x-model="task.title" placeholder="Task title"
                   class="flex-1 min-w-[200px] bg-transparent border border-[#333] rounded px-2 py-1 text-sm text-[#eee] focus:border-[#c9a227] focus:outline-none">
            <input type="number" name="task_offset" x-model="task.offset" placeholder="Offset days"
                   class="w-24 bg-transparent border border-[#333] rounded px-2 py-1 text-sm text-[#eee] focus:border-[#c9a227] focus:outline-none">
            <input type="text" name="task_role" x-model="task.role" placeholder="Role (optional)"
                   class="w-32 bg-transparent border border-[#333] rounded px-2 py-1 text-sm text-[#eee] focus:border-[#c9a227] focus:outline-none">
            <button type="button" @click="tasks.splice(idx, 1)" x-show="tasks.length > 1"
                    class="text-[#888] hover:text-[#e74c3c] text-sm px-2">&times;</button>
          </div>
        </template>
      </div>

      <div class="pt-4">
        <button type="submit" class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
          Save Changes
        </button>
      </div>
    </form>
  {% else %}
    <!-- Read-only view -->
    {% if template.description %}
      <p class="text-sm text-[#ccc] mb-4">{{ template.description }}</p>
    {% endif %}
    <h2 class="text-xs uppercase tracking-wide text-[#888] mb-3">Tasks</h2>
    <ul class="space-y-2">
      {% for tt in template_tasks %}
        <li class="bg-[#1a1a1a] border border-[#333] rounded-md p-3">
          <div class="text-[#eee]">{{ tt.title }}</div>
          <div class="text-xs text-[#666] mt-1">
            {{ tt.relative_due_offset_days }} days from event
            {% if tt.role_placeholder %}&middot; role: {{ tt.role_placeholder }}{% endif %}
          </div>
        </li>
      {% endfor %}
    </ul>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateDetailView -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add core/views.py templates/core/comms/project_template_detail.html tests/test_project_templates.py
git commit -m "feat(templates): add ProjectTemplate detail and edit view"
```

---

## Task 6: ProjectTemplate delete view

**Files:**
- Modify: `core/views.py` (replace `project_template_delete` stub)
- Test: `tests/test_project_templates.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestProjectTemplateDeleteView:
    """Tests for deleting a ProjectTemplate."""

    def test_creator_can_delete(self, client, user_alpha_owner, org_alpha):
        """Creator of template can delete it."""
        from core.models import ProjectTemplate
        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='T', created_by=user_alpha_owner,
        )
        client.force_login(user_alpha_owner)

        response = client.post(reverse('project_template_delete', args=[t.pk]))

        assert response.status_code == 302
        assert not ProjectTemplate.objects.filter(pk=t.pk).exists()

    def test_non_creator_cannot_delete(
        self, client, user_alpha_owner, user_alpha_member, org_alpha
    ):
        """Non-creator cannot delete even a shared template."""
        from core.models import ProjectTemplate
        t = ProjectTemplate.objects.create(
            organization=org_alpha, name='T',
            created_by=user_alpha_owner, is_shared=True,
        )
        client.force_login(user_alpha_member)

        client.post(reverse('project_template_delete', args=[t.pk]))

        assert ProjectTemplate.objects.filter(pk=t.pk).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateDeleteView -v`
Expected: FAIL (stub doesn't delete)

- [ ] **Step 3: Replace stub with real view**

In `core/views.py`:

```python
@login_required
@require_POST
def project_template_delete(request, pk):
    """Delete a ProjectTemplate. Only the creator can delete."""
    from .models import ProjectTemplate

    org = get_org(request)
    queryset = ProjectTemplate.objects.all()
    if org:
        queryset = queryset.filter(organization=org)
    template = get_object_or_404(queryset, pk=pk)

    if template.created_by != request.user:
        return redirect('project_template_detail', pk=template.pk)

    template.delete()
    return redirect('project_template_list')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateDeleteView -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_project_templates.py
git commit -m "feat(templates): add ProjectTemplate delete view"
```

---

## Task 7: Apply-template view (spawn project from template)

**Files:**
- Modify: `core/views.py` (replace `project_template_apply` stub)
- Create: `templates/core/comms/project_template_apply.html`
- Test: `tests/test_project_templates.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestProjectTemplateApplyView:
    """Tests for creating a Project from a template."""

    def _template(self, user, org):
        from core.models import ProjectTemplate, ProjectTemplateTask
        t = ProjectTemplate.objects.create(
            organization=org, name='Sunday', created_by=user,
        )
        ProjectTemplateTask.objects.create(
            template=t, title='Stage', relative_due_offset_days=-3, order=0,
        )
        return t

    def test_get_apply_form(self, client, user_alpha_owner, org_alpha):
        """GET shows form to pick event date and project name."""
        t = self._template(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('project_template_apply', args=[t.pk]))

        assert response.status_code == 200
        body = response.content.decode().lower()
        assert 'event date' in body or 'event_date' in body

    def test_post_creates_project(self, client, user_alpha_owner, org_alpha):
        """POST spawns a new Project with tasks from the template."""
        from core.models import Project
        t = self._template(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('project_template_apply', args=[t.pk]),
            {
                'project_name': 'Easter 2026',
                'event_date': '2026-04-05',
            },
        )

        assert response.status_code == 302
        p = Project.objects.get(name='Easter 2026')
        assert p.organization == org_alpha
        assert p.owner == user_alpha_owner
        assert p.tasks.count() == 1
        stage = p.tasks.first()
        assert stage.title == 'Stage'
        assert str(stage.due_date) == '2026-04-02'

    def test_post_requires_fields(self, client, user_alpha_owner, org_alpha):
        """POST without name or date re-renders form."""
        from core.models import Project
        t = self._template(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('project_template_apply', args=[t.pk]),
            {'project_name': '', 'event_date': ''},
        )

        assert response.status_code == 200
        assert not Project.objects.filter(organization=org_alpha).exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateApplyView -v`
Expected: FAIL (stub doesn't create project)

- [ ] **Step 3: Replace the stub view**

In `core/views.py`:

```python
@login_required
def project_template_apply(request, pk):
    """Create a new Project from a ProjectTemplate."""
    from .models import ProjectTemplate
    from datetime import datetime

    org = get_org(request)
    queryset = ProjectTemplate.objects.all()
    if org:
        queryset = queryset.filter(organization=org)
    template = get_object_or_404(queryset, pk=pk)

    # Visibility check
    if template.created_by != request.user and not template.is_shared:
        return redirect('project_template_list')

    if request.method == 'POST':
        project_name = request.POST.get('project_name', '').strip()
        event_date_str = request.POST.get('event_date', '').strip()
        project_description = request.POST.get('project_description', '').strip()

        error = None
        event_date = None
        if not project_name:
            error = 'Project name is required.'
        elif not event_date_str:
            error = 'Event date is required.'
        else:
            try:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
            except ValueError:
                error = 'Invalid date format.'

        if error:
            return render(request, 'core/comms/project_template_apply.html', {
                'template': template,
                'error': error,
                'form': request.POST,
            })

        project = template.apply(
            event_date=event_date,
            project_name=project_name,
            user=request.user,
            project_description=project_description,
        )
        return redirect('project_detail', pk=project.pk)

    return render(request, 'core/comms/project_template_apply.html', {
        'template': template,
    })
```

- [ ] **Step 4: Create template `templates/core/comms/project_template_apply.html`**

```html
{% extends 'base.html' %}

{% block title %}Use Template: {{ template.name }}{% endblock %}

{% block content %}
<div class="max-w-2xl mx-auto px-4 py-6">
  <div class="mb-4 text-sm text-[#888]">
    <a href="{% url 'project_template_list' %}" class="hover:text-[#c9a227]">Project Templates</a>
    <span class="mx-2">/</span>
    <a href="{% url 'project_template_detail' template.pk %}" class="hover:text-[#c9a227]">{{ template.name }}</a>
    <span class="mx-2">/</span>
    <span>Use</span>
  </div>

  <h1 class="text-xl font-semibold text-[#eee] mb-5">Create Project from Template</h1>
  <p class="text-sm text-[#888] mb-5">
    Template "<span class="text-[#eee]">{{ template.name }}</span>" will spawn a new project with
    {{ template.template_tasks.count }} task{{ template.template_tasks.count|pluralize }}
    scheduled relative to the event date you pick.
  </p>

  {% if error %}
    <div class="mb-4 p-3 bg-[#2a0a0a] border border-[#e74c3c]/30 text-[#e74c3c] rounded text-sm">{{ error }}</div>
  {% endif %}

  <form method="post" class="space-y-4">
    {% csrf_token %}
    <div>
      <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Project Name</label>
      <input type="text" name="project_name" required maxlength="200"
             value="{{ form.project_name|default:'' }}"
             placeholder="e.g. Easter Sunday 2026"
             class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#eee] focus:border-[#c9a227] focus:outline-none">
    </div>
    <div>
      <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Event Date</label>
      <input type="date" name="event_date" required
             value="{{ form.event_date|default:'' }}"
             class="bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#eee] focus:border-[#c9a227] focus:outline-none"
             style="color-scheme: dark;">
    </div>
    <div>
      <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Description (optional)</label>
      <textarea name="project_description" rows="2"
                class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#ccc] focus:border-[#c9a227] focus:outline-none resize-none">{{ form.project_description|default:'' }}</textarea>
    </div>

    <div class="pt-4">
      <h3 class="text-xs uppercase tracking-wide text-[#888] mb-2">Tasks that will be created:</h3>
      <ul class="space-y-1 text-sm text-[#ccc]">
        {% for tt in template.template_tasks.all %}
          <li class="flex items-center gap-2">
            <span class="text-[#666] text-xs w-20">
              {% if tt.relative_due_offset_days < 0 %}{{ tt.relative_due_offset_days }}d{% elif tt.relative_due_offset_days > 0 %}+{{ tt.relative_due_offset_days }}d{% else %}event{% endif %}
            </span>
            <span>{{ tt.title }}</span>
          </li>
        {% endfor %}
      </ul>
    </div>

    <div class="flex items-center gap-3 pt-4">
      <button type="submit" class="px-4 py-1.5 bg-[#c9a227] text-[#0f0f0f] text-sm font-semibold rounded hover:bg-[#d9b237]">
        Create Project
      </button>
      <a href="{% url 'project_template_detail' template.pk %}" class="text-sm text-[#888] hover:text-[#eee]">Cancel</a>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_project_templates.py::TestProjectTemplateApplyView -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add core/views.py templates/core/comms/project_template_apply.html tests/test_project_templates.py
git commit -m "feat(templates): add apply-template view to spawn projects"
```

---

## Task 8: Add PCO fields to TaskTemplate

**Files:**
- Modify: `core/models.py` (TaskTemplate class)
- Test: `tests/test_pco_recurrence.py` (new file)

- [ ] **Step 1: Create test file with failing test**

Create `tests/test_pco_recurrence.py`:

```python
"""Tests for PCO-service-linked TaskTemplate recurrence."""
import pytest
from django.utils import timezone


@pytest.mark.django_db
class TestPCOFields:
    """Tests for PCO-related fields on TaskTemplate."""

    def test_pco_fields_default_empty(self, user_alpha_owner, org_alpha):
        """New TaskTemplate has PCO fields with sensible defaults."""
        from core.models import Project, TaskTemplate
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        t = TaskTemplate.objects.create(
            name='Weekly',
            title_template='Prep {weekday}',
            project=project,
            recurrence_type='weekly',
            recurrence_days=[6],
            created_by=user_alpha_owner,
        )
        assert t.pco_service_type_id == ''
        assert t.pco_days_before_service == 0

    def test_pco_service_recurrence_choice(self, user_alpha_owner, org_alpha):
        """recurrence_type='pco_service' is a valid choice."""
        from core.models import Project, TaskTemplate
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        t = TaskTemplate.objects.create(
            name='PCO-linked',
            title_template='Service prep',
            project=project,
            recurrence_type='pco_service',
            pco_service_type_id='12345',
            pco_days_before_service=2,
            created_by=user_alpha_owner,
        )
        t.full_clean()  # Should not raise
        assert t.recurrence_type == 'pco_service'
        assert t.pco_service_type_id == '12345'
        assert t.pco_days_before_service == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pco_recurrence.py::TestPCOFields -v`
Expected: FAIL with `AttributeError: 'TaskTemplate' object has no attribute 'pco_service_type_id'` OR validation error on recurrence_type

- [ ] **Step 3: Add PCO fields to TaskTemplate in core/models.py**

Find the `TaskTemplate.RECURRENCE_CHOICES` list (around line 3051) and add one new choice:

```python
    RECURRENCE_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Every 2 Weeks'),
        ('monthly', 'Monthly (same day)'),
        ('monthly_weekday', 'Monthly (same weekday)'),
        ('custom', 'Custom Days'),
        ('pco_service', 'PCO Service (tied to Planning Center services)'),
    ]
```

Then find the location where `recurrence_days` is defined (around line 3085) and ADD two new fields immediately after it:

```python
    # PCO-service-linked recurrence
    pco_service_type_id = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Planning Center service type ID (used when recurrence_type='pco_service')",
    )
    pco_days_before_service = models.IntegerField(
        default=0,
        help_text="Days before the service date to create the task (0 = same day)",
    )
```

- [ ] **Step 4: Create and apply migration**

Run: `python manage.py makemigrations core --name tasktemplate_pco_fields`
Then: `python manage.py migrate core`

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_recurrence.py::TestPCOFields -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_pco_recurrence.py
git commit -m "feat(templates): add PCO service recurrence fields to TaskTemplate"
```

---

## Task 9: PCO-linked next_occurrences logic

**Files:**
- Modify: `core/models.py` (TaskTemplate.get_next_occurrences method)
- Test: `tests/test_pco_recurrence.py` (append)

- [ ] **Step 1: Append failing test with mocked PCO API**

```python
@pytest.mark.django_db
class TestPCOGetNextOccurrences:
    """Tests for get_next_occurrences when recurrence_type='pco_service'."""

    def test_pco_returns_service_dates(
        self, user_alpha_owner, org_alpha, monkeypatch
    ):
        """get_next_occurrences queries PCO and returns plan dates minus offset."""
        from datetime import date
        from core.models import Project, TaskTemplate

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        template = TaskTemplate.objects.create(
            name='PCO',
            title_template='Prep {month} {day}',
            project=project,
            recurrence_type='pco_service',
            pco_service_type_id='srv-123',
            pco_days_before_service=2,
            created_by=user_alpha_owner,
        )

        # Mock the PCO API so the test doesn't hit the network
        mock_plans = [
            {'sort_date': '2026-04-05T10:00:00Z'},  # Sunday
            {'sort_date': '2026-04-12T10:00:00Z'},  # Sunday
            {'sort_date': '2026-04-19T10:00:00Z'},  # Sunday
        ]
        def fake_fetch(self, service_type_id, start_date, end_date, limit=10):
            return mock_plans

        monkeypatch.setattr(
            'core.planning_center.PlanningCenterServicesAPI.get_plans_by_date_range',
            fake_fetch,
        )

        occurrences = template.get_next_occurrences(
            from_date=date(2026, 4, 1), count=3,
        )
        # Expected: each service date minus 2 days
        assert occurrences == [
            date(2026, 4, 3),
            date(2026, 4, 10),
            date(2026, 4, 17),
        ]

    def test_pco_handles_missing_service_type(
        self, user_alpha_owner, org_alpha,
    ):
        """Empty pco_service_type_id returns empty list."""
        from datetime import date
        from core.models import Project, TaskTemplate
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        template = TaskTemplate.objects.create(
            name='Bad', title_template='X', project=project,
            recurrence_type='pco_service', pco_service_type_id='',
            created_by=user_alpha_owner,
        )
        occurrences = template.get_next_occurrences(
            from_date=date(2026, 4, 1), count=3,
        )
        assert occurrences == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pco_recurrence.py::TestPCOGetNextOccurrences -v`
Expected: FAIL with `KeyError` or empty list (existing logic doesn't handle 'pco_service')

- [ ] **Step 3: Read the existing get_next_occurrences method**

Find `def get_next_occurrences` in core/models.py (around line 3220) and understand the existing branching on `recurrence_type`.

- [ ] **Step 4: Add pco_service branch to get_next_occurrences**

In core/models.py, find the existing `elif self.recurrence_type == 'custom':` branch in `get_next_occurrences`, and add this new branch AFTER it (still inside the method):

```python
            elif self.recurrence_type == 'pco_service':
                if not self.pco_service_type_id:
                    return []
                try:
                    from .planning_center import PlanningCenterServicesAPI
                    api = PlanningCenterServicesAPI()
                    from datetime import timedelta
                    start_str = start_from.strftime('%Y-%m-%d')
                    end_str = (start_from + timedelta(days=365)).strftime('%Y-%m-%d')
                    plans = api.get_plans_by_date_range(
                        service_type_id=self.pco_service_type_id,
                        start_date=start_str,
                        end_date=end_str,
                        limit=count * 2,  # fetch a few extra
                    )
                    results = []
                    for plan in plans:
                        sort_date = plan.get('sort_date') or plan.get('date')
                        if not sort_date:
                            continue
                        # sort_date format: '2026-04-05T10:00:00Z' or similar
                        date_str = sort_date[:10]
                        try:
                            service_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
                        except (ValueError, TypeError):
                            continue
                        target_date = service_date - timedelta(days=self.pco_days_before_service)
                        if target_date >= start_from:
                            results.append(target_date)
                        if len(results) >= count:
                            break
                    return results
                except Exception:
                    return []
```

**IMPORTANT:** This new branch must be placed INSIDE the `get_next_occurrences` method, as a sibling of the existing `if`/`elif` branches. It should NOT be inside the `while` loop if there is one — look at the existing code structure carefully.

**Guidance for placement:** Look at how the existing branches (`'daily'`, `'weekly'`, etc.) are structured. If they're inside a loop that generates dates one at a time, your `pco_service` branch can return the complete list early with `return results`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_pco_recurrence.py::TestPCOGetNextOccurrences -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Run full Phase 3 test suite + existing**

```bash
pytest tests/test_project_templates.py tests/test_pco_recurrence.py -v 2>&1 | tail -20
pytest tests/ -x 2>&1 | tail -10
```

Expected: All Phase 3 tests pass, no regressions.

- [ ] **Step 7: Commit**

```bash
git add core/models.py tests/test_pco_recurrence.py
git commit -m "feat(templates): PCO service-linked recurrence for TaskTemplate"
```

---

## Task 10: Add PCO config UI to TaskTemplate create/edit

**Files:**
- Modify: `templates/core/comms/template_create.html`
- Modify: `templates/core/comms/template_detail.html`
- Modify: `core/views.py` (`template_create` and `template_detail` views)

- [ ] **Step 1: Read the existing template_create view**

Find `def template_create` in core/views.py to understand the current form handling. Note which POST fields it reads.

- [ ] **Step 2: Add pco_service_type_id and pco_days_before_service to POST handling**

In BOTH `template_create` and `template_detail` views, add lines to read and save these new fields. Look for the existing save logic (e.g., where `recurrence_type` and `recurrence_days` are written). Add:

```python
    # PCO-linked recurrence fields
    pco_service_type_id = request.POST.get('pco_service_type_id', '').strip()
    try:
        pco_days_before_service = int(request.POST.get('pco_days_before_service', '0') or 0)
    except ValueError:
        pco_days_before_service = 0
```

And include them when setting template attributes / creating the object.

- [ ] **Step 3: Add PCO fields to template_create.html form**

Read the existing `templates/core/comms/template_create.html`. Find the recurrence_type select input and add an `<option value="pco_service">PCO Service</option>` entry to it. Then add two new inputs (after the recurrence config, perhaps in a collapsible section or shown via Alpine conditional):

```html
<div x-show="recurrenceType === 'pco_service'" x-cloak class="space-y-3 pt-3 border-t border-[#333]">
  <div>
    <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">PCO Service Type ID</label>
    <input type="text" name="pco_service_type_id"
           placeholder="e.g. 12345 (from Planning Center)"
           class="w-full bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#eee] focus:border-[#c9a227] focus:outline-none">
  </div>
  <div>
    <label class="block text-xs uppercase tracking-wide text-[#888] mb-1.5">Days Before Service</label>
    <input type="number" name="pco_days_before_service" value="0" min="0"
           class="w-24 bg-[#1a1a1a] border border-[#333] rounded-md px-3 py-2 text-[#eee] focus:border-[#c9a227] focus:outline-none">
    <p class="text-xs text-[#666] mt-1">0 = same day as service. 2 = task created 2 days before each service.</p>
  </div>
</div>
```

Add `x-data='{ recurrenceType: "weekly" }'` to a wrapping element (or the recurrence select's scope), and `@change="recurrenceType = $event.target.value"` on the select.

**Guidance:** If the existing form doesn't use Alpine for recurrence visibility, you can alternatively show the PCO fields always. Prefer the Alpine approach if the existing form already uses Alpine; otherwise, show unconditionally with a label "(only used when recurrence is PCO Service)".

- [ ] **Step 4: Add same fields to template_detail.html (edit form)**

Apply the same pattern to `templates/core/comms/template_detail.html` — add PCO service-type ID and days-before-service inputs, pre-filled from the existing template's values.

- [ ] **Step 5: Manual smoke test**

Run: `python manage.py runserver`
- Navigate to the Recurring Task Templates create form
- Select "PCO Service" from the recurrence dropdown
- Verify the new fields appear
- Save and verify values round-trip on the edit form

Run: `pytest tests/ -x 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add core/views.py templates/core/comms/template_create.html templates/core/comms/template_detail.html
git commit -m "feat(templates): add PCO service config to TaskTemplate create/edit forms"
```

---

## Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ 2>&1 | tail -10`
Expected: All tests pass, no regressions.

- [ ] **Step 2: Manual smoke test**

Start dev server: `python manage.py runserver`

**ProjectTemplate flow:**
1. Navigate to the hub → click "Project Templates"
2. Create a new template with 3 tasks (e.g., -7 days, -3 days, 0 days offsets)
3. Click "Use" → enter project name + event date → see new project with 3 tasks at correct dates
4. Edit a template → add a task → save → verify
5. Delete a template → confirm

**PCO recurrence flow:**
6. Navigate to Recurring Task Templates → create new
7. Select "PCO Service" recurrence → fill in service type ID + days-before
8. Save → verify next_occurrence shows an actual PCO plan date

---

## Deployment Notes

- Migrations are additive (no data loss)
- Deploy migrations first, then code
- PCO-linked templates degrade gracefully if PCO API is unavailable (return empty list, log but don't crash)
- No new environment variables required (PCO creds already configured)
