"""Tests for the Knowledge Base document upload feature."""
import pytest
from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import DocumentCategory, Document, DocumentChunk, DocumentImage


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


@pytest.mark.django_db
class TestDocumentImageModel:
    def test_create_image_from_pdf(self, org_alpha, user_alpha_owner):
        fake_pdf = SimpleUploadedFile('test.pdf', b'%PDF-fake', content_type='application/pdf')
        doc = Document.objects.create(
            title='Stage Plot', file=fake_pdf,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100,
        )
        fake_img = SimpleUploadedFile('stage.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
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
        fake_img = SimpleUploadedFile('diagram.jpg', b'\xff\xd8\xff' + b'\x00' * 100, content_type='image/jpeg')
        doc = Document.objects.create(
            title='Equipment Diagram', file=fake_img,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='image', file_size=200,
        )
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
        fake_pdf = SimpleUploadedFile('test.pdf', b'%PDF-fake', content_type='application/pdf')
        doc = Document.objects.create(
            title='Stage Plot', file=fake_pdf,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=100,
        )
        fake_img = SimpleUploadedFile('img.png', b'\x89PNG\r\n\x1a\n' + b'\x00' * 100, content_type='image/png')
        img = DocumentImage.objects.create(
            document=doc, organization=org_alpha,
            image_file=fake_img, original_filename='img.png',
            source_type='pdf_extract',
        )
        assert 'Stage Plot' in str(img)

    def test_image_organization_isolation(self, org_alpha, org_beta, user_alpha_owner, user_beta_owner):
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


@pytest.mark.django_db
class TestExtractImagesFromPdf:
    def test_extract_no_images_returns_empty(self, tmp_path):
        """A text-only PDF yields no images."""
        from core.document_processing import extract_images_from_pdf
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

    def test_small_image_kept_if_one_dimension_large(self):
        """An image like 10x800 should be kept because one dimension is >= min."""
        from core.document_processing import _filter_small_images
        images = [
            {'image_bytes': b'fake', 'width': 10, 'height': 800, 'page_number': 1, 'name': 'banner.png'},
        ]
        filtered = _filter_small_images(images, min_dimension=50)
        assert len(filtered) == 1
        assert filtered[0]['name'] == 'banner.png'

    def test_max_images_cap(self, tmp_path):
        """No more than 20 images should be returned."""
        from core.document_processing import _cap_images
        images = [{'image_bytes': b'fake', 'page_number': i, 'name': f'img{i}.png'} for i in range(30)]
        capped = _cap_images(images, max_images=20)
        assert len(capped) == 20

    def test_cap_images_no_cap_needed(self):
        """When fewer images than max, all are returned."""
        from core.document_processing import _cap_images
        images = [{'image_bytes': b'fake', 'page_number': i, 'name': f'img{i}.png'} for i in range(5)]
        capped = _cap_images(images, max_images=20)
        assert len(capped) == 5


from unittest.mock import patch, MagicMock
from core.document_processing import process_document


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


@pytest.mark.django_db
class TestProcessDocumentImages:
    @patch('core.document_processing.describe_image_with_vision')
    @patch('core.document_processing.get_embedding')
    @patch('core.document_processing.extract_images_from_pdf')
    def test_process_pdf_with_images(self, mock_extract, mock_embed, mock_describe, org_alpha, user_alpha_owner, tmp_path):
        from core.models import DocumentImage
        from django.core.files.uploadedfile import SimpleUploadedFile

        fake_pdf = SimpleUploadedFile('test.pdf', b'%PDF-fake-content', content_type='application/pdf')
        doc = Document.objects.create(
            title='Stage Guide', file=fake_pdf,
            organization=org_alpha, uploaded_by=user_alpha_owner,
            file_type='pdf', file_size=500,
        )

        mock_extract.return_value = [{
            'image_bytes': b'\x89PNG\r\n\x1a\n' + b'\x00' * 100,
            'page_number': 2,
            'name': 'stage_plot.png',
            'width': 800,
            'height': 600,
        }]
        mock_describe.return_value = {
            'description': 'A stage plot diagram',
            'ocr_text': 'Monitor 1',
        }
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

        assert response.status_code == 302
        doc = Document.objects.filter(title='Stage Layout').first()
        assert doc is not None
        assert doc.file_type == 'image'
        images = DocumentImage.objects.filter(document=doc)
        assert images.count() == 1
        assert images.first().source_type == 'standalone'

    def test_upload_unsupported_type_rejected(self, client_alpha):
        fake_file = SimpleUploadedFile('doc.docx', b'fake', content_type='application/vnd.openxmlformats')
        response = client_alpha.post('/documents/upload/', {'file': fake_file})

        assert response.status_code == 200
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

        query_embedding = [0.0] + [1.0] + [0.0] * 1534
        results = search_similar_images(query_embedding, org_alpha, limit=3, threshold=0.3)
        assert len(results) == 0


@pytest.mark.django_db
class TestAgentImageIntegration:
    def test_image_context_built_correctly(self):
        """Verify that _build_image_context creates proper context with IMAGE_REF tokens."""
        from core.agent import _build_image_context

        image_results = [{
            'description': 'A stage plot showing positions',
            'ocr_text': 'Monitor 1',
            'image_url': '/media/document_images/2026/02/stage.png',
            'document_title': 'Stage Guide',
            'document_id': 1,
            'image_id': 42,
            'similarity': 0.85,
        }]

        context = _build_image_context(image_results)

        assert '[IMAGE_REF:42]' in context
        assert 'Stage Guide' in context
        assert 'stage plot' in context.lower()
        assert 'Monitor 1' in context
        assert '[KNOWLEDGE BASE IMAGES]' in context

    def test_image_context_empty_results(self):
        from core.agent import _build_image_context
        assert _build_image_context([]) == ''

    def test_image_context_no_ocr_text(self):
        from core.agent import _build_image_context
        result = _build_image_context([{
            'description': 'A photo',
            'ocr_text': '',
            'image_url': '/media/img.png',
            'document_title': 'Photos',
            'document_id': 1,
            'image_id': 10,
            'similarity': 0.7,
        }])
        assert 'Text in image' not in result
        assert '[IMAGE_REF:10]' in result


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
        assert 'Stage Guide' in result

    def test_strips_invalid_image_ref(self, org_alpha):
        from core.views import render_image_refs
        content = 'Here is the image:\n\n[IMAGE_REF:99999]'
        result = render_image_refs(content, org_alpha)

        assert '[IMAGE_REF:' not in result
        assert '<img' not in result

    def test_strips_cross_org_image_ref(self, org_alpha, org_beta, user_beta_owner):
        from core.models import DocumentImage
        from core.views import render_image_refs

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
        # The green image icon SVG should appear for image file types
        assert 'text-green-400' in content

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
        # Image preview section should contain an <img> tag and the AI description
        assert '<img' in content
        assert 'Image Preview' in content
        assert 'A stage layout diagram' in content
