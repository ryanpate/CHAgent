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


@pytest.mark.django_db
class TestPCOGetNextOccurrences:
    """Tests for get_next_occurrences when recurrence_type='pco_service'."""

    def test_pco_returns_service_dates(
        self, user_alpha_owner, org_alpha, monkeypatch
    ):
        """get_next_occurrences queries PCO and returns plan dates minus offset."""
        from datetime import date
        from core.models import Project, TaskTemplate

        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        template = TaskTemplate.objects.create(
            name='PCO',
            title_template='Prep {month} {day}',
            project=project,
            recurrence_type='pco_service',
            pco_service_type_id='srv-123',
            pco_days_before_service=2,
            created_by=user_alpha_owner,
        )

        # Mock the PCO API so the test doesn't hit the network
        mock_plans = [
            {'sort_date': '2026-04-05T10:00:00Z'},  # Sunday
            {'sort_date': '2026-04-12T10:00:00Z'},  # Sunday
            {'sort_date': '2026-04-19T10:00:00Z'},  # Sunday
        ]
        def fake_fetch(self, service_type_id, start_date, end_date, limit=10):
            return mock_plans

        monkeypatch.setattr(
            'core.planning_center.PlanningCenterServicesAPI.get_plans_by_date_range',
            fake_fetch,
        )

        occurrences = template.get_next_occurrences(
            from_date=date(2026, 4, 1), count=3,
        )
        # Expected: each service date minus 2 days
        assert occurrences == [
            date(2026, 4, 3),
            date(2026, 4, 10),
            date(2026, 4, 17),
        ]

    def test_pco_handles_missing_service_type(
        self, user_alpha_owner, org_alpha,
    ):
        """Empty pco_service_type_id returns empty list."""
        from datetime import date
        from core.models import Project, TaskTemplate
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        template = TaskTemplate.objects.create(
            name='Bad', title_template='X', project=project,
            recurrence_type='pco_service', pco_service_type_id='',
            created_by=user_alpha_owner,
        )
        occurrences = template.get_next_occurrences(
            from_date=date(2026, 4, 1), count=3,
        )
        assert occurrences == []
