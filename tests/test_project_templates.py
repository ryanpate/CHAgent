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
