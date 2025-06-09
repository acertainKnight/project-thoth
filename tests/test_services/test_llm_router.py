"""
Tests for LLMRouter service.

Tests the query-based model routing functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from thoth.services.llm_router import LLMRouter
from thoth.utilities.config import ThothConfig


@pytest.fixture
def mock_openrouter_models():
    """Mock response from get_openrouter_models."""
    return [
        {
            'id': 'google/gemini-pro',
            'description': 'A capable model for general tasks.',
            'architecture': {'tool_use': True, 'json_grammar': True},
        },
        {
            'id': 'openai/gpt-4o-mini',
            'description': 'A fast and efficient model.',
            'architecture': {'tool_use': True, 'json_grammar': True},
        },
        {
            'id': 'anthropic/claude-3-haiku',
            'description': 'A model that does not support tool use.',
            'architecture': {'tool_use': False, 'json_grammar': True},
        },
    ]


def test_routing_disabled_single_model(thoth_config: ThothConfig):
    """Test that if routing is disabled, the single model is returned."""
    thoth_config.query_based_routing_config.enabled = False
    thoth_config.research_agent_llm_config.model = 'openai/gpt-4o-mini'

    router = LLMRouter(thoth_config)
    selected_model = router.select_model('some query')

    assert selected_model == 'openai/gpt-4o-mini'


def test_routing_disabled_multiple_models(thoth_config: ThothConfig):
    """Test that if routing is disabled with multiple models, 'auto' is returned."""
    thoth_config.query_based_routing_config.enabled = False
    thoth_config.research_agent_llm_config.model = [
        'google/gemini-pro',
        'openai/gpt-4o-mini',
    ]

    router = LLMRouter(thoth_config)
    selected_model = router.select_model('some query')

    assert selected_model == 'auto'


@patch('thoth.services.llm_router.get_openrouter_models')
def test_routing_enabled_filters_by_capability(
    mock_get_models, mock_openrouter_models, thoth_config: ThothConfig
):
    """Test that the router correctly filters models by required capabilities."""
    mock_get_models.return_value = mock_openrouter_models
    thoth_config.query_based_routing_config.enabled = True
    thoth_config.research_agent_llm_config.model = [
        'google/gemini-pro',
        'openai/gpt-4o-mini',
        'anthropic/claude-3-haiku',
    ]
    # Require tool use, which will filter out claude-3-haiku
    thoth_config.research_agent_llm_config.use_auto_model_selection = True
    thoth_config.research_agent_llm_config.auto_model_require_tool_calling = True

    with patch('thoth.services.llm_router.OpenRouterClient') as mock_router_llm:
        mock_llm_instance = MagicMock()
        mock_llm_instance.invoke.return_value.content = 'google/gemini-pro'
        mock_router_llm.return_value = mock_llm_instance

        router = LLMRouter(thoth_config)
        selected_model = router.select_model('A query that needs tool use')

        assert selected_model == 'google/gemini-pro'

        # Check that the prompt sent to the router LLM only contained the
        # filtered models
        invoke_args = mock_llm_instance.invoke.call_args[0]
        prompt = invoke_args[0]
        assert 'anthropic/claude-3-haiku' not in prompt


@patch('thoth.services.llm_router.get_openrouter_models')
def test_routing_selects_model(
    mock_get_models, mock_openrouter_models, thoth_config: ThothConfig
):
    """Test the full routing flow where a model is selected."""
    mock_get_models.return_value = mock_openrouter_models
    thoth_config.query_based_routing_config.enabled = True
    thoth_config.research_agent_llm_config.model = [
        'google/gemini-pro',
        'openai/gpt-4o-mini',
    ]
    thoth_config.research_agent_llm_config.use_auto_model_selection = False

    with patch('thoth.services.llm_router.OpenRouterClient') as mock_router_llm:
        mock_llm_instance = MagicMock()
        # Simulate the router LLM selecting a model
        mock_llm_instance.invoke.return_value.content = 'openai/gpt-4o-mini'
        mock_router_llm.return_value = mock_llm_instance

        router = LLMRouter(thoth_config)
        selected_model = router.select_model('A query about recent events')

        assert selected_model == 'openai/gpt-4o-mini'
        mock_llm_instance.invoke.assert_called_once()


@patch('thoth.services.llm_router.get_openrouter_models')
def test_routing_fallback_on_invalid_selection(
    mock_get_models, mock_openrouter_models, thoth_config: ThothConfig
):
    """Test that the router falls back if the LLM returns an invalid model."""
    mock_get_models.return_value = mock_openrouter_models
    thoth_config.query_based_routing_config.enabled = True
    thoth_config.research_agent_llm_config.model = [
        'google/gemini-pro',
        'openai/gpt-4o-mini',
    ]
    thoth_config.research_agent_llm_config.use_auto_model_selection = False

    with patch('thoth.services.llm_router.OpenRouterClient') as mock_router_llm:
        mock_llm_instance = MagicMock()
        # Simulate the router LLM returning garbage
        mock_llm_instance.invoke.return_value.content = 'not_a_real_model'
        mock_router_llm.return_value = mock_llm_instance

        router = LLMRouter(thoth_config)
        selected_model = router.select_model('some query')

        # Should fall back to the first candidate model
        assert selected_model == 'google/gemini-pro'
