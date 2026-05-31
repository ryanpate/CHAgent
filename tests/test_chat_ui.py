import pytest
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan

def _login_active_org(client, slug):
    plan = SubscriptionPlan.objects.create(slug=f'plan-{slug}', name='P', tier='team',
                                            has_analytics=True, has_care_insights=True)
    org = Organization.objects.create(name=f'Org {slug}', email=f'{slug}@x.org', slug=f'org-{slug}',
                                      subscription_plan=plan, subscription_status='active', stripe_subscription_id='sub_x')
    u = User.objects.create_user(username=f'{slug}@x.org', email=f'{slug}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner')
    u.default_organization = org; u.save()
    client.force_login(u)
    return org, u

@pytest.mark.django_db
def test_chat_messages_height_is_responsive(client):
    _login_active_org(client, 'chat')
    body = client.get(reverse('chat')).content.decode()
    assert 'h-[400px]' in body and 'sm:h-[500px]' in body
