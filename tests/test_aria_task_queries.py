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
