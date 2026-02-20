import pytest
from django.test import TestCase
from core.models import TOTPDevice
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
