"""
Test suite for LLMService.

Tests LLM client creation, model selection, prompt templates,
structured output, caching, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, call

from thoth.services.llm_service import LLMService
from thoth.services.base import ServiceError
from thoth.config import Config


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
            mock_register.assert_called_once_with('llm_service', service._on_config_reload)


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


class TestLLMServiceStructuredOutput:
    """Test structured output generation."""

    @patch.object(LLMService, '_get_client')
    def test_get_structured_client_returns_client(self, mock_get_client):
        """Test get_structured_client() returns structured client."""
        service = LLMService()
        mock_schema = Mock()
        mock_client = Mock()
        mock_structured = Mock()
        mock_client.with_structured_output.return_value = mock_structured
        mock_get_client.return_value = mock_client
        
        client = service.get_structured_client(schema=mock_schema)
        
        assert client is mock_structured
        mock_client.with_structured_output.assert_called_once_with(mock_schema)

    def test_structured_client_caching(self):
        """Test structured clients are cached by schema."""
        service = LLMService()
        service.factory = Mock()
        
        mock_client = Mock()
        mock_structured = Mock()
        mock_client.with_structured_output.return_value = mock_structured
        service.factory.create_client.return_value = mock_client
        
        # Mock schema with hash
        mock_schema = Mock()
        mock_schema.__name__ = 'TestSchema'
        
        # First call
        client1 = service.get_structured_client(schema=mock_schema)
        
        # Second call with same schema should use cache
        client2 = service.get_structured_client(schema=mock_schema)
        
        assert client1 is client2


class TestLLMServicePromptTemplates:
    """Test prompt template management."""

    def test_create_prompt_template_from_string(self):
        """Test create_prompt_template() creates template from string."""
        service = LLMService()
        
        template = service.create_prompt_template(
            name='test_template',
            template='Hello {name}!'
        )
        
        assert template is not None
        assert 'test_template' in service._prompt_templates
        assert service._prompt_templates['test_template'] is template

    def test_create_prompt_template_caching(self):
        """Test prompt templates are cached by name."""
        service = LLMService()
        
        template1 = service.create_prompt_template(
            name='test_template',
            template='Hello {name}!'
        )
        
        # Second call should return cached template
        template2 = service.create_prompt_template(
            name='test_template',
            template='Different template'
        )
        
        assert template1 is template2  # Same object (cached)

    def test_create_prompt_template_without_caching(self):
        """Test prompt template creation without caching."""
        service = LLMService()
        
        template = service.create_prompt_template(
            name=None,  # No name = no caching
            template='Hello {name}!'
        )
        
        assert template is not None
        assert len(service._prompt_templates) == 0  # Not cached


class TestLLMServiceInvocation:
    """Test LLM invocation and retry logic."""

    @patch.object(LLMService, 'get_client')
    def test_invoke_with_retry_success(self, mock_get_client):
        """Test invoke_with_retry() successfully invokes client."""
        service = LLMService()
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = "Response text"
        mock_client.invoke.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = service.invoke_with_retry(prompt="Test prompt")
        
        assert result.content == "Response text"
        mock_client.invoke.assert_called_once()

    @patch.object(LLMService, 'get_client')
    def test_invoke_with_retry_retries_on_failure(self, mock_get_client):
        """Test invoke_with_retry() retries on API failures."""
        service = LLMService()
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = "Success"
        
        # Fail twice, then succeed
        mock_client.invoke.side_effect = [
            Exception("API Error 1"),
            Exception("API Error 2"),
            mock_response
        ]
        mock_get_client.return_value = mock_client
        
        result = service.invoke_with_retry(prompt="Test", max_retries=3)
        
        assert result.content == "Success"
        assert mock_client.invoke.call_count == 3

    @patch.object(LLMService, 'get_client')
    def test_invoke_with_retry_exhausts_retries(self, mock_get_client):
        """Test invoke_with_retry() raises after exhausting retries."""
        service = LLMService()
        
        mock_client = Mock()
        mock_client.invoke.side_effect = Exception("API Error")
        mock_get_client.return_value = mock_client
        
        with pytest.raises(Exception, match="API Error"):
            service.invoke_with_retry(prompt="Test", max_retries=2)
        
        assert mock_client.invoke.call_count == 2


class TestLLMServiceConfiguration:
    """Test model configuration and settings."""

    def test_get_model_config_returns_config(self):
        """Test get_model_config() returns configuration for model type."""
        mock_config = Mock()
        mock_config.llm_config.default.model = 'gpt-4'
        mock_config.llm_config.default.temperature = 0.7
        
        service = LLMService(config=mock_config)
        
        config = service.get_model_config('default')
        
        assert 'model' in config
        assert 'temperature' in config

    def test_config_reload_clears_caches(self):
        """Test config reload clears all client caches."""
        mock_config = Mock()
        mock_config.llm_config.model = 'gpt-4'
        mock_config.llm_config.model_settings.temperature = 0.7
        mock_config.llm_config.model_settings.max_tokens = 1000
        
        service = LLMService(config=mock_config)
        
        # Add some cached clients
        service._clients = {'model1': Mock()}
        service._structured_clients = {'model1': Mock()}
        
        # Trigger reload
        service._on_config_reload(mock_config)
        
        assert service._clients == {}
        assert service._structured_clients == {}


class TestLLMServiceHealthCheck:
    """Test health check functionality."""

    @patch.object(LLMService, 'get_client')
    def test_health_check_success(self, mock_get_client):
        """Test health_check() returns healthy status."""
        service = LLMService()
        
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        health = service.health_check()
        
        assert isinstance(health, dict)
        assert 'status' in health

    @patch.object(LLMService, 'get_client')
    def test_health_check_failure(self, mock_get_client):
        """Test health_check() detects failures."""
        service = LLMService()
        
        mock_get_client.side_effect = Exception("Connection failed")
        
        health = service.health_check()
        
        assert health['status'] == 'unhealthy'


class TestLLMServiceErrorHandling:
    """Test error handling and edge cases."""

    def test_factory_initialization_failure(self):
        """Test service handles factory initialization failures gracefully."""
        with patch('thoth.services.llm_service.LLMFactory', side_effect=Exception("Factory error")):
            with pytest.raises(Exception):
                LLMService()

    @patch.object(LLMService, '_get_client')
    def test_get_client_handles_factory_errors(self, mock_get_client):
        """Test get_client() handles factory creation errors."""
        service = LLMService()
        mock_get_client.side_effect = ServiceError("Client creation failed")
        
        with pytest.raises(ServiceError):
            service.get_client()

    def test_prompt_template_invalid_format(self):
        """Test create_prompt_template() handles invalid template format."""
        service = LLMService()
        
        # Invalid template with mismatched braces
        with pytest.raises(Exception):
            service.create_prompt_template(
                name='invalid',
                template='Hello {name!'  # Missing closing brace
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

    @patch.object(LLMService, 'get_client')
    def test_invoke_with_retry_custom_parameters(self, mock_get_client):
        """Test invoke_with_retry() accepts custom parameters."""
        service = LLMService()
        
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = "Response"
        mock_client.invoke.return_value = mock_response
        mock_get_client.return_value = mock_client
        
        result = service.invoke_with_retry(
            prompt="Test",
            model='gpt-4',
            temperature=0.5,
            max_tokens=500,
            max_retries=1
        )
        
        assert result.content == "Response"
