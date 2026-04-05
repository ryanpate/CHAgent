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
