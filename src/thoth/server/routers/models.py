"""
Models router for listing available models from providers.

Provides REST API endpoints for browsing available models from configured providers.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from thoth.utilities.openrouter import ModelRegistry

router = APIRouter()


class ModelResponse(BaseModel):
    """Response model for a single model."""

    id: str = Field(description="Model identifier (e.g., 'openai/gpt-4o')")
    name: str = Field(description='Human-readable model name')
    context_length: int = Field(description='Maximum context window size in tokens')
    supported_parameters: list[str] = Field(
        description="List of supported features (e.g., 'structured_outputs', 'tools')"
    )
    pricing_prompt: str | None = Field(None, description='Cost per token for prompts')
    pricing_completion: str | None = Field(
        None, description='Cost per token for completions'
    )


class AvailableModelsResponse(BaseModel):
    """Response model for available models endpoint."""

    provider: str = Field(description='Provider name')
    total_count: int = Field(description='Total number of models returned')
    models: list[ModelResponse] = Field(description='List of available models')


@router.get('/available', response_model=AvailableModelsResponse)
async def get_available_models(
    provider: str = Query(
        'openrouter',
        description="Provider name (currently only 'openrouter' supported)",
    ),
    structured_output: bool = Query(
        False, description='Filter to models supporting structured outputs'
    ),
) -> AvailableModelsResponse:
    """
    Get available models from a provider.

    Args:
        provider: Provider name (currently only 'openrouter' supported)
        structured_output: If True, filter to models supporting structured outputs

    Returns:
        AvailableModelsResponse with list of models

    Example:
        GET /models/available?provider=openrouter&structured_output=true
    """
    if provider != 'openrouter':
        # For now, only OpenRouter is supported
        # Future: add OpenAI, Anthropic, etc.
        return AvailableModelsResponse(
            provider=provider,
            total_count=0,
            models=[],
        )

    # Fetch from registry (uses cache)
    all_models = await ModelRegistry.get_openrouter_models()

    # Filter if requested
    if structured_output:
        all_models = ModelRegistry.filter_structured_output(all_models)

    # Convert to response format
    models_response = [
        ModelResponse(
            id=m.id,
            name=m.name,
            context_length=m.context_length,
            supported_parameters=m.supported_parameters,
            pricing_prompt=m.pricing_prompt,
            pricing_completion=m.pricing_completion,
        )
        for m in all_models
    ]

    return AvailableModelsResponse(
        provider=provider,
        total_count=len(models_response),
        models=models_response,
    )


@router.get('/context-length/{model_id:path}')
async def get_model_context_length(model_id: str) -> dict[str, Any]:
    """
    Get context length for a specific model.

    Args:
        model_id: Model identifier (e.g., "openai/gpt-4o")

    Returns:
        Dict with model_id and context_length

    Example:
        GET /models/context-length/openai/gpt-4o
    """
    context_length = ModelRegistry.get_context_length(model_id)

    if context_length is None:
        return {
            'model_id': model_id,
            'context_length': None,
            'error': 'Model not found in registry. Try refreshing the model list.',
        }

    return {
        'model_id': model_id,
        'context_length': context_length,
    }
