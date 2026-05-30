# Public Launch — Core (Pricing + De-Beta + Billing + Feature Gating) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open ARIA to public self-serve signup with a card-required 14-day trial, reconcile pricing to a single source of truth ($9.99/$39.99/$79.99), grandfather existing beta orgs, and gate premium features by plan.

**Architecture:** Reuse the existing onboarding wizard (`onboarding_signup → select_plan → checkout → connect_pco → invite_team → complete`). The signup view changes from creating a `BetaRequest` to creating a real `User` + `Organization` (trial). A new `require_plan_feature` decorator (mirroring the existing `require_role`/`require_permission` decorators in `core/middleware.py`) enforces premium features. A data migration corrects seeded plan prices. Beta orgs are grandfathered by teaching two `Organization` properties to treat `'beta'` as active.

**Tech Stack:** Django 5, pytest + pytest-django, Stripe Checkout (subscription mode, `trial_period_days`), Tailwind templates.

**Scope note:** This is plan 1 of 3 for the public launch. Plan 2 = conversion-funnel/first-run UI fixes (workstream E). Plan 3 = SEO fixes (workstream D). Soft usage caps (volunteers, AI queries) are explicitly deferred per the spec.

**Spec:** `docs/superpowers/specs/2026-05-30-public-launch-design.md`

**Test command:** `python manage.py test tests -v 2` (or `pytest` if configured). Confirm whichever the repo uses before starting; existing suite = 452 tests, must stay green.

---

## Workstream B — Pricing Single Source of Truth

### Task 1: Correct seeded subscription-plan prices

**Files:**
- Create: `core/migrations/0050_update_plan_prices_public_launch.py` (latest is `0049_notificationpreference_studio_builds_and_more`; depend on it)
- Test: `tests/test_pricing_launch.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pricing_launch.py
import pytest
from core.models import SubscriptionPlan


@pytest.mark.django_db
def test_launch_plan_prices_are_canonical():
    """Seeded plans must match the locked public-launch pricing."""
    expected = {
        'starter': (999, 10000),    # $9.99/mo, $100/yr
        'team': (3999, 40000),      # $39.99/mo, $400/yr
        'ministry': (7999, 80000),  # $79.99/mo, $800/yr
    }
    for slug, (monthly, yearly) in expected.items():
        plan = SubscriptionPlan.objects.get(slug=slug)
        assert plan.price_monthly_cents == monthly, f"{slug} monthly"
        assert plan.price_yearly_cents == yearly, f"{slug} yearly"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test tests.test_pricing_launch.test_launch_plan_prices_are_canonical -v 2`
Expected: FAIL — starter is 2900/29000 (old seed), not 999/10000.

- [ ] **Step 3: Write the data migration**

```python
# core/migrations/0035_update_plan_prices_public_launch.py
from django.db import migrations

NEW_PRICES = {
    'starter':  {'price_monthly_cents': 999,  'price_yearly_cents': 10000},
    'team':     {'price_monthly_cents': 3999, 'price_yearly_cents': 40000},
    'ministry': {'price_monthly_cents': 7999, 'price_yearly_cents': 80000},
}
OLD_PRICES = {
    'starter':  {'price_monthly_cents': 2900,  'price_yearly_cents': 29000},
    'team':     {'price_monthly_cents': 7900,  'price_yearly_cents': 79000},
    'ministry': {'price_monthly_cents': 14900, 'price_yearly_cents': 149000},
}


def apply_prices(prices):
    def _run(apps, schema_editor):
        SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')
        for slug, fields in prices.items():
            SubscriptionPlan.objects.filter(slug=slug).update(**fields)
    return _run


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0049_notificationpreference_studio_builds_and_more'),
    ]
    operations = [
        migrations.RunPython(apply_prices(NEW_PRICES), apply_prices(OLD_PRICES)),
    ]
```

- [ ] **Step 4: Run the migration and the test**

Run: `python manage.py migrate core && python manage.py test tests.test_pricing_launch.test_launch_plan_prices_are_canonical -v 2`
Expected: migration applies; test PASSES.

- [ ] **Step 5: Commit**

```bash
git add core/migrations/0035_update_plan_prices_public_launch.py tests/test_pricing_launch.py
git commit -m "feat: reconcile subscription plan prices to public-launch values"
```

---

### Task 2: Fix annual price display + verify pricing-page schema

**Files:**
- Modify: `templates/core/pricing.html` (yearly price block, ~lines 188-194; JSON-LD ~lines 13-135)
- Test: `tests/test_pricing_launch.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pricing_launch.py
@pytest.mark.django_db
def test_pricing_page_shows_canonical_prices(client):
    resp = client.get('/pricing/')
    assert resp.status_code == 200
    body = resp.content.decode()
    assert '9.99' in body
    assert '39.99' in body
    assert '79.99' in body
    # No stale prices from the old seed
    assert '$149' not in body and '149.00' not in body
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `python manage.py test tests.test_pricing_launch.test_pricing_page_shows_canonical_prices -v 2`
Expected: PASS once Task 1 migration is applied (prices come from DB). If it FAILS because the page hardcodes old prices or JSON-LD shows wrong numbers, fix those literals in `pricing.html` so all displayed/structured prices read 9.99/39.99/79.99.

- [ ] **Step 3: Improve the yearly display**

In `templates/core/pricing.html`, the yearly block currently shows the raw yearly price. Replace it so the monthly-equivalent and savings are legible. Example (adapt to surrounding markup/variables `plan.yearly_price`, `plan.yearly_savings`):

```html
<div x-show="billing === 'yearly'" class="text-sm text-gray-400 mt-1">
  ~${{ plan.yearly_price|floatformat:0|add:"0"|stringformat:"s" }} /yr
  <span class="text-ch-gold">
    (${{ plan.yearly_savings|floatformat:2 }} off)
  </span>
</div>
```

Keep it simple — the key requirement is the page shows the yearly price AND the savings. Do not invent new template variables; `yearly_price` and `yearly_savings` already exist on the model.

- [ ] **Step 4: Run the test**

Run: `python manage.py test tests.test_pricing_launch.test_pricing_page_shows_canonical_prices -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/core/pricing.html tests/test_pricing_launch.py
git commit -m "feat: show legible annual pricing and verify canonical prices on pricing page"
```

---

### Task 3: Sync CLAUDE.md pricing table

**Files:**
- Modify: `CLAUDE.md` (subscription plans table)

- [ ] **Step 1: Update the table**

The CLAUDE.md table already reads $9.99/$39.99/$79.99 (it matches the launch values) but yearly says $100/$400/$800 — confirm it matches the migration. Verify and correct any mismatch so docs == migration == pricing page. No test (docs only).

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: align CLAUDE.md pricing table with launch prices"
```

---

## Workstream A — De-Beta, Open Signup, Grandfather Beta Orgs

### Task 4: Grandfather beta orgs (fix active-status properties)

**Files:**
- Modify: `core/models.py:276-292` (`needs_subscription`, `is_subscription_active`)
- Test: `tests/test_pricing_launch.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pricing_launch.py
@pytest.mark.django_db
def test_beta_org_is_active_and_not_blocked():
    from core.models import Organization
    org = Organization.objects.create(
        name='Beta Grandfathered', email='b@x.org',
        subscription_status='beta',
    )
    assert org.is_subscription_active is True
    assert org.needs_subscription is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test tests.test_pricing_launch.test_beta_org_is_active_and_not_blocked -v 2`
Expected: FAIL — `is_subscription_active` returns False for `'beta'`.

- [ ] **Step 3: Update the two properties**

In `core/models.py`, replace the bodies:

```python
    @property
    def needs_subscription(self):
        """Check if org needs to subscribe to continue using the service."""
        # Beta orgs are grandfathered with permanent free access.
        if self.subscription_status == 'beta':
            return False
        # Trial expired
        if self.is_trial_expired:
            return True
        # Subscription cancelled or suspended
        if self.subscription_status in ['cancelled', 'suspended']:
            return True
        return False

    @property
    def is_subscription_active(self):
        """Check if organization has an active subscription."""
        if self.subscription_status == 'beta':
            return True  # Grandfathered beta orgs always active
        if self.subscription_status == 'trial':
            return self.is_trial  # Only active if trial hasn't expired
        return self.subscription_status == 'active'
```

- [ ] **Step 4: Run the test**

Run: `python manage.py test tests.test_pricing_launch.test_beta_org_is_active_and_not_blocked -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_pricing_launch.py
git commit -m "fix: treat beta subscription_status as active (grandfather beta orgs)"
```

---

### Task 5: Convert `/signup/` to open self-serve signup

**Files:**
- Modify: `core/views.py:5391-5443` (`onboarding_signup`)
- Test: `tests/test_open_signup.py` (create)

This replaces BetaRequest creation with real User + Organization (trial) creation, logs the user in, seeds onboarding session, and redirects into the plan-selection step.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_open_signup.py
import pytest
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership


@pytest.mark.django_db
def test_open_signup_creates_trial_org_and_redirects_to_plan(client, subscription_plan):
    resp = client.post(reverse('onboarding_signup'), {
        'first_name': 'Pat', 'last_name': 'Lee',
        'email': 'pat@newchurch.org', 'password': 'supersecret1',
        'church_name': 'New Life Church',
    })
    assert resp.status_code == 302
    assert resp.url == reverse('onboarding_select_plan')

    user = User.objects.get(email='pat@newchurch.org')
    org = Organization.objects.get(name='New Life Church')
    assert org.subscription_status == 'trial'
    assert org.trial_ends_at is not None
    assert OrganizationMembership.objects.filter(
        user=user, organization=org, role='owner').exists()


@pytest.mark.django_db
def test_open_signup_rejects_duplicate_email(client, subscription_plan):
    User.objects.create_user(username='dupe@x.org', email='dupe@x.org', password='x')
    resp = client.post(reverse('onboarding_signup'), {
        'first_name': 'D', 'last_name': 'U', 'email': 'dupe@x.org',
        'password': 'supersecret1', 'church_name': 'Dup Church',
    })
    assert resp.status_code == 200  # re-render with error
    assert b'already' in resp.content.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test tests.test_open_signup -v 2`
Expected: FAIL — current view creates a BetaRequest and renders confirmation, never redirects to `onboarding_select_plan`.

- [ ] **Step 3: Rewrite `onboarding_signup`**

Replace the body of `onboarding_signup` in `core/views.py` with:

```python
def onboarding_signup(request):
    """
    Open self-serve signup. Creates a real User + Organization (trial)
    and starts the onboarding wizard at plan selection.
    """
    from datetime import timedelta
    from django.contrib.auth import login
    from accounts.models import User
    from .models import Organization, OrganizationMembership

    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        church_name = request.POST.get('church_name', '').strip()

        errors = []
        if not first_name:
            errors.append('Your first name is required.')
        if not email:
            errors.append('Email address is required.')
        if not password or len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if not church_name:
            errors.append('Church name is required.')
        if email and User.objects.filter(email=email).exists():
            errors.append('An account with this email already exists.')

        if errors:
            return render(request, 'core/onboarding/signup.html', {
                'errors': errors,
                'first_name': first_name, 'last_name': last_name,
                'email': email, 'church_name': church_name,
            })

        user = User.objects.create_user(
            username=email, email=email, password=password,
            first_name=first_name, last_name=last_name,
        )

        trial_days = getattr(settings, 'TRIAL_PERIOD_DAYS', 14)
        org = Organization.objects.create(
            name=church_name,
            email=email,
            subscription_status='trial',
            trial_ends_at=timezone.now() + timedelta(days=trial_days),
        )

        OrganizationMembership.objects.create(
            user=user, organization=org, role='owner',
            can_manage_users=True, can_manage_settings=True,
            can_view_analytics=True, can_manage_billing=True,
        )
        user.default_organization = org
        user.save()

        try:
            from .guide_seeder import seed_guide_document
            seed_guide_document(org)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Failed to seed guide for {org.name}: {e}")

        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        request.session['onboarding_org_id'] = org.id
        return redirect('onboarding_select_plan')

    return render(request, 'core/onboarding/signup.html', {})
```

- [ ] **Step 4: Run the tests**

Run: `python manage.py test tests.test_open_signup -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_open_signup.py
git commit -m "feat: open self-serve signup creates trial org and enters onboarding"
```

---

### Task 6: Update the signup template for open signup

**Files:**
- Modify: `templates/core/onboarding/signup.html`
- Test: `tests/test_open_signup.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_open_signup.py
@pytest.mark.django_db
def test_signup_page_is_open_not_beta(client):
    resp = client.get(reverse('onboarding_signup'))
    body = resp.content.decode()
    assert resp.status_code == 200
    assert 'name="password"' in body
    assert 'Request Beta Access' not in body
    assert 'BETA' not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test tests.test_open_signup.test_signup_page_is_open_not_beta -v 2`
Expected: FAIL — template has BETA badge (~line 12), no password field, beta feature list (~lines 79-105).

- [ ] **Step 3: Edit the template**

In `templates/core/onboarding/signup.html`:
- Remove the BETA badge (~line 12) and the "Request Beta Access" heading → use "Start your free trial".
- Replace the church-size dropdown block with form fields: `first_name`, `last_name`, `email`, `password` (type=password), `church_name`. Keep existing Tailwind input classes from the surrounding markup.
- Remove the beta feature list (~lines 77-106).
- Add a trust line under the submit button: `Cancel anytime. Your card isn't charged until your 14-day trial ends.`
- Add security/privacy trust links above the form:

```html
<p class="text-xs text-gray-400 text-center mb-6">
  <a href="{% url 'security' %}" class="hover:text-gray-300">Your data is secure</a> ·
  <a href="{% url 'privacy' %}" class="hover:text-gray-300">Privacy policy</a>
</p>
```

Render `{{ errors }}` the same way the current template does (it already loops errors).

- [ ] **Step 4: Run the test**

Run: `python manage.py test tests.test_open_signup.test_signup_page_is_open_not_beta -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/core/onboarding/signup.html tests/test_open_signup.py
git commit -m "feat: open signup form with password and trust signals, no beta branding"
```

---

### Task 7: Require Stripe checkout for new orgs (close the free-access fallback)

**Files:**
- Modify: `core/views.py:5615-5617` (`onboarding_checkout` fallback)
- Test: `tests/test_open_signup.py`

The current fallback silently grants free access when no Stripe price is configured. For card-required launch, surface an error instead.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_open_signup.py
@pytest.mark.django_db
def test_checkout_without_stripe_config_does_not_grant_free_access(client, settings, subscription_plan):
    # No Stripe keys configured
    settings.STRIPE_SECRET_KEY = ''
    user = User.objects.create_user(username='c@x.org', email='c@x.org', password='supersecret1')
    from core.models import Organization, OrganizationMembership
    org = Organization.objects.create(name='Checkout Church', email='c@x.org',
                                      subscription_status='trial', subscription_plan=subscription_plan)
    OrganizationMembership.objects.create(user=user, organization=org, role='owner',
                                          can_manage_billing=True)
    user.default_organization = org; user.save()
    client.force_login(user)
    session = client.session
    session['onboarding_org_id'] = org.id
    session['selected_plan_id'] = subscription_plan.id
    session['billing_cycle'] = 'monthly'
    session.save()

    resp = client.get(reverse('onboarding_checkout'))
    # Must NOT silently redirect into the app as if paid; should render an error page.
    assert resp.status_code == 200
    assert b'unavailable' in resp.content.lower() or b'error' in resp.content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test tests.test_open_signup.test_checkout_without_stripe_config_does_not_grant_free_access -v 2`
Expected: FAIL — current code redirects to `onboarding_connect_pco` (302).

- [ ] **Step 3: Replace the fallback**

In `core/views.py`, change the block at ~5615-5617 from the silent redirect to:

```python
    if not price_id or not stripe.api_key:
        # Card is required for launch — never grant free access on misconfiguration.
        return render(request, 'core/onboarding/checkout_error.html', {
            'error': 'Billing is temporarily unavailable. Please try again shortly '
                     'or contact support@aria.church.',
            'organization': org,
        })
```

(`checkout_error.html` already exists — it's used by the StripeError branches below.)

- [ ] **Step 4: Run the test**

Run: `python manage.py test tests.test_open_signup.test_checkout_without_stripe_config_does_not_grant_free_access -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_open_signup.py
git commit -m "fix: do not grant free access when Stripe is unconfigured at checkout"
```

---

### Task 8: Strip beta branding from public templates

**Files:**
- Modify: `templates/core/landing.html` (~95, 102, 345), `templates/core/pricing.html` (~142-146, 152, 462-464), `templates/core/onboarding/base_public.html` (~72-79, 86), `templates/accounts/login.html` (~56)
- Test: `tests/test_open_signup.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_open_signup.py
@pytest.mark.django_db
def test_public_pages_have_no_beta_branding(client):
    for path in ['/', '/pricing/']:
        body = client.get(path).content.decode()
        assert 'Request Beta Access' not in body, path
        assert 'closed beta' not in body.lower(), path
        assert 'Free During Beta' not in body, path
        assert 'Start your 14-day free trial' in body or 'Start Free Trial' in body, path
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test tests.test_open_signup.test_public_pages_have_no_beta_branding -v 2`
Expected: FAIL — landing/pricing still carry beta copy.

- [ ] **Step 3: Edit the templates**

For each file, make these replacements (preserve surrounding markup/classes):
- `landing.html`: line ~95 subtitle "Currently in closed beta — request early access" → "AI for your worship team — start a free 14-day trial." Buttons "Request Beta Access" (lines ~102, ~345) → "Start Free Trial" linking to `{% url 'onboarding_signup' %}`.
- `pricing.html`: delete the "Free During Beta" banner (~142-146); remove "all features free during beta" copy (~152); bottom CTA (~462) "Request Beta Access" → "Start Free Trial"; replace "Free during beta. No credit card required." (~464) with "14-day free trial. Cancel anytime."
- `base_public.html`: delete the dismissible closed-beta banner (~72-79); remove the `BETA` badge (~86); add a "Start Free Trial" button next to the existing "Sign In" link in the nav.
- `login.html`: line ~56 "Request Beta Access" → "Start your free trial" linking to `{% url 'onboarding_signup' %}`.

- [ ] **Step 4: Run the test + full suite**

Run: `python manage.py test tests.test_open_signup -v 2 && python manage.py test tests -v 1`
Expected: new tests PASS; full suite green (fix any beta-flow tests that now assert old behavior — update them to the open-signup expectations).

- [ ] **Step 5: Commit**

```bash
git add templates/ tests/test_open_signup.py
git commit -m "feat: remove beta branding from public pages, use free-trial CTAs"
```

---

## Workstream C — Premium Feature Gating

### Task 9: Add the `require_plan_feature` decorator

**Files:**
- Modify: `core/middleware.py` (add after `require_role`, ~line 348)
- Test: `tests/test_feature_gating.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_feature_gating.py
import pytest
from django.test import RequestFactory
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from core.middleware import require_plan_feature
from core.models import Organization, SubscriptionPlan


def _req(rf, org):
    request = rf.get('/analytics/')
    # attach session + messages so redirect+message works
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    MessageMiddleware(lambda r: None).process_request(request)
    request.organization = org
    return request


@pytest.mark.django_db
def test_require_plan_feature_blocks_when_missing(request_factory):
    plan = SubscriptionPlan.objects.create(slug='gate-starter', name='S', tier='starter',
                                            has_analytics=False)
    org = Organization.objects.create(name='Gate Starter', email='g@x.org',
                                      subscription_plan=plan, subscription_status='active')

    @require_plan_feature('analytics')
    def view(request):
        from django.http import HttpResponse
        return HttpResponse('ok')

    resp = view(_req(request_factory, org))
    assert resp.status_code == 302  # redirected to upgrade


@pytest.mark.django_db
def test_require_plan_feature_allows_when_present(request_factory):
    plan = SubscriptionPlan.objects.create(slug='gate-team', name='T', tier='team',
                                            has_analytics=True)
    org = Organization.objects.create(name='Gate Team', email='t@x.org',
                                      subscription_plan=plan, subscription_status='active')

    @require_plan_feature('analytics')
    def view(request):
        from django.http import HttpResponse
        return HttpResponse('ok')

    resp = view(_req(request_factory, org))
    assert resp.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test tests.test_feature_gating -v 2`
Expected: FAIL — `cannot import name 'require_plan_feature'`.

- [ ] **Step 3: Add the decorator**

In `core/middleware.py`, after `require_role` (~line 348), add:

```python
def require_plan_feature(feature_name):
    """
    Decorator to require the organization's plan to include a feature.

    Grandfathered beta orgs map to a Ministry-equivalent plan and pass.

    Usage:
        @login_required
        @require_plan_feature('analytics')
        def analytics_dashboard(request):
            ...
    """
    from functools import wraps
    from django.contrib import messages
    from django.shortcuts import redirect

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            org = getattr(request, 'organization', None)
            if org is None or not org.has_feature(feature_name):
                messages.info(
                    request,
                    f"That feature isn't included in your current plan. "
                    f"Upgrade to unlock it."
                )
                return redirect('org_settings_billing')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
```

Confirm the billing URL name with `grep -n "name='org_settings_billing'\|name=\"org_settings_billing\"" core/urls.py`. If the name differs (e.g. `billing`), use the actual name in the `redirect(...)` call.

- [ ] **Step 4: Run the tests**

Run: `python manage.py test tests.test_feature_gating -v 2`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/middleware.py tests/test_feature_gating.py
git commit -m "feat: add require_plan_feature decorator for tier enforcement"
```

---

### Task 10: Gate analytics and care views by plan

**Files:**
- Modify: `core/views.py` — analytics views (`analytics_dashboard` 1420, `analytics_volunteer_engagement` 1467, `analytics_team_care` 1498, `analytics_interaction_trends` 1529, `analytics_prayer_requests` 1562, `analytics_ai_performance` 1593, `analytics_export` 1624, `analytics_refresh_cache` 1661) and care views (`care_dashboard` 1684, `care_dismiss_insight` 1756, `care_create_followup` 1793, `care_refresh_insights` 1836)
- Modify: import `require_plan_feature` at the top of `core/views.py` (where other middleware decorators are imported — `grep -n "from .middleware import" core/views.py`)
- Test: `tests/test_feature_gating.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_feature_gating.py
from django.urls import reverse
from core.models import OrganizationMembership
from accounts.models import User


def _member(org):
    u = User.objects.create_user(username=f'm{org.id}@x.org', email=f'm{org.id}@x.org',
                                 password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner',
                                          can_view_analytics=True)
    u.default_organization = org; u.save()
    return u


@pytest.mark.django_db
def test_starter_org_blocked_from_analytics(client):
    plan = SubscriptionPlan.objects.create(slug='s2', name='S', tier='starter', has_analytics=False)
    org = Organization.objects.create(name='S2', email='s2@x.org', slug='s2-church',
                                      subscription_plan=plan, subscription_status='active')
    client.force_login(_member(org))
    resp = client.get(reverse('analytics_dashboard'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_ministry_org_allowed_into_analytics(client):
    plan = SubscriptionPlan.objects.create(slug='m2', name='M', tier='ministry', has_analytics=True)
    org = Organization.objects.create(name='M2', email='m2@x.org', slug='m2-church',
                                      subscription_plan=plan, subscription_status='active')
    client.force_login(_member(org))
    resp = client.get(reverse('analytics_dashboard'))
    assert resp.status_code == 200
```

> Note: these tests assume `TenantMiddleware` resolves `request.organization` from the user's default org. Confirm with an existing analytics test in the suite; if those tests set up org context differently, mirror their setup here.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test tests.test_feature_gating -v 2`
Expected: starter-blocked test FAILS (returns 200 today — no gating).

- [ ] **Step 3: Apply the decorator**

At the top of `core/views.py`, add `require_plan_feature` to the existing middleware import. Then add the decorator under `@login_required` on each view:

```python
@login_required
@require_plan_feature('analytics')
def analytics_dashboard(request):
    ...
```

Apply `@require_plan_feature('analytics')` to all 8 analytics views and `@require_plan_feature('care_insights')` to all 4 care views, each placed directly below `@login_required`.

- [ ] **Step 4: Run the tests + full suite**

Run: `python manage.py test tests.test_feature_gating -v 2 && python manage.py test tests -v 1`
Expected: gating tests PASS. Full suite green — note existing analytics/care tests may now need their fixture orgs to have `has_analytics=True`/`has_care_insights=True` (the `subscription_plan` conftest fixture already sets both True, so `org_alpha`/`org_beta` pass; fix any test that uses a starter-tier org).

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_feature_gating.py
git commit -m "feat: gate analytics and care views by plan feature flags"
```

---

### Task 11: Gate API access and custom branding by plan

**Files:**
- Modify: the settings view(s) that enable the API and that save custom branding (locate them — see Step 1)
- Test: `tests/test_feature_gating.py`

The `has_api_access` and `has_custom_branding` flags exist but aren't enforced. Gate the actions that turn on the API and that change branding (`ai_assistant_name` / `primary_color`).

- [ ] **Step 1: Locate the views**

Run:
```bash
grep -n "api_enabled\|generate_api_key\|api_key" core/views.py
grep -n "ai_assistant_name\|primary_color" core/views.py
grep -n "name='org_settings" core/urls.py
```
Identify the view that toggles `api_enabled` (API access) and the view/branch that writes `ai_assistant_name`/`primary_color` (custom branding). Record their function names and URL names.

- [ ] **Step 2: Write the failing test**

```python
# append to tests/test_feature_gating.py
@pytest.mark.django_db
def test_starter_org_cannot_enable_api(client):
    plan = SubscriptionPlan.objects.create(slug='s3', name='S', tier='starter', has_api_access=False)
    org = Organization.objects.create(name='S3', email='s3@x.org', slug='s3-church',
                                      subscription_plan=plan, subscription_status='active')
    u = User.objects.create_user(username='s3o@x.org', email='s3o@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner',
                                          can_manage_settings=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    # Use the actual API-enable URL name found in Step 1:
    resp = client.post(reverse('REPLACE_api_enable_url_name'))
    org.refresh_from_db()
    assert resp.status_code in (302, 403)
    assert org.api_enabled is False  # gate prevented enabling
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python manage.py test tests.test_feature_gating.test_starter_org_cannot_enable_api -v 2`
Expected: FAIL — API gets enabled for a starter org.

- [ ] **Step 4: Apply the decorator**

Add `@require_plan_feature('api_access')` (below `@login_required`/`@require_organization`) to the API-enable view, and `@require_plan_feature('custom_branding')` to the branding-save view. If branding is saved inside a larger general-settings view that also handles non-branding fields, do NOT decorate the whole view — instead guard the branding fields inline:

```python
if request.organization.has_feature('custom_branding'):
    org.ai_assistant_name = request.POST.get('ai_assistant_name', org.ai_assistant_name)
    org.primary_color = request.POST.get('primary_color', org.primary_color)
```

- [ ] **Step 5: Run the test + commit**

Run: `python manage.py test tests.test_feature_gating -v 2`
Expected: PASS.

```bash
git add core/views.py tests/test_feature_gating.py
git commit -m "feat: gate API access and custom branding by plan feature flags"
```

---

### Task 12: Document the deferred usage caps

**Files:**
- Modify: `CLAUDE.md` (Technical Debt → High Priority)

- [ ] **Step 1: Add the follow-up note**

Add under Technical Debt:
> **Soft usage caps not enforced (deferred from public launch):** volunteer count and monthly AI query limits are tracked but not blocked. Enforce with upgrade prompts in a fast-follow. User-count IS enforced on invite.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: log deferred usage-cap enforcement as known follow-up"
```

---

## Final Verification

- [ ] **Run the complete suite**

Run: `python manage.py test tests -v 1`
Expected: all tests pass (452 existing + new tests from this plan, minus any beta-flow tests intentionally updated).

- [ ] **Manual smoke test (DEBUG, Stripe test keys)**

1. Visit `/signup/` → fill form → confirm redirect to plan selection, trial org created.
2. Pick a plan → confirm Stripe test checkout opens (requires `STRIPE_PRICE_*` test env vars).
3. Visit `/` and `/pricing/` → confirm no beta language, prices read $9.99/$39.99/$79.99.
4. Log in as a starter-plan org → hit `/analytics/` → confirm redirect to billing with upgrade message.
5. Confirm an existing `subscription_status='beta'` org reaches the dashboard without a subscription prompt.

## User Actions (cannot be automated)

1. **Stripe:** create Prices for starter/team/ministry × monthly/yearly at the launch amounts; set
   `STRIPE_PRICE_STARTER_MONTHLY=…` (=$9.99), `_STARTER_YEARLY` (=$100), `_TEAM_MONTHLY` (=$39.99),
   `_TEAM_YEARLY` (=$400), `_MINISTRY_MONTHLY` (=$79.99), `_MINISTRY_YEARLY` (=$800) in Railway.
2. Deploy and run `python manage.py migrate` on Railway.
