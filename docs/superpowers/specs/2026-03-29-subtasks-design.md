# Subtasks Feature Design

**Date:** 2026-03-29
**Status:** Approved
**Author:** Claude + Ryan

## Overview

Add subtask support to the existing Task model so tasks can contain nested child tasks. This enables managing large projects (like Easter Weekend prep) with hierarchical task breakdowns where each subtask has its own title, assignees, comments, status, and optional due date.

## Requirements

- Unlimited nesting depth (tasks can have subtasks, which can have their own subtasks)
- Subtasks inherit project and organization from their root ancestor (cannot override)
- Assignees, due dates, priority, and status are independent per subtask
- Expandable/collapsible subtask display in project detail and task detail views
- Progress indicator on parent tasks showing "X/Y subtasks done"
- Visual nudge when all subtasks are completed: "All subtasks done — mark complete?"
- Inline subtask creation via HTMX without page reload

## Data Model

### Task Model Changes

Add one field to the existing `Task` model (`core/models.py`):

```python
parent = models.ForeignKey(
    'self',
    on_delete=models.CASCADE,
    null=True,
    blank=True,
    related_name='subtasks'
)
```

### Behavior

- **Cascade delete**: Deleting a parent deletes all descendants.
- **Project/org inheritance**: On `save()`, if `parent` is set, copy `project` and `organization` from the root ancestor. Reject attempts to override.
- **Circular reference guard**: In `save()`, walk up the `parent` chain (max 20 iterations). If `self` is found, raise `ValidationError`.
- **Move restriction**: Moving a task to a different project is blocked if it has subtasks.
- **No auto-complete**: Completing a parent does NOT auto-complete its subtasks.

### New Properties

```python
@property
def subtask_progress(self):
    """Returns (completed_count, total_count) for direct subtasks."""
    total = self.subtasks.count()
    completed = self.subtasks.filter(status='completed').count()
    return completed, total
```

### Migration

Single migration adding `parent` ForeignKey to `Task`. Nullable field, no data migration needed — all existing tasks are root tasks (`parent=None`).

## Views & URLs

### Modified Views

- **`project_detail`**: Filter tasks to `parent=None` (root only). Annotate with `subtask_count` and `completed_subtask_count` via `Count` for progress badges on kanban cards.
- **`task_detail`**: Show subtasks section below description, above comments. Display progress summary ("Subtasks 3/5" with progress bar). Show "All subtasks done" nudge when applicable. Breadcrumb shows full ancestor chain.
- **`task_create`**: Accept optional `parent_id`. When creating a subtask, inherit project/org from parent.
- **`task_update_status`**: After marking a subtask completed, check if all sibling subtasks are done. If so, include nudge HTML in HTMX response.

### New Views

- **`task_create_subtask`**: Creates a subtask under a given parent. Inherits project/org. Returns HTMX partial to append to subtask list.
- **`task_subtasks_partial`**: HTMX partial returning the subtask list for a given task. Powers expand/collapse.

### New URL Patterns

```python
path('tasks/<int:parent_pk>/subtasks/create/', views.task_create_subtask, name='task_create_subtask')
path('tasks/<int:pk>/subtasks/', views.task_subtasks_partial, name='task_subtasks_partial')
```

## Templates & UI

### Project Detail (Kanban Cards)

- Only root tasks (`parent=None`) shown in kanban columns.
- Cards with subtasks show:
  - Collapsible arrow icon (chevron right / chevron down)
  - Badge: "3/5" with thin progress bar underneath
- Clicking the arrow fires HTMX GET to `task_subtasks_partial`, expands subtask list below the card, indented.
- Subtasks rendered recursively — subtasks with their own children get the same expand arrow.
- Indentation increases per nesting level (padding-left).

### Subtask List Item

Each subtask row displays:
- Completion circle (click to toggle status via HTMX)
- Title
- Description preview (first line, truncated, gray text)
- Comment count badge (if comments exist)
- Assignee avatar(s) on the right
- Expand arrow if subtask has its own subtasks

### Task Detail Page

- **Subtasks section** below description, above comments:
  - Section header: "Subtasks 3/5" with progress bar
  - Each subtask row: checkbox, title, assignee avatars, comment count, due date
  - Expand arrow for subtasks with children (recursive)
  - "Add Subtask" button at bottom
- **Completion nudge**: Banner appears when all subtasks are done — "All subtasks done — mark complete?" with a button to mark the parent complete.
- **Breadcrumbs**: Full ancestor chain, e.g., `Projects > Easter Weekend > GF Stage Set > Lighting Setup`

### Add Subtask Inline Form

- Appears inline via HTMX when clicking "Add Subtask"
- Fields: title (required), assignee (optional dropdown), due date (optional), priority (optional, defaults to parent's priority)
- Submit creates subtask and appends to list without page reload

## Query & Performance

### Prefetching Strategy

- **Project detail**: `Task.objects.filter(project=project, parent=None).prefetch_related('subtasks', 'subtasks__assignees', 'assignees')` — only root tasks upfront.
- **Subtask expansion (HTMX)**: Loads one level of children per click with `prefetch_related('subtasks', 'assignees')` — bounded queries.
- **No full-tree recursive prefetch** — lazy loading via HTMX keeps pages fast.

### Subtask Count Annotation

For kanban cards, annotate root tasks:

```python
from django.db.models import Count, Q

tasks = project.tasks.filter(parent=None).annotate(
    subtask_count=Count('subtasks'),
    completed_subtask_count=Count('subtasks', filter=Q(subtasks__status='completed'))
)
```

Avoids N+1 queries for progress badges.

### Circular Reference Guard

In `Task.save()`:

```python
if self.parent:
    current = self.parent
    depth = 0
    while current is not None and depth < 20:
        if current.pk == self.pk:
            raise ValidationError("Circular subtask reference detected.")
        current = current.parent
        depth += 1
```

## Testing Plan

### Model Tests (~8 tests)

- Create subtask with parent FK
- Verify project/org inheritance from parent in `save()`
- Circular reference detection (A->B->A rejected)
- Deep nesting (A->B->C->D) works correctly
- CASCADE delete removes all descendants
- `subtask_progress` returns correct counts
- Moving subtask parent blocked when would create cycle
- Root tasks have `parent=None`

### View Tests (~8 tests)

- Create subtask via `task_create_subtask` — inherits project/org
- `task_subtasks_partial` returns correct children
- Project detail only shows root tasks (`parent=None`)
- Task detail shows subtask list and progress
- Completion nudge appears when all siblings completed
- Breadcrumb shows full ancestor chain on subtask detail
- Inline form creates subtask without page reload
- Subtask count annotation correct on kanban cards

### Permission Tests (~4 tests)

- Only project members/owner can create subtasks
- Org isolation — subtasks scoped to organization
- Cannot create subtask on task from different org
- Standalone task subtask creation requires org membership

**Total: ~20 new tests**

## Files to Modify

| File | Change |
|------|--------|
| `core/models.py` | Add `parent` FK, `subtask_progress` property, circular guard in `save()` |
| `core/views.py` | Modify `project_detail`, `task_detail`, `task_update_status`; add `task_create_subtask`, `task_subtasks_partial` |
| `core/urls.py` | Add 2 new URL patterns |
| `templates/core/comms/project_detail.html` | Add expand/collapse arrows, subtask count badges, progress bars on task cards |
| `templates/core/comms/task_detail.html` | Add subtasks section, progress bar, nudge banner, inline add form, ancestor breadcrumbs |
| `templates/core/comms/partials/subtask_list.html` | New partial for HTMX subtask rendering (recursive) |
| `templates/core/comms/partials/subtask_form.html` | New partial for inline add subtask form |
| `tests/test_subtasks.py` | New test file with ~20 tests |

## Out of Scope

- Drag-and-drop reordering of subtasks (can be added later)
- Subtask templates / repeating subtask patterns
- Bulk subtask operations (complete all, assign all)
- Subtask dependencies (blocked-by relationships between subtasks)
