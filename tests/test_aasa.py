import pytest
import json


@pytest.mark.django_db
class TestAppleAppSiteAssociation:
    def test_aasa_returns_json(self, client):
        """AASA endpoint returns valid JSON with correct content type."""
        from django.test import Client
        c = Client()
        response = c.get('/.well-known/apple-app-site-association')
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/json'

    def test_aasa_contains_applinks(self, client):
        """AASA contains applinks with correct app ID."""
        from django.test import Client
        c = Client()
        response = c.get('/.well-known/apple-app-site-association')
        data = json.loads(response.content)
        assert 'applinks' in data
        assert 'details' in data['applinks']
        details = data['applinks']['details']
        assert len(details) >= 1
        assert details[0]['appIDs'][0].endswith('.church.aria.app')

    def test_aasa_specifies_paths(self, client):
        """AASA specifies allowed paths."""
        from django.test import Client
        c = Client()
        response = c.get('/.well-known/apple-app-site-association')
        data = json.loads(response.content)
        details = data['applinks']['details'][0]
        components = details.get('components', [])
        assert len(components) > 0
