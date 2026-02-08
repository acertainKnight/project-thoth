"""
Discovery source repository for managing discovery sources in PostgreSQL.

This module provides specialized methods for discovery source data access,
including scheduling, statistics, and active source queries.
"""

from typing import Any, Dict, List  # noqa: I001, UP035
from datetime import datetime
from loguru import logger

from thoth.repositories.base import BaseRepository


class DiscoverySourceRepository(BaseRepository[Dict[str, Any]]):  # noqa: UP006
    """Repository for managing discovery source records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize discovery source repository."""
        super().__init__(postgres_service, table_name='discovery_sources', **kwargs)

    async def get_by_name(self, source_name: str) -> Dict[str, Any] | None:  # noqa: UP006
        """
        Get a discovery source by name.

        Args:
            source_name: Name of the discovery source

        Returns:
            Optional[Dict[str, Any]]: Source data or None
        """
        cache_key = self._cache_key('name', source_name)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = 'SELECT * FROM discovery_sources WHERE source_name = $1'
            result = await self.postgres.fetchrow(query, source_name)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get discovery source by name {source_name}: {e}')
            return None

    async def get_active_sources(self) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get all active discovery sources.

        Returns:
            List[Dict[str, Any]]: List of active sources
        """
        cache_key = self._cache_key('active')
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = """
                SELECT * FROM discovery_sources
                WHERE enabled = TRUE
                ORDER BY source_name
            """
            results = await self.postgres.fetch(query)
            data = [dict(row) for row in results]
            self._set_in_cache(cache_key, data)
            return data

        except Exception as e:
            logger.error(f'Failed to get active discovery sources: {e}')
            return []

    async def get_sources_by_type(self, source_type: str) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get discovery sources by type.

        Args:
            source_type: Type of discovery source (arxiv, pubmed, etc.)

        Returns:
            List[Dict[str, Any]]: List of sources of the specified type
        """
        try:
            query = """
                SELECT * FROM discovery_sources
                WHERE source_type = $1
                ORDER BY source_name
            """
            results = await self.postgres.fetch(query, source_type)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get discovery sources by type {source_type}: {e}')
            return []

    async def get_sources_due_for_run(
        self, current_time: datetime | None = None
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        Get sources that are due for their scheduled run.

        Args:
            current_time: Time to check against (defaults to now)

        Returns:
            List[Dict[str, Any]]: List of sources ready to run
        """
        if current_time is None:
            current_time = datetime.now()

        try:
            query = """
                SELECT * FROM discovery_sources
                WHERE enabled = TRUE
                AND next_run_at IS NOT NULL
                AND next_run_at <= $1
                ORDER BY next_run_at
            """
            results = await self.postgres.fetch(query, current_time)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to get sources due for run: {e}')
            return []

    async def update_run_statistics(
        self,
        source_id: str,
        papers_discovered: int,
        last_run_at: datetime | None = None,
        next_run_at: datetime | None = None,
    ) -> bool:
        """
        Update run statistics for a source.

        Args:
            source_id: Source UUID
            papers_discovered: Number of papers discovered in this run
            last_run_at: Time of last run (defaults to now)
            next_run_at: Time for next scheduled run

        Returns:
            bool: True if successful
        """
        if last_run_at is None:
            last_run_at = datetime.now()

        try:
            query = """
                UPDATE discovery_sources
                SET total_papers_discovered = total_papers_discovered + $1,
                    total_runs = total_runs + 1,
                    last_run_at = $2,
                    next_run_at = $3,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $4
            """
            await self.postgres.execute(
                query, papers_discovered, last_run_at, next_run_at, source_id
            )

            # Invalidate cache
            self._invalidate_cache()

            logger.debug(f'Updated run statistics for source {source_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to update run statistics for source {source_id}: {e}')
            return False

    async def update_schedule(
        self,
        source_id: str,
        schedule_interval_minutes: int | None = None,
        next_run_at: datetime | None = None,
        enabled: bool | None = None,
    ) -> bool:
        """
        Update scheduling configuration for a source.

        Args:
            source_id: Source UUID
            schedule_interval_minutes: New interval in minutes
            next_run_at: New next run time
            enabled: Enable/disable the source

        Returns:
            bool: True if successful
        """
        try:
            updates = {}
            if schedule_interval_minutes is not None:
                updates['schedule_interval_minutes'] = schedule_interval_minutes
            if next_run_at is not None:
                updates['next_run_at'] = next_run_at
            if enabled is not None:
                updates['enabled'] = enabled

            if not updates:
                return True

            return await self.update(source_id, updates)

        except Exception as e:
            logger.error(f'Failed to update schedule for source {source_id}: {e}')
            return False

    async def get_statistics(self) -> Dict[str, Any]:  # noqa: UP006
        """
        Get overall discovery source statistics.

        Returns:
            Dict[str, Any]: Statistics including totals by type and status
        """
        try:
            query = """
                SELECT
                    COUNT(*) as total_sources,
                    COUNT(*) FILTER (WHERE enabled = TRUE) as active_sources,
                    SUM(total_papers_discovered) as total_papers,
                    SUM(total_runs) as total_runs,
                    jsonb_object_agg(
                        source_type,
                        jsonb_build_object(
                            'count', COUNT(*),
                            'papers', COALESCE(SUM(total_papers_discovered), 0)
                        )
                    ) as by_type
                FROM discovery_sources
            """
            result = await self.postgres.fetchrow(query)

            if result:
                return dict(result)

            return {
                'total_sources': 0,
                'active_sources': 0,
                'total_papers': 0,
                'total_runs': 0,
                'by_type': {},
            }

        except Exception as e:
            logger.error(f'Failed to get discovery source statistics: {e}')
            return {}

    async def disable_source(self, source_id: str) -> bool:
        """
        Disable a discovery source.

        Args:
            source_id: Source UUID

        Returns:
            bool: True if successful
        """
        return await self.update(source_id, {'enabled': False})

    async def enable_source(self, source_id: str) -> bool:
        """
        Enable a discovery source.

        Args:
            source_id: Source UUID

        Returns:
            bool: True if successful
        """
        return await self.update(source_id, {'enabled': True})
