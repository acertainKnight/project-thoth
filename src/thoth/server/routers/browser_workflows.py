"""Browser workflow management API endpoints.

This module provides RESTful API endpoints for managing browser-based discovery workflows,
including CRUD operations, workflow execution, execution history tracking, and
LLM-powered auto-detection of article sources via the WorkflowBuilder.
"""  # noqa: W505

from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from loguru import logger
from pydantic import BaseModel, Field

from thoth.discovery.browser.workflow_builder import WorkflowBuilder
from thoth.discovery.browser.workflow_execution_service import (
    WorkflowExecutionService,
    WorkflowExecutionServiceError,  # noqa: F401
)
from thoth.repositories.browser_workflow_repository import BrowserWorkflowRepository
from thoth.repositories.workflow_actions_repository import WorkflowActionsRepository
from thoth.repositories.workflow_executions_repository import (
    WorkflowExecutionsRepository,
)
from thoth.repositories.workflow_search_config_repository import (
    WorkflowSearchConfigRepository,
)
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas.browser_workflow import (
    BrowserWorkflowCreate,  # noqa: F401
    BrowserWorkflowUpdate,  # noqa: F401
    ExecutionParameters,
    ExecutionStatus,
    ExecutionTrigger,
    WorkflowAction,  # noqa: F401
)

from thoth.server.dependencies import (
    get_postgres_service,
    get_workflow_builder,
    get_workflow_execution_service,
)

router = APIRouter(prefix='/api/workflows', tags=['browser_workflows'])

# REMOVED: Module-level globals - Phase 5
# Dependencies now injected via FastAPI Depends() from dependencies module


# Dependency injection helpers - updated to use central dependencies
async def get_workflow_repo(
    postgres_service: Optional[PostgresService] = Depends(get_postgres_service)
) -> BrowserWorkflowRepository:
    """Get browser workflow repository dependency."""
    if postgres_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database service not initialized',
        )
    return BrowserWorkflowRepository(postgres_service)


async def get_executions_repo(
    postgres_service: Optional[PostgresService] = Depends(get_postgres_service)
) -> WorkflowExecutionsRepository:
    """Get workflow executions repository dependency."""
    if postgres_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database service not initialized',
        )
    return WorkflowExecutionsRepository(postgres_service)


async def get_actions_repo(
    postgres_service: Optional[PostgresService] = Depends(get_postgres_service)
) -> WorkflowActionsRepository:
    """Get workflow actions repository dependency."""
    if postgres_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database service not initialized',
        )
    return WorkflowActionsRepository(postgres_service)


async def get_search_config_repo(
    postgres_service: Optional[PostgresService] = Depends(get_postgres_service)
) -> WorkflowSearchConfigRepository:
    """Get workflow search config repository dependency."""
    if postgres_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Database service not initialized',
        )
    return WorkflowSearchConfigRepository(postgres_service)


async def get_execution_service(
    workflow_execution_service: Optional[WorkflowExecutionService] = Depends(
        get_workflow_execution_service
    )
) -> WorkflowExecutionService:
    """Get workflow execution service dependency."""
    if workflow_execution_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='Workflow execution service not initialized',
        )
    return workflow_execution_service


# Request/Response models
class WorkflowCreateRequest(BaseModel):
    """Request model for creating a new workflow."""

    name: str = Field(..., description='Unique workflow name')
    description: Optional[str] = Field(None, description='Workflow description')  # noqa: UP007
    website_domain: str = Field(..., description='Target website domain')
    start_url: str = Field(..., description='Starting URL for workflow')
    extraction_rules: dict[str, Any] = Field(
        ..., description='Article extraction rules'
    )
    requires_authentication: bool = Field(default=False)
    authentication_type: Optional[str] = Field(default=None)  # noqa: UP007
    pagination_config: Optional[dict[str, Any]] = Field(default=None)  # noqa: UP007
    max_articles_per_run: int = Field(default=100, ge=1)
    timeout_seconds: int = Field(default=60, ge=1)


class WorkflowUpdateRequest(BaseModel):
    """Request model for updating a workflow."""

    name: Optional[str] = Field(None)  # noqa: UP007
    description: Optional[str] = Field(None)  # noqa: UP007
    website_domain: Optional[str] = Field(None)  # noqa: UP007
    start_url: Optional[str] = Field(None)  # noqa: UP007
    extraction_rules: Optional[dict[str, Any]] = Field(None)  # noqa: UP007
    requires_authentication: Optional[bool] = Field(None)  # noqa: UP007
    authentication_type: Optional[str] = Field(None)  # noqa: UP007
    pagination_config: Optional[dict[str, Any]] = Field(None)  # noqa: UP007
    max_articles_per_run: Optional[int] = Field(None, ge=1)  # noqa: UP007
    timeout_seconds: Optional[int] = Field(None, ge=1)  # noqa: UP007
    is_active: Optional[bool] = Field(None)  # noqa: UP007


class WorkflowResponse(BaseModel):
    """Response model for workflow data."""

    id: UUID
    name: str
    description: Optional[str]  # noqa: UP007
    website_domain: str
    start_url: str
    requires_authentication: bool
    extraction_rules: dict[str, Any]
    pagination_config: Optional[dict[str, Any]]  # noqa: UP007
    max_articles_per_run: int
    timeout_seconds: int
    is_active: bool
    health_status: str
    total_executions: int
    successful_executions: int
    failed_executions: int
    total_articles_extracted: int
    average_execution_time_ms: Optional[int]  # noqa: UP007
    last_executed_at: Optional[datetime]  # noqa: UP007
    last_success_at: Optional[datetime]  # noqa: UP007
    last_failure_at: Optional[datetime]  # noqa: UP007
    created_at: datetime
    updated_at: datetime


class WorkflowDetailResponse(WorkflowResponse):
    """Detailed workflow response with search config."""

    search_config: Optional[dict[str, Any]] = Field(None)  # noqa: UP007


class WorkflowExecutionRequest(BaseModel):
    """Request model for executing a workflow."""

    keywords: list[str] = Field(default_factory=list)
    date_range: Optional[str] = Field(None)  # noqa: UP007
    date_from: Optional[str] = Field(None)  # noqa: UP007
    date_to: Optional[str] = Field(None)  # noqa: UP007
    subject: Optional[str] = Field(None)  # noqa: UP007
    custom_filters: dict[str, Any] = Field(default_factory=dict)
    max_articles: Optional[int] = Field(None, ge=1)  # noqa: UP007


class WorkflowExecutionResponse(BaseModel):
    """Response model for workflow execution initiation."""

    execution_id: UUID
    workflow_id: UUID
    status: str
    message: str


class ExecutionHistoryResponse(BaseModel):
    """Response model for execution history."""

    id: UUID
    workflow_id: UUID
    status: str
    started_at: datetime
    completed_at: Optional[datetime]  # noqa: UP007
    duration_ms: Optional[int]  # noqa: UP007
    articles_extracted: int
    pages_visited: int
    error_message: Optional[str]  # noqa: UP007
    execution_parameters: dict[str, Any]
    triggered_by: str


class WorkflowActionRequest(BaseModel):
    """Request model for adding an action to a workflow."""

    step_number: int = Field(..., ge=0)
    action_type: str = Field(...)
    target_selector: Optional[dict[str, Any]] = Field(None)  # noqa: UP007
    target_description: Optional[str] = Field(None)  # noqa: UP007
    action_value: Optional[str] = Field(None)  # noqa: UP007
    is_parameterized: bool = Field(default=False)
    parameter_name: Optional[str] = Field(None)  # noqa: UP007
    wait_condition: Optional[str] = Field(None)  # noqa: UP007
    wait_timeout_ms: int = Field(default=30000, ge=0)
    retry_on_failure: bool = Field(default=True)
    max_retries: int = Field(default=3, ge=0)
    continue_on_error: bool = Field(default=False)


class WorkflowActionResponse(BaseModel):
    """Response model for workflow action."""

    action_id: UUID
    workflow_id: UUID
    message: str


class CreateWorkflowResponse(BaseModel):
    """Response model for workflow creation."""

    workflow_id: UUID


# Endpoints


@router.post('', response_model=CreateWorkflowResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    request: WorkflowCreateRequest,
    repo: BrowserWorkflowRepository = Depends(get_workflow_repo),  # noqa: B008
):
    """Create a new browser workflow.

    Args:
        request: Workflow creation parameters
        repo: Browser workflow repository

    Returns:
        Dictionary with workflow_id

    Raises:
        HTTPException: If creation fails
    """
    try:
        workflow_data = {
            'name': request.name,
            'description': request.description,
            'website_domain': request.website_domain,
            'start_url': request.start_url,
            'extraction_rules': request.extraction_rules,
            'requires_authentication': request.requires_authentication,
            'authentication_type': request.authentication_type,
            'pagination_config': request.pagination_config,
            'max_articles_per_run': request.max_articles_per_run,
            'timeout_seconds': request.timeout_seconds,
            'is_active': True,
            'health_status': 'unknown',
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_articles_extracted': 0,
        }

        workflow_id = await repo.create(workflow_data)

        if workflow_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to create workflow',
            )

        logger.info(f'Created workflow: {workflow_id} ({request.name})')
        return CreateWorkflowResponse(workflow_id=workflow_id)

    except Exception as e:
        logger.error(f'Error creating workflow: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to create workflow: {str(e)}',  # noqa: RUF010
        )


@router.get('', response_model=list[WorkflowResponse])
async def list_workflows(
    is_active: Optional[bool] = Query(None, description='Filter by active status'),  # noqa: UP007
    domain: Optional[str] = Query(None, description='Filter by website domain'),  # noqa: UP007
    repo: BrowserWorkflowRepository = Depends(get_workflow_repo),  # noqa: B008
):
    """List all workflows with optional filters.

    Args:
        is_active: Filter by active status
        domain: Filter by website domain
        repo: Browser workflow repository

    Returns:
        List of workflows
    """
    try:
        if domain:
            workflows = await repo.get_by_domain(domain)
        elif is_active is not None:
            if is_active:
                workflows = await repo.get_active_workflows()
            else:
                # Get all and filter inactive
                query = 'SELECT * FROM browser_workflows'
                all_workflows = await repo.postgres.fetch(query)
                workflows = [dict(w) for w in all_workflows if not w.get('is_active', True)]
        else:
            query = 'SELECT * FROM browser_workflows'
            result = await repo.postgres.fetch(query)
            workflows = [dict(w) for w in result]

        return [WorkflowResponse(**w) for w in workflows]

    except Exception as e:
        logger.error(f'Error listing workflows: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to list workflows: {str(e)}',  # noqa: RUF010
        )


@router.get('/{workflow_id}', response_model=WorkflowDetailResponse)
async def get_workflow(
    workflow_id: UUID,
    workflow_repo: BrowserWorkflowRepository = Depends(get_workflow_repo),  # noqa: B008
    search_repo: WorkflowSearchConfigRepository = Depends(get_search_config_repo),  # noqa: B008
):
    """Get workflow details including search configuration.

    Args:
        workflow_id: Workflow UUID
        workflow_repo: Browser workflow repository
        search_repo: Search config repository

    Returns:
        Workflow details with search config

    Raises:
        HTTPException: If workflow not found
    """
    try:
        workflow = await workflow_repo.get_by_id(workflow_id)

        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Workflow {workflow_id} not found',
            )

        # Get search config
        search_config = await search_repo.get_by_workflow_id(workflow_id)

        response_data = {**workflow, 'search_config': search_config}
        return WorkflowDetailResponse(**response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting workflow {workflow_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to get workflow: {str(e)}',  # noqa: RUF010
        )


@router.put('/{workflow_id}', response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    request: WorkflowUpdateRequest,
    repo: BrowserWorkflowRepository = Depends(get_workflow_repo),  # noqa: B008
):
    """Update a workflow's configuration.

    Args:
        workflow_id: Workflow UUID
        request: Update parameters
        repo: Browser workflow repository

    Returns:
        Updated workflow data

    Raises:
        HTTPException: If workflow not found or update fails
    """
    try:
        # Check if workflow exists
        existing = await repo.get_by_id(workflow_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Workflow {workflow_id} not found',
            )

        # Build updates dict (exclude None values)
        updates = {k: v for k, v in request.model_dump().items() if v is not None}

        if not updates:
            # No updates provided, return existing
            return WorkflowResponse(**existing)

        success = await repo.update(workflow_id, updates)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to update workflow',
            )

        # Fetch updated workflow
        updated = await repo.get_by_id(workflow_id)
        logger.info(f'Updated workflow: {workflow_id}')

        return WorkflowResponse(**updated)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating workflow {workflow_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to update workflow: {str(e)}',  # noqa: RUF010
        )


@router.delete('/{workflow_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: UUID,
    repo: BrowserWorkflowRepository = Depends(get_workflow_repo),  # noqa: B008
):
    """Delete a workflow.

    Args:
        workflow_id: Workflow UUID
        repo: Browser workflow repository

    Raises:
        HTTPException: If workflow not found or deletion fails
    """
    try:
        # Check if workflow exists
        existing = await repo.get_by_id(workflow_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Workflow {workflow_id} not found',
            )

        success = await repo.delete(workflow_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to delete workflow',
            )

        logger.info(f'Deleted workflow: {workflow_id}')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error deleting workflow {workflow_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to delete workflow: {str(e)}',  # noqa: RUF010
        )


async def _execute_workflow_background(
    workflow_id: UUID,
    execution_id: UUID,
    parameters: ExecutionParameters,
    execution_service: WorkflowExecutionService,
    executions_repo: WorkflowExecutionsRepository,
):
    """Background task to execute workflow."""
    try:
        logger.info(f'Starting background execution for workflow {workflow_id}')

        # Execute workflow
        result = await execution_service.execute_workflow(
            workflow_id=workflow_id,
            parameters=parameters,
            trigger=ExecutionTrigger.MANUAL,
        )

        # Update execution status
        if result.stats.success:
            await executions_repo.update_status(
                execution_id,
                ExecutionStatus.SUCCESS.value,  # noqa: F821
            )
            logger.info(
                f'Workflow execution {execution_id} completed successfully: '
                f'{result.stats.articles_count} articles extracted'
            )
        else:
            await executions_repo.update_status(
                execution_id,
                ExecutionStatus.FAILED.value,  # noqa: F821
                error_message=result.stats.error_message,
            )
            logger.error(
                f'Workflow execution {execution_id} failed: {result.stats.error_message}'
            )

    except Exception as e:
        logger.error(
            f'Background execution failed for workflow {workflow_id}: {e}',
            exc_info=True,
        )
        try:
            await executions_repo.update_status(
                execution_id,
                ExecutionStatus.FAILED.value,  # noqa: F821
                error_message=str(e),
            )
        except Exception as update_error:
            logger.error(f'Failed to update execution status: {update_error}')


@router.post('/{workflow_id}/execute', response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: UUID,
    request: WorkflowExecutionRequest,
    background_tasks: BackgroundTasks,
    workflow_repo: BrowserWorkflowRepository = Depends(get_workflow_repo),  # noqa: B008
    executions_repo: WorkflowExecutionsRepository = Depends(get_executions_repo),  # noqa: B008
    execution_service: WorkflowExecutionService = Depends(get_execution_service),  # noqa: B008
):
    """Execute a workflow asynchronously with provided parameters.

    Args:
        workflow_id: Workflow UUID
        request: Execution parameters
        background_tasks: FastAPI background tasks
        workflow_repo: Browser workflow repository
        executions_repo: Workflow executions repository
        execution_service: Workflow execution service

    Returns:
        Execution ID and status

    Raises:
        HTTPException: If workflow not found or execution fails
    """
    try:
        # Verify workflow exists and is active
        workflow = await workflow_repo.get_by_id(workflow_id)
        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Workflow {workflow_id} not found',
            )

        if not workflow.get('is_active', False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Workflow {workflow_id} is not active',
            )

        # Create execution record
        execution_data = {
            'workflow_id': workflow_id,
            'status': ExecutionStatus.RUNNING.value,  # noqa: F821
            'execution_parameters': request.model_dump(),
            'triggered_by': ExecutionTrigger.MANUAL.value,
            'started_at': datetime.utcnow(),
        }

        execution_id = await executions_repo.create(execution_data)

        if execution_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to create execution record',
            )

        logger.info(f'Created execution {execution_id} for workflow {workflow_id}')

        # Convert request to ExecutionParameters
        parameters = ExecutionParameters(
            keywords=request.keywords,
            date_range=request.date_range,
            subject=request.subject,
            custom_filters={
                **request.custom_filters,
                'max_articles': request.max_articles or 100,
            },
        )

        # Queue background execution
        background_tasks.add_task(
            _execute_workflow_background,
            workflow_id,
            execution_id,
            parameters,
            execution_service,
            executions_repo,
        )

        return WorkflowExecutionResponse(
            execution_id=execution_id,
            workflow_id=workflow_id,
            status=ExecutionStatus.RUNNING.value,  # noqa: F821
            message='Workflow execution started in background',
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error starting workflow execution {workflow_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to start workflow execution: {str(e)}',  # noqa: RUF010
        )


@router.get('/{workflow_id}/executions', response_model=list[ExecutionHistoryResponse])
async def get_workflow_executions(
    workflow_id: UUID,
    limit: int = Query(default=10, ge=1, le=100, description='Maximum results'),
    repo: WorkflowExecutionsRepository = Depends(get_executions_repo),  # noqa: B008
):
    """Get execution history for a workflow.

    Args:
        workflow_id: Workflow UUID
        limit: Maximum number of executions to return
        repo: Workflow executions repository

    Returns:
        List of workflow executions
    """
    try:
        executions = await repo.get_by_workflow_id(workflow_id, limit=limit)

        return [ExecutionHistoryResponse(**exec_data) for exec_data in executions]

    except Exception as e:
        logger.error(f'Error getting executions for workflow {workflow_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to get workflow executions: {str(e)}',  # noqa: RUF010
        )


@router.post('/{workflow_id}/actions', response_model=WorkflowActionResponse)
async def add_workflow_action(
    workflow_id: UUID,
    request: WorkflowActionRequest,
    workflow_repo: BrowserWorkflowRepository = Depends(get_workflow_repo),  # noqa: B008
    actions_repo: WorkflowActionsRepository = Depends(get_actions_repo),  # noqa: B008
):
    """Add an action step to a workflow.

    Args:
        workflow_id: Workflow UUID
        request: Action configuration
        workflow_repo: Browser workflow repository
        actions_repo: Workflow actions repository

    Returns:
        Action ID and confirmation

    Raises:
        HTTPException: If workflow not found or action creation fails
    """
    try:
        # Verify workflow exists
        workflow = await workflow_repo.get_by_id(workflow_id)
        if workflow is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Workflow {workflow_id} not found',
            )

        # Create action data
        action_data = {
            'workflow_id': workflow_id,
            **request.model_dump(),
        }

        action_id = await actions_repo.create(action_data)

        if action_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to create workflow action',
            )

        logger.info(f'Created action {action_id} for workflow {workflow_id}')

        return WorkflowActionResponse(
            action_id=action_id,
            workflow_id=workflow_id,
            message='Workflow action created successfully',
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error creating action for workflow {workflow_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to create workflow action: {str(e)}',  # noqa: RUF010
        )


# ---------------------------------------------------------------------------
# LLM-powered Workflow Builder endpoints
# ---------------------------------------------------------------------------


class AnalyzeUrlRequest(BaseModel):
    """Request model for URL analysis via the LLM workflow builder."""

    url: str = Field(..., description='URL to analyze for article extraction')
    include_screenshot: bool = Field(
        default=True, description='Include a base64 screenshot in the response'
    )


class SelectorInfo(BaseModel):
    """Information about a proposed CSS selector."""

    css_selector: str
    attribute: str = 'text'
    is_multiple: bool = False
    confidence: float = 0.0


class SampleArticleResponse(BaseModel):
    """A sample article extracted during analysis."""

    title: str = ''
    authors: list[str] = Field(default_factory=list)
    abstract: str = ''
    url: str = ''
    pdf_url: str = ''
    doi: str = ''
    publication_date: str = ''
    keywords: list[str] = Field(default_factory=list)
    journal: str = ''


class SearchFilterResponse(BaseModel):
    """A detected search or filter UI element."""

    element_type: str = ''
    css_selector: str = ''
    submit_selector: str | None = None
    filter_type: str = 'text_input'
    description: str = ''


class AnalyzeUrlResponse(BaseModel):
    """Response from URL analysis with proposed selectors and sample articles."""

    url: str
    page_title: str
    page_type: str
    article_container_selector: str
    selectors: dict[str, SelectorInfo]
    pagination_selector: str | None = None
    search_filters: list[SearchFilterResponse] = Field(default_factory=list)
    sample_articles: list[SampleArticleResponse]
    total_articles_found: int
    screenshot_base64: str | None = None
    notes: str = ''
    confidence: float = 0.0


class RefineSelectorsRequest(BaseModel):
    """Request to refine selectors based on user feedback."""

    url: str = Field(..., description='The URL being analyzed')
    current_selectors: dict[str, Any] = Field(
        ..., description='Current selector configuration to refine'
    )
    user_feedback: str = Field(
        ..., description="User's description of what's wrong with current results"
    )
    include_screenshot: bool = Field(default=True)


class ConfirmWorkflowRequest(BaseModel):
    """Request to confirm and save an analyzed URL as a workflow."""

    url: str = Field(..., description='The analyzed URL')
    name: str = Field(..., description='Name for the workflow')
    description: str | None = Field(None, description='Optional description')
    article_container_selector: str = Field(..., description='Confirmed container selector')
    selectors: dict[str, SelectorInfo] = Field(..., description='Confirmed field selectors')
    pagination_selector: str | None = Field(None, description='Pagination selector')
    search_filters: list[SearchFilterResponse] = Field(
        default_factory=list, description='Detected search/filter UI elements',
    )
    max_articles_per_run: int = Field(default=100, ge=1)
    requires_authentication: bool = Field(default=False)


@router.post('/analyze', response_model=AnalyzeUrlResponse)
async def analyze_url(
    request: AnalyzeUrlRequest,
    builder: WorkflowBuilder = Depends(get_workflow_builder),  # noqa: B008
):
    """Analyze a URL to auto-detect article listing structure using LLM.

    This endpoint loads the page, extracts DOM structure, sends it to the LLM
    for analysis, tests the proposed selectors, and returns sample results
    for user confirmation.

    Args:
        request: URL and analysis options.
        builder: WorkflowBuilder instance.

    Returns:
        AnalyzeUrlResponse: Proposed selectors and sample articles.
    """
    try:
        result = await builder.analyze_url(
            url=request.url,
            include_screenshot=request.include_screenshot,
        )

        # Convert to response model
        selectors = {
            k: SelectorInfo(**v) for k, v in result.selectors.items()
        }

        sample_articles = []
        for article in result.sample_articles:
            sample_articles.append(SampleArticleResponse(
                title=article.title,
                authors=article.authors if isinstance(article.authors, list) else [],
                abstract=article.abstract,
                url=article.url,
                pdf_url=article.pdf_url,
                doi=article.doi,
                publication_date=article.publication_date,
                keywords=article.keywords if isinstance(article.keywords, list) else [],
                journal=article.journal,
            ))

        search_filters = [
            SearchFilterResponse(**sf) for sf in result.search_filters
        ]

        return AnalyzeUrlResponse(
            url=result.url,
            page_title=result.page_title,
            page_type=result.page_type,
            article_container_selector=result.article_container_selector,
            selectors=selectors,
            pagination_selector=result.pagination_selector,
            search_filters=search_filters,
            sample_articles=sample_articles,
            total_articles_found=result.total_articles_found,
            screenshot_base64=result.screenshot_base64,
            notes=result.notes,
            confidence=result.confidence,
        )

    except Exception as e:
        logger.error(f'Error analyzing URL {request.url}: {e}', exc_info=True)
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to analyze URL: {str(e)}',  # noqa: RUF010
        )


@router.post('/refine', response_model=AnalyzeUrlResponse)
async def refine_selectors(
    request: RefineSelectorsRequest,
    builder: WorkflowBuilder = Depends(get_workflow_builder),  # noqa: B008
):
    """Refine selectors based on user feedback.

    When auto-detection results are wrong, the user can describe what's incorrect
    and this endpoint uses the LLM to propose corrected selectors.

    Args:
        request: Current selectors and user feedback.
        builder: WorkflowBuilder instance.

    Returns:
        AnalyzeUrlResponse: Refined selectors and updated sample articles.
    """
    try:
        result = await builder.refine_selectors(
            url=request.url,
            current_selectors=request.current_selectors,
            user_feedback=request.user_feedback,
            include_screenshot=request.include_screenshot,
        )

        selectors = {
            k: SelectorInfo(**v) for k, v in result.selectors.items()
        }

        sample_articles = []
        for article in result.sample_articles:
            sample_articles.append(SampleArticleResponse(
                title=article.title,
                authors=article.authors if isinstance(article.authors, list) else [],
                abstract=article.abstract,
                url=article.url,
                pdf_url=article.pdf_url,
                doi=article.doi,
                publication_date=article.publication_date,
                keywords=article.keywords if isinstance(article.keywords, list) else [],
                journal=article.journal,
            ))

        search_filters = [
            SearchFilterResponse(**sf) for sf in result.search_filters
        ]

        return AnalyzeUrlResponse(
            url=result.url,
            page_title=result.page_title,
            page_type=result.page_type,
            article_container_selector=result.article_container_selector,
            selectors=selectors,
            pagination_selector=result.pagination_selector,
            search_filters=search_filters,
            sample_articles=sample_articles,
            total_articles_found=result.total_articles_found,
            screenshot_base64=result.screenshot_base64,
            notes=result.notes,
            confidence=result.confidence,
        )

    except Exception as e:
        logger.error(f'Error refining selectors for {request.url}: {e}', exc_info=True)
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to refine selectors: {str(e)}',  # noqa: RUF010
        )


@router.post('/confirm', response_model=CreateWorkflowResponse, status_code=status.HTTP_201_CREATED)
async def confirm_workflow(
    request: ConfirmWorkflowRequest,
    repo: BrowserWorkflowRepository = Depends(get_workflow_repo),  # noqa: B008
):
    """Confirm and save an analyzed URL as a workflow.

    After the user reviews the auto-detected (or refined) selectors and sample
    articles, this endpoint saves the configuration as a persistent workflow
    that can be executed on-demand or on a schedule.

    Args:
        request: Confirmed workflow configuration.
        repo: Browser workflow repository.

    Returns:
        CreateWorkflowResponse: The created workflow ID.
    """
    try:
        parsed = urlparse(request.url)
        domain = parsed.netloc or parsed.hostname or request.url

        # Build extraction rules from confirmed selectors
        extraction_rules = {
            'article_container': request.article_container_selector,
            'fields': {
                name: sel.model_dump() for name, sel in request.selectors.items()
            },
        }

        # Build pagination config
        pagination_config = None
        if request.pagination_selector:
            pagination_config = {
                'type': 'button',
                'selector': request.pagination_selector,
                'next_page_selector': request.pagination_selector,
            }
        extraction_rules['pagination'] = pagination_config

        # Build search_config from detected filters
        search_config: dict[str, Any] | None = None
        if request.search_filters:
            filters = []
            search_input_selector = None
            search_button_selector = None

            for sf in request.search_filters:
                if sf.element_type in ('search_input', 'keyword_input'):
                    search_input_selector = sf.css_selector
                    search_button_selector = sf.submit_selector
                else:
                    # Map element_type to parameter_name
                    param_name = {
                        'date_filter': 'date_range',
                        'subject_filter': 'subject',
                        'sort_dropdown': 'sort_order',
                    }.get(sf.element_type, sf.element_type)

                    filters.append({
                        'name': sf.description or sf.element_type,
                        'parameter_name': param_name,
                        'selector': {'css': sf.css_selector},
                        'filter_type': sf.filter_type,
                        'optional': True,
                    })

            search_config = {
                'search_input_selector': (
                    {'css': search_input_selector} if search_input_selector else None
                ),
                'search_button_selector': (
                    {'css': search_button_selector} if search_button_selector else None
                ),
                'keywords_format': 'space_separated',
                'filters': filters,
            }

        workflow_data = {
            'name': request.name,
            'description': request.description or f'Auto-detected workflow for {domain}',
            'website_domain': domain,
            'start_url': request.url,
            'extraction_rules': extraction_rules,
            'requires_authentication': request.requires_authentication,
            'authentication_type': None,
            'pagination_config': pagination_config,
            'max_articles_per_run': request.max_articles_per_run,
            'timeout_seconds': 60,
            'is_active': True,
            'health_status': 'healthy',
            'total_executions': 0,
            'successful_executions': 0,
            'failed_executions': 0,
            'total_articles_extracted': 0,
        }

        workflow_id = await repo.create(workflow_data)

        if workflow_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to save workflow',
            )

        # Save search_config if filters were detected
        if search_config:
            logger.info(
                f'Saving search config for workflow {workflow_id}: '
                f'{len(search_config.get("filters", []))} filters, '
                f'search_input={search_config.get("search_input_selector") is not None}'
            )
            # Store search_config in the workflow's extraction_rules for now
            # (search_config_repo requires workflow to already exist)
            await repo.update(workflow_id, {
                'extraction_rules': {
                    **extraction_rules,
                    'search_config': search_config,
                },
            })

        logger.info(f'Created workflow from builder: {workflow_id} ({request.name}) for {domain}')
        return CreateWorkflowResponse(workflow_id=workflow_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error confirming workflow: {e}', exc_info=True)
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to save workflow: {str(e)}',  # noqa: RUF010
        )
