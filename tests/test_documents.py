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
