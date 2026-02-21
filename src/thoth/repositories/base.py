"""
Base repository with common CRUD operations.

This module provides the foundation for all repository classes with
generic CRUD methods, caching support, and error handling.
"""

import json  # noqa: I001
from datetime import datetime, date  # noqa: F401
from typing import Any, Dict, List, TypeVar, Generic  # noqa: UP035
from uuid import UUID
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
    - Multi-tenant user_id filtering with enforcement
    """

    # Set TENANT_SCOPED = False in subclasses for global tables (e.g. available_sources)
    TENANT_SCOPED: bool = True

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
        self._cache: TTLCache | None = None

        if use_cache:
            self._cache = TTLCache(maxsize=cache_size, ttl=cache_ttl)

    def _enforce_tenant_scoping(
        self, user_id: str | None, operation: str
    ) -> str | None:
        """
        Enforce tenant scoping in multi-user mode.

        In multi-user mode with TENANT_SCOPED=True, warns if user_id is missing
        and returns 'default_user' as a fallback (which will return empty results
        for properly scoped data).

        Args:
            user_id: User ID or None
            operation: Operation name for logging

        Returns:
            User ID (original or fallback 'default_user' in multi-user mode)
        """
        import os

        if not self.TENANT_SCOPED:
            # Global table, no enforcement
            return user_id

        multi_user = os.getenv('THOTH_MULTI_USER', 'false').lower() == 'true'

        if multi_user and user_id is None:
            from thoth.mcp.auth import get_mcp_user_id

            resolved_user_id = get_mcp_user_id()
            logger.warning(
                f'{operation} on {self.table_name} called without user_id in multi-user mode. '
                f'Using resolved fallback user_id={resolved_user_id}.'
            )
            return resolved_user_id

        return user_id

    def _resolve_user_id(
        self, user_id: str | None = None, operation: str = 'query'
    ) -> str | None:
        """
        Resolve and enforce user scoping for repository operations.

        Args:
            user_id: Optional user ID supplied by caller.
            operation: Operation label for enforcement logging.

        Returns:
            The resolved user ID, or None when scoping is not required.
        """
        return self._enforce_tenant_scoping(user_id, operation)

    def _cache_key(self, *args, **kwargs) -> str:
        """Generate cache key from arguments."""
        parts = [str(arg) for arg in args]
        parts.extend(f'{k}={v}' for k, v in sorted(kwargs.items()))
        return ':'.join([self.table_name] + parts)  # noqa: RUF005

    def _get_from_cache(self, key: str) -> T | None:
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

    def _invalidate_cache(self, pattern: str | None = None) -> None:
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

    async def create(
        self, data: dict[str, Any], user_id: str | None = None
    ) -> int | None:
        """
        Create a new record.

        Args:
            data: Dictionary of column values
            user_id: Optional user ID for multi-tenant filtering (auto-injected)

        Returns:
            Optional[int]: ID of created record or None
        """
        try:
            user_id = self._resolve_user_id(user_id, 'create')
            if user_id is not None:
                data = {**data, 'user_id': user_id}

            columns = list(data.keys())
            placeholders = [f'${i + 1}' for i in range(len(columns))]

            # Handle data types appropriately:
            # - Lists: pass directly for PostgreSQL array columns (text[], integer[])
            # - Dicts: serialize to JSON for JSONB columns
            # - Date strings: parse to date objects for DATE columns
            values = []
            for col in columns:
                val = data[col]
                if isinstance(val, dict):
                    # Only dicts get JSON serialized (for JSONB columns)
                    values.append(json.dumps(val))
                elif isinstance(val, list):
                    # Lists pass through directly for PostgreSQL array columns
                    values.append(val)
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

    async def get_by_id(
        self, record_id: int | UUID, user_id: str | None = None
    ) -> Dict[str, Any] | None:  # noqa: UP006
        """
        Get a record by ID.

        Args:
            record_id: Record ID (int or UUID)
            user_id: Optional user ID for multi-tenant filtering

        Returns:
            Optional[Dict[str, Any]]: Record data or None
        """
        # Enforce tenant scoping
        user_id = self._enforce_tenant_scoping(user_id, 'get_by_id')

        cache_key = self._cache_key('id', record_id, user_id=user_id)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        try:
            if user_id is not None:
                query = (
                    f'SELECT * FROM {self.table_name} WHERE id = $1 AND user_id = $2'
                )
                result = await self.postgres.fetchrow(query, record_id, user_id)
            else:
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

    async def update(
        self, record_id: int | UUID, data: dict[str, Any], user_id: str | None = None
    ) -> bool:
        """
        Update a record.

        Args:
            record_id: Record ID
            data: Dictionary of column values to update
            user_id: Optional user ID for multi-tenant filtering

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            user_id = self._resolve_user_id(user_id, 'update')
            if not data:
                return True

            # Build SET clause
            set_clauses = [f'{col} = ${i + 2}' for i, col in enumerate(data.keys())]

            # Handle data types appropriately:
            # - Dicts: serialize to JSON for JSONB columns
            # - Lists: pass directly for PostgreSQL array columns
            serialized_values = []
            for val in data.values():
                if isinstance(val, dict):
                    serialized_values.append(json.dumps(val))
                else:
                    # Lists and other types pass through directly
                    serialized_values.append(val)

            values = [record_id] + serialized_values  # noqa: RUF005

            if user_id is not None:
                query = f"""
                    UPDATE {self.table_name}
                    SET {', '.join(set_clauses)}
                    WHERE id = $1 AND user_id = ${len(values) + 1}
                """
                values.append(user_id)
            else:
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

    async def delete(self, record_id: int | UUID, user_id: str | None = None) -> bool:
        """
        Delete a record.

        Args:
            record_id: Record ID (int or UUID)
            user_id: Optional user ID for multi-tenant filtering

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            user_id = self._resolve_user_id(user_id, 'delete')
            if user_id is not None:
                query = f'DELETE FROM {self.table_name} WHERE id = $1 AND user_id = $2'
                await self.postgres.execute(query, record_id, user_id)
            else:
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
        limit: int | None = None,
        offset: int | None = None,
        user_id: str | None = None,
    ) -> List[Dict[str, Any]]:  # noqa: UP006
        """
        List all records with pagination.

        Args:
            limit: Maximum number of records
            offset: Number of records to skip
            user_id: Optional user ID for multi-tenant filtering

        Returns:
            List[Dict[str, Any]]: List of records
        """
        # Enforce tenant scoping
        user_id = self._enforce_tenant_scoping(user_id, 'list_all')

        try:
            query = f'SELECT * FROM {self.table_name}'
            params = []

            if user_id is not None:
                params.append(user_id)
                query += f' WHERE user_id = ${len(params)}'

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

    async def count(self, user_id: str | None = None) -> int:
        """
        Count total records.

        Args:
            user_id: Optional user ID for multi-tenant filtering

        Returns:
            int: Total number of records
        """
        # Enforce tenant scoping
        user_id = self._enforce_tenant_scoping(user_id, 'count')

        try:
            if user_id is not None:
                query = f'SELECT COUNT(*) FROM {self.table_name} WHERE user_id = $1'
                return await self.postgres.fetchval(query, user_id) or 0
            else:
                query = f'SELECT COUNT(*) FROM {self.table_name}'
                return await self.postgres.fetchval(query) or 0

        except Exception as e:
            logger.error(f'Failed to count {self.table_name} records: {e}')
            return 0

    async def exists(self, record_id: int | UUID, user_id: str | None = None) -> bool:
        """
        Check if a record exists.

        Args:
            record_id: Record ID (int or UUID)
            user_id: Optional user ID for multi-tenant filtering

        Returns:
            bool: True if exists, False otherwise
        """
        try:
            if user_id is not None:
                query = f'SELECT EXISTS(SELECT 1 FROM {self.table_name} WHERE id = $1 AND user_id = $2)'
                return await self.postgres.fetchval(query, record_id, user_id) or False
            else:
                query = f'SELECT EXISTS(SELECT 1 FROM {self.table_name} WHERE id = $1)'
                return await self.postgres.fetchval(query, record_id) or False

        except Exception as e:
            logger.error(f'Failed to check {self.table_name} existence: {e}')
            return False

    def transaction(self):
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
        """
        return self.postgres.transaction()
