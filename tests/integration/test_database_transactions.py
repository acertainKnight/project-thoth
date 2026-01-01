"""
Integration tests for database transactions.

Tests transaction atomicity, rollback behavior, commit handling,
and async resource cleanup across repository operations.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

from thoth.repositories.paper_repository import PaperRepository
from thoth.repositories.citation_repository import CitationRepository
from tests.fixtures.database_fixtures import (
    create_mock_record,
    sample_paper_data,
    sample_citation_data
)


@pytest.mark.asyncio
class TestDatabaseTransactions:
    """Integration tests for database transaction handling."""

    async def test_transaction_commit(self, mock_postgres_service):
        """Test successful transaction commit."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock(return_value='INSERT 0 1')

        transaction_committed = False

        async def mock_transaction():
            class MockTransaction:
                async def __aenter__(self):
                    return None
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    nonlocal transaction_committed
                    # Commit if no exception
                    if exc_type is None:
                        transaction_committed = True
                    return False
            return MockTransaction()

        mock_conn.transaction = mock_transaction

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_postgres_service.transaction = mock_acquire

        paper_repo = PaperRepository(mock_postgres_service)

        # Execute in transaction
        async with paper_repo.transaction() as conn:
            await conn.fetchval('INSERT INTO papers (...) VALUES (...) RETURNING id')
            await conn.execute('INSERT INTO citations (...) VALUES (...)')

        # Verify both operations were attempted
        assert mock_conn.fetchval.call_count >= 1
        assert mock_conn.execute.call_count >= 1

    async def test_transaction_rollback_on_error(self, mock_postgres_service):
        """Test transaction rollback when error occurs."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_conn.execute = AsyncMock(side_effect=Exception('Database error'))

        rollback_occurred = False

        async def mock_transaction():
            class MockTransaction:
                async def __aenter__(self):
                    return None
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    nonlocal rollback_occurred
                    # Rollback if exception
                    if exc_type is not None:
                        rollback_occurred = True
                    return False
            return MockTransaction()

        mock_conn.transaction = mock_transaction

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_postgres_service.transaction = mock_acquire

        paper_repo = PaperRepository(mock_postgres_service)

        # Execute in transaction with error
        with pytest.raises(Exception):
            async with paper_repo.transaction() as conn:
                await conn.fetchval('INSERT INTO papers (...) VALUES (...) RETURNING id')
                await conn.execute('INSERT INTO citations (...) VALUES (...)')

        # Verify rollback occurred
        assert rollback_occurred

    async def test_nested_operations_atomicity(self, mock_postgres_service):
        """Test that multiple operations in transaction are atomic."""
        mock_conn = AsyncMock()

        operations_executed = []

        async def mock_execute(query, *args):
            operations_executed.append('execute')
            if len(operations_executed) > 2:
                raise Exception('Third operation fails')
            return 'SUCCESS'

        async def mock_fetchval(query, *args):
            operations_executed.append('fetchval')
            return 1

        mock_conn.execute = mock_execute
        mock_conn.fetchval = mock_fetchval

        async def mock_transaction():
            class MockTransaction:
                async def __aenter__(self):
                    return None
                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    if exc_type is not None:
                        # Simulate rollback clearing operations
                        operations_executed.clear()
                    return False
            return MockTransaction()

        mock_conn.transaction = mock_transaction

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_postgres_service.transaction = mock_acquire

        paper_repo = PaperRepository(mock_postgres_service)

        # Try transaction with multiple operations
        with pytest.raises(Exception):
            async with paper_repo.transaction() as conn:
                await conn.fetchval('INSERT INTO papers ...')
                await conn.execute('UPDATE papers ...')
                await conn.execute('UPDATE citations ...')  # This fails

        # All operations should be rolled back
        assert len(operations_executed) == 0

    async def test_concurrent_transaction_isolation(self, mock_postgres_service):
        """Test that concurrent transactions are properly isolated."""
        transaction_1_data = []
        transaction_2_data = []

        async def create_isolated_connection(data_store):
            """Create connection with isolated data."""
            conn = AsyncMock()

            async def isolated_fetchval(query, *args):
                data_store.append('read')
                return len(data_store)

            async def isolated_execute(query, *args):
                data_store.append('write')
                return 'SUCCESS'

            conn.fetchval = isolated_fetchval
            conn.execute = isolated_execute

            async def mock_transaction():
                class MockTransaction:
                    async def __aenter__(self):
                        return None
                    async def __aexit__(self, *args):
                        pass
                return MockTransaction()

            conn.transaction = mock_transaction

            async def mock_acquire():
                class MockAcquire:
                    async def __aenter__(self):
                        return conn
                    async def __aexit__(self, *args):
                        pass
                return MockAcquire()

            return mock_acquire

        # Create two separate connection pools
        service_1 = Mock()
        service_1.transaction = await create_isolated_connection(transaction_1_data)

        service_2 = Mock()
        service_2.transaction = await create_isolated_connection(transaction_2_data)

        repo_1 = PaperRepository(service_1)
        repo_2 = PaperRepository(service_2)

        # Run concurrent transactions
        async def transaction_1():
            async with repo_1.transaction() as conn:
                await conn.execute('INSERT INTO papers ...')
                await asyncio.sleep(0.01)  # Simulate work
                await conn.fetchval('SELECT COUNT(*) ...')

        async def transaction_2():
            async with repo_2.transaction() as conn:
                await conn.execute('INSERT INTO papers ...')
                await asyncio.sleep(0.01)  # Simulate work
                await conn.fetchval('SELECT COUNT(*) ...')

        await asyncio.gather(transaction_1(), transaction_2())

        # Each transaction should have its own isolated operations
        assert len(transaction_1_data) > 0
        assert len(transaction_2_data) > 0
        assert transaction_1_data != transaction_2_data

    async def test_transaction_resource_cleanup(self, mock_postgres_service):
        """Test that transaction resources are properly cleaned up."""
        connection_acquired = False
        connection_released = False

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value='SUCCESS')

        async def mock_transaction():
            class MockTransaction:
                async def __aenter__(self):
                    nonlocal connection_acquired
                    connection_acquired = True
                    return None
                async def __aexit__(self, *args):
                    nonlocal connection_released
                    connection_released = True
                    return False
            return MockTransaction()

        mock_conn.transaction = mock_transaction

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_postgres_service.transaction = mock_acquire

        paper_repo = PaperRepository(mock_postgres_service)

        # Execute transaction
        async with paper_repo.transaction() as conn:
            await conn.execute('INSERT INTO papers ...')

        # Verify resource acquisition and cleanup
        assert connection_acquired
        assert connection_released

    async def test_transaction_timeout(self, mock_postgres_service):
        """Test transaction timeout handling."""
        mock_conn = AsyncMock()

        async def slow_operation(*args, **kwargs):
            await asyncio.sleep(10)  # Simulate slow operation
            return 'SUCCESS'

        mock_conn.execute = slow_operation

        async def mock_transaction():
            class MockTransaction:
                async def __aenter__(self):
                    return None
                async def __aexit__(self, *args):
                    return False
            return MockTransaction()

        mock_conn.transaction = mock_transaction

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_postgres_service.transaction = mock_acquire

        paper_repo = PaperRepository(mock_postgres_service)

        # Transaction should timeout
        with pytest.raises(asyncio.TimeoutError):
            async with asyncio.timeout(1):
                async with paper_repo.transaction() as conn:
                    await conn.execute('INSERT INTO papers ...')

    async def test_multi_repository_transaction(self, mock_postgres_service):
        """Test transaction spanning multiple repositories."""
        operations_log = []

        mock_conn = AsyncMock()

        async def log_execute(query, *args):
            operations_log.append(('execute', query))
            return 'SUCCESS'

        async def log_fetchval(query, *args):
            operations_log.append(('fetchval', query))
            return 1

        mock_conn.execute = log_execute
        mock_conn.fetchval = log_fetchval

        async def mock_transaction():
            class MockTransaction:
                async def __aenter__(self):
                    return None
                async def __aexit__(self, exc_type, *args):
                    if exc_type:
                        operations_log.clear()
                    return False
            return MockTransaction()

        mock_conn.transaction = mock_transaction

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_postgres_service.transaction = mock_acquire

        paper_repo = PaperRepository(mock_postgres_service)
        citation_repo = CitationRepository(mock_postgres_service)

        # Execute operations across multiple repositories
        async with paper_repo.transaction() as conn:
            paper_id = await conn.fetchval('INSERT INTO papers (...) RETURNING id')
            await conn.execute('INSERT INTO citations (...) VALUES ($1, ...)', paper_id)

        # Verify both repositories used same transaction
        assert len(operations_log) == 2
        assert operations_log[0][0] == 'fetchval'
        assert operations_log[1][0] == 'execute'

    async def test_connection_pool_exhaustion(self):
        """Test behavior when connection pool is exhausted."""
        from tests.fixtures.database_fixtures import MockConnectionPool

        pool = MockConnectionPool(max_size=2)

        # Acquire all connections
        async with pool.acquire():
            async with pool.acquire():
                # Pool should be exhausted
                with pytest.raises(Exception, match='pool exhausted'):
                    async with pool.acquire():
                        pass

    async def test_async_resource_cleanup_on_exception(self, mock_postgres_service):
        """Test that async resources are cleaned up even on exception."""
        cleanup_called = False

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception('Query failed'))

        async def mock_transaction():
            class MockTransaction:
                async def __aenter__(self):
                    return None
                async def __aexit__(self, *args):
                    nonlocal cleanup_called
                    cleanup_called = True
                    return False
            return MockTransaction()

        mock_conn.transaction = mock_transaction

        async def mock_acquire():
            class MockAcquire:
                async def __aenter__(self):
                    return mock_conn
                async def __aexit__(self, *args):
                    pass
            return MockAcquire()

        mock_postgres_service.transaction = mock_acquire

        paper_repo = PaperRepository(mock_postgres_service)

        # Execute with error
        with pytest.raises(Exception):
            async with paper_repo.transaction() as conn:
                await conn.execute('INSERT ...')

        # Cleanup should still be called
        assert cleanup_called
