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
        'name': 'Nature Journal Workflow',
        'description': 'Automated workflow for Nature journal',
        'website_domain': 'nature.com',
        'start_url': 'https://www.nature.com/search',
        'extraction_rules': {
            'article_list_selector': '.article',
            'title_selector': 'h2.title',
            'author_selector': '.authors',
            'abstract_selector': '.abstract'
        },
        'requires_authentication': False,
        'is_active': True,
    }


@pytest.fixture
def sample_workflow_record():
    """Sample workflow database record."""
    workflow_id = uuid4()
    return {
        'id': workflow_id,
        'name': 'Nature Journal Workflow',
        'description': 'Automated workflow for Nature journal',
        'website_domain': 'nature.com',
        'start_url': 'https://www.nature.com/search',
        'extraction_rules': {
            'article_list_selector': '.article',
            'title_selector': 'h2.title',
            'author_selector': '.authors',
            'abstract_selector': '.abstract'
        },
        'requires_authentication': False,
        'is_active': True,
        'health_status': 'healthy',
        'total_executions': 0,
        'successful_executions': 0,
        'failed_executions': 0,
        'total_articles_extracted': 0,
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
        'null value in column "website_domain"'
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
    """Test retrieving workflow by name."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_workflow_record

    # Act
    result = await workflow_repo.get_by_name('Nature Journal Workflow')

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
    result = await workflow_repo.get_by_name('Nonexistent Workflow')

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_active_workflows(workflow_repo, mock_postgres):
    """Test retrieving all active workflows."""
    # Arrange
    active_workflows = [
        {'id': uuid4(), 'name': f'Workflow {i}', 'is_active': True}
        for i in range(1, 6)
    ]
    mock_postgres.fetch.return_value = active_workflows

    # Act
    results = await workflow_repo.get_active_workflows()

    # Assert
    assert len(results) == 5
    assert all(w['is_active'] is True for w in results)


# ============================================================================
# QUERY OPERATION TESTS
# ============================================================================


# ============================================================================
# REMOVED TESTS - Schema doesn't support these features
# ============================================================================
# - test_get_workflows_due_for_run (no next_run_at field)
# - test_get_by_tags_* (no tags field)
# - test_get_by_user_* (no user_id field)
# - test_get_by_schedule (no schedule_frequency field)
# - test_update_next_run_time (no next_run_at field)
# - test_update_tags_* (no tags field)


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
        'is_active': False,
        'health_status': 'maintenance',
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
async def test_update_execution_statistics(workflow_repo, mock_postgres):
    """Test updating workflow execution statistics after run."""
    # Arrange
    workflow_id = uuid4()
    mock_postgres.execute.return_value = None

    # Act - using actual method signature: update_statistics(workflow_id, success, articles_found, duration_ms)
    await workflow_repo.update_statistics(
        workflow_id, success=True, articles_found=25, duration_ms=15000
    )

    # Assert - update_statistics doesn't return anything, just verify it was called
    mock_postgres.execute.assert_called()

    # Verify statistics are updated
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'total_executions' in query.lower()
    assert 'successful_executions' in query.lower()


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

    # Verify is_active is set to FALSE
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'is_active' in query.lower()


# ============================================================================
# STATISTICS TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_workflow_statistics(workflow_repo, mock_postgres):
    """Test retrieving overall workflow statistics (not per-workflow)."""
    # Arrange
    mock_postgres.fetchrow.return_value = {
        'total_workflows': 10,
        'active_workflows': 8,
        'total_executions': 100,
        'successful_executions': 95,
        'failed_executions': 5,
        'total_articles_extracted': 450,
        'avg_execution_time_ms': 12050,
    }

    # Act - get_statistics() returns OVERALL stats, not per-workflow
    stats = await workflow_repo.get_statistics()

    # Assert
    assert stats is not None
    assert stats['total_workflows'] == 10
    assert stats['total_executions'] == 100
    assert stats['successful_executions'] == 95
    assert stats['failed_executions'] == 5


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
    results = await workflow_repo.list_all()

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
# REMOVED SCHEDULE MANAGEMENT TESTS
# ============================================================================
# Schema doesn't support schedule_frequency or next_run_at fields
# These features are not in the current database schema
