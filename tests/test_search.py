from django.utils.safestring import SafeString
from core.search import snippet


def test_snippet_highlights_match_case_insensitive():
    out = snippet("We moved the Easter set to G", "easter")
    assert '<mark>Easter</mark>' in out
    assert isinstance(out, SafeString)


def test_snippet_escapes_html():
    out = snippet("<script>alert(1)</script> easter", "easter")
    assert '<script>' not in out
    assert '&lt;script&gt;' in out
    assert '<mark>easter</mark>' in out


def test_snippet_windows_long_text():
    text = "x" * 500 + " easter " + "y" * 500
    out = snippet(text, "easter")
    assert 'easter' in out.lower()
    assert len(out) < 500
    assert '…' in out
