"""
Article repository for managing discovered articles with deduplication.

This module provides specialized methods for article discovery tracking,
deduplication across sources, and processing status management.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from loguru import logger

from thoth.repositories.base import BaseRepository


class ArticleRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing discovered article records with deduplication."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize article repository."""
        super().__init__(postgres_service, table_name='discovered_articles', **kwargs)

    async def find_duplicate(
        self,
        doi: str | None = None,
        arxiv_id: str | None = None,
        title: str | None = None,
    ) -> UUID | None:
        """
        Find duplicate article by identifiers.

        Uses the database function to check DOI, arXiv ID, and normalized title.

        Args:
            doi: Digital Object Identifier
            arxiv_id: arXiv identifier
            title: Article title

        Returns:
            Optional[UUID]: Article ID if duplicate found, None otherwise
        """
        try:
            query = 'SELECT find_duplicate_article($1, $2, $3)'
            result = await self.postgres.fetchval(query, doi, arxiv_id, title)
            return result

        except Exception as e:
            logger.error(f'Failed to find duplicate article: {e}')
            return None

    async def get_or_create_article(
        self,
        doi: str | None = None,
        arxiv_id: str | None = None,
        title: str = '',
        **article_data,
    ) -> tuple[UUID, bool]:
        """
        Get existing article or create new one with deduplication.

        Args:
            doi: Digital Object Identifier
            arxiv_id: arXiv identifier
            title: Article title
            **article_data: Additional article metadata

        Returns:
            tuple[UUID, bool]: (article_id, created) where created=True if new article
        """
        try:
            # Check for existing article
            existing_id = await self.find_duplicate(doi, arxiv_id, title)

            if existing_id:
                # Update last_seen_at
                await self.postgres.execute(
                    'UPDATE discovered_articles SET last_seen_at = $1 WHERE id = $2',
                    datetime.now(),
                    existing_id,
                )
                return existing_id, False

            # Create new article
            data = {
                'doi': doi,
                'arxiv_id': arxiv_id,
                'title': title,
                'title_normalized': await self._normalize_title(title),
                **article_data,
            }

            article_id = await self.create(data)
            return article_id, True

        except Exception as e:
            logger.error(f'Failed to get or create article: {e}')
            raise

    async def link_to_discovery(
        self,
        article_id: UUID,
        source_id: UUID,
        discovery_query: str | None = None,
        relevance_score: float | None = None,
        rank_in_results: int | None = None,
        source_metadata: dict[str, Any] | None = None,
        external_id: str | None = None,
    ) -> bool:
        """
        Link article to a discovery source.

        Creates entry in article_discoveries table, handling duplicates gracefully.

        Args:
            article_id: Article UUID
            source_id: Discovery source UUID
            discovery_query: Query that found this article
            relevance_score: Relevance to discovery query
            rank_in_results: Position in search results
            source_metadata: Source-specific metadata
            external_id: Source-specific external ID

        Returns:
            bool: True if successful
        """
        try:
            query = """
                INSERT INTO article_discoveries (
                    article_id, source_id, discovery_query, relevance_score,
                    rank_in_results, source_metadata, external_id
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (article_id, source_id) DO UPDATE SET
                    relevance_score = GREATEST(
                        article_discoveries.relevance_score,
                        EXCLUDED.relevance_score
                    ),
                    source_metadata = EXCLUDED.source_metadata
                RETURNING id
            """

            await self.postgres.fetchval(
                query,
                article_id,
                source_id,
                discovery_query,
                relevance_score,
                rank_in_results,
                source_metadata,
                external_id,
            )

            return True

        except Exception as e:
            logger.error(
                f'Failed to link article {article_id} to source {source_id}: {e}'
            )
            return False

    async def has_been_processed(self, article_id: UUID, source_id: UUID) -> bool:
        """
        Check if article has been processed by a specific source.

        Args:
            article_id: Article UUID
            source_id: Discovery source UUID

        Returns:
            bool: True if processed, False otherwise
        """
        try:
            query = 'SELECT has_article_been_processed($1, $2)'
            result = await self.postgres.fetchval(query, article_id, source_id)
            return result or False

        except Exception as e:
            logger.error(
                f'Failed to check processing status for article {article_id}: {e}'
            )
            return False

    async def mark_as_processed(self, article_id: UUID, source_id: UUID) -> bool:
        """
        Mark article as processed for a specific source.

        Args:
            article_id: Article UUID
            source_id: Discovery source UUID

        Returns:
            bool: True if successful
        """
        try:
            query = 'SELECT mark_article_as_processed($1, $2)'
            result = await self.postgres.fetchval(query, article_id, source_id)
            return result or False

        except Exception as e:
            logger.error(f'Failed to mark article {article_id} as processed: {e}')
            return False

    async def get_new_articles_since(
        self, source_id: UUID, since: datetime
    ) -> list[dict[str, Any]]:
        """
        Get articles discovered by source since a timestamp.

        Args:
            source_id: Discovery source UUID
            since: Timestamp to check from

        Returns:
            list[dict[str, Any]]: List of article records
        """
        try:
            query = 'SELECT * FROM get_new_articles_since($1, $2)'
            results = await self.postgres.fetch(query, source_id, since)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get new articles for source {source_id}: {e}')
            return []

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
        try:
            query = """
                SELECT * FROM pending_articles
                LIMIT $1 OFFSET $2
            """
            results = await self.postgres.fetch(query, limit, offset)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get pending articles: {e}')
            return []

    async def get_multi_source_articles(
        self, min_sources: int = 2, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Get articles discovered by multiple sources.

        Articles found by multiple sources are often more relevant.

        Args:
            min_sources: Minimum number of sources that found the article
            limit: Maximum number of results

        Returns:
            list[dict[str, Any]]: List of multi-source articles
        """
        try:
            query = """
                SELECT * FROM multi_source_articles
                WHERE source_count >= $1
                LIMIT $2
            """
            results = await self.postgres.fetch(query, min_sources, limit)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get multi-source articles: {e}')
            return []

    async def get_by_doi(self, doi: str) -> dict[str, Any] | None:
        """
        Get article by DOI.

        Args:
            doi: Digital Object Identifier

        Returns:
            Optional[dict[str, Any]]: Article data or None
        """
        cache_key = self._cache_key('doi', doi)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = 'SELECT * FROM discovered_articles WHERE doi = $1'
            result = await self.postgres.fetchrow(query, doi)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get article by DOI {doi}: {e}')
            return None

    async def get_by_arxiv_id(self, arxiv_id: str) -> dict[str, Any] | None:
        """
        Get article by arXiv ID.

        Args:
            arxiv_id: arXiv identifier

        Returns:
            Optional[dict[str, Any]]: Article data or None
        """
        cache_key = self._cache_key('arxiv', arxiv_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = 'SELECT * FROM discovered_articles WHERE arxiv_id = $1'
            result = await self.postgres.fetchrow(query, arxiv_id)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get article by arXiv ID {arxiv_id}: {e}')
            return None

    async def update_processing_status(
        self,
        article_id: UUID,
        status: str,
        paper_id: UUID | None = None,
    ) -> bool:
        """
        Update article processing status.

        Args:
            article_id: Article UUID
            status: New processing status
            paper_id: Optional linked paper UUID

        Returns:
            bool: True if successful
        """
        try:
            data = {
                'processing_status': status,
                'processed_at': datetime.now() if status == 'completed' else None,
            }

            if paper_id:
                data['paper_id'] = paper_id

            return await self.update(article_id, data)

        except Exception as e:
            logger.error(
                f'Failed to update processing status for article {article_id}: {e}'
            )
            return False

    async def get_discovery_statistics(
        self,
        source_id: UUID | None = None,
    ) -> dict[str, Any]:
        """
        Get discovery statistics for all sources or a specific source.

        Args:
            source_id: Optional source UUID to filter by

        Returns:
            dict[str, Any]: Discovery statistics
        """
        try:
            if source_id:
                query = """
                    SELECT
                        COUNT(*) as total_articles,
                        COUNT(*) FILTER (WHERE processed) as processed_articles,
                        COUNT(*) FILTER (WHERE NOT processed) as pending_articles,
                        AVG(relevance_score) as avg_relevance_score,
                        MAX(discovered_at) as latest_discovery,
                        MIN(discovered_at) as earliest_discovery
                    FROM article_discoveries
                    WHERE source_id = $1
                """
                result = await self.postgres.fetchrow(query, source_id)
            else:
                query = """
                    SELECT
                        COUNT(DISTINCT article_id) as total_articles,
                        COUNT(*) FILTER (WHERE processed) as processed_discoveries,
                        COUNT(*) FILTER (WHERE NOT processed) as pending_discoveries,
                        COUNT(DISTINCT source_id) as total_sources,
                        AVG(relevance_score) as avg_relevance_score,
                        MAX(discovered_at) as latest_discovery,
                        MIN(discovered_at) as earliest_discovery
                    FROM article_discoveries
                """
                result = await self.postgres.fetchrow(query)

            return dict(result) if result else {}

        except Exception as e:
            logger.error(f'Failed to get discovery statistics: {e}')
            return {}

    async def _normalize_title(self, title: str) -> str:
        """
        Normalize title using database function.

        Args:
            title: Original title

        Returns:
            str: Normalized title
        """
        try:
            query = 'SELECT normalize_title($1)'
            result = await self.postgres.fetchval(query, title)
            return result or title.lower()

        except Exception as e:
            logger.warning(f'Failed to normalize title via database: {e}')
            # Fallback to Python implementation
            import re

            normalized = re.sub(r'[^\w\s]', '', title.lower())
            normalized = re.sub(r'\s+', ' ', normalized)
            return normalized.strip()
