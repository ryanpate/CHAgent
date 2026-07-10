# SEO Tier 3 — Growth Content Design

**Date:** 2026-07-10
**Status:** Approved
**Goal:** Move pages with demonstrated GSC demand from page 2 to page 1, and
open new cluster lanes. Follows Tiers 1–2 (indexing hygiene + on-page fixes,
already shipped).

## Data basis (GSC, Apr–Jul 2026)

- `ai planning center` — pos 15, 29 impr (blog post `ai-for-planning-center-worship-teams`).
- PCO setup guide — pos 18, 149 impr, "crawled – not indexed".
- `aria free`/`ariafreeof` — pos 5–8, 0 clicks (brand snippet not earning clicks).
- Open cluster (no dedicated page): `ai tools for churches` (38), `ai tools for
  church management` (59), `ai tools for church staff`, `church management
  software ai` (65). NOTE: `ai church software` is already owned by
  `best-ai-church-software-2026` — avoid cannibalizing it.

## Content storage facts

- Blog `content` is HTML rendered via `{{ post.content|safe }}` (help_text says
  Markdown but the template renders raw HTML; seeded posts use HTML). `meta_title`
  is max 60 chars. Posts are seeded/updated via data migrations (`blog/0002`,
  `0003`). Latest blog migration: `0003_expand_and_add_posts` → new one is `0004`.
- The PCO setup guide is a TEMPLATE (`templates/resources/pco_setup_guide.html`),
  not a blog row — edit directly. Homepage is `templates/core/landing.html`.

## Work items

### 1. Deepen the AI-for-Planning-Center post (migration `blog/0004`)

Update the `ai-for-planning-center-worship-teams` row: content 713 → ~1,400
words. Add sections: concrete example questions Aria answers from PCO data; how
the AI ↔ Planning Center connection works (reads live PCO People + Services);
three worked use-cases (Sunday scheduling, volunteer care, song/setlist);
manual-vs-AI comparison; FAQ (rendered as HTML in content). Use both
"AI for Planning Center" and "Planning Center AI" phrasings naturally. Internal
links: setup guide, `/integrations/`, `/signup/`. Keep slug, category, published
status. `meta_title` ≤60, keyword-first.

### 2. Deepen the PCO setup guide (template edit)

`pco_setup_guide.html` 1,103 → ~1,800 words. Per step (1–6) add: exact Planning
Center UI path, worship-specific advice, and the common gotcha. Add a "Common
setup mistakes" section. Expand the FAQ (keep existing FAQPage + HowTo schema
valid). Keep the CTR-optimized title ("Planning Center Setup Guide: 6 Steps for
Worship Teams", brandless). Keep/extend internal links to `/integrations/`,
the AI post, `/signup/`.

### 3. Homepage meta description (template edit)

`landing.html` — keep the `<title>`. Rewrite `meta_description` to front-load the
free-trial / no-credit-card message (answers the "aria free" intent) while
keeping the Planning Center + AI keywords. ≤160 chars.

### 4. Two new cluster posts (migration `blog/0004`)

Each: ~1,000+ words HTML content, `meta_title` ≤60 keyword-first, `meta_description`
≤160, `focus_keyword`, `status='published'`, `published_at` set (pass a fixed
timestamp into the migration — `timezone.now()` is fine in a migration, but use a
stable value), assigned to an existing category, FAQ where it fits, internal
links into the cluster (Aria/home, setup guide, AI post, relevant template).

- **Post A — "AI Tools for Churches: A Practical Guide"**
  - slug: `ai-tools-for-churches`
  - focus: `ai tools for churches`
  - Angle: categories of AI tools for churches (worship/scheduling, communication,
    sermon prep, admin/ops), practical and vendor-neutral in tone, with Aria as the
    worship + Planning Center example. Distinct from the software-roundup post.
- **Post B — "AI for Church Volunteer Management"**
  - slug: `ai-church-volunteer-management`
  - focus: `church volunteer management`
  - Angle: volunteer-care/coordination (recruiting, scheduling, follow-up, retention),
    how AI helps a coordinator specifically. Links to the volunteer-application
    template and the care angle. Distinct from the two software-roundup posts.

## Testing

- New/updated posts return 200 and appear in the sitemap (existing sitemap-200
  guard covers this once published).
- Word-count floors: AI post ≥1,300; setup guide ≥1,700; each new post ≥900.
- All JSON-LD on touched pages parses (FAQPage where added).
- `meta_title` of new posts ≤60; homepage meta_description ≤160.
- Internal links present (AI post → setup guide/integrations/signup; new posts →
  cluster).
- Full suite green.

## Out of scope

- The "worship team application" post (deferred).
- Backlinks/authority (Tier 4).
- New keyword targets beyond the cluster already showing impressions.
