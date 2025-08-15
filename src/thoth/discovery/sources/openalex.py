"""
OpenAlex API source for scholarly works discovery.
"""

import time
from datetime import datetime
from typing import Any

import requests
from loguru import logger

from thoth.utilities.schemas import ScrapedArticleMetadata

from .base import APISourceError, BaseAPISource


class OpenAlexAPISource(BaseAPISource):
    """OpenAlex API source for discovering scholarly works."""

    def __init__(self, rate_limit_delay: float = 1.0):
        self.base_url = 'https://api.openalex.org/works'
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """Search OpenAlex for works."""
        try:
            params = {
                'per-page': min(max_results, 200),
                'sort': config.get('sort_by', 'relevance'),
            }

            keywords = config.get('keywords', [])
            if keywords:
                params['search'] = ' '.join(keywords)

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
                except Exception as e:  # pragma: no cover - log and continue
                    logger.error(f'Error parsing OpenAlex item: {e}')

            logger.info(f'Found {len(articles)} articles from OpenAlex')
            return articles

        except Exception as e:
            raise APISourceError(f'OpenAlex search failed: {e}') from e

    def _parse_item(self, item: dict[str, Any]) -> ScrapedArticleMetadata | None:
        title = item.get('title') or item.get('display_name')
        if not title:
            return None

        authors = []
        for a in item.get('authorships', []):
            name = a.get('author', {}).get('display_name')
            if name:
                authors.append(name)

        abstract = item.get('abstract')
        pub_date = item.get('publication_date')

        journal = None
        container = item.get('host_venue') or {}
        if container:
            journal = container.get('display_name')

        doi = item.get('doi')
        url = container.get('url') if container else None
        pdf_url = container.get('pdf_url') if container else None

        keywords = [
            c.get('display_name')
            for c in item.get('concepts', [])
            if c.get('display_name')
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
            keywords=keywords,
            source='openalex',
            scrape_timestamp=datetime.now().isoformat(),
            additional_metadata={'id': item.get('id')},
        )

    def _rate_limit(self) -> None:
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()