"""Structured error classes for Thoth."""

from __future__ import annotations

from typing import Any

from loguru import logger


class ThothError(Exception):
    """Base exception for Thoth errors."""

    def __init__(
        self,
        error_code: str,
        message: str,
        recoverable: bool = False,
        context: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.recoverable = recoverable
        self.context = context or {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize error details to a dictionary."""
        return {
            'error_code': self.error_code,
            'message': self.message,
            'recoverable': self.recoverable,
            'context': self.context,
        }


class ServiceError(ThothError):
    """Error raised for service-related issues."""


class PipelineError(ThothError):
    """Error raised for pipeline failures."""


class DiscoveryError(ThothError):
    """Error raised for discovery problems."""


class LLMError(ThothError):
    """Error raised for LLM processing failures."""


class ErrorHandler:
    """Centralized error handler for Thoth."""

    def __init__(self) -> None:
        self.errors: list[ThothError] = []

    def handle(self, error: ThothError) -> bool:
        """Handle an error and return whether it is recoverable."""
        logger.error(f'{error.error_code}: {error.message}')
        self.errors.append(error)
        return error.recoverable

    def serialize_errors(self) -> list[dict[str, Any]]:
        """Serialize stored errors to a list of dictionaries."""
        return [err.to_dict() for err in self.errors]

    def clear(self) -> None:
        """Clear stored errors."""
        self.errors.clear()
