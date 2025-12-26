"""
Browser automation module for workflow-based discovery.

This module provides browser automation capabilities using Playwright for
executing user-recorded workflows to discover articles from sources that
require authentication or don't provide public APIs.
"""

from thoth.discovery.browser.browser_manager import BrowserManager

__all__ = ['BrowserManager']
