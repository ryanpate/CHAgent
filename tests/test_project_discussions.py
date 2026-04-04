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


@pytest.mark.django_db
class TestProjectDiscussionMessageModel:
    """Tests for the ProjectDiscussionMessage model."""

    def _make_discussion(self, user, org):
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(
            organization=org, name='P', owner=user,
        )
        discussion = ProjectDiscussion.objects.create(
            organization=org, project=project, title='T', created_by=user,
        )
        return discussion

    def test_create_message(self, user_alpha_owner, org_alpha):
        """Message created with author, content, defaults."""
        from core.models import ProjectDiscussionMessage

        discussion = self._make_discussion(user_alpha_owner, org_alpha)
        msg = ProjectDiscussionMessage.objects.create(
            discussion=discussion,
            author=user_alpha_owner,
            content='First post',
        )
        assert msg.discussion == discussion
        assert msg.author == user_alpha_owner
        assert msg.content == 'First post'
        assert msg.parent is None
        assert msg.is_decision is False
        assert msg.decision_marked_by is None
        assert msg.decision_marked_at is None

    def test_threaded_reply(self, user_alpha_owner, org_alpha):
        """parent FK creates threaded replies."""
        from core.models import ProjectDiscussionMessage

        discussion = self._make_discussion(user_alpha_owner, org_alpha)
        root = ProjectDiscussionMessage.objects.create(
            discussion=discussion, author=user_alpha_owner, content='Root',
        )
        reply = ProjectDiscussionMessage.objects.create(
            discussion=discussion,
            author=user_alpha_owner,
            content='Reply',
            parent=root,
        )
        assert reply.parent == root
        assert list(root.replies.all()) == [reply]

    def test_link_tasks(self, user_alpha_owner, org_alpha):
        """Message can be linked to multiple tasks via M2M."""
        from core.models import Project, Task, ProjectDiscussionMessage

        discussion = self._make_discussion(user_alpha_owner, org_alpha)
        project = discussion.project
        task_a = Task.objects.create(project=project, title='A', created_by=user_alpha_owner)
        task_b = Task.objects.create(project=project, title='B', created_by=user_alpha_owner)

        msg = ProjectDiscussionMessage.objects.create(
            discussion=discussion, author=user_alpha_owner, content='Multi',
        )
        msg.linked_tasks.set([task_a, task_b])

        assert msg.linked_tasks.count() == 2
        assert task_a in msg.linked_tasks.all()

    def test_mark_as_decision(self, user_alpha_owner, org_alpha):
        """Decision fields can be set together."""
        from core.models import ProjectDiscussionMessage

        discussion = self._make_discussion(user_alpha_owner, org_alpha)
        msg = ProjectDiscussionMessage.objects.create(
            discussion=discussion, author=user_alpha_owner, content='Decide',
        )

        msg.is_decision = True
        msg.decision_marked_by = user_alpha_owner
        msg.decision_marked_at = timezone.now()
        msg.save()

        msg.refresh_from_db()
        assert msg.is_decision is True
        assert msg.decision_marked_by == user_alpha_owner
        assert msg.decision_marked_at is not None


@pytest.mark.django_db
class TestDiscussionListView:
    """Tests for the discussion list view."""

    def _setup(self, user, org):
        from core.models import Project, ProjectDiscussion
        project = Project.objects.create(
            organization=org, name='P', owner=user,
        )
        open_disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='Open one', created_by=user,
        )
        resolved_disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='Resolved one',
            created_by=user, is_resolved=True,
        )
        return project, open_disc, resolved_disc

    def test_list_view_renders(self, client, user_alpha_owner, org_alpha):
        """GET renders the list of discussions for a project."""
        project, open_disc, resolved_disc = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('discussion_list', args=[project.pk]))

        assert response.status_code == 200
        assert 'Open one' in response.content.decode()
        assert 'Resolved one' in response.content.decode()

    def test_list_view_denies_non_members(
        self, client, user_alpha_owner, user_beta_owner, org_alpha
    ):
        """Non-project-members cannot view the list."""
        project, _, _ = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.get(reverse('discussion_list', args=[project.pk]))

        assert response.status_code in (302, 403, 404)


@pytest.mark.django_db
class TestDiscussionCreateView:
    """Tests for creating new discussions."""

    def _project(self, user, org):
        from core.models import Project
        return Project.objects.create(organization=org, name='P', owner=user)

    def test_get_form(self, client, user_alpha_owner, org_alpha):
        """GET renders the new-discussion form."""
        project = self._project(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('discussion_create', args=[project.pk]))

        assert response.status_code == 200
        assert b'title' in response.content.lower()

    def test_post_creates_discussion(self, client, user_alpha_owner, org_alpha):
        """POST creates a ProjectDiscussion and redirects to it."""
        from core.models import ProjectDiscussion
        project = self._project(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.post(
            reverse('discussion_create', args=[project.pk]),
            {'title': 'New discussion topic'},
        )

        assert response.status_code == 302
        assert ProjectDiscussion.objects.filter(
            project=project, title='New discussion topic'
        ).exists()

    def test_post_empty_title_rejected(self, client, user_alpha_owner, org_alpha):
        """POST with empty title doesn't create a discussion."""
        from core.models import ProjectDiscussion
        project = self._project(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        client.post(reverse('discussion_create', args=[project.pk]), {'title': ''})

        assert not ProjectDiscussion.objects.filter(project=project).exists()

    def test_non_member_denied(self, client, user_alpha_owner, user_beta_owner, org_alpha):
        """Non-project-members cannot create discussions."""
        project = self._project(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.post(
            reverse('discussion_create', args=[project.pk]),
            {'title': 'Hack'},
        )

        assert response.status_code in (302, 403, 404)

@pytest.mark.django_db
class TestDiscussionDetailView:
    """Tests for the discussion detail/thread view."""

    def _setup(self, user, org):
        from core.models import Project, ProjectDiscussion, ProjectDiscussionMessage
        project = Project.objects.create(organization=org, name='P', owner=user)
        disc = ProjectDiscussion.objects.create(
            organization=org, project=project, title='Topic', created_by=user,
        )
        msg1 = ProjectDiscussionMessage.objects.create(
            discussion=disc, author=user, content='First reply',
        )
        return project, disc, msg1

    def test_detail_renders(self, client, user_alpha_owner, org_alpha):
        """GET renders discussion with its messages."""
        project, disc, msg = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_alpha_owner)

        response = client.get(reverse('discussion_detail', args=[project.pk, disc.pk]))

        assert response.status_code == 200
        body = response.content.decode()
        assert 'Topic' in body
        assert 'First reply' in body

    def test_non_member_denied(self, client, user_alpha_owner, user_beta_owner, org_alpha):
        project, disc, _ = self._setup(user_alpha_owner, org_alpha)
        client.force_login(user_beta_owner)

        response = client.get(reverse('discussion_detail', args=[project.pk, disc.pk]))

        assert response.status_code in (302, 403, 404)
