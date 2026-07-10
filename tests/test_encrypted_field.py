"""EncryptedTextField: transparent Fernet encryption at rest."""
import pytest
from django.db import connection


def test_get_fernet_stable_without_setting(settings):
    settings.FIELD_ENCRYPTION_KEY = ''
    from core.fields import get_fernet
    f1 = get_fernet()
    token = f1.encrypt(b'hello')
    # A second call derives the same key from SECRET_KEY and can decrypt.
    from importlib import reload
    import core.fields as fields_mod
    assert reload(fields_mod).get_fernet().decrypt(token) == b'hello'


def test_uses_explicit_key(settings):
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    settings.FIELD_ENCRYPTION_KEY = key
    from importlib import reload
    import core.fields as fields_mod
    reload(fields_mod)
    plaintext = 'secret-token-123'
    enc = fields_mod.get_fernet().encrypt(plaintext.encode()).decode()
    assert Fernet(key.encode()).decrypt(enc.encode()).decode() == plaintext


@pytest.mark.django_db
def test_field_round_trips_and_stores_ciphertext(settings):
    from core.models import Organization
    org = Organization.objects.create(
        name='Enc Co', email='enc@x.org', planning_center_secret='pco-secret-xyz',
    )
    org.refresh_from_db()
    assert org.planning_center_secret == 'pco-secret-xyz'  # decrypts on read
    # Raw column value is ciphertext, not the plaintext.
    with connection.cursor() as cur:
        cur.execute('SELECT planning_center_secret FROM core_organization WHERE id=%s', [org.id])
        raw = cur.fetchone()[0]
    assert raw != 'pco-secret-xyz'
    assert 'pco-secret-xyz' not in (raw or '')


@pytest.mark.django_db
def test_field_reads_legacy_plaintext_unchanged(settings):
    from core.models import Organization
    org = Organization.objects.create(name='Legacy Co', email='legacy@x.org')
    # Simulate a pre-migration plaintext value written directly to the column.
    with connection.cursor() as cur:
        cur.execute('UPDATE core_organization SET planning_center_secret=%s WHERE id=%s',
                    ['legacy-plaintext', org.id])
    org.refresh_from_db()
    assert org.planning_center_secret == 'legacy-plaintext'  # InvalidToken fallback
