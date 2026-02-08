"""
Browser automation module for workflow-based discovery.

This module provides browser automation capabilities using Playwright for
executing user-recorded workflows to discover articles from sources that
require authentication or don't provide public APIs.

NOTE: Browser automation dependencies (playwright) are optional.
If not installed, browser-based discovery features will be unavailable.
"""

# Try to import browser automation components, but make them optional
try:
    from thoth.discovery.browser.browser_manager import (
        BrowserManager,
        BrowserManagerError,
    )
    from thoth.discovery.browser.extraction_service import (
        ExtractionService,
        ExtractionServiceError,
    )
    from thoth.discovery.browser.workflow_execution_service import (
        WorkflowExecutionOutput,
        WorkflowExecutionService,
        WorkflowExecutionServiceError,
        WorkflowExecutionStats,
    )

    BROWSER_AVAILABLE = True
except ImportError as e:
    # Browser dependencies not available - create placeholder classes
    import warnings

    warnings.warn(
        f'Browser automation dependencies not available: {e}. '
        'Browser-based discovery features will be disabled. '
        'Install with: pip install playwright && playwright install chromium',
        ImportWarning,
    )

    BROWSER_AVAILABLE = False

    # Create placeholder exception classes
    class BrowserManagerError(Exception):
        """Placeholder for missing browser manager."""

        pass

    class ExtractionServiceError(Exception):
        """Placeholder for missing extraction service."""

        pass

    class WorkflowExecutionServiceError(Exception):
        """Placeholder for missing workflow execution service."""

        pass

    # Create placeholder classes that raise helpful errors
    class BrowserManager:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                'Browser automation not available. Install playwright: '
                'pip install playwright && playwright install chromium'
            )

    class ExtractionService:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                'Browser automation not available. Install playwright: '
                'pip install playwright && playwright install chromium'
            )

    class WorkflowExecutionService:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                'Browser automation not available. Install playwright: '
                'pip install playwright && playwright install chromium'
            )

    # Placeholder data classes
    class WorkflowExecutionOutput:
        pass

    class WorkflowExecutionStats:
        pass


__all__ = [  # noqa: RUF022
    'BrowserManager',
    'BrowserManagerError',
    'ExtractionService',
    'ExtractionServiceError',
    'WorkflowExecutionService',
    'WorkflowExecutionServiceError',
    'WorkflowExecutionOutput',
    'WorkflowExecutionStats',
    'BROWSER_AVAILABLE',
]
