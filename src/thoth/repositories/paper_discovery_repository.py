"""
Paper discovery repository for tracking paper discovery events.

This module tracks which papers were discovered by which sources,
enabling deduplication and source attribution.
"""

from typing import Any, Dict, List  # noqa: I001, UP035
from datetime import datetime, timedelta
from loguru import logger

from thoth.repositories.base import BaseRepository


class PaperDiscoveryRepository(BaseRepository[Dict[str, Any]]):  # noqa: UP006
    """Repository for managing paper discovery tracking records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize paper discovery repository."""
        super().__init__(postgres_service, table_name='paper_discoveries', **kwargs)

    async def record_discovery(
        self,
        paper_id: str,
        source_id: str,
        source_metadata: Dict[str, Any] | None = None,  # noqa: UP006
        discovered_at: datetime | None = None,
        user_id: str | None = None,
    ) -> str | None:
        """
        Record that a paper was discovered by a source.

        Args:
            paper_id: UUID of the paper
            source_id: UUID of the discovery source
            source_metadata: Additional metadata from the source
            discovered_at: Discovery timestamp (defaults to now)

        Returns:
            Optional[str]: Discovery record ID or None if already exists
        """
        if discovered_at is None:
            discovered_at = datetime.now()

        try:
            user_id = self._resolve_user_id(user_id, 'record_discovery')
            query = """
                INSERT INTO paper_discoveries (paper_id, source_id, discovered_at, source_metadata, user_id)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (paper_id, source_id, user_id) DO NOTHING
                RETURNING id
            """
            result = await self.postgres.fetchval(
                query, paper_id, source_id, discovered_at, source_metadata, user_id
            )

            # Invalidate cache
            self._invalidate_cache()

            if result:
                logger.debug(
                    f'Recorded discovery of paper {paper_id} by source {source_id}'
                )
                return str(result)
            else:
                logger.debug(
                    f'Paper {paper_id} already recorded for source {source_id}'
                )
                return None

        except Exception as e:
            logger.error(f'Failed to record discovery: {e}')
            return None

    async def is_paper_discovered(
        self, paper_id: str, source_id: str | None = None, user_id: str | None = None
    ) -> bool:
        """
        Check if a paper has been discovered.

        Args:
            paper_id: UUID of the paper
            source_id: Optional source UUID to check specific source

        Returns:
            bool: True if paper has been discovered
        """
        user_id = self._resolve_user_id(user_id, 'is_paper_discovered')
        cache_key = self._cache_key(
            'discovered', paper_id, source_id or 'any', user_id=user_id
        )
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            if source_id:
                query = """
                    SELECT EXISTS(
                        SELECT 1 FROM paper_discoveries
                        WHERE paper_id = $1 AND source_id = $2 {user_filter}
                    )
                """
                if user_id is not None:
                    result = await self.postgres.fetchval(
                        query.format(user_filter='AND user_id = $3'),
                        paper_id,
                        source_id,
                        user_id,
                    )
                else:
                    result = await self.postgres.fetchval(
                        query.format(user_filter=''),
                        paper_id,
                        source_id,
                    )
            else:
                query = """
                    SELECT EXISTS(
                        SELECT 1 FROM paper_discoveries
                        WHERE paper_id = $1 {user_filter}
                    )
                """
                if user_id is not None:
                    result = await self.postgres.fetchval(
                        query.format(user_filter='AND user_id = $2'),
                        paper_id,
                        user_id,
                    )
                else:
                    result = await self.postgres.fetchval(
                        query.format(user_filter=''), paper_id
                    )

            discovered = bool(result)
            self._set_in_cache(cache_key, discovered)
            return discovered

        except Exception as e:
            logger.error(f'Failed to check if paper is discovered: {e}')
            return False

    async def get_discoveries_for_paper(
        self, paper_id: str, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get all discovery records for a paper.

        Args:
            paper_id: UUID of the paper

        Returns:
            List[Dict[str, Any]]: List of discovery records
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_discoveries_for_paper')
            query = """
                SELECT pd.*, ds.source_name, ds.source_type
                FROM paper_discoveries pd
                JOIN discovery_sources ds ON pd.source_id = ds.id
                WHERE pd.paper_id = $1
                {user_filter}
                ORDER BY pd.discovered_at DESC
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND pd.user_id = $2 AND ds.user_id = $2'),
                    paper_id,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''), paper_id
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get discoveries for paper {paper_id}: {e}')
            return []

    async def get_discoveries_for_source(
        self,
        source_id: str,
        limit: int = 100,
        offset: int = 0,
        since: datetime | None = None,
        user_id: str | None = None,
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get papers discovered by a specific source.

        Args:
            source_id: UUID of the discovery source
            limit: Maximum number of results
            offset: Number of records to skip
            since: Only return discoveries after this time

        Returns:
            List[Dict[str, Any]]: List of discovery records with paper info
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_discoveries_for_source')
            if since:
                query = """
                    SELECT pd.*, p.title, p.doi, p.arxiv_id
                    FROM paper_discoveries pd
                    JOIN papers p ON pd.paper_id = p.id
                    WHERE pd.source_id = $1 AND pd.discovered_at >= $2
                    {user_filter}
                    ORDER BY pd.discovered_at DESC
                    LIMIT $3 OFFSET $4
                """
                if user_id is not None:
                    results = await self.postgres.fetch(
                        query.format(
                            user_filter='AND pd.user_id = $5 AND p.user_id = $5'
                        ),
                        source_id,
                        since,
                        limit,
                        offset,
                        user_id,
                    )
                else:
                    results = await self.postgres.fetch(
                        query.format(user_filter=''), source_id, since, limit, offset
                    )
            else:
                query = """
                    SELECT pd.*, p.title, p.doi, p.arxiv_id
                    FROM paper_discoveries pd
                    JOIN papers p ON pd.paper_id = p.id
                    WHERE pd.source_id = $1
                    {user_filter}
                    ORDER BY pd.discovered_at DESC
                    LIMIT $2 OFFSET $3
                """
                if user_id is not None:
                    results = await self.postgres.fetch(
                        query.format(
                            user_filter='AND pd.user_id = $4 AND p.user_id = $4'
                        ),
                        source_id,
                        limit,
                        offset,
                        user_id,
                    )
                else:
                    results = await self.postgres.fetch(
                        query.format(user_filter=''), source_id, limit, offset
                    )

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get discoveries for source {source_id}: {e}')
            return []

    async def get_recent_discoveries(
        self, hours: int = 24, limit: int = 100, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get recent paper discoveries across all sources.

        Args:
            hours: Number of hours to look back
            limit: Maximum number of results

        Returns:
            List[Dict[str, Any]]: List of recent discoveries with paper and source info
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_recent_discoveries')
            since = datetime.now() - timedelta(hours=hours)
            query = """
                SELECT pd.*, p.title, p.doi, p.arxiv_id,
                       ds.source_name, ds.source_type
                FROM paper_discoveries pd
                JOIN papers p ON pd.paper_id = p.id
                JOIN discovery_sources ds ON pd.source_id = ds.id
                WHERE pd.discovered_at >= $1
                {user_filter}
                ORDER BY pd.discovered_at DESC
                LIMIT $2
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(
                        user_filter='AND pd.user_id = $3 AND p.user_id = $3 AND ds.user_id = $3'
                    ),
                    since,
                    limit,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''), since, limit
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get recent discoveries: {e}')
            return []

    async def count_discoveries_by_source(
        self,
        source_id: str,
        since: datetime | None = None,
        user_id: str | None = None,
    ) -> int:
        """
        Count discoveries for a specific source.

        Args:
            source_id: UUID of the discovery source
            since: Only count discoveries after this time

        Returns:
            int: Number of discoveries
        """
        try:
            user_id = self._resolve_user_id(user_id, 'count_discoveries_by_source')
            if since:
                query = """
                    SELECT COUNT(*) FROM paper_discoveries
                    WHERE source_id = $1 AND discovered_at >= $2
                    {user_filter}
                """
                if user_id is not None:
                    return (
                        await self.postgres.fetchval(
                            query.format(user_filter='AND user_id = $3'),
                            source_id,
                            since,
                            user_id,
                        )
                        or 0
                    )
                return (
                    await self.postgres.fetchval(
                        query.format(user_filter=''), source_id, since
                    )
                    or 0
                )
            else:
                query = """
                    SELECT COUNT(*) FROM paper_discoveries
                    WHERE source_id = $1
                    {user_filter}
                """
                if user_id is not None:
                    return (
                        await self.postgres.fetchval(
                            query.format(user_filter='AND user_id = $2'),
                            source_id,
                            user_id,
                        )
                        or 0
                    )
                return (
                    await self.postgres.fetchval(
                        query.format(user_filter=''), source_id
                    )
                    or 0
                )

        except Exception as e:
            logger.error(f'Failed to count discoveries for source {source_id}: {e}')
            return 0

    async def get_discovery_statistics(
        self, days: int = 30, user_id: str | None = None
    ) -> Dict[str, Any]:  # noqa: UP006
        """
        Get discovery statistics for the last N days.

        Args:
            days: Number of days to analyze

        Returns:
            Dict[str, Any]: Statistics including totals and breakdowns by source
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_discovery_statistics')
            since = datetime.now() - timedelta(days=days)
            query = """
                SELECT
                    COUNT(*) as total_discoveries,
                    COUNT(DISTINCT paper_id) as unique_papers,
                    COUNT(DISTINCT source_id) as active_sources,
                    jsonb_object_agg(
                        ds.source_name,
                        COUNT(pd.id)
                    ) as by_source
                FROM paper_discoveries pd
                JOIN discovery_sources ds ON pd.source_id = ds.id
                WHERE pd.discovered_at >= $1
                {user_filter}
                GROUP BY ds.source_name
            """
            if user_id is not None:
                result = await self.postgres.fetchrow(
                    query.format(user_filter='AND pd.user_id = $2 AND ds.user_id = $2'),
                    since,
                    user_id,
                )
            else:
                result = await self.postgres.fetchrow(
                    query.format(user_filter=''), since
                )

            if result:
                stats = dict(result)
                stats['days'] = days
                stats['since'] = since.isoformat()
                return stats

            return {
                'total_discoveries': 0,
                'unique_papers': 0,
                'active_sources': 0,
                'by_source': {},
                'days': days,
                'since': since.isoformat(),
            }

        except Exception as e:
            logger.error(f'Failed to get discovery statistics: {e}')
            return {}

    async def find_duplicate_discoveries(
        self, paper_id: str, user_id: str | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Find all sources that discovered the same paper.

        Args:
            paper_id: UUID of the paper

        Returns:
            List[Dict[str, Any]]: List of sources that found this paper
        """
        try:
            user_id = self._resolve_user_id(user_id, 'find_duplicate_discoveries')
            query = """
                SELECT pd.*, ds.source_name, ds.source_type
                FROM paper_discoveries pd
                JOIN discovery_sources ds ON pd.source_id = ds.id
                WHERE pd.paper_id = $1
                {user_filter}
                ORDER BY pd.discovered_at
            """
            if user_id is not None:
                results = await self.postgres.fetch(
                    query.format(user_filter='AND pd.user_id = $2 AND ds.user_id = $2'),
                    paper_id,
                    user_id,
                )
            else:
                results = await self.postgres.fetch(
                    query.format(user_filter=''), paper_id
                )
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(
                f'Failed to find duplicate discoveries for paper {paper_id}: {e}'
            )
            return []

    async def get_papers_not_in_vault(
        self,
        source_id: str | None = None,
        limit: int = 100,
        user_id: str | None = None,
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get discovered papers that haven't been added to the vault yet.

        Args:
            source_id: Optional source UUID to filter by
            limit: Maximum number of results

        Returns:
            List[Dict[str, Any]]: List of papers pending vault addition
        """
        try:
            user_id = self._resolve_user_id(user_id, 'get_papers_not_in_vault')
            if source_id:
                query = """
                    SELECT DISTINCT p.*
                    FROM paper_discoveries pd
                    JOIN papers p ON pd.paper_id = p.id
                    WHERE pd.source_id = $1
                    AND p.file_path IS NULL
                    {user_filter}
                    ORDER BY pd.discovered_at DESC
                    LIMIT $2
                """
                if user_id is not None:
                    results = await self.postgres.fetch(
                        query.format(
                            user_filter='AND pd.user_id = $3 AND p.user_id = $3'
                        ),
                        source_id,
                        limit,
                        user_id,
                    )
                else:
                    results = await self.postgres.fetch(
                        query.format(user_filter=''),
                        source_id,
                        limit,
                    )
            else:
                query = """
                    SELECT DISTINCT p.*
                    FROM paper_discoveries pd
                    JOIN papers p ON pd.paper_id = p.id
                    WHERE p.file_path IS NULL
                    {user_filter}
                    ORDER BY pd.discovered_at DESC
                    LIMIT $1
                """
                if user_id is not None:
                    results = await self.postgres.fetch(
                        query.format(
                            user_filter='AND pd.user_id = $2 AND p.user_id = $2'
                        ),
                        limit,
                        user_id,
                    )
                else:
                    results = await self.postgres.fetch(
                        query.format(user_filter=''), limit
                    )

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get papers not in vault: {e}')
            return []
