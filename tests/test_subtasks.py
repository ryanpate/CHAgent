import pytest
from core.models import Task, Project


@pytest.mark.django_db
class TestSubtaskModel:
    def test_create_subtask_with_parent(self, user_alpha_owner, org_alpha):
        parent = Task.objects.create(
            organization=org_alpha,
            title='Parent Task',
            created_by=user_alpha_owner,
        )
        child = Task.objects.create(
            organization=org_alpha,
            title='Child Task',
            parent=parent,
            created_by=user_alpha_owner,
        )
        assert child.parent == parent
        assert child.parent_id == parent.pk
        assert parent.subtasks.count() == 1
        assert parent.subtasks.first() == child
