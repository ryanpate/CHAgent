# Todoist Replacement: Conversation-First Task Management

**Date:** 2026-04-04
**Status:** Design approved, pending implementation plan
**Author:** Ryan Pate

## Problem Statement

The team currently uses Todoist for project and task management alongside Aria. The biggest pain point is that **communication within projects is scattered and invisible**:

1. Comments on tasks get buried at the bottom of task detail views. Assignees don't see them until days later (or never).
2. Discussions about a topic span many tasks, with no way to have one conversation that touches multiple tasks.
3. Decisions made in comments or verbal conversations are lost — the next time someone needs that information, it has to be re-asked.

Secondary pain points: no reusable templates for repeating events (like Sunday services), no integration with the team's existing tools (PCO, Aria), and no recurring tasks tied to service dates.

## Goals

- Replace Todoist entirely for the team's task and project management
- Eliminate the "communication buried in tasks" problem through a conversation-first UI
- Capture decisions as first-class, searchable artifacts
- Leverage Aria's existing strengths: AI assistant, PCO integration, volunteer context
- Keep the implementation additive — Aria's existing project/task/channel models already exist and work

## Non-Goals (for v1)

- Kanban board customization, timeline/Gantt views (future)
- Task dependencies with critical-path (future)
- Workload visualization (future)
- Custom fields per project (future)
- Time tracking (future)

## Design Overview

The design has three pillars:

1. **Conversation-first tasks** — Comments are the main interface to a task, not a footer section
2. **Project discussions + decisions** — Threaded conversations that span tasks, with decisions captured as a permanent record
3. **AI, templates, and recurrence** — Aria understands task data; templates eliminate repetitive setup; recurring rules handle rhythm work

## 1. Conversation-First Tasks

### Current vs. new model

**Current:** Task detail shows status/assignee/description at top, comments collapsed at bottom. Users don't scroll down. Comments are missed.

**New:** Comments are the primary content of the task detail view. Description is a short blurb above the conversation. Status/assignee/due date collapse into a header bar. The page reads like a message thread.

### Features

- **Unread tracking:** Per-user `TaskReadState` tracks when a user last viewed each task thread. Task cards show `💬 3` unread count. Opening a task marks it read.
- **Watchers:** Any team member can "watch" a task they're not assigned to. Watchers get notifications per their preferences.
- **Decision marking:** Any comment can be marked as a decision via a "Mark as decision" action. Decision comments render with a green highlight and "DECISION" badge. Decision marking is reversible.
- **Inline checklists:** Tasks get an optional checklist (JSON array of items). Checklist progress shows inline on task cards (`3/8`).

### Notifications

- **@mention** → push + badge
- **Assigned to task** → push + badge
- **Comment on task you're assigned to** → badge (no push by default)
- **Comment on task you're watching** → badge (no push by default)
- **Daily digest** (opt-in) → 8 AM summary of unread comments, new decisions, tasks due today

## 2. Project Discussions & Decisions

### Project detail: 4 tabs

- **Tasks** — existing task list/board view
- **Discussions** — threaded conversations about the project (new)
- **Decisions** — aggregated list of every decision across tasks + discussions (new)
- **Files** — existing file attachments

### Project Discussions

- Separate from task comments. Use for topics that span multiple tasks or are project-wide.
- A discussion has a title, body, replies, and can link to N tasks via M2M.
- Linked tasks render as chips inline; clicking a chip opens the task.
- Discussions can be marked resolved when the topic is settled. Resolved discussions remain visible but de-emphasized.
- @mentions, reactions, and file attachments supported (reuses patterns from ChannelMessage).

### Decisions Tab

- Flat list of every comment marked `is_decision=True` across the project's task comments AND project discussion messages.
- Each decision shows: decision text, who made it, when, and which task/discussion it came from (with deep link).
- Sortable by date, filterable by person, searchable by text.
- Solves "wait, what did we decide about X?" in seconds.

## 3. Templates

### Project Templates

- `ProjectTemplate` — saved blueprint with N template tasks
- `ProjectTemplateTask` — title, description, checklist items, role placeholder (e.g., "tech_lead"), relative due offset (e.g., "-3 days" = 3 days before event)
- "Create project from template" flow: pick template, pick event date, template resolves:
  - Relative dates → concrete dates based on event date
  - Role placeholders → current users in that role, or left unassigned
- Ship 2-3 default templates: "Sunday Service Prep," "Special Event Setup," "Tech Rehearsal Day"
- Admins can create and share custom templates within their org

### Checklist Templates

- `ChecklistTemplate` — reusable N-item checklist for quick reuse in tasks
- When creating a task, "Use checklist template" applies a saved list
- Example: "Sound Check" template with 8 items

## 4. Recurring Tasks

### RecurringTaskRule

Fields: project (optional), title, description, checklist_template, assignees, recurrence_pattern, offset_days, service_type_id (optional), last_generated_at, is_active

### Recurrence patterns

- **Weekly** — e.g., "every Thursday"
- **Monthly** — e.g., "1st Sunday of each month"
- **PCO service-linked** — e.g., "every Cherry Hills Morning Main service, 2 hours before"

### Generation

- Nightly management command (`python manage.py generate_recurring_tasks`) runs each rule
- Generates task instances for next N days (configurable, default 14)
- Each generated task references its rule and the trigger date/service
- Completed instances remain as history

### Editing rules

- "Apply to future tasks only" — default behavior
- "Also update unfinished existing tasks" — optional for bulk updates

## 5. Aria AI Integration

Extend query detection in `core/agent.py`:

**New query types:**
- `my_tasks` — "What's on my plate?" "What do I need to do this week?"
- `team_tasks` — "What's John working on?" "Show me the team's tasks for Sunday"
- `overdue_tasks` — "What's overdue?" "What did we miss for Easter?"
- `project_status` — "Summarize Easter production" "How's Sunday prep going?"
- `decision_search` — "What did we decide about monitors?" "Decisions on stage layout"
- `task_create` — "Remind me to call Sarah about the worship song Friday"

**Data integration:**
- Task and discussion text becomes searchable context alongside interactions and documents
- Decisions are a high-value data source (human-verified, compact)

**Auto-task creation:**
- When processing interaction logs, Aria detects action items ("I'll send her the chord chart")
- Offers: "Create task? Assign to you? Link to Sarah?"
- User confirms inline; task is created with interaction as source

## 6. Data Model

### New models

```python
class ProjectTemplate(models.Model):
    organization = ForeignKey(Organization)
    name = CharField
    description = TextField
    is_shared = BooleanField  # visible to all org members
    created_by = ForeignKey(User)

class ProjectTemplateTask(models.Model):
    template = ForeignKey(ProjectTemplate, related_name='tasks')
    title = CharField
    description = TextField
    role_placeholder = CharField  # e.g., 'tech_lead', 'worship_leader'
    relative_due_offset_days = IntegerField  # -3 = 3 days before event
    checklist_items = JSONField  # list of strings
    order = PositiveIntegerField

class ChecklistTemplate(models.Model):
    organization = ForeignKey(Organization)
    name = CharField
    items = JSONField  # list of {text, ...}
    created_by = ForeignKey(User)

class ProjectDiscussion(models.Model):
    organization = ForeignKey(Organization)
    project = ForeignKey(Project, related_name='discussions')
    title = CharField
    created_by = ForeignKey(User)
    is_resolved = BooleanField(default=False)
    resolved_at = DateTimeField(null=True)
    resolved_by = ForeignKey(User, null=True)
    created_at = DateTimeField(auto_now_add=True)

class ProjectDiscussionMessage(models.Model):
    discussion = ForeignKey(ProjectDiscussion, related_name='messages')
    author = ForeignKey(User)
    content = TextField
    parent = ForeignKey('self', null=True)  # threading
    mentioned_users = ManyToManyField(User)
    linked_tasks = ManyToManyField(Task, related_name='linked_discussions')
    is_decision = BooleanField(default=False)
    decision_marked_by = ForeignKey(User, null=True)
    decision_marked_at = DateTimeField(null=True)
    created_at = DateTimeField(auto_now_add=True)

class RecurringTaskRule(models.Model):
    organization = ForeignKey(Organization)
    project = ForeignKey(Project, null=True)
    title = CharField
    description = TextField
    checklist_template = ForeignKey(ChecklistTemplate, null=True)
    assignees = ManyToManyField(User)
    recurrence_pattern = CharField  # 'weekly', 'monthly', 'pco_service'
    offset_days = IntegerField(default=0)
    service_type_id = CharField(blank=True)  # PCO service type
    day_of_week = IntegerField(null=True)  # 0-6 for weekly
    last_generated_at = DateTimeField(null=True)
    is_active = BooleanField(default=True)
    created_by = ForeignKey(User)

class TaskReadState(models.Model):
    user = ForeignKey(User)
    task = ForeignKey(Task)
    last_read_at = DateTimeField
    class Meta:
        unique_together = ('user', 'task')

class DiscussionReadState(models.Model):
    user = ForeignKey(User)
    discussion = ForeignKey(ProjectDiscussion)
    last_read_at = DateTimeField
    class Meta:
        unique_together = ('user', 'discussion')

class TaskWatcher(models.Model):
    user = ForeignKey(User)
    task = ForeignKey(Task)
    created_at = DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('user', 'task')
```

### Extended models

```python
# Task
checklist = JSONField(default=list)  # [{text, done, done_by, done_at}, ...]
recurring_rule = ForeignKey(RecurringTaskRule, null=True)
is_recurring_instance = BooleanField(default=False)

# TaskComment
is_decision = BooleanField(default=False)
decision_marked_by = ForeignKey(User, null=True, related_name='decisions_marked')
decision_marked_at = DateTimeField(null=True)

# NotificationPreference
task_comment_on_assigned = BooleanField(default=True)
task_comment_on_watched = BooleanField(default=True)
decision_notifications = BooleanField(default=True)
daily_digest_enabled = BooleanField(default=False)
daily_digest_time = TimeField(default='08:00')
```

### Migration strategy

- All migrations additive. No data loss.
- Existing projects/tasks/comments continue to work unchanged.
- On first deploy, treat existing task comments as "already read" for current users (populate TaskReadState with `last_read_at=now()`).

## 7. Files Touched

- `core/models.py` — new models + extensions
- `core/migrations/*` — new migration
- `core/views.py` — task detail redesign, discussion views, decision views, template views, watcher toggle, checklist toggle
- `core/agent.py` — new query patterns for task/decision queries
- `core/notifications.py` — task comment + decision notification helpers, digest generation
- `core/management/commands/generate_recurring_tasks.py` — new nightly command
- `core/management/commands/send_daily_digests.py` — new daily command
- `templates/core/comms/task_detail.html` — major redesign
- `templates/core/comms/project_detail.html` — add tabs for Discussions, Decisions
- `templates/core/comms/discussion_*.html` — new discussion templates
- `templates/core/comms/decisions_tab.html` — new decisions list
- `templates/core/comms/templates/*.html` — new template management UI
- `templates/core/comms/recurring_*.html` — new recurring rule UI
- `core/urls.py` — new URL routes
- `tests/test_task_conversations.py` — new tests
- `tests/test_discussions.py` — new tests
- `tests/test_templates.py` — new tests
- `tests/test_recurring.py` — new tests

## 8. Build Order

Each phase is independently shippable.

**Phase 1 — Conversation-First Tasks** (core fix)
- Task detail redesign
- TaskComment.is_decision field + UI
- TaskReadState + unread badges
- TaskWatcher + watch button
- Task.checklist field + inline UI
- Notification preference extensions

**Phase 2 — Project Discussions & Decisions**
- ProjectDiscussion + ProjectDiscussionMessage models
- Project tabs (Tasks | Discussions | Decisions | Files)
- Discussion thread UI, @mentions, reactions, task linking
- Decisions tab aggregating across comments + discussions
- Resolve/unresolve discussions

**Phase 3 — Templates**
- ProjectTemplate + ProjectTemplateTask models
- Create-from-template flow with event date
- ChecklistTemplate model + reuse
- 2-3 default templates shipped

**Phase 4 — Recurring Tasks**
- RecurringTaskRule model
- Nightly generation command
- Rule UI (create/edit)
- PCO-service-linked recurrence

**Phase 5 — Aria AI Integration**
- Task/project/decision query patterns in agent.py
- Task data in searchable context
- Auto-task creation from interaction logs

**Phase 6 — Digest Notifications**
- Daily digest generation command
- Opt-in preference
- Push + email delivery

## 9. Testing Strategy

- **Model tests:** CRUD, tenant isolation, read-state correctness, recurring task generation
- **View tests:** Task detail renders comments prominently, unread badges correct, decision marking, discussion threading, template resolution
- **Integration tests:** End-to-end task-create → comment → mark-decision → see-in-Decisions-tab flow; recurring rule → nightly command → task generated
- **Agent tests:** New query patterns detected correctly, task data included in responses, decision search works
- Target: add ~50 new tests, maintain 0 failures in existing 452-test suite

## 10. Success Criteria

- Team stops using Todoist entirely within 2 weeks of Phase 1+2 shipping
- Zero reports of "I didn't see that comment" after Phase 1
- "Decisions" tab is used weekly (measurable via view counts)
- Template usage covers 80%+ of repeating event setup (Sunday services, special events)
- Aria successfully answers "what's on my plate?" and decision-search queries (measured via feedback system)

## Open Questions

None at this time — all scope questions resolved during brainstorming.
