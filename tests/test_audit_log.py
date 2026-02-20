"""Tests for the AuditLog model."""
import pytest
from django.test import TestCase
from core.models import AuditLog, Organization
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
