"""
Client for the OpenRouter API leveraging the OpenAI API.
"""

import asyncio
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openai import ChatOpenAI
from loguru import logger

from thoth.services.llm.base_client import BaseLLMClient


@dataclass
class ModelInfo:
    """
    Information about an LLM model from a provider API.

    Attributes:
        id: Model identifier (e.g., "openai/gpt-4o", "google/gemini-2.5-flash")
        name: Human-readable model name
        context_length: Maximum context window size in tokens
        supported_parameters: List of supported features (e.g., "structured_outputs")
        pricing_prompt: Cost per token for prompts (optional)
        pricing_completion: Cost per token for completions (optional)
    """

    id: str
    name: str
    context_length: int
    supported_parameters: list[str]
    pricing_prompt: str | None = None
    pricing_completion: str | None = None


# Fallback models if API is unreachable
FALLBACK_OPENROUTER_MODELS = [
    ModelInfo(
        id="google/gemini-2.0-flash-exp:free",
        name="Google Gemini 2.0 Flash (Free)",
        context_length=100000,
        supported_parameters=["structured_outputs"],
    ),
    ModelInfo(
        id="anthropic/claude-3.5-sonnet",
        name="Claude 3.5 Sonnet",
        context_length=200000,
        supported_parameters=["structured_outputs"],
    ),
    ModelInfo(
        id="openai/gpt-4o",
        name="GPT-4o",
        context_length=128000,
        supported_parameters=["structured_outputs"],
    ),
    ModelInfo(
        id="openai/gpt-4o-mini",
        name="GPT-4o Mini",
        context_length=128000,
        supported_parameters=["structured_outputs"],
    ),
]


class ModelRegistry:
    """
    Cached registry of available models from providers.

    Provides both async and sync access with 1-hour caching.
    """

    _cache: list[ModelInfo] = []
    _cache_time: float = 0
    _cache_ttl: int = 3600  # 1 hour

    @classmethod
    async def get_openrouter_models(
        cls, force_refresh: bool = False
    ) -> list[ModelInfo]:
        """
        Fetch OpenRouter models with caching (async).

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            List of ModelInfo objects, sorted with free models first

        Example:
            >>> models = await ModelRegistry.get_openrouter_models()
            >>> for model in models:
            ...     print(f"{model.id}: {model.context_length} tokens")
        """
        current_time = time.time()

        # Return cached data if valid
        if (
            not force_refresh
            and cls._cache
            and (current_time - cls._cache_time < cls._cache_ttl)
        ):
            return cls._cache

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get("https://openrouter.ai/api/v1/models")
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    models = []
                    for m in data:
                        supported = m.get("supported_parameters", [])
                        model_id = m.get("id", "")

                        # Skip beta/auto models
                        if ":beta" in model_id or model_id == "auto":
                            continue

                        pricing = m.get("pricing", {})
                        models.append(
                            ModelInfo(
                                id=model_id,
                                name=m.get("name", model_id),
                                context_length=m.get("context_length", 0),
                                supported_parameters=supported,
                                pricing_prompt=pricing.get("prompt"),
                                pricing_completion=pricing.get("completion"),
                            )
                        )

                    if models:
                        # Sort: free models first, then by name
                        def sort_key(model: ModelInfo) -> tuple[int, str]:
                            return (0 if ":free" in model.id else 1, model.id)

                        cls._cache = sorted(models, key=sort_key)
                        cls._cache_time = current_time
                        logger.info(
                            f"Fetched and cached {len(cls._cache)} models from OpenRouter."
                        )
                        return cls._cache
        except Exception as e:
            logger.error(f"Failed to fetch models from OpenRouter: {e}")

        # Return stale cache if available, otherwise fallback
        if cls._cache:
            logger.warning("Returning stale cache due to API error")
            return cls._cache

        logger.warning("Using fallback model list")
        return FALLBACK_OPENROUTER_MODELS

    @classmethod
    def get_openrouter_models_sync(cls) -> list[ModelInfo]:
        """
        Sync wrapper for get_openrouter_models.

        Uses asyncio.run() for non-async contexts (e.g., llm_router).

        Returns:
            List of ModelInfo objects

        Example:
            >>> models = ModelRegistry.get_openrouter_models_sync()
            >>> print(len(models))
        """
        try:
            # Try to get existing event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, we can't use asyncio.run()
                # Return cached data or fallback
                if cls._cache:
                    return cls._cache
                return FALLBACK_OPENROUTER_MODELS
            else:
                return loop.run_until_complete(cls.get_openrouter_models())
        except RuntimeError:
            # No event loop exists, create one
            return asyncio.run(cls.get_openrouter_models())

    @classmethod
    def filter_structured_output(cls, models: list[ModelInfo]) -> list[ModelInfo]:
        """
        Filter to models supporting structured outputs.

        Args:
            models: List of ModelInfo objects to filter

        Returns:
            Filtered list containing only models with structured_outputs support

        Example:
            >>> all_models = ModelRegistry.get_openrouter_models_sync()
            >>> structured = ModelRegistry.filter_structured_output(all_models)
            >>> print(f"{len(structured)} of {len(all_models)} support structured outputs")
        """
        return [
            m
            for m in models
            if "structured_outputs" in m.supported_parameters
        ]

    @classmethod
    def get_context_length(cls, model_id: str) -> int | None:
        """
        Look up context length from cache for a specific model.

        Args:
            model_id: Model identifier to look up

        Returns:
            Context length in tokens, or None if model not found

        Example:
            >>> length = ModelRegistry.get_context_length("openai/gpt-4o")
            >>> print(f"Context length: {length}")
        """
        for model in cls._cache:
            if model.id == model_id:
                return model.context_length
        return None


def get_openrouter_models() -> list[dict[str, Any]]:
    """
    Legacy sync wrapper for backward compatibility.

    Returns raw dicts instead of ModelInfo objects.

    Returns:
        List of model dicts matching the old OpenRouter API response format

    Example:
        >>> models = get_openrouter_models()
        >>> print(models[0]['id'])
    """
    models = ModelRegistry.get_openrouter_models_sync()
    return [asdict(m) for m in models]


class OpenRouterError(Exception):
    """Exception raised for errors in the OpenRouter API."""

    pass


class OpenRouterRateLimiter:
    """
    Rate limiter for the OpenRouter API based on available credits.

    OpenRouter allows 1 request per credit per second up to a surge limit.
    This class checks the available credits and configures a rate limiter accordingly.

    Args:
        api_key (str): OpenRouter API key for authentication.
        max_surge_limit (int, optional): Maximum requests per second regardless of credits.
            Defaults to 500.
        min_requests_per_second (float, optional): Minimum requests per second when credits < 1.
            Defaults to 1.0.
        check_interval (float, optional): How often to check if a request is allowed.
            Defaults to 0.1 seconds.

    Example:
        >>> # Method 1: Use with OpenRouterClient (recommended)
        >>> client = OpenRouterClient(
        ...     api_key='your-api-key', model='openai/gpt-4', use_rate_limiter=True
        ... )
        >>> response = client.invoke('Hello world')
        >>>
        >>> # Method 2: Use directly with any LangChain model
        >>> from src.thoth.utilities.openrouter import OpenRouterRateLimiter
        >>> rate_limiter = OpenRouterRateLimiter(api_key='your-api-key')
        >>> rate_limiter.setup()  # Sets up the rate limiter based on available credits
        >>> from langchain_openai import ChatOpenAI
        >>> model = ChatOpenAI(
        ...     openai_api_key='sk-...',
        ...     rate_limiter=rate_limiter.get_langchain_limiter(),
        ... )
        >>> response = model.invoke('Hello world')
    """  # noqa: W505

    def __init__(
        self,
        api_key: str,
        max_surge_limit: int = 500,
        min_requests_per_second: float = 1.0,
        check_interval: float = 0.1,
    ) -> None:
        """Initialize the OpenRouter rate limiter with the specified parameters."""
        self.api_key = api_key
        self.max_surge_limit = max_surge_limit
        self.min_requests_per_second = min_requests_per_second
        self.check_interval = check_interval
        self.credits = None
        self.rate_limiter = None

    def _get_credits(self) -> float | None:
        """
        Get the available credits for the API key.

        Returns:
            Optional[float]: The number of available credits or None if the request failed.
        """  # noqa: W505
        try:
            response = httpx.get(
                'https://openrouter.ai/api/v1/auth/key',
                headers={'Authorization': f'Bearer {self.api_key}'},
            )
            if response.status_code == 200:
                data = response.json().get('data', {})
                usage = data.get('usage', 0)
                limit = data.get('limit')

                # Calculate remaining credits
                if limit is not None:
                    return max(0, limit - usage)
                # If no limit (unlimited), return a high value
                return float(self.max_surge_limit)
            else:
                logger.error(
                    f'Failed to get credits: {response.status_code} {response.text}'
                )
                return None
        except Exception as e:
            logger.error(f'Error getting credits: {e}')
            return None

    def setup(self) -> None:
        """
        Set up the rate limiter based on the available credits.

        OpenRouter allows 1 request per credit per second up to the surge limit.
        """
        self.credits = self._get_credits()

        if self.credits is None:
            # If we can't get credits, use a conservative limit
            requests_per_second = self.min_requests_per_second
            logger.warning(
                f'Unable to determine credits. Setting rate limit to {requests_per_second} req/s'
            )
        else:
            # Calculate requests per second based on credits (1 req/credit/s)
            # If credits < 1, still allow 1 req/s as the minimum
            if self.credits < 1:
                requests_per_second = self.min_requests_per_second
            else:
                requests_per_second = min(
                    float(self.credits), float(self.max_surge_limit)
                )

            logger.info(
                f'Available credits: {self.credits}, setting rate limit to {requests_per_second} req/s'
            )

        self.rate_limiter = InMemoryRateLimiter(
            requests_per_second=requests_per_second,
            check_every_n_seconds=self.check_interval,
            # Allow some burst capacity but not exceeding the surge limit
            max_bucket_size=min(10, self.max_surge_limit),
        )

    def acquire(self) -> None:
        """
        Acquire permission to make a request. This method blocks until permission is granted.

        If the rate limiter is not set up, it will be set up automatically.
        """  # noqa: W505
        if self.rate_limiter is None:
            self.setup()

        if self.rate_limiter:
            self.rate_limiter.acquire()
        else:
            # If rate limiter setup failed, use a simple delay to be safe
            time.sleep(1.0 / self.min_requests_per_second)

    def get_langchain_limiter(self):
        """
        Get the underlying LangChain InMemoryRateLimiter for direct use with LangChain models.

        This method ensures the rate limiter is set up before returning it.

        Returns:
            InMemoryRateLimiter: The configured rate limiter ready to use with LangChain models.
        """  # noqa: W505
        if self.rate_limiter is None:
            self.setup()

        return self.rate_limiter


class OpenRouterClient(BaseLLMClient, ChatOpenAI):
    """
    Client for the OpenRouter API leveraging the OpenAI API.

    This class extends ChatOpenAI to provide a client for the OpenRouter API, which allows
    access to multiple LLM providers through a unified interface. OpenRouter normalizes
    responses across different models to match the OpenAI Chat API format.

    It inherits methods from `ChatOpenAI`, including `with_structured_output` for generating
    structured data based on a Pydantic schema or function definition. This typically relies
    on the underlying model's tool-calling capabilities, which OpenRouter standardizes.

    Args:
        api_key (str, optional): OpenRouter API key for authentication. Defaults to OPENROUTER_API_KEY env var.
        model (str or list of str): Model identifier(s) (e.g. "openai/gpt-4", "anthropic/claude-2.1")
        temperature (float, optional): Sampling temperature between 0 and 2. Defaults to 0.7
        max_tokens (int, optional): Maximum tokens to generate. Defaults to None.
        site_url (str, optional): Your site URL for rankings on openrouter.ai
        site_name (str, optional): Your site name for rankings on openrouter.ai
        streaming (bool, optional): Whether to stream responses. Defaults to False.
        use_rate_limiter (bool, optional): Whether to use rate limiting based on OpenRouter credits. Defaults to True.
        **kwargs: Additional arguments passed to ChatOpenAI

    Example:
        >>> # Basic usage with rate limiter
        >>> client = OpenRouterClient(
        ...     api_key='your-api-key',
        ...     model='openai/gpt-4',
        ...     temperature=0.7,
        ...     site_url='https://example.com',
        ...     site_name='My Application',
        ...     use_rate_limiter=True,
        ... )
        >>> response = client.invoke('What is the meaning of life?')
        >>> print(response.content)
        >>>
        >>> # Structured output using inherited .with_structured_output()
        >>> from pydantic import BaseModel, Field
        >>>
        >>> class Joke(BaseModel):
        ...     \"\"\"Joke structure.\"\"\"
        ...     setup: str = Field(description="The setup of the joke")
        ...     punchline: str = Field(description="The punchline to the joke")
        >>>
        >>> structured_client = client.with_structured_output(Joke)
        >>> joke_response = structured_client.invoke(
        ...     'Tell me a joke about programmers.'
        ... )
        >>> print(joke_response)  # Outputs a Joke object
        >>>
        >>> # Using rate limiter directly with any LangChain model
        >>> from langchain_openai import ChatOpenAI
        >>> from src.thoth.utilities.openrouter import OpenRouterRateLimiter
        >>>
        >>> # First, set up the rate limiter
        >>> rate_limiter = OpenRouterRateLimiter(api_key='your-api-key')
        >>> rate_limiter.setup()
        >>>
        >>> # Then use it with any LangChain model (even non-OpenRouter)
        >>> model = ChatOpenAI(
        ...     openai_api_key='sk-...',  # Standard OpenAI key
        ...     model_name='gpt-4',
        ...     rate_limiter=rate_limiter.get_langchain_limiter(),  # Use OpenRouter-based limiter
        ... )
        >>> response = model.invoke('Hello world')
    """  # noqa: W505

    def __init__(
        self,
        api_key: str | None = None,
        model: str | list[str] = 'openai/gpt-4',
        temperature: float = 0.7,
        max_tokens: int | None = None,
        site_url: str | None = None,
        site_name: str | None = None,
        streaming: bool = False,
        use_rate_limiter: bool = True,
        **kwargs: Any,
    ) -> None:
        """Initialize the OpenRouter client."""
        # Get API key from parameter or environment
        api_key = (
            api_key
            or os.getenv('OPENROUTER_API_KEY')
            or os.getenv('API_OPENROUTER_KEY')
        )
        if not api_key:
            raise ValueError(
                'OpenRouter API key not found. Please set OPENROUTER_API_KEY or API_OPENROUTER_KEY environment variable or pass api_key parameter.'
            )

        # Set up rate limiter if requested
        if use_rate_limiter:
            rate_limiter = OpenRouterRateLimiter(api_key=api_key)
            rate_limiter.setup()
            kwargs['rate_limiter'] = rate_limiter.get_langchain_limiter()

        # Set up headers for OpenRouter
        extra_headers = {
            'HTTP-Referer': site_url
            or 'http://localhost:8000',  # OpenRouter tracks usage by site
            'X-Title': site_name or 'Thoth Research Assistant',  # Shows in rankings
        }

        # Add extra_headers to model_kwargs to avoid warning
        if 'model_kwargs' not in kwargs:
            kwargs['model_kwargs'] = {}
        kwargs['model_kwargs']['extra_headers'] = extra_headers

        # Initialize the parent ChatOpenAI with OpenRouter configuration
        super().__init__(
            api_key=api_key,  # OpenRouter API key
            base_url='https://openrouter.ai/api/v1',  # OpenRouter API base URL
            model_name=model,  # Use model_name to pass model string or list
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            **kwargs,
        )

        # Store custom attributes as instance variables (fixes memory leak)
        # Using leading underscore to avoid conflicts with parent class
        self._use_rate_limiter = use_rate_limiter
        self._rate_limiter = None

        # Set up rate limiter if requested
        if use_rate_limiter and api_key:
            self._rate_limiter = OpenRouterRateLimiter(api_key=api_key)

    def _generate(self, *args, **kwargs):
        """
        Synchronous method for generating completions with rate limiting.

        This method follows LangChain's pattern where _generate is synchronous.
        """
        # Apply rate limiting if enabled (use instance variables)
        if self._use_rate_limiter and self._rate_limiter:
            # Call the synchronous acquire method
            self._rate_limiter.acquire()

        # Call the parent's synchronous _generate method
        return super()._generate(*args, **kwargs)
