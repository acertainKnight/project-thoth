"""
Model fetching utilities for setup wizard.

Fetches available models from provider APIs with caching and fallbacks.
"""

from __future__ import annotations

import httpx
from loguru import logger

# Re-export ModelInfo from openrouter for backward compatibility
from thoth.utilities.openrouter import ModelInfo, ModelRegistry

# Fallback model lists (used if API calls fail)
FALLBACK_OPENAI_CHAT_MODELS = [
    'gpt-4o',
    'gpt-4o-mini',
    'gpt-4-turbo',
    'gpt-3.5-turbo',
]

FALLBACK_OPENAI_EMBEDDING_MODELS = [
    'text-embedding-3-small',
    'text-embedding-3-large',
    'text-embedding-ada-002',
]

FALLBACK_ANTHROPIC_MODELS = [
    'claude-sonnet-4-20250514',
    'claude-3-5-sonnet-20241022',
    'claude-3-5-haiku-20241022',
    'claude-3-opus-20240229',
]

# Letta-tested models that pass the "Basic" support test.
# Source: https://docs.letta.com/connecting-model-providers/supported-models
# Only includes models with Basic pass from Letta's automated scan.
# Format: (provider, model_id, context_window)
LETTA_SUPPORTED_MODELS: list[tuple[str, str, int]] = [
    # Anthropic
    ('anthropic', 'claude-sonnet-4-20250514', 200_000),
    ('anthropic', 'claude-opus-4-20250514', 200_000),
    ('anthropic', 'claude-3-7-sonnet-20250219', 200_000),
    ('anthropic', 'claude-3-5-sonnet-20241022', 200_000),
    ('anthropic', 'claude-3-5-sonnet-20240620', 200_000),
    ('anthropic', 'claude-3-5-haiku-20241022', 200_000),
    # OpenAI
    ('openai', 'gpt-4.1', 1_047_576),
    ('openai', 'gpt-4.1-mini', 1_047_576),
    ('openai', 'gpt-4.1-nano', 1_047_576),
    ('openai', 'gpt-4o', 128_000),
    ('openai', 'gpt-4o-2024-11-20', 128_000),
    ('openai', 'gpt-4o-2024-08-06', 128_000),
    ('openai', 'gpt-4o-mini', 128_000),
    ('openai', 'gpt-4-turbo', 128_000),
    ('openai', 'gpt-4-0613', 8_192),
    ('openai', 'gpt-4-1106-preview', 128_000),
    ('openai', 'gpt-4-turbo-preview', 128_000),
    # Google AI
    ('google_ai', 'gemini-2.5-pro', 1_048_576),
    ('google_ai', 'gemini-2.5-flash-preview-04-17', 1_048_576),
    ('google_ai', 'gemini-2.0-flash-thinking-exp', 1_048_576),
    ('google_ai', 'gemini-1.5-pro', 2_000_000),
    ('google_ai', 'gemini-1.5-pro-002', 2_000_000),
    ('google_ai', 'gemini-1.5-pro-latest', 2_000_000),
    # Together
    ('together', 'meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8', 1_048_576),
    ('together', 'meta-llama/Llama-3.3-70B-Instruct-Turbo', 131_072),
    ('together', 'meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo', 130_815),
    ('together', 'meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo', 131_072),
    ('together', 'deepseek-ai/DeepSeek-V3', 131_072),
    ('together', 'Qwen/Qwen2.5-Coder-32B-Instruct', 32_768),
    ('together', 'arcee-ai/coder-large', 32_768),
]


async def fetch_openrouter_models(
    api_key: str | None = None,  # noqa: ARG001
) -> list[ModelInfo]:
    """Fetch available models from OpenRouter with structured outputs.

    Uses ModelRegistry for caching and filters for models that support
    structured outputs.

    Args:
        api_key: OpenRouter API key (not currently required for list endpoint)

    Returns:
        List of ModelInfo objects with structured output support,
        sorted with free models first

    Example:
        >>> models = await fetch_openrouter_models()
        >>> for model in models:
        ...     print(f'{model.id}: {model.context_length} tokens')
    """
    all_models = await ModelRegistry.get_openrouter_models()
    return ModelRegistry.filter_structured_output(all_models)


async def fetch_openai_chat_models(api_key: str) -> list[str]:
    """
    Fetch available chat models from OpenAI API.

    Filters to gpt-* chat models, excluding instruct, realtime, and audio variants.

    Args:
        api_key: OpenAI API key for authentication

    Returns:
        Sorted list of model IDs, or fallback list on failure.

    Example:
        >>> models = await fetch_openai_chat_models('sk-...')
        >>> print(models)
        ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo']
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                'https://api.openai.com/v1/models',
                headers={'Authorization': f'Bearer {api_key}'},
            )
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                # Filter to chat models (gpt-*), skip instruct/embedding/etc
                chat_models = sorted(
                    m['id']
                    for m in data
                    if m['id'].startswith('gpt-')
                    and 'instruct' not in m['id']
                    and 'realtime' not in m['id']
                    and 'audio' not in m['id']
                )
                if chat_models:
                    return chat_models
    except Exception as e:
        logger.debug(f'Could not fetch OpenAI chat models: {e}')
    return FALLBACK_OPENAI_CHAT_MODELS


async def fetch_openai_embedding_models(api_key: str) -> list[str]:
    """
    Fetch available embedding models from OpenAI API.

    Filters to models with "embedding" in their ID.

    Args:
        api_key: OpenAI API key for authentication

    Returns:
        List of embedding model IDs, or fallback list on failure.

    Example:
        >>> models = await fetch_openai_embedding_models('sk-...')
        >>> print(models)
        ['text-embedding-3-small', 'text-embedding-3-large', 'text-embedding-ada-002']
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                'https://api.openai.com/v1/models',
                headers={'Authorization': f'Bearer {api_key}'},
            )
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                # Filter to embedding models
                embedding_models = sorted(
                    m['id'] for m in data if 'embedding' in m['id']
                )
                if embedding_models:
                    return embedding_models
    except Exception as e:
        logger.debug(f'Could not fetch OpenAI embedding models: {e}')
    return FALLBACK_OPENAI_EMBEDDING_MODELS


async def fetch_anthropic_models(api_key: str) -> list[str]:
    """
    Fetch available models from Anthropic API.

    Args:
        api_key: Anthropic API key for authentication

    Returns:
        List of model IDs, or fallback list on failure.

    Example:
        >>> models = await fetch_anthropic_models('sk-ant-...')
        >>> print(models)
        ['claude-sonnet-4-20250514', 'claude-3-5-sonnet-20241022', ...]
    """
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                'https://api.anthropic.com/v1/models',
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                },
            )
            if resp.status_code == 200:
                data = resp.json().get('data', [])
                models = sorted(m['id'] for m in data if m.get('id'))
                if models:
                    return models
    except Exception as e:
        logger.debug(f'Could not fetch Anthropic models: {e}')
    return FALLBACK_ANTHROPIC_MODELS


async def fetch_letta_compatible_models(
    api_keys: dict[str, str],
    live_models: list[str] | None = None,
) -> list[str]:
    """
    Get models that work with Letta.

    If the Letta mode selection screen detected a running instance and fetched
    live models, those are returned directly. Otherwise falls back to the
    LETTA_SUPPORTED_MODELS static list (models with Basic pass in Letta's test
    matrix), filtered by which API keys the user has.

    Source: https://docs.letta.com/connecting-model-providers/supported-models

    Args:
        api_keys: Dictionary mapping provider names to API keys
                  (e.g., {"openai": "sk-...", "anthropic": "sk-ant-..."})
        live_models: Optional list of model IDs fetched from a running Letta
                     server's GET /v1/models/ endpoint. Takes priority over
                     the static fallback list.

    Returns:
        List of Letta-compatible model IDs in provider/model format.

    Example:
        >>> models = await fetch_letta_compatible_models({'openai': 'sk-...'})
        >>> print(models[:3])
        ['anthropic/claude-sonnet-4-20250514', 'openai/gpt-4.1', ...]
    """
    # If we got live models from a running Letta server, use those
    if live_models:
        logger.info(f'Using {len(live_models)} live models from Letta server')
        return live_models

    # Fall back to static list, filtered by available API keys
    logger.info('No live Letta models — using static supported model list')

    # Anthropic and OpenAI are always shown because:
    # - OpenAI key is required (for embeddings) so those models always work
    # - Anthropic keys can be configured in .env.letta separately
    available_providers: set[str] = {'anthropic', 'openai'}

    # Map Letta provider names to wizard API key names
    provider_key_map = {
        'google_ai': 'google',
        'together': 'together',
    }
    for letta_provider, key_name in provider_key_map.items():
        if api_keys.get(key_name):
            available_providers.add(letta_provider)

    models: list[str] = [
        f'{provider}/{model_id}'
        for provider, model_id, _ctx in LETTA_SUPPORTED_MODELS
        if provider in available_providers
    ]

    if not models:
        # Show all if filtering left nothing
        models = [
            f'{provider}/{model_id}'
            for provider, model_id, _ctx in LETTA_SUPPORTED_MODELS
        ]

    return models
