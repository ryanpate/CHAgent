import re
from django.utils.html import escape
from django.utils.safestring import mark_safe


def snippet(text, query, width=160):
    """Return an HTML-safe excerpt around the first match, with the query <mark>ed.

    Escapes the source text first, then highlights, so user content cannot inject markup.
    """
    if not text:
        return mark_safe('')
    lower = text.lower()
    idx = lower.find(query.lower())
    if idx == -1:
        excerpt = text[:width]
        prefix, suffix = '', ('…' if len(text) > width else '')
    else:
        start = max(0, idx - width // 3)
        end = min(len(text), idx + len(query) + width)
        excerpt = text[start:end]
        prefix = '…' if start > 0 else ''
        suffix = '…' if end < len(text) else ''
    escaped = escape(excerpt)
    pattern = re.escape(escape(query))
    highlighted = re.sub(f'({pattern})', r'<mark>\1</mark>', escaped, flags=re.IGNORECASE)
    return mark_safe(prefix + highlighted + suffix)
