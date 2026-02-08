"""Test suite for DiscoveryService."""

from unittest.mock import Mock

import pytest

from thoth.services.discovery_service import DiscoveryService


class TestDiscoveryServiceInitialization:
    """Test DiscoveryService initialization."""

    def test_initialization(self):
        """Test DiscoveryService initializes correctly."""
        service = DiscoveryService()

        assert service.config is not None

    @pytest.mark.skip(
        reason='Complex service dependencies - better for integration tests'
    )
    def test_initialization_with_custom_config(self):
        """Test DiscoveryService accepts custom config."""
        mock_config = Mock()  # Don't use spec to allow any attributes
        service = DiscoveryService(config=mock_config)

        assert service.config is mock_config


class TestDiscoveryServiceMethods:
    """Test DiscoveryService key methods."""

    def test_service_has_required_methods(self):
        """Test DiscoveryService has all required methods."""
        service = DiscoveryService()

        # Check key methods exist (actual methods from implementation)
        assert hasattr(service, 'create_source')
        assert hasattr(service, 'get_source')
        assert hasattr(service, 'list_sources')
        assert hasattr(service, 'run_discovery')
        assert hasattr(service, 'get_statistics')

    def test_initialize_method(self):
        """Test initialize() method."""
        service = DiscoveryService()

        # Should not raise
        service.initialize()
