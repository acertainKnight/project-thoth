"""
BioRxiv API source for preprint articles discovery.

This module provides the BioRxiv API source implementation for discovering
preprint articles from the BioRxiv server.
"""

import time
from datetime import datetime
from typing import Any

import requests
from loguru import logger

from thoth.utilities.schemas import ScrapedArticleMetadata

from .base import APISourceError, BaseAPISource


class BioRxivAPISource(BaseAPISource):
    """BioRxiv API source for preprint articles."""

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the BioRxiv API source.

        Args:
            rate_limit_delay: Delay between API requests in seconds.
        """
        self.base_url = 'https://api.biorxiv.org/details/biorxiv'
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Search BioRxiv for preprints.

        Args:
            config: Configuration dictionary containing search parameters.
                   Expected keys:
                   - start_date: Start date for search (YYYY-MM-DD)
                   - end_date: End date for search (YYYY-MM-DD)
            max_results: Maximum number of results to return.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered preprint articles.

        Example:
            >>> source = BioRxivAPISource()
            >>> config = {
            ...     'start_date': '2024-01-01',
            ...     'end_date': '2024-01-31',
            ... }
            >>> articles = source.search(config, max_results=10)

        Note:
            BioRxiv API searches by date range. If no dates are provided,
            it defaults to searching today's submissions.
        """
        try:
            start_date = config.get('start_date') or datetime.now().strftime('%Y-%m-%d')
            end_date = config.get('end_date') or start_date

            url = f'{self.base_url}/{start_date}/{end_date}'
            params = {'cursor': 0}

            logger.info(f'Searching BioRxiv with URL: {url}')

            self._rate_limit()
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            items = data.get('collection', [])[:max_results]
            articles: list[ScrapedArticleMetadata] = []

            for item in items:
                try:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f'Error parsing BioRxiv item: {e}')

            logger.info(f'Found {len(articles)} articles from BioRxiv')
            return articles

        except Exception as e:
            raise APISourceError(f'BioRxiv search failed: {e}') from e

    def _parse_item(self, item: dict[str, Any]) -> ScrapedArticleMetadata | None:
        """
        Parse a single BioRxiv item into ScrapedArticleMetadata.

        Args:
            item: BioRxiv API response item.

        Returns:
            ScrapedArticleMetadata: Parsed article metadata, or None if parsing fails.
        """
        title = item.get('title')
        if not title:
            return None

        # Parse authors (semicolon-separated string)
        authors = []
        author_str = item.get('authors')
        if author_str:
            authors = [
                author.strip() for author in author_str.split(';') if author.strip()
            ]

        # Extract other fields
        abstract = item.get('abstract')
        pub_date = item.get('date')
        journal = item.get('journal')
        doi = item.get('doi')
        url = item.get('biorxiv_url')
        pdf_url = item.get('biorxiv_pdf')

        return ScrapedArticleMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            publication_date=pub_date,
            journal=journal,
            doi=doi,
            url=url,
            pdf_url=pdf_url,
            tags=[],  # BioRxiv doesn't provide keywords in this API
            source='biorxiv',
            metadata={'version': item.get('version')},
        )

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()

    def get_required_config_keys(self) -> list[str]:
        """Get required configuration keys."""
        return []  # No required keys for BioRxiv

    def get_optional_config_keys(self) -> list[str]:
        """Get optional configuration keys."""
        return [
            'start_date',
            'end_date',
        ]
