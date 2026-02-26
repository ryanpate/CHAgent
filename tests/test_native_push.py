import pytest
from unittest.mock import patch
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

    def test_badge_count_default_zero(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='badge-test-token',
            platform='ios',
        )
        assert token.unread_badge_count == 0

    def test_badge_count_increment(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='badge-inc-token',
            platform='ios',
        )
        token.unread_badge_count += 1
        token.save()
        token.refresh_from_db()
        assert token.unread_badge_count == 1

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


@pytest.mark.django_db
class TestPushTokenRegistrationAPI:
    def test_register_ios_token(self, client_alpha, org_alpha):
        response = client_alpha.post('/api/push/register/', {
            'token': 'apns-device-token-123',
            'platform': 'ios',
            'device_name': 'iPhone 15 Pro',
        }, content_type='application/json')
        assert response.status_code == 201
        assert NativePushToken.objects.filter(organization=org_alpha).count() == 1

    def test_register_android_token(self, client_alpha, org_alpha):
        response = client_alpha.post('/api/push/register/', {
            'token': 'fcm-token-456',
            'platform': 'android',
            'device_name': 'Pixel 8',
        }, content_type='application/json')
        assert response.status_code == 201

    def test_register_duplicate_token_updates(self, client_alpha, org_alpha):
        # Register once
        client_alpha.post('/api/push/register/', {
            'token': 'same-token',
            'platform': 'ios',
            'device_name': 'Old Name',
        }, content_type='application/json')
        # Register again with same token
        response = client_alpha.post('/api/push/register/', {
            'token': 'same-token',
            'platform': 'ios',
            'device_name': 'New Name',
        }, content_type='application/json')
        assert response.status_code == 200
        assert NativePushToken.objects.filter(organization=org_alpha).count() == 1
        assert NativePushToken.objects.get(token='same-token').device_name == 'New Name'

    def test_register_requires_auth(self, client):
        response = client.post('/api/push/register/', {
            'token': 'some-token',
            'platform': 'ios',
        }, content_type='application/json')
        assert response.status_code in [401, 403]

    def test_unregister_token(self, client_alpha, user_alpha_owner, org_alpha):
        NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='token-to-remove',
            platform='ios',
        )
        response = client_alpha.delete('/api/push/unregister/', {
            'token': 'token-to-remove',
        }, content_type='application/json')
        assert response.status_code == 204
        assert NativePushToken.objects.filter(token='token-to-remove').count() == 0


@pytest.mark.django_db
class TestNativePushNotification:
    def test_send_to_native_ios_token(self, user_alpha_owner, org_alpha):
        from core.notifications import send_notification_to_user
        NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='apns-token-123',
            platform='ios',
        )
        with patch('core.notifications.send_native_push') as mock_send:
            mock_send.return_value = True
            count = send_notification_to_user(
                user_alpha_owner,
                'dm',
                'New Message',
                'You have a new direct message',
                url='/comms/messages/1/',
            )
            assert count >= 1
            mock_send.assert_called()

    def test_send_to_native_android_token(self, user_alpha_owner, org_alpha):
        from core.notifications import send_notification_to_user
        NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='fcm-token-456',
            platform='android',
        )
        with patch('core.notifications.send_native_push') as mock_send:
            mock_send.return_value = True
            count = send_notification_to_user(
                user_alpha_owner,
                'announcement',
                'New Announcement',
                'Team meeting moved to Thursday',
            )
            assert count >= 1

    def test_inactive_token_skipped(self, user_alpha_owner, org_alpha):
        from core.notifications import send_notification_to_user
        NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='inactive-token',
            platform='ios',
            is_active=False,
        )
        with patch('core.notifications.send_native_push') as mock_send:
            send_notification_to_user(
                user_alpha_owner,
                'dm',
                'Test',
                'Test body',
            )
            mock_send.assert_not_called()


@pytest.mark.django_db
class TestAppModeDetection:
    def test_app_mode_cookie_hides_sidebar(self, client_alpha):
        client_alpha.cookies['aria_app'] = '1'
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'app-mode-hidden' in content

    def test_web_mode_shows_sidebar(self, client_alpha):
        response = client_alpha.get('/dashboard/')
        assert response.status_code == 200
        content = response.content.decode()
        assert 'app-mode-hidden' not in content


@pytest.mark.django_db
class TestBadgeCountInPush:
    def test_send_native_push_increments_badge(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='badge-push-token',
            platform='ios',
        )
        assert token.unread_badge_count == 0

        with patch('core.notifications._send_fcm', return_value=True) as mock_fcm:
            from core.notifications import send_native_push
            send_native_push(token, 'Test Title', 'Test Body', '/')

        token.refresh_from_db()
        assert token.unread_badge_count == 1

    def test_send_native_push_passes_badge_to_fcm(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='badge-payload-token',
            platform='ios',
        )

        with patch('core.notifications._send_fcm', return_value=True) as mock_fcm:
            from core.notifications import send_native_push
            send_native_push(token, 'Test', 'Body', '/')

        mock_fcm.assert_called_once()
        call_payload = mock_fcm.call_args[0][1]
        assert call_payload['badge'] == 1

    def test_badge_count_increments_across_sends(self, user_alpha_owner, org_alpha):
        token = NativePushToken.objects.create(
            user=user_alpha_owner,
            organization=org_alpha,
            token='badge-multi-token',
            platform='ios',
        )

        with patch('core.notifications._send_fcm', return_value=True):
            from core.notifications import send_native_push
            send_native_push(token, 'First', 'Body', '/')
            send_native_push(token, 'Second', 'Body', '/')
            send_native_push(token, 'Third', 'Body', '/')

        token.refresh_from_db()
        assert token.unread_badge_count == 3
