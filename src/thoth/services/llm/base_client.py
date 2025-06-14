"""Common functionality shared by LLM clients."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel

T = TypeVar("T")


class BaseLLMClient(BaseChatModel):
    """Base class providing unified LLM client helpers."""

    def invoke(self, prompt: str, **kwargs: Any) -> str:  # type: ignore[override]
        """Return the response text for the given prompt."""
        response = super().invoke(prompt, **kwargs)
        return getattr(response, "content", str(response))

    def invoke_structured(self, prompt: str, schema: type[T], **kwargs: Any) -> T:
        """Return the response parsed as ``schema``."""
        structured = self.with_structured_output(schema)
        return structured.invoke(prompt, **kwargs)

    def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:  # type: ignore[override]
        """Stream the response text for the given prompt."""
        for chunk in super().stream(prompt, **kwargs):
            yield getattr(chunk, "content", str(chunk))
