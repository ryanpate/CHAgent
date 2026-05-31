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
    assert 'alternateName' in body
