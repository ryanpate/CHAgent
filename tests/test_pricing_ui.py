import pytest

@pytest.mark.django_db
def test_pricing_has_mobile_and_desktop_comparison(client):
    body = client.get('/pricing/').content.decode()
    assert 'hidden md:block' in body          # desktop table wrapper hidden on mobile
    assert 'md:hidden' in body                # mobile card stack hidden on desktop
    assert 'data-mobile-comparison' in body   # the mobile comparison container
