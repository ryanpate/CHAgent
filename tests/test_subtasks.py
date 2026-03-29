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

    def test_subtask_progress_counts(self, user_alpha_owner, org_alpha):
        parent = Task.objects.create(
            organization=org_alpha, title='Parent', created_by=user_alpha_owner,
        )
        Task.objects.create(
            title='Done', parent=parent, status='completed', created_by=user_alpha_owner,
        )
        Task.objects.create(
            title='Done 2', parent=parent, status='completed', created_by=user_alpha_owner,
        )
        Task.objects.create(
            title='Todo', parent=parent, status='todo', created_by=user_alpha_owner,
        )
        completed, total = parent.subtask_progress
        assert total == 3
        assert completed == 2

    def test_subtask_progress_no_children(self, user_alpha_owner, org_alpha):
        task = Task.objects.create(
            organization=org_alpha, title='Leaf', created_by=user_alpha_owner,
        )
        completed, total = task.subtask_progress
        assert total == 0
        assert completed == 0

    def test_cascade_delete_removes_subtasks(self, user_alpha_owner, org_alpha):
        parent = Task.objects.create(
            organization=org_alpha, title='Parent', created_by=user_alpha_owner,
        )
        child = Task.objects.create(
            title='Child', parent=parent, created_by=user_alpha_owner,
        )
        grandchild = Task.objects.create(
            title='Grandchild', parent=child, created_by=user_alpha_owner,
        )
        parent.delete()
        assert not Task.objects.filter(pk=child.pk).exists()
        assert not Task.objects.filter(pk=grandchild.pk).exists()


@pytest.mark.django_db
class TestSubtaskViews:
    def test_create_subtask_inherits_project(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        project = Project.objects.create(
            organization=org_alpha, name='Easter', owner=user_alpha_owner,
        )
        parent = Task.objects.create(
            project=project, title='Stage Setup', created_by=user_alpha_owner,
        )
        response = client.post(
            f'/tasks/{parent.pk}/subtasks/create/',
            {'title': 'Lighting Rig'},
        )
        assert response.status_code in (200, 302)
        child = Task.objects.get(title='Lighting Rig')
        assert child.parent == parent
        assert child.project == project
        assert child.organization == org_alpha

    def test_create_subtask_standalone(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        parent = Task.objects.create(
            organization=org_alpha, title='Standalone Parent', created_by=user_alpha_owner,
        )
        response = client.post(
            f'/tasks/{parent.pk}/subtasks/create/',
            {'title': 'Standalone Child'},
        )
        assert response.status_code in (200, 302)
        child = Task.objects.get(title='Standalone Child')
        assert child.parent == parent
        assert child.organization == org_alpha
        assert child.project is None

    def test_create_subtask_with_assignee(self, client, user_alpha_owner, user_alpha_member, org_alpha):
        client.force_login(user_alpha_owner)
        parent = Task.objects.create(
            organization=org_alpha, title='Parent', created_by=user_alpha_owner,
        )
        response = client.post(
            f'/tasks/{parent.pk}/subtasks/create/',
            {'title': 'Assigned Sub', 'assignees': [user_alpha_member.pk]},
        )
        assert response.status_code in (200, 302)
        child = Task.objects.get(title='Assigned Sub')
        assert user_alpha_member in child.assignees.all()

    def test_create_subtask_empty_title_rejected(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        parent = Task.objects.create(
            organization=org_alpha, title='Parent', created_by=user_alpha_owner,
        )
        response = client.post(
            f'/tasks/{parent.pk}/subtasks/create/',
            {'title': ''},
        )
        assert Task.objects.filter(parent=parent).count() == 0

    def test_create_subtask_org_isolation(self, client, user_alpha_owner, org_beta):
        """Cannot create subtask on task from different org."""
        from core.models import Task as TaskModel
        client.force_login(user_alpha_owner)
        other_task = TaskModel.objects.create(
            organization=org_beta, title='Other Org Task',
            created_by=user_alpha_owner,
        )
        response = client.post(
            f'/tasks/{other_task.pk}/subtasks/create/',
            {'title': 'Sneaky Sub'},
        )
        assert response.status_code == 404

    def test_subtasks_partial_returns_children(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        parent = Task.objects.create(
            organization=org_alpha, title='Parent', created_by=user_alpha_owner,
        )
        Task.objects.create(
            title='Child 1', parent=parent, created_by=user_alpha_owner,
        )
        Task.objects.create(
            title='Child 2', parent=parent, created_by=user_alpha_owner,
        )
        response = client.get(f'/tasks/{parent.pk}/subtasks/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Child 1' in content
        assert 'Child 2' in content

    def test_subtasks_partial_excludes_other_org(self, client, user_alpha_owner, org_beta):
        """Cannot load subtasks for a task in another org."""
        from core.models import Task as TaskModel
        client.force_login(user_alpha_owner)
        other_parent = TaskModel.objects.create(
            organization=org_beta, title='Other Parent', created_by=user_alpha_owner,
        )
        response = client.get(f'/tasks/{other_parent.pk}/subtasks/')
        assert response.status_code == 404

    def test_subtasks_partial_empty(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        parent = Task.objects.create(
            organization=org_alpha, title='No Kids', created_by=user_alpha_owner,
        )
        response = client.get(f'/tasks/{parent.pk}/subtasks/')
        assert response.status_code == 200

    def test_task_detail_shows_subtasks_section(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        project = Project.objects.create(
            organization=org_alpha, name='Easter', owner=user_alpha_owner,
        )
        project.members.add(user_alpha_owner)
        parent = Task.objects.create(
            project=project, title='Stage Setup', created_by=user_alpha_owner,
        )
        Task.objects.create(
            title='Lights', parent=parent, status='completed', created_by=user_alpha_owner,
        )
        Task.objects.create(
            title='Sound', parent=parent, status='todo', created_by=user_alpha_owner,
        )
        response = client.get(f'/comms/projects/{project.pk}/tasks/{parent.pk}/')
        content = response.content.decode()
        assert 'Subtasks' in content
        assert '1/2' in content
        assert 'Lights' in content
        assert 'Sound' in content

    def test_task_detail_ancestor_breadcrumbs(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        project = Project.objects.create(
            organization=org_alpha, name='Easter', owner=user_alpha_owner,
        )
        project.members.add(user_alpha_owner)
        grandparent = Task.objects.create(
            project=project, title='Stage', created_by=user_alpha_owner,
        )
        parent = Task.objects.create(
            title='Lighting', parent=grandparent, created_by=user_alpha_owner,
        )
        child = Task.objects.create(
            title='Front Wash', parent=parent, created_by=user_alpha_owner,
        )
        response = client.get(f'/comms/projects/{project.pk}/tasks/{child.pk}/')
        content = response.content.decode()
        assert 'Stage' in content
        assert 'Lighting' in content
        assert 'Front Wash' in content

    def test_completion_nudge_when_all_siblings_done(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        parent = Task.objects.create(
            organization=org_alpha, title='Parent', created_by=user_alpha_owner,
        )
        parent.assignees.add(user_alpha_owner)
        child1 = Task.objects.create(
            title='Child 1', parent=parent, status='completed', created_by=user_alpha_owner,
        )
        child1.assignees.add(user_alpha_owner)
        child2 = Task.objects.create(
            title='Child 2', parent=parent, status='todo', created_by=user_alpha_owner,
        )
        child2.assignees.add(user_alpha_owner)
        # Complete the last remaining subtask
        response = client.post(
            f'/tasks/{child2.pk}/status/',
            {'status': 'completed'},
            HTTP_HX_REQUEST='true',
        )
        content = response.content.decode()
        assert 'All subtasks done' in content

    def test_project_detail_shows_only_root_tasks(self, client, user_alpha_owner, org_alpha):
        client.force_login(user_alpha_owner)
        project = Project.objects.create(
            organization=org_alpha, name='Easter', owner=user_alpha_owner,
        )
        project.members.add(user_alpha_owner)
        root = Task.objects.create(
            project=project, title='Root Task', created_by=user_alpha_owner,
        )
        Task.objects.create(
            title='Child Task', parent=root, created_by=user_alpha_owner,
        )
        response = client.get(f'/comms/projects/{project.pk}/')
        content = response.content.decode()
        assert 'Root Task' in content
        assert 'Child Task' not in content
