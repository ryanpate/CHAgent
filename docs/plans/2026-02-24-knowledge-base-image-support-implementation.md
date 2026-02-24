# Knowledge Base Image Support Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add image support to the Knowledge Base so Aria can understand, search, and display images from PDFs and standalone uploads.

**Architecture:** New `DocumentImage` model stores images (from PDF extraction or direct upload) with Claude Vision-generated descriptions and OCR text. Descriptions are embedded for semantic search alongside text chunks. Aria references images via `[IMAGE_REF:id]` tokens rendered as inline thumbnails in chat.

**Tech Stack:** Django, pypdf (image extraction), Pillow (image processing), Anthropic Claude Vision (descriptions/OCR), OpenAI text-embedding-3-small (embeddings)

---

### Task 1: DocumentImage Model

**Files:**
- Modify: `core/models.py:3448-3502`
- Create: migration via `makemigrations`

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestDocumentImageModel:
    def test_create_image_from_pdf(self, org_alpha, user_alpha_owner):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile('test.pdf', b'%PDF-fake', content_type='application/pdf')
        doc = Document.objects.create(
            title='Stage Plot', file=fake_pdf,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100,
        )
        fake_img = SimpleUploadedFile('stage.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        from core.models import DocumentImage
        img = DocumentImage.objects.create(
            document=doc,
            organization=org_alpha,
            image_file=fake_img,
            original_filename='stage.png',
            source_type='pdf_extract',
            page_number=1,
            description='A stage plot showing speaker positions',
            ocr_text='Monitor 1, Monitor 2',
            width=800,
            height=600,
        )
        assert img.pk is not None
        assert img.document == doc
        assert img.source_type == 'pdf_extract'
        assert img.page_number == 1
        assert str(img.image_file)  # has a file path

    def test_create_standalone_image(self, org_alpha, user_alpha_owner):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_img = SimpleUploadedFile('diagram.jpg', b'\xff\xd8\xff' + b'\x00' * 100, content_type='image/jpeg')
        doc = Document.objects.create(
            title='Equipment Diagram', file=fake_img,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='image', file_size=200,
        )
        from core.models import DocumentImage
        img = DocumentImage.objects.create(
            document=doc,
            organization=org_alpha,
            image_file=fake_img,
            original_filename='diagram.jpg',
            source_type='standalone',
            description='A wiring diagram for the audio setup',
            ocr_text='None',
            width=1024,
            height=768,
        )
        assert img.pk is not None
        assert img.source_type == 'standalone'
        assert img.document.file_type == 'image'

    def test_image_str_representation(self, org_alpha, user_alpha_owner):
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile('test.pdf', b'%PDF-fake', content_type='application/pdf')
        doc = Document.objects.create(
            title='Stage Plot', file=fake_pdf,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100,
        )
        fake_img = SimpleUploadedFile('img.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        from core.models import DocumentImage
        img = DocumentImage.objects.create(
            document=doc, organization=org_alpha,
            image_file=fake_img, original_filename='img.png',
            source_type='pdf_extract',
        )
        assert 'Stage Plot' in str(img)

    def test_image_organization_isolation(self, org_alpha, org_beta, user_alpha_owner, user_beta_owner):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from core.models import DocumentImage
        fake_img1 = SimpleUploadedFile('a.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        doc1 = Document.objects.create(
            title='Alpha Doc', file=fake_img1,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='image', file_size=100,
        )
        DocumentImage.objects.create(
            document=doc1, organization=org_alpha,
            image_file=fake_img1, source_type='standalone',
        )
        fake_img2 = SimpleUploadedFile('b.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        doc2 = Document.objects.create(
            title='Beta Doc', file=fake_img2,
            organization=org_beta, uploaded_by=user_beta_owner,
            file_type='image', file_size=100,
        )
        DocumentImage.objects.create(
            document=doc2, organization=org_beta,
            image_file=fake_img2, source_type='standalone',
        )
        assert DocumentImage.objects.filter(organization=org_alpha).count() == 1
        assert DocumentImage.objects.filter(organization=org_beta).count() == 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestDocumentImageModel -v`
Expected: FAIL with `ImportError: cannot import name 'DocumentImage'`

**Step 3: Add DocumentImage model and update Document.FILE_TYPE_CHOICES**

In `core/models.py`, after the `DocumentChunk` class (line 3502), add:

```python
class DocumentImage(models.Model):
    """An image extracted from a document or uploaded standalone, with AI-generated description."""
    SOURCE_TYPE_CHOICES = [
        ('pdf_extract', 'Extracted from PDF'),
        ('standalone', 'Standalone Upload'),
    ]

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name='images',
        null=True, blank=True
    )
    organization = models.ForeignKey(
        'Organization', on_delete=models.CASCADE, related_name='document_images'
    )

    # Image file
    image_file = models.ImageField(upload_to='document_images/%Y/%m/')
    original_filename = models.CharField(max_length=255, blank=True)

    # Source info
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    page_number = models.IntegerField(null=True, blank=True)

    # AI-generated content (from Claude Vision)
    description = models.TextField(blank=True)
    ocr_text = models.TextField(blank=True)

    # Embedding of combined description + OCR text for semantic search
    embedding_json = models.JSONField(null=True, blank=True)

    # Metadata
    width = models.IntegerField(default=0)
    height = models.IntegerField(default=0)
    processing_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['document', 'page_number', 'created_at']

    def __str__(self):
        doc_title = self.document.title if self.document else 'Standalone'
        return f'{doc_title} - Image {self.pk}'
```

Update `Document.FILE_TYPE_CHOICES` at line 3450:

```python
FILE_TYPE_CHOICES = [
    ('pdf', 'PDF'),
    ('txt', 'Plain Text'),
    ('image', 'Image'),
]
```

**Step 4: Create and run migration**

Run: `python manage.py makemigrations core && python manage.py migrate`
Expected: Migration created and applied successfully

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestDocumentImageModel -v`
Expected: All 4 tests PASS

**Step 6: Commit**

```bash
git add core/models.py core/migrations/ tests/test_documents.py
git commit -m "feat: add DocumentImage model and 'image' file type to Document"
```

---

### Task 2: Claude Vision Processing Function

**Files:**
- Modify: `core/document_processing.py`
- Test: `tests/test_documents.py`

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
class TestDescribeImageWithVision:
    @patch('core.document_processing.anthropic')
    def test_describe_image_returns_description_and_ocr(self, mock_anthropic, tmp_path):
        # Create a fake image file
        img_path = tmp_path / 'test.png'
        img_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

        # Mock the Anthropic client response
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=(
            'DESCRIPTION: A stage layout diagram showing three monitor positions '
            'and the main speaker array.\n\n'
            'OCR_TEXT: Monitor 1, Monitor 2, Main L, Main R'
        ))]
        mock_client.messages.create.return_value = mock_response

        from core.document_processing import describe_image_with_vision
        result = describe_image_with_vision(str(img_path), document_context='Stage Setup Guide')

        assert 'description' in result
        assert 'ocr_text' in result
        assert 'stage layout' in result['description'].lower()
        assert 'Monitor 1' in result['ocr_text']
        mock_client.messages.create.assert_called_once()

    @patch('core.document_processing.anthropic')
    def test_describe_image_handles_no_ocr_text(self, mock_anthropic, tmp_path):
        img_path = tmp_path / 'photo.jpg'
        img_path.write_bytes(b'\xff\xd8\xff' + b'\x00' * 100)

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=(
            'DESCRIPTION: A photograph of the worship team during rehearsal.\n\n'
            'OCR_TEXT: None'
        ))]
        mock_client.messages.create.return_value = mock_response

        from core.document_processing import describe_image_with_vision
        result = describe_image_with_vision(str(img_path))

        assert 'worship team' in result['description'].lower()
        assert result['ocr_text'] == '' or result['ocr_text'] == 'None'

    @patch('core.document_processing.anthropic')
    def test_describe_image_handles_api_error(self, mock_anthropic, tmp_path):
        img_path = tmp_path / 'test.png'
        img_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        mock_client.messages.create.side_effect = Exception('API rate limit')

        from core.document_processing import describe_image_with_vision
        result = describe_image_with_vision(str(img_path))

        assert result['description'] == ''
        assert result['ocr_text'] == ''
        assert 'error' in result
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestDescribeImageWithVision -v`
Expected: FAIL with `ImportError: cannot import name 'describe_image_with_vision'`

**Step 3: Implement describe_image_with_vision**

Add to `core/document_processing.py`:

```python
import anthropic


def describe_image_with_vision(image_path: str, document_context: str = '') -> dict:
    """Send image to Claude Vision for description and OCR.

    Args:
        image_path: Path to image file on disk.
        document_context: Optional document title for context.

    Returns:
        dict with 'description', 'ocr_text', and optionally 'error'.
    """
    import base64
    import mimetypes

    try:
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith('image/'):
            mime_type = 'image/png'

        with open(image_path, 'rb') as f:
            image_data = base64.standard_b64encode(f.read()).decode('utf-8')

        client = anthropic.Anthropic()

        context_line = f'This image is from a document titled "{document_context}". ' if document_context else ''

        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1024,
            messages=[{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': mime_type,
                            'data': image_data,
                        },
                    },
                    {
                        'type': 'text',
                        'text': (
                            f'{context_line}'
                            'Provide two sections:\n'
                            'DESCRIPTION: A detailed description of what this image shows '
                            '(diagrams, layouts, charts, photos, etc.).\n'
                            'OCR_TEXT: Any text visible in the image, transcribed exactly. '
                            'If no text is visible, write "None".'
                        ),
                    },
                ],
            }],
        )

        raw_text = response.content[0].text

        # Parse DESCRIPTION and OCR_TEXT sections
        description = ''
        ocr_text = ''
        if 'DESCRIPTION:' in raw_text:
            parts = raw_text.split('OCR_TEXT:')
            description = parts[0].replace('DESCRIPTION:', '').strip()
            if len(parts) > 1:
                ocr_text = parts[1].strip()
                if ocr_text.lower() == 'none':
                    ocr_text = ''
        else:
            description = raw_text.strip()

        return {'description': description, 'ocr_text': ocr_text}

    except Exception as e:
        logger.error(f'Error describing image with Vision: {e}')
        return {'description': '', 'ocr_text': '', 'error': str(e)}
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestDescribeImageWithVision -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add core/document_processing.py tests/test_documents.py
git commit -m "feat: add Claude Vision image description and OCR function"
```

---

### Task 3: PDF Image Extraction

**Files:**
- Modify: `core/document_processing.py`
- Test: `tests/test_documents.py`

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestExtractImagesFromPdf:
    def test_extract_no_images_returns_empty(self, tmp_path):
        """A text-only PDF yields no images."""
        from core.document_processing import extract_images_from_pdf

        # Create minimal valid PDF with no images
        from pypdf import PdfWriter
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        pdf_path = tmp_path / 'text_only.pdf'
        with open(pdf_path, 'wb') as f:
            writer.write(f)

        images = extract_images_from_pdf(str(pdf_path))
        assert images == []

    def test_small_images_filtered_out(self, tmp_path):
        """Images below 50x50 pixels should be filtered out."""
        from core.document_processing import _filter_small_images

        images = [
            {'image_bytes': b'fake', 'width': 10, 'height': 10, 'page_number': 1, 'name': 'bullet.png'},
            {'image_bytes': b'fake', 'width': 800, 'height': 600, 'page_number': 1, 'name': 'diagram.png'},
        ]
        filtered = _filter_small_images(images, min_dimension=50)
        assert len(filtered) == 1
        assert filtered[0]['name'] == 'diagram.png'

    def test_max_images_cap(self, tmp_path):
        """No more than 20 images should be returned."""
        from core.document_processing import _cap_images

        images = [{'image_bytes': b'fake', 'page_number': i, 'name': f'img{i}.png'} for i in range(30)]
        capped = _cap_images(images, max_images=20)
        assert len(capped) == 20
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestExtractImagesFromPdf -v`
Expected: FAIL with `ImportError: cannot import name 'extract_images_from_pdf'`

**Step 3: Implement image extraction helpers**

Add to `core/document_processing.py`:

```python
def extract_images_from_pdf(pdf_path: str) -> list[dict]:
    """Extract embedded images from a PDF file.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        List of dicts with 'image_bytes', 'page_number', 'name', 'width', 'height'.
        Filtered to skip small decorative images. Capped at 20 images.
    """
    from pypdf import PdfReader
    from PIL import Image
    import io

    reader = PdfReader(pdf_path)
    images = []

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            for image_obj in page.images:
                try:
                    img_bytes = image_obj.data
                    # Get dimensions via Pillow
                    pil_img = Image.open(io.BytesIO(img_bytes))
                    width, height = pil_img.size
                    images.append({
                        'image_bytes': img_bytes,
                        'page_number': page_num,
                        'name': image_obj.name,
                        'width': width,
                        'height': height,
                    })
                except Exception as e:
                    logger.warning(f'Could not process image {image_obj.name} on page {page_num}: {e}')
        except Exception as e:
            logger.warning(f'Could not extract images from page {page_num}: {e}')

    images = _filter_small_images(images)
    images = _cap_images(images)
    return images


def _filter_small_images(images: list[dict], min_dimension: int = 50) -> list[dict]:
    """Remove images smaller than min_dimension in both width and height."""
    return [
        img for img in images
        if img.get('width', 0) >= min_dimension or img.get('height', 0) >= min_dimension
    ]


def _cap_images(images: list[dict], max_images: int = 20) -> list[dict]:
    """Limit to max_images, keeping the first N."""
    if len(images) > max_images:
        logger.warning(f'PDF has {len(images)} images, capping at {max_images}')
    return images[:max_images]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestExtractImagesFromPdf -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add core/document_processing.py tests/test_documents.py
git commit -m "feat: add PDF image extraction with size filtering and cap"
```

---

### Task 4: Update process_document for Image Processing

**Files:**
- Modify: `core/document_processing.py:106-162` (the `process_document` function)
- Test: `tests/test_documents.py`

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestProcessDocumentImages:
    @patch('core.document_processing.describe_image_with_vision')
    @patch('core.document_processing.get_embedding')
    @patch('core.document_processing.extract_images_from_pdf')
    def test_process_pdf_with_images(self, mock_extract, mock_embed, mock_describe, org_alpha, user_alpha_owner, tmp_path):
        from core.models import DocumentImage
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create a fake PDF document
        fake_pdf = SimpleUploadedFile('test.pdf', b'%PDF-fake-content', content_type='application/pdf')
        doc = Document.objects.create(
            title='Stage Guide', file=fake_pdf,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=500,
        )

        # Mock image extraction returning one image
        mock_extract.return_value = [{
            'image_bytes': b'\x89PNG\r\n\x1a\n' + b'\x00' * 100,
            'page_number': 2,
            'name': 'stage_plot.png',
            'width': 800,
            'height': 600,
        }]

        # Mock vision description
        mock_describe.return_value = {
            'description': 'A stage plot diagram',
            'ocr_text': 'Monitor 1',
        }

        # Mock embedding
        mock_embed.return_value = [0.1] * 1536

        from core.document_processing import _process_document_images
        _process_document_images(doc)

        images = DocumentImage.objects.filter(document=doc)
        assert images.count() == 1
        img = images.first()
        assert img.description == 'A stage plot diagram'
        assert img.ocr_text == 'Monitor 1'
        assert img.page_number == 2
        assert img.width == 800
        assert img.height == 600
        assert img.source_type == 'pdf_extract'
        assert img.embedding_json == [0.1] * 1536

    @patch('core.document_processing.describe_image_with_vision')
    @patch('core.document_processing.get_embedding')
    @patch('core.document_processing.extract_images_from_pdf')
    def test_process_pdf_vision_failure_still_saves_image(self, mock_extract, mock_embed, mock_describe, org_alpha, user_alpha_owner):
        from core.models import DocumentImage
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake_pdf = SimpleUploadedFile('test.pdf', b'%PDF-fake', content_type='application/pdf')
        doc = Document.objects.create(
            title='Guide', file=fake_pdf,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100,
        )

        mock_extract.return_value = [{
            'image_bytes': b'\x89PNG\r\n\x1a\n' + b'\x00' * 100,
            'page_number': 1, 'name': 'img.png',
            'width': 400, 'height': 300,
        }]
        mock_describe.return_value = {
            'description': '', 'ocr_text': '', 'error': 'API rate limit',
        }
        mock_embed.return_value = None

        from core.document_processing import _process_document_images
        _process_document_images(doc)

        images = DocumentImage.objects.filter(document=doc)
        assert images.count() == 1
        img = images.first()
        assert img.description == ''
        assert 'API rate limit' in img.processing_error
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestProcessDocumentImages -v`
Expected: FAIL with `ImportError: cannot import name '_process_document_images'`

**Step 3: Implement _process_document_images and update process_document**

Add to `core/document_processing.py`:

```python
def _process_document_images(document) -> None:
    """Extract images from a PDF document, describe with Vision, and save.

    Args:
        document: A Document model instance (must be file_type='pdf').
    """
    from .models import DocumentImage
    from .embeddings import get_embedding
    from django.core.files.base import ContentFile
    from PIL import Image
    import io
    import os

    if document.file_type != 'pdf':
        return

    pdf_path = document.file.path
    images = extract_images_from_pdf(pdf_path)

    if not images:
        logger.info(f'No images found in "{document.title}"')
        return

    logger.info(f'Processing {len(images)} images from "{document.title}"')

    for img_data in images:
        try:
            # Normalize image to PNG or JPEG via Pillow
            pil_img = Image.open(io.BytesIO(img_data['image_bytes']))
            output = io.BytesIO()
            if pil_img.mode in ('RGBA', 'LA', 'P'):
                fmt = 'PNG'
                ext = '.png'
            else:
                fmt = 'JPEG'
                ext = '.jpg'
            pil_img.save(output, format=fmt)
            image_content = output.getvalue()

            # Create the DocumentImage record with the file
            base_name = os.path.splitext(img_data['name'])[0] or f'page{img_data["page_number"]}_img'
            filename = f'{base_name}{ext}'

            doc_image = DocumentImage(
                document=document,
                organization=document.organization,
                original_filename=img_data['name'],
                source_type='pdf_extract',
                page_number=img_data['page_number'],
                width=img_data['width'],
                height=img_data['height'],
            )
            doc_image.image_file.save(filename, ContentFile(image_content), save=False)
            doc_image.save()

            # Describe with Claude Vision
            vision_result = describe_image_with_vision(
                doc_image.image_file.path,
                document_context=document.title,
            )

            doc_image.description = vision_result.get('description', '')
            doc_image.ocr_text = vision_result.get('ocr_text', '')

            if vision_result.get('error'):
                doc_image.processing_error = vision_result['error']
                doc_image.save()
                continue

            # Embed combined description + OCR text
            combined_text = doc_image.description
            if doc_image.ocr_text:
                combined_text += '\n' + doc_image.ocr_text
            if combined_text.strip():
                doc_image.embedding_json = get_embedding(combined_text)

            doc_image.save()
            logger.info(f'Processed image {filename} from page {img_data["page_number"]}')

        except Exception as e:
            logger.error(f'Error processing image {img_data.get("name", "unknown")}: {e}')
```

Update the existing `process_document` function (around line 155, after `document.save()`):

Add this call before the final `document.save()` at the end of the try block:

```python
        # Process images from PDFs
        if document.file_type == 'pdf':
            try:
                _process_document_images(document)
            except Exception as e:
                logger.error(f'Image processing failed for "{document.title}": {e}')
                # Don't fail the whole document processing for image errors
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestProcessDocumentImages -v`
Expected: All 2 tests PASS

**Step 5: Run full document test suite**

Run: `python -m pytest tests/test_documents.py -v`
Expected: All existing + new tests PASS

**Step 6: Commit**

```bash
git add core/document_processing.py tests/test_documents.py
git commit -m "feat: add image processing pipeline to process_document for PDFs"
```

---

### Task 5: Standalone Image Upload

**Files:**
- Modify: `core/views.py:4954-5006` (document_upload view)
- Modify: `core/document_processing.py` (process_document)
- Modify: `templates/core/documents/document_upload.html`
- Test: `tests/test_documents.py`

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestStandaloneImageUpload:
    @patch('core.document_processing.describe_image_with_vision')
    @patch('core.document_processing.get_embedding')
    def test_upload_png_creates_document_and_image(self, mock_embed, mock_describe, client_alpha, org_alpha):
        from core.models import DocumentImage

        mock_describe.return_value = {'description': 'A stage layout', 'ocr_text': ''}
        mock_embed.return_value = [0.1] * 1536

        fake_img = SimpleUploadedFile('stage.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        response = client_alpha.post('/documents/upload/', {
            'file': fake_img,
            'title': 'Stage Layout',
            'description': 'Our current stage layout',
        })

        assert response.status_code == 302  # Redirect to detail
        doc = Document.objects.filter(title='Stage Layout').first()
        assert doc is not None
        assert doc.file_type == 'image'
        images = DocumentImage.objects.filter(document=doc)
        assert images.count() == 1
        assert images.first().source_type == 'standalone'

    def test_upload_unsupported_type_rejected(self, client_alpha):
        fake_file = SimpleUploadedFile('doc.docx', b'fake', content_type='application/vnd.openxmlformats')
        response = client_alpha.post('/documents/upload/', {'file': fake_file})

        assert response.status_code == 200  # Re-renders form
        assert Document.objects.count() == 0

    @patch('core.document_processing.describe_image_with_vision')
    @patch('core.document_processing.get_embedding')
    def test_upload_jpg_accepted(self, mock_embed, mock_describe, client_alpha):
        from core.models import DocumentImage

        mock_describe.return_value = {'description': 'A photo', 'ocr_text': ''}
        mock_embed.return_value = [0.1] * 1536

        fake_img = SimpleUploadedFile('photo.jpg', b'\xff\xd8\xff' + b'\x00' * 100, content_type='image/jpeg')
        response = client_alpha.post('/documents/upload/', {
            'file': fake_img,
            'title': 'Team Photo',
        })

        assert response.status_code == 302
        doc = Document.objects.filter(title='Team Photo').first()
        assert doc is not None
        assert doc.file_type == 'image'
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestStandaloneImageUpload -v`
Expected: FAIL - upload rejected because `.png` and `.jpg` are not accepted

**Step 3: Update document_upload view**

In `core/views.py`, update the `document_upload` function (line 4973-4981). Replace the file type detection block:

```python
        # Determine file type
        name_lower = uploaded_file.name.lower()
        if name_lower.endswith('.pdf'):
            file_type = 'pdf'
        elif name_lower.endswith('.txt'):
            file_type = 'txt'
        elif name_lower.endswith(('.png', '.jpg', '.jpeg')):
            file_type = 'image'
        else:
            messages.error(request, 'Only PDF, TXT, PNG, JPG, and JPEG files are supported.')
            return render(request, 'core/documents/document_upload.html', {'categories': categories})
```

**Step 4: Add standalone image processing to process_document**

Add to `core/document_processing.py` in `process_document()`, at the start of the try block, before the text extraction:

```python
        # Handle standalone image uploads
        if document.file_type == 'image':
            _process_standalone_image(document)
            return
```

Add new function:

```python
def _process_standalone_image(document) -> None:
    """Process a standalone image upload: describe with Vision, embed, save.

    Args:
        document: A Document model instance with file_type='image'.
    """
    from .models import DocumentImage
    from .embeddings import get_embedding
    from PIL import Image as PILImage

    try:
        # Get image dimensions
        pil_img = PILImage.open(document.file.path)
        width, height = pil_img.size

        # Create DocumentImage record (image_file points to the same file)
        doc_image = DocumentImage.objects.create(
            document=document,
            organization=document.organization,
            image_file=document.file.name,  # Reuse the already-saved file
            original_filename=document.file.name.split('/')[-1],
            source_type='standalone',
            width=width,
            height=height,
        )

        # Describe with Claude Vision
        vision_result = describe_image_with_vision(
            document.file.path,
            document_context=document.title,
        )

        doc_image.description = vision_result.get('description', '')
        doc_image.ocr_text = vision_result.get('ocr_text', '')

        if vision_result.get('error'):
            doc_image.processing_error = vision_result['error']
        else:
            combined_text = doc_image.description
            if doc_image.ocr_text:
                combined_text += '\n' + doc_image.ocr_text
            if combined_text.strip():
                doc_image.embedding_json = get_embedding(combined_text)

        doc_image.save()

        # Store description as extracted_text for the detail page
        document.extracted_text = doc_image.description
        document.is_processed = True
        document.processing_error = ''
        document.save()

        logger.info(f'Processed standalone image "{document.title}"')

    except Exception as e:
        logger.error(f'Error processing standalone image "{document.title}": {e}')
        document.processing_error = str(e)
        document.is_processed = False
        document.save()
        raise
```

**Step 5: Update upload template**

In `templates/core/documents/document_upload.html`, line 18:

Change:
```html
<input type="file" name="file" accept=".pdf,.txt" required
```
To:
```html
<input type="file" name="file" accept=".pdf,.txt,.png,.jpg,.jpeg" required
```

Line 20, change:
```html
<p class="text-xs text-gray-500 mt-1">PDF or TXT files up to 10 MB</p>
```
To:
```html
<p class="text-xs text-gray-500 mt-1">PDF, TXT, PNG, JPG, or JPEG files up to 10 MB</p>
```

**Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestStandaloneImageUpload -v`
Expected: All 3 tests PASS

**Step 7: Commit**

```bash
git add core/views.py core/document_processing.py templates/core/documents/document_upload.html tests/test_documents.py
git commit -m "feat: accept standalone image uploads (PNG/JPG) in Knowledge Base"
```

---

### Task 6: Image Semantic Search

**Files:**
- Modify: `core/embeddings.py:108-155`
- Test: `tests/test_documents.py`

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestSearchSimilarImages:
    def test_search_returns_matching_images(self, org_alpha, user_alpha_owner):
        from core.models import DocumentImage
        from core.embeddings import search_similar_images

        fake_file = SimpleUploadedFile('test.pdf', b'%PDF', content_type='application/pdf')
        doc = Document.objects.create(
            title='Stage Guide', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100, is_processed=True,
        )

        fake_img = SimpleUploadedFile('plot.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        DocumentImage.objects.create(
            document=doc, organization=org_alpha,
            image_file=fake_img, source_type='pdf_extract',
            description='A stage plot showing monitor positions',
            ocr_text='Monitor 1, Monitor 2',
            embedding_json=[1.0] + [0.0] * 1535,
        )

        # Query with similar embedding
        query_embedding = [0.9] + [0.0] * 1535
        results = search_similar_images(query_embedding, org_alpha, limit=3, threshold=0.1)

        assert len(results) == 1
        assert results[0]['document_title'] == 'Stage Guide'
        assert 'stage plot' in results[0]['description'].lower()
        assert 'image_url' in results[0]
        assert 'image_id' in results[0]

    def test_search_respects_organization_isolation(self, org_alpha, org_beta, user_alpha_owner, user_beta_owner):
        from core.models import DocumentImage
        from core.embeddings import search_similar_images

        # Create image in org_alpha
        fake_file = SimpleUploadedFile('test.pdf', b'%PDF', content_type='application/pdf')
        doc = Document.objects.create(
            title='Alpha Guide', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100, is_processed=True,
        )
        fake_img = SimpleUploadedFile('a.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        DocumentImage.objects.create(
            document=doc, organization=org_alpha,
            image_file=fake_img, source_type='pdf_extract',
            description='Alpha image',
            embedding_json=[1.0] + [0.0] * 1535,
        )

        # Search from org_beta should find nothing
        query_embedding = [1.0] + [0.0] * 1535
        results = search_similar_images(query_embedding, org_beta, limit=3, threshold=0.1)
        assert len(results) == 0

    def test_search_below_threshold_excluded(self, org_alpha, user_alpha_owner):
        from core.models import DocumentImage
        from core.embeddings import search_similar_images

        fake_file = SimpleUploadedFile('test.pdf', b'%PDF', content_type='application/pdf')
        doc = Document.objects.create(
            title='Guide', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100, is_processed=True,
        )
        fake_img = SimpleUploadedFile('a.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        DocumentImage.objects.create(
            document=doc, organization=org_alpha,
            image_file=fake_img, source_type='pdf_extract',
            description='Unrelated image',
            embedding_json=[1.0] + [0.0] * 1535,
        )

        # Query with orthogonal embedding
        query_embedding = [0.0] * 1 + [1.0] + [0.0] * 1534
        results = search_similar_images(query_embedding, org_alpha, limit=3, threshold=0.3)
        assert len(results) == 0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestSearchSimilarImages -v`
Expected: FAIL with `ImportError: cannot import name 'search_similar_images'`

**Step 3: Implement search_similar_images**

Add to `core/embeddings.py`, after the existing `search_similar_documents` function:

```python
def search_similar_images(query_embedding: list[float], organization, limit: int = 3, threshold: float = 0.3) -> list[dict]:
    """
    Find document images most similar to query, scoped to organization.

    Args:
        query_embedding: The embedding vector to search against.
        organization: Organization instance to scope the search.
        limit: Maximum number of results to return.
        threshold: Minimum cosine similarity score to include.

    Returns:
        List of dicts with 'description', 'ocr_text', 'image_url',
        'document_title', 'document_id', 'image_id', 'similarity'.
    """
    from .models import DocumentImage
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

    images = DocumentImage.objects.filter(
        organization=organization,
        embedding_json__isnull=False,
    ).select_related('document')

    scored = []
    for img in images:
        similarity = cosine_similarity(query_embedding, img.embedding_json)
        if similarity >= threshold:
            scored.append({
                'description': img.description,
                'ocr_text': img.ocr_text,
                'image_url': img.image_file.url if img.image_file else '',
                'document_title': img.document.title if img.document else 'Uploaded image',
                'document_id': img.document.id if img.document else None,
                'image_id': img.id,
                'similarity': similarity,
            })

    scored.sort(key=lambda x: x['similarity'], reverse=True)
    return scored[:limit]
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestSearchSimilarImages -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add core/embeddings.py tests/test_documents.py
git commit -m "feat: add search_similar_images for Knowledge Base image search"
```

---

### Task 7: Agent Integration (Image Context in Aria Responses)

**Files:**
- Modify: `core/agent.py:4352-4379` (document search section)
- Modify: `core/agent.py:2144-2145` (system prompt)
- Test: `tests/test_documents.py`

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestAgentImageIntegration:
    @patch('core.embeddings.search_similar_images')
    @patch('core.embeddings.search_similar_documents')
    def test_image_context_added_to_agent(self, mock_doc_search, mock_img_search):
        """Verify that image search results include IMAGE_REF tokens."""
        mock_doc_search.return_value = []
        mock_img_search.return_value = [{
            'description': 'A stage plot showing positions',
            'ocr_text': 'Monitor 1',
            'image_url': '/media/document_images/2026/02/stage.png',
            'document_title': 'Stage Guide',
            'document_id': 1,
            'image_id': 42,
            'similarity': 0.85,
        }]

        from core.agent import _build_image_context
        context = _build_image_context(mock_img_search.return_value)

        assert '[IMAGE_REF:42]' in context
        assert 'Stage Guide' in context
        assert 'stage plot' in context.lower()
        assert 'Monitor 1' in context
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestAgentImageIntegration -v`
Expected: FAIL with `ImportError: cannot import name '_build_image_context'`

**Step 3: Add _build_image_context and integrate into query_agent**

Add to `core/agent.py` (near the document search section, around line 4379):

```python
def _build_image_context(image_results: list[dict]) -> str:
    """Build context string from image search results for the AI prompt.

    Args:
        image_results: Results from search_similar_images().

    Returns:
        Formatted context string with IMAGE_REF tokens.
    """
    if not image_results:
        return ''

    image_context_parts = []
    for result in image_results:
        part = (
            f'From "{result["document_title"]}" (image):\n'
            f'Description: {result["description"]}\n'
        )
        if result.get('ocr_text'):
            part += f'Text in image: {result["ocr_text"]}\n'
        part += f'[IMAGE_REF:{result["image_id"]}]'
        image_context_parts.append(part)

    return (
        "\n[KNOWLEDGE BASE IMAGES]\n"
        + "\n\n---\n\n".join(image_context_parts)
    )
```

In `query_agent()`, after the existing document search block (around line 4377-4379), add:

```python
            # Search Knowledge Base images
            from .embeddings import search_similar_images
            image_results = search_similar_images(
                question_embedding, organization, limit=3, threshold=0.3
            )
            if image_results:
                image_context = _build_image_context(image_results)
                context = image_context + "\n\n" + context
                logger.info(f"Added {len(image_results)} document images to context")
```

Update system prompt at line 2144-2145. After the existing Knowledge Base document instructions, add:

```
- When referencing images from the Knowledge Base, include the image reference marker exactly as provided (e.g., [IMAGE_REF:123]). Only include image references when the image is directly relevant to the user's question.
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestAgentImageIntegration -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/agent.py tests/test_documents.py
git commit -m "feat: integrate image search results into Aria's context with IMAGE_REF tokens"
```

---

### Task 8: Chat Image Rendering (render_image_refs)

**Files:**
- Modify: `core/agent.py:4433-4439` (where answer is saved as ChatMessage)
- Test: `tests/test_documents.py`

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestRenderImageRefs:
    def test_replaces_image_ref_with_html(self, org_alpha, user_alpha_owner):
        from core.models import DocumentImage
        from core.views import render_image_refs

        fake_file = SimpleUploadedFile('test.pdf', b'%PDF', content_type='application/pdf')
        doc = Document.objects.create(
            title='Stage Guide', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100, is_processed=True,
        )
        fake_img = SimpleUploadedFile('stage.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        img = DocumentImage.objects.create(
            document=doc, organization=org_alpha,
            image_file=fake_img, source_type='pdf_extract',
            description='A stage plot diagram',
        )

        content = f'Here is the stage layout:\n\n[IMAGE_REF:{img.pk}]'
        result = render_image_refs(content, org_alpha)

        assert '[IMAGE_REF:' not in result
        assert '<img' in result
        assert 'src="' in result
        assert 'Stage Guide' in result  # Caption

    def test_strips_invalid_image_ref(self, org_alpha):
        from core.views import render_image_refs
        content = 'Here is the image:\n\n[IMAGE_REF:99999]'
        result = render_image_refs(content, org_alpha)

        assert '[IMAGE_REF:' not in result
        assert '<img' not in result

    def test_strips_cross_org_image_ref(self, org_alpha, org_beta, user_beta_owner):
        from core.models import DocumentImage
        from core.views import render_image_refs

        # Create image in org_beta
        fake_file = SimpleUploadedFile('test.pdf', b'%PDF', content_type='application/pdf')
        doc = Document.objects.create(
            title='Beta Doc', file=fake_file,
            organization=org_beta, uploaded_by=user_beta_owner,
            file_type='pdf', file_size=100, is_processed=True,
        )
        fake_img = SimpleUploadedFile('b.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        img = DocumentImage.objects.create(
            document=doc, organization=org_beta,
            image_file=fake_img, source_type='pdf_extract',
        )

        # Try to reference from org_alpha - should be stripped
        content = f'[IMAGE_REF:{img.pk}]'
        result = render_image_refs(content, org_alpha)
        assert '<img' not in result

    def test_no_image_refs_passes_through(self, org_alpha):
        from core.views import render_image_refs
        content = 'Just a normal response with no images.'
        result = render_image_refs(content, org_alpha)
        assert result == content

    def test_multiple_image_refs(self, org_alpha, user_alpha_owner):
        from core.models import DocumentImage
        from core.views import render_image_refs

        fake_file = SimpleUploadedFile('test.pdf', b'%PDF', content_type='application/pdf')
        doc = Document.objects.create(
            title='Guide', file=fake_file,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100, is_processed=True,
        )
        imgs = []
        for i in range(2):
            fake_img = SimpleUploadedFile(f'img{i}.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
            imgs.append(DocumentImage.objects.create(
                document=doc, organization=org_alpha,
                image_file=fake_img, source_type='pdf_extract',
                description=f'Image {i}',
            ))

        content = f'First image:\n[IMAGE_REF:{imgs[0].pk}]\nSecond:\n[IMAGE_REF:{imgs[1].pk}]'
        result = render_image_refs(content, org_alpha)
        assert result.count('<img') == 2
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestRenderImageRefs -v`
Expected: FAIL with `ImportError: cannot import name 'render_image_refs'`

**Step 3: Implement render_image_refs in views.py**

Add to `core/views.py` (near the top, after imports):

```python
import re


def render_image_refs(content: str, organization) -> str:
    """Replace [IMAGE_REF:id] tokens with HTML img tags.

    Args:
        content: The response text containing IMAGE_REF tokens.
        organization: Organization to scope image lookups (security).

    Returns:
        Content with IMAGE_REF tokens replaced by HTML img elements.
    """
    from .models import DocumentImage

    def replace_match(match):
        image_id = int(match.group(1))
        try:
            image = DocumentImage.objects.get(
                id=image_id,
                organization=organization,
            )
            alt_text = (image.description[:100] + '...') if len(image.description) > 100 else image.description
            doc_title = image.document.title if image.document else 'Uploaded image'
            return (
                f'<div class="my-3">'
                f'<a href="{image.image_file.url}" target="_blank">'
                f'<img src="{image.image_file.url}" '
                f'alt="{alt_text}" '
                f'class="rounded-lg max-w-sm max-h-64 cursor-pointer hover:opacity-90" '
                f'loading="lazy">'
                f'</a>'
                f'<p class="text-xs text-gray-400 mt-1">'
                f'From: {doc_title}'
                f'</p>'
                f'</div>'
            )
        except DocumentImage.DoesNotExist:
            return ''

    return re.sub(r'\[IMAGE_REF:(\d+)\]', replace_match, content)
```

**Step 4: Wire render_image_refs into query_agent**

In `core/agent.py`, at line 4438 where `answer` is saved as a ChatMessage, add the render call just before the save. Replace lines 4433-4439:

```python
    # Render any image references in the answer
    from .views import render_image_refs
    if organization:
        answer = render_image_refs(answer, organization)

    ChatMessage.objects.create(
        user=user,
        organization=organization,
        session_id=session_id,
        role='assistant',
        content=answer
    )
```

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestRenderImageRefs -v`
Expected: All 5 tests PASS

**Step 6: Commit**

```bash
git add core/views.py core/agent.py tests/test_documents.py
git commit -m "feat: render IMAGE_REF tokens as inline thumbnails in chat responses"
```

---

### Task 9: Template Updates (Document List + Detail)

**Files:**
- Modify: `templates/core/documents/document_list.html`
- Modify: `templates/core/documents/document_detail.html`
- Modify: `core/views.py` (document_detail view to pass image data)

**Step 1: Write the failing test**

Add to `tests/test_documents.py`:

```python
@pytest.mark.django_db
class TestImageDocumentTemplates:
    @patch('core.document_processing.describe_image_with_vision')
    @patch('core.document_processing.get_embedding')
    def test_document_list_shows_image_icon(self, mock_embed, mock_describe, client_alpha, org_alpha, user_alpha_owner):
        mock_describe.return_value = {'description': 'Photo', 'ocr_text': ''}
        mock_embed.return_value = [0.1] * 1536

        fake_img = SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        Document.objects.create(
            title='Team Photo', file=fake_img,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='image', file_size=100, is_processed=True,
        )

        response = client_alpha.get('/documents/')
        content = response.content.decode()
        assert 'IMAGE' in content or 'Team Photo' in content

    @patch('core.document_processing.describe_image_with_vision')
    @patch('core.document_processing.get_embedding')
    def test_document_detail_shows_image_preview(self, mock_embed, mock_describe, client_alpha, org_alpha, user_alpha_owner):
        from core.models import DocumentImage

        mock_describe.return_value = {'description': 'A stage layout', 'ocr_text': ''}
        mock_embed.return_value = [0.1] * 1536

        fake_img = SimpleUploadedFile('stage.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        doc = Document.objects.create(
            title='Stage Layout', file=fake_img,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='image', file_size=100, is_processed=True,
        )
        DocumentImage.objects.create(
            document=doc, organization=org_alpha,
            image_file=fake_img, source_type='standalone',
            description='A stage layout diagram',
        )

        response = client_alpha.get(f'/documents/{doc.pk}/')
        content = response.content.decode()
        assert '<img' in content or 'stage' in content.lower()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_documents.py::TestImageDocumentTemplates -v`
Expected: May PASS partially (list shows file type as "IMAGE") but detail won't show `<img>`.

**Step 3: Update document_list.html**

In `templates/core/documents/document_list.html`, replace the icon block (lines 48-56) with:

```html
                {% if doc.file_type == 'pdf' %}
                <svg class="w-8 h-8 text-red-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"></path>
                </svg>
                {% elif doc.file_type == 'image' %}
                <svg class="w-8 h-8 text-green-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                </svg>
                {% else %}
                <svg class="w-8 h-8 text-blue-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                </svg>
                {% endif %}
```

**Step 4: Update document_detail.html**

In `templates/core/documents/document_detail.html`, add an image preview section before the extracted text block (before line 88):

```html
    {% if document.file_type == 'image' %}
    <div class="bg-ch-dark rounded-lg p-6 mb-6">
        <h3 class="text-gray-400 font-medium mb-4">Image Preview</h3>
        <a href="{{ document.file.url }}" target="_blank">
            <img src="{{ document.file.url }}" alt="{{ document.title }}"
                 class="rounded-lg max-w-full max-h-96 cursor-pointer hover:opacity-90" loading="lazy">
        </a>
        {% if document_images %}
        {% for img in document_images %}
        {% if img.description %}
        <div class="mt-4">
            <h4 class="text-sm text-gray-500 mb-1">AI Description</h4>
            <p class="text-gray-300 text-sm">{{ img.description }}</p>
        </div>
        {% endif %}
        {% if img.ocr_text %}
        <div class="mt-2">
            <h4 class="text-sm text-gray-500 mb-1">Text Found in Image</h4>
            <p class="text-gray-300 text-sm">{{ img.ocr_text }}</p>
        </div>
        {% endif %}
        {% endfor %}
        {% endif %}
    </div>
    {% endif %}

    {% if document.file_type == 'pdf' and document_images %}
    <div class="bg-ch-dark rounded-lg p-6 mb-6">
        <h3 class="text-gray-400 font-medium mb-4">Extracted Images ({{ document_images|length }})</h3>
        <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {% for img in document_images %}
            <div class="bg-ch-gray rounded-lg p-3">
                <a href="{{ img.image_file.url }}" target="_blank">
                    <img src="{{ img.image_file.url }}" alt="{{ img.description|truncatewords:15 }}"
                         class="rounded w-full max-h-48 object-contain cursor-pointer hover:opacity-90" loading="lazy">
                </a>
                {% if img.page_number %}
                <p class="text-xs text-gray-500 mt-2">Page {{ img.page_number }}</p>
                {% endif %}
                {% if img.description %}
                <p class="text-xs text-gray-400 mt-1 line-clamp-2">{{ img.description }}</p>
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endif %}
```

**Step 5: Update document_detail view to pass images**

In `core/views.py`, in the `document_detail` function (around line 5011), add `document_images` to the context. Find the `render()` call and add:

```python
    from .models import DocumentImage
    document_images = DocumentImage.objects.filter(document=document)
```

Pass `document_images` in the template context dict.

**Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/test_documents.py::TestImageDocumentTemplates -v`
Expected: All 2 tests PASS

**Step 7: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (existing 394 + new tests)

**Step 8: Commit**

```bash
git add templates/core/documents/document_list.html templates/core/documents/document_detail.html core/views.py tests/test_documents.py
git commit -m "feat: update document templates with image icons, previews, and extracted image gallery"
```

---

### Task 10: Full Integration Test and Final Cleanup

**Files:**
- All modified files
- Test: `tests/test_documents.py`

**Step 1: Run the full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS, no regressions

**Step 2: Check for import issues**

Run: `python manage.py check`
Expected: No issues found

**Step 3: Verify migrations are clean**

Run: `python manage.py makemigrations --check`
Expected: No new migrations needed (all already created in Task 1)

**Step 4: Manual verification checklist**

- [ ] `DocumentImage` model exists and is migrated
- [ ] `Document.FILE_TYPE_CHOICES` includes `('image', 'Image')`
- [ ] Upload form accepts `.png,.jpg,.jpeg` files
- [ ] Upload help text mentions PNG/JPG/JPEG
- [ ] Document list shows green image icon for image documents
- [ ] Document detail shows image preview for image documents
- [ ] Document detail shows extracted images gallery for PDFs with images
- [ ] `describe_image_with_vision()` calls Claude Vision API
- [ ] `extract_images_from_pdf()` extracts images, filters small ones, caps at 20
- [ ] `process_document()` handles images for both PDFs and standalone uploads
- [ ] `search_similar_images()` returns org-scoped results
- [ ] `_build_image_context()` creates `[IMAGE_REF:id]` tokens
- [ ] `render_image_refs()` replaces tokens with `<img>` HTML
- [ ] Cross-organization image refs are silently stripped
- [ ] Vision API failures don't break document processing

**Step 5: Final commit if any cleanup needed**

```bash
git add -A
git commit -m "chore: final cleanup for Knowledge Base image support"
```
