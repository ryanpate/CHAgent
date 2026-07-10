"""Card-free trial: signup skips plan/checkout, orgs trial at Team level."""
import pytest
from datetime import timedelta
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

User = get_user_model()


@pytest.fixture
def team_plan(db):
    from core.models import SubscriptionPlan
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug='team', defaults={
            'name': 'Team', 'tier': 'team',
            'price_monthly_cents': 3999, 'price_yearly_cents': 40000,
            'max_users': 15, 'max_volunteers': 200,
            'max_ai_queries_monthly': 1000,
            'has_analytics': True, 'has_care_insights': True,
            'is_active': True,
        },
    )
    return plan


@pytest.mark.django_db
def test_signup_redirects_to_connect_pco_and_assigns_team_plan(client, team_plan):
    from core.models import Organization
    response = client.post(reverse('onboarding_signup'), {
        'first_name': 'A', 'last_name': 'B',
        'email': 'cardfree@x.org', 'password': 'supersecret1',
        'church_name': 'Cardfree Church',
    })
    assert response.status_code == 302
    assert response['Location'].endswith(reverse('onboarding_connect_pco'))
    org = Organization.objects.get(name='Cardfree Church')
    assert org.subscription_status == 'trial'
    assert org.subscription_plan_id == team_plan.id


@pytest.mark.django_db
def test_orgless_user_signup_also_gets_team_plan(client, team_plan):
    from core.models import Organization
    user = User.objects.create_user(
        username='noorg2@x.org', email='noorg2@x.org', password='supersecret1',
    )
    client.force_login(user)
    response = client.post(reverse('onboarding_signup'), {'church_name': 'Second Wind'})
    assert response.status_code == 302
    assert response['Location'].endswith(reverse('onboarding_connect_pco'))
    org = Organization.objects.get(name='Second Wind')
    assert org.subscription_plan_id == team_plan.id


@pytest.mark.django_db
def test_default_trial_plan_falls_back_to_cheapest_active(db):
    from core.models import SubscriptionPlan
    from core.views import _default_trial_plan
    SubscriptionPlan.objects.all().delete()
    cheap = SubscriptionPlan.objects.create(
        slug='starter-x', name='Starter', tier='starter',
        price_monthly_cents=999, is_active=True,
    )
    SubscriptionPlan.objects.create(
        slug='ministry-x', name='Ministry', tier='ministry',
        price_monthly_cents=7999, is_active=True,
    )
    assert _default_trial_plan().id == cheap.id


@pytest.mark.django_db
def test_backfill_assigns_team_plan_to_planless_trials(team_plan):
    import importlib
    from django.apps import apps
    from core.models import Organization

    planless = Organization.objects.create(
        name='Planless Trial', email='planless@x.org',
        subscription_status='trial', subscription_plan=None,
    )
    active_untouched = Organization.objects.create(
        name='Active NoPlan', email='activenp@x.org',
        subscription_status='active', subscription_plan=None,
    )

    migration = importlib.import_module('core.migrations.0050_backfill_trial_plan')
    migration.backfill_trial_plan(apps, None)

    planless.refresh_from_db()
    active_untouched.refresh_from_db()
    assert planless.subscription_plan_id == team_plan.id
    assert active_untouched.subscription_plan_id is None


def _billing_owner(client, team_plan, trial_delta_hours):
    from core.models import Organization, OrganizationMembership
    org = Organization.objects.create(
        name='MidTrial', email='midtrial@x.org',
        subscription_status='trial', subscription_plan=team_plan,
        stripe_customer_id='cus_midtrial',
        trial_ends_at=timezone.now() + timedelta(hours=trial_delta_hours),
    )
    user = User.objects.create_user(
        username=f'mid{trial_delta_hours}@x.org',
        email=f'mid{trial_delta_hours}@x.org', password='supersecret1',
    )
    OrganizationMembership.objects.create(
        user=user, organization=org, role='owner', can_manage_billing=True,
    )
    user.default_organization = org
    user.save()
    client.force_login(user)
    return org


@pytest.mark.django_db
def test_mid_trial_checkout_passes_trial_end(client, team_plan, settings):
    settings.STRIPE_SECRET_KEY = 'sk_test_x'
    settings.STRIPE_PRICE_TEAM_MONTHLY = 'price_team_m'
    org = _billing_owner(client, team_plan, trial_delta_hours=24 * 10)

    fake_session = MagicMock()
    fake_session.url = 'https://checkout.stripe.test/cs_1'
    with patch('stripe.checkout.Session.create', return_value=fake_session) as create:
        response = client.post(reverse('subscribe'), {
            'plan_id': team_plan.id, 'billing_period': 'monthly',
        })

    assert response.status_code == 302
    sub_data = create.call_args.kwargs['subscription_data']
    assert sub_data['trial_end'] == int(org.trial_ends_at.timestamp())


@pytest.mark.django_db
def test_trial_ending_within_48h_charges_immediately(client, team_plan, settings):
    settings.STRIPE_SECRET_KEY = 'sk_test_x'
    settings.STRIPE_PRICE_TEAM_MONTHLY = 'price_team_m'
    _billing_owner(client, team_plan, trial_delta_hours=24)

    fake_session = MagicMock()
    fake_session.url = 'https://checkout.stripe.test/cs_2'
    with patch('stripe.checkout.Session.create', return_value=fake_session) as create:
        client.post(reverse('subscribe'), {
            'plan_id': team_plan.id, 'billing_period': 'monthly',
        })

    sub_data = create.call_args.kwargs['subscription_data']
    assert 'trial_end' not in sub_data


@pytest.mark.django_db
def test_trial_banner_shows_days_left_and_plan_cta(client, team_plan):
    _billing_owner(client, team_plan, trial_delta_hours=24 * 10)
    response = client.get(reverse('dashboard'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'days left' in content
    assert 'Choose your plan' in content


@pytest.mark.django_db
def test_trial_banner_hides_cta_once_card_on_file(client, team_plan):
    from core.models import Organization
    org = _billing_owner(client, team_plan, trial_delta_hours=24 * 10)
    org.stripe_subscription_id = 'sub_hascard'
    org.save()
    response = client.get(reverse('dashboard'))
    content = response.content.decode()
    assert 'days left' in content
    assert 'Choose your plan' not in content


@pytest.mark.django_db
def test_signup_page_says_no_card_required(client):
    response = client.get(reverse('onboarding_signup'))
    content = response.content.decode()
    assert 'No credit card required' in content
    assert 'We ask for a card' not in content
