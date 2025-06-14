"""
Base service class for Thoth services.

This module provides the base class and common functionality for all services.
"""

from abc import ABC, abstractmethod
from typing import Any

from loguru import logger

from thoth.utilities.config import ThothConfig, get_config


class ServiceError(Exception):
    """Base exception for service layer errors."""

    pass


class BaseService(ABC):
    """
    Base class for all Thoth services.

    Provides common functionality like configuration access, logging,
    and error handling patterns.
    """

    def __init__(self, config: ThothConfig | None = None):
        """
        Initialize the base service.

        Args:
            config: Optional configuration object. If not provided, will load from
                environment.
        """
        self._config = config or get_config()
        self._logger = logger.bind(service=self.__class__.__name__)

    @property
    def config(self) -> ThothConfig:
        """Get the configuration object."""
        return self._config

    @property
    def logger(self):
        """Get the logger instance for this service."""
        return self._logger

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the service. Must be implemented by subclasses.

        This method should be called after instantiation to set up any
        required resources or connections.
        """
        pass

    def handle_error(self, error: Exception, context: str = '') -> str:
        """
        Handle an error with consistent logging and formatting.

        Args:
            error: The exception that occurred
            context: Additional context about what was happening

        Returns:
            str: Formatted error message
        """
        error_msg = f'Error in {self.__class__.__name__}'
        if context:
            error_msg += f' while {context}'
        error_msg += f': {error!s}'

        self.logger.error(error_msg)
        return error_msg

    def validate_input(self, **kwargs) -> None:
        """
        Validate input parameters.

        Args:
            **kwargs: Parameters to validate

        Raises:
            ServiceError: If validation fails
        """
        # Base implementation - can be overridden by subclasses
        for key, value in kwargs.items():
            if value is None:
                raise ServiceError(f"Required parameter '{key}' is None")

    def log_operation(self, operation: str, **details: Any) -> None:
        """
        Log a service operation with details.

        Args:
            operation: Name of the operation
            **details: Additional details to log
        """
        self.logger.info(f'{operation}', **details)

    def health_check(self) -> dict[str, str]:
        """Return basic health status for the service."""
        return {
            'service': self.__class__.__name__,
            'status': 'healthy',
        }
