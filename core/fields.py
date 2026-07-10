"""Field-level encryption at rest (Fernet)."""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def get_fernet():
    """Fernet from FIELD_ENCRYPTION_KEY, else derived from SECRET_KEY (dev/tests)."""
    key = getattr(settings, 'FIELD_ENCRYPTION_KEY', '') or ''
    if key:
        return Fernet(key.encode() if isinstance(key, str) else key)
    derived = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(derived)


class EncryptedTextField(models.TextField):
    """TextField that stores a Fernet-encrypted value; transparent on read/write.

    Reads that fail to decrypt (legacy plaintext not yet migrated) return the
    raw value unchanged so nothing crashes during the migration window.
    """

    def get_prep_value(self, value):
        if value is None or value == '':
            return value
        return get_fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == '':
            return value
        try:
            return get_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, ValueError):
            return value  # legacy plaintext
