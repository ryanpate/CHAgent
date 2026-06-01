import pytest
from django.urls import reverse

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

@pytest.mark.django_db
def test_launch_blog_post_detail_renders(client):
    resp = client.get('/blog/ai-for-planning-center-worship-teams/')
    assert resp.status_code == 200
