# Knowledge Base Document Upload - Design

**Date**: 2026-02-20
**Status**: Approved
**Feature**: Allow organizations to upload documents that Aria can reference when answering questions

## Problem

Teams have institutional knowledge locked in documents (sound board setup guides, lighting procedures, onboarding checklists) that Aria cannot access. Team members must manually search through files or ask someone who knows. Aria should be able to answer questions using these documents.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File types | PDF + plain text | Covers 95% of church documents |
| Upload permissions | Admin/Owner only | Quality control, prevents clutter |
| Organization | Categories/folders | Groups related docs (Sound, Lighting, etc.) |
| File storage | Railway filesystem | Simple for beta, migrate to S3 later |
| Size limit | 10 MB per file | Covers all reasonable documents |
| Search approach | Chunked embeddings (RAG) | Best retrieval quality for natural language |
| Citations | Cite source document | Builds trust, lets users find full doc |

## Data Models

### DocumentCategory

Organizes documents into folders per organization.

```python
class DocumentCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['organization', 'slug']
        ordering = ['name']
```

### Document

An uploaded document with metadata and extracted text.

```python
class Document(models.Model):
    FILE_TYPE_CHOICES = [
        ('pdf', 'PDF'),
        ('txt', 'Plain Text'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(upload_to='documents/%Y/%m/')
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    file_type = models.CharField(max_length=10, choices=FILE_TYPE_CHOICES)
    file_size = models.IntegerField(default=0)  # bytes
    page_count = models.IntegerField(default=0)
    extracted_text = models.TextField(blank=True)
    is_processed = models.BooleanField(default=False)
    processing_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
```

### DocumentChunk

A chunk of document text with its embedding for semantic search.

```python
class DocumentChunk(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='chunks')
    chunk_index = models.IntegerField()
    content = models.TextField()
    embedding_json = models.JSONField(null=True, blank=True)
    page_number = models.IntegerField(null=True, blank=True)
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)  # denormalized

    class Meta:
        ordering = ['document', 'chunk_index']
        unique_together = ['document', 'chunk_index']
```

## Processing Pipeline

1. **Upload**: User submits file via form (admin/owner only)
2. **Validate**: Check file type (PDF/TXT) and size (<= 10 MB)
3. **Extract text**:
   - PDF: `pypdf.PdfReader` to extract text per page
   - TXT: Direct file read with encoding detection
4. **Chunk text**: Split into ~500 token chunks with 50 token overlap
   - Track page numbers for PDF chunks
   - Use sentence boundaries when possible to avoid mid-sentence splits
5. **Embed chunks**: Generate embedding for each chunk via `text-embedding-3-small`
6. **Store**: Save chunks with embeddings to `DocumentChunk`
7. **Mark complete**: Set `Document.is_processed = True`

Processing is synchronous on upload. At 10 MB / ~500 tokens per chunk, worst case is ~100 chunks, ~100 embedding API calls. This takes a few seconds and is acceptable for the upload UX (with a processing indicator).

## Aria Integration

### Query Flow Changes

In `query_agent()`, after generating the query embedding:

1. Search `DocumentChunk` where `organization = request.organization`
2. Compute cosine similarity against query embedding
3. Take top 5 chunks above a relevance threshold (0.3)
4. Group chunks by document for context assembly

### Context Assembly

Add a new section to the system prompt context:

```
--- Knowledge Base Documents ---
From "Sound Board Setup Guide" (Sound category):
[chunk content here]

From "Lighting Procedures Manual" (Lighting category):
[chunk content here]
```

### System Prompt Update

Add to Aria's instructions:
> When answering questions using uploaded Knowledge Base documents, cite the document title.
> Example: "According to the Sound Board Setup Guide, the first step is to..."
> Only use document content that is relevant to the user's question.

### Query Detection

Add `is_document_query()` function that detects questions about procedures, how-to, setup, guides. However, document search should ALSO run for general queries - a user asking "how do I turn on the sound board" shouldn't need special phrasing. Document chunks are searched alongside interactions for all queries.

## URL Routes

```python
# Knowledge Base
path('documents/', views.document_list, name='document_list'),
path('documents/upload/', views.document_upload, name='document_upload'),
path('documents/<int:pk>/', views.document_detail, name='document_detail'),
path('documents/<int:pk>/edit/', views.document_edit, name='document_edit'),
path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),
path('documents/<int:pk>/download/', views.document_download, name='document_download'),

# Document Categories
path('documents/categories/', views.document_category_list, name='document_category_list'),
path('documents/categories/create/', views.document_category_create, name='document_category_create'),
path('documents/categories/<int:pk>/edit/', views.document_category_edit, name='document_category_edit'),
path('documents/categories/<int:pk>/delete/', views.document_category_delete, name='document_category_delete'),
```

## UI

### Sidebar
- New "Knowledge Base" nav item (book/document icon)

### Document List (`/documents/`)
- Category filter sidebar/dropdown
- Search bar (title/description)
- Upload button (visible to admin/owner only)
- Document cards showing: title, category badge, file type icon, page count, upload date, uploader
- Processing status indicator for recently uploaded docs

### Upload Form (`/documents/upload/`)
- File picker (accepts .pdf, .txt)
- Title field (auto-populated from filename)
- Description textarea
- Category dropdown (with option to create new)
- 10 MB limit shown, client-side validation

### Document Detail (`/documents/<id>/`)
- Metadata: title, category, uploader, date, file size, page count
- Extracted text preview (first 500 chars with expand)
- Chunk count and processing status
- Edit/Delete buttons (admin/owner only)
- Download original file button

## Permissions

| Action | Admin/Owner | Leader | Member | Viewer |
|--------|------------|--------|--------|--------|
| Upload document | Yes | No | No | No |
| Edit/delete document | Yes | No | No | No |
| Manage categories | Yes | No | No | No |
| View document list | Yes | Yes | Yes | Yes |
| Download document | Yes | Yes | Yes | Yes |
| Ask Aria about docs | Yes | Yes | Yes | Yes |

## File Storage

Configure Django MEDIA settings:

```python
# config/settings.py
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024   # 10 MB
```

In production (Railway), configure a persistent volume mounted at `/app/media`.

## Security

- Files served through Django view (not direct MEDIA_URL access) to enforce org scoping
- File type validation on both client and server side (check MIME type, not just extension)
- Extracted text sanitized before storage
- Document chunks scoped to organization in all queries
- Audit log entry on upload/edit/delete actions

## Testing

- Model tests: Document, DocumentChunk, DocumentCategory CRUD
- Processing tests: PDF text extraction, text chunking, embedding generation
- View tests: upload, list, detail, edit, delete with permission checks
- Integration test: upload document, then ask Aria a question it can answer from the doc
- Multi-tenant isolation: documents from org A not visible to org B
