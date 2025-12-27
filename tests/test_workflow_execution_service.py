"""
Unit tests for WorkflowExecutionService.

Tests the high-level workflow execution service that coordinates
browser manager, workflow engine, and extraction service.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

from thoth.discovery.browser import (
    WorkflowExecutionService,
    WorkflowExecutionServiceError,
)
from thoth.utilities.schemas.browser_workflow import ExecutionParameters, ExecutionTrigger


@pytest.fixture
def mock_postgres_service():
    """Create a mock PostgreSQL service."""
    service = AsyncMock()
    service.initialize = AsyncMock()
    service.shutdown = AsyncMock()
    return service


@pytest.fixture
def mock_browser_manager():
    """Create a mock browser manager."""
    manager = AsyncMock()
    manager.initialize = AsyncMock()
    manager.shutdown = AsyncMock()
    manager.get_browser = AsyncMock()
    manager.cleanup = AsyncMock()
    return manager


@pytest.fixture
def service(mock_postgres_service):
    """Create a workflow execution service instance."""
    return WorkflowExecutionService(
        postgres_service=mock_postgres_service,
        max_concurrent_browsers=3,
        default_timeout=10000,
        max_retries=2,
    )


class TestWorkflowExecutionServiceInitialization:
    """Test service initialization and lifecycle."""

    @pytest.mark.asyncio
    async def test_service_creation(self, mock_postgres_service):
        """Test service can be created with dependencies."""
        service = WorkflowExecutionService(
            postgres_service=mock_postgres_service,
            max_concurrent_browsers=5,
        )

        assert service.postgres == mock_postgres_service
        assert service.max_retries == 3  # default
        assert not service.is_initialized

    @pytest.mark.asyncio
    async def test_initialization(self, service, mock_browser_manager):
        """Test service initialization."""
        with patch.object(service, 'browser_manager', mock_browser_manager):
            await service.initialize()

            assert service.is_initialized
            mock_browser_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_double_initialization(self, service, mock_browser_manager):
        """Test that double initialization is safe."""
        with patch.object(service, 'browser_manager', mock_browser_manager):
            await service.initialize()
            await service.initialize()  # Should not raise

            # Should only initialize once
            assert service.is_initialized

    @pytest.mark.asyncio
    async def test_shutdown(self, service, mock_browser_manager):
        """Test service shutdown."""
        with patch.object(service, 'browser_manager', mock_browser_manager):
            await service.initialize()
            await service.shutdown()

            assert not service.is_initialized
            mock_browser_manager.shutdown.assert_called_once()


class TestParameterValidation:
    """Test execution parameter validation."""

    @pytest.mark.asyncio
    async def test_validate_keywords(self, service):
        """Test keyword validation."""
        # Valid keywords
        params = ExecutionParameters(keywords=['test', 'keywords'])
        service._validate_parameters(params)  # Should not raise

        # Empty keywords list should raise
        with pytest.raises(WorkflowExecutionServiceError, match='At least keywords or custom_filters'):
            params = ExecutionParameters(keywords=[])
            service._validate_parameters(params)

    @pytest.mark.asyncio
    async def test_validate_no_parameters(self, service):
        """Test that at least some parameters are required."""
        with pytest.raises(
            WorkflowExecutionServiceError,
            match='At least keywords or custom_filters must be provided',
        ):
            params = ExecutionParameters()
            service._validate_parameters(params)

    @pytest.mark.asyncio
    async def test_validate_custom_filters(self, service):
        """Test custom filters are accepted."""
        params = ExecutionParameters(custom_filters={'journal': 'Nature'})
        service._validate_parameters(params)  # Should not raise

    @pytest.mark.asyncio
    async def test_validate_date_range(self, service):
        """Test date range validation warns on unusual values."""
        # Valid date range
        params = ExecutionParameters(keywords=['test'], date_range='last_7d')
        service._validate_parameters(params)

        # Unusual date range should log warning but not raise
        params = ExecutionParameters(keywords=['test'], date_range='custom_range')
        service._validate_parameters(params)  # Should not raise


class TestWorkflowExecution:
    """Test workflow execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_workflow_not_initialized(self, service):
        """Test execution fails if service not initialized."""
        params = ExecutionParameters(keywords=['test'])
        workflow_id = uuid4()

        with pytest.raises(
            WorkflowExecutionServiceError, match='Service not initialized'
        ):
            await service.execute_workflow(workflow_id, params)

    @pytest.mark.asyncio
    async def test_execute_workflow_invalid_parameters(self, service, mock_browser_manager):
        """Test execution fails with invalid parameters."""
        with patch.object(service, 'browser_manager', mock_browser_manager):
            await service.initialize()

            workflow_id = uuid4()
            params = ExecutionParameters()  # No keywords or filters

            # Should return failed result, not raise (graceful error handling)
            result = await service.execute_workflow(workflow_id, params)

            assert not result.stats.success
            assert 'At least keywords or custom_filters' in result.stats.error_message

    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, service, mock_browser_manager):
        """Test successful workflow execution."""
        with patch.object(service, 'browser_manager', mock_browser_manager):
            await service.initialize()

            # Mock workflow engine
            mock_engine_result = MagicMock()
            mock_engine_result.success = True
            mock_engine_result.execution_id = uuid4()
            mock_engine_result.articles_extracted = 10
            mock_engine_result.pages_visited = 2
            mock_engine_result.duration_ms = 5000
            mock_engine_result.error_message = None
            mock_engine_result.execution_log = [
                {'timestamp': '2024-01-01T00:00:00', 'action': 'workflow_loaded'}
            ]

            service.workflow_engine.execute_workflow = AsyncMock(
                return_value=mock_engine_result
            )

            # Execute workflow
            workflow_id = uuid4()
            params = ExecutionParameters(keywords=['machine learning'])

            result = await service.execute_workflow(
                workflow_id=workflow_id,
                parameters=params,
                trigger=ExecutionTrigger.MANUAL,
                max_articles=50,
            )

            # Verify result
            assert result.stats.success
            assert result.stats.articles_extracted == 10
            assert result.stats.pages_visited == 2
            assert result.stats.error_message is None
            assert len(result.execution_log) > 0

    @pytest.mark.asyncio
    async def test_execute_workflow_with_query_id(self, service, mock_browser_manager):
        """Test workflow execution with query ID."""
        with patch.object(service, 'browser_manager', mock_browser_manager):
            await service.initialize()

            # Mock successful execution
            mock_engine_result = MagicMock()
            mock_engine_result.success = True
            mock_engine_result.execution_id = uuid4()
            mock_engine_result.articles_extracted = 5
            mock_engine_result.pages_visited = 1
            mock_engine_result.duration_ms = 3000
            mock_engine_result.error_message = None
            mock_engine_result.execution_log = []

            service.workflow_engine.execute_workflow = AsyncMock(
                return_value=mock_engine_result
            )

            # Execute with query ID
            workflow_id = uuid4()
            query_id = uuid4()
            params = ExecutionParameters(keywords=['quantum computing'])

            result = await service.execute_workflow(
                workflow_id=workflow_id,
                parameters=params,
                trigger=ExecutionTrigger.QUERY,
                query_id=query_id,
            )

            # Verify engine was called with query_id
            service.workflow_engine.execute_workflow.assert_called_once()
            call_kwargs = service.workflow_engine.execute_workflow.call_args.kwargs
            assert call_kwargs['query_id'] == query_id
            assert call_kwargs['trigger'] == ExecutionTrigger.QUERY


class TestWorkflowInfo:
    """Test workflow information retrieval."""

    @pytest.mark.asyncio
    async def test_get_workflow_info(self, service):
        """Test getting workflow information."""
        workflow_id = uuid4()
        workflow_data = {
            'id': workflow_id,
            'name': 'Test Workflow',
            'website_domain': 'example.com',
        }

        service.workflow_repo.get_by_id = AsyncMock(return_value=workflow_data)

        result = await service.get_workflow_info(workflow_id)

        assert result == workflow_data
        service.workflow_repo.get_by_id.assert_called_once_with(workflow_id)

    @pytest.mark.asyncio
    async def test_get_workflow_info_not_found(self, service):
        """Test getting non-existent workflow."""
        workflow_id = uuid4()
        service.workflow_repo.get_by_id = AsyncMock(return_value=None)

        result = await service.get_workflow_info(workflow_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_active_workflows(self, service):
        """Test listing active workflows."""
        workflows = [
            {'id': uuid4(), 'name': 'Workflow 1', 'is_active': True},
            {'id': uuid4(), 'name': 'Workflow 2', 'is_active': True},
        ]

        service.workflow_repo.get_active_workflows = AsyncMock(return_value=workflows)

        result = await service.list_active_workflows()

        assert len(result) == 2
        assert result == workflows

    @pytest.mark.asyncio
    async def test_list_active_workflows_empty(self, service):
        """Test listing when no active workflows."""
        service.workflow_repo.get_active_workflows = AsyncMock(return_value=[])

        result = await service.list_active_workflows()

        assert result == []
