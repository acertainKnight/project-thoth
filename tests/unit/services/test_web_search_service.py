"""Test suite for WebSearchService."""

from unittest.mock import Mock

from thoth.config import Config
from thoth.services.web_search_service import WebSearchService


class TestWebSearchServiceInitialization:
    """Test WebSearchService initialization."""

    def test_initialization(self):
        """Test WebSearchService initializes correctly."""
        service = WebSearchService()

        assert service.config is not None

    def test_initialization_with_custom_config(self):
        """Test WebSearchService accepts custom config."""
        mock_config = Mock(spec=Config)
        service = WebSearchService(config=mock_config)

        assert service.config is mock_config


class TestWebSearchServiceMethods:
    """Test WebSearchService key methods."""

    def test_service_has_required_methods(self):
        """Test WebSearchService has all required methods."""
        service = WebSearchService()

        # Check key methods exist
        assert hasattr(service, 'search')

    def test_initialize_method(self):
        """Test initialize() method."""
        service = WebSearchService()

        # Should not raise
        service.initialize()
