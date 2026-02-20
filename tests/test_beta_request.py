"""Tests for the BetaRequest model and beta request flow."""
import pytest
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
