"""
Workflow Engine for orchestrating browser-based article discovery.

This module executes parameterized browser workflows with search parameter injection,
authentication handling, and robust error recovery.
"""

from __future__ import annotations  # noqa: I001

import asyncio  # noqa: F401
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional  # noqa: F401
from uuid import UUID

from loguru import logger

# Make playwright imports optional to avoid blocking if not installed
if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page
else:
    try:
        from playwright.async_api import BrowserContext, Error as PlaywrightError, Page
    except ImportError:
        # Playwright not installed - create placeholders
        BrowserContext = None  # type: ignore
        Page = None  # type: ignore
        PlaywrightError = Exception  # type: ignore

from thoth.discovery.browser.action_executor import ActionExecutor
from thoth.discovery.browser.browser_manager import BrowserManager, BrowserManagerError  # noqa: F401
from thoth.discovery.browser.extraction_service import ExtractionService
from thoth.repositories.browser_workflow_repository import BrowserWorkflowRepository
from thoth.repositories.workflow_actions_repository import WorkflowActionsRepository
from thoth.repositories.workflow_credentials_repository import (
    WorkflowCredentialsRepository,
)
from thoth.repositories.workflow_executions_repository import (
    WorkflowExecutionsRepository,
)
from thoth.repositories.workflow_search_config_repository import (
    WorkflowSearchConfigRepository,
)
from thoth.utilities.schemas.browser_workflow import (
    ActionType,
    ElementSelector,
    ExecutionParameters,
    ExecutionStatus,
    ExecutionTrigger,
    KeywordsFormat,
    SelectorStrategy,
    WaitCondition,  # noqa: F401
)


class WorkflowEngineError(Exception):
    """Exception raised for workflow engine errors."""

    pass


class WorkflowExecutionResult:
    """Result of a workflow execution."""

    def __init__(
        self,
        success: bool,
        execution_id: UUID,
        articles_extracted: int = 0,
        pages_visited: int = 0,
        duration_ms: int = 0,
        error_message: str | None = None,
        error_step: int | None = None,
        execution_log: list[dict[str, Any]] | None = None,
        articles: list[Any] | None = None,
    ):
        """Initialize execution result."""
        self.success = success
        self.execution_id = execution_id
        self.articles_extracted = articles_extracted
        self.pages_visited = pages_visited
        self.duration_ms = duration_ms
        self.error_message = error_message
        self.error_step = error_step
        self.execution_log = execution_log or []
        self.articles = articles or []

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            'success': self.success,
            'execution_id': str(self.execution_id),
            'articles_extracted': self.articles_extracted,
            'pages_visited': self.pages_visited,
            'duration_ms': self.duration_ms,
            'error_message': self.error_message,
            'error_step': self.error_step,
            'execution_log': self.execution_log,
        }


class WorkflowEngine:
    """
    Orchestrates browser workflow execution with parameter injection.

    This engine:
    - Loads workflows from database
    - Manages browser sessions with authentication
    - Injects search parameters dynamically
    - Executes workflow actions with retry logic
    - Extracts article data
    - Tracks execution statistics

    Example:
        >>> engine = WorkflowEngine(browser_manager, workflow_repo, ...)
        >>> params = ExecutionParameters(
        ...     keywords=['neural', 'pathways'], date_range='last_24h'
        ... )
        >>> result = await engine.execute_workflow(workflow_id, params)
    """

    def __init__(
        self,
        browser_manager: BrowserManager,
        workflow_repo: BrowserWorkflowRepository,
        search_config_repo: WorkflowSearchConfigRepository,
        executions_repo: WorkflowExecutionsRepository,
        credentials_repo: WorkflowCredentialsRepository,
        actions_repo: WorkflowActionsRepository,
        max_retries: int = 3,
    ):
        """
        Initialize the workflow engine.

        Args:
            browser_manager: Browser lifecycle manager
            workflow_repo: Repository for browser workflows
            search_config_repo: Repository for search configurations
            executions_repo: Repository for execution tracking
            credentials_repo: Repository for encrypted credentials
            actions_repo: Repository for workflow action steps
            max_retries: Maximum retry attempts for failed actions
        """
        self.browser_manager = browser_manager
        self.workflow_repo = workflow_repo
        self.search_config_repo = search_config_repo
        self.executions_repo = executions_repo
        self.credentials_repo = credentials_repo
        self.actions_repo = actions_repo
        self.max_retries = max_retries

        logger.info(f'WorkflowEngine initialized (max_retries={max_retries})')

    async def execute_workflow(
        self,
        workflow_id: UUID,
        parameters: ExecutionParameters,
        trigger: ExecutionTrigger = ExecutionTrigger.MANUAL,
        query_id: UUID | None = None,
    ) -> WorkflowExecutionResult:
        """
        Execute a workflow with injected parameters.

        This is the main entry point for workflow execution. It orchestrates:
        1. Loading workflow configuration
        2. Creating browser session
        3. Authenticating if required
        4. Injecting search parameters
        5. Executing workflow actions
        6. Extracting results
        7. Tracking execution statistics

        Args:
            workflow_id: UUID of the workflow to execute
            parameters: Execution parameters (keywords, filters, etc.)
            trigger: What triggered this execution
            query_id: Optional research question ID if triggered by query

        Returns:
            WorkflowExecutionResult: Execution result with extracted data

        Raises:
            WorkflowEngineError: If workflow execution fails critically
        """
        start_time = datetime.utcnow()
        context: BrowserContext | None = None
        page: Page | None = None
        execution_log: list[dict[str, Any]] = []

        # Create execution record
        execution_id = await self.executions_repo.create(
            {
                'workflow_id': workflow_id,
                'status': ExecutionStatus.RUNNING.value,
                'started_at': start_time,
                'execution_parameters': parameters.model_dump(),
                'triggered_by': trigger.value,
                'triggered_by_query_id': query_id,
            }
        )

        if not execution_id:
            raise WorkflowEngineError('Failed to create execution record')

        try:
            # 1. Load workflow configuration
            workflow = await self.workflow_repo.get_by_id(workflow_id)
            if not workflow:
                raise WorkflowEngineError(f'Workflow not found: {workflow_id}')

            if not workflow.get('is_active'):
                raise WorkflowEngineError(f'Workflow is inactive: {workflow_id}')

            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'workflow_loaded',
                    'workflow_name': workflow.get('name'),
                }
            )

            # 2. Load search configuration
            search_config = await self.search_config_repo.get_by_workflow_id(
                workflow_id
            )
            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'search_config_loaded',
                    'has_config': search_config is not None,
                }
            )

            # 3. Initialize browser context
            context = await self.browser_manager.get_browser(
                headless=True,
                viewport={'width': 1920, 'height': 1080},
            )
            page = await context.new_page()

            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'browser_initialized',
                }
            )

            # 4. Navigate to start URL
            start_url = workflow.get('start_url')
            await page.goto(start_url, wait_until='domcontentloaded')
            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'navigated',
                    'url': start_url,
                }
            )

            # 5. Handle authentication if required
            if workflow.get('requires_authentication'):
                await self._authenticate(page, workflow, execution_log)

            # 6. Inject search parameters
            if search_config:
                await self._inject_search_parameters(
                    page, search_config, parameters, execution_log
                )

            # 7. Execute workflow actions if defined
            await self._execute_workflow_actions(
                page, workflow_id, parameters, execution_log
            )

            # 8. Extract articles
            articles = await self._extract_articles(
                page, workflow, parameters, execution_log
            )

            # 9. Calculate duration and mark success
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            await self.executions_repo.update_status(
                execution_id, ExecutionStatus.SUCCESS.value
            )

            # Update workflow statistics
            await self.workflow_repo.update_statistics(
                workflow_id,
                success=True,
                articles_found=len(articles),
                duration_ms=duration_ms,
            )

            logger.info(
                f'Workflow execution completed: {workflow_id} '
                f'(articles={len(articles)}, duration={duration_ms}ms)'
            )

            return WorkflowExecutionResult(
                success=True,
                execution_id=execution_id,
                articles_extracted=len(articles),
                pages_visited=1,
                duration_ms=duration_ms,
                execution_log=execution_log,
                articles=articles,
            )

        except Exception as e:
            # Calculate duration
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            error_message = str(e)
            logger.error(f'Workflow execution failed: {workflow_id} - {error_message}')

            # Update execution status
            await self.executions_repo.update_status(
                execution_id, ExecutionStatus.FAILED.value, error_message=error_message
            )

            # Update workflow statistics
            await self.workflow_repo.update_statistics(
                workflow_id, success=False, articles_found=0, duration_ms=duration_ms
            )

            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'error',
                    'error': error_message,
                }
            )

            return WorkflowExecutionResult(
                success=False,
                execution_id=execution_id,
                articles_extracted=0,
                pages_visited=1,
                duration_ms=duration_ms,
                error_message=error_message,
                execution_log=execution_log,
            )

        finally:
            # Always cleanup browser resources
            if context:
                await self.browser_manager.cleanup(context)

    async def _authenticate(
        self,
        page: Page,
        workflow: dict[str, Any],
        execution_log: list[dict[str, Any]],
    ) -> None:
        """
        Handle authentication if required.

        Args:
            page: Browser page
            workflow: Workflow configuration
            execution_log: Execution log to append to

        Raises:
            WorkflowEngineError: If authentication fails
        """
        workflow_id = workflow['id']
        auth_type = workflow.get('authentication_type', 'form')  # noqa: F841

        # Get credentials from repository
        creds_data = await self.credentials_repo.get_by_workflow_id(workflow_id)
        if not creds_data:
            raise WorkflowEngineError(
                f'Authentication required but no credentials found for workflow {workflow_id}'
            )

        credentials = creds_data['credentials']
        stored_auth_type = creds_data['credential_type']

        logger.info(f'Authenticating with type: {stored_auth_type}')

        try:
            if stored_auth_type == 'form':
                # Form-based authentication (most common)
                await self._authenticate_form(page, credentials, execution_log)
            elif stored_auth_type == 'basic_auth':
                # HTTP Basic Authentication
                await self._authenticate_basic(page, credentials, execution_log)
            elif stored_auth_type == 'api_key':
                # API key in headers or URL
                await self._authenticate_api_key(page, credentials, execution_log)
            else:
                raise WorkflowEngineError(
                    f'Unsupported authentication type: {stored_auth_type}'
                )

            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'authentication_success',
                    'auth_type': stored_auth_type,
                }
            )

            logger.info(f'Authentication successful for workflow {workflow_id}')

        except Exception as e:
            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'authentication_failed',
                    'auth_type': stored_auth_type,
                    'error': str(e),
                }
            )
            raise WorkflowEngineError(f'Authentication failed: {e}') from e

    async def _authenticate_form(
        self,
        page: Page,
        credentials: dict[str, str],
        execution_log: list[dict[str, Any]],
    ) -> None:
        """Perform form-based authentication."""
        username = credentials.get('username')
        password = credentials.get('password')
        username_selector = credentials.get(
            'username_selector', 'input[name="username"], input[type="email"]'
        )
        password_selector = credentials.get(
            'password_selector', 'input[name="password"], input[type="password"]'
        )
        submit_selector = credentials.get(
            'submit_selector', 'button[type="submit"], input[type="submit"]'
        )

        if not username or not password:
            raise WorkflowEngineError(
                'Username and password required for form authentication'
            )

        # Fill username
        username_input = await page.wait_for_selector(username_selector, timeout=10000)
        await username_input.fill(username)

        # Fill password
        password_input = await page.wait_for_selector(password_selector, timeout=10000)
        await password_input.fill(password)

        # Submit form
        submit_button = await page.wait_for_selector(submit_selector, timeout=10000)
        await submit_button.click()

        # Wait for navigation to complete
        await page.wait_for_load_state('networkidle', timeout=30000)

        execution_log.append(
            {
                'timestamp': datetime.utcnow().isoformat(),
                'action': 'form_authentication_completed',
            }
        )

    async def _authenticate_basic(
        self,
        page: Page,
        credentials: dict[str, str],
        execution_log: list[dict[str, Any]],
    ) -> None:
        """Perform HTTP Basic Authentication."""
        username = credentials.get('username')
        password = credentials.get('password')

        if not username or not password:
            raise WorkflowEngineError(
                'Username and password required for basic authentication'
            )

        # Set authentication header
        await page.context.set_extra_http_headers(
            {'Authorization': f'Basic {username}:{password}'}
        )

        execution_log.append(
            {
                'timestamp': datetime.utcnow().isoformat(),
                'action': 'basic_auth_header_set',
            }
        )

    async def _authenticate_api_key(
        self,
        page: Page,
        credentials: dict[str, str],
        execution_log: list[dict[str, Any]],
    ) -> None:
        """Perform API key authentication."""
        api_key = credentials.get('api_key')
        header_name = credentials.get('header_name', 'X-API-Key')

        if not api_key:
            raise WorkflowEngineError('API key required for API key authentication')

        # Set API key header
        await page.context.set_extra_http_headers({header_name: api_key})

        execution_log.append(
            {
                'timestamp': datetime.utcnow().isoformat(),
                'action': 'api_key_header_set',
                'header_name': header_name,
            }
        )

    async def _inject_search_parameters(
        self,
        page: Page,
        search_config: dict[str, Any],
        parameters: ExecutionParameters,
        execution_log: list[dict[str, Any]],
    ) -> None:
        """
        Inject search parameters into the page.

        Args:
            page: Browser page
            search_config: Search configuration
            parameters: Execution parameters to inject
            execution_log: Execution log to append to

        Raises:
            WorkflowEngineError: If parameter injection fails
        """
        try:
            # Format keywords according to configuration
            if parameters.keywords:
                keywords_format = search_config.get(
                    'keywords_format', 'space_separated'
                )
                formatted_keywords = self._format_keywords(
                    parameters.keywords, keywords_format
                )

                # Find and fill search input
                search_input_selector = search_config.get('search_input_selector')
                if search_input_selector:
                    element = await self._find_element(page, search_input_selector)
                    if element:
                        await element.fill(formatted_keywords)
                        execution_log.append(
                            {
                                'timestamp': datetime.utcnow().isoformat(),
                                'action': 'keywords_injected',
                                'keywords': formatted_keywords,
                            }
                        )

            # Apply filters
            filters = search_config.get('filters', [])
            for filter_config in filters:
                filter_name = filter_config.get('name')  # noqa: F841
                parameter_name = filter_config.get('parameter_name')

                # Get value from parameters
                value = None
                if parameter_name == 'date_range':
                    value = parameters.date_range
                elif parameter_name == 'subject':
                    value = parameters.subject
                else:
                    value = parameters.custom_filters.get(parameter_name)

                # Skip if no value and filter is optional
                if not value and filter_config.get('optional'):
                    continue

                # Apply filter value
                if value:
                    await self._apply_filter(page, filter_config, value, execution_log)

            # Click search button if configured
            search_button_selector = search_config.get('search_button_selector')
            if search_button_selector:
                element = await self._find_element(page, search_button_selector)
                if element:
                    await element.click()
                    # Wait for results to load
                    await page.wait_for_load_state('networkidle', timeout=30000)
                    execution_log.append(
                        {
                            'timestamp': datetime.utcnow().isoformat(),
                            'action': 'search_submitted',
                        }
                    )

        except Exception as e:
            raise WorkflowEngineError(f'Failed to inject search parameters: {e}') from e

    async def _execute_workflow_actions(
        self,
        page: Page,
        workflow_id: UUID,
        parameters: ExecutionParameters,
        execution_log: list[dict[str, Any]],
    ) -> None:
        """
        Execute recorded workflow actions using ActionExecutor.

        Loads workflow_actions from database and executes them in step_number order.
        Supports parameter substitution for dynamic values.

        Args:
            page: Browser page
            workflow_id: UUID of the workflow
            parameters: Execution parameters for substitution
            execution_log: Execution log to append to

        Raises:
            WorkflowEngineError: If action execution fails
        """
        try:
            # Load workflow actions ordered by step_number
            actions_data = await self.actions_repo.get_by_workflow_id(workflow_id)

            if not actions_data or len(actions_data) == 0:
                logger.debug(f'No workflow actions defined for workflow {workflow_id}')
                execution_log.append(
                    {
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': 'workflow_actions_skipped',
                        'reason': 'no_actions_defined',
                    }
                )
                return

            logger.info(
                f'Executing {len(actions_data)} workflow actions for workflow {workflow_id}'
            )

            # Initialize ActionExecutor with page and retry settings
            action_executor = ActionExecutor(
                page=page,
                default_timeout=30000,
                max_retries=self.max_retries,
            )

            # Build parameter dict for substitution
            param_dict = {}
            if parameters.keywords:
                param_dict['keywords'] = ' '.join(parameters.keywords)
                param_dict['keyword'] = (
                    parameters.keywords[0] if parameters.keywords else ''
                )
            if parameters.date_range:
                param_dict['date_range'] = parameters.date_range
            if parameters.subject:
                param_dict['subject'] = parameters.subject
            if parameters.custom_filters:
                param_dict.update(parameters.custom_filters)

            # Execute each action in sequence
            for action_data in actions_data:
                step_num = action_data.get('step_number', 0)
                action_type = action_data.get('action_type', 'unknown')

                logger.info(f'Executing action step {step_num}: {action_type}')

                try:
                    # Convert action_data to WorkflowAction schema
                    from thoth.utilities.schemas.browser_workflow import WorkflowAction

                    workflow_action = WorkflowAction(
                        action_type=ActionType(action_type),
                        selector=action_data.get('selector'),
                        value=action_data.get('action_config', {}).get('value'),
                        timeout=action_data.get('action_config', {}).get('timeout'),
                        wait_condition=action_data.get('action_config', {}).get(
                            'wait_condition'
                        ),
                    )

                    # Execute action with parameter substitution
                    result = await action_executor.execute_action(
                        action=workflow_action,
                        parameters=param_dict,
                    )

                    if result.success:
                        execution_log.append(
                            {
                                'timestamp': datetime.utcnow().isoformat(),
                                'action': 'workflow_action_executed',
                                'step_number': step_num,
                                'action_type': action_type,
                                'success': True,
                            }
                        )
                        logger.info(f'Action step {step_num} completed successfully')
                    else:
                        execution_log.append(
                            {
                                'timestamp': datetime.utcnow().isoformat(),
                                'action': 'workflow_action_failed',
                                'step_number': step_num,
                                'action_type': action_type,
                                'error': result.error,
                            }
                        )
                        logger.warning(f'Action step {step_num} failed: {result.error}')
                        # Continue execution unless it's a critical failure
                        if action_data.get('is_required', True):
                            raise WorkflowEngineError(
                                f'Required action step {step_num} failed: {result.error}'
                            )

                except Exception as e:
                    logger.error(f'Error executing action step {step_num}: {e}')
                    execution_log.append(
                        {
                            'timestamp': datetime.utcnow().isoformat(),
                            'action': 'workflow_action_error',
                            'step_number': step_num,
                            'error': str(e),
                        }
                    )
                    # Re-raise if it's a required action
                    if action_data.get('is_required', True):
                        raise

            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'workflow_actions_completed',
                    'total_actions': len(actions_data),
                }
            )

            logger.info(f'Completed execution of {len(actions_data)} workflow actions')

        except Exception as e:
            logger.error(f'Workflow actions execution failed: {e}')
            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'workflow_actions_failed',
                    'error': str(e),
                }
            )
            raise WorkflowEngineError(f'Workflow actions execution failed: {e}') from e

    async def _extract_articles(
        self,
        page: Page,
        workflow: dict[str, Any],
        parameters: ExecutionParameters,
        execution_log: list[dict[str, Any]],
    ) -> list[Any]:
        """
        Extract articles from the page using ExtractionService.

        Args:
            page: Browser page
            workflow: Workflow configuration
            parameters: Execution parameters
            execution_log: Execution log to append to

        Returns:
            List of extracted article metadata objects
        """
        try:
            extraction_rules = workflow.get('extraction_rules', {})
            if not extraction_rules:
                logger.warning(
                    f'No extraction rules defined for workflow {workflow["id"]}'
                )
                execution_log.append(
                    {
                        'timestamp': datetime.utcnow().isoformat(),
                        'action': 'extraction_skipped',
                        'reason': 'no_extraction_rules',
                    }
                )
                return []

            max_articles = parameters.custom_filters.get(
                'max_articles', workflow.get('max_articles_per_run', 100)
            )

            # Load existing DOIs and titles for incremental discovery
            existing_dois: set[str] = set()
            existing_titles: set[str] = set()
            try:
                # Query previously discovered articles for this workflow
                query = """
                    SELECT DISTINCT doi, title
                    FROM discovered_articles
                    WHERE source = $1 AND (doi IS NOT NULL OR title IS NOT NULL)
                    ORDER BY discovered_at DESC
                    LIMIT 5000
                """
                rows = await self.executions_repo.postgres.fetch(
                    query, workflow.get('name', 'browser_workflow'),
                )
                for row in rows:
                    if row.get('doi'):
                        existing_dois.add(row['doi'])
                    if row.get('title'):
                        normalized = ExtractionService._normalize_title(row['title'])
                        existing_titles.add(normalized)
                logger.info(
                    f'Loaded {len(existing_dois)} DOIs and {len(existing_titles)} '
                    f'titles for incremental discovery'
                )
            except Exception as e:
                logger.debug(
                    f'Could not load existing articles for dedup (table may not exist): {e}'
                )

            # Initialize extraction service with incremental stop-on-known
            extraction_service = ExtractionService(
                page=page,
                source_name=workflow.get('name', 'browser_workflow'),
                existing_dois=existing_dois,
                existing_titles=existing_titles,
                stop_on_known=True,
            )

            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'extraction_started',
                    'max_articles': max_articles,
                }
            )

            # Extract articles
            articles = await extraction_service.extract_articles(
                extraction_rules=extraction_rules,
                max_articles=max_articles,
            )

            # Get extraction statistics
            stats = extraction_service.extraction_stats

            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'extraction_completed',
                    'articles_extracted': stats['extracted'],
                    'articles_skipped': stats['skipped'],
                    'articles_errors': stats['errors'],
                }
            )

            logger.info(
                f'Extracted {len(articles)} articles for workflow {workflow["id"]} '
                f'(extracted={stats["extracted"]}, skipped={stats["skipped"]}, errors={stats["errors"]})'
            )

            return articles

        except Exception as e:
            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'extraction_failed',
                    'error': str(e),
                }
            )
            logger.error(f'Article extraction failed: {e}')
            raise WorkflowEngineError(f'Article extraction failed: {e}') from e

    async def _find_element(
        self,
        page: Page,
        selector_config: dict[str, Any] | ElementSelector,
    ) -> Any:
        """
        Find an element using multi-strategy selector.

        Tries selectors in priority order until one succeeds.

        Args:
            page: Browser page
            selector_config: Element selector configuration

        Returns:
            Found element or None

        Raises:
            WorkflowEngineError: If element cannot be found
        """
        # Convert dict to ElementSelector if needed
        if isinstance(selector_config, dict):
            selector = ElementSelector(**selector_config)
        else:
            selector = selector_config

        priority = selector.priority or [
            SelectorStrategy.CSS,
            SelectorStrategy.XPATH,
            SelectorStrategy.TEXT,
        ]

        for strategy in priority:
            try:
                if strategy == SelectorStrategy.CSS and selector.css:
                    return await page.wait_for_selector(selector.css, timeout=5000)
                elif strategy == SelectorStrategy.XPATH and selector.xpath:
                    return await page.wait_for_selector(
                        f'xpath={selector.xpath}', timeout=5000
                    )
                elif strategy == SelectorStrategy.TEXT and selector.text:
                    return await page.get_by_text(selector.text).first
                elif strategy == SelectorStrategy.ID and selector.id:
                    return await page.wait_for_selector(f'#{selector.id}', timeout=5000)
                elif strategy == SelectorStrategy.CLASS and selector.class_name:
                    return await page.wait_for_selector(
                        f'.{selector.class_name}', timeout=5000
                    )
            except PlaywrightError:
                continue

        raise WorkflowEngineError(
            f'Could not find element: {selector.description or "unknown"}'
        )

    async def _apply_filter(
        self,
        page: Page,
        filter_config: dict[str, Any],
        value: str,
        execution_log: list[dict[str, Any]],
    ) -> None:
        """
        Apply a filter value to a filter element.

        Args:
            page: Browser page
            filter_config: Filter configuration
            value: Value to apply
            execution_log: Execution log to append to

        Raises:
            WorkflowEngineError: If filter cannot be applied
        """
        try:
            selector = filter_config.get('selector')
            filter_type = filter_config.get('filter_type')
            filter_name = filter_config.get('name')

            element = await self._find_element(page, selector)

            if filter_type == 'dropdown':
                # Select dropdown option
                await element.select_option(value)
            elif filter_type in ('text_input', 'date_input'):
                # Fill text/date input
                await element.fill(value)
            elif filter_type == 'checkbox':
                # Check/uncheck checkbox
                if value.lower() in ('true', '1', 'yes'):
                    await element.check()
            elif filter_type == 'radio':
                # Click radio button
                await element.click()

            execution_log.append(
                {
                    'timestamp': datetime.utcnow().isoformat(),
                    'action': 'filter_applied',
                    'filter_name': filter_name,
                    'filter_type': filter_type,
                    'value': value,
                }
            )

        except Exception as e:
            raise WorkflowEngineError(
                f'Failed to apply filter {filter_name}: {e}'
            ) from e

    def _format_keywords(self, keywords: list[str], format_type: str) -> str:
        """
        Format keywords according to the specified format.

        Args:
            keywords: List of keywords
            format_type: Format type (space_separated, comma_separated, etc.)

        Returns:
            Formatted keyword string
        """
        if format_type == KeywordsFormat.SPACE_SEPARATED.value:
            return ' '.join(keywords)
        elif format_type == KeywordsFormat.COMMA_SEPARATED.value:
            return ', '.join(keywords)
        elif format_type == KeywordsFormat.BOOLEAN_AND.value:
            return ' AND '.join(keywords)
        elif format_type == KeywordsFormat.BOOLEAN_OR.value:
            return ' OR '.join(keywords)
        else:
            # Default to space separated
            return ' '.join(keywords)
