"""
Tests for Phase 2: Project Discussions & Decisions.
"""
import pytest
from django.utils import timezone
from django.urls import reverse


@pytest.mark.django_db
class TestProjectDiscussionModel:
    """Tests for the ProjectDiscussion model."""

    def test_create_discussion(self, user_alpha_owner, org_alpha):
        """Discussion is created with title, project, creator, defaults."""
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        discussion = ProjectDiscussion.objects.create(
            organization=org_alpha,
            project=project,
            title='Stage layout change',
            created_by=user_alpha_owner,
        )

        assert discussion.organization == org_alpha
        assert discussion.project == project
        assert discussion.title == 'Stage layout change'
        assert discussion.created_by == user_alpha_owner
        assert discussion.is_resolved is False
        assert discussion.resolved_at is None
        assert discussion.resolved_by is None
        assert discussion.created_at is not None

    def test_discussion_inherits_org_from_project(self, user_alpha_owner, org_alpha):
        """If organization is not set explicitly, save pulls it from project."""
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(
            organization=org_alpha, name='P', owner=user_alpha_owner,
        )
        discussion = ProjectDiscussion(
            project=project,
            title='Test',
            created_by=user_alpha_owner,
        )
        discussion.save()
        assert discussion.organization == org_alpha
