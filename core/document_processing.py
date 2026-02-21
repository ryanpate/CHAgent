"""
Document processing module for the Knowledge Base feature.
Handles text extraction from uploaded files and chunking for embedding.
"""
import logging
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
