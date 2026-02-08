"""
Async utility helpers for safely running coroutines from sync contexts.

Provides run_async_safely() which works correctly whether called from:
- A synchronous context (no event loop running) -> uses asyncio.run()
- An async context (event loop already running, e.g. inside uvicorn/MCP server)
  -> runs the coroutine in a dedicated thread with its own event loop

This solves the common "asyncio.run() cannot be called from a running event loop"
error that occurs when sync service methods are called from async MCP tool handlers.
"""

import asyncio
import threading
from collections.abc import Coroutine
from typing import TypeVar

from loguru import logger

T = TypeVar('T')


def run_async_safely(coro: Coroutine) -> T:
    """Run an async coroutine safely from a synchronous context.

    Works regardless of whether an event loop is already running.

    Args:
        coro: An awaitable coroutine object (e.g., ``fetch_data()``).
            The coroutine will be awaited in the appropriate event loop context.

    Returns:
        T: The return value of the coroutine.

    Raises:
        Exception: Any exception raised by the coroutine is re-raised.

    Example:
        >>> async def fetch_data():
        ...     return await some_async_operation()
        >>> result = run_async_safely(fetch_data())
    """
    has_running_loop = False
    try:
        asyncio.get_running_loop()
        has_running_loop = True
    except RuntimeError:
        pass

    if has_running_loop:
        # We're inside a running event loop (e.g., uvicorn/MCP server).
        # Run the coroutine in a separate thread with its own event loop.
        logger.debug(
            'run_async_safely: running event loop detected, '
            'delegating to background thread'
        )
        return _run_in_new_thread(coro)
    else:
        # No event loop running — safe to use asyncio.run()
        return asyncio.run(coro)


def _run_in_new_thread(coro: Coroutine) -> T:
    """Run a coroutine in a new thread with its own event loop.

    Args:
        coro: The coroutine to run.

    Returns:
        T: The return value of the coroutine.
    """
    result = None
    exception = None

    def _thread_target():
        nonlocal result, exception
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro)
            finally:
                loop.close()
        except Exception as e:
            exception = e

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    thread.join(timeout=300)  # 5-minute timeout for long operations

    if thread.is_alive():
        raise TimeoutError('Async operation timed out after 300 seconds')

    if exception is not None:
        raise exception

    return result
