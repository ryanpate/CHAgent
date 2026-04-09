"""Seed the user guide into an organization's Knowledge Base."""
import json
import logging

from django.core.files.base import ContentFile

from .guide_content import GUIDE_SECTIONS, GUIDE_GROUPS
from .models import Document, DocumentCategory

logger = logging.getLogger(__name__)

GUIDE_TITLE = 'Getting Started with ARIA'
GUIDE_CATEGORY = 'Help & Guides'


def _build_plain_text():
    """Concatenate all sections' plain_text into a single document."""
    parts = []
    for group in GUIDE_GROUPS:
        group_sections = [s for s in GUIDE_SECTIONS if s['group'] == group['id']]
        if group_sections:
            parts.append(f"{'=' * 60}")
            parts.append(group['title'].upper())
            parts.append(f"{'=' * 60}\n")
            for section in group_sections:
                parts.append(section['plain_text'].strip())
                parts.append('')
    return '\n'.join(parts)


def seed_guide_document(organization):
    """
    Create or skip the Getting Started guide in an org's Knowledge Base.
    Idempotent: skips if a document with the guide title already exists.
    """
    if Document.objects.filter(
        organization=organization, title=GUIDE_TITLE
    ).exists():
        logger.info(f"Guide already exists for {organization.name}, skipping")
        return None

    category, _ = DocumentCategory.objects.get_or_create(
        organization=organization,
        name=GUIDE_CATEGORY,
        defaults={'description': 'Help documentation and user guides'},
    )

    plain_text = _build_plain_text()

    doc = Document(
        organization=organization,
        title=GUIDE_TITLE,
        description='Comprehensive guide to all ARIA features for new and existing users.',
        category=category,
        file_type='txt',
        extracted_text=plain_text,
        is_processed=True,
        page_count=1,
    )
    doc.file.save(
        'getting-started-with-aria.txt',
        ContentFile(plain_text.encode('utf-8')),
        save=False,
    )
    doc.save()

    from .document_processing import chunk_text
    from .models import DocumentChunk
    from .embeddings import get_embedding

    chunks = chunk_text(plain_text)
    for chunk_data in chunks:
        embedding = get_embedding(chunk_data['content'])
        DocumentChunk.objects.create(
            document=doc,
            organization=organization,
            chunk_index=chunk_data['chunk_index'],
            content=chunk_data['content'],
            embedding_json=json.dumps(embedding) if embedding else None,
        )

    logger.info(f"Seeded guide for {organization.name}: {len(chunks)} chunks")
    return doc
