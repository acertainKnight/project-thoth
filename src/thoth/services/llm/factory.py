"""Factory for creating LLM clients."""

from __future__ import annotations

from collections.abc import Callable

from thoth.utilities import OpenAIClient, OpenRouterClient

from .protocols import UnifiedLLMClient

# Optional import: AnthropicClient requires langchain-anthropic
try:
    from thoth.utilities import AnthropicClient

    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


class LLMFactory:
    """Factory class for creating LLM clients."""

    def __init__(self) -> None:
        self._registry: dict[str, Callable[[dict], UnifiedLLMClient]] = {
            'openrouter': lambda cfg: OpenRouterClient(**cfg),
            'openai': lambda cfg: OpenAIClient(**cfg),
        }

        # Register Anthropic only if available
        if _ANTHROPIC_AVAILABLE:
            self._registry['anthropic'] = lambda cfg: AnthropicClient(**cfg)

    def register_provider(
        self, provider: str, constructor: Callable[[dict], UnifiedLLMClient]
    ) -> None:
        """Register a new provider with its constructor."""
        self._registry[provider] = constructor

    def create_client(self, provider: str, config: dict) -> UnifiedLLMClient:
        """Create a client for the given provider using provided config."""
        if provider not in self._registry:
            raise ValueError(f"Unknown provider '{provider}'")
        return self._registry[provider](config)
