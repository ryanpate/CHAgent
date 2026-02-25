import pytest
from django.db import IntegrityError
from core.models import NativePushToken


@pytest.mark.django_db
class TestNativePushTokenModel:
    def test_create_ios_token(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='abc123-apns-token',
            platform='ios',
            device_name='iPhone 15',
        )
        assert token.platform == 'ios'
        assert token.is_active is True
        assert str(token) == f"{user_alpha_owner.email} - ios - iPhone 15"

    def test_create_android_token(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='fcm-token-xyz',
            platform='android',
            device_name='Pixel 8',
        )
        assert token.platform == 'android'

    def test_unique_together_user_token(self, user_alpha_owner, org_alpha):
        NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='same-token',
            platform='ios',
        )
        with pytest.raises(IntegrityError):
            NativePushToken.objects.create(
                user=user_alpha_owner,
                organization=org_alpha,
                token='same-token',
                platform='ios',
            )

    def test_tenant_isolation(self, user_alpha_owner, org_alpha, user_beta_owner, org_beta):
        NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='alpha-token',
            platform='ios',
        )
        NativePushToken.objects.create(
            user=user_beta_owner,
            organization=org_beta,
            token='beta-token',
            platform='android',
        )
        alpha_tokens = NativePushToken.objects.filter(organization=org_alpha)
        assert alpha_tokens.count() == 1
        assert alpha_tokens.first().token == 'alpha-token'
