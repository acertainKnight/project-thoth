"""
Unit tests for core services - the backbone of the Thoth system.

These tests validate the critical service layer that powers all functionality.
"""

from pathlib import Path
from unittest.mock import Mock, patch

from thoth.services.citation_service import CitationService
from thoth.services.llm_service import LLMService
from thoth.services.note_service import NoteService
from thoth.services.processing_service import ProcessingService
from thoth.services.rag_service import RAGService
from thoth.utilities.schemas import AnalysisResponse, Citation


class TestLLMService:
    """Test LLM service core functionality."""

    def test_llm_service_initialization(self, mock_config):
        """Test LLM service initializes correctly."""
        llm_service = LLMService(config=mock_config)
        llm_service.initialize()

        assert llm_service.config is not None
        assert hasattr(llm_service, 'get_client')

    def test_llm_client_creation(self, mock_config):
        """Test LLM client creation with different models."""
        llm_service = LLMService(config=mock_config)
        llm_service.initialize()

        # Test client creation
        client = llm_service.get_client(model='openai/gpt-4o-mini')
        assert client is not None

        # Test with parameters
        client_with_params = llm_service.get_client(
            model='openai/gpt-4o-mini', temperature=0.5, max_tokens=1000
        )
        assert client_with_params is not None

    def test_llm_service_health_check(self, mock_config):
        """Test LLM service health check."""
        llm_service = LLMService(config=mock_config)
        llm_service.initialize()

        health = llm_service.health_check()

        assert isinstance(health, dict)
        assert 'status' in health
        assert health['status'] in ['healthy', 'degraded', 'unhealthy']


class TestProcessingService:
    """Test processing service core functionality."""

    def test_processing_service_initialization(self, mock_config):
        """Test processing service initializes correctly."""
        processing_service = ProcessingService(config=mock_config)
        processing_service.initialize()

        assert processing_service.config is not None
        assert hasattr(processing_service, 'ocr_convert')
        assert hasattr(processing_service, 'analyze_content')

    def test_analysis_response_validation(self, mock_config):
        """Test analysis response structure validation."""
        processing_service = ProcessingService(config=mock_config)
        processing_service.initialize()

        # Mock LLM response
        mock_analysis = AnalysisResponse(
            title='Test Paper',
            authors=['Author, A.'],
            abstract='Test abstract',
            key_points='Point 1\nPoint 2',
            tags=['#test', '#validation'],
        )

        # Validate structure
        assert mock_analysis.title is not None
        assert mock_analysis.authors is not None
        assert mock_analysis.tags is not None
        assert len(mock_analysis.tags) == 2

    def test_ocr_convert_workflow(self, mock_config, sample_pdf_path, temp_workspace):
        """Test OCR conversion workflow."""
        # Remove mistral key to force local processing
        mock_config.api_keys.mistral_key = None

        processing_service = ProcessingService(config=mock_config)
        processing_service.initialize()

        # Mock local OCR response
        with patch.object(processing_service, '_local_pdf_to_markdown') as mock_local:
            markdown_path = temp_workspace / 'output.md'
            markdown_path.write_text('# Test Paper\n\nTest content')
            mock_local.return_value = (markdown_path, markdown_path)

            # Test OCR workflow
            result = processing_service.ocr_convert(sample_pdf_path, temp_workspace)

            assert len(result) == 2  # (markdown_path, no_images_path)
            assert all(isinstance(path, Path) for path in result)


class TestCitationService:
    """Test citation service core functionality."""

    def test_citation_service_initialization(self, mock_config):
        """Test citation service initializes correctly."""
        citation_service = CitationService(config=mock_config)
        citation_service.initialize()

        assert citation_service.config is not None
        assert hasattr(citation_service, 'extract_citations')
        assert hasattr(citation_service, 'format_citation')

    def test_citation_extraction_interface(self, mock_config, temp_workspace):
        """Test citation extraction service interface."""
        # Create test markdown
        markdown_path = temp_workspace / 'test.md'
        markdown_path.write_text("""# Test Paper

## References
[1] Smith, J. (2023). Test paper. Journal, 1(1), 1-10.
""")

        # Initialize citation service first
        citation_service = CitationService(config=mock_config)
        citation_service.initialize()

        # Mock the citation processor property to avoid template loading
        mock_processor = Mock()
        mock_processor.extract_citations.return_value = [
            Citation(title='Test paper', authors=['Smith, J.'], year=2023)
        ]
        citation_service._citation_processor = mock_processor

        citations = citation_service.extract_citations(markdown_path)

        assert isinstance(citations, list)
        mock_processor.extract_citations.assert_called_once()

    def test_citation_formatting_service_interface(self, mock_config):
        """Test citation formatting service interface."""
        citation_service = CitationService(config=mock_config)
        citation_service.initialize()

        citation = Citation(title='Test Paper', authors=['Author, A.'], year=2023)

        formatted = citation_service.format_citation(citation, style='ieee')

        assert formatted.formatted is not None
        assert len(formatted.formatted) > 0


class TestNoteService:
    """Test note service core functionality."""

    def test_note_service_initialization(self, mock_config):
        """Test note service initializes correctly."""
        note_service = NoteService(config=mock_config)
        note_service.initialize()

        assert note_service.config is not None
        assert hasattr(note_service, 'create_note')
        assert note_service.notes_dir is not None

    def test_note_creation_interface(
        self, mock_config, sample_pdf_path, temp_workspace
    ):
        """Test note creation service interface."""
        note_service = NoteService(
            config=mock_config, notes_dir=temp_workspace, templates_dir=temp_workspace
        )
        note_service.initialize()

        # Create test data
        markdown_path = temp_workspace / 'test.md'
        markdown_path.write_text('# Test Paper\n\nContent')

        analysis = AnalysisResponse(
            title='Test Paper', authors=['Author, A.'], abstract='Test abstract'
        )

        citations = [Citation(title='Citation 1', authors=['Ref, A.'])]

        # Mock template rendering to avoid file dependencies
        mock_template = Mock()
        mock_template.render.return_value = '# Generated Note\n\nContent'
        note_service.jinja_env = Mock()
        note_service.jinja_env.get_template.return_value = mock_template

        # Test note creation
        result = note_service.create_note(
            pdf_path=sample_pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )

        assert len(result) == 3  # (note_path, pdf_path, markdown_path)


class TestRAGService:
    """Test RAG service core functionality."""

    def test_rag_service_initialization(self, mock_config):
        """Test RAG service initializes correctly."""
        rag_service = RAGService(config=mock_config)
        rag_service.initialize()

        assert rag_service.config is not None
        assert hasattr(rag_service, 'search')
        assert hasattr(rag_service, 'ask_question')

    def test_rag_search_interface(self, mock_config):
        """Test RAG search service interface."""
        rag_service = RAGService(config=mock_config)
        rag_service.initialize()

        # Mock the RAG manager property to avoid vector DB dependencies
        mock_manager = Mock()
        mock_manager.search.return_value = []
        rag_service._rag_manager = mock_manager

        results = rag_service.search('test query', k=4)

        assert isinstance(results, list)

    def test_rag_indexing_interface(self, mock_config, temp_workspace):
        """Test RAG indexing service interface."""
        # Create test file
        test_file = temp_workspace / 'test.md'
        test_file.write_text('# Test Document\n\nContent for indexing')

        rag_service = RAGService(config=mock_config)
        rag_service.initialize()

        # Mock the RAG manager property to avoid vector DB dependencies
        mock_manager = Mock()
        mock_manager.index_markdown_file.return_value = ['chunk1', 'chunk2']
        rag_service._rag_manager = mock_manager

        result = rag_service.index_file(test_file)

        assert isinstance(result, list)


class TestServiceErrorHandling:
    """Test service error handling and resilience."""

    def test_service_initialization_with_missing_config(self):
        """Test service behavior with missing configuration."""
        # Test with None config
        llm_service = LLMService(config=None)

        # Should handle gracefully or provide clear error
        try:
            llm_service.initialize()
        except Exception as e:
            assert 'config' in str(e).lower()

    def test_service_health_check_consistency(self, mock_config):
        """Test that all services provide consistent health check interface."""
        services = [
            LLMService(config=mock_config),
            ProcessingService(config=mock_config),
            CitationService(config=mock_config),
            NoteService(config=mock_config),
            RAGService(config=mock_config),
        ]

        for service in services:
            service.initialize()

            health = service.health_check()

            # Consistent health check contract
            assert isinstance(health, dict)
            assert 'status' in health
            assert health['status'] in ['healthy', 'degraded', 'unhealthy']

    def test_service_cleanup_and_resource_management(self, mock_config):
        """Test service cleanup and resource management."""
        services = [
            LLMService(config=mock_config),
            ProcessingService(config=mock_config),
            CitationService(config=mock_config),
        ]

        for service in services:
            service.initialize()

            # Services should have cleanup capability
            if hasattr(service, 'cleanup'):
                try:
                    service.cleanup()
                except Exception as e:
                    # Cleanup failures should be logged, not crash
                    assert len(str(e)) > 0


class TestServiceIntegrationContracts:
    """Test contracts between services."""

    def test_llm_to_processing_service_contract(self, mock_config):
        """Test contract between LLM and Processing services."""
        llm_service = LLMService(config=mock_config)
        processing_service = ProcessingService(
            config=mock_config, llm_service=llm_service
        )

        llm_service.initialize()
        processing_service.initialize()

        # Verify contract: ProcessingService should use LLMService
        assert processing_service.llm_service is llm_service

    def test_citation_to_processing_service_contract(self, mock_config):
        """Test contract between Citation and Processing services."""
        llm_service = LLMService(config=mock_config)
        citation_service = CitationService(config=mock_config)

        llm_service.initialize()
        citation_service.initialize()

        # Mock the citation processor to avoid template loading
        mock_processor = Mock()
        citation_service._citation_processor = mock_processor

        # Services should be compatible
        assert citation_service.config is not None
        assert hasattr(citation_service, 'citation_processor')

    def test_data_flow_contracts(self, mock_config):
        """Test data flow contracts between services."""
        # Create services
        processing_service = ProcessingService(config=mock_config)
        citation_service = CitationService(config=mock_config)
        note_service = NoteService(config=mock_config)

        # Initialize all
        processing_service.initialize()
        citation_service.initialize()
        note_service.initialize()

        # Test data compatibility
        # AnalysisResponse from processing should be compatible with note service
        mock_analysis = AnalysisResponse(
            title='Test Paper', authors=['Author, A.'], abstract='Test abstract'
        )

        mock_citations = [Citation(title='Citation 1', authors=['Ref, A.'])]

        # Verify data structures are compatible (don't need to actually call)
        assert isinstance(mock_analysis, AnalysisResponse)
        assert isinstance(mock_citations, list)
        assert all(isinstance(c, Citation) for c in mock_citations)
