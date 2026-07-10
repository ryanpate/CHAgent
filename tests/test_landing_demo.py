"""Landing hero chat demo: scripted content renders server-side."""
import pytest


@pytest.mark.django_db
def test_landing_renders_hero_demo(client):
    response = client.get('/')
    assert response.status_code == 200
    content = response.content.decode()

    # Demo container and honesty label
    assert 'id="lpDemo"' in content
    assert 'Sample data' in content

    # All three scripted questions ship in the page source
    assert "Who's on the team this Sunday?" in content
    assert 'Any follow-ups for me?' in content
    assert 'What key is Goodness of God in?' in content

    # The static medallion is gone
    assert 'lp-medallion' not in content
