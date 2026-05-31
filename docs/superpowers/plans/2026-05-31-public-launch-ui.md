# Public Launch — Plan 2: Conversion Funnel + First-Run UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the highest-impact usability blockers for new public signups — mobile-responsive pricing, real first-run guidance on an empty dashboard, a usable mobile chat, and a working password-reset flow.

**Architecture:** Pure Django-template + view-context changes (no new models). One small URL/view addition for Django's built-in password reset. Tests assert rendered markup and the reset email, using the active-org login pattern (the card-enforcement middleware from plan 1 redirects trial orgs without a Stripe subscription, so all UI tests must use an `active` org).

**Tech Stack:** Django 5 templates (Tailwind, Alpine, HTMX), `django.contrib.auth.views` for password reset, pytest.

**Spec:** `docs/superpowers/specs/2026-05-30-public-launch-design.md` (workstream E).

**Test command:** `python3 -m pytest tests/<file> -v`. Full suite must stay green (currently 791 passing).

**Shared test helper** (paste into each new test file that needs an authenticated app page):

```python
import pytest
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan

def _login_active_org(client, slug, *, pco=False, interactions=0):
    """Active org (passes card-enforcement + trial gates) for UI tests."""
    plan = SubscriptionPlan.objects.create(slug=f'plan-{slug}', name='P', tier='team',
                                            has_analytics=True, has_care_insights=True)
    org = Organization.objects.create(
        name=f'Org {slug}', email=f'{slug}@x.org', slug=f'org-{slug}',
        subscription_plan=plan, subscription_status='active', stripe_subscription_id='sub_x',
        planning_center_app_id=('app' if pco else ''),
        planning_center_secret=('sec' if pco else ''),
    )
    u = User.objects.create_user(username=f'{slug}@x.org', email=f'{slug}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner',
                                          can_view_analytics=True, can_manage_settings=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    return org, u
```

> NOTE: `Organization.has_pco_credentials()` is a **method**; in templates Django auto-calls it as `{{ organization.has_pco_credentials }}`. To avoid ambiguity, tasks below pass an explicit `pco_connected` boolean from the view.

---

### Task 1: Mobile-responsive pricing comparison table

**Files:**
- Modify: `templates/core/pricing.html:310-422` (the `overflow-x-auto` feature-comparison table)
- Test: `tests/test_pricing_ui.py` (create)

The 5-column table is unreadable on phones (mobile converts 13× better, per GSC). Keep the table for `md+` and add a stacked per-plan card view for small screens.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pricing_ui.py
import pytest

@pytest.mark.django_db
def test_pricing_has_mobile_and_desktop_comparison(client):
    body = client.get('/pricing/').content.decode()
    assert 'hidden md:block' in body          # desktop table wrapper hidden on mobile
    assert 'md:hidden' in body                # mobile card stack hidden on desktop
    assert 'data-mobile-comparison' in body   # the mobile comparison container
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pricing_ui.py::test_pricing_has_mobile_and_desktop_comparison -v`
Expected: FAIL — the table is a single `overflow-x-auto` block with no mobile variant.

- [ ] **Step 3: Implement the responsive split**

In `templates/core/pricing.html`, wrap the existing `<div class="overflow-x-auto">...<table>...</table></div>` (lines ~310-422) so the table only shows on desktop, and add a mobile card stack before/after it. Read the surrounding section first. Change the wrapper opening from:

```html
<div class="overflow-x-auto">
```
to:
```html
<div class="overflow-x-auto hidden md:block">
```

Then immediately AFTER the closing `</div>` of that table block, add a mobile-only stacked comparison driven by the same `plans` context already used by the cards above:

```html
<div class="md:hidden space-y-6" data-mobile-comparison>
    {% for plan in plans %}
    {% if plan.name != 'Enterprise' %}
    <div class="bg-ch-dark rounded-xl border border-ch-gray p-5">
        <h3 class="text-xl font-bold text-white mb-3">{{ plan.name }}</h3>
        <ul class="space-y-2 text-sm">
            <li class="flex justify-between"><span class="text-gray-400">Team members</span>
                <span class="text-white">{% if plan.max_users %}{{ plan.max_users }}{% else %}Unlimited{% endif %}</span></li>
            <li class="flex justify-between"><span class="text-gray-400">Volunteers</span>
                <span class="text-white">{% if plan.max_volunteers %}{{ plan.max_volunteers }}{% else %}Unlimited{% endif %}</span></li>
            <li class="flex justify-between"><span class="text-gray-400">AI queries / mo</span>
                <span class="text-white">{% if plan.max_ai_queries %}{{ plan.max_ai_queries }}{% else %}Unlimited{% endif %}</span></li>
            <li class="flex justify-between"><span class="text-gray-400">Analytics</span>
                <span class="text-white">{% if plan.features.analytics %}&#10003;{% else %}&mdash;{% endif %}</span></li>
            <li class="flex justify-between"><span class="text-gray-400">AI care insights</span>
                <span class="text-white">{% if plan.features.care_insights %}&#10003;{% else %}&mdash;{% endif %}</span></li>
            <li class="flex justify-between"><span class="text-gray-400">API access</span>
                <span class="text-white">{% if plan.features.api_access %}&#10003;{% else %}&mdash;{% endif %}</span></li>
            <li class="flex justify-between"><span class="text-gray-400">Custom branding</span>
                <span class="text-white">{% if plan.features.custom_branding %}&#10003;{% else %}&mdash;{% endif %}</span></li>
        </ul>
    </div>
    {% endif %}
    {% endfor %}
</div>
```

(`plan.features` and `plan.max_*` are confirmed available on the model. Match the surrounding Tailwind palette: `bg-ch-dark`, `border-ch-gray`, `text-ch-gold`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_pricing_ui.py::test_pricing_has_mobile_and_desktop_comparison -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/core/pricing.html tests/test_pricing_ui.py
git commit -m "feat: mobile-responsive pricing comparison (card stack + desktop table)"
```

---

### Task 2: Dashboard view context — `pco_connected` + `interactions_this_week`

**Files:**
- Modify: `core/views.py` dashboard view (context dict ~lines 261-272)
- Test: `tests/test_dashboard_ui.py` (create)

The template references `interactions_this_week` but the view never provides it (renders blank), and there is no PCO-connected flag for first-run logic. Add both.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dashboard_ui.py  (include the shared _login_active_org helper at top)
import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan, Interaction

def _login_active_org(client, slug, *, pco=False):
    plan = SubscriptionPlan.objects.create(slug=f'plan-{slug}', name='P', tier='team',
                                            has_analytics=True, has_care_insights=True)
    org = Organization.objects.create(
        name=f'Org {slug}', email=f'{slug}@x.org', slug=f'org-{slug}',
        subscription_plan=plan, subscription_status='active', stripe_subscription_id='sub_x',
        planning_center_app_id=('app' if pco else ''),
        planning_center_secret=('sec' if pco else ''),
    )
    u = User.objects.create_user(username=f'{slug}@x.org', email=f'{slug}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner',
                                          can_view_analytics=True, can_manage_settings=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    return org, u

@pytest.mark.django_db
def test_dashboard_context_has_pco_and_week_count(client):
    org, u = _login_active_org(client, 'ctx')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200
    assert resp.context['pco_connected'] is False
    assert resp.context['interactions_this_week'] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dashboard_ui.py::test_dashboard_context_has_pco_and_week_count -v`
Expected: FAIL — `KeyError: 'pco_connected'` (and `interactions_this_week` absent).

- [ ] **Step 3: Add the context values**

In `core/views.py`, in the dashboard view, read the existing `org` and `interaction_qs` variables (already present). Add before the `context = {...}` dict:

```python
    week_ago = timezone.now() - timedelta(days=7)
    interactions_this_week = interaction_qs.filter(created_at__gte=week_ago).count()
    pco_connected = bool(org and org.has_pco_credentials())
```

Then add these two keys into the existing `context` dict:

```python
        'interactions_this_week': interactions_this_week,
        'pco_connected': pco_connected,
```

Confirm `timedelta` and `timezone` are imported at the top of `core/views.py` (they are used elsewhere in the file — verify with `grep -n "from datetime import\|from django.utils import timezone" core/views.py`; add `timedelta` to the datetime import if missing).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_dashboard_ui.py::test_dashboard_context_has_pco_and_week_count -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_dashboard_ui.py
git commit -m "feat: dashboard context exposes pco_connected and interactions_this_week"
```

---

### Task 3: Dashboard empty state + first-run PCO banner

**Files:**
- Modify: `templates/core/dashboard.html` (empty state ~199-201; add banner near top of content; quick-action chips ~47-54)
- Test: `tests/test_dashboard_ui.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_dashboard_ui.py
@pytest.mark.django_db
def test_dashboard_empty_state_and_pco_banner(client):
    org, u = _login_active_org(client, 'empty', pco=False)  # no volunteers, no PCO
    body = client.get(reverse('dashboard')).content.decode()
    assert 'Log your first interaction' in body          # real empty-state CTA
    assert 'Connect Planning Center' in body             # first-run banner (no PCO)

@pytest.mark.django_db
def test_dashboard_no_pco_banner_when_connected(client):
    org, u = _login_active_org(client, 'haspco', pco=True)
    body = client.get(reverse('dashboard')).content.decode()
    assert 'Connect Planning Center' not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dashboard_ui.py -k "empty_state or no_pco_banner" -v`
Expected: FAIL — current empty state is bare text; no PCO banner.

- [ ] **Step 3: Implement empty state + banner**

In `templates/core/dashboard.html`:

(a) Replace the recent-interactions empty state (~199-201):
```html
{% else %}
<div class="text-center py-10">
    <p class="text-gray-400 mb-3 text-sm">No interactions logged yet.</p>
    <a href="{% url 'chat' %}?q=Log+interaction%3A+" class="text-ch-gold hover:underline font-medium text-sm">Log your first interaction &rarr;</a>
</div>
{% endif %}
```

(b) Add a first-run banner at the very top of the main content block (just inside the content container, before the "Ask Aria" card). Use `pco_connected` from Task 2:
```html
{% if not pco_connected %}
<div class="bg-ch-gold/10 border border-ch-gold/30 rounded-lg p-4 mb-6">
    <p class="text-sm text-gray-300">
        <strong class="text-ch-gold">Getting started:</strong>
        Connect Planning Center to import your team, schedules, and songs so Aria can answer questions about them.
    </p>
    <a href="{% url 'onboarding_connect_pco' %}" class="inline-block mt-2 text-ch-gold hover:underline text-sm font-medium">Connect Planning Center &rarr;</a>
</div>
{% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dashboard_ui.py -k "empty_state or no_pco_banner" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/core/dashboard.html tests/test_dashboard_ui.py
git commit -m "feat: dashboard empty-state CTA and first-run Connect PCO banner"
```

---

### Task 4: Disable data-dependent quick actions until PCO connected

**Files:**
- Modify: `templates/core/dashboard.html` (quick-action chips ~47-54), `templates/core/chat.html` (quick-action buttons ~165-202)
- Test: `tests/test_dashboard_ui.py`

PCO-dependent chips ("This Sunday's Team", "Last Setlist", "Check Blockouts") error out when PCO isn't connected. Keep "Log Interaction"/"Find Volunteer"/"Prayer Requests" (these work without PCO) but visually disable the PCO-dependent ones until connected.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_dashboard_ui.py
@pytest.mark.django_db
def test_pco_dependent_chips_disabled_without_pco(client):
    org, u = _login_active_org(client, 'chips', pco=False)
    body = client.get(reverse('dashboard')).content.decode()
    # PCO-dependent chips are rendered disabled (non-link) when PCO not connected
    assert 'data-pco-chip-disabled' in body

@pytest.mark.django_db
def test_pco_chips_enabled_with_pco(client):
    org, u = _login_active_org(client, 'chips2', pco=True)
    body = client.get(reverse('dashboard')).content.decode()
    assert 'data-pco-chip-disabled' not in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dashboard_ui.py -k "pco_dependent_chips or chips_enabled" -v`
Expected: FAIL — chips are always plain links.

- [ ] **Step 3: Implement conditional chips**

In `templates/core/dashboard.html`, wrap each PCO-dependent chip (the ones querying Planning Center — "This Sunday's Team", "Last Setlist", "Check Blockouts") so that when `not pco_connected` they render as a disabled span instead of a link. Read the chip block (~47-90) first. For each PCO-dependent chip, use this pattern (example for "This Sunday's Team"):

```html
{% if pco_connected %}
<a href="{% url 'chat' %}?q=Who+is+serving+this+Sunday%3F" class="bg-ch-gray border border-gray-700 rounded-full px-3 py-1.5 text-xs text-gray-300 hover:border-ch-gold hover:text-white transition">This Sunday's Team</a>
{% else %}
<span data-pco-chip-disabled title="Connect Planning Center to use this" class="bg-ch-gray/50 border border-gray-800 rounded-full px-3 py-1.5 text-xs text-gray-600 cursor-not-allowed">This Sunday's Team</span>
{% endif %}
```

Leave the non-PCO chips ("Log Interaction", "Find Volunteer", "Prayer Requests") as plain links unconditionally. Apply the same `{% if pco_connected %}` guard to the matching PCO-dependent buttons in `templates/core/chat.html` (~165-202).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dashboard_ui.py -k "pco_dependent_chips or chips_enabled" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/core/dashboard.html templates/core/chat.html tests/test_dashboard_ui.py
git commit -m "feat: disable PCO-dependent quick actions until Planning Center connected"
```

---

### Task 5: Responsive chat height + clearer chat input placeholder

**Files:**
- Modify: `templates/core/chat.html` (height ~29; placeholder ~148)
- Test: `tests/test_chat_ui.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_chat_ui.py  (include the _login_active_org helper)
import pytest
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan

def _login_active_org(client, slug):
    plan = SubscriptionPlan.objects.create(slug=f'plan-{slug}', name='P', tier='team',
                                            has_analytics=True, has_care_insights=True)
    org = Organization.objects.create(name=f'Org {slug}', email=f'{slug}@x.org', slug=f'org-{slug}',
                                      subscription_plan=plan, subscription_status='active', stripe_subscription_id='sub_x')
    u = User.objects.create_user(username=f'{slug}@x.org', email=f'{slug}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner')
    u.default_organization = org; u.save()
    client.force_login(u)
    return org, u

@pytest.mark.django_db
def test_chat_messages_height_is_responsive(client):
    _login_active_org(client, 'chat')
    body = client.get(reverse('chat')).content.decode()
    assert 'h-[400px]' in body and 'sm:h-[500px]' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_chat_ui.py::test_chat_messages_height_is_responsive -v`
Expected: FAIL — current class is the fixed `h-[500px]`.

- [ ] **Step 3: Implement**

In `templates/core/chat.html` line ~29, change `h-[500px]` to `h-[400px] sm:h-[500px]`. Change the input placeholder (~148) from `"Log an interaction or ask a question..."` to `"Ask Aria a question…"` (chat is for questions; logging happens via the explicit "Log Interaction" action). Leave the dashboard input placeholder as-is.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_chat_ui.py::test_chat_messages_height_is_responsive -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/core/chat.html tests/test_chat_ui.py
git commit -m "feat: responsive chat height and clearer chat placeholder"
```

---

### Task 6: Password-reset flow + "Forgot password?" link

**Files:**
- Modify: `accounts/urls.py` (add 4 reset URLs)
- Create: `templates/accounts/password_reset.html`, `password_reset_done.html`, `password_reset_confirm.html`, `password_reset_complete.html`, `password_reset_email.html`, `password_reset_subject.txt`
- Modify: `templates/accounts/login.html` (add link after password field)
- Test: `tests/test_password_reset.py` (create)

There is currently NO password-reset capability. Wire Django's built-in views (project already sends email).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_password_reset.py
import pytest
from django.urls import reverse, NoReverseMatch
from django.core import mail
from accounts.models import User

@pytest.mark.django_db
def test_password_reset_sends_email(client):
    User.objects.create_user(username='r@x.org', email='r@x.org', password='oldpass123')
    url = reverse('password_reset')
    resp = client.post(url, {'email': 'r@x.org'})
    assert resp.status_code == 302
    assert resp.url == reverse('password_reset_done')
    assert len(mail.outbox) == 1
    assert 'r@x.org' in mail.outbox[0].to

@pytest.mark.django_db
def test_login_page_has_forgot_password_link(client):
    body = client.get(reverse('login')).content.decode()
    assert reverse('password_reset') in body
    assert 'Forgot' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_password_reset.py -v`
Expected: FAIL — `NoReverseMatch: 'password_reset'`. (Also confirm the login URL name: `grep -n "name='login'\|name=\"login\"" accounts/urls.py config/urls.py`; if it's `accounts:login` or similar, adjust the test's `reverse('login')` accordingly.)

- [ ] **Step 3: Add the URLs**

In `accounts/urls.py`, add at top `from django.contrib.auth import views as auth_views` and add these patterns to `urlpatterns`:

```python
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.html',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url='/accounts/password-reset/done/'),
        name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url='/accounts/reset/done/'), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),
```

Confirm how `accounts/urls.py` is included (`grep -n "accounts" config/urls.py`) and that the prefix makes these resolve under `/accounts/`. Adjust the `success_url` literals if the prefix differs.

- [ ] **Step 4: Create the templates**

Create each file extending the public base for visual consistency. `templates/accounts/password_reset.html`:

```html
{% extends "core/onboarding/base_public.html" %}
{% block title %}Reset Password | Aria{% endblock %}
{% block content %}
<div class="max-w-md mx-auto">
  <h1 class="text-2xl font-bold text-white mb-4">Reset your password</h1>
  <p class="text-gray-400 text-sm mb-6">Enter your email and we'll send you a reset link.</p>
  <form method="post" class="space-y-4">{% csrf_token %}
    <input type="email" name="email" required placeholder="you@church.org"
           class="w-full bg-ch-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-ch-gold">
    <button type="submit" class="w-full bg-ch-gold text-black py-3 rounded-lg font-medium hover:bg-yellow-500 transition">Send reset link</button>
  </form>
</div>
{% endblock %}
```

`templates/accounts/password_reset_done.html`:
```html
{% extends "core/onboarding/base_public.html" %}
{% block title %}Check your email | Aria{% endblock %}
{% block content %}
<div class="max-w-md mx-auto text-center">
  <h1 class="text-2xl font-bold text-white mb-4">Check your email</h1>
  <p class="text-gray-400 text-sm">If an account exists for that address, we've sent a password reset link. It may take a few minutes to arrive.</p>
</div>
{% endblock %}
```

`templates/accounts/password_reset_confirm.html`:
```html
{% extends "core/onboarding/base_public.html" %}
{% block title %}Set a new password | Aria{% endblock %}
{% block content %}
<div class="max-w-md mx-auto">
  {% if validlink %}
  <h1 class="text-2xl font-bold text-white mb-4">Set a new password</h1>
  <form method="post" class="space-y-4">{% csrf_token %}
    <input type="password" name="new_password1" required placeholder="New password"
           class="w-full bg-ch-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-ch-gold">
    <input type="password" name="new_password2" required placeholder="Confirm new password"
           class="w-full bg-ch-gray border border-gray-700 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-ch-gold">
    <button type="submit" class="w-full bg-ch-gold text-black py-3 rounded-lg font-medium hover:bg-yellow-500 transition">Change password</button>
  </form>
  {% if form.errors %}<div class="mt-4 text-red-400 text-sm">{{ form.errors }}</div>{% endif %}
  {% else %}
  <p class="text-gray-400">This reset link is invalid or expired. <a href="{% url 'password_reset' %}" class="text-ch-gold hover:underline">Request a new one</a>.</p>
  {% endif %}
</div>
{% endblock %}
```

`templates/accounts/password_reset_complete.html`:
```html
{% extends "core/onboarding/base_public.html" %}
{% block title %}Password updated | Aria{% endblock %}
{% block content %}
<div class="max-w-md mx-auto text-center">
  <h1 class="text-2xl font-bold text-white mb-4">Password updated</h1>
  <p class="text-gray-400 text-sm mb-6">Your password has been changed.</p>
  <a href="{% url 'login' %}" class="text-ch-gold hover:underline font-medium">Sign in</a>
</div>
{% endblock %}
```

`templates/accounts/password_reset_email.html`:
```html
Hello,

You requested a password reset for your Aria account.

Click the link below to choose a new password:
{{ protocol }}://{{ domain }}{% url 'password_reset_confirm' uidb64=uid token=token %}

If you didn't request this, you can ignore this email.

— The Aria Team
```

`templates/accounts/password_reset_subject.txt`:
```
Reset your Aria password
```
(The subject template must be a single line.)

- [ ] **Step 5: Add the link to the login page**

In `templates/accounts/login.html`, add directly after the password field's closing `</div>` (~after line 44):
```html
<div class="text-right -mt-2">
  <a href="{% url 'password_reset' %}" class="text-ch-gold text-xs hover:underline">Forgot password?</a>
</div>
```

- [ ] **Step 6: Run tests + full suite**

Run: `python3 -m pytest tests/test_password_reset.py -v && python3 -m pytest tests/ -q 2>&1 | tail -6`
Expected: reset tests PASS (email lands in `mail.outbox` via the test locmem backend); full suite green.

- [ ] **Step 7: Commit**

```bash
git add accounts/urls.py templates/accounts/ tests/test_password_reset.py
git commit -m "feat: add password-reset flow and forgot-password link on login"
```

---

## Self-Review / Coverage

Spec workstream E launch-blocking items → tasks: mobile pricing table (Task 1); dashboard empty state + first-run PCO guidance + disabled chips (Tasks 2-4); responsive chat (Task 5); forgot-password (Task 6). Signup security/privacy trust links and "what happens after trial" FAQ were already shipped (plan 1 / already present) — no task needed. Nice-to-have polish (nav badges, chat welcome simplification) intentionally deferred.

## Final Verification

- [ ] `python3 -m pytest tests/ -q` → all pass.
- [ ] Manual: load `/pricing/` narrow viewport → card stack shows, table hidden. New active org dashboard → empty-state CTA + Connect-PCO banner + disabled PCO chips. `/accounts/password-reset/` → submitting a known email shows "check your email".
