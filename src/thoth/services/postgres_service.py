"""
PostgreSQL service for managing database connections and operations.

This module provides AsyncPG connection pool management, query builders,
transaction context managers, and retry logic for all database operations.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import asyncpg

from thoth.services.base import BaseService, ServiceError


class PostgresService(BaseService):
    """
    Service for managing PostgreSQL database operations.

    This service provides:
    - AsyncPG connection pool management
    - Query builders for common operations
    - Transaction context managers
    - Retry logic with exponential backoff
    - Health checks and monitoring
    """

    def __init__(self, config=None, database_url: str | None = None):
        """
        Initialize the PostgresService.

        Args:
            config: Optional configuration object
            database_url: PostgreSQL connection URL
        """
        super().__init__(config)
        self.database_url = database_url or config.secrets.database_url
        self._pool: asyncpg.Pool | None = None
        self._connection_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the PostgreSQL connection pool."""
        # Use lock to prevent race condition where multiple threads
        # could simultaneously create multiple connection pools
        async with self._connection_lock:
            # Double-check pattern: verify pool is still None after acquiring lock
            if self._pool is not None:
                return  # Another thread already initialized the pool

            try:
                self._pool = await asyncpg.create_pool(
                    self.database_url,
                    min_size=5,
                    max_size=20,
                    max_queries=50000,
                    max_inactive_connection_lifetime=300.0,
                    command_timeout=60.0,
                )
                self.logger.info(
                    f'PostgreSQL connection pool initialized: {self._pool}'
                )

                # Verify connection
                async with self._pool.acquire() as conn:
                    version = await conn.fetchval('SELECT version()')
                    self.logger.info(f'Connected to PostgreSQL: {version}')

            except Exception as e:
                # Clear pool on error to allow retry
                self._pool = None
                raise ServiceError(
                    self.handle_error(e, 'initializing PostgreSQL connection pool')
                ) from e

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self.logger.info('PostgreSQL connection pool closed')

    @asynccontextmanager
    async def acquire(self):
        """
        Acquire a connection from the pool.

        Usage:
            async with postgres.acquire() as conn:
                result = await conn.fetchrow('SELECT * FROM papers WHERE id = $1', paper_id)
        """  # noqa: W505
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as connection:
            yield connection

    @asynccontextmanager
    async def transaction(self):
        """
        Create a transaction context.

        Usage:
            async with postgres.transaction() as conn:
                await conn.execute('INSERT INTO papers (...) VALUES (...)')
                await conn.execute('INSERT INTO citations (...) VALUES (...)')
        """
        if not self._pool:
            await self.initialize()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def execute(
        self,
        query: str,
        *args,
        timeout: float | None = None,
        retry_count: int = 3,
    ) -> str:
        """
        Execute a query with retry logic.

        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Query timeout in seconds
            retry_count: Number of retries on failure

        Returns:
            str: Status message

        Raises:
            ServiceError: If query execution fails
        """
        for attempt in range(retry_count):
            try:
                async with self.acquire() as conn:
                    result = await conn.execute(query, *args, timeout=timeout)
                    self.log_operation('query_executed', rows_affected=result)
                    return result

            except asyncpg.exceptions.PostgresError as e:
                if attempt == retry_count - 1:
                    raise ServiceError(self.handle_error(e, 'executing query')) from e

                # Exponential backoff
                wait_time = 2**attempt
                self.logger.warning(
                    f'Query failed (attempt {attempt + 1}/{retry_count}), '
                    f'retrying in {wait_time}s: {e}'
                )
                await asyncio.sleep(wait_time)

    async def fetch(
        self,
        query: str,
        *args,
        timeout: float | None = None,
        retry_count: int = 3,
    ) -> list[asyncpg.Record]:
        """
        Fetch multiple rows with retry logic.

        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Query timeout in seconds
            retry_count: Number of retries on failure

        Returns:
            list[asyncpg.Record]: Query results

        Raises:
            ServiceError: If query execution fails
        """
        for attempt in range(retry_count):
            try:
                async with self.acquire() as conn:
                    results = await conn.fetch(query, *args, timeout=timeout)
                    self.log_operation('query_fetch', rows_returned=len(results))
                    return results

            except asyncpg.exceptions.PostgresError as e:
                if attempt == retry_count - 1:
                    raise ServiceError(
                        self.handle_error(e, 'fetching query results')
                    ) from e

                wait_time = 2**attempt
                self.logger.warning(
                    f'Fetch failed (attempt {attempt + 1}/{retry_count}), '
                    f'retrying in {wait_time}s: {e}'
                )
                await asyncio.sleep(wait_time)

    async def fetchrow(
        self,
        query: str,
        *args,
        timeout: float | None = None,
        retry_count: int = 3,
    ) -> asyncpg.Record | None:
        """
        Fetch a single row with retry logic.

        Args:
            query: SQL query to execute
            *args: Query parameters
            timeout: Query timeout in seconds
            retry_count: Number of retries on failure

        Returns:
            Optional[asyncpg.Record]: Query result or None

        Raises:
            ServiceError: If query execution fails
        """
        for attempt in range(retry_count):
            try:
                async with self.acquire() as conn:
                    result = await conn.fetchrow(query, *args, timeout=timeout)
                    self.log_operation('query_fetchrow', found=result is not None)
                    return result

            except asyncpg.exceptions.PostgresError as e:
                if attempt == retry_count - 1:
                    raise ServiceError(
                        self.handle_error(e, 'fetching query row')
                    ) from e

                wait_time = 2**attempt
                self.logger.warning(
                    f'Fetchrow failed (attempt {attempt + 1}/{retry_count}), '
                    f'retrying in {wait_time}s: {e}'
                )
                await asyncio.sleep(wait_time)

    async def fetchval(
        self,
        query: str,
        *args,
        column: int = 0,
        timeout: float | None = None,
        retry_count: int = 3,
    ) -> Any:
        """
        Fetch a single value with retry logic.

        Args:
            query: SQL query to execute
            *args: Query parameters
            column: Column index to return
            timeout: Query timeout in seconds
            retry_count: Number of retries on failure

        Returns:
            Any: Query result value

        Raises:
            ServiceError: If query execution fails
        """
        for attempt in range(retry_count):
            try:
                async with self.acquire() as conn:
                    result = await conn.fetchval(
                        query, *args, column=column, timeout=timeout
                    )
                    self.log_operation('query_fetchval', value=result)
                    return result

            except asyncpg.exceptions.PostgresError as e:
                if attempt == retry_count - 1:
                    raise ServiceError(
                        self.handle_error(e, 'fetching query value')
                    ) from e

                wait_time = 2**attempt
                self.logger.warning(
                    f'Fetchval failed (attempt {attempt + 1}/{retry_count}), '
                    f'retrying in {wait_time}s: {e}'
                )
                await asyncio.sleep(wait_time)

    async def executemany(
        self,
        query: str,
        args: list[tuple],
        timeout: float | None = None,
        retry_count: int = 3,
    ) -> None:
        """
        Execute a query with multiple parameter sets.

        Args:
            query: SQL query to execute
            args: List of parameter tuples
            timeout: Query timeout in seconds
            retry_count: Number of retries on failure

        Raises:
            ServiceError: If query execution fails
        """
        for attempt in range(retry_count):
            try:
                async with self.acquire() as conn:
                    await conn.executemany(query, args, timeout=timeout)
                    self.log_operation('query_executemany', batch_size=len(args))
                    return

            except asyncpg.exceptions.PostgresError as e:
                if attempt == retry_count - 1:
                    raise ServiceError(
                        self.handle_error(e, 'executing batch query')
                    ) from e

                wait_time = 2**attempt
                self.logger.warning(
                    f'Executemany failed (attempt {attempt + 1}/{retry_count}), '
                    f'retrying in {wait_time}s: {e}'
                )
                await asyncio.sleep(wait_time)

    async def health_check(self) -> dict[str, Any]:
        """
        Check PostgreSQL connection health.

        Returns:
            dict[str, Any]: Health check results
        """
        try:
            if not self._pool:
                return {
                    'status': 'error',
                    'message': 'Connection pool not initialized',
                }

            # Check pool stats
            pool_size = self._pool.get_size()
            pool_free = self._pool.get_idle_size()

            # Test query
            start = datetime.now()
            async with self.acquire() as conn:
                await conn.fetchval('SELECT 1')
            latency = (datetime.now() - start).total_seconds() * 1000

            return {
                'status': 'healthy',
                'pool_size': pool_size,
                'pool_free': pool_free,
                'pool_used': pool_size - pool_free,
                'latency_ms': round(latency, 2),
            }

        except Exception as e:
            return {
                'status': 'error',
                'message': str(e),
            }
