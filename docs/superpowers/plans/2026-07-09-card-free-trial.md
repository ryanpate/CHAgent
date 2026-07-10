# Card-Free Trial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the credit-card requirement from signup: new orgs get a 14-day Team-level trial with no card; the card is collected mid-trial or at expiry via `/subscribe/`.

**Architecture:** Signup assigns the Team plan and skips the plan/checkout wizard steps (account → connect PCO → invite team). The middleware card-gate is deleted; the existing trial-expiry hard block (`needs_subscription` → `subscription_required`) is the only gate. A persistent banner drives mid-trial conversion through the existing `subscribe` view, which passes Stripe `subscription_data.trial_end` so early subscribers aren't charged before day 14.

**Tech Stack:** Django 5, pytest(-django), Stripe Checkout, Tailwind-styled Django templates.

**Spec:** `docs/superpowers/specs/2026-07-09-card-free-trial-design.md`

## Global Constraints

- Trial plan level is **Team** (`tier='team'`), falling back to the cheapest active plan if no Team plan exists.
- Stripe Checkout requires `subscription_data.trial_end` ≥ 48 hours in the future; below that, omit it (billing starts at checkout).
- Test commands: `python3 -m pytest <path> -q`. Full suite must be green before the final commit.
- All new user-facing copy: "No credit card required" phrasing; keep "cancel anytime".
- Repo convention: function-local imports inside views are normal; module-level `logger` exists in `core/views.py`.
- Commit messages end with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_013HvrcrDi5Je8kWxCi55LbL`

---

### Task 1: Signup assigns Team plan and skips plan/checkout steps

**Files:**
- Modify: `core/views.py` (`onboarding_signup` — both org-creation variants; add `_default_trial_plan` helper directly above `onboarding_signup`)
- Modify: `tests/test_launch_billing.py:24` (redirect assertion)
- Modify: `tests/test_funnel_fixes.py:68` (redirect assertion)
- Test: `tests/test_card_free_trial.py` (new)

**Interfaces:**
- Produces: `core.views._default_trial_plan() -> SubscriptionPlan | None` (used by Task 3's migration only conceptually — the migration re-implements the query on historical models; no import between them).
- Signup now redirects to `reverse('onboarding_connect_pco')` and creates orgs with `subscription_plan` set.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_card_free_trial.py`:

```python
"""Card-free trial: signup skips plan/checkout, orgs trial at Team level."""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

User = get_user_model()


@pytest.fixture
def team_plan(db):
    from core.models import SubscriptionPlan
    plan, _ = SubscriptionPlan.objects.get_or_create(
        slug='team', defaults={
            'name': 'Team', 'tier': 'team',
            'price_monthly_cents': 3999, 'price_yearly_cents': 40000,
            'max_users': 15, 'max_volunteers': 200,
            'max_ai_queries_monthly': 1000,
            'has_analytics': True, 'has_care_insights': True,
            'is_active': True,
        },
    )
    return plan


@pytest.mark.django_db
def test_signup_redirects_to_connect_pco_and_assigns_team_plan(client, team_plan):
    from core.models import Organization
    response = client.post(reverse('onboarding_signup'), {
        'first_name': 'A', 'last_name': 'B',
        'email': 'cardfree@x.org', 'password': 'supersecret1',
        'church_name': 'Cardfree Church',
    })
    assert response.status_code == 302
    assert response['Location'].endswith(reverse('onboarding_connect_pco'))
    org = Organization.objects.get(name='Cardfree Church')
    assert org.subscription_status == 'trial'
    assert org.subscription_plan_id == team_plan.id


@pytest.mark.django_db
def test_orgless_user_signup_also_gets_team_plan(client, team_plan):
    from core.models import Organization
    user = User.objects.create_user(
        username='noorg2@x.org', email='noorg2@x.org', password='supersecret1',
    )
    client.force_login(user)
    response = client.post(reverse('onboarding_signup'), {'church_name': 'Second Wind'})
    assert response.status_code == 302
    assert response['Location'].endswith(reverse('onboarding_connect_pco'))
    org = Organization.objects.get(name='Second Wind')
    assert org.subscription_plan_id == team_plan.id


@pytest.mark.django_db
def test_default_trial_plan_falls_back_to_cheapest_active(db):
    from core.models import SubscriptionPlan
    from core.views import _default_trial_plan
    SubscriptionPlan.objects.all().delete()
    cheap = SubscriptionPlan.objects.create(
        slug='starter-x', name='Starter', tier='starter',
        price_monthly_cents=999, is_active=True,
    )
    SubscriptionPlan.objects.create(
        slug='ministry-x', name='Ministry', tier='ministry',
        price_monthly_cents=7999, is_active=True,
    )
    assert _default_trial_plan().id == cheap.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_card_free_trial.py -q`
Expected: 3 failures — redirect goes to `/onboarding/select-plan/`, `subscription_plan_id` is None, `_default_trial_plan` import error.

- [ ] **Step 3: Implement**

In `core/views.py`, add directly above `onboarding_signup`:

```python
def _default_trial_plan():
    """Plan level for card-free trials (spec decision: Team).

    Falls back to the cheapest active plan so a missing Team seed can't
    create plan-less orgs (which would have unlimited AI queries).
    """
    from .models import SubscriptionPlan
    return (
        SubscriptionPlan.objects.filter(is_active=True, tier='team').first()
        or SubscriptionPlan.objects.filter(is_active=True)
        .order_by('price_monthly_cents').first()
    )
```

In the **org-only variant** (the `create_org_only and request.method == 'POST'` block), change the `Organization.objects.create(...)` call:

```python
            org = Organization.objects.create(
                name=church_name, email=request.user.email,
                subscription_status='trial',
                subscription_plan=_default_trial_plan(),
                trial_ends_at=timezone.now() + timedelta(days=trial_days),
            )
```

and its trailing redirect from `return redirect('onboarding_select_plan')` to `return redirect('onboarding_connect_pco')`.

In the **new-user variant** (inside `transaction.atomic()`), change the `Organization.objects.create(...)` call:

```python
                org = Organization.objects.create(
                    name=church_name, email=email,
                    subscription_status='trial',
                    subscription_plan=_default_trial_plan(),
                    trial_ends_at=timezone.now() + timedelta(days=trial_days),
                )
```

and its trailing redirect from `return redirect('onboarding_select_plan')` to `return redirect('onboarding_connect_pco')`. Keep the `preselected_plan_slug` session lines in both variants unchanged.

Update the two existing assertions that pinned the old redirect:
- `tests/test_launch_billing.py:24`: `assert resp.url == reverse('onboarding_select_plan')` → `assert resp.url == reverse('onboarding_connect_pco')`
- `tests/test_funnel_fixes.py:68`: `assert response['Location'].endswith(reverse('onboarding_select_plan'))` → `assert response['Location'].endswith(reverse('onboarding_connect_pco'))`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_free_trial.py tests/test_launch_billing.py tests/test_funnel_fixes.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_card_free_trial.py tests/test_launch_billing.py tests/test_funnel_fixes.py
git commit -m "feat: signup skips plan/checkout, assigns Team-level card-free trial"
```

---

### Task 2: Remove the middleware card-gate; invert enforcement tests

**Files:**
- Modify: `core/middleware.py` (`TenantMiddleware._check_subscription_status`)
- Modify: `tests/test_card_enforcement.py` (rewrite)

**Interfaces:**
- Consumes: nothing new. Produces: trial orgs without `stripe_subscription_id` can reach all app pages until `trial_ends_at`.

- [ ] **Step 1: Rewrite the enforcement tests (failing first)**

Replace the body of `tests/test_card_enforcement.py` with:

```python
import pytest
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from accounts.models import User
from core.models import Organization, OrganizationMembership, SubscriptionPlan


def _login_org(client, status, stripe_sub='', trial_delta_days=10):
    plan = SubscriptionPlan.objects.create(slug=f'p-{status}-{stripe_sub or "none"}-{trial_delta_days}',
                                           name='P', tier='team',
                                           has_analytics=True, has_care_insights=True)
    org = Organization.objects.create(
        name=f'Org {status}', email=f'{status}@x.org',
        subscription_plan=plan, subscription_status=status,
        stripe_subscription_id=stripe_sub,
        trial_ends_at=timezone.now() + timedelta(days=trial_delta_days),
    )
    u = User.objects.create_user(username=f'{status}{stripe_sub}{trial_delta_days}@x.org',
                                 email=f'{status}{stripe_sub}{trial_delta_days}@x.org',
                                 password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner', can_view_analytics=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    return org


@pytest.mark.django_db
def test_trial_without_card_allowed(client):
    """Card-free trial: no card needed while the trial is active."""
    _login_org(client, 'trial', stripe_sub='')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_expired_trial_without_card_blocked(client):
    _login_org(client, 'trial', stripe_sub='', trial_delta_days=-1)
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 302
    assert reverse('subscription_required') in resp.url


@pytest.mark.django_db
def test_trial_with_card_allowed(client):
    _login_org(client, 'trial', stripe_sub='sub_123')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_active_org_allowed(client):
    _login_org(client, 'active', stripe_sub='sub_456')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_beta_org_allowed_without_card(client):
    _login_org(client, 'beta', stripe_sub='')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_cancelled_org_blocked(client):
    _login_org(client, 'cancelled', stripe_sub='sub_x')
    resp = client.get(reverse('dashboard'))
    assert resp.status_code == 302
    assert reverse('subscription_required') in resp.url
```

- [ ] **Step 2: Run to verify the new expectations fail**

Run: `python3 -m pytest tests/test_card_enforcement.py -q`
Expected: `test_trial_without_card_allowed` FAILS (302 to select-plan, not 200). The others pass.

- [ ] **Step 3: Delete the card-gate**

In `core/middleware.py::_check_subscription_status`, delete this entire block (keep the `needs_subscription` check above it and the `past_due` check below it):

```python
        # Card-required trial: a trialing org that never completed Stripe checkout
        # (no subscription on file) must finish checkout before using the app.
        # Beta (grandfathered) and active orgs are unaffected. Onboarding/billing
        # pages are PUBLIC_URLS and never reach this check, so no redirect loop.
        if (organization.subscription_status == 'trial'
                and not organization.stripe_subscription_id):
            logger.info(
                f"Org {organization.slug} is trialing without a payment method; "
                "redirecting to complete checkout."
            )
            return redirect('onboarding_select_plan')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_enforcement.py tests/test_launch_billing.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/middleware.py tests/test_card_enforcement.py
git commit -m "feat: allow active trials without a card (card-free trial gate removal)"
```

---

### Task 3: Backfill migration — plan-less trial orgs get the Team plan

**Files:**
- Create: `core/migrations/0050_backfill_trial_plan.py`
- Test: `tests/test_card_free_trial.py` (append)

**Interfaces:**
- Consumes: migration `core.0049_notificationpreference_studio_builds_and_more` (current latest — verify with `ls core/migrations/ | tail -1` and adjust the dependency if a later one has appeared).
- Produces: no org with `subscription_status='trial'` has `subscription_plan IS NULL`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_card_free_trial.py`:

```python
@pytest.mark.django_db
def test_backfill_assigns_team_plan_to_planless_trials(team_plan):
    import importlib
    from django.apps import apps
    from core.models import Organization

    planless = Organization.objects.create(
        name='Planless Trial', email='planless@x.org',
        subscription_status='trial', subscription_plan=None,
    )
    active_untouched = Organization.objects.create(
        name='Active NoPlan', email='activenp@x.org',
        subscription_status='active', subscription_plan=None,
    )

    migration = importlib.import_module('core.migrations.0050_backfill_trial_plan')
    migration.backfill_trial_plan(apps, None)

    planless.refresh_from_db()
    active_untouched.refresh_from_db()
    assert planless.subscription_plan_id == team_plan.id
    assert active_untouched.subscription_plan_id is None
```

(Note: `importlib.import_module` is required because the module name starts with a digit.)

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_card_free_trial.py::test_backfill_assigns_team_plan_to_planless_trials -q`
Expected: FAIL — `ModuleNotFoundError: core.migrations.0050_backfill_trial_plan`.

- [ ] **Step 3: Write the migration**

Create `core/migrations/0050_backfill_trial_plan.py`:

```python
"""Card-free trial: trials are created with a plan from now on; backfill
existing plan-less trial orgs (features locked but AI uncapped — both wrong)."""
from django.db import migrations


def backfill_trial_plan(apps, schema_editor):
    Organization = apps.get_model('core', 'Organization')
    SubscriptionPlan = apps.get_model('core', 'SubscriptionPlan')
    plan = (
        SubscriptionPlan.objects.filter(is_active=True, tier='team').first()
        or SubscriptionPlan.objects.filter(is_active=True)
        .order_by('price_monthly_cents').first()
    )
    if plan:
        Organization.objects.filter(
            subscription_status='trial', subscription_plan__isnull=True,
        ).update(subscription_plan=plan)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_notificationpreference_studio_builds_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_trial_plan, migrations.RunPython.noop),
    ]
```

- [ ] **Step 4: Run tests + migration check**

Run: `python3 -m pytest tests/test_card_free_trial.py -q` — expected: all pass.
Run: `DEBUG=True ALLOWED_HOSTS=testserver python3 manage.py makemigrations --check --dry-run` — expected: no new migrations detected (exit 0 output "No changes detected").

- [ ] **Step 5: Commit**

```bash
git add core/migrations/0050_backfill_trial_plan.py tests/test_card_free_trial.py
git commit -m "feat: backfill Team plan onto plan-less trial orgs"
```

---

### Task 4: Mid-trial checkout honors the remaining trial

**Files:**
- Modify: `core/views.py::subscribe` (the `stripe.checkout.Session.create` call, around line 5400)
- Test: `tests/test_card_free_trial.py` (append)

**Interfaces:**
- Consumes: `org.trial_ends_at`, `org.subscription_status`.
- Produces: checkout sessions created by `subscribe` include `subscription_data={'metadata': {...}, 'trial_end': <int ts>}` when the org is trialing with > 48h left; `trial_end` absent otherwise.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_card_free_trial.py`:

```python
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.utils import timezone


def _billing_owner(client, team_plan, trial_delta_hours):
    from core.models import Organization, OrganizationMembership
    org = Organization.objects.create(
        name='MidTrial', email='midtrial@x.org',
        subscription_status='trial', subscription_plan=team_plan,
        stripe_customer_id='cus_midtrial',
        trial_ends_at=timezone.now() + timedelta(hours=trial_delta_hours),
    )
    user = User.objects.create_user(
        username=f'mid{trial_delta_hours}@x.org',
        email=f'mid{trial_delta_hours}@x.org', password='supersecret1',
    )
    OrganizationMembership.objects.create(
        user=user, organization=org, role='owner', can_manage_billing=True,
    )
    user.default_organization = org
    user.save()
    client.force_login(user)
    return org


@pytest.mark.django_db
def test_mid_trial_checkout_passes_trial_end(client, team_plan, settings):
    settings.STRIPE_SECRET_KEY = 'sk_test_x'
    settings.STRIPE_PRICE_TEAM_MONTHLY = 'price_team_m'
    org = _billing_owner(client, team_plan, trial_delta_hours=24 * 10)

    fake_session = MagicMock()
    fake_session.url = 'https://checkout.stripe.test/cs_1'
    with patch('stripe.checkout.Session.create', return_value=fake_session) as create:
        response = client.post(reverse('subscribe'), {
            'plan_id': team_plan.id, 'billing_period': 'monthly',
        })

    assert response.status_code == 302
    sub_data = create.call_args.kwargs['subscription_data']
    assert sub_data['trial_end'] == int(org.trial_ends_at.timestamp())


@pytest.mark.django_db
def test_trial_ending_within_48h_charges_immediately(client, team_plan, settings):
    settings.STRIPE_SECRET_KEY = 'sk_test_x'
    settings.STRIPE_PRICE_TEAM_MONTHLY = 'price_team_m'
    _billing_owner(client, team_plan, trial_delta_hours=24)

    fake_session = MagicMock()
    fake_session.url = 'https://checkout.stripe.test/cs_2'
    with patch('stripe.checkout.Session.create', return_value=fake_session) as create:
        client.post(reverse('subscribe'), {
            'plan_id': team_plan.id, 'billing_period': 'monthly',
        })

    sub_data = create.call_args.kwargs['subscription_data']
    assert 'trial_end' not in sub_data
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_card_free_trial.py -q -k "mid_trial or 48h"`
Expected: FAIL with `KeyError: 'subscription_data'` (the call doesn't pass it today).

- [ ] **Step 3: Implement**

In `core/views.py::subscribe`, replace the `session = stripe.checkout.Session.create(...)` call:

```python
            # Honor the remainder of a card-free trial: card saved now, first
            # charge at trial end. Stripe Checkout requires trial_end to be at
            # least 48h in the future; inside that window billing starts now.
            subscription_data = {
                'metadata': {'organization_id': str(org.id)},
            }
            if (org.subscription_status == 'trial' and org.trial_ends_at
                    and org.trial_ends_at > timezone.now() + timedelta(hours=48)):
                subscription_data['trial_end'] = int(org.trial_ends_at.timestamp())

            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=org.stripe_customer_id,
                mode='subscription',
                line_items=[{
                    'price': stripe_price_id,
                    'quantity': 1,
                }],
                subscription_data=subscription_data,
                success_url=request.build_absolute_uri(
                    reverse('subscription_success')
                ) + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=request.build_absolute_uri(
                    reverse('subscription_required')
                ),
                metadata={
                    'organization_id': str(org.id),
                    'plan_id': str(plan.id),
                },
            )
```

(`timedelta` and `timezone` are already imported at module level in `core/views.py`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_free_trial.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/views.py tests/test_card_free_trial.py
git commit -m "feat: mid-trial checkout keeps first charge at trial end (Stripe trial_end)"
```

---

### Task 5: Persistent trial banner

**Files:**
- Modify: `core/context_processors.py` (defaults dict + organization block)
- Modify: `templates/base.html` (replace the `show_trial_warning` banner block, ~line 369)
- Test: `tests/test_card_free_trial.py` (append)

**Interfaces:**
- Consumes: `is_trial`, `show_trial_warning`, `trial_days_remaining`, `can_manage_billing`, `is_owner` (all already in the context processor); the `_billing_owner(client, team_plan, trial_delta_hours)` test helper defined in Task 4's additions to `tests/test_card_free_trial.py`.
- Produces: new context key `trial_has_card: bool`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_card_free_trial.py`:

```python
@pytest.mark.django_db
def test_trial_banner_shows_days_left_and_plan_cta(client, team_plan):
    _billing_owner(client, team_plan, trial_delta_hours=24 * 10)
    response = client.get(reverse('dashboard'))
    assert response.status_code == 200
    content = response.content.decode()
    assert 'days left' in content
    assert 'Choose your plan' in content


@pytest.mark.django_db
def test_trial_banner_hides_cta_once_card_on_file(client, team_plan):
    from core.models import Organization
    org = _billing_owner(client, team_plan, trial_delta_hours=24 * 10)
    org.stripe_subscription_id = 'sub_hascard'
    org.save()
    response = client.get(reverse('dashboard'))
    content = response.content.decode()
    assert 'days left' in content
    assert 'Choose your plan' not in content
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_card_free_trial.py -q -k banner`
Expected: FAIL — banner only renders in the last 3 days, and says "Subscribe now", not "Choose your plan".

- [ ] **Step 3: Implement**

`core/context_processors.py` — in the defaults dict, after `'show_trial_warning': False,` add:

```python
        'trial_has_card': False,
```

In the `if organization:` block, after `context['show_trial_warning'] = ...` add:

```python
        context['trial_has_card'] = bool(organization.stripe_subscription_id)
```

`templates/base.html` — replace this block:

```html
    {% if show_trial_warning %}
    <div class="bg-amber-600 text-white px-4 py-2 text-center text-sm">
        <span class="font-medium">Trial ending soon!</span>
        Your free trial expires in {{ trial_days_remaining }} day{{ trial_days_remaining|pluralize }}.
        {% if can_manage_billing or is_owner %}
        <a href="{% url 'subscribe' %}" class="underline font-semibold ml-2">Subscribe now</a>
        {% else %}
        Contact your account owner to subscribe.
        {% endif %}
    </div>
    {% endif %}
```

with:

```html
    {% if is_trial %}
    <div class="{% if show_trial_warning %}bg-amber-600{% else %}bg-ch-dark border-b border-ch-gray{% endif %} text-white px-4 py-2 text-center text-sm">
        <span class="font-medium">Free trial{% if show_trial_warning %} — ending soon{% endif %}:</span>
        {{ trial_days_remaining }} day{{ trial_days_remaining|pluralize }} left.
        {% if not trial_has_card %}
            {% if can_manage_billing or is_owner %}
            <a href="{% url 'subscribe' %}" class="underline font-semibold ml-2 text-ch-gold{% if show_trial_warning %} text-white{% endif %}">Choose your plan</a>
            {% else %}
            Contact your account owner to subscribe.
            {% endif %}
        {% endif %}
    </div>
    {% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_free_trial.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add core/context_processors.py templates/base.html tests/test_card_free_trial.py
git commit -m "feat: persistent trial countdown banner with choose-your-plan CTA"
```

---

### Task 6: Wizard step headers and no-card copy

**Files:**
- Modify: `templates/core/onboarding/connect_pco.html` (progress steps, lines ~8-22)
- Modify: `templates/core/onboarding/invite_team.html` (progress steps, lines ~8-22)
- Modify: `templates/core/onboarding/signup.html` (copy at lines ~19, ~31-37, ~45-47, ~135)
- Modify: `templates/core/landing.html` (hero CTA, ~line 269)
- Test: `tests/test_card_free_trial.py` (append)

**Interfaces:** none — template-only.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_card_free_trial.py`:

```python
@pytest.mark.django_db
def test_signup_page_says_no_card_required(client):
    response = client.get(reverse('onboarding_signup'))
    content = response.content.decode()
    assert 'No credit card required' in content
    assert 'We ask for a card' not in content
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_card_free_trial.py::test_signup_page_says_no_card_required -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

**`connect_pco.html`** — replace the progress-steps inner div (Account done, Connect current, Team pending):

```html
        <div class="flex items-center text-sm">
            <span class="flex items-center justify-center w-8 h-8 rounded-full bg-ch-gold text-ch-black font-bold">1</span>
            <span class="ml-2 text-ch-gold">Account</span>
            <div class="w-12 h-0.5 bg-ch-gold mx-4"></div>
            <span class="flex items-center justify-center w-8 h-8 rounded-full bg-ch-gold text-ch-black font-bold">2</span>
            <span class="ml-2 text-ch-gold">Connect</span>
            <div class="w-12 h-0.5 bg-ch-gray mx-4"></div>
            <span class="flex items-center justify-center w-8 h-8 rounded-full bg-ch-gray text-gray-400 font-bold">3</span>
            <span class="ml-2 text-gray-400">Team</span>
        </div>
```

**`invite_team.html`** — replace the progress-steps inner div (all three gold):

```html
        <div class="flex items-center text-sm">
            <span class="flex items-center justify-center w-8 h-8 rounded-full bg-ch-gold text-ch-black font-bold">1</span>
            <span class="ml-2 text-ch-gold">Account</span>
            <div class="w-12 h-0.5 bg-ch-gold mx-4"></div>
            <span class="flex items-center justify-center w-8 h-8 rounded-full bg-ch-gold text-ch-black font-bold">2</span>
            <span class="ml-2 text-ch-gold">Connect</span>
            <div class="w-12 h-0.5 bg-ch-gold mx-4"></div>
            <span class="flex items-center justify-center w-8 h-8 rounded-full bg-ch-gold text-ch-black font-bold">3</span>
            <span class="ml-2 text-ch-gold">Team</span>
        </div>
```

**`signup.html`** — four copy edits:

1. Line ~17-20, replace:
   `Create your account and connect your Planning Center data in a few minutes &mdash; no
            credit card charge until your 14-day trial ends.`
   with:
   `Create your account and connect your Planning Center data in a few minutes &mdash;
            no credit card required.`

2. Lines ~31-37 ("Trial details" paragraph), replace:
   `Your 14-day free trial includes full access. We ask for a card so your account continues
            seamlessly if you keep it, but you are not charged until the trial ends, and you can
            cancel anytime before then.`
   with:
   `Your 14-day free trial includes full access to Team-plan features. No credit card
            required to start &mdash; you choose a plan and add payment whenever you're ready,
            and you can cancel anytime.`

3. Line ~46 (FAQ answer "Will I be charged during the trial?"), replace:
   `No. Your card is not charged until the 14-day trial ends, and you can cancel anytime before then.`
   with:
   `No. No credit card required to start &mdash; nothing is charged unless you choose a plan and subscribe.`

4. Line ~135 (under the submit button), replace:
   `Cancel anytime. Your card isn't charged until your 14-day trial ends.`
   with:
   `No credit card required. Cancel anytime.`

**`landing.html`** — directly after the hero CTA
`<a class="lp-btn lp-btn-gold lp-btn-lg" href="{% url 'onboarding_signup' %}">Start your free trial</a>` (~line 269), add on the next line:

```html
                    <p style="color:#9ca3af;font-size:0.875rem;margin-top:0.75rem">No credit card required · 14-day free trial</p>
```

(Also check the closing CTA at ~line 491 and add the same `<p>` after it.)

**`pricing.html`** — verified during planning: the only card mentions are the
payment-methods FAQ ("We accept all major credit cards through Stripe", lines
~71 and ~471), which describes how paid plans are billed and stays as-is. No
pricing.html change needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_card_free_trial.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add templates/core/onboarding/connect_pco.html templates/core/onboarding/invite_team.html templates/core/onboarding/signup.html templates/core/landing.html tests/test_card_free_trial.py
git commit -m "feat: 3-step wizard headers + no-credit-card-required copy"
```

---

### Task 7: Docs update, full suite, ship

**Files:**
- Modify: `CLAUDE.md` (Public Launch section)
- No new tests.

- [ ] **Step 1: Update CLAUDE.md**

In the "Public Launch (May–June 2026)" section, replace:

`**Public self-serve signup** — \`/signup/\` creates a real org on a **14-day card-required Stripe trial**`

with:

`**Public self-serve signup** — \`/signup/\` creates a real org on a **14-day card-free trial at the Team plan level** (July 2026: card requirement removed to unblock conversions; card collected mid-trial via the persistent banner → \`/subscribe/\`, or at expiry via \`subscription_required\`; mid-trial checkout passes Stripe \`trial_end\` so the first charge stays on day 14)`

Also update the "Strict card enforcement" bullet:

`**Strict card enforcement** — \`TenantMiddleware\` redirects a \`trial\` org with no \`stripe_subscription_id\` to complete checkout;`

with:

`**Card-free trial (replaces strict card enforcement, July 2026)** — active trials need no card; expired trials hard-block via \`needs_subscription\`;`

- [ ] **Step 2: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: all pass, 0 failures. If any unrelated test asserts the old card-gate or old redirect target, fix the assertion to the new behavior (the known ones are already handled in Tasks 1–2).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md reflects card-free trial"
```

- [ ] **Step 4: Push (deploys to production via Railway)**

Only after the full suite is green and the user has confirmed shipping:

```bash
git push origin main
```

Post-deploy smoke checks: signup a throwaway account on aria.church in incognito — expect no plan/checkout step, land on Connect PCO, dashboard shows the trial banner. Confirm `python3 manage.py migrate` ran (Railway start command) so the backfill applied.
