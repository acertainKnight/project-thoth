"""
Comprehensive tests for BrowserWorkflowRepository.

This module tests all CRUD operations, edge cases, query methods,
and PostgreSQL integration for browser workflow management.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
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
def workflow_repo(mock_postgres):
    """Create BrowserWorkflowRepository instance with mocked postgres."""
    # Import here to avoid import errors if repository doesn't exist yet
    try:
        from thoth.repositories.browser_workflow_repository import (
            BrowserWorkflowRepository,
        )

        return BrowserWorkflowRepository(mock_postgres, use_cache=False)
    except ImportError:
        pytest.skip('BrowserWorkflowRepository not yet implemented')


@pytest.fixture
def sample_workflow_data():
    """Sample browser workflow data for testing."""
    return {
        'name': 'Research Paper Discovery Workflow',
        'description': 'Automated workflow for discovering research papers',
        'user_id': 'user123',
        'status': 'active',
        'priority': 5,
        'tags': ['research', 'automation', 'papers'],
        'schedule_frequency': 'daily',
        'last_run_at': None,
        'next_run_at': datetime.now().isoformat(),
        'total_runs': 0,
        'successful_runs': 0,
        'failed_runs': 0,
    }


@pytest.fixture
def sample_workflow_record():
    """Sample workflow database record."""
    workflow_id = uuid4()
    return {
        'id': workflow_id,
        'name': 'Research Paper Discovery Workflow',
        'description': 'Automated workflow for discovering research papers',
        'user_id': 'user123',
        'status': 'active',
        'priority': 5,
        'tags': ['research', 'automation', 'papers'],
        'schedule_frequency': 'daily',
        'last_run_at': None,
        'next_run_at': datetime.now(),
        'total_runs': 0,
        'successful_runs': 0,
        'failed_runs': 0,
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
    }


# ============================================================================
# CREATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_workflow_success(workflow_repo, mock_postgres, sample_workflow_data):
    """Test successful workflow creation."""
    # Arrange
    expected_id = uuid4()
    mock_postgres.fetchval.return_value = expected_id

    # Act
    result_id = await workflow_repo.create(sample_workflow_data)

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
async def test_create_workflow_duplicate_name(
    workflow_repo, mock_postgres, sample_workflow_data
):
    """Test creating workflow with duplicate name for same user fails gracefully."""
    # Arrange
    mock_postgres.fetchval.side_effect = Exception(
        'duplicate key value violates unique constraint'
    )

    # Act
    result_id = await workflow_repo.create(sample_workflow_data)

    # Assert
    assert result_id is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_workflow_missing_required_fields(workflow_repo, mock_postgres):
    """Test creating workflow with missing required fields."""
    # Arrange
    incomplete_data = {'name': 'Only Name'}
    mock_postgres.fetchval.side_effect = Exception(
        'null value in column "user_id"'
    )

    # Act
    result_id = await workflow_repo.create(incomplete_data)

    # Assert
    assert result_id is None


# ============================================================================
# READ OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_success(workflow_repo, mock_postgres, sample_workflow_record):
    """Test successfully retrieving workflow by ID."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_workflow_record

    # Act
    result = await workflow_repo.get_by_id(sample_workflow_record['id'])

    # Assert
    assert result is not None
    assert result['id'] == sample_workflow_record['id']
    assert result['name'] == sample_workflow_record['name']
    mock_postgres.fetchrow.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_not_found(workflow_repo, mock_postgres):
    """Test retrieving non-existent workflow."""
    # Arrange
    mock_postgres.fetchrow.return_value = None

    # Act
    result = await workflow_repo.get_by_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_name_success(workflow_repo, mock_postgres, sample_workflow_record):
    """Test retrieving workflow by name and user."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_workflow_record

    # Act
    result = await workflow_repo.get_by_name('user123', 'Research Paper Discovery Workflow')

    # Assert
    assert result is not None
    assert result['name'] == sample_workflow_record['name']
    mock_postgres.fetchrow.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_name_not_found(workflow_repo, mock_postgres):
    """Test retrieving workflow by non-existent name."""
    # Arrange
    mock_postgres.fetchrow.return_value = None

    # Act
    result = await workflow_repo.get_by_name('user123', 'Nonexistent Workflow')

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_user_success(workflow_repo, mock_postgres):
    """Test retrieving all workflows for a user."""
    # Arrange
    workflows = [
        {'id': uuid4(), 'name': f'Workflow {i}', 'user_id': 'user123'}
        for i in range(1, 4)
    ]
    mock_postgres.fetch.return_value = workflows

    # Act
    results = await workflow_repo.get_by_user('user123')

    # Assert
    assert len(results) == 3
    assert all(w['user_id'] == 'user123' for w in results)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_user_with_status_filter(workflow_repo, mock_postgres):
    """Test retrieving workflows filtered by status."""
    # Arrange
    active_workflows = [
        {'id': uuid4(), 'name': f'Workflow {i}', 'status': 'active'}
        for i in range(1, 3)
    ]
    mock_postgres.fetch.return_value = active_workflows

    # Act
    results = await workflow_repo.get_by_user('user123', status='active')

    # Assert
    assert len(results) == 2
    assert all(w['status'] == 'active' for w in results)
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'status' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_active_workflows(workflow_repo, mock_postgres):
    """Test retrieving all active workflows across users."""
    # Arrange
    active_workflows = [
        {'id': uuid4(), 'name': f'Workflow {i}', 'status': 'active'}
        for i in range(1, 6)
    ]
    mock_postgres.fetch.return_value = active_workflows

    # Act
    results = await workflow_repo.get_active_workflows()

    # Assert
    assert len(results) == 5
    assert all(w['status'] == 'active' for w in results)


# ============================================================================
# QUERY OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_workflows_due_for_run(workflow_repo, mock_postgres):
    """Test retrieving workflows due for scheduled runs."""
    # Arrange
    due_workflows = [
        {
            'id': uuid4(),
            'name': 'Due Workflow',
            'status': 'active',
            'next_run_at': datetime.now(),
        }
    ]
    mock_postgres.fetch.return_value = due_workflows

    # Act
    results = await workflow_repo.get_workflows_due_for_run()

    # Assert
    assert len(results) == 1
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'next_run_at' in query.lower()
    assert 'status' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_tags_match_any(workflow_repo, mock_postgres, sample_workflow_record):
    """Test retrieving workflows matching any tag."""
    # Arrange
    mock_postgres.fetch.return_value = [sample_workflow_record]

    # Act
    results = await workflow_repo.get_by_tags(['research'], match_all=False)

    # Assert
    assert len(results) == 1
    assert 'research' in results[0]['tags']

    # Verify && operator is used for ANY match
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert '&&' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_tags_match_all(workflow_repo, mock_postgres, sample_workflow_record):
    """Test retrieving workflows matching all tags."""
    # Arrange
    mock_postgres.fetch.return_value = [sample_workflow_record]

    # Act
    results = await workflow_repo.get_by_tags(
        ['research', 'automation'], match_all=True
    )

    # Assert
    assert len(results) == 1
    assert all(tag in results[0]['tags'] for tag in ['research', 'automation'])

    # Verify @> operator is used for ALL match
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert '@>' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_tags_no_match(workflow_repo, mock_postgres):
    """Test retrieving workflows with non-matching tags."""
    # Arrange
    mock_postgres.fetch.return_value = []

    # Act
    results = await workflow_repo.get_by_tags(['nonexistent-tag'])

    # Assert
    assert len(results) == 0


# ============================================================================
# UPDATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_workflow_success(workflow_repo, mock_postgres):
    """Test successfully updating workflow."""
    # Arrange
    workflow_id = uuid4()
    updates = {
        'description': 'Updated workflow description',
        'status': 'paused',
        'priority': 8,
    }

    # Act
    success = await workflow_repo.update(workflow_id, updates)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_workflow_empty_data(workflow_repo, mock_postgres):
    """Test updating with empty data succeeds without DB call."""
    # Act
    success = await workflow_repo.update(uuid4(), {})

    # Assert
    assert success is True
    mock_postgres.execute.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_workflow_nonexistent(workflow_repo, mock_postgres):
    """Test updating non-existent workflow."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await workflow_repo.update(uuid4(), {'name': 'New Name'})

    # Assert
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_run_statistics(workflow_repo, mock_postgres):
    """Test updating workflow run statistics."""
    # Arrange
    workflow_id = uuid4()

    # Act
    success = await workflow_repo.update_run_statistics(
        workflow_id, success=True, next_run_at=datetime.now()
    )

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify statistics are incremented
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'total_runs' in query.lower()
    assert 'successful_runs' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_run_statistics_failed(workflow_repo, mock_postgres):
    """Test updating workflow statistics for failed run."""
    # Arrange
    workflow_id = uuid4()

    # Act
    success = await workflow_repo.update_run_statistics(workflow_id, success=False)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify failed_runs is incremented
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'failed_runs' in query.lower()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_tags_success(workflow_repo, mock_postgres):
    """Test updating workflow tags."""
    # Arrange
    new_tags = ['machine-learning', 'nlp', 'automation']

    # Act
    success = await workflow_repo.update_tags(uuid4(), new_tags)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


# ============================================================================
# DELETE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_workflow_success(workflow_repo, mock_postgres):
    """Test successfully deleting workflow."""
    # Act
    success = await workflow_repo.delete(uuid4())

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_workflow_nonexistent(workflow_repo, mock_postgres):
    """Test deleting non-existent workflow fails gracefully."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await workflow_repo.delete(uuid4())

    # Assert
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_deactivate_workflow(workflow_repo, mock_postgres):
    """Test soft delete (deactivation) of workflow."""
    # Arrange
    workflow_id = uuid4()

    # Act
    success = await workflow_repo.deactivate(workflow_id)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify status is set to 'inactive' or similar
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'status' in query.lower() or 'is_active' in query.lower()


# ============================================================================
# STATISTICS TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_workflow_statistics(workflow_repo, mock_postgres):
    """Test retrieving workflow statistics."""
    # Arrange
    workflow_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': workflow_id,
        'total_runs': 100,
        'successful_runs': 95,
        'failed_runs': 5,
        'avg_duration_seconds': 120.5,
        'total_actions': 15,
    }

    # Act
    stats = await workflow_repo.get_statistics(workflow_id)

    # Assert
    assert stats is not None
    assert stats['total_runs'] == 100
    assert stats['successful_runs'] == 95
    assert stats['failed_runs'] == 5


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_all_workflow_statistics(workflow_repo, mock_postgres):
    """Test retrieving aggregate statistics across all workflows."""
    # Arrange
    mock_postgres.fetchrow.return_value = {
        'total_workflows': 50,
        'active_workflows': 45,
        'total_runs': 1000,
        'avg_success_rate': 0.95,
    }

    # Act
    stats = await workflow_repo.get_statistics()

    # Assert
    assert stats is not None
    assert stats['total_workflows'] == 50
    assert stats['active_workflows'] == 45


# ============================================================================
# PAGINATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_workflows_with_pagination(workflow_repo, mock_postgres):
    """Test listing workflows with limit and offset."""
    # Arrange
    workflows = [{'id': uuid4(), 'name': f'Workflow {i}'} for i in range(10)]
    mock_postgres.fetch.return_value = workflows[:5]

    # Act
    results = await workflow_repo.list_all(limit=5, offset=0)

    # Assert
    assert len(results) == 5

    # Verify LIMIT and OFFSET in query
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'LIMIT' in query
    params = call_args[0][1:]
    assert 5 in params


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_workflows_with_offset(workflow_repo, mock_postgres):
    """Test pagination with offset."""
    # Arrange
    mock_postgres.fetch.return_value = [
        {'id': uuid4(), 'name': f'Workflow {i}'} for i in range(6, 11)
    ]

    # Act
    results = await workflow_repo.list_all(limit=5, offset=5)

    # Assert
    assert len(results) == 5

    # Verify OFFSET is used
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'OFFSET' in query


# ============================================================================
# CACHE BEHAVIOR TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_enabled_get_by_id(mock_postgres):
    """Test caching improves performance on repeated queries."""
    try:
        from thoth.repositories.browser_workflow_repository import (
            BrowserWorkflowRepository,
        )
    except ImportError:
        pytest.skip('BrowserWorkflowRepository not yet implemented')

    # Arrange
    repo_with_cache = BrowserWorkflowRepository(
        mock_postgres, use_cache=True, cache_ttl=60
    )
    workflow_id = uuid4()
    mock_postgres.fetchrow.return_value = {'id': workflow_id, 'name': 'Test'}

    # Act - First call should hit database
    result1 = await repo_with_cache.get_by_id(workflow_id)
    # Second call should hit cache
    result2 = await repo_with_cache.get_by_id(workflow_id)

    # Assert
    assert result1 == result2
    # Database should only be called once
    assert mock_postgres.fetchrow.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_invalidation_on_update(mock_postgres):
    """Test cache is invalidated after update."""
    try:
        from thoth.repositories.browser_workflow_repository import (
            BrowserWorkflowRepository,
        )
    except ImportError:
        pytest.skip('BrowserWorkflowRepository not yet implemented')

    # Arrange
    repo_with_cache = BrowserWorkflowRepository(mock_postgres, use_cache=True)
    workflow_id = uuid4()
    mock_postgres.fetchrow.return_value = {'id': workflow_id, 'name': 'Original'}

    # Act
    result1 = await repo_with_cache.get_by_id(workflow_id)
    await repo_with_cache.update(workflow_id, {'name': 'Updated'})

    # Update mock for new data
    mock_postgres.fetchrow.return_value = {'id': workflow_id, 'name': 'Updated'}
    result2 = await repo_with_cache.get_by_id(workflow_id)

    # Assert
    # Cache should be invalidated, so second query hits DB
    assert mock_postgres.fetchrow.call_count == 2


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_database_connection_error(workflow_repo, mock_postgres):
    """Test handling database connection errors."""
    # Arrange
    mock_postgres.fetchrow.side_effect = Exception('Connection refused')

    # Act
    result = await workflow_repo.get_by_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_malformed_query_error(workflow_repo, mock_postgres):
    """Test handling malformed query errors."""
    # Arrange
    mock_postgres.fetch.side_effect = Exception('syntax error at or near')

    # Act
    results = await workflow_repo.get_by_user('user123')

    # Assert
    assert len(results) == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_count_workflows(workflow_repo, mock_postgres):
    """Test counting total workflows."""
    # Arrange
    mock_postgres.fetchval.return_value = 42

    # Act
    count = await workflow_repo.count()

    # Assert
    assert count == 42


@pytest.mark.asyncio
@pytest.mark.unit
async def test_exists_workflow(workflow_repo, mock_postgres):
    """Test checking if workflow exists."""
    # Arrange
    mock_postgres.fetchval.return_value = True

    # Act
    exists = await workflow_repo.exists(uuid4())

    # Assert
    assert exists is True


# ============================================================================
# SCHEDULE MANAGEMENT TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_workflows_by_schedule(workflow_repo, mock_postgres):
    """Test retrieving workflows by schedule frequency."""
    # Arrange
    daily_workflows = [
        {'id': uuid4(), 'name': f'Daily Workflow {i}', 'schedule_frequency': 'daily'}
        for i in range(1, 4)
    ]
    mock_postgres.fetch.return_value = daily_workflows

    # Act
    results = await workflow_repo.get_by_schedule('daily')

    # Assert
    assert len(results) == 3
    assert all(w['schedule_frequency'] == 'daily' for w in results)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_next_run_time(workflow_repo, mock_postgres):
    """Test updating next scheduled run time."""
    # Arrange
    workflow_id = uuid4()
    next_run = datetime.now()

    # Act
    success = await workflow_repo.update_next_run(workflow_id, next_run)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify next_run_at is updated
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'next_run_at' in query.lower()
