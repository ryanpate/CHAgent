# Usage-Cap Enforcement — Design Spec

**Date:** 2026-05-31
**Status:** Approved (design), pending implementation plan
**Author:** Ryan Pate + Claude

## Goal

Enforce the subscription plans' usage limits now that ARIA is a live, paid product.
Hard-block monthly AI queries past the plan limit (the real cost driver), and surface
volunteer overage as an advisory upgrade nudge (volunteers come from Planning Center
sync, so a hard cap would break the core product). This closes the revenue/cost leak
deferred from the public-launch work (`docs/superpowers/specs/2026-05-30-public-launch-design.md`,
workstream C deferral).

## Decisions (locked)

| Decision | Choice |
|---|---|
| Volunteer cap | **Advisory only** — never block PCO sync or interaction auto-matching; show an upgrade banner + billing notice when over limit |
| AI-query cap | **Hard block at 100%** with a friendly upgrade message; **≥80% warning banner**; counter resets monthly (already implemented) |
| Enforcement point | At the **agent query entry** (one user question = one metered unit), before the Claude call |
| Grandfathering | Plans with the `-1` sentinel (Ministry, beta orgs, Cherry Hills) are unlimited → never warned or blocked. No data migration needed. |

## Context (verified)

- Volunteers are created by `PlanningCenterServicesAPI.sync_volunteers()` and auto-created
  during interaction matching (`core/volunteer_matching.py:296`). There is **no manual
  "add volunteer" view** to gate.
- `Organization.increment_ai_usage()` (`core/models.py:327`) increments
  `ai_queries_this_month` and resets it on a new month. It is called **after** the Claude
  call in `core/agent.py:2944`. There is **no pre-check** today.
- `Organization.check_limit(limit_name, current_count)` exists and already treats `-1` as
  unlimited.
- Plan limits (`0018_seed_subscription_plans.py`): Starter 50 vol / 500 queries,
  Team 200 / 2000, Ministry -1 / -1, Enterprise -1 / -1. Beta orgs run the Ministry plan;
  Cherry Hills runs a custom `-1` plan.

## Out of Scope (explicit / YAGNI)

- No hard blocking of volunteer count (no truncating PCO sync or interaction logging).
- No per-feature AI metering beyond the existing single agent-query counter (document
  embeddings, Vision, care insights are NOT separately metered).
- No email/push notification when a cap is hit (banners only).
- No change to how a query is counted (still one increment per agent query).

---

## A. Model layer (`core/models.py`, `Organization`)

Single source of truth so views, the agent, and templates stay thin.

1. **Extract month-reset** from `increment_ai_usage()` into a helper
   `_reset_ai_usage_if_new_month()` that zeroes `ai_queries_this_month` and sets
   `ai_queries_reset_at` when the stored reset month differs from the current month.
   `increment_ai_usage()` calls it, then increments. The agent pre-check (Section B) also
   calls it explicitly (which persists the reset) **before** reading the quota properties,
   so a stale prior-month counter never wrongly blocks. The properties themselves stay pure
   reads (no DB writes on attribute access).

2. **Add properties:**
   - `ai_queries_limit` → `subscription_plan.max_ai_queries_monthly` (or a safe default if no plan).
   - `ai_queries_remaining` → `max(0, limit - ai_queries_this_month)`; `None`/unlimited when limit is `-1`.
   - `ai_query_usage_pct` → integer percent used (0 when unlimited).
   - `ai_quota_exceeded` → `True` only when limit ≥ 0 and `ai_queries_this_month >= limit` (pure read; caller resets first per A.1).
   - `ai_quota_approaching` → `True` when limit ≥ 0 and usage ≥ 80% and not exceeded.
   - `volunteer_limit` → `subscription_plan.max_volunteers`.
   - `volunteer_limit_exceeded` → `True` only when limit ≥ 0 and `get_volunteer_count() > limit`.
   - `volunteer_usage` → dict/tuple `(count, limit)` for display.

   All limit-aware properties treat `-1` (and no-plan unlimited cases) as unlimited → return
   `False`/unlimited so Ministry, beta, and Cherry Hills are never warned or blocked.

## B. AI-query hard enforcement (agent entry)

At the start of the agent query function (the single entry that today leads to the Claude
call + `increment_ai_usage()` at `core/agent.py:2944`):

- If `org.ai_quota_exceeded`: short-circuit. Return a normal assistant-role response with a
  friendly message — e.g. *"You've reached your monthly limit of {limit} AI queries. It
  resets on the 1st of next month, or upgrade your plan for more."* Do **not** call Claude
  and do **not** increment.
- Otherwise: proceed exactly as today (call Claude, then increment).

The blocked response must flow through the normal chat rendering/persistence path so the
user sees it as an Aria message (no 500, no broken UI). Unlimited orgs never hit this branch.

## C. Banners (read-only; dashboard + chat + billing)

Add context vars from the dashboard and chat views (both already resolve `org`):

- `ai_quota_exceeded`, `ai_quota_approaching`, `ai_queries_this_month`, `ai_queries_limit`.
- `volunteer_limit_exceeded`, `volunteer_usage`.

Templates:
- **AI usage banner** (dashboard + chat) when approaching or exceeded:
  "{used} / {limit} AI queries this month" — amber when approaching, red + upgrade link when
  exceeded. Link to `org_settings_billing`.
- **Volunteer advisory banner** (dashboard) when `volunteer_limit_exceeded`:
  "You're tracking {count} volunteers; your plan includes {limit}. Upgrade to stay within
  plan." Link to `org_settings_billing`.
- **Billing notice** on `templates/core/settings/billing.html` mirroring both states.

No banner blocks anything; they are purely informational.

## D. Grandfathering / existing orgs

No migration required. Unlimited plans (`-1`) bypass all helpers. Beta orgs already run the
Ministry plan; Cherry Hills runs a custom `-1` plan. A Starter/Team org already over a limit
at rollout simply sees the advisory banner (volunteers) or is blocked once over the monthly
query cap (correct — they are over).

## Testing / Success Criteria

- **Model helpers:** month-reset zeroes a stale prior-month counter; `ai_quota_exceeded`
  true at/over limit, false under; `ai_quota_approaching` true in [80%, 100%); `-1` plans
  return unlimited/`False` everywhere; `volunteer_limit_exceeded` true only when count > limit
  and limit ≥ 0.
- **Agent pre-check:** an org at its limit gets the upgrade message and **no** Claude call /
  **no** increment (mock the Claude client; assert it isn't called); an org under the limit
  proceeds and increments; an unlimited org is never blocked; a stale prior-month counter
  resets and allows the query.
- **Banners:** dashboard/chat render the AI banner when approaching/exceeded and not
  otherwise; volunteer advisory renders only when over; billing notice mirrors state.
- Full existing suite stays green (currently 820 passing).

## User Actions

None — fully automatable. (Limits are already seeded; no Stripe or env changes.)
