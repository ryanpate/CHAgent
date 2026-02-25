import pytest
from django.db import IntegrityError
from django.test import override_settings
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


@pytest.mark.django_db
class TestAuthTokenAPI:
    def test_obtain_token_valid_credentials(self, client, user_alpha_owner):
        user_alpha_owner.set_password('testpass123')
        user_alpha_owner.save()
        response = client.post('/api/auth/token/', {
            'email': user_alpha_owner.email,
            'password': 'testpass123',
        }, content_type='application/json')
        assert response.status_code == 200
        data = response.json()
        assert 'access' in data
        assert 'refresh' in data

    def test_obtain_token_invalid_credentials(self, client):
        response = client.post('/api/auth/token/', {
            'email': 'nobody@example.com',
            'password': 'wrong',
        }, content_type='application/json')
        assert response.status_code == 401

    def test_refresh_token(self, client, user_alpha_owner):
        user_alpha_owner.set_password('testpass123')
        user_alpha_owner.save()
        # Get tokens
        response = client.post('/api/auth/token/', {
            'email': user_alpha_owner.email,
            'password': 'testpass123',
        }, content_type='application/json')
        refresh = response.json()['refresh']
        # Refresh
        response = client.post('/api/auth/token/refresh/', {
            'refresh': refresh,
        }, content_type='application/json')
        assert response.status_code == 200
        assert 'access' in response.json()
