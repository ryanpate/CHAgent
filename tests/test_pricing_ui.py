import pytest

@pytest.mark.django_db
def test_pricing_has_mobile_and_desktop_comparison(client):
    body = client.get('/pricing/').content.decode()
    assert 'hidden md:block' in body          # desktop table wrapper hidden on mobile
    assert 'md:hidden' in body                # mobile card stack hidden on desktop
    assert 'data-mobile-comparison' in body   # the mobile comparison container


@pytest.mark.django_db
def test_mobile_comparison_shows_correct_limits_and_excludes_enterprise(client):
    body = client.get('/pricing/').content.decode()
    # Slice to just the mobile comparison stack (from its container open to the FAQ section)
    mobile = body.split('data-mobile-comparison', 1)[1].split('<!-- FAQ Section -->', 1)[0]
    # Starter limits appear; AI-query number is real (not blank/Unlimited everywhere)
    assert '500' in mobile          # Starter monthly AI queries
    assert '2000' in mobile         # Team monthly AI queries
    # Unlimited shown as a word, never as the raw sentinel
    assert '-1' not in mobile
    assert 'Unlimited' in mobile    # Ministry unlimited rows
    # Enterprise excluded from the mobile stack
    assert 'Enterprise' not in mobile
