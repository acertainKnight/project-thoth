"""
Browser Manager for workflow execution.

This module manages browser lifecycle, pooling, and session persistence
for browser-based discovery workflows.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Dict, Optional
from uuid import UUID

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    async_playwright,
)

from thoth.config import Config, config


class BrowserManagerError(Exception):
    """Exception raised for browser manager errors."""

    pass


class BrowserManager:
    """
    Manages browser lifecycle and pooling for workflow execution.

    This class provides:
    - Browser instance pooling (max 5 concurrent browsers)
    - Session state persistence (cookies + localStorage)
    - Headless mode by default
    - Proper cleanup to prevent memory leaks
    - Error handling and timeouts

    Example:
        >>> manager = BrowserManager()
        >>> await manager.initialize()
        >>> browser = await manager.get_browser()
        >>> # Use browser for workflow execution
        >>> await manager.cleanup(browser)
        >>> await manager.shutdown()
    """

    def __init__(
        self,
        thoth_config: Config | None = None,
        max_concurrent_browsers: int = 5,
        default_timeout: int = 30000,
    ):
        """
        Initialize the BrowserManager.

        Args:
            thoth_config: Optional Thoth configuration object
            max_concurrent_browsers: Maximum number of concurrent browser instances
            default_timeout: Default timeout in milliseconds for operations
        """
        self.config = thoth_config or config
        self.max_concurrent_browsers = max_concurrent_browsers
        self.default_timeout = default_timeout

        # Browser pool management
        self._playwright = None
        self._browser_type = None
        self._active_contexts: Dict[str, BrowserContext] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_browsers)

        # Session storage directory
        self.session_dir = Path(self.config.agent_storage_dir) / 'browser_sessions'
        self.session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(
            f'BrowserManager initialized (max_browsers={max_concurrent_browsers}, '
            f'timeout={default_timeout}ms)'
        )

    async def initialize(self) -> None:
        """
        Initialize Playwright and browser type.

        Must be called before using the browser manager.

        Raises:
            BrowserManagerError: If initialization fails
        """
        try:
            self._playwright = await async_playwright().start()
            # Use Chromium for better compatibility
            self._browser_type = self._playwright.chromium
            logger.info('Playwright initialized successfully')
        except Exception as e:
            raise BrowserManagerError(f'Failed to initialize Playwright: {e}') from e

    async def get_browser(
        self,
        headless: bool = True,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
    ) -> BrowserContext:
        """
        Get a browser context from the pool.

        This method acquires a semaphore slot to enforce the concurrent browser limit.
        The browser context is isolated and can be used for workflow execution.

        Args:
            headless: Whether to run browser in headless mode (default: True)
            viewport: Viewport size dict with 'width' and 'height' keys
            user_agent: Custom user agent string

        Returns:
            BrowserContext: Isolated browser context for workflow execution

        Raises:
            BrowserManagerError: If browser cannot be created
        """
        if not self._browser_type:
            raise BrowserManagerError('BrowserManager not initialized. Call initialize() first.')

        # Acquire semaphore to limit concurrent browsers
        await self._semaphore.acquire()

        try:
            # Default viewport
            if viewport is None:
                viewport = {'width': 1920, 'height': 1080}

            # Launch browser with configuration
            browser = await self._browser_type.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ],
            )

            # Create isolated context
            context = await browser.new_context(
                viewport=viewport,
                user_agent=user_agent,
                locale='en-US',
                timezone_id='America/New_York',
            )

            # Set default timeouts
            context.set_default_timeout(self.default_timeout)
            context.set_default_navigation_timeout(self.default_timeout)

            # Track context
            context_id = str(id(context))
            self._active_contexts[context_id] = context

            logger.debug(
                f'Created browser context {context_id} '
                f'(active={len(self._active_contexts)}/{self.max_concurrent_browsers})'
            )

            return context

        except Exception as e:
            # Release semaphore on error
            self._semaphore.release()
            raise BrowserManagerError(f'Failed to create browser context: {e}') from e

    @asynccontextmanager
    async def browser_context(
        self,
        headless: bool = True,
        viewport: Optional[Dict[str, int]] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[UUID] = None,
    ) -> AsyncIterator[BrowserContext]:
        """
        Context manager for safely acquiring and releasing browser contexts.

        This ensures the semaphore is always released, even if the workflow fails.

        Example:
            >>> async with manager.browser_context() as context:
            ...     page = await context.new_page()
            ...     # Use the browser context
            ...     # Automatic cleanup happens here

        Args:
            headless: Whether to run browser in headless mode
            viewport: Custom viewport dimensions
            user_agent: Custom user agent string
            session_id: Optional session ID to restore saved state

        Yields:
            BrowserContext: A ready-to-use browser context

        Raises:
            BrowserManagerError: If browser context cannot be created
        """
        if session_id:
            context = await self.load_session(session_id, headless, viewport, user_agent)
        else:
            context = await self.get_browser(headless, viewport, user_agent)

        try:
            yield context
        finally:
            # Always cleanup, even if workflow fails
            await self.cleanup(context)

    async def save_session(
        self,
        context: BrowserContext,
        session_id: UUID,
    ) -> None:
        """
        Save browser session state for later reuse.

        Saves cookies and localStorage state to disk, allowing workflows
        to reuse authentication sessions without re-logging in.

        Args:
            context: Browser context to save
            session_id: Unique identifier for this session

        Raises:
            BrowserManagerError: If session cannot be saved
        """
        try:
            session_file = self.session_dir / f'{session_id}.json'

            # Save storage state (cookies + localStorage)
            await context.storage_state(path=str(session_file))

            logger.info(f'Saved browser session to {session_file}')

        except PlaywrightError as e:
            raise BrowserManagerError(f'Failed to save session: {e}') from e

    async def load_session(
        self,
        session_id: UUID,
        headless: bool = True,
        viewport: Optional[Dict[str, int]] = None,
    ) -> BrowserContext:
        """
        Load a previously saved browser session.

        Restores cookies and localStorage from a saved session,
        avoiding the need to re-authenticate.

        Args:
            session_id: UUID of the saved session
            headless: Whether to run browser in headless mode
            viewport: Viewport size dict with 'width' and 'height' keys

        Returns:
            BrowserContext: Browser context with restored session state

        Raises:
            BrowserManagerError: If session cannot be loaded
        """
        if not self._browser_type:
            raise BrowserManagerError('BrowserManager not initialized. Call initialize() first.')

        session_file = self.session_dir / f'{session_id}.json'

        if not session_file.exists():
            raise BrowserManagerError(f'Session file not found: {session_file}')

        # Acquire semaphore
        await self._semaphore.acquire()

        try:
            # Default viewport
            if viewport is None:
                viewport = {'width': 1920, 'height': 1080}

            # Launch browser
            browser = await self._browser_type.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                ],
            )

            # Create context with stored state
            context = await browser.new_context(
                viewport=viewport,
                storage_state=str(session_file),
                locale='en-US',
                timezone_id='America/New_York',
            )

            # Set default timeouts
            context.set_default_timeout(self.default_timeout)
            context.set_default_navigation_timeout(self.default_timeout)

            # Track context
            context_id = str(id(context))
            self._active_contexts[context_id] = context

            logger.info(f'Loaded browser session from {session_file}')

            return context

        except Exception as e:
            # Release semaphore on error
            self._semaphore.release()
            raise BrowserManagerError(f'Failed to load session: {e}') from e

    async def cleanup(
        self,
        context: BrowserContext,
    ) -> None:
        """
        Clean up browser context and release resources.

        Closes the browser context and releases the semaphore slot.
        Should always be called after workflow execution completes.

        Args:
            context: Browser context to clean up
        """
        context_id = str(id(context))

        try:
            # Close context and browser
            if context:
                await context.close()
                # Close the browser instance
                if context.browser:
                    await context.browser.close()

            # Remove from tracking
            if context_id in self._active_contexts:
                del self._active_contexts[context_id]

            logger.debug(
                f'Cleaned up browser context {context_id} '
                f'(active={len(self._active_contexts)}/{self.max_concurrent_browsers})'
            )

        except Exception as e:
            logger.error(f'Error during browser cleanup: {e}')

        finally:
            # Always release semaphore
            self._semaphore.release()

    async def cleanup_expired_sessions(
        self,
        max_age_days: int = 7,
    ) -> int:
        """
        Clean up expired session files.

        Removes session files older than the specified age to prevent
        storage bloat and remove stale sessions.

        Args:
            max_age_days: Maximum age of session files in days

        Returns:
            Number of session files deleted
        """
        import time

        deleted = 0
        max_age_seconds = max_age_days * 24 * 60 * 60
        current_time = time.time()

        for session_file in self.session_dir.glob('*.json'):
            file_age = current_time - session_file.stat().st_mtime

            if file_age > max_age_seconds:
                try:
                    session_file.unlink()
                    deleted += 1
                    logger.debug(f'Deleted expired session: {session_file.name}')
                except Exception as e:
                    logger.error(f'Failed to delete session {session_file.name}: {e}')

        if deleted > 0:
            logger.info(f'Cleaned up {deleted} expired browser sessions')

        return deleted

    async def shutdown(self) -> None:
        """
        Shutdown the browser manager.

        Closes all active browser contexts and stops Playwright.
        Should be called when the application is shutting down.
        """
        logger.info('Shutting down BrowserManager...')

        # Close all active contexts
        for context_id, context in list(self._active_contexts.items()):
            try:
                await context.close()
                if context.browser:
                    await context.browser.close()
            except Exception as e:
                logger.error(f'Error closing context {context_id}: {e}')

        self._active_contexts.clear()

        # Stop Playwright
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.error(f'Error stopping Playwright: {e}')

        logger.info('BrowserManager shutdown complete')

    @property
    def active_browser_count(self) -> int:
        """Get the number of currently active browser contexts."""
        return len(self._active_contexts)

    @property
    def available_slots(self) -> int:
        """Get the number of available browser slots."""
        return self.max_concurrent_browsers - len(self._active_contexts)
