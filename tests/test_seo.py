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
