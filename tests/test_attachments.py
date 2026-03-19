import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import MessageAttachment


@pytest.mark.django_db
def test_create_attachment_for_dm(org_alpha, user_alpha_owner):
    """MessageAttachment can be linked to a DirectMessage."""
    from accounts.models import User
    from core.models import DirectMessage

    sender = user_alpha_owner
    recipient = User.objects.create_user(username='recipient@test.com', password='test')
    dm = DirectMessage.objects.create(
        sender=sender, recipient=recipient, content='hello'
    )

    attachment = MessageAttachment.objects.create(
        organization=org_alpha,
        uploaded_by=sender,
        file=SimpleUploadedFile('test.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png'),
        filename='test.png',
        file_size=108,
        file_type='image',
        content_type='image/png',
        direct_message=dm,
    )
    assert attachment.pk is not None
    assert attachment.direct_message == dm
    assert attachment.channel_message is None
    assert attachment.task_comment is None
    assert dm.attachments.count() == 1


@pytest.mark.django_db
def test_attachment_str(org_alpha, user_alpha_owner):
    """MessageAttachment __str__ returns filename."""
    attachment = MessageAttachment(
        organization=org_alpha,
        uploaded_by=user_alpha_owner,
        filename='report.pdf',
        file_size=1024,
        file_type='document',
        content_type='application/pdf',
    )
    assert str(attachment) == 'report.pdf'


@pytest.mark.django_db
def test_attachment_is_image(org_alpha):
    """is_image property returns True for image file types."""
    from accounts.models import User
    user = User.objects.create_user(username='imgtest@test.com', password='test')
    img = MessageAttachment(
        organization=org_alpha, uploaded_by=user, filename='photo.jpg',
        file_type='image', file_size=100, content_type='image/jpeg',
    )
    doc = MessageAttachment(
        organization=org_alpha, uploaded_by=user, filename='file.pdf',
        file_type='document', file_size=100, content_type='application/pdf',
    )
    assert img.is_image is True
    assert doc.is_image is False
