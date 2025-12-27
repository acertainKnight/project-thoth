"""Browser workflow discovery plugin for article discovery via browser automation.

This plugin integrates browser-based workflows as a discovery source, enabling
parameterized searches on websites that require authentication or lack APIs.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from loguru import logger

from thoth.discovery.browser.workflow_execution_service import (
    WorkflowExecutionService,
    WorkflowExecutionServiceError,
)
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas import ResearchQuery, ScrapedArticleMetadata
from thoth.utilities.schemas.browser_workflow import (
    ExecutionParameters,
    ExecutionTrigger,
)

from .base import BaseDiscoveryPlugin


class BrowserWorkflowPluginError(Exception):
    """Exception raised for browser workflow plugin errors."""

    pass


class BrowserWorkflowPlugin(BaseDiscoveryPlugin):
    """
    Discovery plugin for executing browser-based workflows.

    This plugin enables browser automation workflows as a discovery source,
    allowing searches on websites that require:
    - Authentication/login
    - Form submissions
    - JavaScript rendering
    - Dynamic content loading
    - Custom search interfaces

    The plugin integrates with WorkflowExecutionService to:
    1. Load configured browser workflows
    2. Execute workflows with query parameters
    3. Extract article metadata from results
    4. Track execution statistics

    Configuration:
        - workflow_id: UUID of the browser workflow to execute (required)
        - max_articles: Maximum articles to extract (default: 100)
        - timeout: Execution timeout in milliseconds (default: 30000)
        - max_retries: Maximum retry attempts (default: 3)

    Example:
        >>> plugin = BrowserWorkflowPlugin(
        ...     postgres_service=postgres,
        ...     config={'workflow_id': 'uuid-string', 'max_articles': 50}
        ... )
        >>> articles = await plugin.discover(
        ...     query=ResearchQuery(
        ...         name='ML Research',
        ...         keywords=['machine learning', 'neural networks'],
        ...         research_question='What are recent advances in ML?'
        ...     ),
        ...     max_results=50
        ... )
    """

    def __init__(
        self,
        postgres_service: PostgresService,
        config: dict | None = None,
    ) -> None:
        """
        Initialize the browser workflow plugin.

        Args:
            postgres_service: PostgreSQL service for database operations
            config: Plugin configuration containing workflow_id and optional settings
        """
        super().__init__(config)

        self.postgres = postgres_service
        self.execution_service = WorkflowExecutionService(
            postgres_service=postgres_service,
            max_concurrent_browsers=self.config.get('max_concurrent_browsers', 5),
            default_timeout=self.config.get('timeout', 30000),
            max_retries=self.config.get('max_retries', 3),
        )

        self._initialized = False
        self.logger.info('BrowserWorkflowPlugin created')

    async def initialize(self) -> None:
        """
        Initialize the plugin and workflow execution service.

        Must be called before discovering articles.

        Raises:
            BrowserWorkflowPluginError: If initialization fails
        """
        if self._initialized:
            return

        try:
            await self.execution_service.initialize()
            self._initialized = True
            self.logger.info('BrowserWorkflowPlugin initialized successfully')

        except Exception as e:
            self.logger.error(f'Failed to initialize plugin: {e}')
            raise BrowserWorkflowPluginError(f'Initialization failed: {e}') from e

    async def shutdown(self) -> None:
        """Shutdown the plugin and cleanup resources."""
        try:
            await self.execution_service.shutdown()
            self._initialized = False
            self.logger.info('BrowserWorkflowPlugin shut down successfully')

        except Exception as e:
            self.logger.warning(f'Error during shutdown: {e}')

    def discover(
        self, query: ResearchQuery, max_results: int
    ) -> list[ScrapedArticleMetadata]:
        """
        Synchronous discover method (required by BaseDiscoveryPlugin).

        This is a wrapper that raises an error since browser workflows
        require async execution. Use discover_async() instead.

        Args:
            query: Research query with keywords and filters
            max_results: Maximum number of articles to return

        Raises:
            BrowserWorkflowPluginError: Always raises - use discover_async()
        """
        raise BrowserWorkflowPluginError(
            'Browser workflow plugin requires async execution. '
            'Use discover_async() instead of discover().'
        )

    async def discover_async(
        self,
        query: ResearchQuery,
        max_results: int,
        query_id: UUID | None = None,
    ) -> list[ScrapedArticleMetadata]:
        """
        Discover articles by executing browser workflow with query parameters.

        This method:
        1. Validates plugin is initialized and configured
        2. Extracts workflow_id from config
        3. Builds execution parameters from query
        4. Executes workflow via WorkflowExecutionService
        5. Returns extracted article metadata
        6. Logs errors but continues on failures

        Args:
            query: Research query containing keywords, topics, and filters
            max_results: Maximum number of articles to extract
            query_id: Optional UUID linking execution to research question

        Returns:
            List of ScrapedArticleMetadata from workflow execution

        Raises:
            BrowserWorkflowPluginError: If plugin not initialized or misconfigured
        """
        if not self._initialized:
            raise BrowserWorkflowPluginError(
                'Plugin not initialized. Call initialize() first.'
            )

        # Validate workflow_id in config
        workflow_id_str = self.config.get('workflow_id')
        if not workflow_id_str:
            raise BrowserWorkflowPluginError(
                'workflow_id must be provided in plugin config'
            )

        try:
            workflow_id = UUID(workflow_id_str)
        except (ValueError, TypeError) as e:
            raise BrowserWorkflowPluginError(
                f'Invalid workflow_id format: {workflow_id_str}'
            ) from e

        # Build execution parameters from query
        parameters = self._build_execution_parameters(query)

        # Log execution start
        self.logger.info(
            f'Starting workflow execution: {workflow_id} '
            f'(keywords={parameters.keywords}, max_results={max_results})'
        )

        try:
            # Execute workflow
            result = await self.execution_service.execute_workflow(
                workflow_id=workflow_id,
                parameters=parameters,
                trigger=ExecutionTrigger.QUERY,
                query_id=query_id,
                max_articles=max_results,
            )

            # Log results
            stats = result.stats
            self.logger.info(
                f'Workflow execution completed: {workflow_id} '
                f'(success={stats.success}, articles={len(result.articles)}, '
                f'duration={stats.duration_ms}ms)'
            )

            if not stats.success:
                self.logger.warning(
                    f'Workflow execution failed: {stats.error_message or "Unknown error"}'
                )

            # Return articles (may be empty if workflow failed)
            return result.articles

        except WorkflowExecutionServiceError as e:
            # Log error but don't raise - continue discovery from other sources
            self.logger.error(
                f'Workflow execution service error for {workflow_id}: {e}'
            )
            return []

        except Exception as e:
            # Catch unexpected errors to prevent blocking other discovery sources
            self.logger.error(
                f'Unexpected error executing workflow {workflow_id}: {e}',
                exc_info=True,
            )
            return []

    def _build_execution_parameters(
        self, query: ResearchQuery
    ) -> ExecutionParameters:
        """
        Build ExecutionParameters from ResearchQuery.

        Converts ResearchQuery fields to ExecutionParameters format:
        - keywords: Combined from query.keywords and query.required_topics
        - date_range: Extracted from query.publication_date_range
        - custom_filters: Built from query preferences and exclusions

        Args:
            query: Research query to convert

        Returns:
            ExecutionParameters suitable for workflow execution
        """
        # Combine keywords and required topics
        keywords = list(query.keywords or [])
        if query.required_topics:
            keywords.extend(query.required_topics)

        # Convert publication date range to simple string format
        date_range = None
        if query.publication_date_range:
            # Try to infer common date ranges
            start = query.publication_date_range.get('start')
            end = query.publication_date_range.get('end')
            if start and end:
                # Could implement smart date range detection here
                date_range = 'custom'

        # Build custom filters from query preferences
        custom_filters = {}

        if query.preferred_topics:
            custom_filters['preferred_topics'] = query.preferred_topics

        if query.excluded_topics:
            custom_filters['excluded_topics'] = query.excluded_topics

        if query.methodology_preferences:
            custom_filters['methodology'] = query.methodology_preferences

        # Include research question as context
        if query.research_question:
            custom_filters['research_question'] = query.research_question

        return ExecutionParameters(
            keywords=keywords if keywords else None,
            date_range=date_range,
            custom_filters=custom_filters if custom_filters else None,
        )

    def validate_config(self, config: dict) -> bool:
        """
        Validate plugin configuration.

        Checks that required workflow_id is present and valid UUID format.

        Args:
            config: Configuration dictionary to validate

        Returns:
            True if configuration is valid, False otherwise
        """
        if not config:
            self.logger.error('Config cannot be empty')
            return False

        workflow_id = config.get('workflow_id')
        if not workflow_id:
            self.logger.error('workflow_id is required in config')
            return False

        try:
            UUID(workflow_id)
        except (ValueError, TypeError) as e:
            self.logger.error(f'Invalid workflow_id format: {workflow_id} - {e}')
            return False

        return True

    def get_name(self) -> str:
        """Return the plugin's unique name."""
        return 'browser_workflow'

    @property
    def is_initialized(self) -> bool:
        """Check if plugin is initialized and ready."""
        return self._initialized
