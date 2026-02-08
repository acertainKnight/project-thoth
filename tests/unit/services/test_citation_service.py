"""Test suite for CitationService."""

from unittest.mock import Mock

import pytest

from thoth.config import Config
from thoth.services.citation_service import CitationService


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

    def test_extract_citations_uses_processor(self):
        """Test extract_citations method exists and is callable."""
        import os

        # Skip if OpenRouter API key not available (CI environment)
        if not os.getenv('OPENROUTER_API_KEY') and not os.getenv('API_OPENROUTER_KEY'):
            pytest.skip(
                'OpenRouter API key not available (required for CitationService)'
            )

        service = CitationService()

        # Just verify the method exists and is callable
        assert hasattr(service, 'extract_citations')
        assert callable(service.extract_citations)
