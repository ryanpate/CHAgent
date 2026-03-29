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

    def test_subtask_inherits_project_from_parent(self, user_alpha_owner, org_alpha):
        project = Project.objects.create(
            organization=org_alpha,
            name='Easter Weekend',
            owner=user_alpha_owner,
        )
        parent = Task.objects.create(
            project=project,
            organization=org_alpha,
            title='Stage Setup',
            created_by=user_alpha_owner,
        )
        child = Task.objects.create(
            title='Lighting',
            parent=parent,
            created_by=user_alpha_owner,
        )
        assert child.project == project
        assert child.organization == org_alpha

    def test_subtask_inherits_org_from_standalone_parent(self, user_alpha_owner, org_alpha):
        parent = Task.objects.create(
            organization=org_alpha,
            title='Standalone Parent',
            created_by=user_alpha_owner,
        )
        child = Task.objects.create(
            title='Standalone Child',
            parent=parent,
            created_by=user_alpha_owner,
        )
        assert child.organization == org_alpha
        assert child.project is None

    def test_circular_reference_rejected(self, user_alpha_owner, org_alpha):
        from django.core.exceptions import ValidationError
        task_a = Task.objects.create(
            organization=org_alpha,
            title='Task A',
            created_by=user_alpha_owner,
        )
        task_b = Task.objects.create(
            organization=org_alpha,
            title='Task B',
            parent=task_a,
            created_by=user_alpha_owner,
        )
        with pytest.raises(ValidationError, match="Circular subtask reference"):
            task_a.parent = task_b
            task_a.save()

    def test_deep_circular_reference_rejected(self, user_alpha_owner, org_alpha):
        from django.core.exceptions import ValidationError
        task_a = Task.objects.create(
            organization=org_alpha, title='A', created_by=user_alpha_owner,
        )
        task_b = Task.objects.create(
            organization=org_alpha, title='B', parent=task_a, created_by=user_alpha_owner,
        )
        task_c = Task.objects.create(
            organization=org_alpha, title='C', parent=task_b, created_by=user_alpha_owner,
        )
        with pytest.raises(ValidationError, match="Circular subtask reference"):
            task_a.parent = task_c
            task_a.save()

    def test_deep_nesting_works(self, user_alpha_owner, org_alpha):
        project = Project.objects.create(
            organization=org_alpha, name='Deep Project', owner=user_alpha_owner,
        )
        a = Task.objects.create(project=project, title='A', created_by=user_alpha_owner)
        b = Task.objects.create(title='B', parent=a, created_by=user_alpha_owner)
        c = Task.objects.create(title='C', parent=b, created_by=user_alpha_owner)
        d = Task.objects.create(title='D', parent=c, created_by=user_alpha_owner)
        assert d.parent == c
        assert c.parent == b
        assert b.parent == a
        assert d.project == project
        assert d.organization == org_alpha
