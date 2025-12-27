"""
Browser automation module for workflow-based discovery.

This module provides browser automation capabilities using Playwright for
executing user-recorded workflows to discover articles from sources that
require authentication or don't provide public APIs.
"""

from thoth.discovery.browser.browser_manager import BrowserManager, BrowserManagerError
from thoth.discovery.browser.extraction_service import (
    ExtractionService,
    ExtractionServiceError,
)
from thoth.discovery.browser.workflow_execution_service import (
    WorkflowExecutionService,
    WorkflowExecutionServiceError,
    WorkflowExecutionOutput,
    WorkflowExecutionStats,
)

__all__ = [
    'BrowserManager',
    'BrowserManagerError',
    'ExtractionService',
    'ExtractionServiceError',
    'WorkflowExecutionService',
    'WorkflowExecutionServiceError',
    'WorkflowExecutionOutput',
    'WorkflowExecutionStats',
]
