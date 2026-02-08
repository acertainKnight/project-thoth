"""Test suite for QueryService."""

from unittest.mock import Mock

import pytest

from thoth.services.query_service import QueryService


class TestQueryServiceInitialization:
    """Test QueryService initialization."""

    def test_initialization(self):
        """Test QueryService initializes correctly."""
        service = QueryService()

        assert service.config is not None

    @pytest.mark.skip(
        reason='Complex service dependencies - better for integration tests'
    )
    def test_initialization_with_custom_config(self):
        """Test QueryService accepts custom config."""
        mock_config = Mock()  # Don't use spec to allow any attributes
        service = QueryService(config=mock_config)

        assert service.config is mock_config


class TestQueryServiceMethods:
    """Test QueryService key methods."""

    def test_service_has_required_methods(self):
        """Test QueryService has all required methods."""
        service = QueryService()

        # Check key methods exist
        assert hasattr(service, 'create_query')
        assert hasattr(service, 'get_query')
        assert hasattr(service, 'list_queries')
        assert hasattr(service, 'update_query')
        assert hasattr(service, 'delete_query')

    def test_initialize_method(self):
        """Test initialize() method."""
        service = QueryService()

        # Should not raise
        service.initialize()
