"""PlanningCenterAPI resolves per-org creds and refreshes OAuth tokens."""
from datetime import timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.utils import timezone


def _ok(json_body):
    r = MagicMock()
    r.json.return_value = json_body
    r.raise_for_status.return_value = None
    r.status_code = 200
    return r


@pytest.mark.django_db
def test_manual_org_uses_basic_auth():
    from core.models import Organization
    from core.planning_center import PlanningCenterAPI
    org = Organization.objects.create(
        name='Manual Co', email='m@x.org',
        planning_center_app_id='APPID', planning_center_secret='SECRET',
    )
    api = PlanningCenterAPI(organization=org)
    assert api.is_configured
    with patch('core.planning_center.requests.get', return_value=_ok({'data': []})) as get:
        api._get('/people/v2/people')
    assert get.call_args.kwargs.get('auth') == ('APPID', 'SECRET')
    assert 'Authorization' not in (get.call_args.kwargs.get('headers') or {})


@pytest.mark.django_db
def test_oauth_org_uses_bearer_header():
    from core.models import Organization
    from core.planning_center import PlanningCenterAPI
    org = Organization.objects.create(
        name='OAuth Co', email='o@x.org',
        pco_access_token='ACCESS', pco_refresh_token='REFRESH',
        pco_token_expires_at=timezone.now() + timedelta(hours=1),
        pco_auth_method='oauth',
    )
    api = PlanningCenterAPI(organization=org)
    assert api.is_configured
    with patch('core.planning_center.requests.get', return_value=_ok({'data': []})) as get:
        api._get('/people/v2/people')
    assert get.call_args.kwargs.get('auth') is None
    assert get.call_args.kwargs['headers']['Authorization'] == 'Bearer ACCESS'


@pytest.mark.django_db
def test_expired_oauth_token_refreshes_before_request():
    from core.models import Organization
    from core.planning_center import PlanningCenterAPI
    org = Organization.objects.create(
        name='Stale Co', email='s@x.org',
        pco_access_token='OLD', pco_refresh_token='RT',
        pco_token_expires_at=timezone.now() - timedelta(minutes=1),  # expired
        pco_auth_method='oauth',
    )
    api = PlanningCenterAPI(organization=org)
    new_tokens = {'access_token': 'NEW', 'refresh_token': 'RT2', 'expires_in': 7200}
    with patch('core.pco_oauth.refresh_access_token', return_value=new_tokens) as refresh, \
         patch('core.planning_center.requests.get', return_value=_ok({'data': []})) as get:
        api._get('/people/v2/people')
    refresh.assert_called_once_with('RT')
    assert get.call_args.kwargs['headers']['Authorization'] == 'Bearer NEW'
    org.refresh_from_db()
    assert org.pco_access_token == 'NEW'
    assert org.pco_refresh_token == 'RT2'


@pytest.mark.django_db
def test_no_org_falls_back_to_global_settings(settings):
    settings.PLANNING_CENTER_APP_ID = 'GLOBAL_ID'
    settings.PLANNING_CENTER_SECRET = 'GLOBAL_SECRET'
    from core.planning_center import PlanningCenterAPI
    api = PlanningCenterAPI()
    assert api.is_configured
    with patch('core.planning_center.requests.get', return_value=_ok({'data': []})) as get:
        api._get('/people/v2/people')
    assert get.call_args.kwargs.get('auth') == ('GLOBAL_ID', 'GLOBAL_SECRET')
