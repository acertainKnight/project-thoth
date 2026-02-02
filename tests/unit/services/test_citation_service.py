"""Test suite for CitationService."""

import pytest
from unittest.mock import Mock, patch

from thoth.services.citation_service import CitationService
from thoth.config import Config


class TestCitationServiceInitialization:
    """Test CitationService initialization."""

    def test_initialization(self):
        """Test CitationService initializes correctly."""
        service = CitationService()
        
        assert service.config is not None

    def test_initialization_with_custom_config(self):
        """Test CitationService accepts custom config."""
        mock_config = Mock(spec=Config)
        service = CitationService(config=mock_config)
        
        assert service.config is mock_config


class TestCitationServiceMethods:
    """Test CitationService key methods."""

    def test_service_has_required_methods(self):
        """Test CitationService has all required methods."""
        service = CitationService()
        
        # Check key methods exist (actual methods from implementation)
        assert hasattr(service, 'extract_citations')
        assert hasattr(service, 'format_citation')
        assert hasattr(service, 'track_citations')
        assert hasattr(service, 'get_citation_network')
        assert hasattr(service, 'search_articles')

    def test_initialize_method(self):
        """Test initialize() method."""
        service = CitationService()
        
        # Should not raise
        service.initialize()

    @patch('thoth.services.citation_service.CitationProcessor')
    @patch('thoth.services.llm_service.LLMService')
    def test_extract_citations_uses_processor(self, mock_llm_service, mock_processor_class):
        """Test extract_citations uses CitationProcessor."""
        mock_processor = Mock()
        mock_processor.extract_citations.return_value = []
        mock_processor_class.return_value = mock_processor
        
        # Mock the LLM service to avoid API key errors
        mock_llm_instance = Mock()
        mock_llm_service.return_value = mock_llm_instance
        
        service = CitationService()
        result = service.extract_citations("Sample text with citations.")
        
        # Should call processor
        mock_processor.extract_citations.assert_called_once()
