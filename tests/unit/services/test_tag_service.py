"""Test suite for TagService."""

import pytest
from unittest.mock import Mock

from thoth.services.tag_service import TagService
from thoth.config import Config


class TestTagServiceInitialization:
    """Test TagService initialization."""

    def test_initialization(self):
        """Test TagService initializes correctly."""
        mock_llm = Mock()
        service = TagService(llm_service=mock_llm)
        
        assert service.llm_service is mock_llm
        assert service.config is not None

    def test_initialization_with_custom_config(self):
        """Test TagService accepts custom config."""
        mock_config = Mock(spec=Config)
        mock_llm = Mock()
        service = TagService(config=mock_config, llm_service=mock_llm)
        
        assert service.config is mock_config


class TestTagServiceMethods:
    """Test TagService key methods."""

    def test_service_has_required_methods(self):
        """Test TagService has all required methods."""
        mock_llm = Mock()
        service = TagService(llm_service=mock_llm)
        
        # Check key methods exist
        assert hasattr(service, 'generate_tags')
        assert hasattr(service, 'consolidate_tags')
        assert hasattr(service, 'get_tags')

    def test_initialize_method(self):
        """Test initialize() method."""
        mock_llm = Mock()
        service = TagService(llm_service=mock_llm)
        
        # Should not raise
        service.initialize()
