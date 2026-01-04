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

    def test_initialization_with_custom_config(self):
        """Test ArticleService accepts custom config."""
        mock_config = Mock(spec=Config)
        mock_llm = Mock()
        service = ArticleService(config=mock_config, llm_service=mock_llm)
        
        assert service.config is mock_config


class TestArticleServiceMethods:
    """Test ArticleService key methods."""

    def test_service_has_required_methods(self):
        """Test ArticleService has all required methods."""
        mock_llm = Mock()
        service = ArticleService(llm_service=mock_llm)
        
        # Check key methods exist
        assert hasattr(service, 'create_article')
        assert hasattr(service, 'get_article')
        assert hasattr(service, 'list_articles')
        assert hasattr(service, 'update_article')
        assert hasattr(service, 'delete_article')

    def test_initialize_method(self):
        """Test initialize() method."""
        mock_llm = Mock()
        service = ArticleService(llm_service=mock_llm)
        
        # Should not raise
        service.initialize()
