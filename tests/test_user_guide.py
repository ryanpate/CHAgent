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
