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

        search_name = user_alpha_member.display_name or user_alpha_member.username
        result = handle_team_tasks(search_name, organization=org_alpha)

        assert 'Setup sound' in result

    def test_user_not_found(self, user_alpha_owner, org_alpha):
        from core.agent import handle_team_tasks
        result = handle_team_tasks('NonexistentPerson', organization=org_alpha)
        assert isinstance(result, str)
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

        search = (user_alpha_owner.display_name or user_alpha_owner.username).lower()
        result = handle_team_tasks(search, organization=org_alpha)
        assert 'Build stage' in result


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
        lower = result.lower()
        assert '3' in result  # 3 total tasks
        assert 'completed' in lower or 'done' in lower

    def test_project_not_found(self, user_alpha_owner, org_alpha):
        from core.agent import handle_project_status
        result = handle_project_status('NonexistentProject', organization=org_alpha)
        assert 'not find' in result.lower() or "could not find" in result.lower() or 'no project' in result.lower()

    def test_partial_name_match(self, user_alpha_owner, org_alpha):
        from core.models import Project
        from core.agent import handle_project_status

        Project.objects.create(
            organization=org_alpha, name='Easter Sunday Production',
            owner=user_alpha_owner,
        )
        result = handle_project_status('easter production', organization=org_alpha)
        assert 'Easter' in result


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
        assert 'no decision' in result.lower() or "did not find" in result.lower() or "didn't find" in result.lower() or 'no match' in result.lower()

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
        # The "not found" message may echo the search term, but it must NOT
        # contain the beta org's decision content.
        assert 'beta decided' not in result.lower()


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

        captured_context = {}
        class FakeContentItem:
            text = ''
        class FakeResp:
            content = [FakeContentItem()]

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
        class FakeContentItem:
            text = 'Decision answer.'
        class FakeResp:
            content = [FakeContentItem()]
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
