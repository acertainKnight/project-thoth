"""
Available Source repository for managing discovery plugin registry.

This module provides methods for managing available discovery sources,
health monitoring, and usage statistics.
"""

from datetime import datetime
from typing import Any, List  # noqa: UP035

from loguru import logger

from thoth.repositories.base import BaseRepository


class AvailableSourceRepository(BaseRepository[dict[str, Any]]):
    """Repository for managing available discovery source plugins."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize available source repository."""
        super().__init__(postgres_service, table_name='available_sources', **kwargs)

    async def get_by_name(self, name: str) -> dict[str, Any] | None:
        """
        Get source by name.

        Args:
            name: Source name (e.g., 'arxiv', 'pubmed')

        Returns:
            Optional[dict[str, Any]]: Source data or None
        """
        cache_key = self._cache_key('name', name)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = 'SELECT * FROM available_sources WHERE name = $1'
            result = await self.postgres.fetchrow(query, name)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get source by name {name}: {e}')
            return None

    async def get_active_sources(self) -> List[dict[str, Any]]:  # noqa: UP006
        """
        Get all active sources.

        Returns:
            List[dict[str, Any]]: List of active sources
        """
        cache_key = self._cache_key('active')
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM available_sources
                WHERE is_active = true
                ORDER BY display_name ASC
            """

            results = await self.postgres.fetch(query)
            data = [dict(row) for row in results]

            self._set_in_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f'Failed to get active sources: {e}')
            return []

    async def list_all_source_names(self) -> List[str]:  # noqa: UP006
        """
        Get list of all active source names.

        Returns:
            List[str]: List of source names
        """
        cache_key = self._cache_key('names')
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT name FROM available_sources
                WHERE is_active = true
                ORDER BY name ASC
            """

            results = await self.postgres.fetch(query)
            names = [row['name'] for row in results]

            self._set_in_cache(cache_key, names)
            return names

        except Exception as e:
            logger.error(f'Failed to list source names: {e}')
            return []

    async def update_health_status(
        self,
        name: str,
        health_status: str,
        error_count: int | None = None,
    ) -> bool:
        """
        Update health status for a source.

        Args:
            name: Source name
            health_status: Health status ('active', 'degraded', 'down', 'unknown')
            error_count: Optional error count to set

        Returns:
            bool: True if successful
        """
        try:
            source = await self.get_by_name(name)
            if not source:
                logger.warning(f'Source {name} not found')
                return False

            data = {
                'health_status': health_status,
                'last_health_check': datetime.now(),
            }

            if error_count is not None:
                data['error_count'] = error_count

            query = """
                UPDATE available_sources
                SET health_status = $1,
                    last_health_check = $2,
                    error_count = COALESCE($3, error_count)
                WHERE name = $4
            """

            await self.postgres.execute(
                query,
                health_status,
                datetime.now(),
                error_count,
                name,
            )

            # Invalidate cache
            self._invalidate_cache(name)

            logger.debug(f'Updated health status for {name}: {health_status}')
            return True

        except Exception as e:
            logger.error(f'Failed to update health status for {name}: {e}')
            return False

    async def increment_query_count(
        self,
        name: str,
        articles_found: int = 0,
        response_time_ms: float | None = None,
    ) -> bool:
        """
        Increment query statistics for a source.

        Args:
            name: Source name
            articles_found: Number of articles found in this query
            response_time_ms: Query response time in milliseconds

        Returns:
            bool: True if successful
        """
        try:
            query = """
                UPDATE available_sources
                SET total_queries = total_queries + 1,
                    total_articles_found = total_articles_found + $1,
                    avg_response_time_ms = CASE
                        WHEN $2::DOUBLE PRECISION IS NOT NULL THEN
                            COALESCE(
                                (avg_response_time_ms * total_queries + $2::DOUBLE PRECISION) /
                                (total_queries + 1),
                                $2::DOUBLE PRECISION
                            )
                        ELSE avg_response_time_ms
                    END
                WHERE name = $3
            """

            await self.postgres.execute(query, articles_found, response_time_ms, name)

            # Invalidate cache
            self._invalidate_cache(name)

            return True

        except Exception as e:
            logger.error(f'Failed to increment query count for {name}: {e}')
            return False

    async def increment_error_count(self, name: str) -> bool:
        """
        Increment error count for a source.

        Args:
            name: Source name

        Returns:
            bool: True if successful
        """
        try:
            query = """
                UPDATE available_sources
                SET error_count = error_count + 1,
                    health_status = CASE
                        WHEN error_count + 1 >= 5 THEN 'down'
                        WHEN error_count + 1 >= 3 THEN 'degraded'
                        ELSE health_status
                    END
                WHERE name = $1
            """

            await self.postgres.execute(query, name)

            # Invalidate cache
            self._invalidate_cache(name)

            return True

        except Exception as e:
            logger.error(f'Failed to increment error count for {name}: {e}')
            return False

    async def reset_error_count(self, name: str) -> bool:
        """
        Reset error count for a source (after successful query).

        Args:
            name: Source name

        Returns:
            bool: True if successful
        """
        try:
            query = """
                UPDATE available_sources
                SET error_count = 0,
                    health_status = 'active'
                WHERE name = $1
            """

            await self.postgres.execute(query, name)

            # Invalidate cache
            self._invalidate_cache(name)

            return True

        except Exception as e:
            logger.error(f'Failed to reset error count for {name}: {e}')
            return False

    async def get_statistics(self) -> dict[str, Any]:
        """
        Get overall source statistics.

        Returns:
            dict[str, Any]: Aggregated statistics across all sources
        """
        try:
            query = """
                SELECT
                    COUNT(*) as total_sources,
                    COUNT(*) FILTER (WHERE is_active = true) as active_sources,
                    COUNT(*) FILTER (WHERE health_status = 'active') as healthy_sources,
                    COUNT(*) FILTER (WHERE health_status = 'degraded') as degraded_sources,
                    COUNT(*) FILTER (WHERE health_status = 'down') as down_sources,
                    SUM(total_queries) as total_queries,
                    SUM(total_articles_found) as total_articles_found,
                    AVG(avg_response_time_ms) as avg_response_time_ms
                FROM available_sources
            """

            result = await self.postgres.fetchrow(query)
            return dict(result) if result else {}

        except Exception as e:
            logger.error(f'Failed to get source statistics: {e}')
            return {}

    async def get_source_statistics(self, name: str) -> dict[str, Any]:
        """
        Get statistics for a specific source.

        Args:
            name: Source name

        Returns:
            dict[str, Any]: Source-specific statistics
        """
        try:
            source = await self.get_by_name(name)
            if not source:
                return {}

            # Add derived statistics
            stats = dict(source)
            if source['total_queries'] > 0:
                stats['avg_articles_per_query'] = (
                    source['total_articles_found'] / source['total_queries']
                )
            else:
                stats['avg_articles_per_query'] = 0

            return stats

        except Exception as e:
            logger.error(f'Failed to get statistics for {name}: {e}')
            return {}

    async def register_source(
        self,
        name: str,
        display_name: str,
        description: str,
        source_type: str,
        capabilities: dict[str, Any],
        rate_limit_per_minute: int = 60,
    ) -> bool:
        """
        Register a new discovery source.

        Args:
            name: Internal source name
            display_name: User-facing display name
            description: Source description
            source_type: Type ('api', 'web_scraper', etc.)
            capabilities: Source capabilities dict
            rate_limit_per_minute: Rate limit

        Returns:
            bool: True if successful
        """
        try:
            # Check if source already exists
            existing = await self.get_by_name(name)
            if existing:
                logger.warning(f'Source {name} already registered')
                return False

            query = """
                INSERT INTO available_sources (
                    name, display_name, description, source_type,
                    capabilities, rate_limit_per_minute,
                    is_active, health_status
                )
                VALUES ($1, $2, $3, $4, $5, $6, true, 'active')
            """

            await self.postgres.execute(
                query,
                name,
                display_name,
                description,
                source_type,
                capabilities,
                rate_limit_per_minute,
            )

            # Invalidate cache
            self._invalidate_cache()

            logger.info(f'Registered new source: {display_name} ({name})')
            return True

        except Exception as e:
            logger.error(f'Failed to register source {name}: {e}')
            return False

    async def deactivate(self, name: str) -> bool:
        """
        Deactivate a source.

        Args:
            name: Source name

        Returns:
            bool: True if successful
        """
        try:
            query = 'UPDATE available_sources SET is_active = false WHERE name = $1'
            await self.postgres.execute(query, name)

            # Invalidate cache
            self._invalidate_cache(name)

            logger.info(f'Deactivated source: {name}')
            return True

        except Exception as e:
            logger.error(f'Failed to deactivate source {name}: {e}')
            return False

    async def activate(self, name: str) -> bool:
        """
        Activate a source.

        Args:
            name: Source name

        Returns:
            bool: True if successful
        """
        try:
            query = 'UPDATE available_sources SET is_active = true WHERE name = $1'
            await self.postgres.execute(query, name)

            # Invalidate cache
            self._invalidate_cache(name)

            logger.info(f'Activated source: {name}')
            return True

        except Exception as e:
            logger.error(f'Failed to activate source {name}: {e}')
            return False
