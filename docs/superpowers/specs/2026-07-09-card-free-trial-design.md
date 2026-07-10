# Card-Free Trial — Design

**Date:** 2026-07-09
**Status:** Approved
**Goal:** Remove the credit-card requirement from signup to unblock trial starts.
The site currently has no non-tester signups; requiring a church credit card
before the product is ever seen is the largest identified funnel blocker.

## Decisions (made with Ryan)

1. **Trial feature level: Team.** Every new org gets `subscription_plan = Team`
   for the 14-day trial. Analytics and care insights are included (the tier we
   want them to keep); AI queries are capped at Team's 1,000/month, which caps
   throwaway-signup abuse. Ministry-only features stay locked during trial.
2. **Mid-trial conversion honors the remaining trial.** Subscribing on day 5
   saves the card but bills on day 14 (Stripe `subscription_data.trial_end`).
3. **Trial reminder emails are a follow-up project** (needs scheduled-job
   infrastructure). This change ships the in-app countdown only.

## Approach

Skip the plan-selection and checkout steps at signup entirely (approach A).
The wizard becomes **account → connect PCO → invite team**. The card is
collected later through the existing `/subscribe/` flow, either mid-trial
(via a new persistent banner) or at expiry (via the existing
`subscription_required` hard block).

Rejected: keeping the plan step without the card (retains decision friction),
and Stripe's `payment_method_collection: 'if_required'` (still routes new
users through a Stripe checkout page).

## Changes

### 1. Signup flow (`core/views.py::onboarding_signup`)

- Both variants (new user, and authenticated org-less user) assign
  `subscription_plan` at org creation: the active Team-tier plan, falling back
  to the cheapest active plan if Team is missing (mirrors `beta_signup`'s
  fallback pattern).
- Redirect after org creation changes from `onboarding_select_plan` to
  `onboarding_connect_pco`.
- The `?plan=` query param keeps being stored in
  `session['preselected_plan_slug']`; the plan page still uses it if visited.
  No new persistence.

### 2. Enforcement (`core/middleware.py`)

- Delete the card-required block in `_check_subscription_status`
  (trial + no `stripe_subscription_id` → redirect to plan selection).
- Everything else is unchanged: expired trials still hit `needs_subscription`
  → `subscription_required`; beta orgs still bypass everything.

### 3. Backfill migration

- Data migration: existing orgs with `subscription_status='trial'` and
  `subscription_plan IS NULL` get the Team plan. (A plan-less org has
  features locked but **unlimited** AI queries — both wrong for trials.)

### 4. Conversion surface

- **Banner (`templates/base.html` + `core/context_processors.py`):** replace
  the last-3-days-only warning with a persistent trial pill:
  "Free trial — N days left · Choose your plan", linking to `/subscribe/`.
  Urgent styling at ≤ 3 days. Once `stripe_subscription_id` is set (card
  already on file), the "Choose your plan" CTA is hidden but the days-left
  pill stays visible for the remainder of the trial.
- **Mid-trial checkout (`core/views.py::subscribe`):** when the org is in an
  active trial with `trial_ends_at` more than 48 hours away (Stripe Checkout's
  minimum for `trial_end`), pass
  `subscription_data={'trial_end': int(org.trial_ends_at.timestamp())}` so the
  first charge lands at trial end. Under 48 hours, billing starts immediately
  (Stripe constraint; at most a 2-day difference).
- Post-trial conversion (`subscription_required` → `subscribe`) and
  `subscription_success` finalization (with the session-ownership check) are
  unchanged.

### 5. Wizard step indicators

- Onboarding templates (`connect_pco.html`, `invite_team.html`, `complete.html`,
  and any others showing the 4-step progress header) change from
  Account → Plan → Connect → Team to **Account → Connect → Team**.
- `select_plan.html` keeps its own header (it remains the mid-trial upgrade
  page); its copy may drop trial-specific phrasing.

### 6. Copy

- `signup.html`: "We ask for a card…" trial-details paragraph and the
  "Will I be charged during the trial?" FAQ → "No credit card required to
  start." Keep the cancel-anytime note.
- `landing.html`: "no credit card charge until your trial ends" and similar →
  "no credit card required".
- `pricing.html`: same treatment wherever card-at-signup language appears
  (including FAQ/JSON-LD strings).

### 7. Kept, not deleted

- `onboarding_select_plan` and `onboarding_checkout` routes remain functional —
  they are the mid-trial upgrade surface reached from the banner/pricing.

## Out of scope (follow-ups)

- Trial reminder emails (day 11 / day 14) — needs Railway cron; pairs with the
  weekly digest project.
- PCO OAuth, landing-page demo, free tier.

## Testing

- New: signup redirects to connect-pco and assigns the Team plan (both signup
  variants); middleware allows an active trial with no card; expired trial
  still blocked; mid-trial `subscribe` checkout passes `trial_end` (>48h) and
  omits it (<48h); banner renders days-left + CTA, hides CTA when a
  subscription id exists; backfill migration assigns Team to plan-less trials.
- Inverted: `tests/test_card_enforcement.py` (6 tests assert the old
  card-required redirects).
- Full suite green before push.
