"""
Base service class for Thoth services.

This module provides the base class and common functionality for all services.
"""

from pathlib import Path  # noqa: I001
from typing import Any

from jinja2 import Environment, FileSystemLoader
from loguru import logger

from thoth.config import config, Config  # noqa: F401


class ServiceError(Exception):
    """Base exception for service layer errors."""

    pass


class TemplateServiceMixin:
    """Mixin for services that use Jinja templates."""

    def setup_template_environment(self, prompts_dir: Path | None = None):
        """Set up Jinja template environments for different providers."""
        if not hasattr(self, 'config'):
            raise RuntimeError('TemplateServiceMixin requires config attribute')

        self.prompts_dir = prompts_dir or Path(self.config.prompts_dir)
        self.jinja_envs = {}

        # Common providers that services use
        for provider in ['openai', 'google', 'anthropic']:
            provider_dir = self.prompts_dir / provider
            if provider_dir.exists():
                self.jinja_envs[provider] = Environment(
                    loader=FileSystemLoader(provider_dir)
                )

    def get_template_env(self, provider: str) -> Environment:
        """Get Jinja environment for a specific provider."""
        if not hasattr(self, 'jinja_envs'):
            self.setup_template_environment()
        return self.jinja_envs.get(provider)


class ClientManagerMixin:
    """Mixin for services that manage multiple client instances."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._clients: dict[str, Any] = {}

    def get_or_create_client(self, key: str, factory_func):
        """Get existing client or create new one using factory function."""
        if key not in self._clients:
            self._clients[key] = factory_func()
        return self._clients[key]

    def clear_clients(self):
        """Clear all cached clients."""
        self._clients.clear()


class BaseService:
    """
    Base class for all Thoth services.

    Provides common functionality like configuration access, logging,
    and error handling patterns.
    """

    def __init__(self, thoth_config: Config | None = None):
        """
        Initialize the base service.

        Args:
            config: Optional configuration object. If not provided, will load from
                environment.
        """
        from thoth.config import config as global_config

        self._config = thoth_config or global_config
        self._logger = logger.bind(service=self.__class__.__name__)

    @property
    def config(self) -> Config:  # noqa: F811
        """Get the configuration object."""
        return self._config

    @property
    def logger(self):
        """Get the logger instance for this service."""
        return self._logger

    def initialize(self) -> None:
        """
        Initialize the service.

        Default implementation logs initialization. Services can override
        this method to perform additional setup.
        """
        service_name = self.__class__.__name__.replace('Service', '').lower()
        self.logger.info(
            f'{service_name.replace("_", " ").title()} service initialized'
        )

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

        # Check if this is an expected API key error during early initialization
        error_str = str(error)
        if 'API key not found' in error_str or (
            'OPENROUTER' in error_str.upper() and 'API' in error_str.upper()
        ):
            self.logger.debug(error_msg)
        else:
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
