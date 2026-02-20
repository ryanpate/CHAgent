# Security Round 2 Design

**Date:** 2026-02-19
**Status:** Approved

## Overview

Second round of security features for Aria: two-factor authentication (TOTP), audit logging for admin actions, dependency vulnerability scanning, and Sentry error monitoring. Builds on the security hardening completed earlier (HSTS, CSP, django-axes, session timeout).

## 1. Two-Factor Authentication (TOTP)

### Approach

Custom implementation using `pyotp` + `qrcode[pil]`. Avoids django-two-factor-auth to maintain full control over HTMX + Tailwind UI.

### New Model: `TOTPDevice`

Fields:
- `user` (OneToOneField to User)
- `secret` (CharField, max 32, Base32-encoded TOTP secret)
- `is_verified` (BooleanField, default False -- True after first successful verification)
- `created_at` (DateTimeField, auto_now_add)
- `last_used_at` (DateTimeField, nullable)
- `backup_codes` (JSONField, default list -- 8 hashed one-time backup codes)

### Setup Flow

1. User goes to Settings > Security (new tab)
2. Clicks "Enable Two-Factor Authentication"
3. Shown QR code and manual entry key
4. User scans with authenticator app, enters 6-digit code to verify
5. Shown 8 backup codes to save, must confirm they've saved them
6. 2FA is now active (`is_verified = True`)

### Login Flow

1. User enters email + password (existing flow)
2. If user has verified TOTPDevice, redirect to `/login/2fa/`
3. User enters 6-digit code from authenticator app (or backup code)
4. On success, `request.session['2fa_verified'] = True`, continue to dashboard
5. On failure, show error, allow retry

### Disable Flow

1. User goes to Settings > Security
2. Clicks "Disable 2FA"
3. Must enter current TOTP code to confirm
4. Device is deleted

### Middleware

If user has verified TOTP device and session lacks `2fa_verified`, redirect to 2FA verification page. Exempt: login page, 2FA page, logout, public URLs.

### URL Routes

- `/settings/security/` -- Security settings page (2FA status, setup/disable button)
- `/settings/security/2fa/setup/` -- QR code display and initial verification
- `/settings/security/2fa/verify-setup/` -- Verify TOTP code during setup
- `/settings/security/2fa/disable/` -- Disable 2FA (requires TOTP code)
- `/login/2fa/` -- 2FA verification during login

### Packages

- `pyotp` -- TOTP code generation and verification
- `qrcode[pil]` -- QR code image generation

### Key Details

- TOTP secret stored as plaintext (must be readable for verification, same protection level as PCO credentials)
- Session flag: `request.session['2fa_verified'] = True`
- Backup codes: 8 codes, each usable once, hashed with `django.contrib.auth.hashers.make_password`
- QR code label: "Aria (user@email.com)"
- Issuer: "Aria Church"
- Optional for all users, not enforced

## 2. Audit Logging (Admin Actions)

### Approach

Custom AuditLog model with helper function. Scoped to admin and org management actions only.

### New Model: `AuditLog`

Fields:
- `user` (FK to User, SET_NULL, nullable -- who performed the action)
- `action` (CharField, max 50, choices -- see below)
- `timestamp` (DateTimeField, auto_now_add)
- `ip_address` (GenericIPAddressField, nullable)
- `organization` (FK to Organization, SET_NULL, nullable)
- `target_user` (FK to User, SET_NULL, nullable, related_name='audit_target')
- `details` (JSONField, default dict -- flexible context)

### Action Choices

- `beta_approve` -- Beta Request Approved
- `beta_reject` -- Beta Request Rejected
- `org_status_change` -- Organization Status Changed
- `org_impersonate` -- Organization Impersonated
- `user_role_change` -- User Role Changed
- `user_removed` -- User Removed
- `invitation_sent` -- Invitation Sent
- `invitation_cancelled` -- Invitation Cancelled
- `settings_updated` -- Settings Updated

### Helper Function

```python
def log_admin_action(request, action, organization=None, target_user=None, **details):
    AuditLog.objects.create(
        user=request.user,
        action=action,
        ip_address=get_client_ip(request),
        organization=organization,
        target_user=target_user,
        details=details,
    )
```

### Instrumentation Points

In `admin_views.py`:
- `admin_beta_approve` -- beta_approve
- `admin_beta_reject` -- beta_reject
- `admin_organization_update_status` -- org_status_change
- `admin_organization_impersonate` -- org_impersonate

In `views.py`:
- `org_update_member_role` -- user_role_change
- `org_remove_member` -- user_removed
- `org_invite_member` -- invitation_sent
- `org_cancel_invitation` -- invitation_cancelled

### Admin Dashboard View

New section in platform admin: "Audit Log"
- Table: timestamp, user, action, organization, target, details
- Filter by action type and date range
- Paginated (25 per page), most recent first
- URL: `/platform-admin/audit-log/`

## 3. Dependency Vulnerability Scanning

### GitHub Dependabot

Create `.github/dependabot.yml`:
- Package ecosystem: pip
- Directory: /
- Schedule: weekly
- Auto-create PRs for security updates
- Labels: dependencies, security
- Limit: 10 open PRs

### pip-audit (Local/CI)

- Add `pip-audit` to dev requirements
- Run locally: `pip-audit -r requirements.txt`
- Optional CI integration later

## 4. Sentry Error Monitoring

### Package

`sentry-sdk[django]`

### Configuration (settings.py)

```python
import sentry_sdk

if not DEBUG:
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN', ''),
        traces_sample_rate=0.1,
        profiles_sample_rate=0.1,
        send_default_pii=False,
        environment="production",
    )
```

### Key Details

- New env var: `SENTRY_DSN`
- `send_default_pii=False` -- no personally identifiable info sent (church member data protection)
- Low sample rates (10%) to stay within free tier (5K events/month)
- Automatic Django middleware captures unhandled exceptions
- No custom instrumentation needed for basic error tracking

### Custom Error Pages

- `templates/404.html` -- User-friendly "Page Not Found"
- `templates/500.html` -- User-friendly "Server Error"
- Both extend base template styling

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `core/models.py` | Modify | Add TOTPDevice and AuditLog models |
| `core/views.py` | Modify | Add security settings views, TOTP setup/verify/disable views, instrument audit logging |
| `core/admin_views.py` | Modify | Instrument audit logging, add audit log view |
| `core/urls.py` | Modify | Add security settings, 2FA, and audit log routes |
| `core/middleware.py` | Modify | Add 2FA enforcement middleware, add /settings/security/ and /login/2fa/ to appropriate URL lists |
| `config/settings.py` | Modify | Add Sentry SDK init, add SENTRY_DSN env var |
| `requirements.txt` | Modify | Add pyotp, qrcode[pil], sentry-sdk[django], pip-audit |
| `templates/core/settings/security.html` | Create | Security settings page with 2FA status |
| `templates/core/auth/totp_setup.html` | Create | QR code and verification form |
| `templates/core/auth/totp_login.html` | Create | 2FA login verification page |
| `templates/core/admin/audit_log.html` | Create | Audit log admin view |
| `templates/404.html` | Create | Custom 404 error page |
| `templates/500.html` | Create | Custom 500 error page |
| `.github/dependabot.yml` | Create | Dependabot configuration |
| Migration file | Create | TOTPDevice and AuditLog models |
