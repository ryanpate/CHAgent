"""Card-free trial: signup skips plan/checkout, orgs trial at Team level."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

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
