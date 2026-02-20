# Beta Testing & Security Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transition Aria from open signup to closed beta with admin-approved access, add security hardening, and create a public security page.

**Architecture:** New `BetaRequest` model replaces the signup form. Admin approves requests in platform-admin, which auto-sends invitation emails using the existing `OrganizationInvitation` system. Security headers (HSTS, CSP, rate limiting) are added to `settings.py` and middleware. A new `/security/` public page documents the platform's security posture.

**Tech Stack:** Django 5.x, django-axes (login rate limiting), custom CSP middleware, Tailwind CSS (via CDN)

---

### Task 1: Add BetaRequest Model

**Files:**
- Modify: `core/models.py` (after line ~460, near OrganizationInvitation)

**Step 1: Write the failing test**

Create file `tests/test_beta_request.py`:

```python
"""Tests for the BetaRequest model and beta request flow."""
import pytest
from django.test import Client
from core.models import BetaRequest


@pytest.mark.django_db
class TestBetaRequestModel:
    """Test BetaRequest model creation and status transitions."""

    def test_create_beta_request(self):
        """A beta request can be created with required fields."""
        req = BetaRequest.objects.create(
            name='John Pastor',
            email='john@firstchurch.org',
            church_name='First Community Church',
            church_size='medium',
        )
        assert req.status == 'pending'
        assert req.name == 'John Pastor'
        assert req.email == 'john@firstchurch.org'
        assert req.church_name == 'First Community Church'
        assert req.church_size == 'medium'
        assert req.created_at is not None

    def test_email_uniqueness(self):
        """Duplicate emails are rejected."""
        BetaRequest.objects.create(
            name='John', email='john@church.org',
            church_name='Church A', church_size='small',
        )
        with pytest.raises(Exception):
            BetaRequest.objects.create(
                name='Jane', email='john@church.org',
                church_name='Church B', church_size='large',
            )

    def test_str_representation(self):
        """String representation shows church name and email."""
        req = BetaRequest.objects.create(
            name='John', email='john@church.org',
            church_name='First Church', church_size='small',
        )
        assert 'First Church' in str(req)
        assert 'john@church.org' in str(req)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py -v`
Expected: FAIL — `ImportError: cannot import name 'BetaRequest' from 'core.models'`

**Step 3: Write the BetaRequest model**

Add to `core/models.py` after the `OrganizationInvitation` class (around line 460):

```python
class BetaRequest(models.Model):
    """
    Tracks requests for beta access to the platform.

    Admin reviews and approves/rejects requests from the platform admin dashboard.
    On approval, an OrganizationInvitation is auto-created and emailed.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('invited', 'Invitation Sent'),
        ('signed_up', 'Signed Up'),
    ]

    CHURCH_SIZE_CHOICES = [
        ('small', 'Under 100'),
        ('medium', '100-500'),
        ('large', '500-2,000'),
        ('mega', '2,000+'),
    ]

    name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    church_name = models.CharField(max_length=200)
    church_size = models.CharField(max_length=20, choices=CHURCH_SIZE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reviewed_beta_requests'
    )
    rejection_reason = models.TextField(blank=True)
    invitation = models.ForeignKey(
        'OrganizationInvitation', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='beta_request'
    )
    referral_source = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.church_name} ({self.email})"
```

Also add `'beta'` to the Organization `STATUS_CHOICES` (line ~127 of `core/models.py`):

```python
STATUS_CHOICES = [
    ('trial', 'Trial'),
    ('active', 'Active'),
    ('past_due', 'Past Due'),
    ('cancelled', 'Cancelled'),
    ('suspended', 'Suspended'),
    ('beta', 'Beta'),
]
```

**Step 4: Create and run migration**

Run: `cd /Users/ryanpate/chagent && python manage.py makemigrations core -n add_beta_request_model`
Run: `cd /Users/ryanpate/chagent && python manage.py migrate`

**Step 5: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py -v`
Expected: 3 passed

**Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_beta_request.py
git commit -m "feat: add BetaRequest model and beta subscription status"
```

---

### Task 2: Replace Signup View with Beta Request Form

**Files:**
- Modify: `core/views.py` (line ~3741, `onboarding_signup` function)
- Modify: `templates/core/onboarding/signup.html`
- Create: `templates/core/onboarding/beta_confirmation.html`

**Step 1: Write the failing test**

Add to `tests/test_beta_request.py`:

```python
@pytest.mark.django_db
class TestBetaRequestView:
    """Test the beta request form submission."""

    def test_signup_page_shows_beta_form(self):
        """GET /signup/ renders the beta request form."""
        client = Client()
        response = client.get('/signup/')
        assert response.status_code == 200
        assert b'Request Beta Access' in response.content

    def test_submit_beta_request(self):
        """POST /signup/ creates a BetaRequest and shows confirmation."""
        client = Client()
        response = client.post('/signup/', {
            'name': 'Sarah Pastor',
            'email': 'sarah@gracechurch.org',
            'church_name': 'Grace Community Church',
            'church_size': 'medium',
        })
        assert response.status_code == 200
        assert b'review your request' in response.content
        assert BetaRequest.objects.filter(email='sarah@gracechurch.org').exists()

    def test_submit_duplicate_email(self):
        """POST /signup/ with existing email shows error."""
        BetaRequest.objects.create(
            name='Existing', email='exists@church.org',
            church_name='Some Church', church_size='small',
        )
        client = Client()
        response = client.post('/signup/', {
            'name': 'New Person',
            'email': 'exists@church.org',
            'church_name': 'Another Church',
            'church_size': 'large',
        })
        assert response.status_code == 200
        assert b'already' in response.content.lower()

    def test_submit_missing_fields(self):
        """POST /signup/ with missing fields shows errors."""
        client = Client()
        response = client.post('/signup/', {
            'name': '',
            'email': 'test@church.org',
            'church_name': '',
            'church_size': 'small',
        })
        assert response.status_code == 200
        assert b'required' in response.content.lower()
        assert not BetaRequest.objects.filter(email='test@church.org').exists()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaRequestView -v`
Expected: FAIL — form shows old signup, not beta request

**Step 3: Replace the signup view**

In `core/views.py`, replace the `onboarding_signup` function (line ~3741) with:

```python
def onboarding_signup(request):
    """
    Beta request form - replaces the original signup page.

    Collects name, email, church name, and church size.
    Creates a BetaRequest for admin review.
    """
    from .models import BetaRequest

    # Redirect logged-in users to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        church_name = request.POST.get('church_name', '').strip()
        church_size = request.POST.get('church_size', '').strip()

        errors = []

        if not name:
            errors.append('Your name is required.')
        if not email:
            errors.append('Email address is required.')
        if not church_name:
            errors.append('Church name is required.')
        if not church_size:
            errors.append('Church size is required.')
        if email and BetaRequest.objects.filter(email=email).exists():
            errors.append('A request with this email already exists. We\'ll be in touch soon!')

        if errors:
            return render(request, 'core/onboarding/signup.html', {
                'errors': errors,
                'name': name,
                'email': email,
                'church_name': church_name,
                'church_size': church_size,
                'is_beta': True,
            })

        BetaRequest.objects.create(
            name=name,
            email=email,
            church_name=church_name,
            church_size=church_size,
        )

        return render(request, 'core/onboarding/beta_confirmation.html', {
            'church_name': church_name,
            'email': email,
        })

    return render(request, 'core/onboarding/signup.html', {'is_beta': True})
```

**Step 4: Replace the signup template**

Overwrite `templates/core/onboarding/signup.html`:

```html
{% extends "core/onboarding/base_public.html" %}

{% block title %}Request Beta Access{% endblock %}
{% block meta_description %}Request early access to Aria, AI-powered worship team management software. Join our closed beta program.{% endblock %}

{% block content %}
<div class="max-w-md mx-auto">
    <div class="bg-ch-dark rounded-lg border border-ch-gray p-8">
        <div class="flex items-center gap-2 mb-2">
            <h1 class="text-2xl font-bold text-white">Request Beta Access</h1>
            <span class="bg-ch-gold/20 text-ch-gold text-xs font-semibold px-2 py-1 rounded-full">BETA</span>
        </div>
        <p class="text-gray-400 mb-6">We're onboarding churches one at a time to ensure a great experience. Tell us about your team and we'll be in touch.</p>

        {% if errors %}
        <div class="bg-red-900/50 border border-red-500 rounded-lg p-4 mb-6">
            <ul class="text-red-300 text-sm">
                {% for error in errors %}
                <li>{{ error }}</li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}

        <form method="post" class="space-y-4">
            {% csrf_token %}

            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">Your Name</label>
                <input type="text" name="name" value="{{ name|default:'' }}"
                       required placeholder="John Smith"
                       class="w-full bg-ch-gray border border-ch-gray rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-ch-gold focus:ring-1 focus:ring-ch-gold outline-none">
            </div>

            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">Email Address</label>
                <input type="email" name="email" value="{{ email|default:'' }}"
                       required placeholder="john@church.org"
                       class="w-full bg-ch-gray border border-ch-gray rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-ch-gold focus:ring-1 focus:ring-ch-gold outline-none">
            </div>

            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">Church Name</label>
                <input type="text" name="church_name" value="{{ church_name|default:'' }}"
                       required placeholder="e.g., First Baptist Church"
                       class="w-full bg-ch-gray border border-ch-gray rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-ch-gold focus:ring-1 focus:ring-ch-gold outline-none">
            </div>

            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">Church Size</label>
                <select name="church_size" required
                        class="w-full bg-ch-gray border border-ch-gray rounded-lg px-4 py-3 text-white focus:border-ch-gold focus:ring-1 focus:ring-ch-gold outline-none">
                    <option value="">Select size...</option>
                    <option value="small" {% if church_size == 'small' %}selected{% endif %}>Under 100</option>
                    <option value="medium" {% if church_size == 'medium' %}selected{% endif %}>100 - 500</option>
                    <option value="large" {% if church_size == 'large' %}selected{% endif %}>500 - 2,000</option>
                    <option value="mega" {% if church_size == 'mega' %}selected{% endif %}>2,000+</option>
                </select>
            </div>

            <button type="submit"
                    class="w-full bg-ch-gold hover:bg-ch-gold/90 text-ch-black font-semibold py-3 px-6 rounded-lg transition-colors">
                Request Beta Access
            </button>
        </form>

        <p class="text-center text-gray-500 text-sm mt-6">
            Already have an account?
            <a href="{% url 'login' %}" class="text-ch-gold hover:underline">Sign in</a>
        </p>
    </div>

    <div class="mt-8 text-center">
        <p class="text-gray-400 mb-4">What you'll get with beta access:</p>
        <div class="grid grid-cols-2 gap-4 text-sm text-gray-300">
            <div class="flex items-center gap-2">
                <svg class="w-5 h-5 text-ch-gold flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                Full platform access
            </div>
            <div class="flex items-center gap-2">
                <svg class="w-5 h-5 text-ch-gold flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                Free during beta
            </div>
            <div class="flex items-center gap-2">
                <svg class="w-5 h-5 text-ch-gold flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                Direct support access
            </div>
            <div class="flex items-center gap-2">
                <svg class="w-5 h-5 text-ch-gold flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
                Shape the product
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 5: Create the confirmation template**

Create `templates/core/onboarding/beta_confirmation.html`:

```html
{% extends "core/onboarding/base_public.html" %}

{% block title %}Request Received{% endblock %}

{% block content %}
<div class="max-w-md mx-auto text-center">
    <div class="bg-ch-dark rounded-lg border border-ch-gray p-8">
        <div class="w-16 h-16 bg-ch-gold/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg class="w-8 h-8 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
            </svg>
        </div>
        <h1 class="text-2xl font-bold text-white mb-2">Request Received!</h1>
        <p class="text-gray-400 mb-4">
            Thanks for your interest in Aria, <strong class="text-white">{{ church_name }}</strong>.
        </p>
        <p class="text-gray-400 mb-6">
            We'll review your request and reach out to <strong class="text-white">{{ email }}</strong> when your spot is ready. We're onboarding churches one at a time to ensure everyone has a great experience.
        </p>
        <a href="/"
           class="inline-block bg-ch-gray hover:bg-ch-gray/80 text-white font-medium py-2 px-6 rounded-lg transition-colors border border-ch-gray hover:border-ch-gold/50">
            Back to Home
        </a>
    </div>
</div>
{% endblock %}
```

**Step 6: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py -v`
Expected: 7 passed (3 model + 4 view tests)

**Step 7: Commit**

```bash
git add core/views.py templates/core/onboarding/signup.html templates/core/onboarding/beta_confirmation.html tests/test_beta_request.py
git commit -m "feat: replace signup with beta request form"
```

---

### Task 3: Update Landing Page for Beta Branding

**Files:**
- Modify: `templates/core/landing.html`
- Modify: `templates/core/onboarding/base_public.html`

**Step 1: Write the failing test**

Add to `tests/test_beta_request.py`:

```python
@pytest.mark.django_db
class TestBetaLandingPage:
    """Test that public pages reflect beta status."""

    def test_landing_page_shows_beta_badge(self):
        """Landing page displays beta badge."""
        client = Client()
        response = client.get('/')
        assert response.status_code == 200
        assert b'BETA' in response.content

    def test_landing_page_has_request_access_cta(self):
        """Landing page CTA says 'Request Beta Access' not 'Start Free Trial'."""
        client = Client()
        response = client.get('/')
        assert b'Request Beta Access' in response.content
        assert b'Start Free Trial' not in response.content

    def test_beta_banner_on_public_pages(self):
        """Public pages include the beta banner."""
        client = Client()
        response = client.get('/')
        assert b'closed beta' in response.content.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaLandingPage -v`
Expected: FAIL — landing page still says "Start Free Trial"

**Step 3: Update base_public.html**

In `templates/core/onboarding/base_public.html`, make these changes:

1. Add beta banner after `<body>` tag (before the header, line ~71):

```html
<body class="bg-ch-black text-gray-100 min-h-screen">
    <!-- Beta Banner -->
    <div id="beta-banner" class="bg-ch-gold/10 border-b border-ch-gold/30 py-2 px-4 text-center text-sm">
        <span class="text-ch-gold">Aria is in closed beta.</span>
        <span class="text-gray-300">We're onboarding churches one at a time to ensure a great experience.</span>
        <a href="{% url 'onboarding_signup' %}" class="text-ch-gold font-medium hover:underline ml-1">Request Access</a>
        <button onclick="document.getElementById('beta-banner').style.display='none';localStorage.setItem('beta-banner-dismissed','1')" class="ml-2 text-gray-500 hover:text-gray-300">&times;</button>
    </div>
    <script>if(localStorage.getItem('beta-banner-dismissed')==='1')document.getElementById('beta-banner').style.display='none';</script>
```

2. Add beta badge next to logo in header (line ~76):

```html
<a href="/" class="text-2xl font-bold text-ch-gold">Aria</a>
<span class="bg-ch-gold/20 text-ch-gold text-xs font-semibold px-2 py-0.5 rounded-full ml-2">BETA</span>
```

3. Update footer (line ~95) to add security link:

```html
<footer class="bg-ch-dark border-t border-ch-gray py-4 px-6 text-center text-gray-500 text-sm">
    <p>&copy; {% now "Y" %} Aria. All rights reserved.</p>
    <p class="text-xs text-gray-600 mt-2">
        <a href="{% url 'security' %}" class="hover:text-gray-400">Security</a>
        <span class="mx-2">|</span>
        Song tempo data powered by <a href="https://getsongbpm.com" target="_blank" class="hover:text-gray-400">GetSongBPM.com</a>
    </p>
</footer>
```

**Step 4: Update landing.html**

In `templates/core/landing.html`, find the hero section and update:

1. Replace hero subtitle text to mention beta
2. Replace "Start Free Trial" button text with "Request Beta Access"
3. Remove any "Start Free Trial" text elsewhere

Search for `Start Free Trial` in the template and replace all instances with `Request Beta Access`.

**Step 5: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaLandingPage -v`
Expected: 3 passed

**Step 6: Commit**

```bash
git add templates/core/landing.html templates/core/onboarding/base_public.html
git commit -m "feat: update landing page and public pages for beta branding"
```

---

### Task 4: Update Pricing Page for Beta

**Files:**
- Modify: `templates/core/onboarding/pricing.html` (find via grep for "pricing")

**Step 1: Write the failing test**

Add to `tests/test_beta_request.py`:

```python
@pytest.mark.django_db
class TestBetaPricingPage:
    """Test pricing page reflects beta status."""

    def test_pricing_page_shows_beta_note(self, subscription_plan):
        """Pricing page shows 'free during beta' messaging."""
        client = Client()
        response = client.get('/pricing/')
        assert response.status_code == 200
        assert b'free during beta' in response.content.lower()
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaPricingPage -v`
Expected: FAIL

**Step 3: Update the pricing template**

Find the pricing template (likely `templates/core/onboarding/pricing.html` or within `landing.html`). Add a banner at the top of the pricing section:

```html
<div class="bg-ch-gold/10 border border-ch-gold/30 rounded-lg p-4 mb-8 text-center">
    <p class="text-ch-gold font-semibold">Free During Beta</p>
    <p class="text-gray-400 text-sm">All features are free during our closed beta. These will be the prices when we launch publicly.</p>
</div>
```

Replace any "Subscribe" or "Get Started" buttons on pricing cards with "Free During Beta" text or a link to `/signup/`.

**Step 4: Run test to verify it passes**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaPricingPage -v`
Expected: PASS

**Step 5: Commit**

```bash
git add templates/core/onboarding/pricing.html
git commit -m "feat: update pricing page with beta messaging"
```

---

### Task 5: Security Hardening — Settings & Headers

**Files:**
- Modify: `config/settings.py` (lines 216-225, production security block)
- Modify: `core/middleware.py` (add SecurityHeadersMiddleware)
- Modify: `requirements.txt` (add django-axes)

**Step 1: Write the failing test**

Add to `tests/test_beta_request.py`:

```python
from django.test import override_settings


class TestSecurityHeaders:
    """Test that security headers are properly configured."""

    @override_settings(
        SECURE_HSTS_SECONDS=31536000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
        SESSION_COOKIE_AGE=86400,
        SECURE_REFERRER_POLICY='strict-origin-when-cross-origin',
    )
    def test_hsts_settings_configured(self, settings):
        """HSTS settings are present in production config."""
        assert settings.SECURE_HSTS_SECONDS == 31536000
        assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
        assert settings.SECURE_HSTS_PRELOAD is True

    def test_session_timeout_configured(self, settings):
        """Session cookie age is set."""
        assert hasattr(settings, 'SESSION_COOKIE_AGE')
        assert settings.SESSION_COOKIE_AGE == 86400
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestSecurityHeaders -v`
Expected: FAIL — settings not yet configured

**Step 3: Update settings.py**

In `config/settings.py`, replace the production security block (lines 216-225) with:

```python
# Security settings (for production)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_REDIRECT_EXEMPT = [r'^health/$']
    # HSTS - enforce HTTPS for 1 year
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    # Referrer policy
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# Session timeout (applies in all environments)
SESSION_COOKIE_AGE = 86400  # 24 hours
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
```

**Step 4: Add SecurityHeadersMiddleware**

In `core/middleware.py`, add after the `TenantMiddleware` class:

```python
class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Adds security headers not covered by Django's SecurityMiddleware.

    - Content-Security-Policy
    - Permissions-Policy
    """

    def process_response(self, request, response):
        # Content Security Policy
        csp = "; ".join([
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data: https:",
            "font-src 'self' https://fonts.gstatic.com",
            "connect-src 'self'",
            "frame-ancestors 'none'",
        ])
        response['Content-Security-Policy'] = csp

        # Permissions Policy
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'

        return response
```

Register in `config/settings.py` MIDDLEWARE list (add after `XFrameOptionsMiddleware`):

```python
'core.middleware.SecurityHeadersMiddleware',
```

**Step 5: Add django-axes to requirements.txt**

Append to `requirements.txt`:

```
# Login rate limiting
django-axes>=7.0.0
```

Add to `INSTALLED_APPS` in `config/settings.py`:

```python
'axes',
```

Add to `MIDDLEWARE` (must be after `AuthenticationMiddleware`):

```python
'axes.middleware.AxesMiddleware',
```

Add axes config to `config/settings.py` (after the email config section):

```python
# =============================================================================
# Login Rate Limiting (django-axes)
# =============================================================================
AXES_FAILURE_LIMIT = 5  # Lock after 5 failed attempts
AXES_COOLOFF_TIME = 0.5  # 30 minutes (in hours)
AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True
AXES_RESET_ON_SUCCESS = True
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]
```

**Step 6: Install django-axes and run migration**

Run: `cd /Users/ryanpate/chagent && pip install django-axes>=7.0.0`
Run: `cd /Users/ryanpate/chagent && python manage.py migrate`

**Step 7: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestSecurityHeaders -v`
Expected: PASS

Run full suite: `cd /Users/ryanpate/chagent && python -m pytest tests/ -v`
Expected: All existing tests still pass

**Step 8: Commit**

```bash
git add config/settings.py core/middleware.py requirements.txt
git commit -m "feat: add security hardening - HSTS, CSP, rate limiting, session timeout"
```

---

### Task 6: Create Security Page

**Files:**
- Create: `templates/core/security.html`
- Modify: `core/views.py` (add `security_page` view)
- Modify: `core/urls.py` (add `/security/` route)
- Modify: `core/middleware.py` (add `/security/` to PUBLIC_URLS)
- Modify: `core/sitemaps.py` (add security page)

**Step 1: Write the failing test**

Add to `tests/test_beta_request.py`:

```python
@pytest.mark.django_db
class TestSecurityPage:
    """Test the public security page."""

    def test_security_page_accessible(self):
        """GET /security/ returns 200 without authentication."""
        client = Client()
        response = client.get('/security/')
        assert response.status_code == 200

    def test_security_page_has_data_protection(self):
        """Security page mentions data protection."""
        client = Client()
        response = client.get('/security/')
        content = response.content.decode()
        assert 'Data Protection' in content or 'data protection' in content

    def test_security_page_has_technical_details(self):
        """Security page includes technical details section."""
        client = Client()
        response = client.get('/security/')
        content = response.content.decode()
        assert 'Technical Details' in content or 'technical' in content.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestSecurityPage -v`
Expected: FAIL — 404 for /security/

**Step 3: Add the security view**

In `core/views.py`, add near the other public page views (after `home` and `pricing`, around line 100):

```python
def security_page(request):
    """Public security page describing platform security measures."""
    return render(request, 'core/security.html')
```

**Step 4: Add the URL route**

In `core/urls.py`, add after the pricing route (line ~7):

```python
path('security/', views.security_page, name='security'),
```

**Step 5: Add to PUBLIC_URLS**

In `core/middleware.py`, add `/security/` to the `PUBLIC_URLS` list (line ~29):

```python
'/security/',
```

**Step 6: Add to sitemap**

In `core/sitemaps.py`, add `'security'` to the `items()` list and add priority/changefreq entries:

In `items()` return list, add: `'security'`

In `priority()` dict, add: `'security': 0.6`

In `changefreq()` dict, add: `'security': 'monthly'`

**Step 7: Create the security template**

Create `templates/core/security.html`:

```html
{% extends "core/onboarding/base_public.html" %}

{% block title %}Security | Aria - Worship Team Management{% endblock %}
{% block meta_description %}Learn how Aria protects your church's data with encryption, access controls, multi-tenant isolation, and AI privacy safeguards.{% endblock %}
{% block og_title %}Security - Aria{% endblock %}
{% block og_description %}Learn how Aria protects your church's data with enterprise-grade security.{% endblock %}

{% block schema_markup %}
<script type="application/ld+json">
{
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    "itemListElement": [
        {"@type": "ListItem", "position": 1, "name": "Home", "item": "https://aria.church/"},
        {"@type": "ListItem", "position": 2, "name": "Security", "item": "https://aria.church/security/"}
    ]
}
</script>
{% endblock %}

{% block container_class %}max-w-4xl{% endblock %}

{% block content %}
<div class="space-y-8">
    <!-- Page Header -->
    <div class="text-center mb-12">
        <h1 class="text-3xl font-bold text-white mb-4">Security at Aria</h1>
        <p class="text-gray-400 max-w-2xl mx-auto">We take the security of your church's data seriously. Here's how we protect your team's information.</p>
    </div>

    <!-- Plain Language Section -->
    <div class="grid gap-6 md:grid-cols-2">
        <!-- Data Protection -->
        <div class="bg-ch-dark rounded-lg border border-ch-gray p-6">
            <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-ch-gold/20 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                    </svg>
                </div>
                <h2 class="text-lg font-semibold text-white">Data Protection</h2>
            </div>
            <p class="text-gray-400 text-sm">Your church's data is completely isolated from other organizations. No other church can see your volunteers, conversations, or team information. Each organization operates in its own secure space.</p>
        </div>

        <!-- Encryption -->
        <div class="bg-ch-dark rounded-lg border border-ch-gray p-6">
            <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-ch-gold/20 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"/>
                    </svg>
                </div>
                <h2 class="text-lg font-semibold text-white">Encryption</h2>
            </div>
            <p class="text-gray-400 text-sm">All data transmitted between your browser and our servers is encrypted using HTTPS/TLS. Passwords are never stored in plain text — they're hashed using industry-standard algorithms.</p>
        </div>

        <!-- Access Controls -->
        <div class="bg-ch-dark rounded-lg border border-ch-gray p-6">
            <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-ch-gold/20 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
                    </svg>
                </div>
                <h2 class="text-lg font-semibold text-white">Access Controls</h2>
            </div>
            <p class="text-gray-400 text-sm">Role-based permissions ensure the right people have the right access. Roles include Owner, Admin, Team Leader, Member, and Viewer — each with specific capabilities that you control.</p>
        </div>

        <!-- AI Privacy -->
        <div class="bg-ch-dark rounded-lg border border-ch-gray p-6">
            <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-ch-gold/20 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/>
                    </svg>
                </div>
                <h2 class="text-lg font-semibold text-white">AI Privacy</h2>
            </div>
            <p class="text-gray-400 text-sm">Conversations with Aria are scoped to your organization. We do not use your data to train AI models. Your volunteer information, interactions, and team details remain private to your church.</p>
        </div>

        <!-- Planning Center -->
        <div class="bg-ch-dark rounded-lg border border-ch-gray p-6">
            <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-ch-gold/20 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
                    </svg>
                </div>
                <h2 class="text-lg font-semibold text-white">Planning Center</h2>
            </div>
            <p class="text-gray-400 text-sm">Planning Center credentials are stored per-organization and only used to access your team's data. Each church connects their own PCO account independently.</p>
        </div>

        <!-- Payments -->
        <div class="bg-ch-dark rounded-lg border border-ch-gray p-6">
            <div class="flex items-center gap-3 mb-3">
                <div class="w-10 h-10 bg-ch-gold/20 rounded-lg flex items-center justify-center">
                    <svg class="w-5 h-5 text-ch-gold" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z"/>
                    </svg>
                </div>
                <h2 class="text-lg font-semibold text-white">Payments</h2>
            </div>
            <p class="text-gray-400 text-sm">All billing is handled by Stripe, a PCI-compliant payment processor. We never store credit card numbers on our servers. Your financial information goes directly to Stripe.</p>
        </div>
    </div>

    <!-- Technical Details (Collapsible) -->
    <div class="bg-ch-dark rounded-lg border border-ch-gray overflow-hidden">
        <button onclick="document.getElementById('tech-details').classList.toggle('hidden');this.querySelector('svg').classList.toggle('rotate-180')"
                class="w-full flex items-center justify-between p-6 text-left hover:bg-ch-gray/30 transition-colors">
            <h2 class="text-xl font-semibold text-white">Technical Details</h2>
            <svg class="w-5 h-5 text-gray-400 transition-transform" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
            </svg>
        </button>
        <div id="tech-details" class="hidden border-t border-ch-gray">
            <div class="p-6 space-y-6">
                <div>
                    <h3 class="text-sm font-semibold text-ch-gold uppercase tracking-wide mb-2">Transport Security</h3>
                    <ul class="text-gray-400 text-sm space-y-1">
                        <li>TLS 1.2+ enforced on all connections</li>
                        <li>HTTP Strict Transport Security (HSTS) with 1-year max-age</li>
                        <li>Automatic HTTP to HTTPS redirect</li>
                        <li>Secure and HttpOnly cookie flags</li>
                    </ul>
                </div>
                <div>
                    <h3 class="text-sm font-semibold text-ch-gold uppercase tracking-wide mb-2">Security Headers</h3>
                    <ul class="text-gray-400 text-sm space-y-1">
                        <li>Content-Security-Policy (CSP) restricting script and resource origins</li>
                        <li>X-Frame-Options: DENY (clickjacking protection)</li>
                        <li>X-Content-Type-Options: nosniff</li>
                        <li>Referrer-Policy: strict-origin-when-cross-origin</li>
                        <li>Permissions-Policy restricting browser APIs</li>
                    </ul>
                </div>
                <div>
                    <h3 class="text-sm font-semibold text-ch-gold uppercase tracking-wide mb-2">Authentication</h3>
                    <ul class="text-gray-400 text-sm space-y-1">
                        <li>PBKDF2 password hashing with SHA-256</li>
                        <li>CSRF protection on all forms</li>
                        <li>Login rate limiting (account lockout after failed attempts)</li>
                        <li>Password strength requirements (minimum 8 characters, common password detection)</li>
                        <li>24-hour session timeout</li>
                    </ul>
                </div>
                <div>
                    <h3 class="text-sm font-semibold text-ch-gold uppercase tracking-wide mb-2">Multi-Tenant Isolation</h3>
                    <ul class="text-gray-400 text-sm space-y-1">
                        <li>All database queries scoped to organization via middleware</li>
                        <li>Role-based access control with granular permissions</li>
                        <li>Cryptographically secure invitation tokens (32 bytes, 7-day expiration)</li>
                        <li>Unique API keys per organization</li>
                    </ul>
                </div>
                <div>
                    <h3 class="text-sm font-semibold text-ch-gold uppercase tracking-wide mb-2">Infrastructure</h3>
                    <ul class="text-gray-400 text-sm space-y-1">
                        <li>Hosted on Railway (SOC 2 compliant infrastructure)</li>
                        <li>PostgreSQL database with connection health checks</li>
                        <li>Static assets served via WhiteNoise with compression</li>
                        <li>Environment-based configuration (secrets never in code)</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>

    <!-- Responsible Disclosure -->
    <div class="bg-ch-dark rounded-lg border border-ch-gray p-6 text-center">
        <h2 class="text-lg font-semibold text-white mb-2">Responsible Disclosure</h2>
        <p class="text-gray-400 text-sm mb-4">Found a security vulnerability? We appreciate responsible disclosure.</p>
        <a href="mailto:security@aria.church" class="text-ch-gold hover:underline font-medium">security@aria.church</a>
    </div>
</div>
{% endblock %}
```

**Step 8: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestSecurityPage -v`
Expected: 3 passed

**Step 9: Commit**

```bash
git add templates/core/security.html core/views.py core/urls.py core/middleware.py core/sitemaps.py
git commit -m "feat: add public security page at /security/"
```

---

### Task 7: Beta Admin Dashboard — Manage Requests

**Files:**
- Modify: `core/admin_views.py`
- Modify: `core/urls.py` (add admin beta request routes)
- Create: `templates/core/admin/beta_requests.html`

**Step 1: Write the failing test**

Add to `tests/test_beta_request.py`:

```python
@pytest.mark.django_db
class TestBetaAdminView:
    """Test platform admin can manage beta requests."""

    def test_admin_can_view_beta_requests(self):
        """Superadmin can access beta requests list."""
        from accounts.models import User
        admin = User.objects.create_user(
            username='superadmin', email='admin@aria.church',
            password='testpass123', is_superadmin=True,
        )
        BetaRequest.objects.create(
            name='Test Church', email='test@church.org',
            church_name='Test Church', church_size='medium',
        )
        client = Client()
        client.login(username='superadmin', password='testpass123')
        response = client.get('/platform-admin/beta-requests/')
        assert response.status_code == 200
        assert b'Test Church' in response.content

    def test_admin_can_approve_request(self):
        """Superadmin can approve a beta request."""
        from accounts.models import User
        admin = User.objects.create_user(
            username='superadmin2', email='admin2@aria.church',
            password='testpass123', is_superadmin=True,
        )
        req = BetaRequest.objects.create(
            name='Approved Church', email='approved@church.org',
            church_name='Approved Church', church_size='small',
        )
        client = Client()
        client.login(username='superadmin2', password='testpass123')
        response = client.post(f'/platform-admin/beta-requests/{req.id}/approve/')
        req.refresh_from_db()
        assert req.status in ('approved', 'invited')

    def test_non_admin_cannot_access(self):
        """Non-superadmin users are rejected."""
        from accounts.models import User
        user = User.objects.create_user(
            username='regular', email='user@church.org',
            password='testpass123', is_superadmin=False,
        )
        client = Client()
        client.login(username='regular', password='testpass123')
        response = client.get('/platform-admin/beta-requests/')
        assert response.status_code in (302, 403)
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaAdminView -v`
Expected: FAIL — 404 for /platform-admin/beta-requests/

**Step 3: Add admin views**

In `core/admin_views.py`, add these views after the existing admin views. Import `BetaRequest` at the top:

```python
from .models import (
    Organization, SubscriptionPlan, OrganizationMembership,
    Volunteer, Interaction, ChatMessage, FollowUp,
    Announcement, Channel, Project, Task, BetaRequest
)
```

Then add the views:

```python
@login_required
@require_superadmin
def admin_beta_requests(request):
    """List all beta requests with filtering."""
    status_filter = request.GET.get('status', '')
    requests_qs = BetaRequest.objects.all()
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)

    context = {
        'beta_requests': requests_qs,
        'status_filter': status_filter,
        'pending_count': BetaRequest.objects.filter(status='pending').count(),
    }
    return render(request, 'core/admin/beta_requests.html', context)


@login_required
@require_superadmin
def admin_beta_approve(request, pk):
    """Approve a beta request and send invitation email."""
    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    beta_req = get_object_or_404(BetaRequest, pk=pk)

    if request.method == 'POST' and beta_req.status == 'pending':
        beta_req.status = 'approved'
        beta_req.reviewed_at = timezone.now()
        beta_req.reviewed_by = request.user
        beta_req.save()

        # Send approval email with signup instructions
        try:
            send_mail(
                subject='Your Aria Beta Access is Approved!',
                message=(
                    f"Hi {beta_req.name},\n\n"
                    f"Great news! Your beta access request for {beta_req.church_name} has been approved.\n\n"
                    f"You can now create your account and get started:\n"
                    f"{django_settings.SITE_URL}/beta/signup/?email={beta_req.email}\n\n"
                    f"During the beta period, all features are free. We'd love your feedback!\n\n"
                    f"Welcome to Aria,\n"
                    f"The Aria Team"
                ),
                from_email=django_settings.DEFAULT_FROM_EMAIL,
                recipient_list=[beta_req.email],
                fail_silently=True,
            )
            beta_req.status = 'invited'
            beta_req.save()
        except Exception:
            pass  # Email failure shouldn't block approval

        messages.success(request, f'Beta request from {beta_req.church_name} approved.')

    return redirect('admin_beta_requests')


@login_required
@require_superadmin
def admin_beta_reject(request, pk):
    """Reject a beta request."""
    beta_req = get_object_or_404(BetaRequest, pk=pk)

    if request.method == 'POST' and beta_req.status == 'pending':
        beta_req.status = 'rejected'
        beta_req.reviewed_at = timezone.now()
        beta_req.reviewed_by = request.user
        beta_req.rejection_reason = request.POST.get('reason', '')
        beta_req.save()
        messages.success(request, f'Beta request from {beta_req.church_name} rejected.')

    return redirect('admin_beta_requests')
```

**Step 4: Add URL routes**

In `core/urls.py`, add after the existing platform-admin routes (around line ~139):

```python
path('platform-admin/beta-requests/', admin_views.admin_beta_requests, name='admin_beta_requests'),
path('platform-admin/beta-requests/<int:pk>/approve/', admin_views.admin_beta_approve, name='admin_beta_approve'),
path('platform-admin/beta-requests/<int:pk>/reject/', admin_views.admin_beta_reject, name='admin_beta_reject'),
```

**Step 5: Create admin template**

Create `templates/core/admin/beta_requests.html` extending the existing admin template pattern (check `templates/core/admin/dashboard.html` for the base template structure).

The template should show:
- A table with: Name, Email, Church, Size, Status, Date, Actions
- Filter buttons for status (All, Pending, Approved, Rejected)
- Approve/Reject buttons for pending requests
- A count badge showing pending requests

**Step 6: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaAdminView -v`
Expected: 3 passed

**Step 7: Commit**

```bash
git add core/admin_views.py core/urls.py templates/core/admin/beta_requests.html tests/test_beta_request.py
git commit -m "feat: add beta request management in platform admin"
```

---

### Task 8: Beta Signup Flow (Approved Users)

**Files:**
- Modify: `core/views.py` (add `beta_signup` view)
- Modify: `core/urls.py` (add `/beta/signup/` route)
- Create: `templates/core/onboarding/beta_signup.html`

**Step 1: Write the failing test**

Add to `tests/test_beta_request.py`:

```python
@pytest.mark.django_db
class TestBetaSignupFlow:
    """Test that approved beta users can create their account."""

    def test_beta_signup_page_accessible(self, subscription_plan):
        """Approved users can access the beta signup page."""
        BetaRequest.objects.create(
            name='Approved User', email='approved@church.org',
            church_name='Approved Church', church_size='medium',
            status='invited',
        )
        client = Client()
        response = client.get('/beta/signup/?email=approved@church.org')
        assert response.status_code == 200
        assert b'Approved Church' in response.content

    def test_beta_signup_creates_org_with_beta_status(self, subscription_plan):
        """Signing up via beta creates org with beta status."""
        from core.models import Organization
        BetaRequest.objects.create(
            name='Beta User', email='beta@church.org',
            church_name='Beta Church', church_size='small',
            status='invited',
        )
        client = Client()
        response = client.post('/beta/signup/?email=beta@church.org', {
            'email': 'beta@church.org',
            'password': 'securepassword123',
            'first_name': 'Beta',
            'last_name': 'User',
        })
        org = Organization.objects.filter(name='Beta Church').first()
        assert org is not None
        assert org.subscription_status == 'beta'

    def test_uninvited_email_rejected(self):
        """Non-approved emails can't use the beta signup."""
        client = Client()
        response = client.get('/beta/signup/?email=random@church.org')
        assert response.status_code == 302  # Redirect to /signup/
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaSignupFlow -v`
Expected: FAIL — 404

**Step 3: Create beta signup view**

In `core/views.py`, add:

```python
def beta_signup(request):
    """
    Account creation for approved beta users.

    Expects ?email= query param matching an approved/invited BetaRequest.
    Creates an organization with subscription_status='beta'.
    """
    from django.contrib.auth import login
    from accounts.models import User
    from .models import Organization, OrganizationMembership, SubscriptionPlan, BetaRequest

    email = request.GET.get('email', '').strip().lower() or request.POST.get('email', '').strip().lower()

    # Verify this email has an approved/invited beta request
    beta_req = BetaRequest.objects.filter(
        email=email, status__in=('approved', 'invited')
    ).first()

    if not beta_req:
        messages.error(request, 'No approved beta request found for this email.')
        return redirect('onboarding_signup')

    if request.method == 'POST':
        password = request.POST.get('password', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        errors = []
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.objects.filter(email=email).exists():
            errors.append('An account with this email already exists.')

        if errors:
            return render(request, 'core/onboarding/beta_signup.html', {
                'errors': errors, 'beta_request': beta_req,
                'first_name': first_name, 'last_name': last_name,
            })

        # Create user
        user = User.objects.create_user(
            username=email, email=email, password=password,
            first_name=first_name, last_name=last_name,
        )

        # Get best available plan for beta (Ministry tier or highest)
        plan = SubscriptionPlan.objects.filter(
            is_active=True, tier='ministry'
        ).first() or SubscriptionPlan.objects.filter(is_active=True).order_by('-price_monthly_cents').first()

        # Create organization with beta status
        org = Organization.objects.create(
            name=beta_req.church_name,
            email=email,
            subscription_plan=plan,
            subscription_status='beta',
        )

        OrganizationMembership.objects.create(
            user=user, organization=org, role='owner',
            can_manage_users=True, can_manage_settings=True,
            can_view_analytics=True, can_manage_billing=True,
        )

        user.default_organization = org
        user.save()

        # Update beta request status
        beta_req.status = 'signed_up'
        beta_req.save()

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        request.session['onboarding_org_id'] = org.id

        # Skip plan selection and checkout — go straight to PCO connection
        return redirect('onboarding_connect_pco')

    return render(request, 'core/onboarding/beta_signup.html', {
        'beta_request': beta_req,
    })
```

**Step 4: Add URL route**

In `core/urls.py`, add:

```python
path('beta/signup/', views.beta_signup, name='beta_signup'),
```

**Step 5: Add to PUBLIC_URLS in middleware**

In `core/middleware.py`, add `'/beta/'` to `PUBLIC_URLS`.

**Step 6: Create beta signup template**

Create `templates/core/onboarding/beta_signup.html`:

```html
{% extends "core/onboarding/base_public.html" %}

{% block title %}Create Your Account{% endblock %}

{% block content %}
<div class="max-w-md mx-auto">
    <div class="bg-ch-dark rounded-lg border border-ch-gray p-8">
        <div class="flex items-center gap-2 mb-2">
            <h1 class="text-2xl font-bold text-white">Welcome to the Beta!</h1>
            <span class="bg-ch-gold/20 text-ch-gold text-xs font-semibold px-2 py-1 rounded-full">BETA</span>
        </div>
        <p class="text-gray-400 mb-6">Create your account for <strong class="text-white">{{ beta_request.church_name }}</strong>.</p>

        {% if errors %}
        <div class="bg-red-900/50 border border-red-500 rounded-lg p-4 mb-6">
            <ul class="text-red-300 text-sm">
                {% for error in errors %}
                <li>{{ error }}</li>
                {% endfor %}
            </ul>
        </div>
        {% endif %}

        <form method="post" class="space-y-4">
            {% csrf_token %}
            <input type="hidden" name="email" value="{{ beta_request.email }}">

            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">Email</label>
                <input type="email" value="{{ beta_request.email }}" disabled
                       class="w-full bg-ch-gray/50 border border-ch-gray rounded-lg px-4 py-3 text-gray-400 outline-none">
            </div>

            <div class="grid grid-cols-2 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">First Name</label>
                    <input type="text" name="first_name" value="{{ first_name|default:'' }}" placeholder="John"
                           class="w-full bg-ch-gray border border-ch-gray rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-ch-gold focus:ring-1 focus:ring-ch-gold outline-none">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">Last Name</label>
                    <input type="text" name="last_name" value="{{ last_name|default:'' }}" placeholder="Smith"
                           class="w-full bg-ch-gray border border-ch-gray rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-ch-gold focus:ring-1 focus:ring-ch-gold outline-none">
                </div>
            </div>

            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">Password</label>
                <input type="password" name="password" required minlength="8" placeholder="At least 8 characters"
                       class="w-full bg-ch-gray border border-ch-gray rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:border-ch-gold focus:ring-1 focus:ring-ch-gold outline-none">
            </div>

            <button type="submit"
                    class="w-full bg-ch-gold hover:bg-ch-gold/90 text-ch-black font-semibold py-3 px-6 rounded-lg transition-colors">
                Create Account
            </button>
        </form>
    </div>
</div>
{% endblock %}
```

**Step 7: Run tests to verify they pass**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/test_beta_request.py::TestBetaSignupFlow -v`
Expected: 3 passed

**Step 8: Run full test suite**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/ -v`
Expected: All tests pass

**Step 9: Commit**

```bash
git add core/views.py core/urls.py core/middleware.py templates/core/onboarding/beta_signup.html tests/test_beta_request.py
git commit -m "feat: add beta signup flow for approved users"
```

---

### Task 9: Final Integration — Verify Everything Works Together

**Files:**
- No new files — integration testing and final checks

**Step 1: Run the full test suite**

Run: `cd /Users/ryanpate/chagent && python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Manual verification checklist**

Run the dev server: `cd /Users/ryanpate/chagent && python manage.py runserver`

Verify:
- [ ] `http://localhost:8000/` — Landing page shows "BETA" badge, "Request Beta Access" CTA, beta banner
- [ ] `http://localhost:8000/signup/` — Shows beta request form (not account creation)
- [ ] Submit beta request form — Shows confirmation page
- [ ] `http://localhost:8000/pricing/` — Shows "Free During Beta" note
- [ ] `http://localhost:8000/security/` — Security page loads, technical details toggle works
- [ ] Admin beta request management works at `/platform-admin/beta-requests/`
- [ ] `/beta/signup/?email=approved@email` — Works for approved emails, rejects others

**Step 3: Commit any final adjustments**

```bash
git add -A
git commit -m "chore: final integration adjustments for beta and security"
```
