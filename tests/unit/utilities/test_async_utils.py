"""
Tests for thoth.utilities.async_utils module.

Verifies that run_async_safely() works correctly in both sync and async contexts,
preventing the "asyncio.run() cannot be called from a running event loop" error
that broke MCP tools when called from uvicorn's event loop.
"""

import asyncio

import pytest

from thoth.utilities.async_utils import run_async_safely


class TestRunAsyncSafely:
    """Test run_async_safely() in various contexts."""

    def test_basic_coroutine_from_sync_context(self):
        """Test running a simple coroutine from a synchronous context."""

        async def fetch_value():
            return 42

        result = run_async_safely(fetch_value())
        assert result == 42

    def test_coroutine_with_await_from_sync_context(self):
        """Test running a coroutine that uses await internally."""

        async def compute():
            await asyncio.sleep(0.01)
            return 'hello'

        result = run_async_safely(compute())
        assert result == 'hello'

    def test_coroutine_from_async_context(self):
        """Test running a coroutine when already inside an event loop.

        This is the critical test case: simulates what happens when an MCP
        tool handler (async) calls a sync service method that needs to run
        a coroutine. Without run_async_safely, this would raise:
        RuntimeError: asyncio.run() cannot be called from a running event loop
        """

        async def inner_coro():
            await asyncio.sleep(0.01)
            return 'from_async_context'

        async def outer():
            # We're inside an event loop here (just like inside uvicorn)
            # Calling asyncio.run() directly would fail
            result = run_async_safely(inner_coro())
            return result

        result = asyncio.run(outer())
        assert result == 'from_async_context'

    def test_coroutine_exception_propagates(self):
        """Test that exceptions from coroutines are properly re-raised."""

        async def failing_coro():
            raise ValueError('test error')

        with pytest.raises(ValueError, match='test error'):
            run_async_safely(failing_coro())

    def test_coroutine_exception_propagates_from_async_context(self):
        """Test exception propagation when called from an async context."""

        async def failing_coro():
            raise RuntimeError('async failure')

        async def outer():
            return run_async_safely(failing_coro())

        with pytest.raises(RuntimeError, match='async failure'):
            asyncio.run(outer())

    def test_return_value_types(self):
        """Test that various return types are preserved."""

        async def return_dict():
            return {'key': 'value', 'count': 3}

        async def return_list():
            return [1, 2, 3]

        async def return_none():
            return None

        assert run_async_safely(return_dict()) == {'key': 'value', 'count': 3}
        assert run_async_safely(return_list()) == [1, 2, 3]
        assert run_async_safely(return_none()) is None

    def test_nested_async_calls_from_sync(self):
        """Test coroutine that calls other coroutines."""

        async def fetch_item(item_id: int) -> str:
            await asyncio.sleep(0.001)
            return f'item_{item_id}'

        async def fetch_all():
            results = []
            for i in range(3):
                results.append(await fetch_item(i))
            return results

        result = run_async_safely(fetch_all())
        assert result == ['item_0', 'item_1', 'item_2']

    def test_concurrent_calls_from_async_context(self):
        """Test multiple run_async_safely calls from the same async context."""

        async def get_value(n: int) -> int:
            await asyncio.sleep(0.001)
            return n * 2

        async def outer():
            results = []
            for i in range(3):
                results.append(run_async_safely(get_value(i)))
            return results

        result = asyncio.run(outer())
        assert result == [0, 2, 4]


class TestRunAsyncSafelyWithAsyncpgPattern:
    """Test the specific pattern used by rag_service and discovery scheduler.

    These tests mirror the actual usage pattern: a sync method defines an async
    inner function that makes database calls, then uses run_async_safely to
    execute it.
    """

    def test_sync_method_with_async_db_pattern(self):
        """Test the sync-method-wrapping-async-db-call pattern."""

        def sync_service_method() -> list[str]:
            """Simulates RAGService.index_from_database."""

            async def fetch_from_db():
                # Simulate async DB query
                await asyncio.sleep(0.01)
                return ['paper_1', 'paper_2', 'paper_3']

            return run_async_safely(fetch_from_db())

        result = sync_service_method()
        assert result == ['paper_1', 'paper_2', 'paper_3']

    def test_sync_method_with_async_db_pattern_from_async_context(self):
        """Test the DB pattern when called from an MCP tool handler (async context)."""

        def sync_service_method() -> dict:
            async def fetch_and_process():
                await asyncio.sleep(0.01)
                return {'status': 'ok', 'count': 5}

            return run_async_safely(fetch_and_process())

        async def mcp_tool_handler():
            """Simulates an MCP tool's execute() method calling a sync service."""
            return sync_service_method()

        result = asyncio.run(mcp_tool_handler())
        assert result == {'status': 'ok', 'count': 5}

    def test_sync_save_method_from_async_context(self):
        """Test the save/write pattern (no return value) from async context."""
        saved_data = []

        def sync_save_method(data: str) -> None:
            async def save_to_db():
                await asyncio.sleep(0.01)
                saved_data.append(data)

            run_async_safely(save_to_db())

        async def mcp_tool_handler():
            sync_save_method('test_record')

        asyncio.run(mcp_tool_handler())
        assert saved_data == ['test_record']
