from .openai_client import OpenAIClient
from .openrouter import OpenRouterClient, OpenRouterRateLimiter

# Optional import: AnthropicClient requires langchain-anthropic (optional dependency)
try:
    from .anthropic_client import AnthropicClient

    __all__ = [
        'AnthropicClient',
        'OpenAIClient',
        'OpenRouterClient',
        'OpenRouterRateLimiter',
    ]
except ImportError:
    # langchain-anthropic not installed - AnthropicClient unavailable
    __all__ = [
        'OpenAIClient',
        'OpenRouterClient',
        'OpenRouterRateLimiter',
    ]
