"""
Tests for ProcessingService.

Tests the PDF processing, OCR, and analysis functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from thoth.services.processing_service import ProcessingService
from thoth.utilities.models import AnalysisResponse


class TestProcessingService:
    """Test suite for ProcessingService."""

    @pytest.fixture
    def processing_service(self):
        """Create a ProcessingService instance for testing."""
        service = ProcessingService()
        return service

    def test_ocr_convert_success(
        self,
        processing_service,
        sample_pdf_path,
        temp_workspace,
    ):
        """Test successful OCR conversion."""
        # Create mock mistral client
        mock_mistral = MagicMock()

        # Mock file upload
        mock_file = MagicMock()
        mock_file.id = 'file-123'
        mock_mistral.files.upload.return_value = mock_file

        # Mock signed URL
        mock_signed_url = MagicMock()
        mock_signed_url.url = 'https://example.com/signed-url'
        mock_mistral.files.get_signed_url.return_value = mock_signed_url

        # Mock OCR response
        mock_page = MagicMock()
        mock_page.markdown = '# Test Document\n\nThis is test content.'
        mock_page.images = []

        mock_ocr_response = MagicMock()
        mock_ocr_response.pages = [mock_page]

        mock_mistral.ocr.process.return_value = mock_ocr_response

        # Set the mock on the private attribute
        processing_service._mistral_client = mock_mistral

        # Process PDF
        markdown_path, no_images_path = processing_service.ocr_convert(
            sample_pdf_path, output_dir=temp_workspace
        )

        assert markdown_path.exists()
        assert no_images_path.exists()
        assert markdown_path.suffix == '.md'
        assert no_images_path.suffix == '.md'

    def test_ocr_convert_failure(self, processing_service, sample_pdf_path):
        """Test OCR conversion failure handling."""
        # Create mock mistral client
        mock_mistral = MagicMock()
        mock_mistral.files.upload.side_effect = Exception('Upload failed')

        # Set the mock on the private attribute
        processing_service._mistral_client = mock_mistral

        # Process should raise exception
        with pytest.raises(Exception) as exc_info:
            processing_service.ocr_convert(sample_pdf_path)

        assert 'OCR conversion' in str(exc_info.value)

    def test_analyze_content_with_path(
        self,
        processing_service,
        sample_markdown_path,
        sample_analysis_response,
    ):
        """Test content analysis with file path."""
        # Create mock processor
        mock_processor = MagicMock()
        mock_processor.analyze_content.return_value = sample_analysis_response

        # Set the mock on the private attribute
        processing_service._llm_processor = mock_processor

        # Analyze content
        analysis = processing_service.analyze_content(sample_markdown_path)

        assert analysis == sample_analysis_response
        mock_processor.analyze_content.assert_called_once()

    def test_analyze_content_with_string(
        self,
        processing_service,
        sample_analysis_response,
    ):
        """Test content analysis with string content."""
        content = 'Sample paper content for analysis'

        # Create mock processor
        mock_processor = MagicMock()
        mock_processor.analyze_content.return_value = sample_analysis_response

        # Set the mock on the private attribute
        processing_service._llm_processor = mock_processor

        analysis = processing_service.analyze_content(content)

        assert analysis == sample_analysis_response
        mock_processor.analyze_content.assert_called_once_with(
            content, force_processing_strategy=None
        )

    def test_extract_metadata_basic(self, processing_service):
        """Test basic metadata extraction."""
        content = """# Test Paper Title

Authors: John Doe, Jane Smith
Date: 2023-01-01

This is the content of the paper.
        """

        metadata = processing_service.extract_metadata(content, metadata_type='basic')

        assert metadata['title'] == 'Test Paper Title'
        assert 'John Doe' in metadata.get('authors', [])
        assert 'Jane Smith' in metadata.get('authors', [])
        assert metadata.get('date') == '2023-01-01'

    def test_validate_analysis_valid(
        self, processing_service, sample_analysis_response
    ):
        """Test validation of a valid analysis."""
        is_valid, missing = processing_service.validate_analysis(
            sample_analysis_response
        )

        assert is_valid is True
        assert len(missing) == 0

    def test_validate_analysis_missing_fields(self, processing_service):
        """Test validation with missing required fields."""
        # Create analysis with missing abstract
        analysis = AnalysisResponse(
            summary='Test summary',
            key_points='Test key points',
        )

        is_valid, missing = processing_service.validate_analysis(
            analysis, required_fields=['abstract', 'summary', 'key_points']
        )

        assert is_valid is False
        assert 'abstract' in missing
        assert 'summary' not in missing  # Has value
        assert 'key_points' not in missing  # Has value

    def test_get_processing_stats(self, processing_service):
        """Test getting processing statistics."""
        stats = processing_service.get_processing_stats()

        assert 'ocr_available' in stats
        assert 'llm_model' in stats
        assert 'max_context_length' in stats
        assert 'chunk_size' in stats

    def test_process_pdf_to_markdown(
        self,
        processing_service,
        sample_pdf_path,
        temp_workspace,
    ):
        """Test the process_pdf_to_markdown convenience method."""
        # Mock OCR conversion
        with patch.object(processing_service, 'ocr_convert') as mock_ocr:
            markdown_path = temp_workspace / 'test.md'
            no_images_path = temp_workspace / 'test_no_images.md'
            mock_ocr.return_value = (markdown_path, no_images_path)

            # Create the files
            markdown_path.write_text('# Test')
            no_images_path.write_text('# Test')

            # Process PDF
            pdf_out, markdown_out = processing_service.process_pdf_to_markdown(
                sample_pdf_path, output_dir=temp_workspace
            )

            assert pdf_out.exists()
            assert markdown_out == no_images_path
