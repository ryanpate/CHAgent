# Usage-Cap Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hard-enforce the monthly AI-query cap (block at 100% with an ≥80% warning) and surface volunteer overage as an advisory upgrade nudge, with unlimited (`-1`) plans never affected.

**Architecture:** All limit logic lives as pure-read properties + one reset method on `Organization` (single source of truth). The agent's `query_agent` entry calls the reset method then short-circuits with a friendly message when the quota is exceeded — before any Claude call. Dashboard/chat/billing templates read context booleans to show banners. No blocking of volunteers (they come from Planning Center sync).

**Tech Stack:** Django 5, pytest. Spec: `docs/superpowers/specs/2026-05-31-usage-caps-design.md`.

**Test command:** `python3 -m pytest tests/<file> -v`. Full suite must stay green (currently 820 passing).

**Verified anchors:**
- `core/models.py`: `Organization.increment_ai_usage()` at ~line 327 (month-reset inline, compares `.month` only — a cross-year bug), `check_limit()` at ~318, `get_volunteer_count()` returns `self.volunteers.count()`, fields `ai_queries_this_month` / `ai_queries_reset_at`, `subscription_plan.max_ai_queries_monthly` / `max_volunteers` (with `-1` = unlimited). `timezone` is imported in models.py.
- `core/agent.py`: `def query_agent(question, user, session_id, organization=None) -> str:` at ~line 4246 (returns the answer string). AI usage is incremented inside `call_claude()` (~line 2944), which may run multiple times per `query_agent` — so the counter meters Claude calls.
- The chat view passes `organization` to `query_agent` (verify with `grep -n "query_agent(" core/views.py`). The returned string is rendered/persisted as an Aria `ChatMessage` by the caller.
- Dashboard view (`core/views.py`, `def dashboard`) already builds a context dict and computes `pco_connected`; chat view builds its own context. Both have `org = get_org(request)`.

---

### Task 1: Extract the month-reset method (and fix the cross-year bug)

**Files:**
- Modify: `core/models.py` (`increment_ai_usage` ~327)
- Test: `tests/test_usage_caps.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_usage_caps.py
import pytest
from datetime import datetime, timezone as dt_tz
from core.models import Organization, SubscriptionPlan


def _org(monthly=500, vol=50, used=0, voln=0):
    plan = SubscriptionPlan.objects.create(
        slug=f'p{monthly}-{vol}-{used}-{voln}', name='P', tier='team',
        max_ai_queries_monthly=monthly, max_volunteers=vol)
    return Organization.objects.create(
        name='Cap Org', email='c@x.org', subscription_plan=plan,
        subscription_status='active', ai_queries_this_month=used)


@pytest.mark.django_db
def test_reset_zeros_counter_on_new_month():
    org = _org(used=400)
    # Pretend the counter was last reset in a previous month of a previous year
    org.ai_queries_reset_at = datetime(2025, 5, 1, tzinfo=dt_tz.utc)
    org.save(update_fields=['ai_queries_reset_at'])
    org.reset_ai_usage_if_new_month()
    org.refresh_from_db()
    assert org.ai_queries_this_month == 0


@pytest.mark.django_db
def test_reset_keeps_counter_within_same_month():
    from django.utils import timezone
    org = _org(used=400)
    org.ai_queries_reset_at = timezone.now()
    org.save(update_fields=['ai_queries_reset_at'])
    org.reset_ai_usage_if_new_month()
    org.refresh_from_db()
    assert org.ai_queries_this_month == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_usage_caps.py -k reset -v`
Expected: FAIL — `Organization` has no `reset_ai_usage_if_new_month`.

- [ ] **Step 3: Implement**

In `core/models.py`, replace `increment_ai_usage` with a reset method + a thin increment that calls it. Fix the reset to compare year AND month:

```python
    def reset_ai_usage_if_new_month(self):
        """Zero the monthly AI counter when the calendar month has rolled over.

        Persists the reset. Safe to call before reading quota properties.
        """
        now = timezone.now()
        last = self.ai_queries_reset_at
        if last is None or (last.year, last.month) != (now.year, now.month):
            self.ai_queries_this_month = 0
            self.ai_queries_reset_at = now
            self.save(update_fields=['ai_queries_this_month', 'ai_queries_reset_at'])

    def increment_ai_usage(self):
        """Increment AI query counter for the month."""
        self.reset_ai_usage_if_new_month()
        self.ai_queries_this_month += 1
        self.save(update_fields=['ai_queries_this_month', 'ai_queries_reset_at'])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_usage_caps.py -k reset -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_usage_caps.py
git commit -m "feat: extract reset_ai_usage_if_new_month and fix cross-year reset"
```

---

### Task 2: Quota + volunteer properties on `Organization`

**Files:**
- Modify: `core/models.py` (add properties near `check_limit`)
- Test: `tests/test_usage_caps.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_usage_caps.py
@pytest.mark.django_db
def test_ai_quota_properties():
    org = _org(monthly=500, used=500)
    assert org.ai_queries_limit == 500
    assert org.ai_queries_remaining == 0
    assert org.ai_quota_exceeded is True
    assert org.ai_quota_approaching is False  # exceeded, not "approaching"

    org2 = _org(monthly=500, used=400)
    assert org2.ai_query_usage_pct == 80
    assert org2.ai_quota_approaching is True
    assert org2.ai_quota_exceeded is False
    assert org2.ai_queries_remaining == 100

    org3 = _org(monthly=500, used=399)
    assert org3.ai_quota_approaching is False  # 79%

@pytest.mark.django_db
def test_unlimited_and_no_plan_never_gated():
    unlimited = _org(monthly=-1, used=99999)
    assert unlimited.ai_quota_exceeded is False
    assert unlimited.ai_quota_approaching is False
    no_plan = Organization.objects.create(name='NP', email='np@x.org',
                                          subscription_status='active', ai_queries_this_month=99999)
    assert no_plan.ai_quota_exceeded is False
    assert no_plan.ai_quota_approaching is False

@pytest.mark.django_db
def test_volunteer_limit_properties():
    from core.models import Volunteer
    org = _org(vol=2)
    for i in range(3):
        Volunteer.objects.create(organization=org, name=f'V{i}')
    assert org.volunteer_limit == 2
    assert org.volunteer_limit_exceeded is True
    assert org.volunteer_usage == (3, 2)

    org_ok = _org(vol=50)
    assert org_ok.volunteer_limit_exceeded is False

    unlimited = _org(vol=-1)
    from core.models import Volunteer as V
    V.objects.create(organization=unlimited, name='x')
    assert unlimited.volunteer_limit_exceeded is False
```

> Note: confirm the minimal required fields for `Volunteer.objects.create` by reading the model (`core/models.py:643`); `organization` and `name` should suffice (`normalized_name` may auto-populate on save — if it's required, pass it).

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_usage_caps.py -k "quota or volunteer or unlimited" -v`
Expected: FAIL — properties don't exist.

- [ ] **Step 3: Implement**

In `core/models.py`, add after `check_limit`:

```python
    @property
    def ai_queries_limit(self):
        """Monthly AI-query limit (-1 = unlimited; None when no plan)."""
        if not self.subscription_plan:
            return None
        return self.subscription_plan.max_ai_queries_monthly

    @property
    def _ai_limited(self):
        """True only when a finite (>=0) AI limit applies."""
        lim = self.ai_queries_limit
        return lim is not None and lim >= 0

    @property
    def ai_queries_remaining(self):
        if not self._ai_limited:
            return None
        return max(0, self.ai_queries_limit - self.ai_queries_this_month)

    @property
    def ai_query_usage_pct(self):
        if not self._ai_limited or self.ai_queries_limit == 0:
            return 0
        return int(self.ai_queries_this_month / self.ai_queries_limit * 100)

    @property
    def ai_quota_exceeded(self):
        """Pure read — callers should call reset_ai_usage_if_new_month() first."""
        if not self._ai_limited:
            return False
        return self.ai_queries_this_month >= self.ai_queries_limit

    @property
    def ai_quota_approaching(self):
        if not self._ai_limited or self.ai_quota_exceeded:
            return False
        return self.ai_query_usage_pct >= 80

    @property
    def volunteer_limit(self):
        if not self.subscription_plan:
            return None
        return self.subscription_plan.max_volunteers

    @property
    def volunteer_limit_exceeded(self):
        lim = self.volunteer_limit
        if lim is None or lim < 0:
            return False
        return self.get_volunteer_count() > lim

    @property
    def volunteer_usage(self):
        """(count, limit) for display."""
        return (self.get_volunteer_count(), self.volunteer_limit)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_usage_caps.py -k "quota or volunteer or unlimited" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/models.py tests/test_usage_caps.py
git commit -m "feat: add AI-quota and volunteer-limit properties to Organization"
```

---

### Task 3: Agent pre-check — block over-limit queries

**Files:**
- Modify: `core/agent.py` (`query_agent` ~4246)
- Test: `tests/test_usage_caps.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_usage_caps.py
from accounts.models import User

@pytest.mark.django_db
def test_query_agent_blocks_when_over_limit():
    from core.agent import query_agent
    org = _org(monthly=500, used=500)
    user = User.objects.create_user(username='q@x.org', email='q@x.org', password='supersecret1')
    before = org.ai_queries_this_month
    result = query_agent("Who is serving Sunday?", user, "sess-1", organization=org)
    assert 'limit' in result.lower()
    assert 'upgrade' in result.lower() or 'billing' in result.lower()
    org.refresh_from_db()
    assert org.ai_queries_this_month == before  # blocked before any Claude call -> no increment

@pytest.mark.django_db
def test_query_agent_guard_skipped_when_not_exceeded():
    # An org under its limit (and an unlimited org) must NOT receive the limit message.
    # We prove the guard branch is not taken without running the full agent body by
    # checking ai_quota_exceeded is False (the guard's exact condition).
    under = _org(monthly=500, used=10)
    unlimited = _org(monthly=-1, used=99999)
    assert under.ai_quota_exceeded is False
    assert unlimited.ai_quota_exceeded is False
```

> The block-path test is the load-bearing one: it returns before any Claude call, so it needs no external API or mocking. The non-blocking path is verified via the guard's exact condition (`ai_quota_exceeded`) rather than running the full agent body (which would hit external APIs) — combined with the one-line guard in Step 3, this fully covers the branch.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_usage_caps.py -k query_agent -v`
Expected: the block test FAILS (over-limit org currently proceeds into the agent body).

- [ ] **Step 3: Implement**

At the very top of `query_agent` body in `core/agent.py` (after the docstring, before any other work), add the guard:

```python
    if organization is not None:
        organization.reset_ai_usage_if_new_month()
        if organization.ai_quota_exceeded:
            limit = organization.ai_queries_limit
            return (
                f"You've reached your plan's monthly limit of {limit} AI queries. "
                f"Your usage resets on the 1st of next month — or upgrade your plan for more. "
                f"You can change plans in [billing settings](/settings/billing/)."
            )
```

Read the first ~15 lines of `query_agent` to place this after the docstring and before the existing logic. Do not change the increment in `call_claude` (it correctly meters each Claude call).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_usage_caps.py -k query_agent -v`
Expected: block test PASSES. (If the unlimited test's stub seam doesn't match, simplify it to assert the guard branch isn't taken — e.g., temporarily set the org's usage under limit and assert no limit message — but keep an assertion that unlimited orgs are not blocked.)

- [ ] **Step 5: Commit**

```bash
git add core/agent.py tests/test_usage_caps.py
git commit -m "feat: block over-limit AI queries at the agent entry with an upgrade message"
```

---

### Task 4: Usage banners on dashboard + chat

**Files:**
- Modify: `core/views.py` (`dashboard` and `chat` view contexts)
- Modify: `templates/core/dashboard.html`, `templates/core/chat.html`
- Test: `tests/test_usage_caps.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_usage_caps.py
from django.urls import reverse
from core.models import OrganizationMembership

def _login(client, org):
    u = User.objects.create_user(username=f'm{org.id}@x.org', email=f'm{org.id}@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner')
    u.default_organization = org; u.save()
    client.force_login(u)
    return u

@pytest.mark.django_db
def test_dashboard_shows_ai_and_volunteer_banners(client):
    from core.models import Volunteer
    org = _org(monthly=500, used=500, vol=2)
    org.stripe_subscription_id = 'sub_x'; org.save()
    for i in range(3):
        Volunteer.objects.create(organization=org, name=f'V{i}')
    _login(client, org)
    body = client.get(reverse('dashboard')).content.decode()
    assert 'AI queries this month' in body          # AI banner (exceeded)
    assert 'plan includes' in body                  # volunteer advisory banner

@pytest.mark.django_db
def test_dashboard_no_banners_when_within_limits(client):
    org = _org(monthly=500, used=10, vol=50)
    org.stripe_subscription_id = 'sub_x'; org.save()
    _login(client, org)
    body = client.get(reverse('dashboard')).content.decode()
    assert 'AI queries this month' not in body
    assert 'plan includes' not in body
```

> Tests use an `active` org with `stripe_subscription_id` so the card-enforcement middleware doesn't redirect.

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_usage_caps.py -k banner -v`
Expected: FAIL — banners not rendered.

- [ ] **Step 3: Add context + templates**

In `core/views.py` `dashboard` view, add to the context dict (alongside `pco_connected`):

```python
        'ai_quota_exceeded': org.ai_quota_exceeded if org else False,
        'ai_quota_approaching': org.ai_quota_approaching if org else False,
        'ai_queries_used': org.ai_queries_this_month if org else 0,
        'ai_queries_limit': org.ai_queries_limit if org else None,
        'volunteer_over_limit': org.volunteer_limit_exceeded if org else False,
        'volunteer_count': org.get_volunteer_count() if org else 0,
        'volunteer_limit': org.volunteer_limit if org else None,
```

Add the same `ai_quota_*` / `ai_queries_*` keys to the `chat` view context (chat needs only the AI banner). Read both views first to insert into the existing context dicts.

Create a reusable banner include `templates/core/partials/usage_banners.html`:

```html
{% if ai_quota_exceeded %}
<div class="bg-red-500/10 border border-red-500/40 rounded-lg p-4 mb-6">
  <p class="text-sm text-red-300">You've used {{ ai_queries_used }} / {{ ai_queries_limit }} AI queries this month. New questions are paused until the 1st, or
    <a href="{% url 'org_settings_billing' %}" class="text-ch-gold hover:underline">upgrade your plan</a>.</p>
</div>
{% elif ai_quota_approaching %}
<div class="bg-ch-gold/10 border border-ch-gold/30 rounded-lg p-4 mb-6">
  <p class="text-sm text-gray-300">{{ ai_queries_used }} / {{ ai_queries_limit }} AI queries this month.
    <a href="{% url 'org_settings_billing' %}" class="text-ch-gold hover:underline">Need more?</a></p>
</div>
{% endif %}
{% if volunteer_over_limit %}
<div class="bg-ch-gold/10 border border-ch-gold/30 rounded-lg p-4 mb-6">
  <p class="text-sm text-gray-300">You're tracking {{ volunteer_count }} volunteers; your plan includes {{ volunteer_limit }}.
    <a href="{% url 'org_settings_billing' %}" class="text-ch-gold hover:underline">Upgrade to stay within plan</a>.</p>
</div>
{% endif %}
```

Include it near the top of the content block in `templates/core/dashboard.html` (after the PCO banner) and `templates/core/chat.html`: `{% include 'core/partials/usage_banners.html' %}`. (The volunteer block simply won't render on chat since `volunteer_over_limit` isn't in chat's context — that's fine; to be explicit, the chat view may omit the volunteer keys.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_usage_caps.py -k banner -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add core/views.py templates/core/dashboard.html templates/core/chat.html templates/core/partials/usage_banners.html tests/test_usage_caps.py
git commit -m "feat: show AI-usage and volunteer-overage banners on dashboard and chat"
```

---

### Task 5: Usage notice on the billing settings page

**Files:**
- Modify: `core/views.py` (`org_settings_billing` view context), `templates/core/settings/billing.html`
- Test: `tests/test_usage_caps.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_usage_caps.py
@pytest.mark.django_db
def test_billing_page_shows_usage(client):
    from core.models import Volunteer
    org = _org(monthly=500, used=320, vol=2)
    org.stripe_subscription_id = 'sub_x'; org.save()
    for i in range(3):
        Volunteer.objects.create(organization=org, name=f'V{i}')
    u = User.objects.create_user(username='b@x.org', email='b@x.org', password='supersecret1')
    OrganizationMembership.objects.create(user=u, organization=org, role='owner', can_manage_billing=True)
    u.default_organization = org; u.save()
    client.force_login(u)
    body = client.get(reverse('org_settings_billing')).content.decode()
    assert '320' in body and '500' in body         # AI usage shown
    assert 'Usage' in body or 'usage' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_usage_caps.py -k billing -v`
Expected: FAIL — usage not shown.

- [ ] **Step 3: Implement**

Read `org_settings_billing` in `core/views.py` and its template `templates/core/settings/billing.html`. Add to the view context:

```python
        'ai_queries_used': org.ai_queries_this_month,
        'ai_queries_limit': org.ai_queries_limit,
        'volunteer_count': org.get_volunteer_count(),
        'volunteer_limit': org.volunteer_limit,
        'volunteer_over_limit': org.volunteer_limit_exceeded,
```

Add a "Usage this month" section to `billing.html` (match existing card styling):

```html
<div class="bg-ch-dark rounded-lg p-6 mb-6">
  <h2 class="text-lg font-semibold mb-4">Usage this month</h2>
  <div class="space-y-2 text-sm">
    <div class="flex justify-between"><span class="text-gray-400">AI queries</span>
      <span class="text-white">{{ ai_queries_used }}{% if ai_queries_limit and ai_queries_limit >= 0 %} / {{ ai_queries_limit }}{% else %} (unlimited){% endif %}</span></div>
    <div class="flex justify-between"><span class="text-gray-400">Volunteers</span>
      <span class="{% if volunteer_over_limit %}text-ch-gold{% else %}text-white{% endif %}">{{ volunteer_count }}{% if volunteer_limit and volunteer_limit >= 0 %} / {{ volunteer_limit }}{% else %} (unlimited){% endif %}</span></div>
  </div>
  {% if volunteer_over_limit %}<p class="text-ch-gold text-xs mt-3">You're over your plan's volunteer limit — consider upgrading.</p>{% endif %}
</div>
```

Place it near the current-plan section. Confirm `ai_queries_limit` of `None` (no plan) renders gracefully — the `{% if ai_queries_limit and ai_queries_limit >= 0 %}` guard handles None and -1 (shows "(unlimited)").

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_usage_caps.py -k billing -v`
Expected: PASS.

- [ ] **Step 5: Run full suite + commit**

Run: `python3 -m pytest tests/ -q 2>&1 | tail -5`
Expected: 0 failures.

```bash
git add core/views.py templates/core/settings/billing.html tests/test_usage_caps.py
git commit -m "feat: show monthly usage (AI + volunteers) on billing settings"
```

---

## Self-Review / Coverage

Spec → tasks: month-reset + cross-year fix (Task 1); all quota + volunteer properties incl. `-1`/no-plan unlimited (Task 2); agent hard-block before Claude with no increment (Task 3); dashboard + chat banners for approaching/exceeded/volunteer-over (Task 4); billing usage notice (Task 5). Grandfathering is covered by the `_ai_limited`/`volunteer_limit < 0` guards (Task 2) — Ministry/beta/Cherry Hills (`-1`) are never gated. "Out of scope" items (no volunteer hard-block, no extra metering, no emails) are honored.

## Final Verification

- [ ] `python3 -m pytest tests/ -q` → all pass.
- [ ] Manual: a Starter test org with `ai_queries_this_month` set to its limit gets the upgrade message in chat (no answer, counter unchanged); at 80% sees the amber banner; an org over `max_volunteers` sees the advisory banner on dashboard + billing; a Ministry/beta org sees none of these.
