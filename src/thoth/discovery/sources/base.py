"""
Base classes for API sources.
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