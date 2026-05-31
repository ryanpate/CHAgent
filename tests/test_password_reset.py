import re
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

@pytest.mark.django_db
def test_password_reset_confirm_invalid_link_shows_message(client):
    # A bogus uid/token must render the invalid-link branch, not crash.
    url = reverse('password_reset_confirm', kwargs={'uidb64': 'bad', 'token': 'bad-token'})
    resp = client.get(url, follow=True)
    assert resp.status_code == 200
    assert b'invalid or expired' in resp.content.lower()

@pytest.mark.django_db
def test_password_reset_complete_page_renders(client):
    resp = client.get(reverse('password_reset_complete'))
    assert resp.status_code == 200
    assert reverse('login').encode() in resp.content

@pytest.mark.django_db
def test_password_reset_confirm_weak_password_shows_error(client):
    User.objects.create_user(username='w@x.org', email='w@x.org', password='oldpass123')
    client.post(reverse('password_reset'), {'email': 'w@x.org'})
    link = re.search(r'(/accounts/reset/[^\s]+)', mail.outbox[0].body).group(1)
    # First GET redirects to the set-password URL; follow it.
    resp = client.get(link, follow=True)
    assert resp.status_code == 200
    # Post a weak (too-short, numeric, common) password
    post_url = resp.redirect_chain[-1][0] if resp.redirect_chain else link
    resp2 = client.post(post_url, {'new_password1': '123', 'new_password2': '123'})
    assert resp2.status_code == 200  # re-render with errors, not redirect
    assert b'text-red-400' in resp2.content  # themed error shown in-form
