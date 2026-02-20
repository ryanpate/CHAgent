"""Tests for the BetaRequest model and beta request flow."""
import pytest
from django.test import Client
from core.models import BetaRequest


@pytest.mark.django_db
class TestBetaRequestModel:
    def test_create_beta_request(self):
        req = BetaRequest.objects.create(
            name='John Pastor',
            email='john@firstchurch.org',
            church_name='First Community Church',
            church_size='medium',
        )
        assert req.status == 'pending'
        assert req.name == 'John Pastor'
        assert req.email == 'john@firstchurch.org'
        assert req.church_name == 'First Community Church'
        assert req.church_size == 'medium'
        assert req.created_at is not None

    def test_email_uniqueness(self):
        BetaRequest.objects.create(
            name='John', email='john@church.org',
            church_name='Church A', church_size='small',
        )
        with pytest.raises(Exception):
            BetaRequest.objects.create(
                name='Jane', email='john@church.org',
                church_name='Church B', church_size='large',
            )

    def test_str_representation(self):
        req = BetaRequest.objects.create(
            name='John', email='john@church.org',
            church_name='First Church', church_size='small',
        )
        assert 'First Church' in str(req)
        assert 'john@church.org' in str(req)


@pytest.mark.django_db
class TestBetaRequestView:
    def test_signup_page_shows_beta_form(self):
        client = Client()
        response = client.get('/signup/')
        assert response.status_code == 200
        assert b'Request Beta Access' in response.content

    def test_submit_beta_request(self):
        from core.models import BetaRequest
        client = Client()
        response = client.post('/signup/', {
            'name': 'Sarah Pastor',
            'email': 'sarah@gracechurch.org',
            'church_name': 'Grace Community Church',
            'church_size': 'medium',
        })
        assert response.status_code == 200
        assert b'review your request' in response.content.lower()
        assert BetaRequest.objects.filter(email='sarah@gracechurch.org').exists()

    def test_submit_duplicate_email(self):
        from core.models import BetaRequest
        BetaRequest.objects.create(
            name='Existing', email='exists@church.org',
            church_name='Some Church', church_size='small',
        )
        client = Client()
        response = client.post('/signup/', {
            'name': 'New Person',
            'email': 'exists@church.org',
            'church_name': 'Another Church',
            'church_size': 'large',
        })
        assert response.status_code == 200
        assert b'already' in response.content.lower()

    def test_submit_missing_fields(self):
        from core.models import BetaRequest
        client = Client()
        response = client.post('/signup/', {
            'name': '',
            'email': 'test@church.org',
            'church_name': '',
            'church_size': 'small',
        })
        assert response.status_code == 200
        assert b'required' in response.content.lower()
        assert not BetaRequest.objects.filter(email='test@church.org').exists()


@pytest.mark.django_db
class TestBetaLandingPage:
    def test_landing_page_shows_beta_badge(self):
        client = Client()
        response = client.get('/')
        assert response.status_code == 200
        assert b'BETA' in response.content

    def test_landing_page_has_request_access_cta(self):
        client = Client()
        response = client.get('/')
        assert b'Request Beta Access' in response.content
        assert b'Start Free Trial' not in response.content

    def test_beta_banner_on_public_pages(self):
        client = Client()
        response = client.get('/')
        assert b'closed beta' in response.content.lower()
