# File Attachments & S3 Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add file attachment support (images + documents) to DMs, channel messages, and task comments, backed by S3 storage that persists across Railway deploys.

**Architecture:** A single `MessageAttachment` model with nullable FKs to DirectMessage, ChannelMessage, and TaskComment. Files uploaded via multipart form alongside message text. S3 storage via `django-storages[s3]` replaces local FileSystemStorage in production — all existing FileField models (Document, DocumentImage) automatically benefit.

**Tech Stack:** django-storages, boto3, AWS S3

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `requirements.txt` | Modify | Add django-storages[s3] and boto3 |
| `config/settings.py` | Modify | S3 storage config for production |
| `core/models.py` | Modify | Add MessageAttachment model |
| `core/views.py` | Modify | Update dm_send, channel_send_message, task_comment to handle file uploads |
| `templates/core/partials/dm_message.html` | Modify | Render attachments inline |
| `templates/core/partials/channel_message.html` | Modify | Render attachments inline |
| `templates/core/partials/task_comment.html` | Modify | Render attachments inline |
| `templates/core/partials/attachment_display.html` | Create | Shared attachment rendering partial |
| `templates/core/comms/dm_conversation.html` | Modify | Add file input to message form |
| `templates/core/comms/channel_detail.html` | Modify | Add file input to message form |
| `templates/core/comms/task_detail.html` | Modify | Add file input to comment form |
| `tests/test_attachments.py` | Create | Attachment model and upload tests |

---

### Task 1: Add S3 Storage Dependencies

**Files:**
- Modify: `requirements.txt`
- Modify: `config/settings.py:228-244`

- [ ] **Step 1: Add dependencies to requirements.txt**

Add after the `firebase-admin` line:

```
# Cloud Storage (S3)
django-storages[s3]>=1.14.0
boto3>=1.34.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install django-storages[s3] boto3`

- [ ] **Step 3: Configure S3 storage in settings.py**

Replace the media files and STORAGES section (lines 228-244) with:

```python
# Media files (user-uploaded content)
MEDIA_URL = '/media/'

# S3 Storage for production (persists across Railway deploys)
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.environ.get('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.environ.get('AWS_S3_REGION_NAME', 'us-east-1')
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}

if AWS_ACCESS_KEY_ID and AWS_STORAGE_BUCKET_NAME:
    # Production: use S3
    STORAGES = {
        'default': {
            'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
        },
    }
    MEDIA_URL = f'https://{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/'
else:
    # Development: use local filesystem
    MEDIA_ROOT = BASE_DIR / 'media'
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
        },
    }

# File upload limits (10 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
```

- [ ] **Step 4: Add 'storages' to INSTALLED_APPS**

In `config/settings.py`, add `'storages'` to the INSTALLED_APPS list.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt config/settings.py
git commit -m "feat: add S3 storage backend for file persistence across deploys"
```

---

### Task 2: Create MessageAttachment Model

**Files:**
- Modify: `core/models.py` (append after line 3572)
- Create: migration via `makemigrations`

- [ ] **Step 1: Write test for MessageAttachment model**

Create `tests/test_attachments.py`:

```python
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import MessageAttachment, DirectMessage, ChannelMessage, TaskComment


@pytest.mark.django_db
def test_create_attachment_for_dm(org_user_client, test_org):
    """MessageAttachment can be linked to a DirectMessage."""
    from accounts.models import User
    from core.models import DirectMessage

    sender = User.objects.first()
    recipient = User.objects.create_user(username='recipient@test.com', password='test')
    dm = DirectMessage.objects.create(sender=sender, recipient=recipient, content='hello')

    attachment = MessageAttachment.objects.create(
        organization=test_org,
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
def test_attachment_str(org_user_client, test_org):
    """MessageAttachment __str__ returns filename."""
    from accounts.models import User

    user = User.objects.first()
    attachment = MessageAttachment(
        organization=test_org,
        uploaded_by=user,
        filename='report.pdf',
        file_size=1024,
        file_type='document',
        content_type='application/pdf',
    )
    assert str(attachment) == 'report.pdf'


@pytest.mark.django_db
def test_attachment_is_image(test_org):
    """is_image property returns True for image file types."""
    from accounts.models import User
    user = User.objects.create_user(username='test@test.com', password='test')
    img = MessageAttachment(organization=test_org, uploaded_by=user, filename='photo.jpg', file_type='image', file_size=100, content_type='image/jpeg')
    doc = MessageAttachment(organization=test_org, uploaded_by=user, filename='file.pdf', file_type='document', file_size=100, content_type='application/pdf')
    assert img.is_image is True
    assert doc.is_image is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_attachments.py -v`
Expected: FAIL with ImportError (MessageAttachment not defined)

- [ ] **Step 3: Add MessageAttachment model to core/models.py**

Append at the end of `core/models.py`:

```python
class MessageAttachment(models.Model):
    """
    File attachment for DMs, channel messages, or task comments.
    Uses nullable FKs — exactly one should be set per attachment.
    """
    ALLOWED_EXTENSIONS = {
        'image': ['.png', '.jpg', '.jpeg', '.gif', '.webp'],
        'document': ['.pdf', '.doc', '.docx', '.txt'],
    }
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

    organization = models.ForeignKey(
        'Organization',
        on_delete=models.CASCADE,
        related_name='attachments',
        null=True,
        blank=True,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
    )
    file = models.FileField(upload_to='attachments/%Y/%m/')
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text='File size in bytes')
    file_type = models.CharField(
        max_length=20,
        choices=[('image', 'Image'), ('document', 'Document'), ('other', 'Other')],
    )
    content_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    # Polymorphic links — one should be set
    direct_message = models.ForeignKey(
        'DirectMessage',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attachments',
    )
    channel_message = models.ForeignKey(
        'ChannelMessage',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attachments',
    )
    task_comment = models.ForeignKey(
        'TaskComment',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='attachments',
    )

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return self.filename

    @property
    def is_image(self):
        return self.file_type == 'image'

    @classmethod
    def get_file_type(cls, filename):
        """Determine file type from filename extension."""
        import os
        ext = os.path.splitext(filename)[1].lower()
        for ftype, extensions in cls.ALLOWED_EXTENSIONS.items():
            if ext in extensions:
                return ftype
        return 'other'

    @classmethod
    def validate_file(cls, uploaded_file):
        """Validate file size and type. Returns (file_type, error_msg)."""
        import os
        if uploaded_file.size > cls.MAX_FILE_SIZE:
            return None, 'File too large. Maximum size is 10 MB.'
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        all_extensions = []
        for extensions in cls.ALLOWED_EXTENSIONS.values():
            all_extensions.extend(extensions)
        if ext not in all_extensions:
            return None, f'Unsupported file type. Allowed: images and PDF/DOC/TXT files.'
        return cls.get_file_type(uploaded_file.name), None
```

- [ ] **Step 4: Create and run migration**

Run:
```bash
python3 manage.py makemigrations core
python3 manage.py migrate
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_attachments.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_attachments.py
git commit -m "feat: add MessageAttachment model for DM/channel/task file uploads"
```

---

### Task 3: Create Shared Attachment Display Partial

**Files:**
- Create: `templates/core/partials/attachment_display.html`

- [ ] **Step 1: Create the attachment rendering partial**

Create `templates/core/partials/attachment_display.html`:

```html
{% for attachment in attachments %}
<div class="mt-2">
    {% if attachment.is_image %}
    <a href="{{ attachment.file.url }}" target="_blank" class="block">
        <img src="{{ attachment.file.url }}" alt="{{ attachment.filename }}"
             class="max-w-xs max-h-48 rounded-lg border border-gray-700 hover:border-ch-gold transition">
    </a>
    {% else %}
    <a href="{{ attachment.file.url }}" target="_blank"
       class="inline-flex items-center gap-2 px-3 py-2 bg-ch-gray rounded-lg hover:bg-gray-600 transition text-sm">
        <svg class="w-4 h-4 text-gray-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
        </svg>
        <span class="truncate max-w-[200px]">{{ attachment.filename }}</span>
        <span class="text-xs text-gray-500">{{ attachment.file_size|filesizeformat }}</span>
    </a>
    {% endif %}
</div>
{% endfor %}
```

- [ ] **Step 2: Commit**

```bash
git add templates/core/partials/attachment_display.html
git commit -m "feat: add shared attachment display partial template"
```

---

### Task 4: Add Attachment Upload to DM Send

**Files:**
- Modify: `core/views.py:2378-2407` (dm_send view)
- Modify: `templates/core/comms/dm_conversation.html` (message form)
- Modify: `templates/core/partials/dm_message.html` (render attachments)

- [ ] **Step 1: Write test for DM attachment upload**

Add to `tests/test_attachments.py`:

```python
@pytest.mark.django_db
def test_dm_send_with_attachment(org_user_client, test_org):
    """Sending a DM with a file creates a MessageAttachment."""
    from accounts.models import User
    from core.models import DirectMessage, MessageAttachment

    recipient = User.objects.create_user(username='recv@test.com', password='test')
    # Add recipient to org so they're accessible
    from core.models import OrganizationMembership
    OrganizationMembership.objects.create(user=recipient, organization=test_org, role='member')

    fake_file = SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
    response = org_user_client.post(
        f'/comms/messages/{recipient.pk}/send/',
        {'content': 'Check this out', 'attachments': fake_file},
    )
    assert DirectMessage.objects.filter(recipient=recipient).exists()
    dm = DirectMessage.objects.filter(recipient=recipient).first()
    assert dm.attachments.count() == 1
    att = dm.attachments.first()
    assert att.filename == 'photo.png'
    assert att.file_type == 'image'


@pytest.mark.django_db
def test_dm_send_attachment_only(org_user_client, test_org):
    """Sending a DM with only a file (no text) should work."""
    from accounts.models import User
    from core.models import DirectMessage, MessageAttachment, OrganizationMembership

    recipient = User.objects.create_user(username='recv2@test.com', password='test')
    OrganizationMembership.objects.create(user=recipient, organization=test_org, role='member')

    fake_file = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
    response = org_user_client.post(
        f'/comms/messages/{recipient.pk}/send/',
        {'content': '', 'attachments': fake_file},
    )
    assert DirectMessage.objects.filter(recipient=recipient).exists()
    dm = DirectMessage.objects.filter(recipient=recipient).first()
    assert dm.attachments.count() == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_attachments.py::test_dm_send_with_attachment -v`
Expected: FAIL (no attachment handling in dm_send)

- [ ] **Step 3: Update dm_send view to handle file uploads**

In `core/views.py`, replace the `dm_send` function:

```python
@login_required
@require_POST
def dm_send(request, user_id):
    """Send a direct message to a user, optionally with file attachments."""
    from .models import DirectMessage, MessageAttachment
    from accounts.models import User

    org = get_org(request)
    recipient = get_object_or_404(User, pk=user_id)
    content = request.POST.get('content', '').strip()
    files = request.FILES.getlist('attachments')

    # Must have content or at least one file
    if not content and not files:
        return redirect('dm_conversation', user_id=user_id)

    message = DirectMessage.objects.create(
        sender=request.user,
        recipient=recipient,
        content=content
    )

    # Handle file attachments
    for f in files:
        file_type, error = MessageAttachment.validate_file(f)
        if error:
            continue  # Skip invalid files
        MessageAttachment.objects.create(
            organization=org,
            uploaded_by=request.user,
            file=f,
            filename=f.name,
            file_size=f.size,
            file_type=file_type,
            content_type=f.content_type or 'application/octet-stream',
            direct_message=message,
        )

    # Send push notification
    try:
        from .notifications import notify_new_dm
        notify_new_dm(message)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to send DM notification: {e}")

    if request.headers.get('HX-Request'):
        return render(request, 'core/partials/dm_message.html', {
            'message': message,
            'is_sender': True,
        })

    return redirect('dm_conversation', user_id=user_id)
```

- [ ] **Step 4: Update DM conversation form to accept files**

In `templates/core/comms/dm_conversation.html`, update the message form to add `enctype` and a file button:

Replace the form section with:

```html
    <!-- Message Input (pinned to bottom) -->
    <form id="dm-form" hx-post="{% url 'dm_send' partner.id %}"
          hx-target="#messages-container"
          hx-swap="beforeend"
          hx-encoding="multipart/form-data"
          hx-on::after-request="this.reset(); document.getElementById('file-preview').innerHTML = ''; document.getElementById('messages-container').scrollTop = document.getElementById('messages-container').scrollHeight;"
          class="bg-ch-dark rounded-lg p-3 flex-shrink-0">
        {% csrf_token %}
        <div id="file-preview" class="flex flex-wrap gap-2 mb-2"></div>
        <div class="flex gap-2 items-center">
            <label class="cursor-pointer p-2 text-gray-400 hover:text-ch-gold transition rounded-lg hover:bg-ch-gray flex-shrink-0" title="Attach file">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"></path>
                </svg>
                <input type="file" name="attachments" multiple accept="image/*,.pdf,.doc,.docx,.txt" class="hidden"
                       onchange="previewFiles(this)">
            </label>
            <input type="text" name="content" id="dm-input"
                   placeholder="Write a message..."
                   autocomplete="off"
                   class="flex-1 bg-ch-gray border border-gray-700 rounded-lg px-4 py-3 focus:outline-none focus:border-ch-gold">
            <button type="submit"
                    class="px-5 py-3 bg-ch-gold text-black rounded-lg font-medium hover:bg-yellow-500 transition">
                Send
            </button>
        </div>
    </form>
```

Add a small file preview script before the closing `</script>` tag:

```javascript
function previewFiles(input) {
    var preview = document.getElementById('file-preview');
    preview.innerHTML = '';
    Array.from(input.files).forEach(function(file) {
        var tag = document.createElement('span');
        tag.className = 'inline-flex items-center gap-1 px-2 py-1 bg-ch-gray rounded text-xs text-gray-300';
        tag.textContent = file.name.length > 25 ? file.name.substring(0, 22) + '...' : file.name;
        preview.appendChild(tag);
    });
}
```

- [ ] **Step 5: Update dm_message.html partial to show attachments**

Replace `templates/core/partials/dm_message.html`:

```html
<div class="flex gap-3 {% if is_sender %}flex-row-reverse{% endif %}" id="dm-{{ message.id }}">
    <div class="w-10 h-10 bg-{% if is_sender %}ch-gold{% else %}gray-600{% endif %}/20 rounded-full flex items-center justify-center text-sm font-medium {% if is_sender %}text-ch-gold{% else %}text-gray-400{% endif %} flex-shrink-0">
        {{ message.sender.display_name|default:message.sender.username|slice:":1"|upper }}
    </div>
    <div class="max-w-[70%]">
        {% if message.content %}
        <div class="{% if is_sender %}bg-ch-gold/20 text-white{% else %}bg-ch-gray{% endif %} rounded-lg px-4 py-2">
            <p class="break-words">{{ message.content }}</p>
        </div>
        {% endif %}
        {% with attachments=message.attachments.all %}
        {% include 'core/partials/attachment_display.html' %}
        {% endwith %}
        <p class="text-xs text-gray-500 mt-1 {% if is_sender %}text-right{% endif %}">
            {{ message.created_at|date:"g:i A" }}
        </p>
    </div>
</div>
```

- [ ] **Step 6: Update dm_conversation.html message loop to show attachments**

In `templates/core/comms/dm_conversation.html`, update the message content div inside the for loop to match the same pattern — add after the content paragraph:

```html
        {% with attachments=message.attachments.all %}
        {% include 'core/partials/attachment_display.html' %}
        {% endwith %}
```

- [ ] **Step 7: Run tests**

Run: `python3 -m pytest tests/test_attachments.py -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add core/views.py templates/core/comms/dm_conversation.html templates/core/partials/dm_message.html
git commit -m "feat: add file attachment support to direct messages"
```

---

### Task 5: Add Attachment Upload to Channel Messages

**Files:**
- Modify: `core/views.py:2053-2099` (channel_send_message view)
- Modify: `templates/core/comms/channel_detail.html` (message form)
- Modify or create: `templates/core/partials/channel_message.html` (render attachments)

- [ ] **Step 1: Update channel_send_message view**

In `core/views.py`, update `channel_send_message` to handle files. After the line `content = request.POST.get('content', '').strip()`, add:

```python
    files = request.FILES.getlist('attachments')

    if content or files:
```

And after `message = ChannelMessage.objects.create(...)`, add:

```python
        # Handle file attachments
        for f in files:
            file_type, error = MessageAttachment.validate_file(f)
            if error:
                continue
            MessageAttachment.objects.create(
                organization=org,
                uploaded_by=request.user,
                file=f,
                filename=f.name,
                file_size=f.size,
                file_type=file_type,
                content_type=f.content_type or 'application/octet-stream',
                channel_message=message,
            )
```

Also add `MessageAttachment` to the import: `from .models import Channel, ChannelMessage, MessageAttachment`

- [ ] **Step 2: Update channel_detail.html message form**

In `templates/core/comms/channel_detail.html`, find the message send form and add `hx-encoding="multipart/form-data"` to the form tag, then add the paperclip file input button before the text input (same pattern as DM form from Task 4).

- [ ] **Step 3: Update channel_message.html partial to show attachments**

Add after the message content in the channel message partial:

```html
{% with attachments=message.attachments.all %}
{% include 'core/partials/attachment_display.html' %}
{% endwith %}
```

- [ ] **Step 4: Also update the inline message rendering in channel_detail.html**

The channel detail template renders messages inline (not via partial). Add the same attachment include after each message content block in the messages loop.

- [ ] **Step 5: Run full test suite**

Run: `python3 -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add core/views.py templates/core/comms/channel_detail.html templates/core/partials/channel_message.html
git commit -m "feat: add file attachment support to channel messages"
```

---

### Task 6: Add Attachment Upload to Task Comments

**Files:**
- Modify: `core/views.py` (task_comment view)
- Modify: `templates/core/comms/task_detail.html` (comment form)
- Modify: `templates/core/partials/task_comment.html` (render attachments)

- [ ] **Step 1: Update task_comment view**

In the `task_comment` function in `core/views.py`, add file handling. After `content = request.POST.get('content', '').strip()`, add:

```python
    files = request.FILES.getlist('attachments')
```

Change the condition to `if content or files:` and after `comment = TaskComment.objects.create(...)`, add:

```python
        # Handle file attachments
        from .models import MessageAttachment
        for f in files:
            file_type, error = MessageAttachment.validate_file(f)
            if error:
                continue
            MessageAttachment.objects.create(
                organization=get_org(request),
                uploaded_by=request.user,
                file=f,
                filename=f.name,
                file_size=f.size,
                file_type=file_type,
                content_type=f.content_type or 'application/octet-stream',
                task_comment=comment,
            )
```

- [ ] **Step 2: Update task_detail.html comment form**

In `templates/core/comms/task_detail.html`, add `hx-encoding="multipart/form-data"` to the comment form, and add the paperclip file input button before the textarea (same pattern as DM/channel forms).

- [ ] **Step 3: Update task_comment.html partial to show attachments**

In `templates/core/partials/task_comment.html`, add after the comment content div:

```html
{% with attachments=comment.attachments.all %}
{% include 'core/partials/attachment_display.html' %}
{% endwith %}
```

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add core/views.py templates/core/comms/task_detail.html templates/core/partials/task_comment.html
git commit -m "feat: add file attachment support to task comments"
```

---

### Task 7: Final Integration Testing

**Files:**
- Modify: `tests/test_attachments.py` (add integration tests)

- [ ] **Step 1: Add validation tests**

Add to `tests/test_attachments.py`:

```python
@pytest.mark.django_db
def test_validate_file_rejects_large_file():
    """Files over 10MB should be rejected."""
    large_file = SimpleUploadedFile('big.png', b'\x00' * (11 * 1024 * 1024), content_type='image/png')
    file_type, error = MessageAttachment.validate_file(large_file)
    assert file_type is None
    assert 'too large' in error.lower()


@pytest.mark.django_db
def test_validate_file_rejects_bad_extension():
    """Unsupported file types should be rejected."""
    exe_file = SimpleUploadedFile('virus.exe', b'\x00' * 100, content_type='application/octet-stream')
    file_type, error = MessageAttachment.validate_file(exe_file)
    assert file_type is None
    assert 'unsupported' in error.lower()


@pytest.mark.django_db
def test_validate_file_accepts_image():
    """Image files should be accepted."""
    img = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xff\xe0' + b'\x00' * 100, content_type='image/jpeg')
    file_type, error = MessageAttachment.validate_file(img)
    assert file_type == 'image'
    assert error is None


@pytest.mark.django_db
def test_validate_file_accepts_pdf():
    """PDF files should be accepted."""
    pdf = SimpleUploadedFile('report.pdf', b'%PDF-1.4', content_type='application/pdf')
    file_type, error = MessageAttachment.validate_file(pdf)
    assert file_type == 'document'
    assert error is None
```

- [ ] **Step 2: Run all tests**

Run: `python3 -m pytest tests/ -x -q`
Expected: All tests pass (500+ existing + new attachment tests)

- [ ] **Step 3: Commit**

```bash
git add tests/test_attachments.py
git commit -m "test: add validation and integration tests for file attachments"
```

---

## Post-Implementation Notes

### S3 Setup on Railway

After deploying, set these environment variables on Railway:

```
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_STORAGE_BUCKET_NAME=aria-church-uploads
AWS_S3_REGION_NAME=us-east-1
```

### S3 Bucket Configuration

Create the bucket with:
- **Block all public access** (files served via signed URLs since `AWS_QUERYSTRING_AUTH = True`)
- **Bucket policy**: No public policy needed (signed URLs handle access)
- **CORS**: Not needed (files accessed via signed S3 URLs, not cross-origin fetch)

### Existing Knowledge Base Files

After S3 is configured, existing Document and DocumentImage FileFields will automatically use S3 for new uploads. Previously uploaded files on local storage will need manual migration if they still exist.
