import re
import pytest

@pytest.mark.django_db
def test_every_sitemap_url_returns_200(client):
    xml = client.get('/sitemap.xml').content.decode()
    locs = re.findall(r'<loc>([^<]+)</loc>', xml)
    assert locs, "sitemap is empty"
    bad = []
    for url in locs:
        path = re.sub(r'^https?://[^/]+', '', url)
        resp = client.get(path)
        if resp.status_code != 200:
            bad.append((path, resp.status_code))
    assert not bad, f"sitemap URLs not returning 200: {bad}"

@pytest.mark.django_db
def test_category_sitemap_registered(client):
    from config.urls import sitemaps
    assert 'blog-categories' in sitemaps

@pytest.mark.django_db
def test_pco_guide_has_faq_and_compelling_title(client):
    body = client.get('/resources/planning-center-setup-guide/').content.decode()
    assert 'FAQPage' in body
    assert 'Frequently asked questions' in body or 'Frequently Asked Questions' in body
    assert '2026' in body


@pytest.mark.django_db
def test_pco_guide_title_is_ctr_optimized(client):
    """CTR fix: title must be keyword-first, carry the '6 Steps' number hook,
    and stay short enough to avoid SERP truncation (no double-brand suffix)."""
    import re
    body = client.get('/resources/planning-center-setup-guide/').content.decode()
    title = re.search(r'<title>(.*?)</title>', body, re.S).group(1).strip()
    assert title.startswith('Planning Center Setup Guide')
    assert '6 Steps' in title
    assert len(title) <= 60, f"title too long ({len(title)}): {title}"
    # internal links into the topic cluster (relevance + funnel)
    for link in ['/integrations/', '/blog/ai-for-planning-center-worship-teams/', '/signup/']:
        assert link in body

@pytest.mark.django_db
def test_homepage_targets_brand(client):
    import re
    body = client.get('/').content.decode()
    title = re.search(r'<title>(.*?)</title>', body, re.S).group(1)
    assert title.strip().startswith('Aria')
    assert 'ARIA - AI Worship Team Management' not in title
    assert 'alternateName' in body
    import re as _re
    assert _re.search(r'<h1[^>]*>.*Aria.*</h1>', body, _re.S), "homepage H1 should contain the brand"

@pytest.mark.django_db
def test_homepage_has_no_single_aggregate_rating(client):
    body = client.get('/').content.decode()
    assert 'aggregateRating' not in body

@pytest.mark.django_db
def test_pco_faq_jsonld_answers_match_visible(client):
    body = client.get('/resources/planning-center-setup-guide/').content.decode()
    # both the distinctive visible phrase and the same phrase in JSON-LD should be present
    assert body.count('service types, teams, and people') >= 2  # visible + json-ld
    assert body.count('Start a free trial at aria.church') >= 1  # json-ld plain-text version


@pytest.mark.django_db
def test_public_pages_link_to_orphan_pages(client):
    """Every public page (via base_public footer/header) must link to blog and
    resources so Google has a crawl path — these were 'discovered, not indexed'."""
    body = client.get('/').content.decode()
    for link in [
        '/pricing/',
        '/resources/',
        '/blog/',
        '/resources/planning-center-setup-guide/',
        '/blog/ai-for-planning-center-worship-teams/',
        '/blog/best-ai-church-software-2026/',
    ]:
        assert link in body, f"public footer/header should link to {link}"


@pytest.mark.django_db
def test_www_host_redirects_to_apex(client):
    """www.aria.church 404'd in Search Console; it must 301 to the apex host."""
    resp = client.get('/pricing/', HTTP_HOST='www.aria.church', secure=True)
    assert resp.status_code == 301
    assert resp.headers['Location'] == 'https://aria.church/pricing/'


@pytest.mark.django_db
def test_apex_host_not_redirected(client):
    """The canonical apex host must serve directly with no redirect loop."""
    resp = client.get('/pricing/', HTTP_HOST='aria.church', secure=True)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_www_over_http_redirects_to_https_apex_in_one_hop(client):
    """GSC flagged a 2-hop http-www -> https-www -> apex chain. WwwRedirect runs
    before SecurityMiddleware so http://www collapses straight to https apex."""
    resp = client.get('/pricing/', HTTP_HOST='www.aria.church', secure=False)
    assert resp.status_code == 301
    assert resp.headers['Location'] == 'https://aria.church/pricing/'


@pytest.mark.django_db
def test_public_page_titles_are_single_brand_and_not_truncated(client):
    """GSC: several titles double-branded ('... | Aria | ARIA - AI Worship...')
    and exceeded ~60 chars, hurting CTR. Each public <title> must contain the
    brand once and stay within a sane length."""
    import re
    pages = ['/', '/pricing/', '/security/', '/privacy/', '/integrations/',
             '/resources/', '/resources/worship-schedule-template/',
             '/resources/volunteer-application-template/',
             '/resources/planning-center-setup-guide/', '/blog/']
    for p in pages:
        body = client.get(p).content.decode()
        title = re.search(r'<title>(.*?)</title>', body, re.S).group(1).strip()
        # Brand must never appear twice (the double-brand bug). Exactly one is
        # the norm; the PCO setup guide is a deliberate brandless CTR exception.
        assert title.lower().count('aria') <= 1, f"{p}: double-brand title: {title!r}"
        assert len(title) <= 65, f"{p}: title too long ({len(title)}): {title!r}"


@pytest.mark.django_db
def test_integrations_page_targets_planning_center(client):
    """The integrations page anchors the Planning Center partner listing and
    targets 'planning center integration' — one H1, real content, breadcrumb."""
    resp = client.get('/integrations/')
    assert resp.status_code == 200
    body = resp.content.decode()
    assert body.count('<h1') == 1
    assert 'Planning Center' in body
    assert '"@type": "BreadcrumbList"' in body
    # crawl path to the conversion + supporting pages
    for link in ['/signup/', '/pricing/', '/resources/planning-center-setup-guide/']:
        assert link in body


@pytest.mark.django_db
def test_signup_page_has_indexable_content_and_single_h1(client):
    """/signup/ was thin (~118 words); it needs real content to get indexed,
    and exactly one H1 for clean on-page SEO. The form must remain intact."""
    body = client.get('/signup/').content.decode()
    assert body.count('<h1') == 1
    assert 'What you get' in body and 'Frequently asked questions' in body
    # form still present and complete
    assert '<form method="post"' in body
    for field in ['first_name', 'name="email"', 'name="password"', 'church_name', 'name="plan"']:
        assert field in body, f"signup form missing {field}"
