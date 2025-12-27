"""
Comprehensive tests for WorkflowExecutionsRepository.

This module tests execution tracking, status management, error handling,
statistics collection, and CRUD operations for workflow executions.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4


@pytest.fixture
def mock_postgres():
    """Create mock PostgreSQL service."""
    postgres = MagicMock()
    postgres.fetchrow = AsyncMock()
    postgres.fetch = AsyncMock()
    postgres.fetchval = AsyncMock()
    postgres.execute = AsyncMock()
    return postgres


@pytest.fixture
def executions_repo(mock_postgres):
    """Create WorkflowExecutionsRepository instance with mocked postgres."""
    try:
        from thoth.repositories.workflow_executions_repository import (
            WorkflowExecutionsRepository,
        )

        return WorkflowExecutionsRepository(mock_postgres, use_cache=False)
    except ImportError:
        pytest.skip('WorkflowExecutionsRepository not yet implemented')


@pytest.fixture
def sample_execution_data():
    """Sample workflow execution data for testing."""
    return {
        'workflow_id': uuid4(),
        'status': 'running',
        'started_at': datetime.now().isoformat(),
        'completed_at': None,
        'duration_seconds': None,
        'actions_completed': 0,
        'actions_failed': 0,
        'total_actions': 5,
        'error_message': None,
        'results': {},
        'metadata': {
            'trigger': 'scheduled',
            'user_id': 'user123',
            'environment': 'production',
        },
    }


@pytest.fixture
def sample_execution_record():
    """Sample execution database record."""
    execution_id = uuid4()
    workflow_id = uuid4()
    started_at = datetime.now()
    return {
        'id': execution_id,
        'workflow_id': workflow_id,
        'status': 'completed',
        'started_at': started_at,
        'completed_at': started_at + timedelta(minutes=5),
        'duration_seconds': 300.5,
        'actions_completed': 5,
        'actions_failed': 0,
        'total_actions': 5,
        'error_message': None,
        'results': {
            'papers_found': 42,
            'papers_downloaded': 38,
            'papers_processed': 38,
        },
        'metadata': {
            'trigger': 'scheduled',
            'user_id': 'user123',
            'environment': 'production',
        },
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
    }


# ============================================================================
# CREATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_execution_success(
    executions_repo, mock_postgres, sample_execution_data
):
    """Test successful execution creation."""
    # Arrange
    expected_id = uuid4()
    mock_postgres.fetchval.return_value = expected_id

    # Act
    result_id = await executions_repo.create(sample_execution_data)

    # Assert
    assert result_id == expected_id
    mock_postgres.fetchval.assert_called_once()

    # Verify SQL query contains expected columns
    call_args = mock_postgres.fetchval.call_args
    query = call_args[0][0]
    assert 'INSERT INTO' in query
    assert 'RETURNING id' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_execution_missing_workflow_id(executions_repo, mock_postgres):
    """Test creating execution without workflow_id fails."""
    # Arrange
    incomplete_data = {'status': 'running'}
    mock_postgres.fetchval.side_effect = Exception(
        'null value in column "workflow_id"'
    )

    # Act
    result_id = await executions_repo.create(incomplete_data)

    # Assert
    assert result_id is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_execution_with_metadata(executions_repo, mock_postgres):
    """Test creating execution with JSONB metadata."""
    # Arrange
    execution_data = {
        'workflow_id': uuid4(),
        'status': 'running',
        'metadata': {
            'trigger': 'manual',
            'user_id': 'user456',
            'tags': ['urgent', 'review'],
            'custom_params': {'depth': 2, 'language': 'en'},
        },
    }
    expected_id = uuid4()
    mock_postgres.fetchval.return_value = expected_id

    # Act
    result_id = await executions_repo.create(execution_data)

    # Assert
    assert result_id == expected_id


# ============================================================================
# READ OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_success(
    executions_repo, mock_postgres, sample_execution_record
):
    """Test successfully retrieving execution by ID."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_execution_record

    # Act
    result = await executions_repo.get_by_id(sample_execution_record['id'])

    # Assert
    assert result is not None
    assert result['id'] == sample_execution_record['id']
    assert result['status'] == 'completed'
    assert result['duration_seconds'] == 300.5
    mock_postgres.fetchrow.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_not_found(executions_repo, mock_postgres):
    """Test retrieving non-existent execution."""
    # Arrange
    mock_postgres.fetchrow.return_value = None

    # Act
    result = await executions_repo.get_by_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_workflow_id(executions_repo, mock_postgres):
    """Test retrieving all executions for a workflow."""
    # Arrange
    workflow_id = uuid4()
    executions = [
        {
            'id': uuid4(),
            'workflow_id': workflow_id,
            'status': 'completed',
            'started_at': datetime.now() - timedelta(hours=i),
        }
        for i in range(1, 6)
    ]
    mock_postgres.fetch.return_value = executions

    # Act
    results = await executions_repo.get_by_workflow_id(workflow_id)

    # Assert
    assert len(results) == 5
    assert all(e['workflow_id'] == workflow_id for e in results)

    # Verify executions are ordered by started_at DESC
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'ORDER BY started_at DESC' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_workflow_id_with_limit(executions_repo, mock_postgres):
    """Test retrieving recent executions with limit."""
    # Arrange
    workflow_id = uuid4()
    executions = [
        {'id': uuid4(), 'workflow_id': workflow_id} for _ in range(10)
    ]
    mock_postgres.fetch.return_value = executions[:5]

    # Act
    results = await executions_repo.get_by_workflow_id(workflow_id, limit=5)

    # Assert
    assert len(results) == 5

    # Verify LIMIT is in query
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'LIMIT' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_status(executions_repo, mock_postgres):
    """Test retrieving executions by status."""
    # Arrange
    running_executions = [
        {'id': uuid4(), 'status': 'running', 'workflow_id': uuid4()}
        for _ in range(3)
    ]
    mock_postgres.fetch.return_value = running_executions

    # Act
    results = await executions_repo.get_by_status('running')

    # Assert
    assert len(results) == 3
    assert all(e['status'] == 'running' for e in results)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_recent_executions(executions_repo, mock_postgres):
    """Test retrieving recent executions across all workflows."""
    # Arrange
    recent_executions = [
        {
            'id': uuid4(),
            'workflow_id': uuid4(),
            'started_at': datetime.now() - timedelta(minutes=i * 10),
        }
        for i in range(10)
    ]
    mock_postgres.fetch.return_value = recent_executions

    # Act
    results = await executions_repo.get_recent(limit=10)

    # Assert
    assert len(results) == 10


# ============================================================================
# UPDATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_execution_success(executions_repo, mock_postgres):
    """Test successfully updating execution."""
    # Arrange
    execution_id = uuid4()
    updates = {
        'status': 'completed',
        'completed_at': datetime.now(),
        'duration_seconds': 125.8,
        'actions_completed': 5,
    }

    # Act
    success = await executions_repo.update(execution_id, updates)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_execution_status(executions_repo, mock_postgres):
    """Test updating execution status."""
    # Arrange
    execution_id = uuid4()

    # Act
    success = await executions_repo.update_status(execution_id, 'failed')

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify status update
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'status' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_complete_execution(executions_repo, mock_postgres):
    """Test marking execution as completed."""
    # Arrange
    execution_id = uuid4()
    results = {'papers_found': 42, 'papers_downloaded': 38}

    # Act
    success = await executions_repo.complete_execution(execution_id, results)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify completed_at and status are set
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'completed_at' in query.lower()
    assert 'status' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_fail_execution(executions_repo, mock_postgres):
    """Test marking execution as failed with error message."""
    # Arrange
    execution_id = uuid4()
    error_message = 'Network timeout during action 3'

    # Act
    success = await executions_repo.fail_execution(execution_id, error_message)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify error_message and status are set
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'error_message' in query.lower()
    assert 'status' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_progress(executions_repo, mock_postgres):
    """Test updating execution progress."""
    # Arrange
    execution_id = uuid4()
    actions_completed = 3
    actions_failed = 1
    total_actions = 5

    # Act
    success = await executions_repo.update_progress(
        execution_id, actions_completed, actions_failed, total_actions
    )

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify progress fields are updated
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'actions_completed' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_execution_empty_data(executions_repo, mock_postgres):
    """Test updating with empty data succeeds without DB call."""
    # Act
    success = await executions_repo.update(uuid4(), {})

    # Assert
    assert success is True
    mock_postgres.execute.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_execution_nonexistent(executions_repo, mock_postgres):
    """Test updating non-existent execution."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await executions_repo.update(uuid4(), {'status': 'completed'})

    # Assert
    assert success is False


# ============================================================================
# DELETE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_execution_success(executions_repo, mock_postgres):
    """Test successfully deleting execution."""
    # Act
    success = await executions_repo.delete(uuid4())

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_execution_nonexistent(executions_repo, mock_postgres):
    """Test deleting non-existent execution fails gracefully."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await executions_repo.delete(uuid4())

    # Assert
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_old_executions(executions_repo, mock_postgres):
    """Test deleting executions older than specified date."""
    # Arrange
    cutoff_date = datetime.now() - timedelta(days=30)

    # Act
    deleted_count = await executions_repo.delete_older_than(cutoff_date)

    # Assert
    assert deleted_count >= 0
    mock_postgres.fetchval.assert_called_once()

    # Verify date comparison in query
    call_args = mock_postgres.fetchval.call_args
    query = call_args[0][0]
    assert 'DELETE' in query
    assert 'started_at' in query.lower() or 'created_at' in query.lower()


# ============================================================================
# STATISTICS TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_execution_statistics(executions_repo, mock_postgres):
    """Test retrieving execution statistics for a workflow."""
    # Arrange
    workflow_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'workflow_id': workflow_id,
        'total_executions': 100,
        'completed_executions': 95,
        'failed_executions': 5,
        'avg_duration_seconds': 180.5,
        'median_duration_seconds': 175.0,
        'min_duration_seconds': 120.0,
        'max_duration_seconds': 300.0,
        'success_rate': 0.95,
    }

    # Act
    stats = await executions_repo.get_statistics(workflow_id)

    # Assert
    assert stats is not None
    assert stats['total_executions'] == 100
    assert stats['success_rate'] == 0.95
    assert stats['avg_duration_seconds'] == 180.5


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_all_executions_statistics(executions_repo, mock_postgres):
    """Test retrieving aggregate statistics across all workflows."""
    # Arrange
    mock_postgres.fetchrow.return_value = {
        'total_workflows': 25,
        'total_executions': 500,
        'total_completed': 475,
        'total_failed': 25,
        'avg_success_rate': 0.95,
        'avg_duration_seconds': 200.0,
    }

    # Act
    stats = await executions_repo.get_statistics()

    # Assert
    assert stats is not None
    assert stats['total_executions'] == 500
    assert stats['avg_success_rate'] == 0.95


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_execution_trends(executions_repo, mock_postgres):
    """Test retrieving execution trends over time."""
    # Arrange
    workflow_id = uuid4()
    mock_postgres.fetch.return_value = [
        {
            'date': '2024-12-01',
            'total_executions': 10,
            'completed': 9,
            'failed': 1,
        },
        {
            'date': '2024-12-02',
            'total_executions': 12,
            'completed': 11,
            'failed': 1,
        },
    ]

    # Act
    trends = await executions_repo.get_trends(
        workflow_id, days=7
    )

    # Assert
    assert len(trends) == 2


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_failure_analysis(executions_repo, mock_postgres):
    """Test analyzing failure patterns."""
    # Arrange
    workflow_id = uuid4()
    mock_postgres.fetch.return_value = [
        {'error_pattern': 'Network timeout', 'count': 15},
        {'error_pattern': 'Element not found', 'count': 8},
        {'error_pattern': 'Authentication failed', 'count': 3},
    ]

    # Act
    failures = await executions_repo.get_failure_analysis(workflow_id)

    # Assert
    assert len(failures) == 3
    assert failures[0]['error_pattern'] == 'Network timeout'
    assert failures[0]['count'] == 15


# ============================================================================
# QUERY OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_running_executions(executions_repo, mock_postgres):
    """Test retrieving all currently running executions."""
    # Arrange
    running_executions = [
        {
            'id': uuid4(),
            'workflow_id': uuid4(),
            'status': 'running',
            'started_at': datetime.now(),
        }
        for _ in range(3)
    ]
    mock_postgres.fetch.return_value = running_executions

    # Act
    results = await executions_repo.get_running_executions()

    # Assert
    assert len(results) == 3
    assert all(e['status'] == 'running' for e in results)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_stuck_executions(executions_repo, mock_postgres):
    """Test identifying stuck/stale executions."""
    # Arrange
    threshold = datetime.now() - timedelta(hours=2)
    stuck_executions = [
        {
            'id': uuid4(),
            'workflow_id': uuid4(),
            'status': 'running',
            'started_at': datetime.now() - timedelta(hours=3),
        }
    ]
    mock_postgres.fetch.return_value = stuck_executions

    # Act
    results = await executions_repo.get_stuck_executions(threshold_hours=2)

    # Assert
    assert len(results) == 1

    # Verify time comparison in query
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'status' in query.lower()
    assert 'started_at' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_executions_by_date_range(executions_repo, mock_postgres):
    """Test retrieving executions within date range."""
    # Arrange
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    executions = [
        {
            'id': uuid4(),
            'started_at': datetime.now() - timedelta(days=i),
        }
        for i in range(1, 6)
    ]
    mock_postgres.fetch.return_value = executions

    # Act
    results = await executions_repo.get_by_date_range(start_date, end_date)

    # Assert
    assert len(results) == 5


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_last_execution_for_workflow(executions_repo, mock_postgres):
    """Test retrieving most recent execution for a workflow."""
    # Arrange
    workflow_id = uuid4()
    last_execution = {
        'id': uuid4(),
        'workflow_id': workflow_id,
        'started_at': datetime.now(),
        'status': 'completed',
    }
    mock_postgres.fetchrow.return_value = last_execution

    # Act
    result = await executions_repo.get_last_execution(workflow_id)

    # Assert
    assert result is not None
    assert result['workflow_id'] == workflow_id

    # Verify ORDER BY and LIMIT 1
    call_args = mock_postgres.fetchrow.call_args
    query = call_args[0][0]
    assert 'ORDER BY started_at DESC' in query
    assert 'LIMIT 1' in query


# ============================================================================
# DURATION CALCULATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_calculate_duration_on_completion(executions_repo, mock_postgres):
    """Test duration is automatically calculated on completion."""
    # Arrange
    execution_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': execution_id,
        'started_at': datetime.now() - timedelta(minutes=5),
    }

    # Act
    success = await executions_repo.complete_execution(execution_id, {})

    # Assert
    assert success is True

    # Verify duration_seconds is calculated
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'duration_seconds' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_average_duration(executions_repo, mock_postgres):
    """Test calculating average execution duration."""
    # Arrange
    workflow_id = uuid4()
    mock_postgres.fetchval.return_value = 180.5

    # Act
    avg_duration = await executions_repo.get_average_duration(workflow_id)

    # Assert
    assert avg_duration == 180.5
    mock_postgres.fetchval.assert_called_once()


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_database_connection_error(executions_repo, mock_postgres):
    """Test handling database connection errors."""
    # Arrange
    mock_postgres.fetchrow.side_effect = Exception('Connection refused')

    # Act
    result = await executions_repo.get_by_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_foreign_key_violation(
    executions_repo, mock_postgres, sample_execution_data
):
    """Test handling foreign key constraint violations."""
    # Arrange - Invalid workflow_id
    sample_execution_data['workflow_id'] = uuid4()
    mock_postgres.fetchval.side_effect = Exception(
        'foreign key constraint violation'
    )

    # Act
    result_id = await executions_repo.create(sample_execution_data)

    # Assert
    assert result_id is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_count_executions(executions_repo, mock_postgres):
    """Test counting total executions."""
    # Arrange
    mock_postgres.fetchval.return_value = 542

    # Act
    count = await executions_repo.count()

    # Assert
    assert count == 542


@pytest.mark.asyncio
@pytest.mark.unit
async def test_exists_execution(executions_repo, mock_postgres):
    """Test checking if execution exists."""
    # Arrange
    mock_postgres.fetchval.return_value = True

    # Act
    exists = await executions_repo.exists(uuid4())

    # Assert
    assert exists is True


# ============================================================================
# CACHE BEHAVIOR TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_enabled_get_by_id(mock_postgres):
    """Test caching improves performance on repeated queries."""
    try:
        from thoth.repositories.workflow_executions_repository import (
            WorkflowExecutionsRepository,
        )
    except ImportError:
        pytest.skip('WorkflowExecutionsRepository not yet implemented')

    # Arrange
    repo_with_cache = WorkflowExecutionsRepository(
        mock_postgres, use_cache=True, cache_ttl=60
    )
    execution_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': execution_id,
        'status': 'completed',
    }

    # Act - First call should hit database
    result1 = await repo_with_cache.get_by_id(execution_id)
    # Second call should hit cache
    result2 = await repo_with_cache.get_by_id(execution_id)

    # Assert
    assert result1 == result2
    # Database should only be called once
    assert mock_postgres.fetchrow.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_invalidation_on_execution_update(mock_postgres):
    """Test cache is invalidated after execution update."""
    try:
        from thoth.repositories.workflow_executions_repository import (
            WorkflowExecutionsRepository,
        )
    except ImportError:
        pytest.skip('WorkflowExecutionsRepository not yet implemented')

    # Arrange
    repo_with_cache = WorkflowExecutionsRepository(mock_postgres, use_cache=True)
    execution_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': execution_id,
        'status': 'running',
    }

    # Act
    result1 = await repo_with_cache.get_by_id(execution_id)
    await repo_with_cache.update_status(execution_id, 'completed')

    # Update mock for new data
    mock_postgres.fetchrow.return_value = {
        'id': execution_id,
        'status': 'completed',
    }
    result2 = await repo_with_cache.get_by_id(execution_id)

    # Assert
    # Cache should be invalidated, so second query hits DB
    assert mock_postgres.fetchrow.call_count == 2


# ============================================================================
# PAGINATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_executions_with_pagination(executions_repo, mock_postgres):
    """Test listing executions with limit and offset."""
    # Arrange
    executions = [
        {'id': uuid4(), 'workflow_id': uuid4()} for _ in range(20)
    ]
    mock_postgres.fetch.return_value = executions[:10]

    # Act
    results = await executions_repo.list_all(limit=10, offset=0)

    # Assert
    assert len(results) == 10

    # Verify LIMIT in query
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'LIMIT' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_executions_with_offset(executions_repo, mock_postgres):
    """Test pagination with offset."""
    # Arrange
    mock_postgres.fetch.return_value = [
        {'id': uuid4(), 'workflow_id': uuid4()} for _ in range(10)
    ]

    # Act
    results = await executions_repo.list_all(limit=10, offset=10)

    # Assert
    assert len(results) == 10

    # Verify OFFSET is used
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'OFFSET' in query
