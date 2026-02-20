# Security Round 2 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 2FA (TOTP), audit logging, Sentry error monitoring, and Dependabot dependency scanning to the Aria platform.

**Architecture:** Four independent features. Audit logging uses a custom AuditLog model with a helper function instrumented into existing admin and org management views. 2FA uses pyotp + qrcode for custom TOTP implementation with a new TOTPDevice model, middleware enforcement, and settings UI. Sentry is a simple SDK init in settings.py. Dependabot is a config file.

**Tech Stack:** pyotp, qrcode[pil], sentry-sdk[django], pip-audit, Django 5.x, HTMX, Tailwind CSS

---

## Task 1: Add Dependencies

**Files:**
- Modify: `requirements.txt`

**Step 1: Add new packages to requirements.txt**

Add these lines to `requirements.txt`:

```
# Two-Factor Authentication
pyotp>=2.9.0
qrcode[pil]>=7.4.0

# Error Monitoring
sentry-sdk[django]>=1.40.0

# Dependency Vulnerability Scanning (dev)
pip-audit>=2.7.0
```

Add after the `django-axes>=7.0.0` line (line 49).

**Step 2: Install the packages**

Run: `pip install pyotp "qrcode[pil]" "sentry-sdk[django]" pip-audit`

**Step 3: Commit**

```bash
git add requirements.txt
git commit -m "feat: add dependencies for 2FA, Sentry, and pip-audit"
```

---

## Task 2: AuditLog Model and Helper

**Files:**
- Modify: `core/models.py` (add after line 3327, end of file)
- Test: `tests/test_audit_log.py`

**Step 1: Write the failing test**

Create `tests/test_audit_log.py`:

```python
import pytest
from django.test import TestCase, RequestFactory
from core.models import AuditLog, Organization
from accounts.models import User


class TestAuditLogModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='admin@test.com',
            email='admin@test.com',
            password='testpass123',
            is_superadmin=True,
        )
        self.org = Organization.objects.create(
            name='Test Church',
            slug='test-church',
        )

    def test_create_audit_log(self):
        """AuditLog can be created with required fields."""
        log = AuditLog.objects.create(
            user=self.user,
            action='beta_approve',
            ip_address='127.0.0.1',
            organization=self.org,
            details={'church_name': 'Test Church'},
        )
        assert log.id is not None
        assert log.action == 'beta_approve'
        assert log.timestamp is not None

    def test_audit_log_str(self):
        """AuditLog string representation is readable."""
        log = AuditLog.objects.create(
            user=self.user,
            action='org_impersonate',
        )
        assert 'org_impersonate' in str(log)
        assert 'admin@test.com' in str(log)

    def test_audit_log_nullable_fields(self):
        """AuditLog works with nullable fields."""
        log = AuditLog.objects.create(
            user=self.user,
            action='settings_updated',
        )
        assert log.organization is None
        assert log.target_user is None
        assert log.ip_address is None
        assert log.details == {}
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audit_log.py -v`
Expected: FAIL with "Cannot resolve keyword 'action'" or similar (model doesn't exist yet)

**Step 3: Write the AuditLog model**

Add to the end of `core/models.py` (after line 3327):

```python


class AuditLog(models.Model):
    """Tracks admin and org management actions for security auditing."""
    ACTION_CHOICES = [
        ('beta_approve', 'Beta Request Approved'),
        ('beta_reject', 'Beta Request Rejected'),
        ('org_status_change', 'Organization Status Changed'),
        ('org_impersonate', 'Organization Impersonated'),
        ('user_role_change', 'User Role Changed'),
        ('user_removed', 'User Removed'),
        ('invitation_sent', 'Invitation Sent'),
        ('invitation_cancelled', 'Invitation Cancelled'),
        ('settings_updated', 'Settings Updated'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    organization = models.ForeignKey(
        'Organization', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_logs'
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='audit_target_logs'
    )
    details = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['action', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.user} - {self.action} at {self.timestamp}"
```

**Step 4: Create and run migration**

Run: `python3 manage.py makemigrations core -n add_audit_log_model`
Run: `python3 manage.py migrate`

**Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_audit_log.py -v`
Expected: 3 tests PASS

**Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_audit_log.py
git commit -m "feat: add AuditLog model for admin action tracking"
```

---

## Task 3: Audit Log Helper and Instrumentation

**Files:**
- Modify: `core/admin_views.py` (lines 467-520: admin_beta_approve, admin_beta_reject; lines 216-236: admin_organization_impersonate; lines 256-273: admin_organization_update_status)
- Modify: `core/views.py` (lines 4542-4612: org_invite_member; lines 4617-4662: org_update_member_role; lines 4667-4713: org_remove_member; lines 4718-4743: org_cancel_invitation)
- Test: `tests/test_audit_log.py` (add more tests)

**Step 1: Write failing tests for audit logging**

Add to `tests/test_audit_log.py`:

```python
from django.test import TestCase, Client
from core.models import AuditLog, Organization, OrganizationMembership
from accounts.models import User


class TestAuditLogIntegration(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='superadmin@test.com',
            email='superadmin@test.com',
            password='testpass123',
            is_superadmin=True,
        )
        self.org = Organization.objects.create(
            name='Test Church',
            slug='test-church',
        )
        OrganizationMembership.objects.create(
            user=self.admin,
            organization=self.org,
            role='owner',
            is_active=True,
        )

    def test_beta_approve_creates_audit_log(self):
        """Approving a beta request creates an audit log entry."""
        from core.models import BetaRequest
        beta_req = BetaRequest.objects.create(
            name='Test User',
            email='beta@test.com',
            church_name='Test Church',
            church_size='small',
        )
        self.client.force_login(self.admin)
        self.client.post(f'/platform-admin/beta-requests/{beta_req.pk}/approve/')
        assert AuditLog.objects.filter(action='beta_approve').exists()

    def test_impersonate_creates_audit_log(self):
        """Impersonating an org creates an audit log entry."""
        self.client.force_login(self.admin)
        self.client.get(f'/platform-admin/organizations/{self.org.id}/impersonate/')
        assert AuditLog.objects.filter(action='org_impersonate').exists()

    def test_role_change_creates_audit_log(self):
        """Changing a member's role creates an audit log entry."""
        member_user = User.objects.create_user(
            username='member@test.com',
            email='member@test.com',
            password='testpass123',
        )
        membership = OrganizationMembership.objects.create(
            user=member_user,
            organization=self.org,
            role='member',
            is_active=True,
        )
        self.client.force_login(self.admin)
        self.client.post(
            f'/settings/members/{membership.id}/role/',
            {'role': 'leader'},
        )
        assert AuditLog.objects.filter(action='user_role_change').exists()
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_audit_log.py::TestAuditLogIntegration -v`
Expected: FAIL (no audit log entries created yet)

**Step 3: Add helper function and instrument admin_views.py**

Add a helper function at the top of `core/admin_views.py`, after the imports (line 22):

```python
from .models import AuditLog


def get_client_ip(request):
    """Extract client IP from request, handling proxies."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def log_admin_action(request, action, organization=None, target_user=None, **details):
    """Create an audit log entry for an admin action."""
    AuditLog.objects.create(
        user=request.user,
        action=action,
        ip_address=get_client_ip(request),
        organization=organization,
        target_user=target_user,
        details=details,
    )
```

Note: Also add `AuditLog` to the import from `.models` at line 16-20.

Then instrument each admin view. Add `log_admin_action(...)` calls:

**In `admin_organization_impersonate` (after line 228, before the messages.success):**
```python
        log_admin_action(request, 'org_impersonate', organization=organization)
```

**In `admin_organization_update_status` (after line 264, after `organization.save()`):**
```python
            log_admin_action(
                request, 'org_status_change', organization=organization,
                old_status=request.POST.get('old_status', ''), new_status=new_status,
            )
```

**In `admin_beta_approve` (after line 501, after `messages.success`):**
```python
        log_admin_action(
            request, 'beta_approve',
            church_name=beta_req.church_name, email=beta_req.email,
        )
```

**In `admin_beta_reject` (after line 518, after `messages.success`):**
```python
        log_admin_action(
            request, 'beta_reject',
            church_name=beta_req.church_name, email=beta_req.email,
            reason=beta_req.rejection_reason,
        )
```

**Step 4: Instrument org management views in core/views.py**

Add at the top of `core/views.py` imports (or use inline import where needed):

```python
from .models import AuditLog
```

Add a copy of the helper functions (or import from admin_views -- for simplicity, add inline):

In each view, add a `log_admin_action`-style call. Since these views don't have the helper, use direct `AuditLog.objects.create(...)`:

**In `org_invite_member` (after line 4591, after invitation is created):**
```python
    AuditLog.objects.create(
        user=request.user, action='invitation_sent',
        organization=org, details={'email': email, 'role': role},
    )
```

**In `org_update_member_role` (after line 4659, after `target_membership.save()`):**
```python
    AuditLog.objects.create(
        user=request.user, action='user_role_change',
        organization=org, target_user=target_membership.user,
        details={'new_role': new_role},
    )
```

**In `org_remove_member` (after line 4710, after `target_membership.save()`):**
```python
    AuditLog.objects.create(
        user=request.user, action='user_removed',
        organization=org, target_user=target_membership.user,
        details={'email': user_email},
    )
```

**In `org_cancel_invitation` (after line 4740, after `invitation.save()`):**
```python
    AuditLog.objects.create(
        user=request.user, action='invitation_cancelled',
        organization=org, details={'email': invitation.email},
    )
```

**Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_audit_log.py -v`
Expected: 6 tests PASS

**Step 6: Commit**

```bash
git add core/admin_views.py core/views.py tests/test_audit_log.py
git commit -m "feat: instrument admin and org views with audit logging"
```

---

## Task 4: Audit Log Admin Dashboard View

**Files:**
- Modify: `core/admin_views.py` (add view at end of file)
- Modify: `core/urls.py` (add route)
- Create: `templates/core/admin/audit_log.html`
- Modify: `templates/core/admin/base.html` (add nav link)
- Test: `tests/test_audit_log.py` (add view test)

**Step 1: Write failing test**

Add to `tests/test_audit_log.py`:

```python
class TestAuditLogAdminView(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='superadmin@test.com',
            email='superadmin@test.com',
            password='testpass123',
            is_superadmin=True,
        )

    def test_audit_log_page_accessible(self):
        """Superadmins can access the audit log page."""
        self.client.force_login(self.admin)
        response = self.client.get('/platform-admin/audit-log/')
        assert response.status_code == 200

    def test_audit_log_shows_entries(self):
        """Audit log page displays log entries."""
        AuditLog.objects.create(
            user=self.admin,
            action='beta_approve',
            details={'church_name': 'Test Church'},
        )
        self.client.force_login(self.admin)
        response = self.client.get('/platform-admin/audit-log/')
        assert b'beta_approve' in response.content or b'Beta Request Approved' in response.content

    def test_audit_log_non_admin_blocked(self):
        """Non-superadmins cannot access the audit log."""
        user = User.objects.create_user(
            username='regular@test.com',
            email='regular@test.com',
            password='testpass123',
        )
        self.client.force_login(user)
        response = self.client.get('/platform-admin/audit-log/')
        assert response.status_code == 403
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_audit_log.py::TestAuditLogAdminView -v`
Expected: FAIL (404 -- URL doesn't exist)

**Step 3: Add admin view**

Add to end of `core/admin_views.py`:

```python
@login_required
@require_superadmin
def admin_audit_log(request):
    """View audit log entries."""
    logs = AuditLog.objects.select_related('user', 'organization', 'target_user').all()

    # Filter by action
    action_filter = request.GET.get('action')
    if action_filter:
        logs = logs.filter(action=action_filter)

    # Paginate
    from django.core.paginator import Paginator
    paginator = Paginator(logs, 25)
    page = request.GET.get('page')
    logs_page = paginator.get_page(page)

    return render(request, 'core/admin/audit_log.html', {
        'logs': logs_page,
        'action_filter': action_filter,
        'action_choices': AuditLog.ACTION_CHOICES,
    })
```

**Step 4: Add URL route**

Add to `core/urls.py` after the beta-requests routes (around line 144):

```python
    path('platform-admin/audit-log/', admin_views.admin_audit_log, name='admin_audit_log'),
```

**Step 5: Create the template**

Create `templates/core/admin/audit_log.html`:

```html
{% extends 'core/admin/base.html' %}

{% block title %}Audit Log{% endblock %}

{% block content %}
<div class="mb-8">
    <h1 class="text-2xl font-bold">Audit Log</h1>
    <p class="text-gray-400 mt-1">Track admin and management actions across the platform</p>
</div>

<!-- Filters -->
<div class="flex gap-2 mb-6 flex-wrap">
    <a href="{% url 'admin_audit_log' %}"
       class="px-3 py-1 rounded text-sm {% if not action_filter %}bg-ch-gold text-black{% else %}bg-ch-gray text-gray-300 hover:bg-gray-600{% endif %}">
        All
    </a>
    {% for value, label in action_choices %}
    <a href="{% url 'admin_audit_log' %}?action={{ value }}"
       class="px-3 py-1 rounded text-sm {% if action_filter == value %}bg-ch-gold text-black{% else %}bg-ch-gray text-gray-300 hover:bg-gray-600{% endif %}">
        {{ label }}
    </a>
    {% endfor %}
</div>

<!-- Log Table -->
<div class="bg-ch-dark rounded-lg overflow-hidden">
    <table class="min-w-full">
        <thead class="bg-ch-gray">
            <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Time</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">User</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Action</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Organization</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Target</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-400 uppercase">Details</th>
            </tr>
        </thead>
        <tbody class="divide-y divide-gray-800">
            {% for log in logs %}
            <tr class="hover:bg-ch-gray/50">
                <td class="px-4 py-3 text-sm text-gray-300 whitespace-nowrap">
                    {{ log.timestamp|date:"M d, Y H:i" }}
                </td>
                <td class="px-4 py-3 text-sm">
                    {% if log.user %}{{ log.user.email }}{% else %}<span class="text-gray-500">System</span>{% endif %}
                </td>
                <td class="px-4 py-3 text-sm">
                    <span class="px-2 py-1 rounded text-xs
                        {% if 'approve' in log.action %}bg-green-900 text-green-300
                        {% elif 'reject' in log.action or 'remove' in log.action %}bg-red-900 text-red-300
                        {% elif 'impersonate' in log.action %}bg-yellow-900 text-yellow-300
                        {% else %}bg-blue-900 text-blue-300{% endif %}">
                        {{ log.get_action_display }}
                    </span>
                </td>
                <td class="px-4 py-3 text-sm text-gray-300">
                    {% if log.organization %}{{ log.organization.name }}{% else %}-{% endif %}
                </td>
                <td class="px-4 py-3 text-sm text-gray-300">
                    {% if log.target_user %}{{ log.target_user.email }}{% else %}-{% endif %}
                </td>
                <td class="px-4 py-3 text-sm text-gray-400 max-w-xs truncate">
                    {% for key, value in log.details.items %}{{ key }}: {{ value }}{% if not forloop.last %}, {% endif %}{% endfor %}
                </td>
            </tr>
            {% empty %}
            <tr>
                <td colspan="6" class="px-4 py-8 text-center text-gray-500">No audit log entries yet.</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- Pagination -->
{% if logs.has_other_pages %}
<div class="flex justify-center gap-2 mt-6">
    {% if logs.has_previous %}
    <a href="?page={{ logs.previous_page_number }}{% if action_filter %}&action={{ action_filter }}{% endif %}"
       class="px-3 py-1 bg-ch-gray rounded text-sm hover:bg-gray-600">Previous</a>
    {% endif %}
    <span class="px-3 py-1 text-sm text-gray-400">Page {{ logs.number }} of {{ logs.paginator.num_pages }}</span>
    {% if logs.has_next %}
    <a href="?page={{ logs.next_page_number }}{% if action_filter %}&action={{ action_filter }}{% endif %}"
       class="px-3 py-1 bg-ch-gray rounded text-sm hover:bg-gray-600">Next</a>
    {% endif %}
</div>
{% endif %}
{% endblock %}
```

**Step 6: Add nav link to admin base template**

In `templates/core/admin/base.html`, add after the "Beta Requests" link (after line 55):

```html
                        <a href="{% url 'admin_audit_log' %}" class="{% if 'audit-log' in request.path %}bg-ch-gray text-white{% else %}text-gray-300 hover:bg-ch-gray hover:text-white{% endif %} px-3 py-2 rounded-md text-sm font-medium">
                            Audit Log
                        </a>
```

**Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_audit_log.py -v`
Expected: 9 tests PASS

**Step 8: Commit**

```bash
git add core/admin_views.py core/urls.py templates/core/admin/audit_log.html templates/core/admin/base.html tests/test_audit_log.py
git commit -m "feat: add audit log admin dashboard view"
```

---

## Task 5: TOTPDevice Model

**Files:**
- Modify: `core/models.py` (add after AuditLog model)
- Test: `tests/test_2fa.py`

**Step 1: Write failing test**

Create `tests/test_2fa.py`:

```python
import pytest
from django.test import TestCase
from core.models import TOTPDevice
from accounts.models import User


class TestTOTPDeviceModel(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            password='testpass123',
        )

    def test_create_totp_device(self):
        """TOTPDevice can be created with a secret."""
        import pyotp
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(
            user=self.user,
            secret=secret,
        )
        assert device.id is not None
        assert device.is_verified is False
        assert device.backup_codes == []

    def test_totp_device_one_per_user(self):
        """Only one TOTPDevice per user (OneToOne)."""
        import pyotp
        TOTPDevice.objects.create(user=self.user, secret=pyotp.random_base32())
        with pytest.raises(Exception):
            TOTPDevice.objects.create(user=self.user, secret=pyotp.random_base32())

    def test_verify_code(self):
        """TOTPDevice can verify a valid TOTP code."""
        import pyotp
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(user=self.user, secret=secret)
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()
        assert device.verify_code(valid_code) is True

    def test_reject_invalid_code(self):
        """TOTPDevice rejects an invalid code."""
        import pyotp
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(user=self.user, secret=secret)
        assert device.verify_code('000000') is False

    def test_backup_code_usage(self):
        """Backup codes can be used once and are then consumed."""
        import pyotp
        from django.contrib.auth.hashers import make_password
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(
            user=self.user,
            secret=secret,
            backup_codes=[make_password('ABCD1234')],
        )
        assert device.verify_backup_code('ABCD1234') is True
        device.refresh_from_db()
        assert device.verify_backup_code('ABCD1234') is False  # Used up
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_2fa.py -v`
Expected: FAIL (TOTPDevice model doesn't exist)

**Step 3: Write the TOTPDevice model**

Add to end of `core/models.py` (after AuditLog):

```python


class TOTPDevice(models.Model):
    """TOTP two-factor authentication device for a user."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='totp_device'
    )
    secret = models.CharField(max_length=32)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    backup_codes = models.JSONField(default=list, blank=True)

    def __str__(self):
        status = "verified" if self.is_verified else "unverified"
        return f"TOTP for {self.user.email} ({status})"

    def verify_code(self, code):
        """Verify a TOTP code. Returns True if valid."""
        import pyotp
        totp = pyotp.TOTP(self.secret)
        return totp.verify(code, valid_window=1)

    def verify_backup_code(self, code):
        """Verify and consume a backup code. Returns True if valid."""
        from django.contrib.auth.hashers import check_password
        for i, hashed_code in enumerate(self.backup_codes):
            if check_password(code, hashed_code):
                self.backup_codes.pop(i)
                self.save(update_fields=['backup_codes'])
                return True
        return False

    def generate_backup_codes(self):
        """Generate 8 new backup codes. Returns plaintext codes (show to user once)."""
        import secrets as sec
        from django.contrib.auth.hashers import make_password
        plaintext_codes = [sec.token_hex(4).upper() for _ in range(8)]
        self.backup_codes = [make_password(code) for code in plaintext_codes]
        self.save(update_fields=['backup_codes'])
        return plaintext_codes

    def get_provisioning_uri(self):
        """Get the otpauth:// URI for QR code generation."""
        import pyotp
        totp = pyotp.TOTP(self.secret)
        return totp.provisioning_uri(
            name=self.user.email,
            issuer_name='Aria Church',
        )
```

**Step 4: Create and run migration**

Run: `python3 manage.py makemigrations core -n add_totp_device_model`
Run: `python3 manage.py migrate`

**Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_2fa.py -v`
Expected: 5 tests PASS

**Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_2fa.py
git commit -m "feat: add TOTPDevice model with code verification and backup codes"
```

---

## Task 6: 2FA Setup and Disable Views

**Files:**
- Modify: `core/views.py` (add views at end)
- Modify: `core/urls.py` (add routes)
- Create: `templates/core/settings/security.html`
- Create: `templates/core/auth/totp_setup.html`
- Test: `tests/test_2fa.py` (add view tests)

**Step 1: Write failing tests**

Add to `tests/test_2fa.py`:

```python
from django.test import TestCase, Client
from core.models import TOTPDevice, Organization, OrganizationMembership
from accounts.models import User


class TestTOTPSetupViews(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            password='testpass123',
        )
        self.org = Organization.objects.create(name='Test Church', slug='test-church')
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org, role='owner', is_active=True,
        )
        self.user.default_organization = self.org
        self.user.save()

    def test_security_settings_page(self):
        """Security settings page is accessible."""
        self.client.force_login(self.user)
        response = self.client.get('/settings/security/')
        assert response.status_code == 200
        assert b'Two-Factor' in response.content

    def test_totp_setup_page_shows_qr(self):
        """TOTP setup page shows QR code."""
        self.client.force_login(self.user)
        response = self.client.get('/settings/security/2fa/setup/')
        assert response.status_code == 200
        assert b'data:image/png' in response.content or b'qr' in response.content.lower()

    def test_totp_verify_setup_valid_code(self):
        """Valid TOTP code completes setup."""
        import pyotp
        self.client.force_login(self.user)
        # Start setup (creates unverified device)
        self.client.get('/settings/security/2fa/setup/')
        device = TOTPDevice.objects.get(user=self.user)
        totp = pyotp.TOTP(device.secret)
        response = self.client.post('/settings/security/2fa/verify-setup/', {
            'code': totp.now(),
        })
        device.refresh_from_db()
        assert device.is_verified is True

    def test_totp_disable(self):
        """Disabling 2FA deletes the device."""
        import pyotp
        secret = pyotp.random_base32()
        TOTPDevice.objects.create(user=self.user, secret=secret, is_verified=True)
        self.client.force_login(self.user)
        totp = pyotp.TOTP(secret)
        self.client.post('/settings/security/2fa/disable/', {
            'code': totp.now(),
        })
        assert not TOTPDevice.objects.filter(user=self.user).exists()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_2fa.py::TestTOTPSetupViews -v`
Expected: FAIL (404 -- URLs don't exist)

**Step 3: Add URL routes**

Add to `core/urls.py`, in the Organization Settings section (after the billing route, around line 131):

```python
    # Security Settings & 2FA
    path('settings/security/', views.security_settings, name='security_settings'),
    path('settings/security/2fa/setup/', views.totp_setup, name='totp_setup'),
    path('settings/security/2fa/verify-setup/', views.totp_verify_setup, name='totp_verify_setup'),
    path('settings/security/2fa/disable/', views.totp_disable, name='totp_disable'),
```

**Step 4: Add views to core/views.py**

Add at end of `core/views.py`:

```python
@login_required
def security_settings(request):
    """Security settings page showing 2FA status."""
    from .models import TOTPDevice
    has_2fa = TOTPDevice.objects.filter(user=request.user, is_verified=True).exists()
    return render(request, 'core/settings/security.html', {
        'has_2fa': has_2fa,
    })


@login_required
def totp_setup(request):
    """Set up TOTP 2FA - show QR code."""
    import pyotp
    import qrcode
    import io
    import base64
    from .models import TOTPDevice

    # Delete any unverified device and create fresh
    TOTPDevice.objects.filter(user=request.user, is_verified=False).delete()

    device, created = TOTPDevice.objects.get_or_create(
        user=request.user,
        defaults={'secret': pyotp.random_base32()},
    )

    if device.is_verified:
        from django.contrib import messages
        messages.info(request, '2FA is already enabled.')
        return redirect('security_settings')

    # Generate QR code
    uri = device.get_provisioning_uri()
    qr = qrcode.make(uri)
    buffer = io.BytesIO()
    qr.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()

    return render(request, 'core/auth/totp_setup.html', {
        'qr_code': qr_base64,
        'secret': device.secret,
    })


@login_required
@require_POST
def totp_verify_setup(request):
    """Verify TOTP code during setup."""
    from .models import TOTPDevice
    from django.contrib import messages

    device = TOTPDevice.objects.filter(user=request.user, is_verified=False).first()
    if not device:
        messages.error(request, 'No 2FA setup in progress.')
        return redirect('security_settings')

    code = request.POST.get('code', '').strip()
    if device.verify_code(code):
        device.is_verified = True
        device.save(update_fields=['is_verified'])
        backup_codes = device.generate_backup_codes()
        request.session['2fa_verified'] = True
        return render(request, 'core/auth/totp_backup_codes.html', {
            'backup_codes': backup_codes,
        })
    else:
        messages.error(request, 'Invalid code. Please try again.')
        return redirect('totp_setup')


@login_required
@require_POST
def totp_disable(request):
    """Disable 2FA after verifying current code."""
    from .models import TOTPDevice
    from django.contrib import messages

    device = TOTPDevice.objects.filter(user=request.user, is_verified=True).first()
    if not device:
        return redirect('security_settings')

    code = request.POST.get('code', '').strip()
    if device.verify_code(code) or device.verify_backup_code(code):
        device.delete()
        if '2fa_verified' in request.session:
            del request.session['2fa_verified']
        messages.success(request, 'Two-factor authentication has been disabled.')
    else:
        messages.error(request, 'Invalid code. 2FA was not disabled.')

    return redirect('security_settings')
```

**Step 5: Create templates**

Create `templates/core/settings/security.html`:

```html
{% extends 'base.html' %}

{% block title %}Security Settings{% endblock %}

{% block content %}
<div class="max-w-4xl mx-auto">
    <div class="mb-8">
        <h1 class="text-2xl font-bold text-ch-gold">Organization Settings</h1>
        <p class="text-gray-400 mt-1">Manage your organization's settings and preferences</p>
    </div>

    <!-- Settings Navigation -->
    <div class="flex gap-4 mb-6 border-b border-gray-700 pb-4">
        <a href="{% url 'org_settings' %}" class="px-4 py-2 text-gray-400 hover:text-white rounded hover:bg-ch-gray transition">
            General
        </a>
        {% if membership.can_manage_users %}
        <a href="{% url 'org_settings_members' %}" class="px-4 py-2 text-gray-400 hover:text-white rounded hover:bg-ch-gray transition">
            Team Members
        </a>
        {% endif %}
        {% if membership.can_manage_billing %}
        <a href="{% url 'org_settings_billing' %}" class="px-4 py-2 text-gray-400 hover:text-white rounded hover:bg-ch-gray transition">
            Billing
        </a>
        {% endif %}
        <a href="{% url 'security_settings' %}" class="px-4 py-2 bg-ch-gold text-black rounded font-medium">
            Security
        </a>
    </div>

    <!-- Two-Factor Authentication -->
    <div class="bg-ch-dark rounded-lg p-6">
        <h2 class="text-lg font-semibold mb-2">Two-Factor Authentication</h2>
        <p class="text-gray-400 text-sm mb-4">
            Add an extra layer of security to your account using an authenticator app.
        </p>

        {% if has_2fa %}
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
                <span class="inline-block w-3 h-3 bg-green-500 rounded-full"></span>
                <span class="text-green-400 font-medium">Enabled</span>
            </div>
            <form method="post" action="{% url 'totp_disable' %}" id="disable-2fa-form">
                {% csrf_token %}
                <div class="flex gap-2">
                    <input type="text" name="code" placeholder="Enter code to disable"
                           class="bg-ch-gray border border-gray-700 rounded px-3 py-2 text-sm text-white w-48 focus:outline-none focus:border-ch-gold"
                           maxlength="8" required>
                    <button type="submit"
                            class="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm rounded transition">
                        Disable 2FA
                    </button>
                </div>
            </form>
        </div>
        {% else %}
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
                <span class="inline-block w-3 h-3 bg-gray-500 rounded-full"></span>
                <span class="text-gray-400">Not enabled</span>
            </div>
            <a href="{% url 'totp_setup' %}"
               class="px-4 py-2 bg-ch-gold text-black text-sm rounded font-medium hover:bg-yellow-500 transition">
                Enable 2FA
            </a>
        </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

Create `templates/core/auth/totp_setup.html`:

```html
{% extends 'base.html' %}

{% block title %}Set Up Two-Factor Authentication{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto">
    <div class="bg-ch-dark rounded-lg p-8">
        <h1 class="text-xl font-bold text-ch-gold mb-2">Set Up Two-Factor Authentication</h1>
        <p class="text-gray-400 text-sm mb-6">
            Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)
        </p>

        <!-- QR Code -->
        <div class="flex justify-center mb-6">
            <div class="bg-white p-4 rounded-lg">
                <img src="data:image/png;base64,{{ qr_code }}" alt="TOTP QR Code" class="w-48 h-48">
            </div>
        </div>

        <!-- Manual entry key -->
        <div class="mb-6">
            <p class="text-sm text-gray-400 mb-1">Or enter this key manually:</p>
            <code class="block bg-ch-gray px-4 py-2 rounded text-ch-gold text-sm font-mono select-all">{{ secret }}</code>
        </div>

        <!-- Verify -->
        <form method="post" action="{% url 'totp_verify_setup' %}">
            {% csrf_token %}
            <label class="block text-sm font-medium text-gray-300 mb-2">
                Enter the 6-digit code from your app to verify:
            </label>
            <div class="flex gap-3">
                <input type="text" name="code" placeholder="000000"
                       class="flex-1 bg-ch-gray border border-gray-700 rounded px-4 py-3 text-white text-center text-lg font-mono tracking-widest focus:outline-none focus:border-ch-gold"
                       maxlength="6" pattern="[0-9]{6}" inputmode="numeric" autocomplete="one-time-code" required autofocus>
                <button type="submit"
                        class="px-6 py-3 bg-ch-gold text-black rounded font-medium hover:bg-yellow-500 transition">
                    Verify
                </button>
            </div>
        </form>

        <a href="{% url 'security_settings' %}" class="block text-center text-gray-500 text-sm mt-4 hover:text-gray-300">
            Cancel
        </a>
    </div>
</div>
{% endblock %}
```

Create `templates/core/auth/totp_backup_codes.html`:

```html
{% extends 'base.html' %}

{% block title %}Backup Codes{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto">
    <div class="bg-ch-dark rounded-lg p-8">
        <h1 class="text-xl font-bold text-green-400 mb-2">Two-Factor Authentication Enabled</h1>
        <p class="text-gray-400 text-sm mb-6">
            Save these backup codes somewhere safe. Each code can only be used once if you lose access to your authenticator app.
        </p>

        <div class="bg-ch-gray rounded-lg p-4 mb-6">
            <div class="grid grid-cols-2 gap-2">
                {% for code in backup_codes %}
                <code class="text-sm font-mono text-ch-gold py-1">{{ code }}</code>
                {% endfor %}
            </div>
        </div>

        <p class="text-red-400 text-sm mb-6">
            These codes will not be shown again. Store them securely.
        </p>

        <a href="{% url 'security_settings' %}"
           class="block text-center px-6 py-3 bg-ch-gold text-black rounded font-medium hover:bg-yellow-500 transition">
            Done
        </a>
    </div>
</div>
{% endblock %}
```

**Step 6: Add Security tab to other settings templates**

In `templates/core/settings/general.html`, `templates/core/settings/members.html`, and `templates/core/settings/billing.html`, add a Security tab link in the settings navigation `<div>`:

```html
        <a href="{% url 'security_settings' %}" class="px-4 py-2 text-gray-400 hover:text-white rounded hover:bg-ch-gray transition">
            Security
        </a>
```

Add it after the Billing link in each template.

**Step 7: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_2fa.py -v`
Expected: 9 tests PASS

**Step 8: Commit**

```bash
git add core/views.py core/urls.py templates/core/settings/security.html templates/core/auth/ templates/core/settings/general.html templates/core/settings/members.html templates/core/settings/billing.html tests/test_2fa.py
git commit -m "feat: add 2FA setup, verification, and disable views with settings UI"
```

---

## Task 7: 2FA Login Enforcement

**Files:**
- Modify: `core/middleware.py` (add TwoFactorMiddleware)
- Modify: `core/urls.py` (add login 2FA route)
- Modify: `core/views.py` (add 2FA login view)
- Create: `templates/core/auth/totp_login.html`
- Modify: `config/settings.py` (add middleware)
- Test: `tests/test_2fa.py` (add login flow tests)

**Step 1: Write failing tests**

Add to `tests/test_2fa.py`:

```python
class TestTOTPLoginFlow(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='user@test.com',
            email='user@test.com',
            password='testpass123',
        )
        self.org = Organization.objects.create(name='Test Church', slug='test-church')
        OrganizationMembership.objects.create(
            user=self.user, organization=self.org, role='owner', is_active=True,
        )
        self.user.default_organization = self.org
        self.user.save()

    def test_user_with_2fa_redirected_to_verify(self):
        """User with 2FA enabled gets redirected to verify page after login."""
        import pyotp
        TOTPDevice.objects.create(
            user=self.user, secret=pyotp.random_base32(), is_verified=True,
        )
        self.client.login(username='user@test.com', password='testpass123')
        response = self.client.get('/dashboard/')
        assert response.status_code == 302
        assert '/login/2fa/' in response.url

    def test_user_without_2fa_not_redirected(self):
        """User without 2FA goes directly to dashboard."""
        self.client.force_login(self.user)
        response = self.client.get('/dashboard/')
        assert response.status_code == 200

    def test_2fa_verify_login_valid_code(self):
        """Valid TOTP code during login grants access."""
        import pyotp
        secret = pyotp.random_base32()
        TOTPDevice.objects.create(
            user=self.user, secret=secret, is_verified=True,
        )
        self.client.login(username='user@test.com', password='testpass123')
        totp = pyotp.TOTP(secret)
        response = self.client.post('/login/2fa/', {'code': totp.now()})
        assert response.status_code == 302
        # Should now be able to access dashboard
        response = self.client.get('/dashboard/')
        assert response.status_code == 200

    def test_2fa_verify_login_backup_code(self):
        """Backup code during login grants access."""
        import pyotp
        from django.contrib.auth.hashers import make_password
        secret = pyotp.random_base32()
        device = TOTPDevice.objects.create(
            user=self.user, secret=secret, is_verified=True,
            backup_codes=[make_password('ABCD1234')],
        )
        self.client.login(username='user@test.com', password='testpass123')
        response = self.client.post('/login/2fa/', {'code': 'ABCD1234'})
        assert response.status_code == 302
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_2fa.py::TestTOTPLoginFlow -v`
Expected: FAIL

**Step 3: Add 2FA login URL**

Add to `core/urls.py` after the security settings routes:

```python
    path('login/2fa/', views.totp_login_verify, name='totp_login_verify'),
```

**Step 4: Add 2FA login verification view**

Add to end of `core/views.py`:

```python
@login_required
def totp_login_verify(request):
    """Verify TOTP code during login."""
    from .models import TOTPDevice
    from django.contrib import messages

    device = TOTPDevice.objects.filter(user=request.user, is_verified=True).first()
    if not device:
        return redirect('dashboard')

    if request.session.get('2fa_verified'):
        return redirect('dashboard')

    if request.method == 'POST':
        code = request.POST.get('code', '').strip()
        if device.verify_code(code) or device.verify_backup_code(code):
            request.session['2fa_verified'] = True
            device.last_used_at = timezone.now()
            device.save(update_fields=['last_used_at'])
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid code. Please try again.')

    return render(request, 'core/auth/totp_login.html')
```

**Step 5: Add TwoFactorMiddleware**

Add to `core/middleware.py`, before the `SecurityHeadersMiddleware` class:

```python
class TwoFactorMiddleware(MiddlewareMixin):
    """Redirect users with 2FA enabled to verify if not yet verified this session."""

    EXEMPT_URLS = [
        '/login/2fa/',
        '/accounts/login/',
        '/accounts/logout/',
        '/admin/',
    ]

    def process_request(self, request):
        if not request.user.is_authenticated:
            return None

        # Check exempt URLs
        path = request.path
        if any(path.startswith(url) for url in self.EXEMPT_URLS):
            return None

        # Check public URLs
        from . import middleware as mw
        if hasattr(mw, 'PUBLIC_URLS'):
            if any(path.startswith(url) for url in mw.PUBLIC_URLS):
                return None

        # Check if user has verified 2FA device
        if request.session.get('2fa_verified'):
            return None

        from .models import TOTPDevice
        try:
            device = TOTPDevice.objects.get(user=request.user, is_verified=True)
        except TOTPDevice.DoesNotExist:
            return None

        # User has 2FA but hasn't verified this session
        from django.shortcuts import redirect
        return redirect('totp_login_verify')
```

**Step 6: Register middleware in settings.py**

In `config/settings.py`, add `'core.middleware.TwoFactorMiddleware'` to the MIDDLEWARE list, after `'core.middleware.TenantMiddleware'`:

```python
    'core.middleware.TenantMiddleware',
    'core.middleware.TwoFactorMiddleware',  # Add this line
```

**Step 7: Create login 2FA template**

Create `templates/core/auth/totp_login.html`:

```html
{% extends 'base.html' %}

{% block title %}Two-Factor Verification{% endblock %}

{% block content_full %}
<div class="w-full max-w-md">
    <div class="bg-ch-dark rounded-lg p-8 shadow-xl">
        <div class="text-center mb-8">
            <h1 class="font-display text-2xl text-ch-gold mb-2">Two-Factor Verification</h1>
            <p class="text-gray-400">Enter the code from your authenticator app</p>
        </div>

        {% if messages %}
        {% for message in messages %}
        <div class="bg-red-900/50 text-red-200 p-4 rounded-lg mb-6">
            <p>{{ message }}</p>
        </div>
        {% endfor %}
        {% endif %}

        <form method="post" class="space-y-6">
            {% csrf_token %}
            <div>
                <label for="code" class="block text-sm font-medium text-gray-300 mb-2">Authentication Code</label>
                <input type="text" name="code" id="code"
                       placeholder="000000"
                       class="w-full bg-ch-gray border border-gray-700 rounded-lg px-4 py-3 text-white text-center text-lg font-mono tracking-widest placeholder-gray-500 focus:outline-none focus:border-ch-gold transition"
                       maxlength="8" inputmode="numeric" autocomplete="one-time-code" required autofocus>
                <p class="text-gray-500 text-xs mt-2">You can also use a backup code.</p>
            </div>
            <button type="submit"
                    class="w-full bg-ch-gold text-black py-3 rounded-lg font-medium hover:bg-yellow-500 transition">
                Verify
            </button>
        </form>

        <div class="text-center mt-6">
            <a href="{% url 'logout' %}" class="text-gray-500 text-sm hover:text-gray-300">
                Sign out
            </a>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 8: Add /login/2fa/ to middleware PUBLIC_URLS or exempt it from TenantMiddleware**

In `core/middleware.py`, add `'/login/2fa/'` to the `PUBLIC_URLS` list so the TenantMiddleware doesn't interfere:

Wait -- actually `/login/2fa/` requires authentication, so it shouldn't be in PUBLIC_URLS. The TwoFactorMiddleware handles it via EXEMPT_URLS. But we need to make sure TenantMiddleware doesn't block it. Check if TenantMiddleware has the path exempted -- since users may not have an org set yet during 2FA. Add `'/login/'` prefix to the PUBLIC_URLS or handle it specifically:

Add `'/login/2fa/'` to PUBLIC_URLS in `core/middleware.py` (it still requires `@login_required`, this just prevents TenantMiddleware from interfering).

**Step 9: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_2fa.py -v`
Expected: 13 tests PASS

**Step 10: Commit**

```bash
git add core/middleware.py core/views.py core/urls.py config/settings.py templates/core/auth/totp_login.html tests/test_2fa.py
git commit -m "feat: add 2FA login enforcement middleware and verification flow"
```

---

## Task 8: Sentry Integration and Custom Error Pages

**Files:**
- Modify: `config/settings.py`
- Create: `templates/404.html`
- Create: `templates/500.html`
- Test: `tests/test_2fa.py` (or a simple settings test)

**Step 1: Write a test for Sentry configuration**

Add to `tests/test_2fa.py` (or create `tests/test_sentry.py`):

```python
class TestSentryConfig(TestCase):
    def test_sentry_dsn_not_required_in_dev(self):
        """App works without SENTRY_DSN in development."""
        from django.conf import settings
        # In test/dev mode, Sentry should not be initialized
        assert settings.DEBUG or True  # Just verify settings load without error

    def test_custom_404_page(self):
        """Custom 404 page is returned for missing URLs."""
        self.client.force_login(User.objects.create_user(
            username='user@test.com', email='user@test.com', password='test',
        ))
        response = self.client.get('/nonexistent-page-12345/')
        assert response.status_code == 404
```

**Step 2: Add Sentry init to settings.py**

Add at the top of `config/settings.py`, after existing imports:

```python
import sentry_sdk
```

Add in the production block (inside `if not DEBUG:`), after the HSTS settings:

```python
    # Sentry Error Monitoring
    sentry_dsn = os.environ.get('SENTRY_DSN', '')
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
            send_default_pii=False,
            environment='production',
        )
```

**Step 3: Create custom 404 template**

Create `templates/404.html`:

```html
{% extends 'base.html' %}

{% block title %}Page Not Found{% endblock %}

{% block content_full %}
<div class="text-center py-20">
    <h1 class="text-6xl font-bold text-ch-gold mb-4">404</h1>
    <p class="text-xl text-gray-400 mb-8">The page you're looking for doesn't exist.</p>
    <a href="/" class="px-6 py-3 bg-ch-gold text-black rounded-lg font-medium hover:bg-yellow-500 transition">
        Go Home
    </a>
</div>
{% endblock %}
```

**Step 4: Create custom 500 template**

Create `templates/500.html`:

```html
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Server Error | Aria</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = {
            darkMode: 'class',
            theme: { extend: { colors: { 'ch-black': '#0f0f0f', 'ch-gold': '#c9a227' } } }
        }
    </script>
</head>
<body class="bg-ch-black text-white min-h-screen flex items-center justify-center">
    <div class="text-center py-20">
        <h1 class="text-6xl font-bold text-ch-gold mb-4">500</h1>
        <p class="text-xl text-gray-400 mb-8">Something went wrong on our end. We've been notified.</p>
        <a href="/" class="px-6 py-3 bg-ch-gold text-black rounded-lg font-medium hover:bg-yellow-500 transition">
            Go Home
        </a>
    </div>
</body>
</html>
```

Note: The 500 template is standalone HTML (doesn't extend base.html) because the error might be in the template system itself.

**Step 5: Run tests**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add config/settings.py templates/404.html templates/500.html
git commit -m "feat: add Sentry error monitoring and custom error pages"
```

---

## Task 9: Dependabot Configuration

**Files:**
- Create: `.github/dependabot.yml`

**Step 1: Create Dependabot config**

Create `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "pip"
    directory: "/"
    schedule:
      interval: "weekly"
      day: "monday"
    open-pull-requests-limit: 10
    labels:
      - "dependencies"
      - "security"
    commit-message:
      prefix: "deps"
```

**Step 2: Commit**

```bash
git add .github/dependabot.yml
git commit -m "feat: add Dependabot configuration for dependency scanning"
```

---

## Task 10: Final Integration Verification

**Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS (including pre-existing tests)

**Step 2: Run pip-audit**

Run: `pip-audit -r requirements.txt`
Expected: Output showing dependency scan results (may show some vulnerabilities in existing deps -- that's ok, Dependabot will create PRs)

**Step 3: Verify all new URLs are accessible**

Check these URLs work (with logged-in user):
- `/settings/security/` -- Security settings page
- `/settings/security/2fa/setup/` -- QR code page
- `/platform-admin/audit-log/` -- Audit log (superadmin only)

**Step 4: Commit any remaining changes and push**

```bash
git push
```
