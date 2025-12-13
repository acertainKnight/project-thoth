"""
Discovery service extension with article deduplication logic.

This module provides methods to integrate article deduplication into the
discovery workflow, preventing duplicate processing across sources.
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from loguru import logger

from thoth.repositories.article_repository import ArticleRepository
from thoth.utilities.schemas import ScrapedArticleMetadata


class DiscoveryDeduplicationMixin:
    """
    Mixin to add deduplication capabilities to DiscoveryService.

    This should be mixed into DiscoveryService to provide article
    deduplication and cross-discovery tracking.
    """

    def __init__(self, *args, **kwargs):
        """Initialize deduplication components."""
        super().__init__(*args, **kwargs)
        self.article_repository: ArticleRepository | None = None

    def _init_article_repository(self, postgres_service) -> None:
        """
        Initialize article repository for deduplication.

        Args:
            postgres_service: PostgreSQL service instance
        """
        if not self.article_repository:
            self.article_repository = ArticleRepository(postgres_service)
            logger.info('Article repository initialized for deduplication')

    async def process_discovered_article(
        self,
        metadata: ScrapedArticleMetadata,
        source_id: UUID,
        discovery_query: str | None = None,
        relevance_score: float | None = None,
    ) -> tuple[UUID, bool]:
        """
        Process discovered article with deduplication.

        This method:
        1. Checks if article already exists (by DOI, arXiv ID, or title)
        2. Creates new article or updates existing one
        3. Links article to discovery source
        4. Returns article ID and whether it's new

        Args:
            metadata: Scraped article metadata
            source_id: UUID of discovery source
            discovery_query: Optional query that found this article
            relevance_score: Optional relevance score

        Returns:
            tuple[UUID, bool]: (article_id, is_new_article)
        """
        if not self.article_repository:
            raise RuntimeError('Article repository not initialized')

        try:
            # Extract identifiers
            doi = metadata.doi
            arxiv_id = metadata.arxiv_id
            title = metadata.title

            # Prepare article data
            article_data = {
                'authors': metadata.authors or [],
                'first_author': metadata.authors[0] if metadata.authors else None,
                'abstract': metadata.abstract,
                'publication_date': (
                    datetime.fromisoformat(metadata.publication_date)
                    if metadata.publication_date
                    else None
                ),
                'journal': metadata.journal,
                'url': metadata.url,
                'pdf_url': metadata.pdf_url,
                'keywords': metadata.keywords or [],
                'metadata': metadata.additional_metadata or {},
                'processing_status': 'pending',
                'priority': 5,
            }

            # Get or create article (with deduplication)
            article_id, is_new = await self.article_repository.get_or_create_article(
                doi=doi,
                arxiv_id=arxiv_id,
                title=title,
                **article_data,
            )

            # Link to discovery source
            await self.article_repository.link_to_discovery(
                article_id=article_id,
                source_id=source_id,
                discovery_query=discovery_query,
                relevance_score=relevance_score,
                source_metadata={
                    'source': metadata.source,
                    'scrape_timestamp': metadata.scrape_timestamp,
                },
                external_id=doi or arxiv_id,
            )

            if is_new:
                logger.info(f'New article discovered: {title[:60]}...')
            else:
                logger.debug(
                    f'Article already exists, linked to new source: {title[:60]}...'
                )

            return article_id, is_new

        except Exception as e:
            logger.error(f'Failed to process discovered article: {e}')
            raise

    async def has_article_been_processed(
        self, article_id: UUID, source_id: UUID
    ) -> bool:
        """
        Check if article has been processed by a specific source.

        Args:
            article_id: Article UUID
            source_id: Discovery source UUID

        Returns:
            bool: True if already processed, False otherwise
        """
        if not self.article_repository:
            return False

        return await self.article_repository.has_been_processed(article_id, source_id)

    async def mark_article_as_processed(
        self, article_id: UUID, source_id: UUID
    ) -> bool:
        """
        Mark article as processed for a specific source.

        Args:
            article_id: Article UUID
            source_id: Discovery source UUID

        Returns:
            bool: True if successful
        """
        if not self.article_repository:
            return False

        return await self.article_repository.mark_as_processed(article_id, source_id)

    async def get_new_articles_since(
        self, source_id: UUID, since: datetime
    ) -> list[dict[str, Any]]:
        """
        Get new articles discovered since a timestamp for a source.

        This is useful for incremental processing of discovered articles.

        Args:
            source_id: Discovery source UUID
            since: Timestamp to check from

        Returns:
            list[dict[str, Any]]: List of new article records
        """
        if not self.article_repository:
            return []

        return await self.article_repository.get_new_articles_since(source_id, since)

    async def get_pending_articles(
        self, limit: int = 50, offset: int = 0
    ) -> list[dict[str, Any]]:
        """
        Get pending articles ordered by priority.

        Args:
            limit: Maximum number of results
            offset: Number of records to skip

        Returns:
            list[dict[str, Any]]: List of pending articles
        """
        if not self.article_repository:
            return []

        return await self.article_repository.get_pending_articles(limit, offset)

    async def get_multi_source_articles(
        self, min_sources: int = 2, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get articles discovered by multiple sources.

        Articles found by multiple sources are typically more relevant.

        Args:
            min_sources: Minimum number of sources
            limit: Maximum number of results

        Returns:
            list[dict[str, Any]]: List of multi-source articles
        """
        if not self.article_repository:
            return []

        return await self.article_repository.get_multi_source_articles(
            min_sources, limit
        )

    async def update_article_processing_status(
        self,
        article_id: UUID,
        status: str,
        paper_id: UUID | None = None,
    ) -> bool:
        """
        Update article processing status.

        Args:
            article_id: Article UUID
            status: New status (pending, downloaded, processing, completed, failed, ignored)
            paper_id: Optional linked paper UUID

        Returns:
            bool: True if successful
        """
        if not self.article_repository:
            return False

        return await self.article_repository.update_processing_status(
            article_id, status, paper_id
        )

    async def get_discovery_statistics(
        self, source_id: UUID | None = None
    ) -> dict[str, Any]:
        """
        Get discovery statistics.

        Args:
            source_id: Optional source UUID to filter by

        Returns:
            dict[str, Any]: Discovery statistics
        """
        if not self.article_repository:
            return {}

        return await self.article_repository.get_discovery_statistics(source_id)

    async def process_articles_batch(
        self,
        articles: list[ScrapedArticleMetadata],
        source_id: UUID,
        discovery_query: str | None = None,
    ) -> dict[str, int]:
        """
        Process a batch of discovered articles with deduplication.

        This is an efficient way to process multiple articles at once.

        Args:
            articles: List of scraped article metadata
            source_id: Discovery source UUID
            discovery_query: Optional query that found these articles

        Returns:
            dict[str, int]: Statistics (new_articles, existing_articles, errors)
        """
        stats = {
            'new_articles': 0,
            'existing_articles': 0,
            'errors': 0,
        }

        tasks = []
        for i, article in enumerate(articles):
            # Calculate relevance score based on position (earlier = more relevant)
            relevance_score = 1.0 - (i / len(articles)) if articles else 0.5

            tasks.append(
                self.process_discovered_article(
                    metadata=article,
                    source_id=source_id,
                    discovery_query=discovery_query,
                    relevance_score=relevance_score,
                )
            )

        # Process all articles concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                stats['errors'] += 1
                logger.error(f'Error processing article: {result}')
            else:
                article_id, is_new = result
                if is_new:
                    stats['new_articles'] += 1
                else:
                    stats['existing_articles'] += 1

        logger.info(
            f"Batch processing complete: {stats['new_articles']} new, "
            f"{stats['existing_articles']} existing, {stats['errors']} errors"
        )

        return stats

    async def deduplicate_existing_articles(self) -> dict[str, int]:
        """
        Run deduplication on existing articles in the database.

        This is a maintenance operation to clean up duplicate articles
        that may have been created before deduplication was implemented.

        Returns:
            dict[str, int]: Statistics (duplicates_found, duplicates_merged)
        """
        if not self.article_repository:
            return {'duplicates_found': 0, 'duplicates_merged': 0}

        stats = {
            'duplicates_found': 0,
            'duplicates_merged': 0,
        }

        try:
            # This would need a more sophisticated implementation
            # For now, just log that the operation was attempted
            logger.info('Deduplication maintenance operation started')

            # Query all articles
            all_articles = await self.article_repository.list_all(limit=10000)

            # Group by identifiers and find duplicates
            doi_groups: dict[str, list[dict]] = {}
            arxiv_groups: dict[str, list[dict]] = {}
            title_groups: dict[str, list[dict]] = {}

            for article in all_articles:
                if article.get('doi'):
                    doi = article['doi']
                    doi_groups.setdefault(doi, []).append(article)

                if article.get('arxiv_id'):
                    arxiv_id = article['arxiv_id']
                    arxiv_groups.setdefault(arxiv_id, []).append(article)

                if article.get('title_normalized'):
                    title = article['title_normalized']
                    title_groups.setdefault(title, []).append(article)

            # Count duplicates
            for group in [doi_groups, arxiv_groups, title_groups]:
                for identifier, articles in group.items():
                    if len(articles) > 1:
                        stats['duplicates_found'] += len(articles) - 1

            logger.info(
                f"Deduplication scan complete: {stats['duplicates_found']} duplicates found"
            )

            return stats

        except Exception as e:
            logger.error(f'Failed to run deduplication maintenance: {e}')
            return stats


# Integration helper functions


async def initialize_deduplication_for_service(
    service, postgres_service
) -> None:
    """
    Initialize deduplication for a discovery service.

    Args:
        service: DiscoveryService instance (with mixin)
        postgres_service: PostgreSQL service instance
    """
    if hasattr(service, '_init_article_repository'):
        service._init_article_repository(postgres_service)
        logger.info('Deduplication initialized for discovery service')
    else:
        logger.warning(
            'Discovery service does not have deduplication mixin - skipping initialization'
        )


def check_article_already_exists(
    metadata: ScrapedArticleMetadata,
) -> tuple[str | None, str | None, str]:
    """
    Extract deduplication keys from article metadata.

    Args:
        metadata: Scraped article metadata

    Returns:
        tuple[str | None, str | None, str]: (doi, arxiv_id, title)
    """
    return (
        metadata.doi,
        metadata.arxiv_id,
        metadata.title,
    )
