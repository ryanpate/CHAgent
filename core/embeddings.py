"""
Embeddings module for semantic search over interactions.
Uses OpenAI text-embedding-3-small for cost-effective embeddings.
"""
import logging
from typing import Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Try to import OpenAI, handle gracefully if not available
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    OpenAI = None


def get_openai_client():
    """Get OpenAI client instance."""
    if not HAS_OPENAI:
        logger.warning("OpenAI not installed. Embeddings will not be available.")
        return None

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        logger.warning("OPENAI_API_KEY not set. Embeddings will not be available.")
        return None

    return OpenAI(api_key=api_key)


def get_embedding(text: str) -> Optional[list[float]]:
    """
    Generate embedding vector for text using OpenAI's text-embedding-3-small model.

    Uses Django's cache framework to avoid duplicate API calls for the same text.
    Cache key is based on a SHA-256 hash of the input text with a 24-hour TTL.

    Args:
        text: The text to generate embeddings for.

    Returns:
        A list of floats representing the embedding vector, or None if unavailable.
    """
    import hashlib
    from django.core.cache import cache

    # Check cache first
    text_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    cache_key = f"emb:{text_hash}"
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Embedding cache hit for key {cache_key}")
        return cached

    client = get_openai_client()
    if not client:
        return None

    try:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        embedding = response.data[0].embedding
        # Cache for 24 hours
        cache.set(cache_key, embedding, timeout=86400)
        return embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        return None


def search_similar(query_embedding: list[float], limit: int = 10, organization=None):
    """
    Find interactions most similar to query using cosine similarity.

    For SQLite, this uses a simple Python-based cosine similarity calculation.
    For PostgreSQL with pgvector, this would use the database's built-in similarity search.

    Args:
        query_embedding: The embedding vector to search against.
        limit: Maximum number of results to return.
        organization: Organization to scope the search (required for multi-tenant isolation).

    Returns:
        List of Interaction objects ordered by similarity.
    """
    from .models import Interaction
    import math

    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if not vec1 or not vec2:
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    # Get interactions with embeddings, scoped to organization
    interactions = Interaction.objects.exclude(embedding_json__isnull=True)
    if organization:
        interactions = interactions.filter(organization=organization)

    # Calculate similarities and sort
    scored_interactions = []
    for interaction in interactions:
        if interaction.embedding_json:
            similarity = cosine_similarity(query_embedding, interaction.embedding_json)
            scored_interactions.append((interaction, similarity))

    # Sort by similarity (highest first)
    scored_interactions.sort(key=lambda x: x[1], reverse=True)

    # Return top N interactions
    return [item[0] for item in scored_interactions[:limit]]


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

    def cosine_similarity(vec1, vec2):
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


def search_similar_posts(query_embedding: list[float], organization=None, exclude_post_id=None, limit: int = 3, threshold: float = 0.3):
    """
    Find creative posts most similar to query using cosine similarity.

    Returns: List of dicts with keys: 'post_id', 'title', 'post_type', 'similarity'
    """
    import json
    import math

    from core.models import CreativePost

    posts = CreativePost.objects.filter(
        status='published',
    ).exclude(embedding_json__isnull=True).exclude(embedding_json='')

    if organization:
        posts = posts.filter(organization=organization)
    if exclude_post_id:
        posts = posts.exclude(pk=exclude_post_id)

    results = []
    for post in posts:
        try:
            post_embedding = json.loads(post.embedding_json)
        except (json.JSONDecodeError, TypeError):
            continue

        # Cosine similarity
        dot_product = sum(a * b for a, b in zip(query_embedding, post_embedding))
        norm_a = math.sqrt(sum(a * a for a in query_embedding))
        norm_b = math.sqrt(sum(b * b for b in post_embedding))
        if norm_a == 0 or norm_b == 0:
            continue
        similarity = dot_product / (norm_a * norm_b)

        if similarity >= threshold:
            results.append({
                'post_id': post.pk,
                'title': post.title,
                'post_type': post.post_type,
                'similarity': similarity,
            })

    results.sort(key=lambda x: x['similarity'], reverse=True)
    return results[:limit]
