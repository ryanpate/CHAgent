"""Tests for PCO-service-linked TaskTemplate recurrence."""
import pytest
from django.utils import timezone


@pytest.mark.django_db
class TestPCOFields:
    """Tests for PCO-related fields on TaskTemplate."""

    def test_pco_fields_default_empty(self, user_alpha_owner, org_alpha):
        """New TaskTemplate has PCO fields with sensible defaults."""
        from core.models import Project, TaskTemplate
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        t = TaskTemplate.objects.create(
            name='Weekly',
            title_template='Prep {weekday}',
            project=project,
            recurrence_type='weekly',
            recurrence_days=[6],
            created_by=user_alpha_owner,
        )
        assert t.pco_service_type_id == ''
        assert t.pco_days_before_service == 0

    def test_pco_service_recurrence_choice(self, user_alpha_owner, org_alpha):
        """recurrence_type='pco_service' is a valid choice."""
        from core.models import Project, TaskTemplate
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        t = TaskTemplate.objects.create(
            name='PCO-linked',
            title_template='Service prep',
            project=project,
            recurrence_type='pco_service',
            pco_service_type_id='12345',
            pco_days_before_service=2,
            created_by=user_alpha_owner,
        )
        t.full_clean()  # Should not raise
        assert t.recurrence_type == 'pco_service'
        assert t.pco_service_type_id == '12345'
        assert t.pco_days_before_service == 2
