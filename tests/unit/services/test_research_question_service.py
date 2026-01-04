"""Test suite for ResearchQuestionService."""

import pytest
from unittest.mock import Mock

from thoth.services.research_question_service import ResearchQuestionService
from thoth.config import Config


class TestResearchQuestionServiceInitialization:
    """Test ResearchQuestionService initialization."""

    def test_initialization(self):
        """Test ResearchQuestionService initializes correctly."""
        mock_postgres = Mock()
        service = ResearchQuestionService(postgres_service=mock_postgres)
        
        assert service.postgres_service is mock_postgres
        assert service.config is not None

    def test_initialization_with_custom_config(self):
        """Test ResearchQuestionService accepts custom config."""
        mock_config = Mock(spec=Config)
        mock_postgres = Mock()
        service = ResearchQuestionService(
            config=mock_config,
            postgres_service=mock_postgres
        )
        
        assert service.config is mock_config


class TestResearchQuestionServiceMethods:
    """Test ResearchQuestionService key methods."""

    def test_service_has_required_methods(self):
        """Test ResearchQuestionService has all required methods."""
        mock_postgres = Mock()
        service = ResearchQuestionService(postgres_service=mock_postgres)
        
        # Check key methods exist
        assert hasattr(service, 'create_question')
        assert hasattr(service, 'get_question')
        assert hasattr(service, 'list_questions')
        assert hasattr(service, 'update_question')
        assert hasattr(service, 'delete_question')

    def test_initialize_method(self):
        """Test initialize() method."""
        mock_postgres = Mock()
        service = ResearchQuestionService(postgres_service=mock_postgres)
        
        # Should not raise
        service.initialize()
