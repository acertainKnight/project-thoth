"""
Client for the OpenRouter API leveraging the OpenAI API.
"""

import os
import time
from typing import Any, ClassVar

import requests
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openai import ChatOpenAI
from loguru import logger


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
            response = requests.get(
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


class OpenRouterClient(ChatOpenAI):
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
        model (str): Model identifier (e.g. "openai/gpt-4", "anthropic/claude-2.1")
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

    # Store custom non-Pydantic attributes as class variables
    custom_attributes: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        api_key: str | None = None,
        model: str = 'openai/gpt-4',
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

        # Initialize the parent ChatOpenAI with OpenRouter configuration
        super().__init__(
            api_key=api_key,  # OpenRouter API key
            base_url='https://openrouter.ai/api/v1',  # OpenRouter API base URL
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            extra_headers=extra_headers,
            **kwargs,
        )

        # Store our custom attributes in the class dictionary
        # instead of trying to set them as instance attributes
        instance_id = id(self)
        if instance_id not in self.custom_attributes:
            self.custom_attributes[instance_id] = {}

        self.custom_attributes[instance_id]['use_rate_limiter'] = use_rate_limiter
        self.custom_attributes[instance_id]['rate_limiter'] = None

        # Set up rate limiter if requested
        if use_rate_limiter and api_key:
            self.custom_attributes[instance_id]['rate_limiter'] = OpenRouterRateLimiter(
                api_key=api_key
            )

    def _generate(self, *args, **kwargs):
        """
        Synchronous method for generating completions with rate limiting.

        This method follows LangChain's pattern where _generate is synchronous.
        """
        instance_id = id(self)
        use_rate_limiter = self.custom_attributes.get(instance_id, {}).get(
            'use_rate_limiter', False
        )
        rate_limiter = self.custom_attributes.get(instance_id, {}).get('rate_limiter')

        # Apply rate limiting if enabled
        if use_rate_limiter and rate_limiter:
            # Call the synchronous acquire method
            rate_limiter.acquire()

        # Call the parent's synchronous _generate method
        return super()._generate(*args, **kwargs)
