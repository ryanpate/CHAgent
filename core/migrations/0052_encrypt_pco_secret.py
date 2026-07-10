"""Encrypt existing plaintext planning_center_secret values at rest.

Re-saving each org runs EncryptedTextField.get_prep_value (encrypt on write);
from_db_value tolerates the pre-migration plaintext on read. Idempotent-safe:
a re-run decrypts then re-encrypts.
"""
from django.db import migrations


def encrypt_secrets(apps, schema_editor):
    Organization = apps.get_model('core', 'Organization')
    for org in Organization.objects.exclude(planning_center_secret=''):
        org.save(update_fields=['planning_center_secret'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_pco_oauth_fields'),
    ]

    operations = [
        migrations.RunPython(encrypt_secrets, migrations.RunPython.noop),
    ]
