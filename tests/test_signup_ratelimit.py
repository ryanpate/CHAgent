import pytest
from django.test import override_settings
from django.urls import reverse
from django.core.cache import cache


@pytest.mark.django_db
@override_settings(RATELIMIT_ENABLE=True)
def test_signup_rate_limited_after_threshold(client, subscription_plan):
    cache.clear()
    payload = lambda i: {'first_name': 'A', 'last_name': 'B',
                         'email': f'rl{i}@x.org', 'password': 'supersecret1',
                         'church_name': f'RL {i}'}
    # First 5 succeed (302), 6th is limited (200 re-render with error)
    last = None
    for i in range(6):
        last = client.post(reverse('onboarding_signup'), payload(i))
    assert last.status_code == 200
    assert b'too many' in last.content.lower()
    cache.clear()
