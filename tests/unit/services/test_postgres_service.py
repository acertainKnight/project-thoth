"""
Unit tests for PostgresService.

Tests connection pool management, query execution, transaction handling,
retry logic, and the connection pool race condition fix.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch, MagicMock

import asyncpg

from thoth.services.postgres_service import PostgresService
from thoth.services.base import ServiceError


@pytest.mark.asyncio
class TestPostgresService:
    """Test suite for PostgresService."""

    async def test_initialization(self):
        """Test service initialization without auto-connect."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        service = PostgresService(config)

        assert service.database_url == 'postgresql://localhost/test'
        assert service._pool is None
        assert service._connection_lock is not None

    @patch('asyncpg.create_pool')
    async def test_initialize_pool(self, mock_create_pool):
        """Test connection pool initialization."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        # Mock pool and connection
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        assert service._pool is not None
        mock_create_pool.assert_called_once()

        # Verify pool configuration
        call_kwargs = mock_create_pool.call_args[1]
        assert call_kwargs['min_size'] == 5
        assert call_kwargs['max_size'] == 20
        assert call_kwargs['command_timeout'] == 60.0

    @patch('asyncpg.create_pool')
    async def test_initialize_pool_race_condition(self, mock_create_pool):
        """
        Test that connection pool race condition is prevented.

        This tests the fix for the bug where multiple threads could
        simultaneously create multiple connection pools.
        """
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        # Track number of pool creations
        creation_count = 0

        async def mock_create(*args, **kwargs):
            nonlocal creation_count
            creation_count += 1
            # Simulate delay that could cause race condition
            await asyncio.sleep(0.01)

            mock_pool = AsyncMock()
            mock_conn = AsyncMock()
            mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')

            async def mock_acquire():
                class MockAcquire:
                    async def __aenter__(self):
                        return mock_conn
                    async def __aexit__(self, *args):
                        pass
                return MockAcquire()

            mock_pool.acquire.return_value = mock_acquire()
            return mock_pool

        mock_create_pool.side_effect = mock_create

        service = PostgresService(config)

        # Simulate multiple concurrent initialization attempts
        await asyncio.gather(
            service.initialize(),
            service.initialize(),
            service.initialize()
        )

        # Only one pool should be created due to lock protection
        assert creation_count == 1
        assert service._pool is not None

    @patch('asyncpg.create_pool')
    async def test_initialize_pool_error(self, mock_create_pool):
        """Test error handling during pool initialization."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_create_pool.side_effect = Exception('Connection failed')

        service = PostgresService(config)

        with pytest.raises(ServiceError):
            await service.initialize()

        # Pool should remain None after error
        assert service._pool is None

    async def test_close_pool(self):
        """Test closing connection pool."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        service = PostgresService(config)
        service._pool = AsyncMock()
        service._pool.close = AsyncMock()

        await service.close()

        service._pool.close.assert_called_once()
        assert service._pool is None

    async def test_close_pool_none(self):
        """Test closing when pool is None."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        service = PostgresService(config)
        service._pool = None

        # Should not raise error
        await service.close()

    @patch('asyncpg.create_pool')
    async def test_acquire_connection(self, mock_create_pool):
        """Test acquiring connection from pool."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        async with service.acquire() as conn:
            assert conn is mock_conn

    @patch('asyncpg.create_pool')
    async def test_transaction_context(self, mock_create_pool):
        """Test transaction context manager."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')

        # Track transaction usage
        transaction_started = False

        async def mock_transaction():
            class MockTransaction:
                async def __aenter__(self):
                    nonlocal transaction_started
                    transaction_started = True
                    return None
                async def __aexit__(self, *args):
                    pass
            return MockTransaction()

        mock_conn.transaction = mock_transaction

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        async with service.transaction() as conn:
            assert conn is mock_conn
            assert transaction_started is True

    @patch('asyncpg.create_pool')
    async def test_execute_query(self, mock_create_pool):
        """Test executing a query."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')
        mock_conn.execute = AsyncMock(return_value='INSERT 0 1')

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        result = await service.execute('INSERT INTO papers VALUES ($1)', 'test')

        assert result == 'INSERT 0 1'
        mock_conn.execute.assert_called_once()

    @patch('asyncpg.create_pool')
    async def test_execute_with_retry(self, mock_create_pool):
        """Test query execution with retry logic."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')

        # Fail first two attempts, succeed on third
        attempt_count = 0
        async def mock_execute(*args, **kwargs):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 3:
                raise asyncpg.exceptions.PostgresError('Temporary error')
            return 'SUCCESS'

        mock_conn.execute = mock_execute

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        result = await service.execute('SELECT 1', retry_count=3)

        assert result == 'SUCCESS'
        assert attempt_count == 3

    @patch('asyncpg.create_pool')
    async def test_execute_retry_exhausted(self, mock_create_pool):
        """Test query execution when retries are exhausted."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')
        mock_conn.execute = AsyncMock(
            side_effect=asyncpg.exceptions.PostgresError('Permanent error')
        )

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        with pytest.raises(ServiceError):
            await service.execute('SELECT 1', retry_count=3)

    @patch('asyncpg.create_pool')
    async def test_fetch_rows(self, mock_create_pool):
        """Test fetching multiple rows."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')
        mock_conn.fetch = AsyncMock(return_value=[{'id': 1}, {'id': 2}])

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        results = await service.fetch('SELECT * FROM papers')

        assert len(results) == 2
        mock_conn.fetch.assert_called_once()

    @patch('asyncpg.create_pool')
    async def test_fetchrow(self, mock_create_pool):
        """Test fetching single row."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')
        mock_conn.fetchrow = AsyncMock(return_value={'id': 1, 'title': 'Test'})

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        row = await service.fetchrow('SELECT * FROM papers WHERE id = $1', 1)

        assert row is not None
        assert row['id'] == 1
        mock_conn.fetchrow.assert_called_once()

    @patch('asyncpg.create_pool')
    async def test_fetchval(self, mock_create_pool):
        """Test fetching single value."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(side_effect=[
            'PostgreSQL 15.0',  # For initialization
            42  # For actual query
        ])

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        value = await service.fetchval('SELECT COUNT(*) FROM papers')

        assert value == 42

    @patch('asyncpg.create_pool')
    async def test_executemany(self, mock_create_pool):
        """Test batch query execution."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')
        mock_conn.executemany = AsyncMock()

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        args = [(1, 'Paper 1'), (2, 'Paper 2'), (3, 'Paper 3')]
        await service.executemany(
            'INSERT INTO papers (id, title) VALUES ($1, $2)',
            args
        )

        mock_conn.executemany.assert_called_once()

    @patch('asyncpg.create_pool')
    async def test_health_check_healthy(self, mock_create_pool):
        """Test health check when service is healthy."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        mock_pool = AsyncMock()
        mock_pool.get_size = Mock(return_value=20)
        mock_pool.get_idle_size = Mock(return_value=15)

        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_pool.acquire.return_value = mock_acquire()
        mock_create_pool.return_value = mock_pool

        service = PostgresService(config)
        await service.initialize()

        health = await service.health_check()

        assert health['status'] == 'healthy'
        assert health['pool_size'] == 20
        assert health['pool_free'] == 15
        assert health['pool_used'] == 5
        assert 'latency_ms' in health

    async def test_health_check_no_pool(self):
        """Test health check when pool is not initialized."""
        config = Mock()
        config.secrets = Mock()
        config.secrets.database_url = 'postgresql://localhost/test'

        service = PostgresService(config)

        health = await service.health_check()

        assert health['status'] == 'error'
        assert 'not initialized' in health['message']
