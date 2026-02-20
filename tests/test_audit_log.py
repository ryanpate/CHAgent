"""Tests for the AuditLog model."""
import pytest
from django.test import TestCase, Client
from core.models import AuditLog, Organization, OrganizationMembership
from accounts.models import User


class TestAuditLogModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin@test.com',
            email='admin@test.com',
            password='testpass123',
            is_superadmin=True,
        )
        self.org = Organization.objects.create(
            name='Test Church',
            slug='test-church',
            email='admin@testchurch.org',
        )

    def test_create_audit_log(self):
        log = AuditLog.objects.create(
            user=self.user,
            action='beta_approve',
            ip_address='127.0.0.1',
            organization=self.org,
            details={'church_name': 'Test Church'},
        )
        assert log.id is not None
        assert log.action == 'beta_approve'
        assert log.timestamp is not None

    def test_audit_log_str(self):
        log = AuditLog.objects.create(
            user=self.user,
            action='org_impersonate',
        )
        assert 'org_impersonate' in str(log)
        assert 'admin@test.com' in str(log)

    def test_audit_log_nullable_fields(self):
        log = AuditLog.objects.create(
            user=self.user,
            action='settings_updated',
        )
        assert log.organization is None
        assert log.target_user is None
        assert log.ip_address is None
        assert log.details == {}


class TestAuditLogIntegration(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='superadmin@test.com',
            email='superadmin@test.com',
            password='testpass123',
            is_superadmin=True,
        )
        self.org = Organization.objects.create(
            name='Test Church',
            slug='test-church',
            email='admin@testchurch.org',
        )
        OrganizationMembership.objects.create(
            user=self.admin,
            organization=self.org,
            role='owner',
            is_active=True,
        )
        self.admin.default_organization = self.org
        self.admin.save()

    def test_beta_approve_creates_audit_log(self):
        from core.models import BetaRequest
        beta_req = BetaRequest.objects.create(
            name='Test User',
            email='beta@test.com',
            church_name='Test Church',
            church_size='small',
        )
        self.client.force_login(self.admin)
        self.client.post(f'/platform-admin/beta-requests/{beta_req.pk}/approve/')
        assert AuditLog.objects.filter(action='beta_approve').exists()

    def test_impersonate_creates_audit_log(self):
        self.client.force_login(self.admin)
        self.client.get(f'/platform-admin/organizations/{self.org.id}/impersonate/')
        assert AuditLog.objects.filter(action='org_impersonate').exists()

    def test_role_change_creates_audit_log(self):
        member_user = User.objects.create_user(
            username='member@test.com',
            email='member@test.com',
            password='testpass123',
        )
        membership = OrganizationMembership.objects.create(
            user=member_user,
            organization=self.org,
            role='member',
            is_active=True,
        )
        self.client.force_login(self.admin)
        self.client.post(
            f'/settings/members/{membership.id}/role/',
            {'role': 'leader'},
        )
        assert AuditLog.objects.filter(action='user_role_change').exists()


class TestAuditLogAdminView(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='superadmin@test.com',
            email='superadmin@test.com',
            password='testpass123',
            is_superadmin=True,
        )

    def test_audit_log_page_accessible(self):
        """Superadmins can access the audit log page."""
        self.client.force_login(self.admin)
        response = self.client.get('/platform-admin/audit-log/')
        assert response.status_code == 200

    def test_audit_log_shows_entries(self):
        """Audit log page displays log entries."""
        AuditLog.objects.create(
            user=self.admin,
            action='beta_approve',
            details={'church_name': 'Test Church'},
        )
        self.client.force_login(self.admin)
        response = self.client.get('/platform-admin/audit-log/')
        assert b'beta_approve' in response.content or b'Beta Request Approved' in response.content

    def test_audit_log_non_admin_blocked(self):
        """Non-superadmins cannot access the audit log."""
        user = User.objects.create_user(
            username='regular@test.com',
            email='regular@test.com',
            password='testpass123',
        )
        self.client.force_login(user)
        response = self.client.get('/platform-admin/audit-log/')
        assert response.status_code == 403
