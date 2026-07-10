"""Planning Center OAuth 2 helpers (pure; no Django models)."""
from urllib.parse import urlencode

import requests
from django.conf import settings

AUTHORIZE_URL = 'https://api.planningcenteronline.com/oauth/authorize'
TOKEN_URL = 'https://api.planningcenteronline.com/oauth/token'
SCOPES = 'people services'


def _client_id():
    return getattr(settings, 'PCO_OAUTH_CLIENT_ID', '') or ''


def _client_secret():
    return getattr(settings, 'PCO_OAUTH_CLIENT_SECRET', '') or ''


def _redirect_uri():
    return getattr(settings, 'PCO_OAUTH_REDIRECT_URI', '') or ''


def is_configured():
    return bool(_client_id() and _client_secret())


def build_authorize_url(state):
    params = {
        'client_id': _client_id(),
        'redirect_uri': _redirect_uri(),
        'response_type': 'code',
        'scope': SCOPES,
        'state': state,
    }
    return f'{AUTHORIZE_URL}?{urlencode(params)}'


def exchange_code(code):
    """Exchange an authorization code for tokens. Raises on non-2xx."""
    resp = requests.post(TOKEN_URL, data={
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': _client_id(),
        'client_secret': _client_secret(),
        'redirect_uri': _redirect_uri(),
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()


def refresh_access_token(refresh_token):
    """Exchange a refresh token for a new token pair. Raises on non-2xx."""
    resp = requests.post(TOKEN_URL, data={
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': _client_id(),
        'client_secret': _client_secret(),
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()
