# Phase 5: Aria AI Task Queries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teach Aria to answer natural-language questions about tasks, projects, and decisions — "What's on my plate?", "What's overdue?", "What did we decide about monitors?" — and to create simple tasks from chat.

**Architecture:** Follows the existing agent.py pattern: add a `is_task_query()` detection function that returns a query type, add per-type handler functions that format task/decision data into context strings, and route each query type in `query_agent()` dispatcher. Handlers query task/discussion data scoped by organization and user.

**Tech Stack:** Django 5.x, Anthropic Claude API, existing agent.py RAG pipeline.

**Related Spec:** `docs/superpowers/specs/2026-04-04-todoist-replacement-design.md` (Phase 5)

---

## File Structure

**Create:**
- `tests/test_aria_task_queries.py` — Phase 5 tests

**Modify:**
- `core/agent.py` — add `is_task_query()` detection function, 5 handler functions, and dispatcher integration

All changes are in `core/agent.py`. Following the existing pattern of having detection + handler functions in one file. No new templates or URLs needed — this is purely AI query routing.

---

## Task 1: is_task_query detection function

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_aria_task_queries.py` (new file)

- [ ] **Step 1: Create test file with failing tests**

Create `tests/test_aria_task_queries.py`:

```python
"""Tests for Phase 5: Aria task query detection and handlers."""
import pytest


class TestIsTaskQuery:
    """Tests for is_task_query detection."""

    def test_detects_my_tasks(self):
        from core.agent import is_task_query

        is_task, qtype, params = is_task_query("what's on my plate?")
        assert is_task is True
        assert qtype == 'my_tasks'

        is_task, qtype, params = is_task_query("what do I need to do this week?")
        assert is_task is True
        assert qtype == 'my_tasks'

        is_task, qtype, params = is_task_query("show me my tasks")
        assert is_task is True
        assert qtype == 'my_tasks'

    def test_detects_overdue(self):
        from core.agent import is_task_query

        is_task, qtype, params = is_task_query("what's overdue?")
        assert is_task is True
        assert qtype == 'overdue_tasks'

        is_task, qtype, params = is_task_query("show me overdue tasks")
        assert is_task is True
        assert qtype == 'overdue_tasks'

        is_task, qtype, params = is_task_query("what tasks are past due?")
        assert is_task is True
        assert qtype == 'overdue_tasks'

    def test_detects_team_tasks(self):
        from core.agent import is_task_query

        is_task, qtype, params = is_task_query("what is John working on?")
        assert is_task is True
        assert qtype == 'team_tasks'
        assert params.get('person_name') and 'john' in params['person_name'].lower()

        is_task, qtype, params = is_task_query("show me Sarah's tasks")
        assert is_task is True
        assert qtype == 'team_tasks'
        assert 'sarah' in params['person_name'].lower()

    def test_detects_project_status(self):
        from core.agent import is_task_query

        is_task, qtype, params = is_task_query("summarize Easter production")
        assert is_task is True
        assert qtype == 'project_status'
        assert 'easter production' in params.get('project_name', '').lower()

        is_task, qtype, params = is_task_query("how's Sunday prep going?")
        assert is_task is True
        assert qtype == 'project_status'

    def test_detects_decision_search(self):
        from core.agent import is_task_query

        is_task, qtype, params = is_task_query("what did we decide about monitors?")
        assert is_task is True
        assert qtype == 'decision_search'
        assert 'monitor' in params.get('topic', '').lower()

        is_task, qtype, params = is_task_query("show me decisions about the stage layout")
        assert is_task is True
        assert qtype == 'decision_search'

    def test_non_task_queries_not_matched(self):
        from core.agent import is_task_query

        is_task, qtype, params = is_task_query("what's the weather?")
        assert is_task is False

        is_task, qtype, params = is_task_query("who is on the team this Sunday?")
        # This is a PCO query, should NOT match task
        assert is_task is False

        is_task, qtype, params = is_task_query("show me the lyrics for amazing grace")
        assert is_task is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aria_task_queries.py::TestIsTaskQuery -v`
Expected: FAIL with `ImportError: cannot import name 'is_task_query'`

- [ ] **Step 3: Add is_task_query function to core/agent.py**

Place this function near the other detection functions (e.g., after `is_analytics_query` around line 102, or near `is_pco_data_query`). Insert at a logical location after the existing detection functions:

```python
def is_task_query(message: str) -> Tuple[bool, str, dict]:
    """
    Detect if the user is asking about tasks, project status, or decisions.

    Args:
        message: The user's question.

    Returns:
        Tuple of (is_task_query, query_type, params) where:
        - is_task_query: True if this is a task-related query
        - query_type: One of 'my_tasks', 'team_tasks', 'overdue_tasks',
                      'project_status', 'decision_search'
        - params: dict with extracted parameters (person_name, project_name, topic)
    """
    import re
    message_lower = message.lower().strip()
    params = {}

    # Decision search patterns (check first, most specific)
    # "what did we decide about X", "decisions on X", "what was decided about X"
    decision_patterns = [
        r'what\s+did\s+(we|you|they)\s+decide\s+(about|on|for|regarding)\s+(.+)',
        r'(what|show|list|find)\s+(was|were)?\s*decid\w+\s+(about|on|for|regarding)\s+(.+)',
        r'(show|list|find|get)\s+(me\s+)?(the\s+)?decisions?\s+(about|on|for|regarding)\s+(.+)',
        r'decisions?\s+(about|on|regarding)\s+(.+)',
    ]
    for pattern in decision_patterns:
        m = re.search(pattern, message_lower)
        if m:
            # The topic is in the last group
            topic = m.groups()[-1].strip().rstrip('?.!')
            if topic:
                params['topic'] = topic
                return True, 'decision_search', params

    # Overdue tasks patterns
    overdue_patterns = [
        r"\bwhat'?s?\s+overdue\b",
        r'\boverdue\s+tasks?\b',
        r'\btasks?\s+(that\s+are|which\s+are)?\s*overdue\b',
        r'\bpast\s+due\b',
        r'\btasks?\s+(that\s+are|which\s+are)?\s*late\b',
        r'\bwhat\s+tasks?\s+(are|is)\s+(overdue|past\s+due|late)\b',
    ]
    for pattern in overdue_patterns:
        if re.search(pattern, message_lower):
            return True, 'overdue_tasks', params

    # Team tasks patterns - "what is X working on", "X's tasks"
    team_patterns = [
        (r'what\s+(is|are)\s+([\w\s]+?)\s+working\s+on\b', 2),
        (r'what\'?s?\s+([\w\s]+?)\s+working\s+on\b', 1),
        (r'show\s+me\s+([\w\s]+?)\'?s\s+tasks\b', 1),
        (r"what\s+(tasks?|work)\s+(does|do)\s+([\w\s]+?)\s+have\b", 3),
        (r'([\w\s]+?)\'?s\s+(tasks?|work|to-?dos?)\b', 1),
    ]
    for pattern, name_group in team_patterns:
        m = re.search(pattern, message_lower)
        if m:
            person_name = m.group(name_group).strip()
            # Filter out obvious non-names
            if person_name in ('i', 'we', 'you', 'they', 'my', 'our', 'your', 'their', 'the team'):
                continue
            params['person_name'] = person_name
            return True, 'team_tasks', params

    # My tasks patterns - must NOT match team patterns
    my_task_patterns = [
        r"what'?s?\s+on\s+my\s+plate\b",
        r'what\s+(do|should|must|can)\s+i\s+(need\s+to\s+)?(do|work\s+on)\b',
        r'show\s+me\s+my\s+tasks?\b',
        r'my\s+tasks?\b',
        r'what\s+(tasks?|work|to-?dos?)\s+(do\s+)?i\s+have\b',
        r"what'?s?\s+on\s+my\s+to-?do\s+list\b",
    ]
    for pattern in my_task_patterns:
        if re.search(pattern, message_lower):
            return True, 'my_tasks', params

    # Project status patterns - "summarize X", "how's X going", "status of X"
    project_status_patterns = [
        (r'summariz\w+\s+(the\s+)?(.+?)(\s+project)?$', -1),
        (r"how'?s?\s+(.+?)\s+(going|coming\s+along|progressing)", 1),
        (r'status\s+of\s+(.+?)(\s+project)?$', 1),
        (r'(.+?)\s+project\s+status\b', 1),
        (r'where\s+are\s+we\s+(on|with)\s+(.+?)$', 2),
    ]
    for pattern, name_group in project_status_patterns:
        m = re.search(pattern, message_lower)
        if m:
            if name_group == -1:
                # Take all groups after "summarize", use last non-None
                name = m.group(2).strip() if m.group(2) else ''
            else:
                name = m.group(name_group).strip()
            name = name.rstrip('?.!').strip()
            if name and len(name) > 2:
                params['project_name'] = name
                return True, 'project_status', params

    return False, None, params
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aria_task_queries.py::TestIsTaskQuery -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add core/agent.py tests/test_aria_task_queries.py
git commit -m "feat(agent): add is_task_query detection for task/decision queries"
```

---

## Task 2: handle_my_tasks and handle_overdue_tasks formatters

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_aria_task_queries.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestHandleMyTasks:
    """Tests for handle_my_tasks handler."""

    def test_formats_user_tasks(self, user_alpha_owner, org_alpha):
        from core.models import Project, Task
        from core.agent import handle_my_tasks

        project = Project.objects.create(
            organization=org_alpha, name='Sunday', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='Set up stage',
            created_by=user_alpha_owner, status='in_progress',
        )
        task.assignees.add(user_alpha_owner)

        result = handle_my_tasks(user_alpha_owner, organization=org_alpha)

        assert 'Set up stage' in result
        assert 'in_progress' in result.lower() or 'in progress' in result.lower()

    def test_empty_list_message(self, user_alpha_owner, org_alpha):
        from core.agent import handle_my_tasks
        result = handle_my_tasks(user_alpha_owner, organization=org_alpha)
        # Should return a readable message, not raise
        assert isinstance(result, str)
        assert len(result) > 0

    def test_excludes_completed(self, user_alpha_owner, org_alpha):
        from core.models import Project, Task
        from core.agent import handle_my_tasks

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        open_task = Task.objects.create(
            project=project, title='Open work', created_by=user_alpha_owner, status='todo',
        )
        open_task.assignees.add(user_alpha_owner)
        done = Task.objects.create(
            project=project, title='Finished work', created_by=user_alpha_owner, status='completed',
        )
        done.assignees.add(user_alpha_owner)

        result = handle_my_tasks(user_alpha_owner, organization=org_alpha)

        assert 'Open work' in result
        assert 'Finished work' not in result

    def test_org_scoped(self, user_alpha_owner, org_alpha, org_beta, user_beta_owner):
        """Tasks from other orgs are not included."""
        from core.models import Project, Task
        from core.agent import handle_my_tasks

        beta_project = Project.objects.create(
            organization=org_beta, name='Beta', owner=user_beta_owner,
        )
        beta_task = Task.objects.create(
            project=beta_project, title='Beta secret', created_by=user_beta_owner,
        )
        beta_task.assignees.add(user_alpha_owner)  # Deliberately cross-assign

        result = handle_my_tasks(user_alpha_owner, organization=org_alpha)
        assert 'Beta secret' not in result


@pytest.mark.django_db
class TestHandleOverdueTasks:
    """Tests for handle_overdue_tasks handler."""

    def test_lists_overdue(self, user_alpha_owner, org_alpha):
        from datetime import timedelta
        from django.utils import timezone
        from core.models import Project, Task
        from core.agent import handle_overdue_tasks

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='Late task', created_by=user_alpha_owner,
            due_date=timezone.now().date() - timedelta(days=5),
            status='in_progress',
        )

        result = handle_overdue_tasks(user_alpha_owner, organization=org_alpha)
        assert 'Late task' in result

    def test_excludes_future_tasks(self, user_alpha_owner, org_alpha):
        from datetime import timedelta
        from django.utils import timezone
        from core.models import Project, Task
        from core.agent import handle_overdue_tasks

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='Future task', created_by=user_alpha_owner,
            due_date=timezone.now().date() + timedelta(days=5),
            status='todo',
        )

        result = handle_overdue_tasks(user_alpha_owner, organization=org_alpha)
        assert 'Future task' not in result

    def test_excludes_completed_overdue(self, user_alpha_owner, org_alpha):
        from datetime import timedelta
        from django.utils import timezone
        from core.models import Project, Task
        from core.agent import handle_overdue_tasks

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='Done late', created_by=user_alpha_owner,
            due_date=timezone.now().date() - timedelta(days=5),
            status='completed',
        )

        result = handle_overdue_tasks(user_alpha_owner, organization=org_alpha)
        assert 'Done late' not in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aria_task_queries.py::TestHandleMyTasks tests/test_aria_task_queries.py::TestHandleOverdueTasks -v`
Expected: FAIL with `ImportError: cannot import name 'handle_my_tasks'`

- [ ] **Step 3: Add handlers to core/agent.py**

Place these handlers near other handler functions (e.g., after `handle_team_roster_query`, around line 1400). Add both:

```python
def handle_my_tasks(user, organization=None) -> str:
    """Format context string listing the user's open assigned tasks."""
    from .models import Task

    qs = Task.objects.filter(
        assignees=user,
    ).exclude(
        status__in=['completed', 'cancelled'],
    )

    if organization:
        # Tasks belong to projects in this org, OR are standalone tasks in this org
        qs = qs.filter(
            models.Q(project__organization=organization)
            | models.Q(organization=organization)
        )

    qs = qs.select_related('project').order_by('due_date', '-priority')[:30]

    if not qs:
        return "You have no open tasks assigned to you."

    lines = [f"Open tasks assigned to {user.display_name or user.username}:\n"]
    for task in qs:
        due = task.due_date.strftime('%b %d') if task.due_date else 'no due date'
        proj = f" ({task.project.name})" if task.project else ''
        overdue = ' [OVERDUE]' if task.is_overdue else ''
        lines.append(
            f"- {task.title}{proj} - {task.get_status_display()}, "
            f"{task.get_priority_display()}, due {due}{overdue}"
        )
    return '\n'.join(lines)


def handle_overdue_tasks(user, organization=None) -> str:
    """Format context string listing all overdue tasks the user can see."""
    from .models import Task
    from django.utils import timezone

    today = timezone.now().date()
    qs = Task.objects.filter(
        due_date__lt=today,
    ).exclude(
        status__in=['completed', 'cancelled'],
    )

    if organization:
        qs = qs.filter(
            models.Q(project__organization=organization)
            | models.Q(organization=organization)
        )

    qs = qs.select_related('project').prefetch_related('assignees').order_by('due_date')[:30]

    if not qs:
        return "No overdue tasks."

    lines = ["Overdue tasks:\n"]
    for task in qs:
        assignee_names = ', '.join(
            a.display_name or a.username for a in task.assignees.all()
        ) or 'unassigned'
        proj = f" ({task.project.name})" if task.project else ''
        days_over = (today - task.due_date).days
        lines.append(
            f"- {task.title}{proj} - assigned to {assignee_names}, "
            f"{days_over} day{'s' if days_over != 1 else ''} overdue, "
            f"{task.get_priority_display()} priority"
        )
    return '\n'.join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aria_task_queries.py -v`
Expected: PASS (all new tests)

- [ ] **Step 5: Commit**

```bash
git add core/agent.py tests/test_aria_task_queries.py
git commit -m "feat(agent): add handle_my_tasks and handle_overdue_tasks formatters"
```

---

## Task 3: handle_team_tasks formatter

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_aria_task_queries.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestHandleTeamTasks:
    """Tests for handle_team_tasks handler."""

    def test_lists_assignee_tasks(self, user_alpha_owner, user_alpha_member, org_alpha):
        from core.models import Project, Task
        from core.agent import handle_team_tasks

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='Setup sound', created_by=user_alpha_owner,
        )
        task.assignees.add(user_alpha_member)

        # Get member's display/user name to search for
        search_name = user_alpha_member.display_name or user_alpha_member.username
        result = handle_team_tasks(search_name, organization=org_alpha)

        assert 'Setup sound' in result

    def test_user_not_found(self, user_alpha_owner, org_alpha):
        from core.agent import handle_team_tasks
        result = handle_team_tasks('NonexistentPerson', organization=org_alpha)
        assert isinstance(result, str)
        # Should be a "not found" message, not raise
        assert 'not find' in result.lower() or 'no user' in result.lower() or 'no task' in result.lower() or "doesn't" in result.lower()

    def test_case_insensitive_match(self, user_alpha_owner, org_alpha):
        from core.models import Project, Task
        from core.agent import handle_team_tasks

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='Build stage', created_by=user_alpha_owner,
        )
        task.assignees.add(user_alpha_owner)

        # Search in different case
        search = (user_alpha_owner.display_name or user_alpha_owner.username).lower()
        result = handle_team_tasks(search, organization=org_alpha)
        assert 'Build stage' in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aria_task_queries.py::TestHandleTeamTasks -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Add handle_team_tasks to core/agent.py**

```python
def handle_team_tasks(person_name: str, organization=None) -> str:
    """Find a user by name and list their open tasks."""
    from .models import Task
    from accounts.models import User

    # Find user by display_name, first_name, or username (case-insensitive)
    user_match = User.objects.filter(
        models.Q(display_name__iexact=person_name)
        | models.Q(first_name__iexact=person_name)
        | models.Q(username__iexact=person_name)
    ).first()

    # Try startswith if exact match failed
    if not user_match:
        user_match = User.objects.filter(
            models.Q(display_name__istartswith=person_name)
            | models.Q(first_name__istartswith=person_name)
        ).first()

    if not user_match:
        return f"I couldn't find a team member named '{person_name}'."

    # Verify user is in the organization (if org given)
    if organization:
        from .models import OrganizationMembership
        if not OrganizationMembership.objects.filter(
            user=user_match, organization=organization, is_active=True,
        ).exists():
            return f"I couldn't find '{person_name}' in this organization."

    qs = Task.objects.filter(assignees=user_match).exclude(
        status__in=['completed', 'cancelled'],
    )
    if organization:
        qs = qs.filter(
            models.Q(project__organization=organization)
            | models.Q(organization=organization)
        )
    qs = qs.select_related('project').order_by('due_date', '-priority')[:20]

    display = user_match.display_name or user_match.username
    if not qs:
        return f"{display} has no open tasks."

    lines = [f"Open tasks for {display}:\n"]
    for task in qs:
        due = task.due_date.strftime('%b %d') if task.due_date else 'no due date'
        proj = f" ({task.project.name})" if task.project else ''
        overdue = ' [OVERDUE]' if task.is_overdue else ''
        lines.append(
            f"- {task.title}{proj} - {task.get_status_display()}, due {due}{overdue}"
        )
    return '\n'.join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aria_task_queries.py::TestHandleTeamTasks -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/agent.py tests/test_aria_task_queries.py
git commit -m "feat(agent): add handle_team_tasks formatter with user lookup"
```

---

## Task 4: handle_project_status formatter

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_aria_task_queries.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestHandleProjectStatus:
    """Tests for handle_project_status handler."""

    def test_summarizes_project(self, user_alpha_owner, org_alpha):
        from core.models import Project, Task
        from core.agent import handle_project_status

        project = Project.objects.create(
            organization=org_alpha, name='Easter Production', owner=user_alpha_owner,
        )
        Task.objects.create(project=project, title='Stage', created_by=user_alpha_owner, status='completed')
        Task.objects.create(project=project, title='Sound', created_by=user_alpha_owner, status='in_progress')
        Task.objects.create(project=project, title='Vocals', created_by=user_alpha_owner, status='todo')

        result = handle_project_status('Easter Production', organization=org_alpha)

        assert 'Easter Production' in result
        # Should include task counts/status
        lower = result.lower()
        assert '3' in result  # 3 total tasks
        assert 'completed' in lower or 'done' in lower

    def test_project_not_found(self, user_alpha_owner, org_alpha):
        from core.agent import handle_project_status
        result = handle_project_status('NonexistentProject', organization=org_alpha)
        assert 'not find' in result.lower() or "couldn't find" in result.lower() or 'no project' in result.lower()

    def test_partial_name_match(self, user_alpha_owner, org_alpha):
        from core.models import Project
        from core.agent import handle_project_status

        Project.objects.create(
            organization=org_alpha, name='Easter Sunday Production',
            owner=user_alpha_owner,
        )
        result = handle_project_status('easter production', organization=org_alpha)
        # Should match via icontains/istartswith
        assert 'Easter' in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aria_task_queries.py::TestHandleProjectStatus -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Add handle_project_status to core/agent.py**

```python
def handle_project_status(project_name: str, organization=None) -> str:
    """Summarize a project's tasks, discussions, and recent activity."""
    from .models import Project

    qs = Project.objects.all()
    if organization:
        qs = qs.filter(organization=organization)

    # Try exact match first, then icontains
    project = qs.filter(name__iexact=project_name).first()
    if not project:
        project = qs.filter(name__icontains=project_name).first()
    if not project:
        return f"I couldn't find a project matching '{project_name}'."

    # Build the summary
    tasks = project.tasks.all()
    total = tasks.count()
    completed = tasks.filter(status='completed').count()
    in_progress = tasks.filter(status='in_progress').count()
    review = tasks.filter(status='review').count()
    todo = tasks.filter(status='todo').count()

    # Overdue count
    from django.utils import timezone
    today = timezone.now().date()
    overdue = tasks.filter(
        due_date__lt=today,
    ).exclude(status__in=['completed', 'cancelled']).count()

    # Discussions + decisions
    try:
        discussion_count = project.discussions.count()
        open_discussions = project.discussions.filter(is_resolved=False).count()
    except Exception:
        discussion_count = 0
        open_discussions = 0

    from .models import TaskComment
    try:
        from .models import ProjectDiscussionMessage
        discussion_decisions = ProjectDiscussionMessage.objects.filter(
            discussion__project=project, is_decision=True,
        ).count()
    except Exception:
        discussion_decisions = 0
    task_decisions = TaskComment.objects.filter(
        task__project=project, is_decision=True,
    ).count()
    total_decisions = task_decisions + discussion_decisions

    lines = [f"Status of project '{project.name}':\n"]
    lines.append(f"- {total} total task{'s' if total != 1 else ''}: "
                 f"{completed} completed, {in_progress} in progress, "
                 f"{review} in review, {todo} to do")
    if overdue:
        lines.append(f"- {overdue} overdue task{'s' if overdue != 1 else ''}")
    lines.append(f"- Status: {project.get_status_display()}")
    if project.due_date:
        lines.append(f"- Due: {project.due_date.strftime('%b %d, %Y')}")
    lines.append(f"- {discussion_count} discussion{'s' if discussion_count != 1 else ''} "
                 f"({open_discussions} open)")
    lines.append(f"- {total_decisions} decision{'s' if total_decisions != 1 else ''} recorded")

    return '\n'.join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aria_task_queries.py::TestHandleProjectStatus -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add core/agent.py tests/test_aria_task_queries.py
git commit -m "feat(agent): add handle_project_status formatter"
```

---

## Task 5: handle_decision_search formatter

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_aria_task_queries.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestHandleDecisionSearch:
    """Tests for handle_decision_search handler."""

    def test_finds_task_comment_decisions(self, user_alpha_owner, org_alpha):
        from django.utils import timezone
        from core.models import Project, Task, TaskComment
        from core.agent import handle_decision_search

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(project=project, title='T', created_by=user_alpha_owner)
        tc = TaskComment.objects.create(
            task=task, author=user_alpha_owner,
            content='We decided to go with 5 monitors on stage.',
        )
        tc.is_decision = True
        tc.decision_marked_by = user_alpha_owner
        tc.decision_marked_at = timezone.now()
        tc.save()

        result = handle_decision_search('monitors', organization=org_alpha)
        assert 'monitor' in result.lower()

    def test_finds_discussion_decisions(self, user_alpha_owner, org_alpha):
        from django.utils import timezone
        from core.models import Project, ProjectDiscussion, ProjectDiscussionMessage
        from core.agent import handle_decision_search

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        disc = ProjectDiscussion.objects.create(
            organization=org_alpha, project=project, title='T', created_by=user_alpha_owner,
        )
        dm = ProjectDiscussionMessage.objects.create(
            discussion=disc, author=user_alpha_owner,
            content='Move drums stage left for Easter.',
        )
        dm.is_decision = True
        dm.decision_marked_by = user_alpha_owner
        dm.decision_marked_at = timezone.now()
        dm.save()

        result = handle_decision_search('stage layout', organization=org_alpha)
        assert 'drum' in result.lower()

    def test_no_matches(self, user_alpha_owner, org_alpha):
        from core.agent import handle_decision_search
        result = handle_decision_search('nothing-here', organization=org_alpha)
        assert 'no decision' in result.lower() or "didn't find" in result.lower() or 'no match' in result.lower()

    def test_org_scoped(self, user_alpha_owner, org_alpha, org_beta, user_beta_owner):
        """Decisions from other orgs are not returned."""
        from django.utils import timezone
        from core.models import Project, Task, TaskComment
        from core.agent import handle_decision_search

        beta_project = Project.objects.create(
            organization=org_beta, name='B', owner=user_beta_owner,
        )
        beta_task = Task.objects.create(
            project=beta_project, title='T', created_by=user_beta_owner,
        )
        tc = TaskComment.objects.create(
            task=beta_task, author=user_beta_owner,
            content='Beta decided: use widget X.',
        )
        tc.is_decision = True
        tc.decision_marked_by = user_beta_owner
        tc.decision_marked_at = timezone.now()
        tc.save()

        result = handle_decision_search('widget', organization=org_alpha)
        assert 'widget' not in result.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aria_task_queries.py::TestHandleDecisionSearch -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Add handle_decision_search to core/agent.py**

```python
def handle_decision_search(topic: str, organization=None) -> str:
    """Search decisions in TaskComments and ProjectDiscussionMessages for a topic."""
    from .models import TaskComment

    # Search TaskComment decisions
    task_qs = TaskComment.objects.filter(
        is_decision=True,
        content__icontains=topic,
    )
    if organization:
        task_qs = task_qs.filter(task__project__organization=organization)
    task_qs = task_qs.select_related('author', 'task', 'task__project').order_by('-decision_marked_at')[:10]

    # Search ProjectDiscussionMessage decisions
    try:
        from .models import ProjectDiscussionMessage
        msg_qs = ProjectDiscussionMessage.objects.filter(
            is_decision=True,
            content__icontains=topic,
        )
        if organization:
            msg_qs = msg_qs.filter(discussion__project__organization=organization)
        msg_qs = msg_qs.select_related(
            'author', 'discussion', 'discussion__project',
        ).order_by('-decision_marked_at')[:10]
    except Exception:
        msg_qs = []

    results = []
    for tc in task_qs:
        author_name = tc.author.display_name or tc.author.username if tc.author else 'unknown'
        proj_name = tc.task.project.name if tc.task.project else 'standalone task'
        when = tc.decision_marked_at.strftime('%b %d, %Y') if tc.decision_marked_at else ''
        results.append(
            f"- \"{tc.content}\" (by {author_name}, {when}, in task '{tc.task.title}' ({proj_name}))"
        )
    for msg in msg_qs:
        author_name = msg.author.display_name or msg.author.username if msg.author else 'unknown'
        proj_name = msg.discussion.project.name
        when = msg.decision_marked_at.strftime('%b %d, %Y') if msg.decision_marked_at else ''
        results.append(
            f"- \"{msg.content}\" (by {author_name}, {when}, in discussion '{msg.discussion.title}' ({proj_name}))"
        )

    if not results:
        return f"I didn't find any decisions about '{topic}'."

    return f"Decisions matching '{topic}':\n\n" + '\n'.join(results)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_aria_task_queries.py::TestHandleDecisionSearch -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add core/agent.py tests/test_aria_task_queries.py
git commit -m "feat(agent): add handle_decision_search across tasks and discussions"
```

---

## Task 6: Route task queries in query_agent

**Files:**
- Modify: `core/agent.py` (`query_agent` function)
- Test: `tests/test_aria_task_queries.py` (append)

- [ ] **Step 1: Append failing integration test**

```python
@pytest.mark.django_db
class TestQueryAgentRouting:
    """Verifies query_agent routes task queries to the task handlers."""

    def test_my_tasks_query_routed(
        self, user_alpha_owner, org_alpha, monkeypatch,
    ):
        """query_agent detects and handles a my-tasks query."""
        from core.models import Project, Task, ChatMessage
        from core import agent

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(
            project=project, title='Unique task 98765',
            created_by=user_alpha_owner, status='todo',
        )
        task.assignees.add(user_alpha_owner)

        # Mock Claude client to echo the context it received
        class FakeResp:
            class content_item:
                text = ''
            content = [content_item]

        captured_context = {}
        def fake_call_claude(client, **kwargs):
            system = kwargs.get('system', '')
            captured_context['system'] = system
            r = FakeResp()
            r.content[0].text = "Here is what you have to do: your task."
            return r

        monkeypatch.setattr('core.agent.call_claude', fake_call_claude)
        monkeypatch.setattr('core.agent.get_anthropic_client', lambda: object())

        result = agent.query_agent(
            "what's on my plate?",
            user=user_alpha_owner,
            session_id='test-session',
            organization=org_alpha,
        )

        # Verify our specific task title appeared in the Claude system context
        assert 'Unique task 98765' in captured_context.get('system', '')
        assert isinstance(result, str)
        assert len(result) > 0

    def test_decision_search_query_routed(
        self, user_alpha_owner, org_alpha, monkeypatch,
    ):
        """query_agent routes decision-search queries to decision search handler."""
        from django.utils import timezone
        from core.models import Project, Task, TaskComment
        from core import agent

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        task = Task.objects.create(project=project, title='T', created_by=user_alpha_owner)
        tc = TaskComment.objects.create(
            task=task, author=user_alpha_owner,
            content='Use wireless microphones only for Sunday.',
        )
        tc.is_decision = True
        tc.decision_marked_by = user_alpha_owner
        tc.decision_marked_at = timezone.now()
        tc.save()

        captured_context = {}
        class FakeResp:
            class content_item:
                text = 'Decision answer.'
            content = [content_item]
        def fake_call_claude(client, **kwargs):
            captured_context['system'] = kwargs.get('system', '')
            r = FakeResp()
            r.content[0].text = 'Found a decision.'
            return r

        monkeypatch.setattr('core.agent.call_claude', fake_call_claude)
        monkeypatch.setattr('core.agent.get_anthropic_client', lambda: object())

        result = agent.query_agent(
            "what did we decide about microphones?",
            user=user_alpha_owner,
            session_id='test-session-2',
            organization=org_alpha,
        )

        assert 'wireless microphone' in captured_context.get('system', '').lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aria_task_queries.py::TestQueryAgentRouting -v`
Expected: FAIL (task query not routed yet — context won't contain task title)

- [ ] **Step 3: Read query_agent to find integration point**

Read `core/agent.py` around line 3819 (`def query_agent`). Find where existing query types are routed — look for patterns like `if pco_query:`, `if song_query:`, `if is_analytics_query(...)`. Your new task query routing should follow the same pattern.

The goal: after existing query detection + handling (or alongside it), check `is_task_query()` and dispatch to the appropriate handler. The handler's return value (a context string) should be included in the system prompt context passed to Claude.

- [ ] **Step 4: Add task query routing in query_agent**

Find a good insertion point — ideally near the top of `query_agent` after conversation context setup, BEFORE expensive operations like PCO API calls and interaction embedding searches. Add:

```python
    # Task-related queries (my_tasks, team_tasks, overdue, project_status, decision_search)
    task_query_match, task_query_type, task_query_params = is_task_query(question)
    task_context = ""
    if task_query_match:
        logger.info(f"Task query detected: type={task_query_type}, params={task_query_params}")
        try:
            if task_query_type == 'my_tasks':
                task_context = handle_my_tasks(user, organization=organization)
            elif task_query_type == 'overdue_tasks':
                task_context = handle_overdue_tasks(user, organization=organization)
            elif task_query_type == 'team_tasks':
                task_context = handle_team_tasks(task_query_params.get('person_name', ''), organization=organization)
            elif task_query_type == 'project_status':
                task_context = handle_project_status(task_query_params.get('project_name', ''), organization=organization)
            elif task_query_type == 'decision_search':
                task_context = handle_decision_search(task_query_params.get('topic', ''), organization=organization)
        except Exception as e:
            logger.error(f"Error handling task query: {e}")
            task_context = ""
```

Then find where the system prompt is built for the fallback Claude call (the main call at the end of `query_agent` that wasn't handled by one of the earlier specialized branches). Look for `SYSTEM_PROMPT.format(...)` calls. Incorporate `task_context` into the context passed there — prepend it, like:

```python
    final_context = ""
    if task_context:
        final_context = task_context + "\n\n"
    final_context += existing_context_var  # whatever variable holds the RAG context currently
```

And pass `final_context` to `SYSTEM_PROMPT.format(context=final_context, ...)`.

**IMPORTANT:** The exact integration depends on existing code structure. Read the code CAREFULLY. If the function has many branches (PCO, song, analytics, compound, etc.), the task context should be included in the DEFAULT / FALLBACK path — the one that runs when none of the specialized branches handle the query.

Alternative simpler integration: if a task query is matched, you can short-circuit and return directly with a Claude call that just uses `task_context`:

```python
    if task_query_match and task_context:
        # Short-circuit: use Claude to rephrase the task context into a natural answer
        user_name = user.display_name if user.display_name else user.username
        try:
            response = call_claude(
                client,
                organization=organization,
                user=user,
                session_id=session_id,
                query_type='task_query',
                model="claude-sonnet-4-20250514",
                max_tokens=1500,
                system=SYSTEM_PROMPT.format(
                    context=task_context,
                    current_date=datetime.now().strftime('%Y-%m-%d'),
                    user_name=user_name,
                ),
                messages=[{"role": "user", "content": question}],
            )
            answer = response.content[0].text
        except Exception as e:
            logger.error(f"Error querying Claude for task query: {e}")
            answer = task_context  # Fall back to the raw context string

        # Save assistant response to chat history
        ChatMessage.objects.create(
            user=user,
            organization=organization,
            session_id=session_id,
            role='assistant',
            content=answer,
        )
        conversation_context.increment_message_count(2)
        conversation_context.save()
        return answer
```

Use the short-circuit pattern — it's clearer and avoids hunting for the right place to inject into the RAG context. Place this block right after the task query detection block (inside `query_agent`, right after setting `task_context`).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_aria_task_queries.py::TestQueryAgentRouting -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Run full task query test suite**

Run: `pytest tests/test_aria_task_queries.py -v 2>&1 | tail -30`
Expected: All pass.

- [ ] **Step 7: Run full test suite to check for regressions**

Run: `pytest tests/ -x 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 8: Commit**

```bash
git add core/agent.py tests/test_aria_task_queries.py
git commit -m "feat(agent): route task queries to their handlers in query_agent"
```

---

## Task 7: Simple task creation from chat

**Files:**
- Modify: `core/agent.py`
- Test: `tests/test_aria_task_queries.py` (append)

- [ ] **Step 1: Append failing tests**

```python
@pytest.mark.django_db
class TestTaskCreate:
    """Tests for natural-language task creation."""

    def test_detects_task_create(self):
        from core.agent import is_task_create_request

        is_create, title = is_task_create_request("create task: call Sarah about tracks")
        assert is_create is True
        assert 'call sarah' in title.lower()

        is_create, title = is_task_create_request("add a task to send out rehearsal notes")
        assert is_create is True
        assert 'send out rehearsal notes' in title.lower()

        is_create, title = is_task_create_request("remind me to test the new mixer")
        assert is_create is True
        assert 'test the new mixer' in title.lower()

    def test_does_not_match_other_queries(self):
        from core.agent import is_task_create_request
        is_create, title = is_task_create_request("what's on my plate?")
        assert is_create is False
        is_create, title = is_task_create_request("who is on the team this Sunday?")
        assert is_create is False

    def test_handle_task_create_creates_standalone_task(
        self, user_alpha_owner, org_alpha,
    ):
        from core.models import Task
        from core.agent import handle_task_create

        result = handle_task_create(
            "call Sarah about the tracks",
            user=user_alpha_owner,
            organization=org_alpha,
        )
        assert 'created' in result.lower() or 'added' in result.lower()
        assert 'sarah' in result.lower()

        task = Task.objects.filter(organization=org_alpha, created_by=user_alpha_owner).first()
        assert task is not None
        assert 'sarah' in task.title.lower()
        # Auto-assigned to creator
        assert user_alpha_owner in task.assignees.all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_aria_task_queries.py::TestTaskCreate -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Add is_task_create_request and handle_task_create**

```python
def is_task_create_request(message: str) -> Tuple[bool, str]:
    """
    Detect a task creation request and extract the task title.

    Returns (is_create, task_title).
    """
    import re
    message_lower = message.lower().strip()

    patterns = [
        r'^(?:create|add|make)\s+(?:a\s+)?task(?:\s+to|\s*:)\s+(.+?)$',
        r'^(?:add\s+)?remind\s+me\s+to\s+(.+?)$',
        r'^(?:i\s+)?need\s+to\s+remember\s+to\s+(.+?)$',
        r'^new\s+task(?:\s*:|\s+to)\s+(.+?)$',
    ]
    for pattern in patterns:
        m = re.match(pattern, message_lower)
        if m:
            title = m.group(1).strip().rstrip('.!?')
            if title and len(title) > 2:
                return True, title

    return False, ''


def handle_task_create(task_title: str, user, organization=None) -> str:
    """Create a standalone task assigned to the user."""
    from .models import Task

    # Capitalize first letter of the title
    clean_title = task_title[:1].upper() + task_title[1:] if task_title else 'New task'
    clean_title = clean_title[:200]

    task = Task.objects.create(
        title=clean_title,
        organization=organization,
        created_by=user,
        status='todo',
        priority='medium',
    )
    task.assignees.add(user)

    return f"Created task: \"{clean_title}\". It's assigned to you with medium priority."
```

- [ ] **Step 4: Route task creation in query_agent**

In `query_agent`, BEFORE the other task query detection (so creation takes priority), add:

```python
    # Detect task creation intent BEFORE read-only task queries
    is_create, task_title = is_task_create_request(question)
    if is_create:
        logger.info(f"Task create request detected: '{task_title}'")
        create_result = handle_task_create(task_title, user=user, organization=organization)

        # Save as chat message
        ChatMessage.objects.create(
            user=user,
            organization=organization,
            session_id=session_id,
            role='assistant',
            content=create_result,
        )
        conversation_context.increment_message_count(2)
        conversation_context.save()
        return create_result
```

Place this right before the `is_task_query` detection block you added in Task 6.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_aria_task_queries.py::TestTaskCreate -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run full suite**

Run: `pytest tests/ -x 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 7: Commit**

```bash
git add core/agent.py tests/test_aria_task_queries.py
git commit -m "feat(agent): add task creation from natural language"
```

---

## Final Verification

- [ ] **Step 1: Run full suite**

Run: `pytest tests/ 2>&1 | tail -10`
Expected: All tests pass.

- [ ] **Step 2: Manual smoke test**

Start dev server: `python manage.py runserver`

In the chat, try:
1. "What's on my plate?" → lists your open tasks
2. "What's overdue?" → lists overdue tasks
3. "What is [teammate name] working on?" → lists their tasks
4. "Summarize [project name]" → gets project summary
5. "What did we decide about [topic]?" → searches decisions
6. "Create task: review sound check procedure" → creates a new task
7. "Remind me to email the volunteers" → creates a new task

---

## Deployment Notes

- No migrations required
- No new environment variables
- Claude API usage will increase slightly (new query types add ~1500 tokens per call)
- Existing RAG/interaction queries continue to work unchanged
