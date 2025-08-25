"""
CrossRef API source for scholarly works discovery.

This module provides the CrossRef API source implementation for discovering
scholarly works and articles from the CrossRef database.
"""

import time
from typing import Any

import requests
from loguru import logger

from thoth.utilities.schemas import ScrapedArticleMetadata

from .base import APISourceError, BaseAPISource


class CrossRefAPISource(BaseAPISource):
    """CrossRef API source for discovering scholarly works."""

    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize the CrossRef API source.

        Args:
            rate_limit_delay: Delay between API requests in seconds.
        """
        self.base_url = 'https://api.crossref.org/works'
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """
        Search CrossRef for works.

        Args:
            config: Configuration dictionary containing search parameters.
                   Expected keys:
                   - keywords: List of keywords to search for
                   - start_date: Start date for search (YYYY-MM-DD)
                   - end_date: End date for search (YYYY-MM-DD)
                   - sort_by: Sort criteria ('relevance', 'published', 'score', etc.)
                   - sort_order: Sort order ('desc' or 'asc')
            max_results: Maximum number of results to return.

        Returns:
            list[ScrapedArticleMetadata]: List of discovered articles.

        Example:
            >>> source = CrossRefAPISource()
            >>> config = {
            ...     'keywords': ['machine learning', 'artificial intelligence'],
            ...     'sort_by': 'published',
            ...     'sort_order': 'desc',
            ... }
            >>> articles = source.search(config, max_results=10)
        """
        try:
            params = {
                'rows': min(max_results, 100),  # CrossRef API limit
                'sort': config.get('sort_by', 'relevance'),
                'order': config.get('sort_order', 'desc'),
            }

            # Build query string
            keywords = config.get('keywords', [])
            if keywords:
                params['query'] = ' '.join(keywords)

            # Date filters
            start_date = config.get('start_date')
            end_date = config.get('end_date')
            filters = []
            if start_date:
                filters.append(f'from-pub-date:{start_date}')
            if end_date:
                filters.append(f'until-pub-date:{end_date}')
            if filters:
                params['filter'] = ','.join(filters)

            logger.info(f'Searching CrossRef with params: {params}')

            self._rate_limit()
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            items = data.get('message', {}).get('items', [])
            articles: list[ScrapedArticleMetadata] = []

            for item in items:
                try:
                    article = self._parse_item(item)
                    if article:
                        articles.append(article)
                except Exception as e:
                    logger.error(f'Error parsing CrossRef item: {e}')

            logger.info(f'Found {len(articles)} articles from CrossRef')
            return articles

        except Exception as e:
            raise APISourceError(f'CrossRef search failed: {e}') from e

    def _parse_item(self, item: dict[str, Any]) -> ScrapedArticleMetadata | None:
        """
        Parse a single CrossRef item into ScrapedArticleMetadata.

        Args:
            item: CrossRef API response item.

        Returns:
            ScrapedArticleMetadata: Parsed article metadata, or None if parsing fails.
        """
        title_list = item.get('title', [])
        title = title_list[0] if title_list else None
        if not title:
            return None

        # Parse authors
        authors = []
        for author_info in item.get('author', []):
            given = author_info.get('given')
            family = author_info.get('family')
            if given and family:
                authors.append(f'{family}, {given}')
            elif family:
                authors.append(family)

        # Extract abstract
        abstract = item.get('abstract')

        # Parse publication date
        pub_date_parts = item.get('published-print') or item.get('published-online')
        pub_date = None
        if pub_date_parts and 'date-parts' in pub_date_parts:
            parts = pub_date_parts['date-parts'][0]
            # Pad parts to ensure proper date format
            padded_parts = []
            for i, part in enumerate(parts):
                if i == 0:  # Year
                    padded_parts.append(str(part))
                else:  # Month/Day
                    padded_parts.append(str(part).zfill(2))
            pub_date = '-'.join(padded_parts)

        # Extract journal
        journal_list = item.get('container-title', [])
        journal = journal_list[0] if journal_list else None

        # Extract DOI and URL
        doi = item.get('DOI')
        url = item.get('URL')

        # Look for PDF URL in links
        pdf_url = None
        for link in item.get('link', []):
            if link.get('content-type') == 'application/pdf':
                pdf_url = link.get('URL')
                break

        # Extract keywords/subjects
        keywords = item.get('subject', [])

        return ScrapedArticleMetadata(
            title=title,
            authors=authors,
            abstract=abstract,
            published_date=pub_date,
            journal=journal,
            doi=doi,
            url=url,
            pdf_url=pdf_url,
            tags=keywords,
            source='crossref',
            metadata={'type': item.get('type')},
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
        return []  # No required keys for CrossRef

    def get_optional_config_keys(self) -> list[str]:
        """Get optional configuration keys."""
        return [
            'keywords',
            'start_date',
            'end_date',
            'sort_by',
            'sort_order',
        ]
