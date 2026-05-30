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
