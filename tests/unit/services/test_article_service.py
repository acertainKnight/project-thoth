"""Test suite for ArticleService."""

import pytest
from unittest.mock import Mock, patch

from thoth.services.article_service import ArticleService
from thoth.config import Config


class TestArticleServiceInitialization:
    """Test ArticleService initialization."""

    def test_initialization(self):
        """Test ArticleService initializes correctly."""
        mock_llm = Mock()
        service = ArticleService(llm_service=mock_llm)
        
        assert service.llm_service is mock_llm
        assert service.config is not None

    @pytest.mark.skip(reason="Complex service dependencies - better for integration tests")
    def test_initialization_with_custom_config(self):
        """Test ArticleService accepts custom config."""
        pass


class TestArticleServiceMethods:
    """Test ArticleService key methods."""

    def test_service_has_required_methods(self):
        """Test ArticleService has all required methods."""
        mock_llm = Mock()
        service = ArticleService(llm_service=mock_llm)
        
        # Check key methods exist (actual methods from implementation)
        assert hasattr(service, 'evaluate_against_query')
        assert hasattr(service, 'evaluate_for_download')
        assert hasattr(service, 'check_relevance')
        assert hasattr(service, 'health_check')

    def test_initialize_method(self):
        """Test initialize() method."""
        mock_llm = Mock()
        service = ArticleService(llm_service=mock_llm)
        
        # Should not raise
        service.initialize()
