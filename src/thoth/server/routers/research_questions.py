"""Research Question Management API Router.

This module provides RESTful API endpoints for managing research questions,
which drive the automated discovery system.
"""

from datetime import datetime, time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from loguru import logger
from pydantic import BaseModel, Field, field_validator

from thoth.auth.context import UserContext
from thoth.auth.dependencies import get_user_context
from thoth.mcp.auth import get_current_user_paths

# Create router with prefix and tags
router = APIRouter(
    prefix='/api/research/questions',
    tags=['research-questions'],
)


# ==================== Pydantic Models ====================


class ResearchQuestionCreate(BaseModel):
    """Request model for creating a new research question."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description='Descriptive name for the research question',
    )
    description: str | None = Field(None, description='Optional detailed description')
    keywords: list[str] = Field(
        default_factory=list, description='Keywords to search for'
    )
    topics: list[str] = Field(default_factory=list, description='Research topics')
    authors: list[str] = Field(default_factory=list, description='Preferred authors')
    selected_sources: list[str] = Field(
        ...,
        min_items=1,
        description="Source selection: ['*'] for all, or specific sources like ['arxiv', 'pubmed']",
    )
    schedule_frequency: str = Field(
        default='daily',
        description='Schedule frequency: daily, weekly, monthly, on-demand',
    )
    schedule_time: str | None = Field(
        None,
        pattern=r'^\d{2}:\d{2}$',
        description='Preferred run time in HH:MM format (24-hour)',
    )
    schedule_days_of_week: list[int] | None = Field(
        None, description='Days for weekly schedule: ISO 8601 (1=Monday, 7=Sunday)'
    )
    min_relevance_score: float = Field(
        default=0.5, ge=0.0, le=1.0, description='Minimum relevance threshold (0.0-1.0)'
    )
    auto_download_enabled: bool = Field(
        default=False, description='Automatically download matching PDFs'
    )
    auto_download_min_score: float = Field(
        default=0.7, ge=0.0, le=1.0, description='Minimum score for auto-download'
    )
    max_articles_per_run: int = Field(
        default=50, ge=1, le=500, description='Maximum articles per discovery run'
    )
    publication_date_range: dict[str, str] | None = Field(
        None, description='Date range for filtering publications (start/end keys)'
    )

    @field_validator('keywords', 'topics')
    @classmethod
    def validate_at_least_one_criteria(cls, v, info):  # noqa: ARG003
        """Ensure at least one keyword or topic is provided."""
        # This will be checked across both fields in the service layer
        return v

    @field_validator('schedule_frequency')
    @classmethod
    def validate_schedule_frequency(cls, v):
        """Validate schedule frequency value."""
        valid_frequencies = ['daily', 'weekly', 'monthly', 'on-demand']
        if v not in valid_frequencies:
            raise ValueError(
                f'Schedule frequency must be one of: {", ".join(valid_frequencies)}'
            )
        return v


class ResearchQuestionUpdate(BaseModel):
    """Request model for updating a research question."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    keywords: list[str] | None = None
    topics: list[str] | None = None
    authors: list[str] | None = None
    selected_sources: list[str] | None = Field(None, min_items=1)
    schedule_frequency: str | None = None
    schedule_time: str | None = Field(None, pattern=r'^\d{2}:\d{2}$')
    schedule_days_of_week: list[int] | None = None
    min_relevance_score: float | None = Field(None, ge=0.0, le=1.0)
    auto_download_enabled: bool | None = None
    auto_download_min_score: float | None = Field(None, ge=0.0, le=1.0)
    max_articles_per_run: int | None = Field(None, ge=1, le=500)
    is_active: bool | None = None
    publication_date_range: dict[str, str] | None = Field(
        None, description='Date range for filtering publications (start/end keys)'
    )

    @field_validator('schedule_frequency')
    @classmethod
    def validate_schedule_frequency(cls, v):
        """Validate schedule frequency value."""
        if v is not None:
            valid_frequencies = ['daily', 'weekly', 'monthly', 'on-demand']
            if v not in valid_frequencies:
                raise ValueError(
                    f'Schedule frequency must be one of: {", ".join(valid_frequencies)}'
                )
        return v


class ResearchQuestionResponse(BaseModel):
    """Response model for a single research question."""

    id: UUID
    user_id: str
    name: str
    description: str | None = None
    keywords: list[str]
    topics: list[str]
    authors: list[str]
    selected_sources: list[str]
    schedule_frequency: str
    schedule_time: time | None = None
    schedule_days_of_week: list[int] | None = None
    min_relevance_score: float
    auto_download_enabled: bool
    auto_download_min_score: float
    max_articles_per_run: int
    is_active: bool
    publication_date_range: dict[str, str] | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    articles_found_count: int = 0
    articles_matched_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @field_validator('publication_date_range', mode='before')
    @classmethod
    def parse_publication_date_range(cls, v):
        """Parse publication_date_range if it's a JSON string."""
        if v is None:
            return None
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        return v


class ResearchQuestionList(BaseModel):
    """Response model for a list of research questions with pagination."""

    questions: list[ResearchQuestionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class DiscoveryRunResponse(BaseModel):
    """Response model for manual discovery trigger."""

    question_id: UUID
    status: str = 'initiated'
    message: str
    estimated_time: str | None = None


class ArticleMatchResponse(BaseModel):
    """Response model for a matched article (paper)."""

    match_id: UUID
    paper_id: UUID  # Changed from article_id after schema migration
    question_id: UUID
    relevance_score: float
    matched_keywords: list[str] = Field(default_factory=list)
    matched_topics: list[str] = Field(default_factory=list)
    matched_authors: list[str] = Field(default_factory=list)
    discovered_via_source: str | None = None
    is_viewed: bool = False
    is_bookmarked: bool = False
    user_sentiment: str | None = None
    sentiment_recorded_at: datetime | None = None
    matched_at: datetime | None = None
    # Paper details (from paper_metadata)
    doi: str | None = None
    title: str = Field(default='Untitled')
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    publication_date: datetime | None = None
    journal: str | None = None
    url: str | None = None
    pdf_url: str | None = None

    @field_validator(
        'matched_keywords',
        'matched_topics',
        'matched_authors',
        'authors',
        mode='before',
    )
    @classmethod
    def coerce_to_list(cls, v):
        """Ensure list fields are never None and parse JSON strings.

        PostgreSQL jsonb columns (e.g. paper_metadata.authors) may be
        returned by asyncpg as JSON-encoded strings rather than native
        Python lists.  This validator handles that transparently.
        """
        if v is None:
            return []
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return parsed
            except (json.JSONDecodeError, TypeError):
                pass
            # Non-JSON string → wrap in a single-element list
            return [v]
        return v

    @field_validator('title', mode='before')
    @classmethod
    def coerce_title(cls, v):
        """Ensure title is never None."""
        if v is None:
            return 'Untitled'
        return v

    class Config:
        from_attributes = True


class ArticleMatchList(BaseModel):
    """Response model for matched articles with pagination."""

    matches: list[ArticleMatchResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class StatisticsResponse(BaseModel):
    """Response model for question statistics."""

    question_id: UUID
    total_matches: int = 0
    high_relevance_matches: int = 0
    unviewed_matches: int = 0
    last_match_at: datetime | None = None
    total_runs: int = 0
    successful_runs: int = 0
    avg_relevance_score: float | None = None
    source_count: int = 0


# ==================== Helper Functions ====================


def _get_research_question_service(request: Request):
    """
    Get the research question service from service manager via DI.

    Args:
        request: FastAPI request object (carries app state).

    Returns:
        ResearchQuestionService instance.
    """
    from thoth.server.dependencies import get_service_manager

    sm = get_service_manager(request)
    return sm.research_question


def _get_discovery_orchestrator(request: Request):
    """
    Get the discovery orchestrator from service manager, or None if unavailable.

    Args:
        request: FastAPI request object.

    Returns:
        DiscoveryOrchestrator instance or None.
    """
    from thoth.server.dependencies import get_service_manager

    sm = get_service_manager(request)
    # Access via _services dict to avoid ServiceUnavailableError when None
    return sm._services.get('discovery_orchestrator')


def _get_match_repository(request: Request):
    """
    Get a ResearchQuestionMatchRepository from service manager via DI.

    Args:
        request: FastAPI request object.

    Returns:
        ResearchQuestionMatchRepository instance.
    """
    from thoth.repositories.research_question_match_repository import (
        ResearchQuestionMatchRepository,
    )
    from thoth.server.dependencies import get_service_manager

    sm = get_service_manager(request)
    return ResearchQuestionMatchRepository(sm.postgres)


# ==================== API Endpoints ====================


@router.post(
    '',
    response_model=ResearchQuestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary='Create research question',
    description='Create a new research question to drive automated discovery',
)
async def create_research_question(
    question: ResearchQuestionCreate,
    request: Request,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> ResearchQuestionResponse:
    """
    Create a new research question.

    The research question will be used to automatically discover and match
    relevant articles based on keywords, topics, and authors.

    Args:
        question: Research question creation data
        request: FastAPI request object

    Returns:
        ResearchQuestionResponse: Created question with ID

    Raises:
        HTTPException: 400 if validation fails, 503 if service unavailable
    """
    try:
        service = _get_research_question_service(request)
        user_id = user_context.user_id

        # Validate at least one keyword or topic
        if not question.keywords and not question.topics:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='At least one keyword or topic must be provided',
            )

        # Create the question
        question_id = await service.create_research_question(
            user_id=user_id,
            name=question.name,
            description=question.description,
            keywords=question.keywords,
            topics=question.topics,
            authors=question.authors,
            selected_sources=question.selected_sources,
            schedule_frequency=question.schedule_frequency,
            schedule_time=question.schedule_time,
            schedule_days_of_week=question.schedule_days_of_week,
            min_relevance_score=question.min_relevance_score,
            auto_download_enabled=question.auto_download_enabled,
            auto_download_min_score=question.auto_download_min_score,
            max_articles_per_run=question.max_articles_per_run,
            publication_date_range=question.publication_date_range,
        )

        if not question_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to create research question',
            )

        # Fetch the created question
        created_question = await service.repository.get_by_id(question_id)

        if not created_question:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Question created but could not be retrieved',
            )

        logger.info(
            f'Created research question: {question.name} ({question_id}) for user {user_id}'
        )

        return ResearchQuestionResponse(**created_question)

    except ValueError as e:
        logger.warning(f'Validation error creating research question: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error creating research question: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.get(
    '',
    response_model=ResearchQuestionList,
    summary='List research questions',
    description='Get all research questions for the current user with optional filtering',
)
async def list_research_questions(
    request: Request,
    active_only: bool = Query(True, description='Only return active questions'),
    limit: int = Query(50, ge=1, le=500, description='Maximum number of results'),
    offset: int = Query(0, ge=0, description='Number of records to skip'),
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> ResearchQuestionList:
    """
    List all research questions for the current user.

    Args:
        request: FastAPI request object
        active_only: Filter for active questions only
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        ResearchQuestionList: List of questions with pagination metadata

    Raises:
        HTTPException: 503 if service unavailable
    """
    try:
        service = _get_research_question_service(request)
        user_id = user_context.user_id

        # Get questions from repository with pagination
        questions = await service.repository.get_by_user(
            user_id=user_id,
            is_active=active_only if active_only else None,
            limit=limit + 1,  # Get one extra to check if there are more
            offset=offset,
        )

        # Check if there are more results
        has_more = len(questions) > limit
        if has_more:
            questions = questions[:limit]

        # Get total count (approximate for large datasets)
        total = len(questions) + offset
        if has_more:
            total += 1  # At least one more

        logger.debug(
            f'Retrieved {len(questions)} research questions for user {user_id}'
        )

        return ResearchQuestionList(
            questions=[ResearchQuestionResponse(**q) for q in questions],
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error listing research questions: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.get(
    '/{question_id}',
    response_model=ResearchQuestionResponse,
    summary='Get research question',
    description='Get a specific research question by ID',
)
async def get_research_question(
    question_id: UUID,
    request: Request,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> ResearchQuestionResponse:
    """
    Get a specific research question by ID.

    Args:
        question_id: Research question UUID
        request: FastAPI request object

    Returns:
        ResearchQuestionResponse: Question details

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized, 503 if service unavailable
    """
    try:
        service = _get_research_question_service(request)
        user_id = user_context.user_id

        # Get the question
        question = await service.repository.get_by_id(question_id)

        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Research question {question_id} not found',
            )

        # Check ownership
        if question['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You do not have permission to access this research question',
            )

        logger.debug(f'Retrieved research question: {question_id}')

        return ResearchQuestionResponse(**question)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting research question {question_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.put(
    '/{question_id}',
    response_model=ResearchQuestionResponse,
    summary='Update research question',
    description='Update an existing research question',
)
async def update_research_question(
    question_id: UUID,
    updates: ResearchQuestionUpdate,
    request: Request,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> ResearchQuestionResponse:
    """
    Update an existing research question.

    Only provided fields will be updated. The user must own the question.

    Args:
        question_id: Research question UUID
        updates: Fields to update
        request: FastAPI request object

    Returns:
        ResearchQuestionResponse: Updated question

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized, 400 if validation fails
    """
    try:
        service = _get_research_question_service(request)
        user_id = user_context.user_id

        # Convert to dict and filter out None values
        update_dict = {k: v for k, v in updates.model_dump().items() if v is not None}

        if not update_dict:
            # No updates provided, just return current state
            question = await service.repository.get_by_id(question_id)
            if not question:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f'Research question {question_id} not found',
                )
            return ResearchQuestionResponse(**question)

        # Update the question (service handles ownership check)
        success = await service.update_research_question(
            question_id=question_id, user_id=user_id, **update_dict
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to update research question',
            )

        # Fetch updated question
        updated_question = await service.repository.get_by_id(question_id)

        logger.info(
            f'Updated research question: {question_id} with fields: {list(update_dict.keys())}'
        )

        return ResearchQuestionResponse(**updated_question)

    except ValueError as e:
        logger.warning(f'Validation error updating research question: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except PermissionError as e:
        logger.warning(f'Permission error updating research question: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating research question {question_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.delete(
    '/{question_id}',
    status_code=status.HTTP_204_NO_CONTENT,
    summary='Delete research question',
    description='Delete or deactivate a research question',
)
async def delete_research_question(
    question_id: UUID,
    request: Request,
    hard_delete: bool = Query(
        False, description='Permanently delete instead of soft delete'
    ),
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> None:
    """
    Delete or deactivate a research question.

    By default, performs a soft delete (sets is_active=false). Set hard_delete=true
    to permanently remove the question and all associated matches.

    Args:
        question_id: Research question UUID
        request: FastAPI request object
        hard_delete: If True, permanently delete; if False, soft delete

    Returns:
        None (204 No Content)

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized
    """
    try:
        service = _get_research_question_service(request)
        user_id = user_context.user_id

        # Delete the question (service handles ownership check)
        success = await service.delete_research_question(
            question_id=question_id, user_id=user_id, hard_delete=hard_delete
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Research question {question_id} not found',
            )

        action = 'deleted' if hard_delete else 'deactivated'
        logger.info(f'{action.capitalize()} research question: {question_id}')

        return None

    except PermissionError as e:
        logger.warning(f'Permission error deleting research question: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error deleting research question {question_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.post(
    '/{question_id}/run',
    response_model=DiscoveryRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary='Trigger manual discovery',
    description='Manually trigger a discovery run for this research question',
)
async def trigger_discovery_run(
    question_id: UUID,
    request: Request,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> DiscoveryRunResponse:
    """
    Manually trigger a discovery run for a research question.

    This bypasses the normal schedule and immediately starts discovering articles
    that match the question criteria.

    Args:
        question_id: Research question UUID
        request: FastAPI request object

    Returns:
        DiscoveryRunResponse: Status of the initiated discovery run

    Raises:
        HTTPException: 404 if not found, 403 if unauthorized, 503 if service unavailable
    """
    try:
        service = _get_research_question_service(request)
        orchestrator = _get_discovery_orchestrator(request)
        user_id = user_context.user_id

        # Verify ownership
        question = await service.repository.get_by_id(question_id)

        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Research question {question_id} not found',
            )

        if question['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You do not have permission to trigger discovery for this question',
            )

        # Trigger discovery run (this is async and non-blocking)
        logger.info(f'Manually triggering discovery for question: {question_id}')

        # If orchestrator is available locally, use it (all-in-one mode)
        if orchestrator is not None:
            # Run discovery in background task (non-blocking)
            import asyncio

            _task = asyncio.create_task(  # noqa: RUF006
                orchestrator.run_discovery_for_question(question_id)
            )
            logger.info(f'Discovery task created for question {question_id}')
        else:
            # Microservices: Trigger via database flag for scheduler
            logger.info('Microservices mode: Marking question for immediate discovery')

            # Update the question to trigger immediate run by setting next_run_at to now
            from datetime import datetime

            await service.repository.update(
                question_id, {'next_run_at': datetime.now()}
            )

            logger.info(
                f'Question {question_id} marked for immediate discovery by scheduler'
            )

        return DiscoveryRunResponse(
            question_id=question_id,
            status='initiated',
            message=f'Discovery run initiated for question: {question["name"]}',
            estimated_time='5-10 minutes',
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error triggering discovery for question {question_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.get(
    '/{question_id}/articles',
    response_model=ArticleMatchList,
    summary='Get matched articles',
    description='Get articles that match this research question',
)
async def get_matched_articles(
    question_id: UUID,
    request: Request,
    min_relevance: float | None = Query(
        None, ge=0.0, le=1.0, description='Minimum relevance score filter'
    ),
    is_viewed: bool | None = Query(None, description='Filter by viewed status'),
    is_bookmarked: bool | None = Query(None, description='Filter by bookmarked status'),
    limit: int = Query(50, ge=1, le=500, description='Maximum number of results'),
    offset: int = Query(0, ge=0, description='Number of records to skip'),
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> ArticleMatchList:
    """
    Get all articles that match this research question.

    Returns articles with their relevance scores and match details,
    ordered by relevance score (highest first).

    Args:
        question_id: Research question UUID
        request: FastAPI request object
        min_relevance: Minimum relevance score filter
        is_viewed: Filter by viewed status
        is_bookmarked: Filter by bookmarked status
        limit: Maximum number of results
        offset: Pagination offset

    Returns:
        ArticleMatchList: List of matched articles with pagination

    Raises:
        HTTPException: 404 if question not found, 403 if unauthorized
    """
    try:
        service = _get_research_question_service(request)
        match_repo = _get_match_repository(request)
        user_id = user_context.user_id

        # Verify ownership
        question = await service.repository.get_by_id(question_id)

        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Research question {question_id} not found',
            )

        if question['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You do not have permission to view matches for this question',
            )

        # Build filtered query with optional filters
        query = """
            SELECT
                rqm.id as match_id,
                rqm.paper_id,
                rqm.question_id,
                rqm.relevance_score,
                rqm.matched_keywords,
                rqm.matched_topics,
                rqm.matched_authors,
                rqm.discovered_via_source,
                rqm.is_viewed,
                rqm.is_bookmarked,
                rqm.user_sentiment,
                rqm.sentiment_recorded_at,
                rqm.matched_at,
                pm.doi,
                pm.title,
                pm.authors,
                pm.abstract,
                pm.publication_date,
                pm.journal,
                pm.url,
                pm.pdf_url
            FROM research_question_matches rqm
            JOIN paper_metadata pm ON pm.id = rqm.paper_id
            WHERE rqm.question_id = $1
        """
        params: list = [question_id]
        param_idx = 2

        if min_relevance is not None:
            query += f' AND rqm.relevance_score >= ${param_idx}'
            params.append(min_relevance)
            param_idx += 1

        if is_viewed is not None:
            query += f' AND rqm.is_viewed = ${param_idx}'
            params.append(is_viewed)
            param_idx += 1

        if is_bookmarked is not None:
            query += f' AND rqm.is_bookmarked = ${param_idx}'
            params.append(is_bookmarked)
            param_idx += 1

        query += ' ORDER BY rqm.relevance_score DESC, rqm.matched_at DESC'
        query += f' LIMIT ${param_idx} OFFSET ${param_idx + 1}'
        params.extend([limit + 1, offset])  # Get one extra to check if there are more

        rows = await match_repo.postgres.fetch(query, *params)
        matches = [dict(row) for row in rows]

        # Check if there are more results
        has_more = len(matches) > limit
        if has_more:
            matches = matches[:limit]

        # Get total count (approximate)
        total = len(matches) + offset
        if has_more:
            total += 1

        logger.debug(
            f'Retrieved {len(matches)} matched articles for question {question_id}'
        )

        return ArticleMatchList(
            matches=[ArticleMatchResponse(**m) for m in matches],
            total=total,
            limit=limit,
            offset=offset,
            has_more=has_more,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting matched articles for question {question_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.get(
    '/{question_id}/statistics',
    response_model=StatisticsResponse,
    summary='Get question statistics',
    description='Get comprehensive statistics for this research question',
)
async def get_question_statistics(
    question_id: UUID,
    request: Request,
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> StatisticsResponse:
    """
    Get comprehensive statistics for a research question.

    Includes match counts, relevance averages, run history, and more.

    Args:
        question_id: Research question UUID
        request: FastAPI request object

    Returns:
        StatisticsResponse: Question statistics

    Raises:
        HTTPException: 404 if question not found, 403 if unauthorized
    """
    try:
        service = _get_research_question_service(request)
        user_id = user_context.user_id

        # Get statistics (service handles ownership check)
        stats = await service.get_question_statistics(
            question_id=question_id, user_id=user_id
        )

        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Research question {question_id} not found or no statistics available',
            )

        logger.debug(f'Retrieved statistics for question {question_id}')

        # Build response with defaults for missing fields
        return StatisticsResponse(
            question_id=question_id,
            total_matches=stats.get('total_matches', 0),
            high_relevance_matches=stats.get('high_relevance_matches', 0),
            unviewed_matches=stats.get('unviewed_matches', 0),
            last_match_at=stats.get('last_match_at'),
            total_runs=stats.get('total_runs', 0),
            successful_runs=stats.get('successful_runs', 0),
            avg_relevance_score=stats.get(
                'avg_relevance', stats.get('avg_relevance_score')
            ),
            source_count=stats.get('source_count', 0),
        )

    except PermissionError as e:
        logger.warning(f'Permission error getting statistics: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error getting statistics for question {question_id}: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.patch(
    '/{question_id}/articles/{match_id}/sentiment',
    response_model=ArticleMatchResponse,
    summary='Update article sentiment',
    description='Mark article as liked, disliked, or skip',
)
async def update_article_sentiment(
    question_id: UUID,
    match_id: UUID,
    request: Request,
    sentiment: str = Body(..., embed=True, pattern='^(like|dislike|skip)$'),
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> ArticleMatchResponse:
    """
    Update user sentiment for a matched article.

    Allows users to provide feedback on article relevance by marking them as
    'like', 'dislike', or 'skip'. This helps improve future recommendations.

    Args:
        question_id: Research question UUID
        match_id: Article match UUID
        sentiment: Sentiment value ('like', 'dislike', or 'skip')
        request: FastAPI request object

    Returns:
        ArticleMatchResponse: Updated article match with sentiment data

    Raises:
        HTTPException: 400 if validation fails, 403 if unauthorized, 404 if not found
    """
    try:
        service = _get_research_question_service(request)
        match_repo = _get_match_repository(request)
        user_id = user_context.user_id

        # Verify question ownership first
        question = await service.repository.get_by_id(question_id)

        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Research question {question_id} not found',
            )

        if question['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You do not have permission to update this research question',
            )

        # Get the match to verify it belongs to this question
        match = await match_repo.get_by_id(match_id)

        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Article match {match_id} not found',
            )

        # Verify the match belongs to this question
        if match['question_id'] != question_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Article match {match_id} does not belong to question {question_id}',
            )

        # Update sentiment
        success = await match_repo.update_user_interaction(
            match_id, user_sentiment=sentiment
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to update article sentiment',
            )

        # Fetch updated match with paper details using direct query (after migration)
        # Uses research_question_matches + paper_metadata
        query = """
            SELECT
                rqm.id as match_id,
                rqm.paper_id,
                rqm.question_id,
                rqm.relevance_score,
                rqm.matched_keywords,
                rqm.matched_topics,
                rqm.matched_authors,
                rqm.discovered_via_source,
                rqm.is_viewed,
                rqm.is_bookmarked,
                rqm.user_sentiment,
                rqm.sentiment_recorded_at,
                rqm.matched_at,
                pm.doi,
                pm.title,
                pm.authors,
                pm.abstract,
                pm.publication_date,
                pm.journal,
                pm.url,
                pm.pdf_url
            FROM research_question_matches rqm
            JOIN paper_metadata pm ON rqm.paper_id = pm.id
            WHERE rqm.id = $1
        """

        updated_match = await match_repo.postgres.fetchrow(query, match_id)

        if not updated_match:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to retrieve updated match with article details',
            )

        logger.info(f"Updated sentiment for match {match_id} to '{sentiment}'")

        return ArticleMatchResponse(**dict(updated_match))

    except ValueError as e:
        logger.warning(f'Validation error updating sentiment: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating article sentiment: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.patch(
    '/{question_id}/articles/{match_id}/status',
    response_model=ArticleMatchResponse,
    summary='Update article status',
    description='Mark article as viewed or bookmarked',
)
async def update_article_status(
    question_id: UUID,
    match_id: UUID,
    request: Request,
    is_viewed: bool | None = Body(None, embed=True),
    is_bookmarked: bool | None = Body(None, embed=True),
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> ArticleMatchResponse:
    """
    Update article view/bookmark status.

    Args:
        question_id: Research question UUID
        match_id: Article match UUID
        is_viewed: Mark as viewed (true) or unviewed (false)
        is_bookmarked: Mark as bookmarked (true) or unbookmarked (false)
        request: FastAPI request object

    Returns:
        ArticleMatchResponse: Updated article match

    Raises:
        HTTPException: 400 if validation fails, 403 if unauthorized, 404 if not found
    """
    try:
        service = _get_research_question_service(request)
        match_repo = _get_match_repository(request)
        user_id = user_context.user_id

        # Verify question ownership
        question = await service.repository.get_by_id(question_id)

        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Research question {question_id} not found',
            )

        if question['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You do not have permission to update this research question',
            )

        # Get the match
        match = await match_repo.get_by_id(match_id)

        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Article match {match_id} not found',
            )

        # Verify match belongs to question
        if match['question_id'] != question_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Article match {match_id} does not belong to question {question_id}',
            )

        # Update status fields
        updates = {}
        if is_viewed is not None:
            updates['is_viewed'] = is_viewed
        if is_bookmarked is not None:
            updates['is_bookmarked'] = is_bookmarked

        if not updates:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Must provide at least one status field to update',
            )

        # Update in database
        success = await match_repo.update(match_id, updates)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to update article status',
            )

        # Fetch updated match with paper details using JOIN (same as sentiment endpoint)
        query = """
            SELECT
                rqm.id as match_id,
                rqm.paper_id,
                rqm.question_id,
                rqm.relevance_score,
                rqm.matched_keywords,
                rqm.matched_topics,
                rqm.matched_authors,
                rqm.discovered_via_source,
                rqm.is_viewed,
                rqm.is_bookmarked,
                rqm.user_sentiment,
                rqm.sentiment_recorded_at,
                rqm.matched_at,
                pm.doi,
                pm.title,
                pm.authors,
                pm.abstract,
                pm.publication_date,
                pm.journal,
                pm.url,
                pm.pdf_url
            FROM research_question_matches rqm
            JOIN paper_metadata pm ON rqm.paper_id = pm.id
            WHERE rqm.id = $1
        """
        updated_match = await match_repo.postgres.fetchrow(query, match_id)

        if not updated_match:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail='Failed to retrieve updated article after status update',
            )

        logger.debug(f'Updated article status for match {match_id}: {updates}')

        return ArticleMatchResponse(**dict(updated_match))

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating article status: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )


@router.post(
    '/{question_id}/articles/{match_id}/download',
    summary='Download article PDF',
    description='Download PDF for a matched article',
)
async def download_article_pdf(
    question_id: UUID,
    match_id: UUID,
    request: Request,
    output_directory: str | None = Body(None, embed=True),  # noqa: ARG001
    user_context: UserContext = Depends(get_user_context),  # noqa: B008
) -> dict[str, Any]:
    """
    Download PDF for a matched article.

    Args:
        question_id: Research question UUID
        match_id: Article match UUID
        output_directory: Optional custom output directory (not currently used)
        request: FastAPI request object

    Returns:
        dict: Download result with file path and status

    Raises:
        HTTPException: 400 if validation fails, 403 if unauthorized, 404 if not found
    """
    try:
        service = _get_research_question_service(request)
        match_repo = _get_match_repository(request)
        user_id = user_context.user_id

        # Verify question ownership
        question = await service.repository.get_by_id(question_id)

        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Research question {question_id} not found',
            )

        if question['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You do not have permission to access this research question',
            )

        # Get the match
        match = await match_repo.get_by_id(match_id)

        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Article match {match_id} not found',
            )

        # Verify match belongs to question
        if match['question_id'] != question_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Article match {match_id} does not belong to question {question_id}',
            )

        # Get paper details (includes pdf_url) - after migration uses paper_id
        paper_id = match.get('paper_id') or match.get(
            'article_id'
        )  # Support both for transition

        # Fetch paper metadata to get pdf_url and title
        query = """
            SELECT id, title, pdf_url, url
            FROM paper_metadata
            WHERE id = $1
        """
        paper = await match_repo.postgres.fetchrow(query, paper_id)

        if not paper:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Paper {paper_id} not found',
            )

        pdf_url = paper['pdf_url']
        title = paper['title'] or 'unknown'

        if not pdf_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='No PDF URL available for this article',
            )

        # Download PDF using ingestion service
        from thoth.config import config
        from thoth.ingestion.pdf_downloader import download_pdf

        user_paths = get_current_user_paths()
        pdf_dir = user_paths.pdf_dir if user_paths else config.pdf_dir

        # Sanitize filename from article title
        safe_filename = ''.join(
            c if c.isalnum() or c in (' ', '-', '_') else '_' for c in title
        )
        safe_filename = safe_filename[:200]  # Limit length

        # Ensure .pdf extension
        if not safe_filename.lower().endswith('.pdf'):
            safe_filename += '.pdf'

        try:
            # Download the PDF
            downloaded_path = download_pdf(pdf_url, pdf_dir, safe_filename)

            # Mark as bookmarked in database
            await match_repo.update(match_id, {'is_bookmarked': True})

            # Mark as viewed too
            if not match.get('is_viewed'):
                await match_repo.update_user_interaction(match_id, is_viewed=True)

            logger.info(f'Downloaded PDF for article {paper_id} to {downloaded_path}')

            result = {
                'status': 'success',
                'article_id': str(paper_id),
                'match_id': str(match_id),
                'downloaded_path': str(downloaded_path),
                'message': 'PDF downloaded successfully. File monitor will process it automatically.',
                'filename': downloaded_path.name,
            }
        except Exception as e:
            logger.error(f'Failed to download PDF from {pdf_url}: {e}')
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Failed to download PDF: {e!s}',
            ) from e

        logger.debug(f'Prepared download info for article {paper_id}')

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error preparing article download: {e}')
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Internal server error: {str(e)}',  # noqa: RUF010
        )
