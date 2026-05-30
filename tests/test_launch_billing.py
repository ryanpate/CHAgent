import pytest
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership


@pytest.mark.django_db
def test_beta_org_is_active_and_not_blocked():
    org = Organization.objects.create(
        name='Beta Grandfathered', email='b@x.org', subscription_status='beta',
    )
    assert org.is_subscription_active is True
    assert org.needs_subscription is False


@pytest.mark.django_db
def test_open_signup_creates_trial_org_and_redirects_to_plan(client, subscription_plan):
    resp = client.post(reverse('onboarding_signup'), {
        'first_name': 'Pat', 'last_name': 'Lee',
        'email': 'pat@newchurch.org', 'password': 'supersecret1',
        'church_name': 'New Life Church',
    })
    assert resp.status_code == 302
    assert resp.url == reverse('onboarding_select_plan')
    user = User.objects.get(email='pat@newchurch.org')
    org = Organization.objects.get(name='New Life Church')
    assert org.subscription_status == 'trial'
    assert org.trial_ends_at is not None
    assert OrganizationMembership.objects.filter(user=user, organization=org, role='owner').exists()


@pytest.mark.django_db
def test_open_signup_rejects_duplicate_email(client, subscription_plan):
    User.objects.create_user(username='dupe@x.org', email='dupe@x.org', password='x')
    resp = client.post(reverse('onboarding_signup'), {
        'first_name': 'D', 'last_name': 'U', 'email': 'dupe@x.org',
        'password': 'supersecret1', 'church_name': 'Dup Church',
    })
    assert resp.status_code == 200
    assert b'already' in resp.content.lower()


@pytest.mark.django_db
def test_signup_page_is_open_not_beta(client):
    resp = client.get(reverse('onboarding_signup'))
    body = resp.content.decode()
    assert resp.status_code == 200
    assert 'name="password"' in body
    assert 'Request Beta Access' not in body
    assert 'BETA' not in body


@pytest.mark.django_db
def test_checkout_without_stripe_config_does_not_grant_free_access(client, settings, subscription_plan):
    settings.STRIPE_SECRET_KEY = ''
    user = User.objects.create_user(username='c@x.org', email='c@x.org', password='supersecret1')
    org = Organization.objects.create(name='Checkout Church', email='c@x.org',
                                      subscription_status='trial', subscription_plan=subscription_plan)
    OrganizationMembership.objects.create(user=user, organization=org, role='owner', can_manage_billing=True)
    user.default_organization = org; user.save()
    client.force_login(user)
    session = client.session
    session['onboarding_org_id'] = org.id
    session['selected_plan_id'] = subscription_plan.id
    session['billing_cycle'] = 'monthly'
    session.save()
    resp = client.get(reverse('onboarding_checkout'))
    assert resp.status_code == 200
    assert b'unavailable' in resp.content.lower() or b'error' in resp.content.lower()
