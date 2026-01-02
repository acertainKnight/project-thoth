"""
Database fixtures for testing.

Provides test database setup, mock data, and utilities for testing
repository and service layers with proper isolation and cleanup.
"""

import asyncio  # noqa: I001
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional  # noqa: F401, UP035
from unittest.mock import Mock, AsyncMock, MagicMock  # noqa: F401

import asyncpg
import pytest
import pytest_asyncio


# Event loop fixture removed - pytest-asyncio provides one by default
# If you need a custom event loop, use @pytest.mark.asyncio(loop_scope="session")


@pytest_asyncio.fixture
async def mock_postgres_service():
    """
    Create a mock PostgresService with realistic behavior.

    This mock simulates connection pool operations, transactions,
    and proper resource cleanup without requiring a real database.
    """
    service = Mock()
    service._pool = Mock()
    service._connection_lock = asyncio.Lock()

    # Mock pool stats
    service._pool.get_size = Mock(return_value=10)
    service._pool.get_idle_size = Mock(return_value=5)

    # Track queries for verification
    service.executed_queries = []
    service.transaction_active = False

    async def mock_initialize():
        """Mock pool initialization."""
        service._pool = Mock()
        service._pool.get_size = Mock(return_value=10)
        service._pool.get_idle_size = Mock(return_value=5)

    async def mock_close():
        """Mock pool closure."""
        service._pool = None

    # Create tracking side effects that respect return_value
    def make_tracking_side_effect(mock_obj, query_type, default_return=None):
        """Create a side effect that tracks queries and returns configurable values."""

        async def side_effect(query: str, *args, **kwargs):
            service.executed_queries.append(
                {
                    'type': query_type,
                    'query': query,
                    'args': args,
                    **{k: v for k, v in kwargs.items() if k in ['timeout', 'column']},
                }
            )
            # Return configured return_value if set, otherwise default
            # AsyncMock stores configured return_value in _mock_return_value
            if hasattr(mock_obj, '_mock_return_value'):
                return mock_obj._mock_return_value
            return default_return

        return side_effect

    # Create AsyncMocks with tracking side effects
    # Tests can override .return_value and side_effect will use it
    mock_execute = AsyncMock()
    mock_execute.side_effect = make_tracking_side_effect(
        mock_execute, 'execute', 'EXECUTED'
    )

    mock_fetch = AsyncMock()
    mock_fetch.side_effect = make_tracking_side_effect(mock_fetch, 'fetch', [])

    mock_fetchrow = AsyncMock()
    mock_fetchrow.side_effect = make_tracking_side_effect(
        mock_fetchrow, 'fetchrow', None
    )

    mock_fetchval = AsyncMock()
    mock_fetchval.side_effect = make_tracking_side_effect(
        mock_fetchval, 'fetchval', None
    )

    @asynccontextmanager
    async def mock_acquire():
        """Mock connection acquisition."""
        conn = Mock()
        conn.execute = AsyncMock(return_value='EXECUTED')
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetchval = AsyncMock(return_value=None)
        conn.executemany = AsyncMock()
        yield conn

    @asynccontextmanager
    async def mock_transaction():
        """Mock transaction context."""
        service.transaction_active = True
        conn = Mock()
        conn.execute = AsyncMock(return_value='EXECUTED')
        conn.fetch = AsyncMock(return_value=[])
        conn.fetchrow = AsyncMock(return_value=None)
        conn.fetchval = AsyncMock(return_value=None)

        @asynccontextmanager
        async def transaction_ctx():
            try:
                yield conn
            finally:
                service.transaction_active = False

        conn.transaction = transaction_ctx

        try:
            async with conn.transaction():
                yield conn
        finally:
            service.transaction_active = False

    # Assign mock methods
    service.initialize = mock_initialize
    service.close = mock_close
    service.execute = mock_execute
    service.fetch = mock_fetch
    service.fetchrow = mock_fetchrow
    service.fetchval = mock_fetchval
    service.acquire = mock_acquire
    service.transaction = mock_transaction

    return service


@pytest_asyncio.fixture
async def mock_pool():
    """Create a mock asyncpg connection pool."""
    pool = AsyncMock()
    pool.get_size = Mock(return_value=20)
    pool.get_idle_size = Mock(return_value=15)
    pool.close = AsyncMock()

    # Mock connection
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value='PostgreSQL 15.0')
    conn.execute = AsyncMock(return_value='EXECUTED')
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)

    @asynccontextmanager
    async def mock_acquire():
        yield conn

    pool.acquire = mock_acquire

    return pool


def create_mock_record(**kwargs) -> asyncpg.Record:
    """
    Create a mock asyncpg.Record.

    Args:
        **kwargs: Field name-value pairs

    Returns:
        Mock Record that behaves like asyncpg.Record
    """

    class MockRecord:
        """Mock implementation of asyncpg.Record."""

        def __getitem__(self, key):
            return kwargs[key]

        def keys(self):
            return kwargs.keys()

        def values(self):
            return kwargs.values()

        def items(self):
            return kwargs.items()

        def get(self, key, default=None):
            return kwargs.get(key, default)

        def __iter__(self):
            return iter(kwargs.items())

        def __len__(self):
            return len(kwargs)

    return MockRecord()


@pytest.fixture
def sample_paper_data() -> Dict[str, Any]:  # noqa: UP006
    """Sample paper data for testing."""
    return {
        'id': 1,
        'title': 'Test Paper',
        'authors': ['John Doe', 'Jane Smith'],
        'abstract': 'This is a test abstract.',
        'doi': '10.1000/test.123',
        'arxiv_id': '2024.12345',
        'publication_date': '2024-01-15',
        'tags': ['machine-learning', 'nlp'],
        'content': 'Full paper content...',
        'created_at': '2024-01-20T10:00:00',
        'updated_at': '2024-01-20T10:00:00',
    }


@pytest.fixture
def sample_citation_data() -> Dict[str, Any]:  # noqa: UP006
    """Sample citation data for testing."""
    return {
        'id': 1,
        'citing_paper_id': 1,
        'cited_paper_id': 2,
        'metadata': {'context': 'Related work section'},
        'created_at': '2024-01-20T10:00:00',
    }


@pytest.fixture
def sample_papers_batch() -> list[Dict[str, Any]]:  # noqa: UP006
    """Sample batch of papers for testing."""
    return [
        {
            'id': i,
            'title': f'Test Paper {i}',
            'authors': [f'Author {i}'],
            'abstract': f'Abstract {i}',
            'doi': f'10.1000/test.{i}',
            'tags': ['test'],
            'created_at': f'2024-01-{i:02d}T10:00:00',
        }
        for i in range(1, 11)
    ]


class MockConnectionPool:
    """
    Mock connection pool that simulates race conditions and resource limits.

    This is useful for testing the connection pool race condition fix
    where multiple threads could create duplicate pools.
    """

    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self.active_connections = 0
        self.total_created = 0
        self.initialization_count = 0
        self._lock = asyncio.Lock()

    async def initialize(self):
        """Simulate pool initialization with potential race condition."""
        async with self._lock:
            # Simulate delay that could cause race condition
            await asyncio.sleep(0.01)
            self.initialization_count += 1

    @asynccontextmanager
    async def acquire(self):
        """Acquire connection with resource limits."""
        if self.active_connections >= self.max_size:
            raise Exception('Connection pool exhausted')

        self.active_connections += 1
        self.total_created += 1

        try:
            conn = AsyncMock()
            conn.execute = AsyncMock(return_value='EXECUTED')
            conn.fetch = AsyncMock(return_value=[])
            conn.fetchrow = AsyncMock(return_value=None)
            conn.fetchval = AsyncMock(return_value=1)
            yield conn
        finally:
            self.active_connections -= 1


@pytest.fixture
def mock_connection_pool():
    """Create mock connection pool for testing."""
    return MockConnectionPool()


class AsyncIterator:
    """Helper for creating async iterators in tests."""

    def __init__(self, items):
        self.items = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self.items)
        except StopIteration:
            raise StopAsyncIteration  # noqa: B904


def async_generator(items):
    """Convert list to async generator for testing."""

    async def gen():
        for item in items:
            yield item

    return gen()
