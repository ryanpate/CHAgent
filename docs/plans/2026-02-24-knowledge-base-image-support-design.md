# Knowledge Base Image Support Design

**Date**: 2026-02-24
**Status**: Approved

## Problem

The Knowledge Base currently only extracts text from PDFs using `pypdf`. Images embedded in PDFs (diagrams, stage plots, scanned pages) are silently skipped. Users cannot upload standalone images (PNG/JPG). Aria has no awareness of visual content and cannot display images in chat responses.

## Goals

1. Extract and process images embedded in uploaded PDFs
2. Accept standalone image uploads (PNG, JPG, JPEG) to the Knowledge Base
3. Use Claude Vision to generate descriptions and OCR text for each image
4. Make image content searchable via semantic search alongside text chunks
5. Display relevant images inline in Aria's chat responses

## Approach

**Unified DocumentImage Model (Approach A)** - a new `DocumentImage` model stores images from both PDF extraction and standalone uploads. Each image gets a Claude Vision-generated description and OCR transcription, which is embedded for semantic search. Aria references images via `[IMAGE_REF:id]` tokens that are rendered as inline thumbnails in chat.

## Data Model

### New Model: DocumentImage

```python
class DocumentImage(models.Model):
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    organization = models.ForeignKey('Organization', on_delete=models.CASCADE)

    # Image file
    image_file = models.ImageField(upload_to='document_images/%Y/%m/')
    original_filename = models.CharField(max_length=255, blank=True)

    # Source info
    source_type = models.CharField(max_length=20, choices=[
        ('pdf_extract', 'Extracted from PDF'),
        ('standalone', 'Standalone Upload'),
    ])
    page_number = models.IntegerField(null=True, blank=True)  # For PDF extracts

    # AI-generated content (from Claude Vision)
    description = models.TextField(blank=True)  # Rich text description of image content
    ocr_text = models.TextField(blank=True)     # Any text found in the image

    # Embedding of combined description + OCR text for semantic search
    embedding_json = models.JSONField(null=True, blank=True)

    # Metadata
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    processing_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

### Changes to Existing Document Model

Add `'image'` to `FILE_TYPE_CHOICES`:

```python
FILE_TYPE_CHOICES = [('pdf', 'PDF'), ('txt', 'Plain Text'), ('image', 'Image')]
```

No other model changes needed.

## Image Extraction from PDFs

During `process_document()`, after text extraction, a new step extracts embedded images:

```python
def extract_images_from_pdf(document) -> list[dict]:
    """Extract embedded images from a PDF file.

    Returns list of dicts with:
        - image_bytes: raw image data
        - page_number: which page it came from
        - name: image object name from PDF
        - width, height: pixel dimensions (via Pillow)
    """
```

- Uses `pypdf`'s `page.images` API to access embedded image objects
- Pillow normalizes extracted images to PNG or JPEG format
- Images smaller than 50x50 pixels are skipped (decorative artifacts like bullets)
- Maximum 20 images per PDF to control Vision API costs

Updated `process_document()` pipeline:

1. Extract text, chunk, embed (existing, unchanged)
2. Extract images from PDF (new)
3. Filter out tiny/decorative images (new)
4. Save image files to `MEDIA_ROOT/document_images/YYYY/MM/` (new)
5. Send each image to Claude Vision for description + OCR (new)
6. Embed the combined description text (new)
7. Create `DocumentImage` records (new)

## Claude Vision Processing

A single function handles both image description and OCR:

```python
def describe_image_with_vision(image_path: str, document_context: str = '') -> dict:
    """Send image to Claude Vision for description and OCR.

    Args:
        image_path: Path to image file on disk.
        document_context: Document title for context.

    Returns:
        {'description': str, 'ocr_text': str}
    """
```

- Uses `claude-sonnet-4-20250514` (same model as Aria, cost-effective)
- Prompt asks for two sections: DESCRIPTION (what the image shows) and OCR_TEXT (any visible text)
- Document title provided as context so Claude understands the domain
- Combined description + OCR text is embedded with OpenAI `text-embedding-3-small` for search

## Standalone Image Upload

Extend the existing upload flow to accept PNG/JPG/JPEG files:

- File input accepts `.pdf,.txt,.png,.jpg,.jpeg`
- File type detection sets `file_type='image'` for image extensions
- Creates a `Document` record (for consistency in list/detail views) and a `DocumentImage` record with `source_type='standalone'`

Processing flow for standalone images:

1. Save file, create `Document` with `file_type='image'`
2. Create `DocumentImage` with `source_type='standalone'`
3. Send to Claude Vision for description + OCR
4. Embed combined text
5. Store description in `Document.extracted_text` (for detail page display)
6. Mark `Document.is_processed = True`

Document list shows thumbnail preview for image documents instead of PDF/TXT icon. Document detail page shows the full image.

## Search Integration

### New Function: search_similar_images

```python
def search_similar_images(query_embedding, organization, limit=3, threshold=0.3):
    """Search DocumentImage descriptions by embedding similarity.

    Returns list of dicts:
        {
            'description': str,
            'ocr_text': str,
            'image_url': str,
            'document_title': str,
            'document_id': int,
            'image_id': int,
            'similarity': float,
        }
    """
```

Same cosine similarity approach as existing text chunk search, but queries `DocumentImage.embedding_json`.

### Agent Integration

In `query_agent()`, after existing document chunk search:

```python
image_results = search_similar_images(question_embedding, organization, limit=3)

if image_results:
    image_context_parts = []
    for result in image_results:
        image_context_parts.append(
            f'From "{result["document_title"]}" (image):\n'
            f'Description: {result["description"]}\n'
            f'Text in image: {result["ocr_text"]}\n'
            f'[IMAGE_REF:{result["image_id"]}]'
        )
    # Append to context sent to Claude
```

System prompt addition: "When referencing images from the Knowledge Base, include the image reference marker exactly as provided (e.g., [IMAGE_REF:123]). Only include image references when the image is directly relevant to the user's question."

## Chat Rendering

`[IMAGE_REF:id]` tokens in Aria's responses are replaced with HTML before saving the `ChatMessage`:

```python
def render_image_refs(content, organization):
    """Replace [IMAGE_REF:id] tokens with HTML img tags."""

    def replace_match(match):
        image_id = int(match.group(1))
        try:
            image = DocumentImage.objects.get(id=image_id, organization=organization)
            return (
                f'<div class="my-3">'
                f'<a href="{image.image_file.url}" target="_blank">'
                f'<img src="{image.image_file.url}" '
                f'alt="{image.description[:100]}" '
                f'class="rounded-lg max-w-sm max-h-64 cursor-pointer hover:opacity-90" '
                f'loading="lazy">'
                f'</a>'
                f'<p class="text-xs text-gray-400 mt-1">'
                f'From: {image.document.title if image.document else "Uploaded image"}'
                f'</p>'
                f'</div>'
            )
        except DocumentImage.DoesNotExist:
            return ''

    return re.sub(r'\[IMAGE_REF:(\d+)\]', replace_match, content)
```

- Resolved server-side before saving (consistent with existing raw HTML rendering)
- Clickable thumbnails (`max-w-sm max-h-64`) open full size in new tab
- Source document title shown as caption
- Invalid or cross-organization refs silently stripped (security)
- No template changes needed - assistant messages already render raw HTML

## Error Handling & Limits

| Constraint | Value | Rationale |
|-----------|-------|-----------|
| Max images per PDF | 20 | Controls Vision API costs |
| Min image dimensions | 50x50 px | Filters decorative PDF artifacts |
| Max standalone image size | 10 MB | Matches existing upload limit |
| Accepted formats | PNG, JPG, JPEG | Common image formats |

**Vision API failures**: If Claude Vision fails for a specific image, the `DocumentImage` is saved with an empty description and the error stored in `processing_error`. Document overall still marks as `is_processed = True` so text search isn't blocked. Failed images can be reprocessed later.

**Image format normalization**: PDF-extracted images (which may be TIFF, JBIG2, etc.) are normalized to PNG or JPEG via Pillow before saving. Images Pillow can't open are skipped.

**Processing time**: A PDF with 10 images makes ~10 Vision API calls (~2-3 seconds each = 20-30 seconds). Processing is synchronous. A warning message is shown: "This document contains images. Processing may take a minute." Moving to background processing (Celery/Django-Q) is out of scope for this design.

## Dependencies

- **Pillow** - already installed (required by `qrcode[pil]` in requirements.txt). Used for `ImageField`, dimension extraction, format normalization, small image filtering.
- No new system-level dependencies.

## Migration

- One new model: `DocumentImage`
- One field change: `Document.FILE_TYPE_CHOICES` adds `'image'`
- Single migration file

## Settings Changes

None. `MEDIA_ROOT`, `MEDIA_URL`, Anthropic API key, and CSP `img-src 'self'` are all already configured.

## Cost Impact

- Claude Vision: ~$0.01-0.05 per image depending on resolution
- OpenAI embeddings: ~$0.0001 per image description (negligible)
- A 10-page PDF with 5 images: ~$0.10-0.25 additional API cost

## File Changes Summary

| File | Changes |
|------|---------|
| `core/models.py` | Add `DocumentImage` model, add `'image'` to `Document.FILE_TYPE_CHOICES` |
| `core/document_processing.py` | Add `extract_images_from_pdf()`, `describe_image_with_vision()`, update `process_document()` |
| `core/embeddings.py` | Add `search_similar_images()` |
| `core/agent.py` | Add image search call in `query_agent()`, update system prompt |
| `core/views.py` | Update `document_upload` for image types, add `render_image_refs()`, call it in `chat_send` |
| `templates/core/documents/document_upload.html` | Accept image file extensions |
| `templates/core/documents/document_list.html` | Thumbnail for image documents |
| `templates/core/documents/document_detail.html` | Show full image for image documents |
| `requirements.txt` | No changes (Pillow already present) |
