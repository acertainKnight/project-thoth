import os
from typing import Any, ClassVar

from langchain_anthropic import ChatAnthropic
from langchain_core.rate_limiters import InMemoryRateLimiter


class AnthropicClient(ChatAnthropic):
    """Client for the native Anthropic API."""

    custom_attributes: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        api_key: str | None = None,
        model: str = 'claude-3-sonnet-20240229',
        temperature: float = 0.7,
        max_tokens: int | None = None,
        streaming: bool = False,
        use_rate_limiter: bool = True,
        requests_per_second: float = 10.0,
        **kwargs: Any,
    ) -> None:
        api_key = (
            api_key or os.getenv('ANTHROPIC_API_KEY') or os.getenv('API_ANTHROPIC_KEY')
        )
        if not api_key:
            raise ValueError(
                'Anthropic API key not found. Please set ANTHROPIC_API_KEY or API_ANTHROPIC_KEY environment variable or pass api_key parameter.'
            )

        if use_rate_limiter:
            limiter = InMemoryRateLimiter(requests_per_second=requests_per_second)
            kwargs['rate_limiter'] = limiter

        super().__init__(
            anthropic_api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            streaming=streaming,
            **kwargs,
        )

        instance_id = id(self)
        if instance_id not in self.custom_attributes:
            self.custom_attributes[instance_id] = {}
        self.custom_attributes[instance_id]['use_rate_limiter'] = use_rate_limiter
        self.custom_attributes[instance_id]['rate_limiter'] = kwargs.get('rate_limiter')

    def _generate(self, *args, **kwargs):
        instance_id = id(self)
        if self.custom_attributes.get(instance_id, {}).get(
            'use_rate_limiter'
        ) and self.custom_attributes.get(instance_id, {}).get('rate_limiter'):
            self.custom_attributes[instance_id]['rate_limiter'].acquire()
        return super()._generate(*args, **kwargs)
