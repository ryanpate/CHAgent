# Beta Testing & Security Hardening Design

**Date:** 2026-02-19
**Status:** Approved

## Overview

Transition Aria from open signup to closed beta. Add a beta request system with admin approval, update public-facing pages to reflect beta status, create a dedicated security page, and implement missing security headers.

## 1. Beta Request System

### New Model: `BetaRequest`

Fields:
- `name` (CharField, max 200)
- `email` (EmailField, unique)
- `church_name` (CharField, max 200)
- `church_size` (CharField, choices: under_100, 100-500, 500-2000, 2000+)
- `status` (CharField, choices: pending, approved, rejected, invited, signed_up; default: pending)
- `created_at` (DateTimeField, auto_now_add)
- `reviewed_at` (DateTimeField, nullable)
- `reviewed_by` (FK to User, nullable)
- `rejection_reason` (TextField, blank)
- `invitation` (FK to OrganizationInvitation, nullable)
- `referral_source` (CharField, max 100, blank)

### Flow

1. Visitor fills out beta request form at `/signup/` (replaces current signup form)
2. Request saved as `pending`
3. Confirmation page shown: "Thanks! We'll review your request and reach out soon."
4. Platform admin sees pending requests in `/platform-admin/` dashboard
5. On approval: auto-creates `OrganizationInvitation`, sends email with signup link
6. Signup link uses existing invitation acceptance flow
7. Onboarding skips Stripe checkout (beta orgs are free)

### Organization Changes

- Add `beta` to `SUBSCRIPTION_STATUS_CHOICES` in Organization model
- When beta org is created, set `subscription_status = 'beta'`
- Beta orgs skip the checkout step in onboarding
- Beta orgs get full feature access (equivalent to Ministry plan)

### Admin View

Add "Beta Requests" section to platform-admin dashboard:
- Table: name, email, church name, church size, status, date
- Filter by status
- Approve/reject buttons
- Approval triggers invitation email automatically

## 2. Landing Page Updates

### Header
- Add "Beta" pill badge next to logo (gold/amber)

### Hero Section
- Keep headline: "AI-Powered Worship Team Management Software"
- Add subtitle: "Currently in closed beta -- request early access"
- Replace "Start Free Trial" button with "Request Beta Access" (links to `/signup/`)
- Keep "View Pricing" button

### Beta Banner
- Top-of-page banner on all public pages (base_public.html)
- Text: "Aria is in closed beta. We're onboarding churches one at a time to ensure a great experience."
- Link: "Request Access" pointing to `/signup/`
- Gold/amber background
- Dismissible (JS + localStorage)

### Interactive Demo
- No changes -- keep as-is

### Feature Cards
- No changes -- keep as-is

### Pricing Page
- Add note: "During beta, all features are free. These will be the prices after beta ends."
- Replace subscribe buttons with "Free During Beta" (non-clickable or links to `/signup/`)

### Footer
- Add link to `/security/`

## 3. Security Page (`/security/`)

### URL
- `/security/` -- public, no auth required
- Add to PUBLIC_URLS in middleware
- Add to sitemap

### Template
- Extends `base_public.html`
- Two main sections

### Section 1: Plain-Language Overview

Topics covered:
- **Data Protection**: Organization data isolation, no cross-tenant access
- **Encryption**: HTTPS/TLS in transit, PBKDF2 password hashing
- **Access Controls**: Role-based permissions (Owner, Admin, Leader, Member, Viewer)
- **AI Privacy**: Conversations scoped to organization, not used for AI training
- **Planning Center**: Per-org credentials, OAuth tokens encrypted at rest
- **Payments**: Stripe handles billing, no credit card numbers stored on our servers

### Section 2: Technical Details (Collapsible)

Topics covered:
- Transport security: TLS 1.2+, HSTS, automatic HTTPS
- Security headers: CSP, X-Frame-Options, X-Content-Type-Options, X-XSS-Protection
- Authentication: PBKDF2, CSRF tokens, secure cookies, login rate limiting
- Multi-tenant isolation: Org-scoped queries, middleware enforcement
- Infrastructure: Railway hosting, PostgreSQL, connection pooling
- Session security: Server-side sessions, secure flags, timeout
- Invitation security: Cryptographic tokens, 7-day expiration

### Section 3: Responsible Disclosure

Email: security@aria.church

### Schema Markup

- BreadcrumbList for navigation
- WebPage schema with security-related keywords

## 4. Security Hardening

### settings.py Changes

```python
# HSTS (add to production block)
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Session timeout
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Referrer policy
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
```

### CSP Header

Add Content-Security-Policy via custom middleware or django-csp:
- `default-src 'self'`
- `script-src 'self' 'unsafe-inline'` (needed for HTMX and inline scripts)
- `style-src 'self' 'unsafe-inline'` (needed for Tailwind)
- `img-src 'self' data: https:`
- `font-src 'self' https://fonts.gstatic.com`
- `connect-src 'self'`
- `frame-ancestors 'none'`

### Login Rate Limiting

Add django-axes to requirements:
- Lock out after 5 failed attempts
- 30-minute lockout period
- Track by IP + username combination

### Permissions Policy Header

Add via middleware:
```
Permissions-Policy: camera=(), microphone=(), geolocation=(), payment=()
```

## 5. Security Assessment Summary

### Already Implemented
- CSRF protection with trusted origins
- SSL/HTTPS redirect in production
- Secure cookie flags (session + CSRF)
- Password validation (4 validators)
- Multi-tenant data isolation via middleware
- XSS protection header
- Content-type sniffing prevention
- X-Frame-Options: DENY
- Cryptographically secure invitation tokens (secrets.token_urlsafe)
- Django's built-in SQL injection prevention (ORM parameterized queries)
- Django's template auto-escaping (XSS prevention in templates)

### Implementing This Sprint
- HSTS header
- CSP header
- Login rate limiting (django-axes)
- Session timeout
- Referrer policy
- Permissions policy header

### Recommended for Later
- Two-factor authentication
- Audit logging for admin actions
- Penetration testing before public launch
- SOC 2 compliance process
- Dependency vulnerability scanning (Dependabot)
- Database encryption at rest

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `core/models.py` | Modify | Add BetaRequest model, add 'beta' subscription status |
| `core/views.py` | Modify | Replace signup view, add beta request view, add security page view, add beta admin views |
| `core/urls.py` | Modify | Add /security/ route |
| `config/settings.py` | Modify | Add security headers, HSTS, session timeout, django-axes config |
| `core/middleware.py` | Modify | Add /security/ to PUBLIC_URLS, add CSP middleware, add Permissions-Policy |
| `templates/core/landing.html` | Modify | Beta badge, updated CTAs, subtitle |
| `templates/core/onboarding/base_public.html` | Modify | Beta banner, footer link to security |
| `templates/core/onboarding/signup.html` | Modify | Replace with beta request form |
| `templates/core/security.html` | Create | Security page template |
| `templates/core/onboarding/beta_confirmation.html` | Create | Beta request confirmation page |
| `templates/core/onboarding/pricing.html` | Modify | Beta pricing notes |
| `core/sitemaps.py` | Modify | Add security page to sitemap |
| `requirements.txt` | Modify | Add django-axes |
| Migration file | Create | BetaRequest model migration |
