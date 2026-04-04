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
