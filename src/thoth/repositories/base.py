"""
Base repository with common CRUD operations.

This module provides the foundation for all repository classes with
generic CRUD methods, caching support, and error handling.
"""

import json  # noqa: I001
from datetime import datetime, date  # noqa: F401
from typing import Any, Dict, List, Optional, TypeVar, Generic  # noqa: UP035
from loguru import logger
from cachetools import TTLCache
from dateutil import parser as dateparser

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    Base repository class with common CRUD operations.

    Provides:
    - Generic CRUD methods
    - In-memory LRU cache with TTL
    - Error handling and logging
    - Feature flag support for A/B testing
    """

    def __init__(
        self,
        postgres_service,
        table_name: str,
        cache_ttl: int = 300,  # 5 minutes default
        cache_size: int = 1000,
        use_cache: bool = True,
    ):
        """
        Initialize the base repository.

        Args:
            postgres_service: PostgreSQL service instance
            table_name: Name of the database table
            cache_ttl: Cache time-to-live in seconds
            cache_size: Maximum cache size
            use_cache: Whether to enable caching
        """
        self.postgres = postgres_service
        self.table_name = table_name
        self.use_cache = use_cache
        self._cache: Optional[TTLCache] = None  # noqa: UP007

        if use_cache:
            self._cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)

    def _cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        parts = [str(arg) for arg in args]
        parts.extend(f'{k}={v}' for k, v in sorted(kwargs.items()))
        return ':'.join([self.table_name] + parts)  # noqa: RUF005

    def _get_from_cache(self, key: str) -> Optional[T]:  # noqa: UP007
        """Get value from cache if enabled."""
        if not self.use_cache or self._cache is None:
            return None

        try:
            return self._cache.get(key)
        except Exception as e:
            logger.warning(f'Cache get failed: {e}')
            return None

    def _set_in_cache(self, key: str, value: T) -> None:
        """Set value in cache if enabled."""
        if not self.use_cache or self._cache is None:
            return

        try:
            self._cache[key] = value
        except Exception as e:
            logger.warning(f'Cache set failed: {e}')

    def _invalidate_cache(self, pattern: Optional[str] = None) -> None:  # noqa: UP007
        """Invalidate cache entries matching pattern."""
        if not self.use_cache or self._cache is None:
            return

        try:
            if pattern is None:
                self._cache.clear()
            else:
                keys_to_delete = [k for k in self._cache.keys() if pattern in k]
                for key in keys_to_delete:
                    del self._cache[key]
        except Exception as e:
            logger.warning(f'Cache invalidation failed: {e}')

    async def create(self, data: Dict[str, Any]) -> Optional[int]:  # noqa: UP006, UP007
        """
        Create a new record.

        Args:
            data: Dictionary of column values

        Returns:
            Optional[int]: ID of created record or None
        """
        try:
            columns = list(data.keys())
            placeholders = [f'${i + 1}' for i in range(len(columns))]

            # Serialize lists and dicts to JSON for JSONB columns
            # Parse ISO datetime strings to date objects for DATE columns
            values = []
            for col in columns:
                val = data[col]
                if isinstance(val, (list, dict)):  # noqa: UP038
                    values.append(json.dumps(val))
                elif isinstance(val, str) and (
                    'publication_date' in col or 'date' in col.lower()
                ):
                    # Parse ISO format date strings to date objects
                    try:
                        parsed = dateparser.parse(val)
                        values.append(parsed.date() if parsed else val)
                    except Exception:
                        values.append(val)
                else:
                    values.append(val)

            query = f"""
                INSERT INTO {self.table_name} ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
                RETURNING id
            """

            result = await self.postgres.fetchval(query, *values)

            # Invalidate relevant cache entries
            self._invalidate_cache()

            logger.debug(f'Created {self.table_name} record: {result}')
            return result

        except Exception as e:
            logger.error(f'Failed to create {self.table_name} record: {e}')
            return None

    async def get_by_id(self, record_id: int) -> Optional[Dict[str, Any]]:  # noqa: UP006, UP007
        """
        Get a record by ID.

        Args:
            record_id: Record ID

        Returns:
            Optional[Dict[str, Any]]: Record data or None
        """
        cache_key = self._cache_key('id', record_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            query = f'SELECT * FROM {self.table_name} WHERE id = $1'
            result = await self.postgres.fetchrow(query, record_id)

            if result:
                data = dict(result)
                self._set_in_cache(cache_key, data)
                return data

            return None

        except Exception as e:
            logger.error(f'Failed to get {self.table_name} by ID {record_id}: {e}')
            return None

    async def update(self, record_id: int, data: Dict[str, Any]) -> bool:  # noqa: UP006
        """
        Update a record.

        Args:
            record_id: Record ID
            data: Dictionary of column values to update

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not data:
                return True

            # Build SET clause
            set_clauses = [f'{col} = ${i + 2}' for i, col in enumerate(data.keys())]

            # Serialize lists and dicts to JSON for JSONB columns
            serialized_values = []
            for val in data.values():
                if isinstance(val, (list, dict)):  # noqa: UP038
                    serialized_values.append(json.dumps(val))
                else:
                    serialized_values.append(val)

            values = [record_id] + serialized_values  # noqa: RUF005

            query = f"""
                UPDATE {self.table_name}
                SET {', '.join(set_clauses)}
                WHERE id = $1
            """

            await self.postgres.execute(query, *values)

            # Invalidate cache for this record
            self._invalidate_cache(str(record_id))

            logger.debug(f'Updated {self.table_name} record: {record_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to update {self.table_name} record {record_id}: {e}')
            return False

    async def delete(self, record_id: int) -> bool:
        """
        Delete a record.

        Args:
            record_id: Record ID

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            query = f'DELETE FROM {self.table_name} WHERE id = $1'
            await self.postgres.execute(query, record_id)

            # Invalidate cache
            self._invalidate_cache(str(record_id))

            logger.debug(f'Deleted {self.table_name} record: {record_id}')
            return True

        except Exception as e:
            logger.error(f'Failed to delete {self.table_name} record {record_id}: {e}')
            return False

    async def list_all(
        self,
        limit: Optional[int] = None,  # noqa: UP007
        offset: Optional[int] = None,  # noqa: UP007
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        List all records with pagination.

        Args:
            limit: Maximum number of records
            offset: Number of records to skip

        Returns:
            List[Dict[str, Any]]: List of records
        """
        try:
            query = f'SELECT * FROM {self.table_name}'
            params = []

            if limit is not None:
                params.append(limit)
                query += f' LIMIT ${len(params)}'

            if offset is not None:
                params.append(offset)
                query += f' OFFSET ${len(params)}'

            results = await self.postgres.fetch(query, *params)
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f'Failed to list {self.table_name} records: {e}')
            return []

    async def count(self) -> int:
        """
        Count total records.

        Returns:
            int: Total number of records
        """
        try:
            query = f'SELECT COUNT(*) FROM {self.table_name}'
            return await self.postgres.fetchval(query) or 0

        except Exception as e:
            logger.error(f'Failed to count {self.table_name} records: {e}')
            return 0

    async def exists(self, record_id: int) -> bool:
        """
        Check if a record exists.

        Args:
            record_id: Record ID

        Returns:
            bool: True if exists, False otherwise
        """
        try:
            query = f'SELECT EXISTS(SELECT 1 FROM {self.table_name} WHERE id = $1)'
            return await self.postgres.fetchval(query, record_id) or False

        except Exception as e:
            logger.error(f'Failed to check {self.table_name} existence: {e}')
            return False

    async def transaction(self):
        """
        Create a database transaction context for multi-step operations.

        This ensures ACID guarantees for operations that span multiple queries.
        All queries within the transaction will either all succeed or all fail.

        Usage:
            async with repository.transaction() as conn:
                # All queries in this block are atomic
                await conn.execute("INSERT INTO ...")
                await conn.execute("UPDATE ...")
                # If any query fails, all changes are rolled back

        Example:
            >>> async with paper_repo.transaction() as conn:
            ...     paper_id = await conn.fetchval(
            ...         'INSERT INTO papers (...) RETURNING id'
            ...     )
            ...     await conn.execute(
            ...         'INSERT INTO citations (paper_id, ...) VALUES ($1, ...)',
            ...         paper_id,
            ...     )
            ...     # Both operations succeed together or fail together

        Returns:
            AsyncContextManager yielding a database connection within a transaction
        """  # noqa: W505
        return self.postgres.transaction()
