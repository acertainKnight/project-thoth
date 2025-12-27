"""
Tests for BrowserManager class.

This module tests the browser lifecycle management, pooling,
and session persistence functionality.
"""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from thoth.discovery.browser import BrowserManager
from thoth.discovery.browser.browser_manager import BrowserManagerError


@pytest.fixture
async def browser_manager():
    """Create a BrowserManager instance for testing."""
    manager = BrowserManager(max_concurrent_browsers=2)
    await manager.initialize()
    yield manager
    await manager.shutdown()


@pytest.mark.asyncio
async def test_browser_manager_initialization():
    """Test that BrowserManager initializes correctly."""
    manager = BrowserManager()
    assert manager.max_concurrent_browsers == 5
    assert manager.default_timeout == 30000
    assert manager._playwright is None

    await manager.initialize()
    assert manager._playwright is not None
    assert manager._browser_type is not None

    await manager.shutdown()


@pytest.mark.asyncio
async def test_get_browser_without_initialization():
    """Test that getting browser without initialization raises error."""
    manager = BrowserManager()

    with pytest.raises(BrowserManagerError, match='not initialized'):
        await manager.get_browser()


@pytest.mark.asyncio
async def test_get_browser_basic(browser_manager):
    """Test basic browser context creation."""
    context = await browser_manager.get_browser(headless=True)

    assert context is not None
    assert browser_manager.active_browser_count == 1
    assert browser_manager.available_slots == 1

    # Create a page and navigate
    page = await context.new_page()
    await page.goto('https://example.com')
    assert 'example.com' in page.url.lower()

    await browser_manager.cleanup(context)
    assert browser_manager.active_browser_count == 0


@pytest.mark.asyncio
async def test_browser_pooling(browser_manager):
    """Test browser pooling limits concurrent browsers."""
    # Create 2 browsers (max limit)
    context1 = await browser_manager.get_browser()
    context2 = await browser_manager.get_browser()

    assert browser_manager.active_browser_count == 2
    assert browser_manager.available_slots == 0

    # Try to create a third browser - should block
    # We'll use a timeout to verify it blocks
    try:
        await asyncio.wait_for(
            browser_manager.get_browser(), timeout=0.1
        )
        pytest.fail('Should have blocked due to browser pool limit')
    except asyncio.TimeoutError:
        pass  # Expected

    # Clean up first browser
    await browser_manager.cleanup(context1)
    assert browser_manager.active_browser_count == 1

    # Now we can create a third browser
    context3 = await browser_manager.get_browser()
    assert browser_manager.active_browser_count == 2

    # Clean up remaining browsers
    await browser_manager.cleanup(context2)
    await browser_manager.cleanup(context3)
    assert browser_manager.active_browser_count == 0


@pytest.mark.asyncio
async def test_save_and_load_session(browser_manager, tmp_path):
    """Test session state persistence."""
    # Override session directory for test
    browser_manager.session_dir = tmp_path

    # Create a browser and navigate to set cookies
    session_id = uuid4()
    context = await browser_manager.get_browser()
    page = await context.new_page()

    # Navigate and set some state
    await page.goto('https://example.com')
    await page.evaluate('localStorage.setItem("test_key", "test_value")')

    # Save session
    await browser_manager.save_session(context, session_id)
    await browser_manager.cleanup(context)

    # Verify session file was created
    session_file = tmp_path / f'{session_id}.json'
    assert session_file.exists()

    # Load session
    context2 = await browser_manager.load_session(session_id)
    page2 = await context2.new_page()
    await page2.goto('https://example.com')

    # Verify state was restored
    stored_value = await page2.evaluate('localStorage.getItem("test_key")')
    assert stored_value == 'test_value'

    await browser_manager.cleanup(context2)


@pytest.mark.asyncio
async def test_load_nonexistent_session(browser_manager):
    """Test loading a nonexistent session raises error."""
    with pytest.raises(BrowserManagerError, match='Session file not found'):
        await browser_manager.load_session(uuid4())


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(browser_manager, tmp_path):
    """Test cleanup of expired session files."""
    import time

    browser_manager.session_dir = tmp_path

    # Create some fake session files
    old_session = tmp_path / f'{uuid4()}.json'
    old_session.write_text('{}')

    # Make the file appear old (modify timestamp)
    old_time = time.time() - (8 * 24 * 60 * 60)  # 8 days ago
    import os

    os.utime(old_session, (old_time, old_time))

    recent_session = tmp_path / f'{uuid4()}.json'
    recent_session.write_text('{}')

    # Clean up sessions older than 7 days
    deleted = await browser_manager.cleanup_expired_sessions(max_age_days=7)

    assert deleted == 1
    assert not old_session.exists()
    assert recent_session.exists()


@pytest.mark.asyncio
async def test_browser_custom_viewport(browser_manager):
    """Test creating browser with custom viewport."""
    viewport = {'width': 1280, 'height': 720}
    context = await browser_manager.get_browser(viewport=viewport)

    page = await context.new_page()
    size = page.viewport_size

    assert size['width'] == 1280
    assert size['height'] == 720

    await browser_manager.cleanup(context)


@pytest.mark.asyncio
async def test_browser_cleanup_releases_semaphore(browser_manager):
    """Test that cleanup properly releases semaphore slot."""
    # Fill the pool
    context1 = await browser_manager.get_browser()
    context2 = await browser_manager.get_browser()

    assert browser_manager.available_slots == 0

    # Cleanup one
    await browser_manager.cleanup(context1)
    assert browser_manager.available_slots == 1

    # Can create another
    context3 = await browser_manager.get_browser()
    assert browser_manager.available_slots == 0

    await browser_manager.cleanup(context2)
    await browser_manager.cleanup(context3)


@pytest.mark.asyncio
async def test_multiple_pages_in_context(browser_manager):
    """Test that multiple pages can be created in one context."""
    context = await browser_manager.get_browser()

    page1 = await context.new_page()
    page2 = await context.new_page()

    await page1.goto('https://example.com')
    await page2.goto('https://example.org')

    assert 'example.com' in page1.url.lower()
    assert 'example.org' in page2.url.lower()

    await browser_manager.cleanup(context)
