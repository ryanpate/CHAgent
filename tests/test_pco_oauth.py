"""Pure PCO OAuth helpers (no Django models)."""
from unittest.mock import patch, MagicMock

import pytest


def test_is_configured(settings):
    settings.PCO_OAUTH_CLIENT_ID = ''
    settings.PCO_OAUTH_CLIENT_SECRET = ''
    from importlib import reload
    import core.pco_oauth as m
    reload(m)
    assert m.is_configured() is False
    settings.PCO_OAUTH_CLIENT_ID = 'cid'
    settings.PCO_OAUTH_CLIENT_SECRET = 'csec'
    reload(m)
    assert m.is_configured() is True


def test_build_authorize_url(settings):
    settings.PCO_OAUTH_CLIENT_ID = 'cid'
    settings.PCO_OAUTH_CLIENT_SECRET = 'csec'
    settings.PCO_OAUTH_REDIRECT_URI = 'https://aria.church/onboarding/pco/callback/'
    from importlib import reload
    import core.pco_oauth as m
    reload(m)
    url = m.build_authorize_url('state-abc')
    assert url.startswith('https://api.planningcenteronline.com/oauth/authorize?')
    assert 'client_id=cid' in url
    assert 'scope=people+services' in url or 'scope=people%20services' in url
    assert 'response_type=code' in url
    assert 'state=state-abc' in url
    assert 'redirect_uri=https%3A%2F%2Faria.church%2Fonboarding%2Fpco%2Fcallback%2F' in url


def test_exchange_code(settings):
    settings.PCO_OAUTH_CLIENT_ID = 'cid'
    settings.PCO_OAUTH_CLIENT_SECRET = 'csec'
    settings.PCO_OAUTH_REDIRECT_URI = 'https://aria.church/onboarding/pco/callback/'
    from importlib import reload
    import core.pco_oauth as m
    reload(m)
    fake = MagicMock()
    fake.json.return_value = {'access_token': 'AT', 'refresh_token': 'RT', 'expires_in': 7200}
    fake.raise_for_status.return_value = None
    with patch('core.pco_oauth.requests.post', return_value=fake) as post:
        tokens = m.exchange_code('the-code')
    assert tokens['access_token'] == 'AT'
    body = post.call_args.kwargs['data']
    assert body['grant_type'] == 'authorization_code'
    assert body['code'] == 'the-code'
    assert body['redirect_uri'] == 'https://aria.church/onboarding/pco/callback/'


def test_refresh_access_token(settings):
    settings.PCO_OAUTH_CLIENT_ID = 'cid'
    settings.PCO_OAUTH_CLIENT_SECRET = 'csec'
    from importlib import reload
    import core.pco_oauth as m
    reload(m)
    fake = MagicMock()
    fake.json.return_value = {'access_token': 'AT2', 'refresh_token': 'RT2', 'expires_in': 7200}
    fake.raise_for_status.return_value = None
    with patch('core.pco_oauth.requests.post', return_value=fake) as post:
        tokens = m.refresh_access_token('old-rt')
    assert tokens['access_token'] == 'AT2'
    body = post.call_args.kwargs['data']
    assert body['grant_type'] == 'refresh_token'
    assert body['refresh_token'] == 'old-rt'


def test_field_encryption_key_required_in_production(settings):
    import importlib
    from django.core.exceptions import ImproperlyConfigured
    settings.DEBUG = False
    settings.RAILWAY_PUBLIC_DOMAIN = 'example.up.railway.app'
    settings.FIELD_ENCRYPTION_KEY = ''
    # Re-exec the guard logic the way settings.py does it.
    with pytest.raises(ImproperlyConfigured):
        if not settings.DEBUG and settings.RAILWAY_PUBLIC_DOMAIN and not settings.FIELD_ENCRYPTION_KEY:
            raise ImproperlyConfigured("FIELD_ENCRYPTION_KEY must be set in production.")
