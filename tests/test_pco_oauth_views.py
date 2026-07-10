"""OAuth start/callback views."""
from unittest.mock import patch

import pytest
from django.urls import reverse


def _login_orgless_owner(client, db):
    from django.contrib.auth import get_user_model
    from core.models import Organization, OrganizationMembership
    User = get_user_model()
    org = Organization.objects.create(name='OA Co', email='oa@x.org', subscription_status='trial')
    user = User.objects.create_user(username='oa@x.org', email='oa@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=user, organization=org, role='owner', can_manage_settings=True)
    user.default_organization = org
    user.save()
    client.force_login(user)
    session = client.session
    session['onboarding_org_id'] = org.id
    session.save()
    return org


@pytest.mark.django_db
def test_start_redirects_to_authorize_when_configured(client, settings):
    settings.PCO_OAUTH_CLIENT_ID = 'cid'
    settings.PCO_OAUTH_CLIENT_SECRET = 'csec'
    settings.PCO_OAUTH_REDIRECT_URI = 'https://aria.church/onboarding/pco/callback/'
    _login_orgless_owner(client, db=True)
    resp = client.get(reverse('pco_oauth_start'))
    assert resp.status_code == 302
    assert resp['Location'].startswith('https://api.planningcenteronline.com/oauth/authorize?')
    assert 'state=' in resp['Location']


@pytest.mark.django_db
def test_start_not_configured_redirects_back(client, settings):
    settings.PCO_OAUTH_CLIENT_ID = ''
    settings.PCO_OAUTH_CLIENT_SECRET = ''
    _login_orgless_owner(client, db=True)
    resp = client.get(reverse('pco_oauth_start'))
    assert resp.status_code == 302
    assert reverse('onboarding_connect_pco') in resp['Location']


@pytest.mark.django_db
def test_callback_rejects_state_mismatch(client, settings):
    settings.PCO_OAUTH_CLIENT_ID = 'cid'
    settings.PCO_OAUTH_CLIENT_SECRET = 'csec'
    org = _login_orgless_owner(client, db=True)
    session = client.session
    session['pco_oauth_state'] = 'expected'
    session.save()
    with patch('core.pco_oauth.exchange_code') as ex:
        resp = client.get(reverse('pco_oauth_callback') + '?code=c&state=WRONG')
    ex.assert_not_called()
    org.refresh_from_db()
    assert org.pco_access_token == ''
    assert resp.status_code == 302


@pytest.mark.django_db
def test_callback_happy_path_stores_tokens(client, settings):
    settings.PCO_OAUTH_CLIENT_ID = 'cid'
    settings.PCO_OAUTH_CLIENT_SECRET = 'csec'
    org = _login_orgless_owner(client, db=True)
    session = client.session
    session['pco_oauth_state'] = 'st8'
    session.save()
    tokens = {'access_token': 'AT', 'refresh_token': 'RT', 'expires_in': 7200}
    with patch('core.pco_oauth.exchange_code', return_value=tokens):
        resp = client.get(reverse('pco_oauth_callback') + '?code=c&state=st8')
    assert resp.status_code == 302
    org.refresh_from_db()
    assert org.pco_access_token == 'AT'
    assert org.pco_refresh_token == 'RT'
    assert org.pco_auth_method == 'oauth'
    assert org.planning_center_connected_at is not None
    assert org.pco_token_expires_at is not None
