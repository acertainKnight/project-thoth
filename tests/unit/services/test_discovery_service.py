"""Test suite for DiscoveryService."""

import pytest
from unittest.mock import Mock

from thoth.services.discovery_service import DiscoveryService
from thoth.config import Config


class TestDiscoveryServiceInitialization:
    """Test DiscoveryService initialization."""

    def test_initialization(self):
        """Test DiscoveryService initializes correctly."""
        service = DiscoveryService()
        
        assert service.config is not None

    def test_initialization_with_custom_config(self):
        """Test DiscoveryService accepts custom config."""
        mock_config = Mock(spec=Config)
        service = DiscoveryService(config=mock_config)
        
        assert service.config is mock_config


class TestDiscoveryServiceMethods:
    """Test DiscoveryService key methods."""

    def test_service_has_required_methods(self):
        """Test DiscoveryService has all required methods."""
        service = DiscoveryService()
        
        # Check key methods exist
        assert hasattr(service, 'discover_papers')
        assert hasattr(service, 'search_arxiv')
        assert hasattr(service, 'search_semantic_scholar')

    def test_initialize_method(self):
        """Test initialize() method."""
        service = DiscoveryService()
        
        # Should not raise
        service.initialize()
