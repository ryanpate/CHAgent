import pytest
from django.test import TestCase, Client
from core.models import TOTPDevice, Organization, OrganizationMembership
from accounts.models import User


class TestTOTPDeviceModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            password='testpass123',
        )

    def test_create_totp_device(self):
        """TOTPDevice can be created with a secret."""
        import pyotp
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(
            user=self.user,
            secret=secret,
        )
        assert device.id is not None
        assert device.is_verified is False
        assert device.backup_codes == []

    def test_totp_device_one_per_user(self):
        """Only one TOTPDevice per user (OneToOne)."""
        import pyotp
        TOTPDevice.objects.create(user=self.user, secret=pyotp.random_base32())
        with pytest.raises(Exception):
            TOTPDevice.objects.create(user=self.user, secret=pyotp.random_base32())

    def test_verify_code(self):
        """TOTPDevice can verify a valid TOTP code."""
        import pyotp
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(user=self.user, secret=secret)
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        assert device.verify_code(valid_code) is True

    def test_reject_invalid_code(self):
        """TOTPDevice rejects an invalid code."""
        import pyotp
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(user=self.user, secret=secret)
        assert device.verify_code('000000') is False

    def test_backup_code_usage(self):
        """Backup codes can be used once and are then consumed."""
        import pyotp
        from django.contrib.auth.hashers import make_password
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(
            user=self.user,
            secret=secret,
            backup_codes=[make_password('ABCD1234')],
        )
        assert device.verify_backup_code('ABCD1234') is True
        device.refresh_from_db()
        assert device.verify_backup_code('ABCD1234') is False  # Used up


class TestTOTPSetupViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            password='testpass123',
        )
        self.org = Organization.objects.create(name='Test Church', slug='test-church')
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org, role='owner', is_active=True,
        )
        self.user.default_organization = self.org
        self.user.save()

    def test_security_settings_page(self):
        """Security settings page is accessible."""
        self.client.force_login(self.user)
        response = self.client.get('/settings/security/')
        assert response.status_code == 200
        assert b'Two-Factor' in response.content

    def test_totp_setup_page_shows_qr(self):
        """TOTP setup page shows QR code."""
        self.client.force_login(self.user)
        response = self.client.get('/settings/security/2fa/setup/')
        assert response.status_code == 200
        assert b'data:image/png' in response.content or b'qr' in response.content.lower()

    def test_totp_verify_setup_valid_code(self):
        """Valid TOTP code completes setup."""
        import pyotp
        self.client.force_login(self.user)
        # Start setup (creates unverified device)
        self.client.get('/settings/security/2fa/setup/')
        device = TOTPDevice.objects.get(user=self.user)
        totp = pyotp.TOTP(device.secret)
        response = self.client.post('/settings/security/2fa/verify-setup/', {
            'code': totp.now(),
        })
        device.refresh_from_db()
        assert device.is_verified is True

    def test_totp_disable(self):
        """Disabling 2FA deletes the device."""
        import pyotp
        secret = pyotp.random_base32()
        TOTPDevice.objects.create(user=self.user, secret=secret, is_verified=True)
        self.client.force_login(self.user)
        totp = pyotp.TOTP(secret)
        self.client.post('/settings/security/2fa/disable/', {
            'code': totp.now(),
        })
        assert not TOTPDevice.objects.filter(user=self.user).exists()
