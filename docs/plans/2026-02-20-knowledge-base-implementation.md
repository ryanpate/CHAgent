# Knowledge Base Document Upload - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow organizations to upload PDF/text documents that Aria can search and cite when answering questions.

**Architecture:** New Django models (DocumentCategory, Document, DocumentChunk) with text extraction via pypdf, chunked embedding via OpenAI text-embedding-3-small, and integration into the existing RAG pipeline in query_agent(). Documents served through Django views for org-scoped access control.

**Tech Stack:** Django 5.x, pypdf (already installed), OpenAI embeddings (already integrated), HTMX + Tailwind (existing frontend stack)

---

### Task 1: Add MEDIA settings to config/settings.py

**Files:**
- Modify: `config/settings.py:186-196`
- Modify: `config/urls.py` (add media URL serving for dev)

**Step 1: Add MEDIA_ROOT and MEDIA_URL to settings**

In `config/settings.py`, after the STATICFILES_DIRS block (line 186), add:

```python
# Media files (user-uploaded content)
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'

# File upload limits (10 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
```

**Step 2: Add media URL serving in dev mode**

In `config/urls.py`, add at the bottom:

```python
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

**Step 3: Add media/ to .gitignore**

Add `media/` to `.gitignore` if not already present.

**Step 4: Verify settings load**

Run: `python manage.py check`
Expected: System check identified no issues.

**Step 5: Commit**

```bash
git add config/settings.py config/urls.py .gitignore
git commit -m "feat: add MEDIA settings for document uploads"
```

---

### Task 2: Create DocumentCategory, Document, and DocumentChunk models

**Files:**
- Modify: `core/models.py` (append after TOTPDevice class, ~line 3419)
- Test: `tests/test_documents.py` (new file)

**Step 1: Write the failing tests**

Create `tests/test_documents.py`:

```python
"""Tests for the Knowledge Base document upload feature."""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import DocumentCategory, Document, DocumentChunk


@pytest.mark.django_db
class TestDocumentCategoryModel:
    def test_create_category(self, org_alpha, user_alpha_owner):
        cat = DocumentCategory.objects.create(
            name='Sound',
            slug='sound',
            organization=org_alpha,
            created_by=user_alpha_owner,
        )
        assert cat.name == 'Sound'
        assert cat.slug == 'sound'
        assert cat.organization == org_alpha
        assert str(cat) == 'Sound'

    def test_unique_slug_per_org(self, org_alpha, org_beta, user_alpha_owner, user_beta_owner):
        DocumentCategory.objects.create(
            name='Sound', slug='sound',
            organization=org_alpha, created_by=user_alpha_owner,
        )
        # Same slug in different org should work
        cat2 = DocumentCategory.objects.create(
            name='Sound', slug='sound',
            organization=org_beta, created_by=user_beta_owner,
        )
        assert cat2.pk is not None

    def test_duplicate_slug_same_org_fails(self, org_alpha, user_alpha_owner):
        DocumentCategory.objects.create(
            name='Sound', slug='sound',
            organization=org_alpha, created_by=user_alpha_owner,
        )
        with pytest.raises(Exception):
            DocumentCategory.objects.create(
                name='Sound 2', slug='sound',
                organization=org_alpha, created_by=user_alpha_owner,
            )


@pytest.mark.django_db
class TestDocumentModel:
    def test_create_document(self, org_alpha, user_alpha_owner):
        fake_file = SimpleUploadedFile('test.txt', b'Hello world', content_type='text/plain')
        doc = Document.objects.create(
            title='Sound Board Guide',
            description='How to set up the sound board',
            file=fake_file,
            organization=org_alpha,
            uploaded_by=user_alpha_owner,
            file_type='txt',
            file_size=11,
        )
        assert doc.title == 'Sound Board Guide'
        assert doc.is_processed is False
        assert str(doc) == 'Sound Board Guide'

    def test_document_with_category(self, org_alpha, user_alpha_owner):
        cat = DocumentCategory.objects.create(
            name='Sound', slug='sound',
            organization=org_alpha, created_by=user_alpha_owner,
        )
        fake_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        doc = Document.objects.create(
            title='Guide', file=fake_file,
            category=cat, organization=org_alpha,
            uploaded_by=user_alpha_owner, file_type='txt', file_size=7,
        )
        assert doc.category == cat


@pytest.mark.django_db
class TestDocumentChunkModel:
    def test_create_chunk(self, org_alpha, user_alpha_owner):
        fake_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        doc = Document.objects.create(
            title='Guide', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='txt', file_size=7,
        )
        chunk = DocumentChunk.objects.create(
            document=doc,
            chunk_index=0,
            content='This is the first chunk of text.',
            organization=org_alpha,
        )
        assert chunk.chunk_index == 0
        assert chunk.document == doc
        assert str(chunk) == 'Guide - Chunk 0'

    def test_chunks_deleted_with_document(self, org_alpha, user_alpha_owner):
        fake_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        doc = Document.objects.create(
            title='Guide', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='txt', file_size=7,
        )
        DocumentChunk.objects.create(
            document=doc, chunk_index=0,
            content='Chunk 1', organization=org_alpha,
        )
        DocumentChunk.objects.create(
            document=doc, chunk_index=1,
            content='Chunk 2', organization=org_alpha,
        )
        assert DocumentChunk.objects.filter(document=doc).count() == 2
        doc.delete()
        assert DocumentChunk.objects.count() == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_documents.py -v`
Expected: FAIL with ImportError (models don't exist yet)

**Step 3: Write the models**

Append to `core/models.py` after the TOTPDevice class (after line 3419):

```python


# =============================================================================
# Knowledge Base - Document Upload & Search
# =============================================================================

class DocumentCategory(models.Model):
    """Organizes uploaded documents into categories per organization."""
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='document_categories'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['organization', 'slug']
        ordering = ['name']
        verbose_name_plural = 'document categories'

    def __str__(self):
        return self.name


class Document(models.Model):
    """An uploaded document that Aria can reference when answering questions."""
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('txt', 'Plain Text'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/')
    category = models.ForeignKey(
        DocumentCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='documents'
    )
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='documents'
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True
    )
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    file_size = models.IntegerField(default=0)
    page_count = models.IntegerField(default=0)
    extracted_text = models.TextField(blank=True)
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class DocumentChunk(models.Model):
    """A chunk of document text with its embedding for semantic search."""
    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='chunks'
    )
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding_json = models.JSONField(null=True, blank=True)
    page_number = models.IntegerField(null=True, blank=True)
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='document_chunks'
    )

    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']

    def __str__(self):
        return f'{self.document.title} - Chunk {self.chunk_index}'
```

**Step 4: Create and run migration**

Run: `python manage.py makemigrations core`
Run: `python manage.py migrate`

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_documents.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_documents.py
git commit -m "feat: add DocumentCategory, Document, DocumentChunk models"
```

---

### Task 3: Create document processing module

**Files:**
- Create: `core/document_processing.py`
- Test: `tests/test_documents.py` (add processing tests)

**Step 1: Write the failing tests**

Add to `tests/test_documents.py`:

```python
from core.document_processing import extract_text_from_file, chunk_text


class TestTextExtraction:
    def test_extract_text_from_txt(self, tmp_path):
        txt_file = tmp_path / 'test.txt'
        txt_file.write_text('Hello world. This is a test document.')
        with open(txt_file, 'rb') as f:
            text, page_count = extract_text_from_file(f, 'txt')
        assert text == 'Hello world. This is a test document.'
        assert page_count == 1

    def test_extract_text_from_pdf(self, tmp_path):
        """Test PDF extraction with a minimal valid PDF."""
        # Create a minimal PDF using pypdf
        from pypdf import PdfWriter
        from io import BytesIO

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        # pypdf blank pages have no text, so we test the extraction runs without error
        buf = BytesIO()
        writer.write(buf)
        buf.seek(0)
        text, page_count = extract_text_from_file(buf, 'pdf')
        assert page_count == 1
        assert isinstance(text, str)


class TestChunking:
    def test_chunk_short_text(self):
        text = 'This is a short document.'
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0]['content'] == text
        assert chunks[0]['chunk_index'] == 0

    def test_chunk_long_text(self):
        # Create text that's longer than chunk_size
        sentences = [f'Sentence number {i} is here.' for i in range(100)]
        text = ' '.join(sentences)
        chunks = chunk_text(text, chunk_size=200, overlap=30)
        assert len(chunks) > 1
        # All chunks should have content
        for chunk in chunks:
            assert len(chunk['content']) > 0
            assert 'chunk_index' in chunk

    def test_chunk_preserves_all_content(self):
        sentences = [f'Sentence {i}.' for i in range(50)]
        text = ' '.join(sentences)
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        # Every sentence should appear in at least one chunk
        for sentence in sentences:
            found = any(sentence in c['content'] for c in chunks)
            assert found, f'{sentence} not found in any chunk'

    def test_chunk_empty_text(self):
        chunks = chunk_text('', chunk_size=500, overlap=50)
        assert len(chunks) == 0
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_documents.py::TestTextExtraction -v`
Expected: FAIL with ImportError

**Step 3: Write the implementation**

Create `core/document_processing.py`:

```python
"""
Document processing module for the Knowledge Base feature.
Handles text extraction from uploaded files and chunking for embedding.
"""
import logging
from io import BytesIO
from typing import BinaryIO

logger = logging.getLogger(__name__)


def extract_text_from_file(file_obj: BinaryIO, file_type: str) -> tuple[str, int]:
    """
    Extract text content from an uploaded file.

    Args:
        file_obj: File-like object to read from.
        file_type: 'pdf' or 'txt'.

    Returns:
        Tuple of (extracted_text, page_count).
    """
    if file_type == 'txt':
        return _extract_text_from_txt(file_obj)
    elif file_type == 'pdf':
        return _extract_text_from_pdf(file_obj)
    else:
        raise ValueError(f'Unsupported file type: {file_type}')


def _extract_text_from_txt(file_obj: BinaryIO) -> tuple[str, int]:
    """Extract text from a plain text file."""
    raw = file_obj.read()
    if isinstance(raw, bytes):
        text = raw.decode('utf-8', errors='replace')
    else:
        text = raw
    return text.strip(), 1


def _extract_text_from_pdf(file_obj: BinaryIO) -> tuple[str, int]:
    """Extract text from a PDF file using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(file_obj)
    page_count = len(reader.pages)
    pages_text = []
    for page in reader.pages:
        page_text = page.extract_text() or ''
        pages_text.append(page_text)
    full_text = '\n\n'.join(pages_text).strip()
    return full_text, page_count


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """
    Split text into overlapping chunks for embedding.

    Tries to split on sentence boundaries. Each chunk is roughly chunk_size
    characters with overlap characters of overlap between consecutive chunks.

    Args:
        text: The full text to chunk.
        chunk_size: Target size of each chunk in characters.
        overlap: Number of characters to overlap between chunks.

    Returns:
        List of dicts with 'content' and 'chunk_index' keys.
    """
    if not text or not text.strip():
        return []

    text = text.strip()

    # If text fits in one chunk, return it
    if len(text) <= chunk_size:
        return [{'content': text, 'chunk_index': 0}]

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size

        # If this isn't the last chunk, try to break at a sentence boundary
        if end < len(text):
            # Look for sentence-ending punctuation near the end
            search_start = max(start + chunk_size // 2, start)
            best_break = end
            for i in range(min(end, len(text) - 1), search_start, -1):
                if text[i] in '.!?\n' and (i + 1 >= len(text) or text[i + 1] in ' \n\t'):
                    best_break = i + 1
                    break
            end = best_break

        chunk_content = text[start:end].strip()
        if chunk_content:
            chunks.append({
                'content': chunk_content,
                'chunk_index': chunk_index,
            })
            chunk_index += 1

        # Move start forward, accounting for overlap
        start = end - overlap if end < len(text) else len(text)

    return chunks


def process_document(document) -> None:
    """
    Full processing pipeline for an uploaded document:
    1. Extract text
    2. Chunk text
    3. Generate embeddings for each chunk
    4. Save chunks to database

    Args:
        document: A Document model instance.
    """
    from .models import DocumentChunk
    from .embeddings import get_embedding

    try:
        # Step 1: Extract text
        document.file.seek(0)
        extracted_text, page_count = extract_text_from_file(
            document.file, document.file_type
        )
        document.extracted_text = extracted_text
        document.page_count = page_count

        if not extracted_text.strip():
            document.processing_error = 'No text could be extracted from this file.'
            document.is_processed = True
            document.save()
            return

        # Step 2: Chunk text
        chunks = chunk_text(extracted_text)

        # Step 3: Generate embeddings and save chunks
        # Delete any existing chunks (in case of reprocessing)
        DocumentChunk.objects.filter(document=document).delete()

        for chunk_data in chunks:
            embedding = get_embedding(chunk_data['content'])
            DocumentChunk.objects.create(
                document=document,
                chunk_index=chunk_data['chunk_index'],
                content=chunk_data['content'],
                embedding_json=embedding,
                organization=document.organization,
            )

        document.is_processed = True
        document.processing_error = ''
        document.save()

        logger.info(
            f'Processed document "{document.title}": '
            f'{len(chunks)} chunks, {page_count} pages'
        )

    except Exception as e:
        logger.error(f'Error processing document "{document.title}": {e}')
        document.processing_error = str(e)
        document.is_processed = False
        document.save()
        raise
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_documents.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add core/document_processing.py tests/test_documents.py
git commit -m "feat: add document text extraction and chunking module"
```

---

### Task 4: Add document search to embeddings.py

**Files:**
- Modify: `core/embeddings.py` (add search_similar_documents function)
- Test: `tests/test_documents.py` (add search tests)

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
from unittest.mock import patch
from core.embeddings import search_similar_documents


@pytest.mark.django_db
class TestDocumentSearch:
    def test_search_returns_empty_for_no_chunks(self, org_alpha):
        results = search_similar_documents([0.1] * 10, org_alpha, limit=5)
        assert results == []

    def test_search_scoped_to_organization(self, org_alpha, org_beta, user_alpha_owner, user_beta_owner):
        """Documents from org_beta should not appear in org_alpha search."""
        fake_file_a = SimpleUploadedFile('a.txt', b'content', content_type='text/plain')
        doc_a = Document.objects.create(
            title='Alpha Doc', file=fake_file_a,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='txt', file_size=7, is_processed=True,
        )
        DocumentChunk.objects.create(
            document=doc_a, chunk_index=0, content='Alpha content',
            embedding_json=[0.1] * 10, organization=org_alpha,
        )

        fake_file_b = SimpleUploadedFile('b.txt', b'content', content_type='text/plain')
        doc_b = Document.objects.create(
            title='Beta Doc', file=fake_file_b,
            organization=org_beta, uploaded_by=user_beta_owner,
            file_type='txt', file_size=7, is_processed=True,
        )
        DocumentChunk.objects.create(
            document=doc_b, chunk_index=0, content='Beta content',
            embedding_json=[0.1] * 10, organization=org_beta,
        )

        results = search_similar_documents([0.1] * 10, org_alpha, limit=5)
        doc_titles = [r['document_title'] for r in results]
        assert 'Alpha Doc' in doc_titles
        assert 'Beta Doc' not in doc_titles
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_documents.py::TestDocumentSearch -v`
Expected: FAIL with ImportError

**Step 3: Add search_similar_documents to embeddings.py**

Append to `core/embeddings.py`:

```python


def search_similar_documents(query_embedding: list[float], organization, limit: int = 5, threshold: float = 0.3) -> list[dict]:
    """
    Find document chunks most similar to query, scoped to organization.

    Args:
        query_embedding: The embedding vector to search against.
        organization: Organization instance to scope the search.
        limit: Maximum number of results to return.
        threshold: Minimum cosine similarity score to include.

    Returns:
        List of dicts with 'content', 'document_title', 'document_id',
        'category_name', 'similarity', and 'chunk_index'.
    """
    from .models import DocumentChunk
    import math

    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    chunks = DocumentChunk.objects.filter(
        organization=organization,
        embedding_json__isnull=False,
        document__is_processed=True,
    ).select_related('document', 'document__category')

    scored = []
    for chunk in chunks:
        similarity = cosine_similarity(query_embedding, chunk.embedding_json)
        if similarity >= threshold:
            scored.append({
                'content': chunk.content,
                'document_title': chunk.document.title,
                'document_id': chunk.document.id,
                'category_name': chunk.document.category.name if chunk.document.category else '',
                'similarity': similarity,
                'chunk_index': chunk.chunk_index,
            })

    scored.sort(key=lambda x: x['similarity'], reverse=True)
    return scored[:limit]
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_documents.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add core/embeddings.py tests/test_documents.py
git commit -m "feat: add document chunk semantic search"
```

---

### Task 5: Integrate document search into query_agent()

**Files:**
- Modify: `core/agent.py:2106-2173` (update system prompt)
- Modify: `core/agent.py:4228-4346` (add document search to RAG pipeline)

**Step 1: Update the system prompt**

In `core/agent.py`, in `get_system_prompt()` (line 2106), add a new capability to the list (after item 5):

```
6. Reference uploaded Knowledge Base documents to answer procedural and reference questions
```

And add to the Guidelines section (after the chord chart guideline around line 2142):

```
- When answering from uploaded Knowledge Base documents, always cite the document title. Example: 'According to the Sound Board Setup Guide, the first step is...'
- Only use document content that is directly relevant to the user's question.
```

**Step 2: Add document search to the RAG pipeline**

In `core/agent.py`, after the PCO/song/blockout context is added (around line 4346), add document search:

```python
    # Add Knowledge Base document context if available
    if organization and question_embedding:
        try:
            from .embeddings import search_similar_documents
            doc_results = search_similar_documents(
                question_embedding, organization, limit=5, threshold=0.3
            )
            if doc_results:
                doc_context_parts = []
                seen_docs = set()
                for result in doc_results:
                    doc_key = (result['document_id'], result['chunk_index'])
                    if doc_key not in seen_docs:
                        seen_docs.add(doc_key)
                        cat_label = f" ({result['category_name']})" if result['category_name'] else ""
                        doc_context_parts.append(
                            f'From "{result["document_title"]}"{cat_label}:\n'
                            f'{result["content"]}'
                        )
                if doc_context_parts:
                    doc_context = (
                        "\n[KNOWLEDGE BASE DOCUMENTS]\n"
                        + "\n\n---\n\n".join(doc_context_parts)
                    )
                    context = doc_context + "\n\n" + context
                    logger.info(f"Added {len(doc_context_parts)} document chunks to context")
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
```

Note: `question_embedding` is already computed at line 4229. For aggregate queries where it's not computed, document search is skipped (aggregate queries are about volunteer data, not documents).

**Step 3: Ensure question_embedding is accessible**

The variable `question_embedding` is currently defined inside an `else` block (line 4229). We need to ensure it's initialized before the block so it's accessible later. Add before the aggregate check (around line 4190):

```python
    question_embedding = None
```

And keep the existing assignment at line 4229 as-is.

**Step 4: Run the full test suite**

Run: `pytest --tb=short`
Expected: All existing tests still pass (no regressions).

**Step 5: Commit**

```bash
git add core/agent.py
git commit -m "feat: integrate document search into Aria RAG pipeline"
```

---

### Task 6: Create document views

**Files:**
- Modify: `core/views.py` (add document views)
- Modify: `core/urls.py` (add document URL routes)
- Test: `tests/test_documents.py` (add view tests)

**Step 1: Write the failing view tests**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestDocumentViews:
    def test_document_list_requires_login(self):
        client = Client()
        response = client.get('/documents/')
        assert response.status_code == 302  # Redirect to login

    def test_document_list_accessible(self, client_alpha):
        response = client_alpha.get('/documents/')
        assert response.status_code == 200
        assert b'Knowledge Base' in response.content

    def test_upload_requires_admin(self, client_alpha, org_alpha, user_alpha_member):
        """Regular members cannot upload documents."""
        member_client = Client()
        member_client.force_login(user_alpha_member)
        session = member_client.session
        session['organization_id'] = org_alpha.id
        session.save()

        response = member_client.get('/documents/upload/')
        assert response.status_code == 403

    def test_upload_page_accessible_for_owner(self, client_alpha):
        response = client_alpha.get('/documents/upload/')
        assert response.status_code == 200

    def test_upload_txt_document(self, client_alpha, org_alpha):
        fake_file = SimpleUploadedFile(
            'guide.txt', b'How to turn on the sound board: Step 1...',
            content_type='text/plain'
        )
        response = client_alpha.post('/documents/upload/', {
            'title': 'Sound Board Guide',
            'description': 'How to set up the sound board',
            'file': fake_file,
        })
        assert response.status_code == 302  # Redirect to document detail
        assert Document.objects.filter(organization=org_alpha, title='Sound Board Guide').exists()

    def test_document_detail(self, client_alpha, org_alpha, user_alpha_owner):
        fake_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        doc = Document.objects.create(
            title='Test Doc', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='txt', file_size=7, is_processed=True,
        )
        response = client_alpha.get(f'/documents/{doc.pk}/')
        assert response.status_code == 200
        assert b'Test Doc' in response.content

    def test_document_isolation(self, client_alpha, org_beta, user_beta_owner):
        """Alpha client cannot see Beta's documents."""
        fake_file = SimpleUploadedFile('beta.txt', b'secret', content_type='text/plain')
        doc = Document.objects.create(
            title='Beta Secret', file=fake_file,
            organization=org_beta, uploaded_by=user_beta_owner,
            file_type='txt', file_size=6, is_processed=True,
        )
        response = client_alpha.get(f'/documents/{doc.pk}/')
        assert response.status_code == 404

    def test_delete_document(self, client_alpha, org_alpha, user_alpha_owner):
        fake_file = SimpleUploadedFile('test.txt', b'content', content_type='text/plain')
        doc = Document.objects.create(
            title='To Delete', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='txt', file_size=7,
        )
        response = client_alpha.post(f'/documents/{doc.pk}/delete/')
        assert response.status_code == 302
        assert not Document.objects.filter(pk=doc.pk).exists()

    def test_download_document(self, client_alpha, org_alpha, user_alpha_owner):
        fake_file = SimpleUploadedFile('test.txt', b'file content here', content_type='text/plain')
        doc = Document.objects.create(
            title='Downloadable', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='txt', file_size=17,
        )
        response = client_alpha.get(f'/documents/{doc.pk}/download/')
        assert response.status_code == 200
        assert response['Content-Type'] in ('text/plain', 'application/octet-stream')
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_documents.py::TestDocumentViews -v`
Expected: FAIL (views and URLs don't exist yet)

**Step 3: Add URL routes to core/urls.py**

Add after the My Tasks route (line 89) in `core/urls.py`:

```python
    # Knowledge Base Documents
    path('documents/', views.document_list, name='document_list'),
    path('documents/upload/', views.document_upload, name='document_upload'),
    path('documents/categories/', views.document_category_list, name='document_category_list'),
    path('documents/categories/create/', views.document_category_create, name='document_category_create'),
    path('documents/categories/<int:pk>/edit/', views.document_category_edit, name='document_category_edit'),
    path('documents/categories/<int:pk>/delete/', views.document_category_delete, name='document_category_delete'),
    path('documents/<int:pk>/', views.document_detail, name='document_detail'),
    path('documents/<int:pk>/edit/', views.document_edit, name='document_edit'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('documents/<int:pk>/download/', views.document_download, name='document_download'),
```

**Step 4: Add views to core/views.py**

Add these views to `core/views.py`. Use the existing patterns from the codebase - `@login_required`, `@require_organization`, and `@require_role` decorators from `core/middleware.py`.

```python
@login_required
@require_organization
def document_list(request):
    """List all documents in the organization's knowledge base."""
    from .models import Document, DocumentCategory

    category_slug = request.GET.get('category', '')
    search_query = request.GET.get('q', '')

    documents = Document.objects.filter(organization=request.organization)
    categories = DocumentCategory.objects.filter(organization=request.organization)

    if category_slug:
        documents = documents.filter(category__slug=category_slug)
    if search_query:
        documents = documents.filter(
            models.Q(title__icontains=search_query) |
            models.Q(description__icontains=search_query)
        )

    is_admin = request.membership.role in ('owner', 'admin')
    return render(request, 'core/documents/document_list.html', {
        'documents': documents,
        'categories': categories,
        'selected_category': category_slug,
        'search_query': search_query,
        'is_admin': is_admin,
    })


@login_required
@require_organization
@require_role('owner', 'admin')
def document_upload(request):
    """Upload a new document to the knowledge base."""
    from .models import Document, DocumentCategory
    from .document_processing import process_document

    categories = DocumentCategory.objects.filter(organization=request.organization)

    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            messages.error(request, 'Please select a file to upload.')
            return render(request, 'core/documents/document_upload.html', {'categories': categories})

        # Validate file size (10 MB)
        if uploaded_file.size > 10 * 1024 * 1024:
            messages.error(request, 'File size must be under 10 MB.')
            return render(request, 'core/documents/document_upload.html', {'categories': categories})

        # Determine file type
        name_lower = uploaded_file.name.lower()
        if name_lower.endswith('.pdf'):
            file_type = 'pdf'
        elif name_lower.endswith('.txt'):
            file_type = 'txt'
        else:
            messages.error(request, 'Only PDF and TXT files are supported.')
            return render(request, 'core/documents/document_upload.html', {'categories': categories})

        title = request.POST.get('title', '').strip() or uploaded_file.name
        description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')

        doc = Document.objects.create(
            title=title,
            description=description,
            file=uploaded_file,
            organization=request.organization,
            uploaded_by=request.user,
            file_type=file_type,
            file_size=uploaded_file.size,
            category_id=category_id if category_id else None,
        )

        try:
            process_document(doc)
            messages.success(request, f'"{doc.title}" uploaded and processed successfully.')
        except Exception as e:
            messages.warning(request, f'Document uploaded but processing failed: {e}')

        return redirect('document_detail', pk=doc.pk)

    return render(request, 'core/documents/document_upload.html', {'categories': categories})


@login_required
@require_organization
def document_detail(request, pk):
    """View document details and extracted text."""
    from .models import Document
    doc = get_object_or_404(Document, pk=pk, organization=request.organization)
    is_admin = request.membership.role in ('owner', 'admin')
    return render(request, 'core/documents/document_detail.html', {
        'document': doc,
        'is_admin': is_admin,
        'chunk_count': doc.chunks.count(),
    })


@login_required
@require_organization
@require_role('owner', 'admin')
def document_edit(request, pk):
    """Edit document title, description, or category."""
    from .models import Document, DocumentCategory
    doc = get_object_or_404(Document, pk=pk, organization=request.organization)
    categories = DocumentCategory.objects.filter(organization=request.organization)

    if request.method == 'POST':
        doc.title = request.POST.get('title', doc.title).strip()
        doc.description = request.POST.get('description', '').strip()
        category_id = request.POST.get('category')
        doc.category_id = category_id if category_id else None
        doc.save()
        messages.success(request, 'Document updated.')
        return redirect('document_detail', pk=doc.pk)

    return render(request, 'core/documents/document_edit.html', {
        'document': doc,
        'categories': categories,
    })


@login_required
@require_organization
@require_role('owner', 'admin')
def document_delete(request, pk):
    """Delete a document and all its chunks."""
    from .models import Document
    doc = get_object_or_404(Document, pk=pk, organization=request.organization)
    if request.method == 'POST':
        title = doc.title
        doc.file.delete(save=False)
        doc.delete()
        messages.success(request, f'"{title}" deleted.')
        return redirect('document_list')
    return render(request, 'core/documents/document_confirm_delete.html', {'document': doc})


@login_required
@require_organization
def document_download(request, pk):
    """Download the original uploaded file."""
    from .models import Document
    doc = get_object_or_404(Document, pk=pk, organization=request.organization)
    response = FileResponse(doc.file.open('rb'), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{doc.file.name.split("/")[-1]}"'
    return response


@login_required
@require_organization
@require_role('owner', 'admin')
def document_category_list(request):
    """List and manage document categories."""
    from .models import DocumentCategory
    categories = DocumentCategory.objects.filter(
        organization=request.organization
    ).annotate(doc_count=models.Count('documents'))
    return render(request, 'core/documents/category_list.html', {'categories': categories})


@login_required
@require_organization
@require_role('owner', 'admin')
def document_category_create(request):
    """Create a new document category."""
    from .models import DocumentCategory
    from django.utils.text import slugify

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            slug = slugify(name)
            if DocumentCategory.objects.filter(organization=request.organization, slug=slug).exists():
                messages.error(request, f'A category with that name already exists.')
            else:
                DocumentCategory.objects.create(
                    name=name, slug=slug, description=description,
                    organization=request.organization, created_by=request.user,
                )
                messages.success(request, f'Category "{name}" created.')
                return redirect('document_category_list')

    return render(request, 'core/documents/category_create.html')


@login_required
@require_organization
@require_role('owner', 'admin')
def document_category_edit(request, pk):
    """Edit a document category."""
    from .models import DocumentCategory
    category = get_object_or_404(DocumentCategory, pk=pk, organization=request.organization)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        if name:
            category.name = name
            category.description = description
            category.save()
            messages.success(request, 'Category updated.')
            return redirect('document_category_list')

    return render(request, 'core/documents/category_edit.html', {'category': category})


@login_required
@require_organization
@require_role('owner', 'admin')
def document_category_delete(request, pk):
    """Delete a document category (documents become uncategorized)."""
    from .models import DocumentCategory
    category = get_object_or_404(DocumentCategory, pk=pk, organization=request.organization)
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted. Documents moved to uncategorized.')
        return redirect('document_category_list')
    return render(request, 'core/documents/category_confirm_delete.html', {'category': category})
```

Note: These views use `models.Q` and `models.Count` - make sure `from django.db import models` is imported at the top of views.py (it likely already is). Also ensure `FileResponse` is imported from `django.http`. Check existing imports at top of `core/views.py` and add as needed:
```python
from django.http import FileResponse
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_documents.py::TestDocumentViews -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add core/views.py core/urls.py tests/test_documents.py
git commit -m "feat: add knowledge base document views and URL routes"
```

---

### Task 7: Create document templates

**Files:**
- Create: `templates/core/documents/document_list.html`
- Create: `templates/core/documents/document_upload.html`
- Create: `templates/core/documents/document_detail.html`
- Create: `templates/core/documents/document_edit.html`
- Create: `templates/core/documents/document_confirm_delete.html`
- Create: `templates/core/documents/category_list.html`
- Create: `templates/core/documents/category_create.html`
- Create: `templates/core/documents/category_edit.html`
- Create: `templates/core/documents/category_confirm_delete.html`

Follow the existing dark theme from `templates/base.html` - ch-black background, ch-gold accents, Tailwind utility classes. Use the same card pattern from `interaction_list.html` and `volunteer_list.html`.

Each template extends `base.html` and uses `{% block content %}`. Use HTMX patterns consistent with the rest of the app.

**Key templates to implement:**

**document_list.html:**
- Page title "Knowledge Base"
- Category filter (dropdown or sidebar)
- Search bar
- Upload button (only shown if `is_admin`)
- Grid of document cards showing: title, category badge, file type icon (PDF/TXT), chunk count, upload date
- Empty state message when no documents exist

**document_upload.html:**
- Title: "Upload Document"
- File input (accept=".pdf,.txt")
- Title field (text input)
- Description field (textarea)
- Category dropdown (with "None" option)
- File size limit note (10 MB)
- Submit button

**document_detail.html:**
- Document title and metadata (file type, size, pages, uploaded by, date)
- Category badge
- Processing status indicator
- Extracted text preview (collapsed by default, expandable)
- Chunk count
- Edit/Delete buttons (if `is_admin`)
- Download button
- Back to list link

**Step 1: Create the templates directory**

Run: `mkdir -p templates/core/documents`

**Step 2: Create all templates**

Create each template following existing patterns. The document_list.html and document_upload.html are the most critical.

**Step 3: Verify templates render**

Run: `python manage.py check`
Then manually verify by running: `python manage.py runserver` and visiting `/documents/`

**Step 4: Commit**

```bash
git add templates/core/documents/
git commit -m "feat: add knowledge base document templates"
```

---

### Task 8: Add Knowledge Base to sidebar navigation

**Files:**
- Modify: `templates/base.html` (add nav item to both mobile and desktop sidebars)

**Step 1: Add nav item to mobile sidebar**

In `templates/base.html`, after the "My Tasks" nav link in the mobile sidebar (around line 471), add:

```html
            <a href="{% url 'document_list' %}" @click="sidebarOpen = false" class="nav-link {% if 'document' in request.resolver_match.url_name %}active{% endif %}">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253"></path>
                </svg>
                Knowledge Base
            </a>
```

**Step 2: Add nav item to desktop sidebar**

Add the same nav link to the desktop sidebar (after the "My Tasks" link around line 571).

**Step 3: Verify navigation works**

Run: `python manage.py runserver` and verify the Knowledge Base link appears and works.

**Step 4: Commit**

```bash
git add templates/base.html
git commit -m "feat: add Knowledge Base to sidebar navigation"
```

---

### Task 9: Run full test suite and verify

**Files:**
- None (verification only)

**Step 1: Run the full test suite**

Run: `pytest --tb=short -v`
Expected: All tests pass (existing 370 + new document tests)

**Step 2: Run the server and manually test the flow**

Run: `python manage.py runserver`

Manual test checklist:
1. Navigate to `/documents/` - list page loads
2. Click "Upload" - form loads (requires admin/owner)
3. Upload a .txt file - processes successfully, redirects to detail
4. View detail page - shows extracted text, chunk count
5. Download the file - original file downloads
6. Create a category at `/documents/categories/create/`
7. Edit the document to assign a category
8. Filter by category on list page
9. Delete the document

**Step 3: Verify Aria integration**

If there's a way to test Aria locally (with API keys set), upload a test document and ask a question about its content. Aria should reference the document in her response.

**Step 4: Commit any fixes**

If any issues found, fix and commit.

---

### Task 10: Update CLAUDE.md documentation

**Files:**
- Modify: `CLAUDE.md`

**Step 1: Add Knowledge Base section to CLAUDE.md**

Add documentation for:
- New models (DocumentCategory, Document, DocumentChunk)
- New URL routes (/documents/*)
- Document processing pipeline
- Aria integration (how documents are searched and cited)
- File storage configuration

**Step 2: Update model summary table and file tree**

Add the three new models to the model table and add templates/core/documents/ to the file tree.

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add Knowledge Base feature to CLAUDE.md"
```
