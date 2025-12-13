"""
OpenAlex API source for scholarly works discovery.

This module provides the OpenAlex API source implementation for discovering
scholarly works from the OpenAlex database.
"""

import time
from typing import Any

import requests
from loguru import logger

from thoth.utilities.schemas import ScrapedArticleMetadata

from .base import APISourceError, BaseAPISource


class OpenAlexAPISource(BaseAPISource):
    """OpenAlex API source for discovering scholarly works."""

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the OpenAlex API source.

        Args:
            rate_limit_delay: Delay between API requests in seconds.
        """
        self.base_url = 'https://api.openalex.org/works'
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Search OpenAlex for works.

        Args:
            config: Configuration dictionary containing search parameters.
                   Expected keys:
                   - keywords: List of keywords to search for
                   - start_date: Start date for search (YYYY-MM-DD)
                   - end_date: End date for search (YYYY-MM-DD)
                   - sort_by: Sort criteria ('relevance', 'publication_date',
                        'cited_by_count', etc.)
            max_results: Maximum number of results to return.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.

        Example:
            >>> source = OpenAlexAPISource()
            >>> config = {
            ...     'keywords': ['machine learning', 'neural networks'],
            ...     'sort_by': 'publication_date',
            ...     'start_date': '2023-01-01',
            ... }
            >>> articles = source.search(config, max_results=10)
        """
        try:
            params = {
                'per-page': min(max_results, 200),  # OpenAlex API limit
                'sort': config.get('sort_by', 'relevance'),
            }

            # Add search query from keywords
            keywords = config.get('keywords', [])
            if keywords:
                params['search'] = ' '.join(keywords)

            # Add date filters
            filters = []
            start_date = config.get('start_date')
            end_date = config.get('end_date')
            if start_date:
                filters.append(f'from_publication_date:{start_date}')
            if end_date:
                filters.append(f'to_publication_date:{end_date}')
            if filters:
                params['filter'] = ','.join(filters)

            logger.info(f'Searching OpenAlex with params: {params}')

            self._rate_limit()
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            items = data.get('results', [])
            articles: list[ScrapedArticleMetadata] = []

            for item in items:
                try:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f'Error parsing OpenAlex item: {e}')

            logger.info(f'Found {len(articles)} articles from OpenAlex')
            return articles

        except Exception as e:
            raise APISourceError(f'OpenAlex search failed: {e}') from e

    def _parse_item(self, item: dict[str, Any]) -> ScrapedArticleMetadata | None:
        """
        Parse a single OpenAlex item into ScrapedArticleMetadata.

        Args:
            item: OpenAlex API response item.

        Returns:
            ScrapedArticleMetadata: Parsed article metadata, or None if parsing fails.
        """
        title = item.get('title') or item.get('display_name')
        if not title:
            return None

        # Parse authors
        authors = []
        for authorship in item.get('authorships', []):
            author_info = authorship.get('author', {})
            name = author_info.get('display_name')
            if name:
                authors.append(name)

        # Extract abstract
        abstract = item.get('abstract')

        # Extract publication date
        pub_date = item.get('publication_date')

        # Extract journal information
        journal = None
        container = item.get('host_venue') or {}
        if container:
            journal = container.get('display_name')

        # Extract DOI and URLs
        doi = item.get('doi')
        url = container.get('url') if container else None
        pdf_url = container.get('pdf_url') if container else None

        # Extract keywords/concepts
        keywords = [
            concept.get('display_name')
            for concept in item.get('concepts', [])
            if concept.get('display_name')
        ]

        return ScrapedArticleMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            publication_date=pub_date,
            journal=journal,
            doi=doi,
            url=url,
            pdf_url=pdf_url,
            tags=keywords,
            source='openalex',
            metadata={'id': item.get('id')},
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
        return []  # No required keys for OpenAlex

    def get_optional_config_keys(self) -> list[str]:
        """Get optional configuration keys."""
        return [
            'keywords',
            'start_date',
            'end_date',
            'sort_by',
        ]
