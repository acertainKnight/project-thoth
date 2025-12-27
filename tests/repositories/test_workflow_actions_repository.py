"""
Comprehensive tests for WorkflowActionsRepository.

This module tests action management, sequencing, workflow relationships,
and CRUD operations for browser workflow actions.
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
def actions_repo(mock_postgres):
    """Create WorkflowActionsRepository instance with mocked postgres."""
    try:
        from thoth.repositories.workflow_actions_repository import (
            WorkflowActionsRepository,
        )

        return WorkflowActionsRepository(mock_postgres, use_cache=False)
    except ImportError:
        pytest.skip('WorkflowActionsRepository not yet implemented')


@pytest.fixture
def sample_action_data():
    """Sample workflow action data for testing."""
    return {
        'workflow_id': uuid4(),
        'action_type': 'click',
        'sequence_order': 1,
        'selector': '#search-button',
        'action_value': None,
        'wait_after_ms': 1000,
        'wait_for_selector': '#results',
        'is_optional': False,
        'retry_on_failure': True,
        'max_retries': 3,
        'description': 'Click search button and wait for results',
    }


@pytest.fixture
def sample_action_record():
    """Sample action database record."""
    action_id = uuid4()
    workflow_id = uuid4()
    return {
        'id': action_id,
        'workflow_id': workflow_id,
        'action_type': 'click',
        'sequence_order': 1,
        'selector': '#search-button',
        'action_value': None,
        'wait_after_ms': 1000,
        'wait_for_selector': '#results',
        'is_optional': False,
        'retry_on_failure': True,
        'max_retries': 3,
        'description': 'Click search button and wait for results',
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
    }


# ============================================================================
# CREATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_action_success(actions_repo, mock_postgres, sample_action_data):
    """Test successful action creation."""
    # Arrange
    expected_id = uuid4()
    mock_postgres.fetchval.return_value = expected_id

    # Act
    result_id = await actions_repo.create(sample_action_data)

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
async def test_create_action_missing_workflow_id(actions_repo, mock_postgres):
    """Test creating action without workflow_id fails."""
    # Arrange
    incomplete_data = {'action_type': 'click', 'sequence_order': 1}
    mock_postgres.fetchval.side_effect = Exception(
        'null value in column "workflow_id"'
    )

    # Act
    result_id = await actions_repo.create(incomplete_data)

    # Assert
    assert result_id is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_multiple_actions_in_sequence(actions_repo, mock_postgres):
    """Test creating multiple actions with proper sequencing."""
    # Arrange
    workflow_id = uuid4()
    actions = [
        {'workflow_id': workflow_id, 'action_type': 'navigate', 'sequence_order': 1},
        {'workflow_id': workflow_id, 'action_type': 'click', 'sequence_order': 2},
        {'workflow_id': workflow_id, 'action_type': 'input', 'sequence_order': 3},
    ]
    mock_postgres.fetchval.side_effect = [uuid4() for _ in actions]

    # Act
    results = [await actions_repo.create(action) for action in actions]

    # Assert
    assert all(result is not None for result in results)
    assert mock_postgres.fetchval.call_count == 3


# ============================================================================
# READ OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_success(actions_repo, mock_postgres, sample_action_record):
    """Test successfully retrieving action by ID."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_action_record

    # Act
    result = await actions_repo.get_by_id(sample_action_record['id'])

    # Assert
    assert result is not None
    assert result['id'] == sample_action_record['id']
    assert result['action_type'] == 'click'
    mock_postgres.fetchrow.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_not_found(actions_repo, mock_postgres):
    """Test retrieving non-existent action."""
    # Arrange
    mock_postgres.fetchrow.return_value = None

    # Act
    result = await actions_repo.get_by_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_workflow_id(actions_repo, mock_postgres):
    """Test retrieving all actions for a workflow."""
    # Arrange
    workflow_id = uuid4()
    actions = [
        {
            'id': uuid4(),
            'workflow_id': workflow_id,
            'action_type': f'action_{i}',
            'sequence_order': i,
        }
        for i in range(1, 6)
    ]
    mock_postgres.fetch.return_value = actions

    # Act
    results = await actions_repo.get_by_workflow_id(workflow_id)

    # Assert
    assert len(results) == 5
    assert all(a['workflow_id'] == workflow_id for a in results)

    # Verify actions are ordered by sequence
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'ORDER BY sequence_order' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_workflow_id_empty(actions_repo, mock_postgres):
    """Test retrieving actions for workflow with no actions."""
    # Arrange
    mock_postgres.fetch.return_value = []

    # Act
    results = await actions_repo.get_by_workflow_id(uuid4())

    # Assert
    assert len(results) == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_action_type(actions_repo, mock_postgres):
    """Test retrieving actions by type."""
    # Arrange
    workflow_id = uuid4()
    click_actions = [
        {
            'id': uuid4(),
            'workflow_id': workflow_id,
            'action_type': 'click',
            'sequence_order': i,
        }
        for i in range(1, 4)
    ]
    mock_postgres.fetch.return_value = click_actions

    # Act
    results = await actions_repo.get_by_action_type(workflow_id, 'click')

    # Assert
    assert len(results) == 3
    assert all(a['action_type'] == 'click' for a in results)


# ============================================================================
# UPDATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_action_success(actions_repo, mock_postgres):
    """Test successfully updating action."""
    # Arrange
    action_id = uuid4()
    updates = {
        'selector': '#new-selector',
        'wait_after_ms': 2000,
        'description': 'Updated description',
    }

    # Act
    success = await actions_repo.update(action_id, updates)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_action_sequence_order(actions_repo, mock_postgres):
    """Test updating action sequence order."""
    # Arrange
    action_id = uuid4()
    updates = {'sequence_order': 5}

    # Act
    success = await actions_repo.update(action_id, updates)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_action_empty_data(actions_repo, mock_postgres):
    """Test updating with empty data succeeds without DB call."""
    # Act
    success = await actions_repo.update(uuid4(), {})

    # Assert
    assert success is True
    mock_postgres.execute.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_action_nonexistent(actions_repo, mock_postgres):
    """Test updating non-existent action."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await actions_repo.update(uuid4(), {'selector': '#new'})

    # Assert
    assert success is False


# ============================================================================
# DELETE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_action_success(actions_repo, mock_postgres):
    """Test successfully deleting action."""
    # Act
    success = await actions_repo.delete(uuid4())

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_action_nonexistent(actions_repo, mock_postgres):
    """Test deleting non-existent action fails gracefully."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await actions_repo.delete(uuid4())

    # Assert
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_all_actions_for_workflow(actions_repo, mock_postgres):
    """Test deleting all actions for a specific workflow."""
    # Arrange
    workflow_id = uuid4()

    # Act
    success = await actions_repo.delete_by_workflow_id(workflow_id)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify workflow_id is in WHERE clause
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'workflow_id' in query.lower()
    assert 'DELETE' in query


# ============================================================================
# SEQUENCE MANAGEMENT TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_reorder_actions(actions_repo, mock_postgres):
    """Test reordering action sequences."""
    # Arrange
    workflow_id = uuid4()
    action_ids = [uuid4() for _ in range(5)]
    new_order = {action_ids[i]: i + 1 for i in range(5)}

    # Mock multiple execute calls for each update
    mock_postgres.execute.return_value = None

    # Act
    success = await actions_repo.reorder_actions(workflow_id, new_order)

    # Assert
    assert success is True
    # Should have called execute multiple times (once per action)
    assert mock_postgres.execute.call_count >= len(action_ids)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_insert_action_at_position(actions_repo, mock_postgres):
    """Test inserting action at specific position in sequence."""
    # Arrange
    workflow_id = uuid4()
    new_action_data = {
        'workflow_id': workflow_id,
        'action_type': 'wait',
        'sequence_order': 3,  # Insert at position 3
    }

    # Mock getting existing actions
    existing_actions = [
        {'id': uuid4(), 'sequence_order': i} for i in range(1, 6)
    ]
    mock_postgres.fetch.return_value = existing_actions
    mock_postgres.fetchval.return_value = uuid4()

    # Act
    new_id = await actions_repo.insert_at_position(new_action_data)

    # Assert
    assert new_id is not None
    # Should reorder subsequent actions
    assert mock_postgres.execute.call_count > 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_action_count_by_workflow(actions_repo, mock_postgres):
    """Test counting actions for a workflow."""
    # Arrange
    mock_postgres.fetchval.return_value = 12

    # Act
    count = await actions_repo.count_by_workflow(uuid4())

    # Assert
    assert count == 12
    mock_postgres.fetchval.assert_called_once()


# ============================================================================
# VALIDATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_validate_action_sequence(actions_repo, mock_postgres):
    """Test validating action sequence has no gaps."""
    # Arrange
    workflow_id = uuid4()
    valid_actions = [
        {'id': uuid4(), 'sequence_order': i} for i in range(1, 6)
    ]
    mock_postgres.fetch.return_value = valid_actions

    # Act
    is_valid = await actions_repo.validate_sequence(workflow_id)

    # Assert
    assert is_valid is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_validate_action_sequence_with_gap(actions_repo, mock_postgres):
    """Test detecting gaps in action sequence."""
    # Arrange
    workflow_id = uuid4()
    # Gap: sequence jumps from 3 to 5
    invalid_actions = [
        {'id': uuid4(), 'sequence_order': 1},
        {'id': uuid4(), 'sequence_order': 2},
        {'id': uuid4(), 'sequence_order': 3},
        {'id': uuid4(), 'sequence_order': 5},  # Gap!
    ]
    mock_postgres.fetch.return_value = invalid_actions

    # Act
    is_valid = await actions_repo.validate_sequence(workflow_id)

    # Assert
    assert is_valid is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_validate_action_sequence_duplicate_order(actions_repo, mock_postgres):
    """Test detecting duplicate sequence orders."""
    # Arrange
    workflow_id = uuid4()
    # Duplicate: two actions with sequence_order = 3
    invalid_actions = [
        {'id': uuid4(), 'sequence_order': 1},
        {'id': uuid4(), 'sequence_order': 2},
        {'id': uuid4(), 'sequence_order': 3},
        {'id': uuid4(), 'sequence_order': 3},  # Duplicate!
        {'id': uuid4(), 'sequence_order': 4},
    ]
    mock_postgres.fetch.return_value = invalid_actions

    # Act
    is_valid = await actions_repo.validate_sequence(workflow_id)

    # Assert
    assert is_valid is False


# ============================================================================
# BATCH OPERATIONS TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_bulk_create_actions(actions_repo, mock_postgres):
    """Test bulk creating multiple actions."""
    # Arrange
    workflow_id = uuid4()
    actions_data = [
        {
            'workflow_id': workflow_id,
            'action_type': f'action_{i}',
            'sequence_order': i,
        }
        for i in range(1, 11)
    ]
    mock_postgres.fetchval.side_effect = [uuid4() for _ in actions_data]

    # Act
    results = await actions_repo.bulk_create(actions_data)

    # Assert
    assert len(results) == 10
    assert all(result is not None for result in results)
    assert mock_postgres.fetchval.call_count == 10


@pytest.mark.asyncio
@pytest.mark.unit
async def test_bulk_update_actions(actions_repo, mock_postgres):
    """Test bulk updating multiple actions."""
    # Arrange
    updates = {
        uuid4(): {'wait_after_ms': 1000},
        uuid4(): {'wait_after_ms': 2000},
        uuid4(): {'wait_after_ms': 3000},
    }

    # Act
    success = await actions_repo.bulk_update(updates)

    # Assert
    assert success is True
    assert mock_postgres.execute.call_count == 3


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_database_connection_error(actions_repo, mock_postgres):
    """Test handling database connection errors."""
    # Arrange
    mock_postgres.fetchrow.side_effect = Exception('Connection refused')

    # Act
    result = await actions_repo.get_by_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_foreign_key_violation(actions_repo, mock_postgres, sample_action_data):
    """Test handling foreign key constraint violations."""
    # Arrange - Invalid workflow_id
    sample_action_data['workflow_id'] = uuid4()
    mock_postgres.fetchval.side_effect = Exception(
        'foreign key constraint violation'
    )

    # Act
    result_id = await actions_repo.create(sample_action_data)

    # Assert
    assert result_id is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_count_actions(actions_repo, mock_postgres):
    """Test counting total actions."""
    # Arrange
    mock_postgres.fetchval.return_value = 156

    # Act
    count = await actions_repo.count()

    # Assert
    assert count == 156


@pytest.mark.asyncio
@pytest.mark.unit
async def test_exists_action(actions_repo, mock_postgres):
    """Test checking if action exists."""
    # Arrange
    mock_postgres.fetchval.return_value = True

    # Act
    exists = await actions_repo.exists(uuid4())

    # Assert
    assert exists is True


# ============================================================================
# CACHE BEHAVIOR TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_enabled_get_by_workflow(mock_postgres):
    """Test caching improves performance for workflow action queries."""
    try:
        from thoth.repositories.workflow_actions_repository import (
            WorkflowActionsRepository,
        )
    except ImportError:
        pytest.skip('WorkflowActionsRepository not yet implemented')

    # Arrange
    repo_with_cache = WorkflowActionsRepository(
        mock_postgres, use_cache=True, cache_ttl=60
    )
    workflow_id = uuid4()
    actions = [{'id': uuid4(), 'action_type': 'click'}]
    mock_postgres.fetch.return_value = actions

    # Act - First call should hit database
    result1 = await repo_with_cache.get_by_workflow_id(workflow_id)
    # Second call should hit cache
    result2 = await repo_with_cache.get_by_workflow_id(workflow_id)

    # Assert
    assert result1 == result2
    # Database should only be called once
    assert mock_postgres.fetch.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_invalidation_on_action_update(mock_postgres):
    """Test cache is invalidated after action update."""
    try:
        from thoth.repositories.workflow_actions_repository import (
            WorkflowActionsRepository,
        )
    except ImportError:
        pytest.skip('WorkflowActionsRepository not yet implemented')

    # Arrange
    repo_with_cache = WorkflowActionsRepository(mock_postgres, use_cache=True)
    action_id = uuid4()
    workflow_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': action_id,
        'workflow_id': workflow_id,
        'selector': '#old',
    }

    # Act
    result1 = await repo_with_cache.get_by_id(action_id)
    await repo_with_cache.update(action_id, {'selector': '#new'})

    # Update mock for new data
    mock_postgres.fetchrow.return_value = {
        'id': action_id,
        'workflow_id': workflow_id,
        'selector': '#new',
    }
    result2 = await repo_with_cache.get_by_id(action_id)

    # Assert
    # Cache should be invalidated, so second query hits DB
    assert mock_postgres.fetchrow.call_count == 2
