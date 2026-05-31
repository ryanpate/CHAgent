# Public Launch — Plan 3: SEO Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the SEO problems Google Search Console surfaced — crawl errors, the PCO guide that ranks but gets zero clicks, weak brand targeting, missing social images, and an empty blog — to grow organic visibility.

**Architecture:** Template/meta edits, a Pillow script that generates the social-share PNGs, and a data migration that seeds two published blog posts (no schema changes). A sitemap-health test guards crawlability going forward.

**Tech Stack:** Django 5 templates + sitemaps, Pillow (already a dependency) for image generation, pytest.

**Spec:** `docs/superpowers/specs/2026-05-30-public-launch-design.md` (workstream D).

**GSC data (3-month window, captured 2026-05-30):** ~3 pages indexed; crawl errors = 2× "Not found (404)", 1× "Page with redirect", 1× "Crawled – currently not indexed"; `/resources/planning-center-setup-guide/` = 269 impressions / 0 clicks / avg position 17.8; brand query "aria church" avg position 5.8; mobile CTR 4.08% vs desktop 0.3%; `og-image.png`/`twitter-card.png` referenced but missing.

**Test command:** `python3 -m pytest tests/<file> -v`. Full suite must stay green (currently 791 passing).

---

### Task 1: Sitemap health test + register category sitemap + locate crawl errors

**Files:**
- Modify: `config/urls.py` (sitemaps dict ~16-19)
- Test: `tests/test_seo.py` (create)

The blog **category** sitemap exists (`blog/sitemaps.py:BlogCategorySitemap`) but is NOT registered, so category pages aren't submitted. Register it, and add a permanent guard that every sitemap URL returns 200 (stale sitemap entries are a common 404 source).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seo.py
import re
import pytest

@pytest.mark.django_db
def test_every_sitemap_url_returns_200(client):
    xml = client.get('/sitemap.xml').content.decode()
    locs = re.findall(r'<loc>([^<]+)</loc>', xml)
    assert locs, "sitemap is empty"
    bad = []
    for url in locs:
        path = re.sub(r'^https?://[^/]+', '', url)  # strip domain → local path
        resp = client.get(path)
        if resp.status_code != 200:
            bad.append((path, resp.status_code))
    assert not bad, f"sitemap URLs not returning 200: {bad}"

@pytest.mark.django_db
def test_category_sitemap_registered(client):
    # BlogCategorySitemap must be wired so category pages are submitted.
    from config.urls import sitemaps
    assert 'blog-categories' in sitemaps
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_seo.py -v`
Expected: `test_category_sitemap_registered` FAILS (`blog-categories` not in dict). `test_every_sitemap_url_returns_200` should pass for the static URLs (they're real view names); if it fails, you've found a broken sitemap entry — note it for Step 3.

- [ ] **Step 3: Register the category sitemap**

In `config/urls.py`, import `BlogCategorySitemap` from `blog.sitemaps` and add it to the `sitemaps` dict:

```python
from blog.sitemaps import BlogSitemap, BlogCategorySitemap
...
sitemaps = {
    'static': StaticViewSitemap,
    'blog': BlogSitemap,
    'blog-categories': BlogCategorySitemap,
}
```
(Match the existing import style — confirm the current import line first.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_seo.py -v`
Expected: PASS.

- [ ] **Step 5: Investigate the 2 GSC 404s + 1 redirect (documented, needs the URLs)**

The exact 404 / redirect URLs are NOT in the GSC export (only counts). Get them from **Search Console → Indexing → Pages → "Not found (404)"** and **"Page with redirect"** (the user can export these). For each:
- **Sitemap URL returning 404** → the `test_every_sitemap_url_returns_200` test above already catches it; fix the broken view/template or remove the stale sitemap entry.
- **Old/renamed URL Google still has indexed** (not in sitemap) → add a redirect. Use Django's `RedirectView` in `core/urls.py`, e.g.:
  ```python
  from django.views.generic import RedirectView
  path('old-path/', RedirectView.as_view(url='/new-path/', permanent=True)),
  ```
- **"Page with redirect"** flagged in GSC is usually benign (http→https or trailing slash). Only act if it's an unintended chain.

Record findings in the commit message. If no URLs are available yet, the sitemap-health test + category registration still ship; note the 404 follow-up explicitly so it isn't silently dropped.

- [ ] **Step 6: Commit**

```bash
git add config/urls.py tests/test_seo.py
git commit -m "feat: register blog category sitemap and guard all sitemap URLs return 200"
```

---

### Task 2: Rescue the PCO setup guide (CTR + depth)

**Files:**
- Modify: `templates/resources/pco_setup_guide.html` (title ~3, meta ~4, content + schema)
- Test: `tests/test_seo.py`

269 impressions, 0 clicks at position 17.8 → the title/meta aren't compelling and the page needs more depth + a FAQ to win the query and a rich result.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_seo.py
@pytest.mark.django_db
def test_pco_guide_has_faq_and_compelling_title(client):
    body = client.get('/resources/planning-center-setup-guide/').content.decode()
    # FAQ section + FAQPage schema added for a rich result
    assert 'FAQPage' in body
    assert 'Frequently asked questions' in body or 'Frequently Asked Questions' in body
    # Title leads with the year/benefit to lift CTR
    assert '2026' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_seo.py::test_pco_guide_has_faq_and_compelling_title -v`
Expected: FAIL — no FAQ section/schema; title has no year.

- [ ] **Step 3: Improve title/meta and add a FAQ**

In `templates/resources/pco_setup_guide.html`:

(a) Title block (~line 3) — make it benefit + freshness led:
```html
{% block title %}Planning Center Setup Guide (2026): Step-by-Step for Worship Teams | Aria{% endblock %}
```
(b) Meta description (~line 4) — tighter, action-oriented (≤155 chars):
```html
{% block meta_description %}Set up Planning Center Online for your worship team in 6 steps — Services, Teams, People, and Songs. A clear 2026 walkthrough with pro tips.{% endblock %}
```
(c) Add a FAQ section near the end of the article content (before the closing CTA), with 3 real Q&As, plus FAQPage JSON-LD. Add inside the existing `{% block schema_markup %}` (append a second `<script type="application/ld+json">`) and add the visible FAQ markup in the content block:

Visible FAQ (in the content block):
```html
<h2 class="text-2xl font-bold text-white mt-10 mb-4">Frequently asked questions</h2>
<div class="space-y-4">
  <div><h3 class="text-lg font-semibold text-white">Is Planning Center free?</h3>
    <p class="text-gray-400">Planning Center Services has a free tier for small teams; paid plans add more plans and people. Aria works with any PCO plan.</p></div>
  <div><h3 class="text-lg font-semibold text-white">How long does setup take?</h3>
    <p class="text-gray-400">Most worship teams complete the core setup — service types, teams, and people — in under an hour by following the six steps above.</p></div>
  <div><h3 class="text-lg font-semibold text-white">Can AI answer questions about my Planning Center data?</h3>
    <p class="text-gray-400">Yes. Aria connects to Planning Center and answers questions about schedules, volunteers, blockouts, and songs in plain language. <a href="{% url 'onboarding_signup' %}" class="text-ch-gold hover:underline">Start a free trial</a>.</p></div>
</div>
```

FAQPage schema (append in `schema_markup` block):
```html
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"FAQPage","mainEntity":[
 {"@type":"Question","name":"Is Planning Center free?","acceptedAnswer":{"@type":"Answer","text":"Planning Center Services has a free tier for small teams; paid plans add more plans and people. Aria works with any PCO plan."}},
 {"@type":"Question","name":"How long does Planning Center setup take?","acceptedAnswer":{"@type":"Answer","text":"Most worship teams complete the core setup in under an hour by following the six steps."}},
 {"@type":"Question","name":"Can AI answer questions about my Planning Center data?","acceptedAnswer":{"@type":"Answer","text":"Yes. Aria connects to Planning Center and answers questions about schedules, volunteers, blockouts, and songs in plain language."}}
]}
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_seo.py::test_pco_guide_has_faq_and_compelling_title -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/resources/pco_setup_guide.html tests/test_seo.py
git commit -m "feat: improve PCO guide title/meta and add FAQ + FAQPage schema for CTR"
```

---

### Task 3: Strengthen homepage brand targeting

**Files:**
- Modify: `templates/core/landing.html` (title ~3, H1 ~89), `templates/core/onboarding/base_public.html` (Organization schema ~36-47)
- Test: `tests/test_seo.py`

Brand query "aria church" sits at position 5.8 — you should own it. The title doesn't lead with the brand and the H1 has no brand mention.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_seo.py
@pytest.mark.django_db
def test_homepage_targets_brand(client):
    body = client.get('/').content.decode()
    # Title leads with the brand
    import re
    title = re.search(r'<title>(.*?)</title>', body, re.S).group(1)
    assert title.strip().startswith('Aria')
    # Organization schema carries alternateName for brand variants
    assert 'alternateName' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_seo.py::test_homepage_targets_brand -v`
Expected: FAIL — title starts with "AI Worship…"; schema has no `alternateName`.

- [ ] **Step 3: Implement**

(a) `templates/core/landing.html` title block (~line 3):
```html
{% block title %}Aria — AI Worship Team Management Software with Planning Center{% endblock %}
```
(b) `templates/core/landing.html` H1 (~line 89) — add a brand mention without losing the keyword. Change to:
```html
<h1 class="text-4xl md:text-6xl font-bold text-white mb-6">
    <span class="gradient-text">Aria</span> — AI-Powered Worship Team Management
</h1>
```
(c) `templates/core/onboarding/base_public.html` Organization schema (~36-47): add `alternateName` and populate `sameAs` (use the App Store URL already referenced elsewhere in the project):
```json
    "name": "Aria",
    "alternateName": "Aria Church",
    "url": "https://aria.church",
    "sameAs": ["https://apps.apple.com/us/app/aria-wa-assistant/id6759796456"],
```
(keep the other existing fields).

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_seo.py::test_homepage_targets_brand -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/core/landing.html templates/core/onboarding/base_public.html tests/test_seo.py
git commit -m "feat: target Aria brand in homepage title, H1, and Organization schema"
```

---

### Task 4: Generate the social-share images (og-image + twitter-card)

**Files:**
- Create: `scripts/generate_og_images.py`
- Create (generated, committed): `static/og-image.png` (1200×630), `static/twitter-card.png` (1200×600)
- Test: `tests/test_seo.py`

Both files are referenced by templates but don't exist (every social share renders broken). Generate them reproducibly with Pillow (already a dependency).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_seo.py
from pathlib import Path
from django.conf import settings

def test_social_images_exist_with_correct_dimensions():
    from PIL import Image
    base = Path(settings.BASE_DIR) / 'static'
    og = base / 'og-image.png'
    tw = base / 'twitter-card.png'
    assert og.exists() and tw.exists(), "social images missing"
    assert Image.open(og).size == (1200, 630)
    assert Image.open(tw).size == (1200, 600)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_seo.py::test_social_images_exist_with_correct_dimensions -v`
Expected: FAIL — files don't exist.

- [ ] **Step 3: Write the generator script**

Create `scripts/generate_og_images.py`:

```python
"""Generate Aria social-share images. Run: python3 scripts/generate_og_images.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BG = (15, 15, 15)        # #0f0f0f
GOLD = (201, 162, 39)    # #c9a227
WHITE = (245, 245, 245)
OUT = Path(__file__).resolve().parent.parent / 'static'

def _font(size):
    # Try a bundled TTF; fall back to Pillow's default bitmap font.
    for p in [OUT / 'fonts' / 'Inter-Bold.ttf', OUT / 'fonts' / 'Inter.ttf']:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    try:
        return ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf', size)
    except Exception:
        return ImageFont.load_default()

def _center_text(draw, text, font, y, w, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) / 2, y), text, font=font, fill=fill)

def make(width, height, path):
    img = Image.new('RGB', (width, height), BG)
    d = ImageDraw.Draw(img)
    _center_text(d, 'ARIA', _font(140), height // 2 - 130, width, GOLD)
    _center_text(d, 'AI Worship Team Management', _font(48), height // 2 + 30, width, WHITE)
    _center_text(d, 'Planning Center integration · aria.church', _font(30), height // 2 + 110, width, (160, 160, 160))
    img.save(path)
    print(f'wrote {path} ({width}x{height})')

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    make(1200, 630, OUT / 'og-image.png')
    make(1200, 600, OUT / 'twitter-card.png')
```

- [ ] **Step 4: Run the script, then the test**

Run: `python3 scripts/generate_og_images.py && python3 -m pytest tests/test_seo.py::test_social_images_exist_with_correct_dimensions -v`
Expected: two PNGs written; test PASSES.

- [ ] **Step 5: Commit (include the generated PNGs)**

```bash
git add scripts/generate_og_images.py static/og-image.png static/twitter-card.png tests/test_seo.py
git commit -m "feat: generate og-image and twitter-card social-share images"
```

---

### Task 5: Seed two published blog posts

**Files:**
- Create: `blog/migrations/0002_seed_launch_blog_posts.py` (confirm next number with `ls blog/migrations`)
- Test: `tests/test_seo.py`

The blog is empty, so Google has almost nothing to index. Seed two posts targeting observed long-tail queries ("planning center ai", "ai church software") following the `core/migrations/0018` data-migration pattern.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_seo.py
@pytest.mark.django_db
def test_launch_blog_posts_published_and_listed(client):
    from blog.models import BlogPost
    slugs = ['ai-for-planning-center-worship-teams', 'best-ai-church-software-2026']
    for s in slugs:
        p = BlogPost.objects.get(slug=s)
        assert p.status == 'published'
        assert p.published_at is not None
    body = client.get('/blog/').content.decode()
    assert 'Planning Center' in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_seo.py::test_launch_blog_posts_published_and_listed -v`
Expected: FAIL — posts don't exist.

- [ ] **Step 3: First check how post content renders**

Run `grep -n "content" blog/templates -r 2>/dev/null; grep -rn "post.content\|markdownify\|linebreaks\|safe" blog/` and read `blog/views.py` post_detail + its template to see whether `content` is rendered raw, with `|linebreaks`, or via a markdown filter. Write the seed `content` to match (plain paragraphs separated by blank lines render correctly under both `|linebreaks` and markdown).

- [ ] **Step 4: Write the data migration**

Create `blog/migrations/0002_seed_launch_blog_posts.py` (set the dependency to the actual latest blog migration from `ls blog/migrations`):

```python
from django.db import migrations
from django.utils import timezone

POSTS = [
    {
        'slug': 'ai-for-planning-center-worship-teams',
        'title': 'How AI Helps Worship Teams Get More from Planning Center',
        'excerpt': 'Connect AI to Planning Center to answer questions about schedules, volunteers, blockouts, and songs in plain language.',
        'meta_title': 'AI for Planning Center: Worship Team Guide',
        'meta_description': 'See how AI connects to Planning Center to answer questions about your worship team’s schedules, volunteers, and songs instantly.',
        'focus_keyword': 'planning center ai',
        'content': (
            "Planning Center is where most worship teams keep their schedules, people, and songs. "
            "But finding a specific answer — who is serving Sunday, when a song was last played, who is "
            "blocked out — usually means clicking through several screens.\n\n"
            "An AI assistant that connects to Planning Center changes that. Instead of navigating menus, "
            "you ask a question in plain language and get the answer from your live PCO data.\n\n"
            "## What you can ask\n\n"
            "- Who is serving this Sunday, and what are their phone numbers?\n"
            "- When did we last play a given song, and what key was it in?\n"
            "- Who is blocked out on a specific date?\n\n"
            "## Why it matters\n\n"
            "Worship leaders spend hours each month on logistics. Answering these questions instantly frees "
            "that time for actually caring for the team. Aria connects to Planning Center and does exactly this. "
            "Start a free trial at aria.church."
        ),
    },
    {
        'slug': 'best-ai-church-software-2026',
        'title': 'The Best AI Church Software for Worship Teams in 2026',
        'excerpt': 'What to look for in AI church software — Planning Center integration, volunteer care, and instant answers.',
        'meta_title': 'Best AI Church Software for Worship Teams (2026)',
        'meta_description': 'A practical look at AI church software for worship teams in 2026: Planning Center integration, volunteer care, and instant answers.',
        'focus_keyword': 'ai church software',
        'content': (
            "“AI church software” covers a lot of tools. For worship teams specifically, the features that "
            "actually save time are narrower than the marketing suggests.\n\n"
            "## What to look for\n\n"
            "1. **Planning Center integration.** Your data already lives there; the software should read it, not "
            "duplicate it.\n"
            "2. **Plain-language answers.** Schedules, songs, blockouts, and contact info on demand.\n"
            "3. **Volunteer care.** Logging interactions and surfacing who needs follow-up.\n\n"
            "## Putting it together\n\n"
            "Aria was built around these three things for worship arts teams. It connects to Planning Center, "
            "answers questions instantly, and helps you track relationships with volunteers. Try it free at aria.church."
        ),
    },
]

def seed(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    now = timezone.now()
    for p in POSTS:
        BlogPost.objects.get_or_create(
            slug=p['slug'],
            defaults={**p, 'status': 'published', 'author_name': 'Aria Team', 'published_at': now},
        )

def unseed(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')
    BlogPost.objects.filter(slug__in=[p['slug'] for p in POSTS]).delete()

class Migration(migrations.Migration):
    dependencies = [
        ('blog', '0001_initial'),  # replace with the ACTUAL latest blog migration
    ]
    operations = [migrations.RunPython(seed, unseed)]
```

If Step 3 showed the template renders raw HTML (not markdown / not `|linebreaks`), convert the `##`/`-`/`1.` markdown in `content` to simple `<p>`/`<ul>` HTML instead so it renders cleanly.

- [ ] **Step 5: Run the migration + test**

Run: `python3 manage.py migrate blog && python3 -m pytest tests/test_seo.py::test_launch_blog_posts_published_and_listed -v`
Expected: migration applies; test PASSES.

- [ ] **Step 6: Commit**

```bash
git add blog/migrations/0002_seed_launch_blog_posts.py tests/test_seo.py
git commit -m "feat: seed two launch blog posts targeting PCO/AI church queries"
```

---

## Self-Review / Coverage

Spec workstream D → tasks: crawl-error handling + sitemap health (Task 1, with documented follow-up for the exact GSC URLs since they aren't in the export); PCO guide rescue (Task 2); brand targeting (Task 3); og-image + twitter-card (Task 4); two blog posts (Task 5). Sitemap re-submission in Search Console remains a manual user step (below).

## Final Verification

- [ ] `python3 -m pytest tests/ -q` → all pass.
- [ ] `python3 manage.py migrate` clean; `python3 manage.py makemigrations --check --dry-run` → "No changes detected".
- [ ] Manual: `/sitemap.xml` lists the new blog posts; `/og-image.png` and `/twitter-card.png` load; `/blog/` shows both posts; homepage `<title>` starts with "Aria".

## User Actions (cannot be automated)

1. After deploy, **re-submit the sitemap** in Google Search Console and use **URL Inspection → Request Indexing** on the homepage, pricing, PCO guide, and the two new blog posts.
2. Pull the exact **404** and **redirect** URLs from Search Console → Pages, so Task 1 Step 5 can fix/redirect them precisely.
3. Validate the PCO-guide and homepage structured data with Google's **Rich Results Test**.
