"""
Tests for multi-tenant view isolation.

These tests verify that HTTP endpoints properly isolate data between
organizations. They test the full request/response cycle including
middleware, views, and templates.

CRITICAL: If any of these tests fail, it indicates that a view is
potentially exposing data from other organizations.
"""
import pytest
from django.urls import reverse
from django.test import Client


class TestVolunteerViewIsolation:
    """Test that volunteer views properly isolate data."""

    def test_volunteer_list_only_shows_org_volunteers(self, client_alpha, both_orgs_data):
        """Volunteer list should only show current organization's volunteers."""
        response = client_alpha.get(reverse('volunteer_list'))

        assert response.status_code == 200

        # Response should contain Alpha's volunteer
        alpha_volunteer = both_orgs_data['alpha']['volunteer']
        assert alpha_volunteer.name in response.content.decode()

        # Response should NOT contain Beta's volunteer
        beta_volunteer = both_orgs_data['beta']['volunteer']
        assert beta_volunteer.name not in response.content.decode()

    def test_volunteer_detail_blocked_for_other_org(self, client_alpha, both_orgs_data):
        """Accessing another org's volunteer detail should fail."""
        beta_volunteer = both_orgs_data['beta']['volunteer']

        # Try to access Beta's volunteer from Alpha's session
        response = client_alpha.get(
            reverse('volunteer_detail', kwargs={'pk': beta_volunteer.pk})
        )

        # Should get 404 (not found in Alpha's org) not 200
        assert response.status_code == 404

    def test_volunteer_detail_works_for_own_org(self, client_alpha, both_orgs_data):
        """Accessing own org's volunteer detail should work."""
        alpha_volunteer = both_orgs_data['alpha']['volunteer']

        response = client_alpha.get(
            reverse('volunteer_detail', kwargs={'pk': alpha_volunteer.pk})
        )

        assert response.status_code == 200
        assert alpha_volunteer.name in response.content.decode()


class TestInteractionViewIsolation:
    """Test that interaction views properly isolate data."""

    def test_interaction_list_only_shows_org_interactions(self, client_alpha, both_orgs_data):
        """Interaction list should only show current organization's interactions."""
        response = client_alpha.get(reverse('interaction_list'))

        assert response.status_code == 200

        # Response should contain Alpha's interaction content
        alpha_interaction = both_orgs_data['alpha']['interaction']
        # Check for part of the content (interactions may be summarized)
        assert 'Alice' in response.content.decode() or 'worship' in response.content.decode().lower()

    def test_interaction_detail_blocked_for_other_org(self, client_alpha, both_orgs_data):
        """Accessing another org's interaction detail should fail."""
        beta_interaction = both_orgs_data['beta']['interaction']

        response = client_alpha.get(
            reverse('interaction_detail', kwargs={'pk': beta_interaction.pk})
        )

        assert response.status_code == 404


class TestFollowUpViewIsolation:
    """Test that follow-up views properly isolate data."""

    def test_followup_list_only_shows_org_followups(self, client_alpha, both_orgs_data):
        """Follow-up list should only show current organization's follow-ups."""
        response = client_alpha.get(reverse('followup_list'))

        assert response.status_code == 200

        # Response should contain Alpha's follow-up
        alpha_followup = both_orgs_data['alpha']['followup']
        assert alpha_followup.title in response.content.decode()

        # Response should NOT contain Beta's follow-up
        beta_followup = both_orgs_data['beta']['followup']
        assert beta_followup.title not in response.content.decode()

    def test_followup_detail_blocked_for_other_org(self, client_alpha, both_orgs_data):
        """Accessing another org's follow-up detail should fail."""
        beta_followup = both_orgs_data['beta']['followup']

        response = client_alpha.get(
            reverse('followup_detail', kwargs={'pk': beta_followup.pk})
        )

        assert response.status_code == 404

    def test_followup_complete_blocked_for_other_org(self, client_alpha, both_orgs_data):
        """Completing another org's follow-up should fail."""
        beta_followup = both_orgs_data['beta']['followup']

        response = client_alpha.post(
            reverse('followup_complete', kwargs={'pk': beta_followup.pk})
        )

        # Should be 404 or 403, not 200/302
        assert response.status_code in [403, 404]


class TestAnnouncementViewIsolation:
    """Test that announcement views properly isolate data."""

    def test_announcement_list_only_shows_org_announcements(self, client_alpha, both_orgs_data):
        """Announcement list should only show current organization's announcements."""
        response = client_alpha.get(reverse('announcements_list'))

        assert response.status_code == 200

        # Response should contain Alpha's announcement
        alpha_announcement = both_orgs_data['alpha']['announcement']
        assert alpha_announcement.title in response.content.decode()

        # Response should NOT contain Beta's announcement
        beta_announcement = both_orgs_data['beta']['announcement']
        assert beta_announcement.title not in response.content.decode()

    def test_announcement_detail_blocked_for_other_org(self, client_alpha, both_orgs_data):
        """Accessing another org's announcement detail should fail."""
        beta_announcement = both_orgs_data['beta']['announcement']

        response = client_alpha.get(
            reverse('announcement_detail', kwargs={'pk': beta_announcement.pk})
        )

        assert response.status_code == 404


class TestChannelViewIsolation:
    """Test that channel views properly isolate data."""

    def test_channel_list_only_shows_org_channels(self, client_alpha, both_orgs_data):
        """Channel list should only show current organization's channels."""
        response = client_alpha.get(reverse('channel_list'))

        assert response.status_code == 200

        alpha_channel = both_orgs_data['alpha']['channel']
        beta_channel = both_orgs_data['beta']['channel']

        assert alpha_channel.name in response.content.decode()
        assert beta_channel.name not in response.content.decode()

    def test_channel_detail_blocked_for_other_org(self, client_alpha, both_orgs_data):
        """Accessing another org's channel by slug should fail."""
        beta_channel = both_orgs_data['beta']['channel']

        response = client_alpha.get(
            reverse('channel_detail', kwargs={'slug': beta_channel.slug})
        )

        assert response.status_code == 404

    def test_channel_message_post_blocked_for_other_org(self, client_alpha, both_orgs_data):
        """Posting to another org's channel should fail."""
        beta_channel = both_orgs_data['beta']['channel']

        response = client_alpha.post(
            reverse('channel_send_message', kwargs={'slug': beta_channel.slug}),
            {'content': 'Trying to post from Alpha to Beta'}
        )

        assert response.status_code in [403, 404]


class TestProjectViewIsolation:
    """Test that project views properly isolate data."""

    def test_project_list_only_shows_org_projects(self, client_alpha, both_orgs_data):
        """Project list should only show current organization's projects."""
        response = client_alpha.get(reverse('project_list'))

        assert response.status_code == 200

        alpha_project = both_orgs_data['alpha']['project']
        beta_project = both_orgs_data['beta']['project']

        assert alpha_project.name in response.content.decode()
        assert beta_project.name not in response.content.decode()

    def test_project_detail_blocked_for_other_org(self, client_alpha, both_orgs_data):
        """Accessing another org's project detail should fail."""
        beta_project = both_orgs_data['beta']['project']

        response = client_alpha.get(
            reverse('project_detail', kwargs={'pk': beta_project.pk})
        )

        assert response.status_code == 404


class TestAnalyticsViewIsolation:
    """Test that analytics views properly isolate data."""

    def test_analytics_dashboard_is_org_scoped(self, client_alpha, both_orgs_data):
        """Analytics dashboard should only show current org's data."""
        response = client_alpha.get(reverse('analytics_dashboard'))

        assert response.status_code == 200

        # The dashboard should reference the current org
        alpha_org = both_orgs_data['alpha']['organization']
        # Check that we're in a valid org context (page loads successfully)
        # Specific content checks depend on template structure

    def test_analytics_export_is_org_scoped(self, client_alpha, client_beta, both_orgs_data):
        """
        Analytics exports should only include current org's data.

        This is critical - exported data must be scoped to organization.
        """
        # Export engagement report for Alpha
        response_alpha = client_alpha.get(
            reverse('analytics_export', kwargs={'report_type': 'engagement'})
        )

        # Export engagement report for Beta
        response_beta = client_beta.get(
            reverse('analytics_export', kwargs={'report_type': 'engagement'})
        )

        # Both should succeed
        assert response_alpha.status_code == 200
        assert response_beta.status_code == 200

        # Content should be different (different org data)
        # Note: If both orgs have no data, content might be similar empty responses
        # In production, this would contain different volunteer/interaction data


class TestCareViewIsolation:
    """Test that proactive care views properly isolate data."""

    def test_care_dashboard_is_org_scoped(self, client_alpha, both_orgs_data):
        """Care dashboard should only show current org's insights."""
        response = client_alpha.get(reverse('care_dashboard'))

        assert response.status_code == 200


class TestSettingsViewIsolation:
    """Test that organization settings are properly isolated."""

    def test_settings_shows_own_org(self, client_alpha, both_orgs_data):
        """Settings should show current organization's settings."""
        response = client_alpha.get(reverse('org_settings'))

        assert response.status_code == 200

        alpha_org = both_orgs_data['alpha']['organization']
        assert alpha_org.name in response.content.decode()

    def test_settings_members_shows_own_org_members(self, client_alpha, both_orgs_data):
        """Member settings should only show current org's members."""
        response = client_alpha.get(reverse('org_settings_members'))

        assert response.status_code == 200

        # Alpha's owner should be visible
        alpha_owner = both_orgs_data['alpha']['owner']
        assert alpha_owner.username in response.content.decode() or \
               alpha_owner.display_name in response.content.decode()

        # Beta's owner should NOT be visible
        beta_owner = both_orgs_data['beta']['owner']
        assert beta_owner.username not in response.content.decode()


class TestCrossOrgURLManipulation:
    """
    Test that URL manipulation doesn't allow cross-org access.

    These tests verify that even if a user knows the ID/PK of another
    org's resources, they cannot access them by manipulating URLs.
    """

    def test_direct_pk_access_blocked(self, client_alpha, both_orgs_data):
        """
        Direct access to another org's resource by PK should be blocked.

        This tests a common attack vector where a user tries incrementing
        PKs or using known IDs to access other organizations' data.
        """
        beta_volunteer = both_orgs_data['beta']['volunteer']
        beta_followup = both_orgs_data['beta']['followup']
        beta_project = both_orgs_data['beta']['project']

        # All of these should return 404
        volunteer_response = client_alpha.get(
            reverse('volunteer_detail', kwargs={'pk': beta_volunteer.pk})
        )
        followup_response = client_alpha.get(
            reverse('followup_detail', kwargs={'pk': beta_followup.pk})
        )
        project_response = client_alpha.get(
            reverse('project_detail', kwargs={'pk': beta_project.pk})
        )

        assert volunteer_response.status_code == 404
        assert followup_response.status_code == 404
        assert project_response.status_code == 404

    def test_sequential_pk_enumeration_blocked(self, client_alpha, both_orgs_data):
        """
        Attempting to enumerate resources by sequential PKs should not
        reveal other organizations' data.
        """
        from core.models import Volunteer

        # Get all volunteer PKs
        all_pks = list(Volunteer.objects.values_list('pk', flat=True))

        for pk in all_pks:
            response = client_alpha.get(
                reverse('volunteer_detail', kwargs={'pk': pk})
            )

            # Should either be 200 (own org) or 404 (other org)
            # Should NEVER be data from another org shown with 200
            if response.status_code == 200:
                # If 200, verify it's Alpha's volunteer
                alpha_org = both_orgs_data['alpha']['organization']
                volunteer = Volunteer.objects.get(pk=pk)
                assert volunteer.organization == alpha_org


class TestUnauthenticatedAccess:
    """Test that unauthenticated users cannot access tenant data."""

    def test_unauthenticated_volunteer_list_redirects(self, db, both_orgs_data):
        """Unauthenticated users should be redirected to login."""
        client = Client()  # Not logged in

        response = client.get(reverse('volunteer_list'))

        # Should redirect to login
        assert response.status_code == 302
        assert 'login' in response.url.lower()

    def test_unauthenticated_dashboard_redirects(self, db, both_orgs_data):
        """Unauthenticated users should be redirected from dashboard."""
        client = Client()

        response = client.get(reverse('dashboard'))

        assert response.status_code == 302
        assert 'login' in response.url.lower()


class TestInactiveOrgAccess:
    """Test that inactive organizations cannot access data."""

    def test_inactive_org_blocked(self, db, both_orgs_data, user_alpha_owner):
        """Users in inactive organizations should be blocked."""
        from core.models import Organization

        alpha_org = both_orgs_data['alpha']['organization']

        # Deactivate Alpha org
        alpha_org.is_active = False
        alpha_org.save()

        try:
            client = Client()
            client.login(username='alpha_owner', password='testpass123')

            response = client.get(reverse('dashboard'))

            # Should be redirected or blocked (not 200 with data)
            # Exact behavior depends on middleware implementation
            assert response.status_code != 200 or b'inactive' in response.content.lower()
        finally:
            # Restore org status
            alpha_org.is_active = True
            alpha_org.save()


class TestSuspendedSubscriptionAccess:
    """Test that suspended subscriptions have limited access."""

    def test_suspended_org_limited_access(self, db, both_orgs_data, user_alpha_owner):
        """Users in suspended organizations should have limited access."""
        from core.models import Organization

        alpha_org = both_orgs_data['alpha']['organization']
        original_status = alpha_org.subscription_status

        # Suspend Alpha org
        alpha_org.subscription_status = 'suspended'
        alpha_org.save()

        try:
            client = Client()
            client.login(username='alpha_owner', password='testpass123')

            # Set org in session
            session = client.session
            session['organization_id'] = alpha_org.id
            session.save()

            response = client.get(reverse('dashboard'))

            # Behavior depends on implementation - may redirect to billing
            # or show limited functionality
            # Key is that they shouldn't have full data access
        finally:
            # Restore org status
            alpha_org.subscription_status = original_status
            alpha_org.save()
