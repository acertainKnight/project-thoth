"""
Base classes and common functionality for discovery API sources.

This module provides the abstract base class and common exceptions
that all API sources should inherit from and use.
"""

from abc import ABC, abstractmethod
from typing import Any

from thoth.utilities.schemas import ScrapedArticleMetadata


class APISourceError(Exception):
    """Exception raised for errors in API sources."""

    pass


class BaseAPISource(ABC):
    """
    Base class for API sources.

    This abstract class defines the interface for API sources that can
    search for articles and return standardized metadata.
    """

    @abstractmethod
    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Search for articles using the API.

        Args:
            config: Configuration dictionary for the search.
            max_results: Maximum number of results to return.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.
        """
        pass

    def get_source_name(self) -> str:
        """
        Get the name of this source.

        Returns:
            str: Source name (defaults to class name without 'APISource' suffix)
        """
        class_name = self.__class__.__name__
        if class_name.endswith('APISource'):
            return class_name[:-9].lower()  # Remove 'APISource' suffix
        return class_name.lower()

    def validate_config(self, config: dict[str, Any]) -> dict[str, str]:
        """
        Validate the configuration for this source.

        Args:
            config: Configuration dictionary to validate

        Returns:
            dict[str, str]: Dictionary of validation errors (empty if valid)
        """
        # Default implementation - subclasses can override
        return {}

    def get_required_config_keys(self) -> list[str]:
        """
        Get the list of required configuration keys for this source.

        Returns:
            list[str]: List of required configuration keys
        """
        # Default implementation - subclasses should override
        return []

    def get_optional_config_keys(self) -> list[str]:
        """
        Get the list of optional configuration keys for this source.

        Returns:
            list[str]: List of optional configuration keys
        """
        # Default implementation - subclasses can override
        return []
