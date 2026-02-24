"""
Document processing module for the Knowledge Base feature.
Handles text extraction from uploaded files and chunking for embedding.
"""
import logging
from typing import BinaryIO

import anthropic

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

    if len(text) <= chunk_size:
        return [{'content': text, 'chunk_index': 0}]

    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size

        if end < len(text):
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

        chunks = chunk_text(extracted_text)

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


def extract_images_from_pdf(pdf_path: str) -> list[dict]:
    """Extract embedded images from a PDF file.

    Uses pypdf's page.images API to iterate over images in each page,
    then uses Pillow to determine dimensions. Images that are too small
    are filtered out and the total count is capped.

    Args:
        pdf_path: Path to a PDF file on disk.

    Returns:
        List of dicts with keys: image_bytes, page_number, name, width, height.
    """
    from pypdf import PdfReader
    from PIL import Image
    from io import BytesIO

    reader = PdfReader(pdf_path)
    images: list[dict] = []

    for page_num, page in enumerate(reader.pages, start=1):
        try:
            page_images = page.images
        except Exception as e:
            logger.warning(f'Could not access images on page {page_num}: {e}')
            continue

        for img in page_images:
            try:
                raw_bytes = img.data
                pil_image = Image.open(BytesIO(raw_bytes))
                width, height = pil_image.size
                images.append({
                    'image_bytes': raw_bytes,
                    'page_number': page_num,
                    'name': img.name,
                    'width': width,
                    'height': height,
                })
            except Exception as e:
                logger.warning(
                    f'Skipping image "{getattr(img, "name", "unknown")}" '
                    f'on page {page_num}: {e}'
                )
                continue

    images = _filter_small_images(images)
    images = _cap_images(images)
    return images


def _filter_small_images(
    images: list[dict], min_dimension: int = 50
) -> list[dict]:
    """Remove images where BOTH width AND height are below min_dimension.

    An image that is 10x800 is kept because one dimension exceeds the
    threshold.

    Args:
        images: List of image dicts with 'width' and 'height' keys.
        min_dimension: Minimum size threshold in pixels.

    Returns:
        Filtered list of image dicts.
    """
    return [
        img for img in images
        if img.get('width', 0) >= min_dimension
        or img.get('height', 0) >= min_dimension
    ]


def _cap_images(images: list[dict], max_images: int = 20) -> list[dict]:
    """Return at most the first max_images images.

    Logs a warning if the list was truncated.

    Args:
        images: List of image dicts.
        max_images: Maximum number of images to return.

    Returns:
        Truncated list of image dicts.
    """
    if len(images) > max_images:
        logger.warning(
            f'Document contains {len(images)} images; '
            f'capping to {max_images}.'
        )
        return images[:max_images]
    return images


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
