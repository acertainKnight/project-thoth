import pytest

from thoth.services.llm.factory import LLMFactory
from thoth.utilities.anthropic_client import AnthropicClient
from thoth.utilities.openai_client import OpenAIClient
from thoth.utilities.openrouter import OpenRouterClient


def test_create_clients(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'x')
    monkeypatch.setenv('OPENROUTER_API_KEY', 'x')
    factory = LLMFactory()

    assert isinstance(
        factory.create_client('openai', {'api_key': 'x', 'model': 'openai/gpt-4'}),
        OpenAIClient,
    )
    assert isinstance(
        factory.create_client(
            'anthropic',
            {
                'api_key': 'x',
                'model': 'anthropic/claude-3-haiku',
                'max_tokens': 1,
            },
        ),
        AnthropicClient,
    )
    assert isinstance(
        factory.create_client(
            'openrouter', {'api_key': 'x', 'model': 'openai/gpt-4o-mini'}
        ),
        OpenRouterClient,
    )


def test_unknown_provider():
    factory = LLMFactory()
    with pytest.raises(ValueError):
        factory.create_client('unknown', {})


def test_config_passing(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'x')
    factory = LLMFactory()
    client = factory.create_client(
        'openai', {'api_key': 'x', 'model': 'openai/gpt-4o-mini', 'temperature': 0.5}
    )
    assert client.temperature == 0.5
    assert client.model_name == 'openai/gpt-4o-mini'
