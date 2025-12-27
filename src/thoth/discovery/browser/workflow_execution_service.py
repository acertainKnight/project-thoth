"""
High-level Workflow Execution Service for browser-based article discovery.

This module provides a simple, unified interface for executing browser workflows
by coordinating the BrowserManager, WorkflowEngine, and ExtractionService.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from loguru import logger

from thoth.discovery.browser.browser_manager import BrowserManager
from thoth.discovery.browser.extraction_service import ExtractionService
from thoth.discovery.browser.workflow_engine import WorkflowEngine, WorkflowExecutionResult
from thoth.repositories.browser_workflow_repository import BrowserWorkflowRepository
from thoth.repositories.workflow_actions_repository import WorkflowActionsRepository
from thoth.repositories.workflow_credentials_repository import (
    WorkflowCredentialsRepository,
)
from thoth.repositories.workflow_executions_repository import WorkflowExecutionsRepository
from thoth.repositories.workflow_search_config_repository import (
    WorkflowSearchConfigRepository,
)
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas import ScrapedArticleMetadata
from thoth.utilities.schemas.browser_workflow import (
    ExecutionParameters,
    ExecutionTrigger,
)


class WorkflowExecutionServiceError(Exception):
    """Exception raised for workflow execution service errors."""

    pass


@dataclass
class WorkflowExecutionStats:
    """Statistics from workflow execution."""

    execution_id: UUID
    success: bool
    articles_count: int
    articles_extracted: int
    articles_skipped: int
    articles_errors: int
    duration_ms: int
    pages_visited: int
    error_message: str | None = None


@dataclass
class WorkflowExecutionOutput:
    """Output from workflow execution containing articles and statistics."""

    articles: list[ScrapedArticleMetadata]
    stats: WorkflowExecutionStats
    execution_log: list[dict[str, Any]]


class WorkflowExecutionService:
    """
    High-level service for executing browser-based discovery workflows.

    This service provides a simple interface for workflow execution by:
    1. Initializing all dependencies (BrowserManager, repositories)
    2. Validating workflow parameters
    3. Coordinating WorkflowEngine and ExtractionService
    4. Managing browser lifecycle
    5. Returning extracted articles with execution statistics

    Example:
        >>> service = WorkflowExecutionService(postgres_service)
        >>> await service.initialize()
        >>>
        >>> result = await service.execute_workflow(
        ...     workflow_id=uuid.UUID('...'),
        ...     parameters=ExecutionParameters(
        ...         keywords=['machine learning', 'neural networks'],
        ...         date_range='last_7d'
        ...     )
        ... )
        >>>
        >>> print(f"Extracted {len(result.articles)} articles")
        >>> print(f"Success: {result.stats.success}")
        >>> print(f"Duration: {result.stats.duration_ms}ms")
    """

    def __init__(
        self,
        postgres_service: PostgresService,
        max_concurrent_browsers: int = 5,
        default_timeout: int = 30000,
        max_retries: int = 3,
    ):
        """
        Initialize the WorkflowExecutionService.

        Args:
            postgres_service: PostgreSQL service for database operations
            max_concurrent_browsers: Maximum concurrent browser instances
            default_timeout: Default timeout in milliseconds
            max_retries: Maximum retry attempts for failed actions
        """
        self.postgres = postgres_service

        # Initialize repositories
        self.workflow_repo = BrowserWorkflowRepository(postgres_service)
        self.search_config_repo = WorkflowSearchConfigRepository(postgres_service)
        self.executions_repo = WorkflowExecutionsRepository(postgres_service)
        self.credentials_repo = WorkflowCredentialsRepository(postgres_service)
        self.actions_repo = WorkflowActionsRepository(postgres_service)

        # Browser manager configuration
        self.browser_manager = BrowserManager(
            max_concurrent_browsers=max_concurrent_browsers,
            default_timeout=default_timeout,
        )

        # Workflow engine
        self.workflow_engine: WorkflowEngine | None = None
        self.max_retries = max_retries

        self._initialized = False

        logger.info(
            f'WorkflowExecutionService created '
            f'(max_browsers={max_concurrent_browsers}, timeout={default_timeout}ms, '
            f'retries={max_retries})'
        )

    async def initialize(self) -> None:
        """
        Initialize the service and its dependencies.

        Must be called before executing workflows.

        Raises:
            WorkflowExecutionServiceError: If initialization fails
        """
        if self._initialized:
            logger.debug('Service already initialized')
            return

        try:
            # Initialize browser manager
            await self.browser_manager.initialize()

            # Create workflow engine
            self.workflow_engine = WorkflowEngine(
                browser_manager=self.browser_manager,
                workflow_repo=self.workflow_repo,
                search_config_repo=self.search_config_repo,
                executions_repo=self.executions_repo,
                credentials_repo=self.credentials_repo,
                actions_repo=self.actions_repo,
                max_retries=self.max_retries,
            )

            self._initialized = True
            logger.info('WorkflowExecutionService initialized successfully')

        except Exception as e:
            logger.error(f'Failed to initialize WorkflowExecutionService: {e}')
            raise WorkflowExecutionServiceError(f'Initialization failed: {e}') from e

    async def shutdown(self) -> None:
        """
        Shutdown the service and cleanup resources.

        Should be called when done using the service.
        """
        try:
            await self.browser_manager.shutdown()
            self._initialized = False
            logger.info('WorkflowExecutionService shut down successfully')

        except Exception as e:
            logger.warning(f'Error during shutdown: {e}')

    async def execute_workflow(
        self,
        workflow_id: UUID,
        parameters: ExecutionParameters,
        trigger: ExecutionTrigger = ExecutionTrigger.MANUAL,
        query_id: UUID | None = None,
        max_articles: int = 100,
    ) -> WorkflowExecutionOutput:
        """
        Execute a workflow with given parameters and return extracted articles.

        This is the main entry point for workflow execution. It orchestrates:
        1. Parameter validation
        2. Workflow execution via WorkflowEngine
        3. Article extraction via ExtractionService
        4. Result aggregation and statistics

        Args:
            workflow_id: UUID of the workflow to execute
            parameters: Execution parameters (keywords, filters, date ranges)
            trigger: What triggered this execution (manual, scheduled, query)
            query_id: Optional research question ID if triggered by query
            max_articles: Maximum number of articles to extract (default: 100)

        Returns:
            WorkflowExecutionOutput: Contains extracted articles and execution stats

        Raises:
            WorkflowExecutionServiceError: If execution fails or service not initialized
        """
        if not self._initialized:
            raise WorkflowExecutionServiceError(
                'Service not initialized. Call initialize() first.'
            )

        start_time = datetime.utcnow()

        try:
            # Validate parameters
            self._validate_parameters(parameters)

            logger.info(
                f'Starting workflow execution: {workflow_id} '
                f'(keywords={parameters.keywords}, max_articles={max_articles})'
            )

            # Execute workflow through engine
            workflow_result = await self.workflow_engine.execute_workflow(
                workflow_id=workflow_id,
                parameters=parameters,
                trigger=trigger,
                query_id=query_id,
            )

            # Calculate duration
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Extract articles from workflow result
            articles: list[ScrapedArticleMetadata] = workflow_result.articles

            # Build statistics from workflow result
            stats = WorkflowExecutionStats(
                execution_id=workflow_result.execution_id,
                success=workflow_result.success,
                articles_count=len(articles),
                articles_extracted=workflow_result.articles_extracted,
                articles_skipped=0,
                articles_errors=0,
                duration_ms=workflow_result.duration_ms or duration_ms,
                pages_visited=workflow_result.pages_visited,
                error_message=workflow_result.error_message,
            )

            logger.info(
                f'Workflow execution completed: {workflow_id} '
                f'(success={stats.success}, articles={stats.articles_count}, '
                f'duration={stats.duration_ms}ms)'
            )

            return WorkflowExecutionOutput(
                articles=articles,
                stats=stats,
                execution_log=workflow_result.execution_log or [],
            )

        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            error_message = str(e)

            logger.error(f'Workflow execution failed: {workflow_id} - {error_message}')

            # Return failed result
            stats = WorkflowExecutionStats(
                execution_id=UUID('00000000-0000-0000-0000-000000000000'),
                success=False,
                articles_count=0,
                articles_extracted=0,
                articles_skipped=0,
                articles_errors=0,
                duration_ms=duration_ms,
                pages_visited=0,
                error_message=error_message,
            )

            return WorkflowExecutionOutput(
                articles=[],
                stats=stats,
                execution_log=[
                    {
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': 'execution_failed',
                        'error': error_message,
                    }
                ],
            )

    def _validate_parameters(self, parameters: ExecutionParameters) -> None:
        """
        Validate execution parameters.

        Args:
            parameters: Execution parameters to validate

        Raises:
            WorkflowExecutionServiceError: If parameters are invalid
        """
        # Check if keywords are provided (most common search parameter)
        if not parameters.keywords and not parameters.custom_filters:
            raise WorkflowExecutionServiceError(
                'At least keywords or custom_filters must be provided'
            )

        # Validate keywords if provided
        if parameters.keywords:
            if not isinstance(parameters.keywords, list):
                raise WorkflowExecutionServiceError('Keywords must be a list of strings')

            if not all(isinstance(k, str) for k in parameters.keywords):
                raise WorkflowExecutionServiceError('All keywords must be strings')

            if not parameters.keywords:
                raise WorkflowExecutionServiceError('Keywords list cannot be empty')

        # Validate date range format if provided
        if parameters.date_range:
            valid_ranges = [
                'last_24h',
                'last_7d',
                'last_30d',
                'last_90d',
                'last_year',
                'custom',
            ]
            if parameters.date_range not in valid_ranges:
                logger.warning(
                    f'Unusual date_range value: {parameters.date_range}. '
                    f'Expected one of {valid_ranges}'
                )

    async def get_workflow_info(self, workflow_id: UUID) -> dict[str, Any] | None:
        """
        Get workflow information without executing it.

        Args:
            workflow_id: UUID of the workflow

        Returns:
            Workflow configuration dict or None if not found
        """
        try:
            return await self.workflow_repo.get_by_id(workflow_id)
        except Exception as e:
            logger.error(f'Failed to get workflow info for {workflow_id}: {e}')
            return None

    async def list_active_workflows(self) -> list[dict[str, Any]]:
        """
        List all active workflows.

        Returns:
            List of active workflow configurations
        """
        try:
            return await self.workflow_repo.get_active_workflows()
        except Exception as e:
            logger.error(f'Failed to list active workflows: {e}')
            return []

    @property
    def is_initialized(self) -> bool:
        """Check if service is initialized and ready."""
        return self._initialized
