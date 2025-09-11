"""Base configuration classes and logging utilities."""

import sys
from typing import TYPE_CHECKING

from loguru import logger
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseSettings):
    """Configuration for model parameters."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        extra='ignore',
    )
    temperature: float = Field(0.9, description='Model temperature')
    max_tokens: int = Field(8000, description='Model max tokens for generation')
    top_p: float = Field(1.0, description='Model top p')
    streaming: bool = Field(False, description='Model streaming')
    use_rate_limiter: bool = Field(True, description='Model use rate limiter')


class BaseLLMConfig(BaseSettings):
    """Base configuration class for LLM models."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='allow',
        env_nested_delimiter='_',
    )

    model: str = Field('openai/gpt-4o-mini', description='LLM model identifier')
    model_settings: ModelConfig = Field(
        default_factory=ModelConfig, description='Model parameters'
    )
    max_output_tokens: int = Field(8000, description='Max tokens for generation')
    max_context_length: int = Field(8000, description='Max context length for model')


class BaseServerConfig(BaseSettings):
    """Base configuration for server endpoints."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )

    host: str = Field('localhost', description='Host to bind to')
    port: int = Field(8000, description='Port to bind to')
    auto_start: bool = Field(False, description='Whether to auto-start')


if TYPE_CHECKING:
    from . import ThothConfig


def setup_logging(config: 'ThothConfig') -> None:
    """Set up logging configuration using loguru.

    Args:
        config (ThothConfig): The Thoth configuration object containing logging
            settings.

    Returns:
        None: Sets up loguru logger with file and console handlers.

    Example:
        >>> config = get_config()
        >>> setup_logging(config)
    """
    # Remove default loguru handler
    logger.remove()
    # Add console handler with configured level
    logger.add(
        sys.stderr,
        format=config.logging_config.logformat,
        level=config.logging_config.level,
        colorize=True,
    )

    # Add file handler
    logger.add(
        config.logging_config.filename,
        format=config.logging_config.logformat,
        level=config.logging_config.file_level,
        rotation='10 MB',
        mode=config.logging_config.filemode,
    )
