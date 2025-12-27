"""
Example usage of BrowserManager for workflow automation.

This script demonstrates how to use the BrowserManager class for
browser-based discovery workflows.
"""

import asyncio
from uuid import uuid4

from thoth.discovery.browser import BrowserManager


async def basic_navigation_example():
    """Basic example: Launch browser and navigate to a page."""
    manager = BrowserManager(max_concurrent_browsers=3)
    await manager.initialize()

    try:
        # Get a browser context
        context = await manager.get_browser(headless=True)

        # Create a page
        page = await context.new_page()

        # Navigate to a website
        await page.goto('https://example.com')
        print(f'Navigated to: {page.url}')

        # Get page title
        title = await page.title()
        print(f'Page title: {title}')

        # Take a screenshot
        await page.screenshot(path='/tmp/example.png')
        print('Screenshot saved to /tmp/example.png')

        # Cleanup
        await manager.cleanup(context)

    finally:
        await manager.shutdown()


async def session_persistence_example():
    """Example: Save and restore browser session."""
    manager = BrowserManager()
    await manager.initialize()

    session_id = uuid4()

    try:
        # Create browser and set some state
        print('Creating session...')
        context = await manager.get_browser()
        page = await context.new_page()

        await page.goto('https://example.com')
        await page.evaluate('localStorage.setItem("user", "test_user")')
        print('Set localStorage: user=test_user')

        # Save session
        await manager.save_session(context, session_id)
        print(f'Session saved with ID: {session_id}')
        await manager.cleanup(context)

        # Later: Load the session
        print('\nRestoring session...')
        context2 = await manager.load_session(session_id)
        page2 = await context2.new_page()
        await page2.goto('https://example.com')

        # Verify state was restored
        user = await page2.evaluate('localStorage.getItem("user")')
        print(f'Retrieved localStorage: user={user}')

        await manager.cleanup(context2)

    finally:
        await manager.shutdown()


async def concurrent_browsers_example():
    """Example: Multiple concurrent browser sessions."""
    manager = BrowserManager(max_concurrent_browsers=3)
    await manager.initialize()

    async def visit_site(url: str, index: int):
        """Visit a site and return the title."""
        context = await manager.get_browser()
        page = await context.new_page()

        await page.goto(url)
        title = await page.title()
        print(f'Browser {index}: {title}')

        await manager.cleanup(context)
        return title

    try:
        # Visit multiple sites concurrently
        sites = [
            'https://example.com',
            'https://example.org',
            'https://example.net',
        ]

        tasks = [visit_site(url, i) for i, url in enumerate(sites)]
        results = await asyncio.gather(*tasks)
        print(f'\nVisited {len(results)} sites concurrently')

    finally:
        await manager.shutdown()


async def workflow_simulation_example():
    """Example: Simulate a discovery workflow with authentication."""
    manager = BrowserManager()
    await manager.initialize()

    session_id = uuid4()

    try:
        context = await manager.get_browser(headless=True)
        page = await context.new_page()

        # Step 1: Navigate to site
        print('Step 1: Navigating to example site...')
        await page.goto('https://example.com')

        # Step 2: Simulate form interaction
        print('Step 2: Filling form...')
        # In a real workflow, you would fill authentication forms
        # await page.fill('input[name="username"]', 'user')
        # await page.fill('input[name="password"]', 'pass')
        # await page.click('button[type="submit"]')

        # Step 3: Save session for reuse
        print('Step 3: Saving session...')
        await manager.save_session(context, session_id)

        # Step 4: Extract data (simulated)
        print('Step 4: Extracting data...')
        title = await page.title()
        content = await page.content()
        print(f'Extracted title: {title}')
        print(f'Content length: {len(content)} characters')

        await manager.cleanup(context)

        # Later execution: Reuse session
        print('\n--- Reusing session for next run ---')
        context2 = await manager.load_session(session_id)
        page2 = await context2.new_page()
        await page2.goto('https://example.com')
        print('Session restored, skipped authentication')

        await manager.cleanup(context2)

    finally:
        await manager.shutdown()


if __name__ == '__main__':
    print('=== Browser Manager Examples ===\n')

    print('1. Basic Navigation Example')
    asyncio.run(basic_navigation_example())

    print('\n2. Session Persistence Example')
    asyncio.run(session_persistence_example())

    print('\n3. Concurrent Browsers Example')
    asyncio.run(concurrent_browsers_example())

    print('\n4. Workflow Simulation Example')
    asyncio.run(workflow_simulation_example())

    print('\n=== All examples completed ===')
