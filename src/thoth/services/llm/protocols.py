"""Protocol definitions for LLM clients."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class UnifiedLLMClient(Protocol):
    """Protocol for unified LLM client interface."""

    def invoke(self, prompt: str, **kwargs: Any) -> str:
        """Invoke the model with a prompt and return the response text."""
        ...

    def invoke_structured(self, prompt: str, schema: type[T], **kwargs: Any) -> T:
        """Invoke the model and parse the response as the given schema."""
        ...

    def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        """Stream the response text from the model."""
        ...
