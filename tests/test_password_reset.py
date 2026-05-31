import pytest
from django.urls import reverse
from django.core import mail
from accounts.models import User

@pytest.mark.django_db
def test_password_reset_sends_email(client):
    User.objects.create_user(username='r@x.org', email='r@x.org', password='oldpass123')
    resp = client.post(reverse('password_reset'), {'email': 'r@x.org'})
    assert resp.status_code == 302
    assert resp.url == reverse('password_reset_done')
    assert len(mail.outbox) == 1
    assert 'r@x.org' in mail.outbox[0].to

@pytest.mark.django_db
def test_login_page_has_forgot_password_link(client):
    body = client.get(reverse('login')).content.decode()
    assert reverse('password_reset') in body
    assert 'Forgot' in body
