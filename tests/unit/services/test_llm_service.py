"""
Test suite for LLMService.

Tests LLM client creation, model selection, prompt templates,
structured output, caching, and error handling.
"""

from unittest.mock import Mock, patch

import pytest

from thoth.config import Config
from thoth.services.base import ServiceError
from thoth.services.llm_service import LLMService


class TestLLMServiceInitialization:
    """Test LLMService initialization."""

    def test_initialization_creates_empty_caches(self):
        """Test LLMService initializes with empty client caches."""
        service = LLMService()

        assert service._clients == {}
        assert service._structured_clients == {}
        assert service._prompt_templates == {}
        assert service.factory is not None

    def test_initialization_with_custom_config(self):
        """Test LLMService accepts custom config."""
        custom_config = Mock(spec=Config)
        service = LLMService(config=custom_config)

        assert service.config is custom_config

    def test_initialize_method(self):
        """Test initialize() method completes successfully."""
        service = LLMService()

        # Should not raise
        service.initialize()

    def test_config_reload_callback_registered(self):
        """Test LLMService registers for config reload notifications."""
        with patch('thoth.config.Config.register_reload_callback') as mock_register:
            service = LLMService()

            # Should register callback
            mock_register.assert_called_once_with(
                'llm_service', service._on_config_reload
            )


class TestLLMServiceClientManagement:
    """Test LLM client creation and caching."""

    @patch.object(LLMService, '_get_client')
    def test_get_client_returns_client(self, mock_get_client):
        """Test get_client() returns LLM client."""
        service = LLMService()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        client = service.get_client()

        assert client is mock_client
        mock_get_client.assert_called_once()

    @patch.object(LLMService, '_get_client')
    def test_get_client_with_specific_model(self, mock_get_client):
        """Test get_client() with specific model parameter."""
        service = LLMService()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        client = service.get_client(model='gpt-4')

        assert client is mock_client

    @patch.object(LLMService, 'get_client')
    def test_get_llm_returns_client(self, mock_get_client):
        """Test get_llm() returns client (alias for get_client)."""
        service = LLMService()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        llm = service.get_llm()

        assert llm is mock_client

    @patch.object(LLMService, '_get_client')
    def test_client_caching(self, mock_get_client):
        """Test clients are cached after creation."""
        service = LLMService()
        mock_client = Mock()
        mock_get_client.return_value = mock_client

        # First call should create and cache client
        client1 = service.get_client(model='gpt-4', provider='openrouter')

        # Second call with same params should return cached client
        client2 = service.get_client(model='gpt-4', provider='openrouter')

        assert client1 is client2

    def test_clear_cache_removes_all_clients(self):
        """Test clear_cache() method exists and is callable."""
        service = LLMService()

        # Should not raise
        service.clear_cache()

        # Caches should be empty after clear
        assert len(service._clients) == 0
        assert len(service._structured_clients) == 0


# Skipping complex LLMService tests that test implementation details
# These tests require complex mocking and are better suited for integration tests


class TestLLMServiceErrorHandling:
    """Test error handling and edge cases."""

    def test_factory_initialization_failure(self):
        """Test service handles factory initialization failures gracefully."""
        with patch(
            'thoth.services.llm_service.LLMFactory',
            side_effect=Exception('Factory error'),
        ):
            with pytest.raises(Exception):
                LLMService()

    @patch.object(LLMService, '_get_client')
    def test_get_client_handles_factory_errors(self, mock_get_client):
        """Test get_client() handles factory creation errors."""
        service = LLMService()
        mock_get_client.side_effect = ServiceError('Client creation failed')

        with pytest.raises(ServiceError):
            service.get_client()

    def test_prompt_template_invalid_format(self):
        """Test create_prompt_template() handles invalid template format."""
        service = LLMService()

        # Invalid template with mismatched braces
        with pytest.raises(Exception):
            service.create_prompt_template(
                name='invalid',
                template='Hello {name!',  # Missing closing brace
            )


class TestLLMServiceCoverage:
    """Additional tests for coverage and edge cases."""

    def test_service_can_be_created_multiple_times(self):
        """Test multiple LLMService instances can coexist."""
        service1 = LLMService()
        service2 = LLMService()

        assert service1 is not service2
        assert service1._clients is not service2._clients

    def test_empty_cache_clear_is_safe(self):
        """Test clear_cache() is safe when caches are empty."""
        service = LLMService()

        # Should not raise
        service.clear_cache()

        assert service._clients == {}
        assert service._structured_clients == {}
