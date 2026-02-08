"""
Cache repository for managing API response caching in PostgreSQL.

This module handles caching of external API responses to reduce
redundant API calls and improve performance.
"""

from datetime import datetime, timedelta  # noqa: I001
from typing import Any, Dict  # noqa: UP035
from loguru import logger
import json

from thoth.repositories.base import BaseRepository


class CacheRepository(BaseRepository[Dict[str, Any]]):  # noqa: UP006
    """Repository for managing API cache records."""

    def __init__(self, postgres_service, **kwargs):
        """Initialize cache repository."""
        super().__init__(postgres_service, table_name='api_cache', **kwargs)

    async def get_cached_response(self, cache_key: str) -> Dict[str, Any] | None:  # noqa: UP006
        """
        Get a cached API response if not expired.

        Args:
            cache_key: Unique cache identifier

        Returns:
            Optional[Dict[str, Any]]: Cached response data or None
        """
        try:
            query = """
                SELECT response_data, expires_at
                FROM api_cache
                WHERE cache_key = $1
                  AND (expires_at IS NULL OR expires_at > NOW())
            """
            result = await self.postgres.fetchrow(query, cache_key)

            if result:
                # Parse JSON response
                response_data = result['response_data']
                if isinstance(response_data, str):
                    response_data = json.loads(response_data)

                logger.debug(f'Cache hit for key: {cache_key}')
                return response_data

            logger.debug(f'Cache miss for key: {cache_key}')
            return None

        except Exception as e:
            logger.error(f"Failed to get cached response for key '{cache_key}': {e}")
            return None

    async def set_cached_response(
        self,
        cache_key: str,
        response_data: Dict[str, Any],  # noqa: UP006
        ttl_seconds: int | None = 3600,
    ) -> bool:
        """
        Store an API response in the cache.

        Args:
            cache_key: Unique cache identifier
            response_data: Response data to cache
            ttl_seconds: Time-to-live in seconds (None = no expiration)

        Returns:
            bool: True if successful
        """
        try:
            expires_at = None
            if ttl_seconds is not None:
                expires_at = datetime.now() + timedelta(seconds=ttl_seconds)

            # Convert dict to JSON string
            response_json = json.dumps(response_data)

            query = """
                INSERT INTO api_cache (cache_key, response_data, expires_at)
                VALUES ($1, $2, $3)
                ON CONFLICT (cache_key)
                DO UPDATE SET
                    response_data = EXCLUDED.response_data,
                    expires_at = EXCLUDED.expires_at,
                    created_at = NOW()
            """
            await self.postgres.execute(query, cache_key, response_json, expires_at)

            # Invalidate cache
            self._invalidate_cache(cache_key)

            logger.debug(f'Cached response for key: {cache_key}')
            return True

        except Exception as e:
            logger.error(f"Failed to cache response for key '{cache_key}': {e}")
            return False

    async def invalidate_cache_key(self, cache_key: str) -> bool:
        """
        Invalidate a specific cache entry.

        Args:
            cache_key: Cache key to invalidate

        Returns:
            bool: True if successful
        """
        try:
            query = 'DELETE FROM api_cache WHERE cache_key = $1'
            await self.postgres.execute(query, cache_key)

            # Invalidate memory cache
            self._invalidate_cache(cache_key)

            logger.debug(f'Invalidated cache key: {cache_key}')
            return True

        except Exception as e:
            logger.error(f"Failed to invalidate cache key '{cache_key}': {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all cache entries matching a pattern.

        Args:
            pattern: SQL LIKE pattern (e.g., 'semantic_scholar%')

        Returns:
            int: Number of entries invalidated
        """
        try:
            query = 'DELETE FROM api_cache WHERE cache_key LIKE $1'
            result = await self.postgres.execute(query, pattern)

            # Extract count from result
            count = int(result.split()[-1]) if result else 0

            # Invalidate memory cache
            self._invalidate_cache(pattern)

            logger.info(
                f'Invalidated {count} cache entries matching pattern: {pattern}'
            )
            return count

        except Exception as e:
            logger.error(f"Failed to invalidate cache pattern '{pattern}': {e}")
            return 0

    async def cleanup_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            int: Number of entries removed
        """
        try:
            query = """
                DELETE FROM api_cache
                WHERE expires_at IS NOT NULL
                  AND expires_at < NOW()
            """
            result = await self.postgres.execute(query)

            # Extract count
            count = int(result.split()[-1]) if result else 0

            logger.info(f'Cleaned up {count} expired cache entries')
            return count

        except Exception as e:
            logger.error(f'Failed to cleanup expired cache entries: {e}')
            return 0

    async def get_cache_statistics(self) -> Dict[str, Any]:  # noqa: UP006
        """
        Get cache usage statistics.

        Returns:
            Dict[str, Any]: Cache statistics
        """
        try:
            query = """
                SELECT
                    COUNT(*) as total_entries,
                    COUNT(*) FILTER (WHERE expires_at IS NULL OR expires_at > NOW()) as active_entries,
                    COUNT(*) FILTER (WHERE expires_at < NOW()) as expired_entries,
                    pg_size_pretty(pg_total_relation_size('api_cache')) as table_size
                FROM api_cache
            """
            result = await self.postgres.fetchrow(query)

            return dict(result) if result else {}

        except Exception as e:
            logger.error(f'Failed to get cache statistics: {e}')
            return {}
