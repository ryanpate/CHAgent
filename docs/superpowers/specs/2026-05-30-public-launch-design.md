# Public Launch ("ARIA goes GA") — Design Spec

**Date:** 2026-05-30
**Status:** Approved (design), pending implementation plan
**Author:** Ryan Pate + Claude

## Goal

Take the ARIA worship-arts SaaS out of closed beta and open it for normal public use
with self-serve signup and paid subscriptions. Reconcile a conflicting pricing structure,
gate premium features by plan, fix SEO/crawl problems surfaced by Google Search Console,
and remove the highest-impact usability blockers in the conversion funnel and first-run
experience.

## Launch Decisions (locked)

| Decision | Choice |
|---|---|
| Go-to-market model | 14-day free trial, **card required** at signup (Stripe collects card, auto-converts to paid) |
| Pricing | **$9.99 / $39.99 / $79.99** monthly; **$100 / $400 / $800** yearly (Starter / Team / Ministry) |
| Existing beta orgs | **Grandfathered free forever** — keep `subscription_status='beta'`, full access, $0, never enter Stripe |
| Tier enforcement | **Premium feature gating now** (analytics, care insights, API access, custom branding); soft usage caps (volunteers, AI queries) **deferred** to fast-follow |

## Out of Scope (explicit)

- Hard usage caps on volunteers and AI queries (deferred — logged as known follow-up).
- Deleting the `BetaRequest` model or beta admin views (kept in code, unlinked from public path).
- Stripe Price creation and `STRIPE_PRICE_*` env var setup (user action — cannot be done from the codebase).
- Re-submitting the sitemap in Search Console (manual user action).

---

## Workstream A — De-beta & open self-serve signup

### A1. Signup flow
`/signup/` (`onboarding_signup`) stops creating a `BetaRequest` and becomes step 1 of the
existing onboarding wizard, which already exists but is currently bypassed:

```
signup → select plan → Stripe checkout (card required, 14-day trial)
       → connect Planning Center → invite team → complete
```

- `beta_signup` view, `BetaRequest` model, and admin approval views (`admin_beta_requests`,
  `admin_beta_approve`, `admin_beta_reject`) remain in the codebase but are unlinked from the
  public path. No deletion (surgical change).
- `onboarding_checkout` must **require** a successful Stripe checkout for new orgs. The current
  fallback that silently redirects to `onboarding_connect_pco` when no Stripe price is configured
  (views.py ~5615-5617) must instead surface a clear error rather than granting free access.

### A2. Grandfather existing beta orgs
Fix the latent lockout bug in `core/models.py`:
- `Organization.is_subscription_active` must return `True` for `subscription_status='beta'`.
- `Organization.needs_subscription` must return `False` for `'beta'`.

Beta orgs retain Ministry-equivalent access at $0 indefinitely and never enter Stripe checkout.

### A3. Branding removal
Remove beta branding from the public templates (landing, pricing, onboarding/base_public,
onboarding/signup, accounts/login):
- BETA badges, "closed beta" subtitle/banner, "Request Beta Access" CTAs, "Free During Beta"
  messaging.
- Replace CTAs with **"Start your 14-day free trial."**
- Add trust line near each CTA: **"Cancel anytime. Your card isn't charged until your trial ends."**

---

## Workstream B — Pricing single source of truth

Reconcile the three conflicting price sets to the locked values. Today:
- Docs (`CLAUDE.md`): $9.99 / $39.99 / $79.99
- DB seed migration (`0018_seed_subscription_plans.py`): $29 / $79 / $149 ← **what actually loads**
- Pricing page JSON-LD schema: $9.99 / $39.99 / $79.99

Changes:
- New migration updating `SubscriptionPlan` rows to $9.99/$39.99/$79.99 monthly and
  $100/$400/$800 yearly. Limits unchanged: Starter 5 users / 50 volunteers / 500 queries;
  Team 15 / 200 / 2000; Ministry unlimited.
- Verify pricing-page JSON-LD matches (already correct).
- Update `CLAUDE.md` pricing table to match.
- Annual price display: show monthly-equivalent + savings, e.g.
  "~$8.33/mo, billed $100/yr (save $19.88)".

**User action required:** create the matching Stripe Prices and set
`STRIPE_PRICE_STARTER_MONTHLY/YEARLY`, `STRIPE_PRICE_TEAM_MONTHLY/YEARLY`,
`STRIPE_PRICE_MINISTRY_MONTHLY/YEARLY`. The implementation will document exactly which env
vars and the expected amounts.

---

## Workstream C — Premium feature gating

Currently feature flags exist on `SubscriptionPlan` (`has_analytics`, `has_care_insights`,
`has_api_access`, `has_custom_branding`) but are not enforced at the view level — any plan can
reach every feature.

- Add a reusable decorator/helper, e.g. `@require_plan_feature('analytics')`, that checks
  `request.organization.has_feature(name)` and redirects with an upgrade message when missing.
- Apply to: analytics dashboard views (`/analytics/*`), care insights/dashboard (`/care/*`),
  API access enablement, and custom branding settings.
- Grandfathered beta orgs map to Ministry-equivalent and therefore pass all gates.
- Soft usage caps (volunteers, AI queries) are **deferred** — log as a known follow-up in
  `CLAUDE.md` technical debt.

---

## Workstream D — SEO fixes (from GSC, 3-month window)

Observed in Search Console exports (2026-05-30):
- Only ~3 pages indexed, ~4 not indexed; blog has zero published posts.
- Crawl errors: 2× "Not found (404)", 1× "Page with redirect", 1× "Crawled – currently not indexed".
- `/resources/planning-center-setup-guide/`: 269 impressions, **0 clicks**, avg position 17.8.
- Brand query "aria church": avg position 5.8 (should be #1).
- Mobile CTR 4.08% vs desktop 0.3%.
- `og-image.png` and `twitter-card.png` still missing.

Tasks:
1. Identify and fix the 2× 404 URLs and the redirect-flagged URL (likely stale sitemap entries
   or old internal links). Correct or remove so crawl budget stops being wasted.
2. Rewrite the PCO setup guide `<title>` + meta description for click-through; deepen content;
   add internal links. (Highest-leverage organic opportunity.)
3. Ensure homepage `<title>` / H1 / `Organization` schema cleanly target the brand so "Aria church"
   reaches position #1.
4. Generate `og-image.png` (1200×630) and `twitter-card.png` (1200×600).
5. Publish 2 seed blog posts targeting observed long-tail queries
   ("planning center ai", "ai church software") so the blog is indexable.
6. Reminder to user: re-submit sitemap in Search Console (manual).

---

## Workstream E — UI/UX usability fixes

### Launch-blocking
**Conversion funnel:**
- CTA labels "Request Access" → "Start Free Trial" (landing, pricing).
- Pricing feature-comparison table → mobile-responsive card layout (mobile converts 13× better).
- Add "What happens after the trial?" clarity to pricing FAQ/info.
- Add security + privacy trust links to the signup form.
- Add forgot-password link to login.

**First-run experience (new paying orgs):**
- Real dashboard empty state with CTA ("Log your first interaction →") instead of bare
  "No interactions logged yet."
- "Connect Planning Center to get started" banner when an org has zero volunteers.
- Disable data-dependent quick-action chips (dashboard + chat) until PCO is connected, so a
  brand-new org doesn't hit cryptic errors.

**Mobile:**
- Responsive chat height (`h-[400px] sm:h-[500px]`).
- Responsive dashboard grids and larger tap targets.

### Nice-to-have (post-launch polish)
- Consistent unread/pending count badges in desktop nav.
- Simplify verbose chat welcome (9 bullets → 3 grouped capabilities).
- Distinct chat vs. dashboard input placeholders.

---

## Sequencing

1. **B** — Pricing single source of truth (unblocks correct billing).
2. **A** — De-beta + billing flow + grandfather beta orgs.
3. **C** — Premium feature gating.
4. **E** — Conversion-funnel + first-run UI (launch-blocking subset first).
5. **D** — SEO fixes (can land independently).

## Testing / Success Criteria

- New visitor can complete signup → plan → Stripe checkout (test mode) → trial org created with
  `subscription_status='trial'` and a card on file.
- Existing `'beta'` org is not locked out and is never prompted to pay.
- Starter-plan org is redirected with an upgrade prompt when hitting analytics/care/API/branding;
  Ministry/beta org passes.
- Pricing displayed on page, in DB, and in JSON-LD all read $9.99/$39.99/$79.99.
- No public template references "beta" / "Request Beta Access".
- GSC crawl-error URLs return correct status (200 or intentional 410/redirect resolved).
- Full existing test suite (452 tests) still passes; new tests added for: open-signup flow,
  beta-org active status, feature-gating decorator.

## User Actions (cannot be automated from codebase)

1. Create Stripe Prices for all 6 plan/interval combinations and set `STRIPE_PRICE_*` env vars.
2. Re-submit sitemap in Google Search Console after crawl fixes deploy.
