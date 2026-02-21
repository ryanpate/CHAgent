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
        from pypdf import PdfWriter
        from io import BytesIO

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
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
        sentences = [f'Sentence number {i} is here.' for i in range(100)]
        text = ' '.join(sentences)
        chunks = chunk_text(text, chunk_size=200, overlap=30)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk['content']) > 0
            assert 'chunk_index' in chunk

    def test_chunk_preserves_all_content(self):
        sentences = [f'Sentence {i}.' for i in range(50)]
        text = ' '.join(sentences)
        chunks = chunk_text(text, chunk_size=100, overlap=20)
        for sentence in sentences:
            found = any(sentence in c['content'] for c in chunks)
            assert found, f'{sentence} not found in any chunk'

    def test_chunk_empty_text(self):
        chunks = chunk_text('', chunk_size=500, overlap=50)
        assert len(chunks) == 0


try:
    from core.embeddings import search_similar_documents
    _has_search_similar_documents = True
except ImportError:
    _has_search_similar_documents = False


@pytest.mark.django_db
@pytest.mark.skipif(not _has_search_similar_documents, reason='search_similar_documents not yet implemented')
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
