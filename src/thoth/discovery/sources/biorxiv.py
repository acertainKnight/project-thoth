"""
BioRxiv API source for preprint discovery.
"""

import time
from datetime import datetime
from typing import Any

import requests
from loguru import logger

from thoth.utilities.schemas import ScrapedArticleMetadata

from .base import APISourceError, BaseAPISource


class BioRxivAPISource(BaseAPISource):
    """bioRxiv API source for preprint articles."""

    def __init__(self, rate_limit_delay: float = 1.0):
        self.base_url = 'https://api.biorxiv.org/details/biorxiv'
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0

    def search(
        self, config: dict[str, Any], max_results: int = 50
    ) -> list[ScrapedArticleMetadata]:
        """Search bioRxiv for preprints."""
        try:
            start_date = config.get('start_date') or datetime.now().strftime('%Y-%m-%d')
            end_date = config.get('end_date') or start_date

            url = f'{self.base_url}/{start_date}/{end_date}'
            params = {'cursor': 0}

            logger.info(f'Searching bioRxiv with URL: {url}')

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
                except Exception as e:  # pragma: no cover - log and continue
                    logger.error(f'Error parsing bioRxiv item: {e}')

            logger.info(f'Found {len(articles)} articles from bioRxiv')
            return articles

        except Exception as e:
            raise APISourceError(f'bioRxiv search failed: {e}') from e

    def _parse_item(self, item: dict[str, Any]) -> ScrapedArticleMetadata | None:
        title = item.get('title')
        if not title:
            return None

        authors = []
        author_str = item.get('authors')
        if author_str:
            authors = [a.strip() for a in author_str.split(';') if a.strip()]

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
            keywords=[],
            source='biorxiv',
            scrape_timestamp=datetime.now().isoformat(),
            additional_metadata={'version': item.get('version')},
        )

    def _rate_limit(self) -> None:
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()