"""
Tests for LLMService.

Tests the LLM client management and model selection functionality.
"""

from unittest.mock import patch

from thoth.services.llm_service import LLMService
from thoth.utilities.config import ThothConfig


def test_get_client_default(thoth_config: ThothConfig):
    """Test getting the default LLM client."""
    llm_service = LLMService(config=thoth_config)
    client = llm_service.get_client()
    assert client.model_name == thoth_config.llm_config.model


def test_get_client_specific_model(thoth_config: ThothConfig):
    """Test getting a client for a specific model."""
    llm_service = LLMService(config=thoth_config)
    client = llm_service.get_client(model='openai/gpt-4o-mini')
    assert client.model_name == 'openai/gpt-4o-mini'


def test_get_client_openai_native(thoth_config: ThothConfig, monkeypatch):
    """Test that the native OpenAI client is used when specified."""
    monkeypatch.setenv('API_OPENAI_KEY', 'fake-key')
    thoth_config.api_keys.openai_key = 'fake-key'
    llm_service = LLMService(config=thoth_config)

    with patch('thoth.services.llm_service.OpenAIClient') as mock_openai:
        llm_service.get_client(model='openai/gpt-4o')
        mock_openai.assert_called_once()


def test_get_client_anthropic_native(thoth_config: ThothConfig, monkeypatch):
    """Test that the native Anthropic client is used when specified."""
    monkeypatch.setenv('API_ANTHROPIC_KEY', 'fake-key')
    thoth_config.api_keys.anthropic_key = 'fake-key'
    llm_service = LLMService(config=thoth_config)

    with patch('thoth.services.llm_service.AnthropicClient') as mock_anthropic:
        llm_service.get_client(model='anthropic/claude-3-haiku')
        mock_anthropic.assert_called_once()


def test_get_client_openrouter_fallback(thoth_config: ThothConfig):
    """Test that OpenRouter is used as a fallback."""
    llm_service = LLMService(config=thoth_config)
    with patch('thoth.services.llm_service.OpenRouterClient') as mock_openrouter:
        llm_service.get_client(model='some/other-model')
        mock_openrouter.assert_called_once()


def test_get_structured_client(thoth_config: ThothConfig):
    """Test getting a client configured for structured output."""
    from pydantic import BaseModel

    class MySchema(BaseModel):
        field: str

    llm_service = LLMService(config=thoth_config)
    structured_client = llm_service.get_structured_client(schema=MySchema)
    # We can't easily inspect the internals of the structured client,
    # but we can verify that it's a different object.
    assert structured_client is not None
    assert structured_client != llm_service.get_client()
