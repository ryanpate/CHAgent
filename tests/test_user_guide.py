import pytest
from core.guide_content import GUIDE_SECTIONS, GUIDE_GROUPS


class TestGuideContent:
    def test_guide_sections_exist(self):
        assert len(GUIDE_SECTIONS) >= 21

    def test_guide_groups_exist(self):
        assert len(GUIDE_GROUPS) == 3
        group_ids = [g['id'] for g in GUIDE_GROUPS]
        assert 'getting-started' in group_ids
        assert 'features' in group_ids
        assert 'admin' in group_ids

    def test_each_section_has_required_fields(self):
        for section in GUIDE_SECTIONS:
            assert 'id' in section, f"Section missing 'id': {section.get('title', 'unknown')}"
            assert 'title' in section
            assert 'content' in section
            assert 'plain_text' in section
            assert 'is_admin' in section
            assert 'group' in section

    def test_each_section_group_is_valid(self):
        valid_groups = {g['id'] for g in GUIDE_GROUPS}
        for section in GUIDE_SECTIONS:
            assert section['group'] in valid_groups, f"Section '{section['title']}' has invalid group '{section['group']}'"

    def test_admin_sections_flagged(self):
        admin_sections = [s for s in GUIDE_SECTIONS if s['is_admin']]
        assert len(admin_sections) >= 5
        admin_titles = [s['title'] for s in admin_sections]
        assert any('Settings' in t or 'Members' in t or 'Billing' in t or 'Security' in t or 'Planning Center' in t for t in admin_titles)

    def test_content_not_empty(self):
        for section in GUIDE_SECTIONS:
            assert len(section['content']) > 50, f"Section '{section['title']}' content too short"
            assert len(section['plain_text']) > 50, f"Section '{section['title']}' plain_text too short"

    def test_section_ids_unique(self):
        ids = [s['id'] for s in GUIDE_SECTIONS]
        assert len(ids) == len(set(ids)), "Duplicate section IDs found"


from django.test import Client


class TestGuideView:
    @pytest.fixture
    def client_alpha(self, db, user_alpha_owner, org_alpha):
        client = Client()
        client.force_login(user_alpha_owner)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    @pytest.fixture
    def member_client(self, db, user_alpha_member, org_alpha):
        client = Client()
        client.force_login(user_alpha_member)
        session = client.session
        session['organization_id'] = org_alpha.id
        session.save()
        return client

    def test_guide_renders(self, client_alpha):
        response = client_alpha.get('/guide/')
        assert response.status_code == 200
        assert 'User Guide' in response.content.decode()

    def test_guide_shows_all_feature_sections(self, client_alpha):
        response = client_alpha.get('/guide/')
        content = response.content.decode()
        assert 'Welcome to ARIA' in content
        assert 'Chatting with Aria' in content
        assert 'Creative Studio' in content
        assert 'Knowledge Base' in content
        assert 'Notifications' in content

    def test_guide_admin_sections_visible_for_owner(self, client_alpha):
        response = client_alpha.get('/guide/')
        content = response.content.decode()
        assert 'Organization Settings' in content
        assert 'Managing Members' in content
        assert 'Billing' in content

    def test_guide_admin_sections_hidden_for_member(self, member_client):
        response = member_client.get('/guide/')
        content = response.content.decode()
        assert 'Organization Settings' not in content
        assert 'Managing Members' not in content
        assert 'Billing' not in content

    def test_guide_requires_login(self, db):
        client = Client()
        response = client.get('/guide/')
        assert response.status_code == 302
        assert '/accounts/login/' in response.url


from core.models import Document, DocumentCategory, DocumentChunk


class TestGuideSeeder:
    def test_seed_creates_category(self, db, org_alpha):
        from core.guide_seeder import seed_guide_document
        seed_guide_document(org_alpha)
        assert DocumentCategory.objects.filter(
            organization=org_alpha, name='Help & Guides'
        ).exists()

    def test_seed_creates_document(self, db, org_alpha):
        from core.guide_seeder import seed_guide_document
        seed_guide_document(org_alpha)
        doc = Document.objects.filter(
            organization=org_alpha, title='Getting Started with ARIA'
        ).first()
        assert doc is not None
        assert doc.file_type == 'txt'
        assert len(doc.extracted_text) > 500

    def test_seed_is_idempotent(self, db, org_alpha):
        from core.guide_seeder import seed_guide_document
        seed_guide_document(org_alpha)
        seed_guide_document(org_alpha)
        assert Document.objects.filter(
            organization=org_alpha, title='Getting Started with ARIA'
        ).count() == 1

    def test_seed_creates_chunks(self, db, org_alpha):
        from core.guide_seeder import seed_guide_document
        seed_guide_document(org_alpha)
        doc = Document.objects.get(
            organization=org_alpha, title='Getting Started with ARIA'
        )
        assert DocumentChunk.objects.filter(document=doc).count() > 0
