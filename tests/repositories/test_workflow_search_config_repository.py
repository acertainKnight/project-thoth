"""
Comprehensive tests for WorkflowSearchConfigRepository.

This module tests search configuration management, query patterns,
filter management, and CRUD operations for workflow search configurations.
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
def search_config_repo(mock_postgres):
    """Create WorkflowSearchConfigRepository instance with mocked postgres."""
    try:
        from thoth.repositories.workflow_search_config_repository import (
            WorkflowSearchConfigRepository,
        )

        return WorkflowSearchConfigRepository(mock_postgres, use_cache=False)
    except ImportError:
        pytest.skip('WorkflowSearchConfigRepository not yet implemented')


@pytest.fixture
def sample_search_config_data():
    """Sample search configuration data for testing."""
    return {
        'workflow_id': uuid4(),
        'search_query': 'machine learning transformers',
        'search_url': 'https://arxiv.org/search/',
        'keywords': ['machine learning', 'transformers', 'neural networks'],
        'authors': ['Geoffrey Hinton', 'Yoshua Bengio'],
        'date_range_start': '2020-01-01',
        'date_range_end': '2024-12-31',
        'min_citations': 10,
        'max_results': 100,
        'sort_by': 'relevance',
        'filters': {
            'subject': ['cs.AI', 'cs.LG'],
            'venue': ['NeurIPS', 'ICML', 'ICLR'],
            'language': 'en',
        },
        'advanced_search': True,
    }


@pytest.fixture
def sample_search_config_record():
    """Sample search config database record."""
    config_id = uuid4()
    workflow_id = uuid4()
    return {
        'id': config_id,
        'workflow_id': workflow_id,
        'search_query': 'machine learning transformers',
        'search_url': 'https://arxiv.org/search/',
        'keywords': ['machine learning', 'transformers', 'neural networks'],
        'authors': ['Geoffrey Hinton', 'Yoshua Bengio'],
        'date_range_start': '2020-01-01',
        'date_range_end': '2024-12-31',
        'min_citations': 10,
        'max_results': 100,
        'sort_by': 'relevance',
        'filters': {
            'subject': ['cs.AI', 'cs.LG'],
            'venue': ['NeurIPS', 'ICML', 'ICLR'],
            'language': 'en',
        },
        'advanced_search': True,
        'created_at': datetime.now(),
        'updated_at': datetime.now(),
    }


# ============================================================================
# CREATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_search_config_success(
    search_config_repo, mock_postgres, sample_search_config_data
):
    """Test successful search configuration creation."""
    # Arrange
    expected_id = uuid4()
    mock_postgres.fetchval.return_value = expected_id

    # Act
    result_id = await search_config_repo.create(sample_search_config_data)

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
async def test_create_search_config_missing_workflow_id(
    search_config_repo, mock_postgres
):
    """Test creating search config without workflow_id fails."""
    # Arrange
    incomplete_data = {'search_query': 'test query'}
    mock_postgres.fetchval.side_effect = Exception(
        'null value in column "workflow_id"'
    )

    # Act
    result_id = await search_config_repo.create(incomplete_data)

    # Assert
    assert result_id is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_search_config_with_complex_filters(
    search_config_repo, mock_postgres
):
    """Test creating search config with complex JSONB filters."""
    # Arrange
    config_data = {
        'workflow_id': uuid4(),
        'search_query': 'test',
        'filters': {
            'boolean_logic': {'AND': ['term1', 'term2'], 'NOT': ['term3']},
            'metadata': {'peer_reviewed': True, 'open_access': True},
            'citation_range': {'min': 5, 'max': 1000},
        },
    }
    expected_id = uuid4()
    mock_postgres.fetchval.return_value = expected_id

    # Act
    result_id = await search_config_repo.create(config_data)

    # Assert
    assert result_id == expected_id


# ============================================================================
# READ OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_success(
    search_config_repo, mock_postgres, sample_search_config_record
):
    """Test successfully retrieving search config by ID."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_search_config_record

    # Act
    result = await search_config_repo.get_by_id(sample_search_config_record['id'])

    # Assert
    assert result is not None
    assert result['id'] == sample_search_config_record['id']
    assert result['search_query'] == 'machine learning transformers'
    mock_postgres.fetchrow.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_not_found(search_config_repo, mock_postgres):
    """Test retrieving non-existent search config."""
    # Arrange
    mock_postgres.fetchrow.return_value = None

    # Act
    result = await search_config_repo.get_by_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_workflow_id_success(search_config_repo, mock_postgres):
    """Test retrieving search config by workflow ID."""
    # Arrange
    workflow_id = uuid4()
    config = {
        'id': uuid4(),
        'workflow_id': workflow_id,
        'search_query': 'test query',
    }
    mock_postgres.fetchrow.return_value = config

    # Act
    result = await search_config_repo.get_by_workflow_id(workflow_id)

    # Assert
    assert result is not None
    assert result['workflow_id'] == workflow_id


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_workflow_id_not_found(search_config_repo, mock_postgres):
    """Test retrieving search config for workflow without config."""
    # Arrange
    mock_postgres.fetchrow.return_value = None

    # Act
    result = await search_config_repo.get_by_workflow_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_configs_by_keywords(search_config_repo, mock_postgres):
    """Test retrieving search configs by keyword search."""
    # Arrange
    configs = [
        {
            'id': uuid4(),
            'keywords': ['machine learning', 'ai'],
            'search_query': 'ml research',
        },
        {
            'id': uuid4(),
            'keywords': ['machine learning', 'nlp'],
            'search_query': 'nlp models',
        },
    ]
    mock_postgres.fetch.return_value = configs

    # Act
    results = await search_config_repo.get_by_keywords(['machine learning'])

    # Assert
    assert len(results) == 2
    assert all('machine learning' in r['keywords'] for r in results)


# ============================================================================
# UPDATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_search_config_success(search_config_repo, mock_postgres):
    """Test successfully updating search configuration."""
    # Arrange
    config_id = uuid4()
    updates = {
        'search_query': 'updated query',
        'max_results': 200,
        'sort_by': 'date',
    }

    # Act
    success = await search_config_repo.update(config_id, updates)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_search_filters(search_config_repo, mock_postgres):
    """Test updating JSONB filter configuration."""
    # Arrange
    config_id = uuid4()
    new_filters = {
        'subject': ['cs.AI', 'cs.CV'],
        'venue': ['CVPR', 'ICCV'],
        'peer_reviewed': True,
    }
    updates = {'filters': new_filters}

    # Act
    success = await search_config_repo.update(config_id, updates)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_keywords_array(search_config_repo, mock_postgres):
    """Test updating keywords array field."""
    # Arrange
    config_id = uuid4()
    new_keywords = ['deep learning', 'cnn', 'computer vision']
    updates = {'keywords': new_keywords}

    # Act
    success = await search_config_repo.update(config_id, updates)

    # Assert
    assert success is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_search_config_empty_data(search_config_repo, mock_postgres):
    """Test updating with empty data succeeds without DB call."""
    # Act
    success = await search_config_repo.update(uuid4(), {})

    # Assert
    assert success is True
    mock_postgres.execute.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_search_config_nonexistent(search_config_repo, mock_postgres):
    """Test updating non-existent search config."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await search_config_repo.update(uuid4(), {'search_query': 'new'})

    # Assert
    assert success is False


# ============================================================================
# DELETE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_search_config_success(search_config_repo, mock_postgres):
    """Test successfully deleting search configuration."""
    # Act
    success = await search_config_repo.delete(uuid4())

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_search_config_nonexistent(search_config_repo, mock_postgres):
    """Test deleting non-existent search config fails gracefully."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await search_config_repo.delete(uuid4())

    # Assert
    assert success is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_by_workflow_id(search_config_repo, mock_postgres):
    """Test deleting search config by workflow ID."""
    # Arrange
    workflow_id = uuid4()

    # Act
    success = await search_config_repo.delete_by_workflow_id(workflow_id)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()

    # Verify workflow_id is in WHERE clause
    call_args = mock_postgres.execute.call_args
    query = call_args[0][0]
    assert 'workflow_id' in query.lower()
    assert 'DELETE' in query


# ============================================================================
# QUERY PATTERN TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_by_query_pattern(search_config_repo, mock_postgres):
    """Test searching configs by query pattern."""
    # Arrange
    configs = [
        {'id': uuid4(), 'search_query': 'machine learning models'},
        {'id': uuid4(), 'search_query': 'machine learning algorithms'},
    ]
    mock_postgres.fetch.return_value = configs

    # Act
    results = await search_config_repo.search_by_query_pattern('machine learning')

    # Assert
    assert len(results) == 2
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'ILIKE' in query or '~*' in query  # Case-insensitive pattern match


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_configs_by_author(search_config_repo, mock_postgres):
    """Test retrieving configs that search for specific author."""
    # Arrange
    configs = [
        {'id': uuid4(), 'authors': ['Geoffrey Hinton', 'Yann LeCun']},
        {'id': uuid4(), 'authors': ['Geoffrey Hinton', 'Yoshua Bengio']},
    ]
    mock_postgres.fetch.return_value = configs

    # Act
    results = await search_config_repo.get_by_author('Geoffrey Hinton')

    # Assert
    assert len(results) == 2
    assert all('Geoffrey Hinton' in r['authors'] for r in results)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_configs_by_date_range(search_config_repo, mock_postgres):
    """Test retrieving configs with specific date range filters."""
    # Arrange
    configs = [
        {
            'id': uuid4(),
            'date_range_start': '2020-01-01',
            'date_range_end': '2024-12-31',
        }
    ]
    mock_postgres.fetch.return_value = configs

    # Act
    results = await search_config_repo.get_by_date_range(
        start_date='2020-01-01', end_date='2024-12-31'
    )

    # Assert
    assert len(results) == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_configs_with_citation_threshold(search_config_repo, mock_postgres):
    """Test retrieving configs filtered by minimum citations."""
    # Arrange
    configs = [
        {'id': uuid4(), 'min_citations': 50},
        {'id': uuid4(), 'min_citations': 100},
    ]
    mock_postgres.fetch.return_value = configs

    # Act
    results = await search_config_repo.get_by_min_citations(50)

    # Assert
    assert len(results) == 2
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'min_citations' in query.lower()


# ============================================================================
# FILTER MANAGEMENT TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_add_filter_to_config(search_config_repo, mock_postgres):
    """Test adding a new filter to existing configuration."""
    # Arrange
    config_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': config_id,
        'filters': {'subject': ['cs.AI']},
    }

    # Act
    success = await search_config_repo.add_filter(
        config_id, 'venue', ['NeurIPS', 'ICML']
    )

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_remove_filter_from_config(search_config_repo, mock_postgres):
    """Test removing a filter from configuration."""
    # Arrange
    config_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': config_id,
        'filters': {'subject': ['cs.AI'], 'venue': ['NeurIPS']},
    }

    # Act
    success = await search_config_repo.remove_filter(config_id, 'venue')

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_specific_filter(search_config_repo, mock_postgres):
    """Test updating a specific filter value."""
    # Arrange
    config_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': config_id,
        'filters': {'subject': ['cs.AI'], 'language': 'en'},
    }

    # Act
    success = await search_config_repo.update_filter(
        config_id, 'subject', ['cs.AI', 'cs.LG', 'cs.CV']
    )

    # Assert
    assert success is True


# ============================================================================
# VALIDATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_validate_search_query_not_empty(search_config_repo, mock_postgres):
    """Test validation ensures search query is not empty."""
    # Arrange
    config_data = {'workflow_id': uuid4(), 'search_query': ''}

    # Act
    is_valid = await search_config_repo.validate(config_data)

    # Assert
    assert is_valid is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_validate_url_format(search_config_repo, mock_postgres):
    """Test validation of search URL format."""
    # Arrange
    config_data = {
        'workflow_id': uuid4(),
        'search_query': 'test',
        'search_url': 'invalid-url',
    }

    # Act
    is_valid = await search_config_repo.validate(config_data)

    # Assert
    assert is_valid is False


@pytest.mark.asyncio
@pytest.mark.unit
async def test_validate_date_range_logical(search_config_repo, mock_postgres):
    """Test validation that start date is before end date."""
    # Arrange
    config_data = {
        'workflow_id': uuid4(),
        'search_query': 'test',
        'date_range_start': '2024-12-31',
        'date_range_end': '2020-01-01',  # End before start!
    }

    # Act
    is_valid = await search_config_repo.validate(config_data)

    # Assert
    assert is_valid is False


# ============================================================================
# STATISTICS TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_most_common_keywords(search_config_repo, mock_postgres):
    """Test retrieving most commonly used keywords across configs."""
    # Arrange
    mock_postgres.fetch.return_value = [
        {'keyword': 'machine learning', 'count': 45},
        {'keyword': 'deep learning', 'count': 38},
        {'keyword': 'neural networks', 'count': 32},
    ]

    # Act
    results = await search_config_repo.get_most_common_keywords(limit=10)

    # Assert
    assert len(results) == 3
    assert results[0]['keyword'] == 'machine learning'


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_most_searched_authors(search_config_repo, mock_postgres):
    """Test retrieving most frequently searched authors."""
    # Arrange
    mock_postgres.fetch.return_value = [
        {'author': 'Geoffrey Hinton', 'count': 20},
        {'author': 'Yoshua Bengio', 'count': 18},
    ]

    # Act
    results = await search_config_repo.get_most_searched_authors(limit=10)

    # Assert
    assert len(results) == 2


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_database_connection_error(search_config_repo, mock_postgres):
    """Test handling database connection errors."""
    # Arrange
    mock_postgres.fetchrow.side_effect = Exception('Connection refused')

    # Act
    result = await search_config_repo.get_by_id(uuid4())

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_foreign_key_violation(
    search_config_repo, mock_postgres, sample_search_config_data
):
    """Test handling foreign key constraint violations."""
    # Arrange - Invalid workflow_id
    sample_search_config_data['workflow_id'] = uuid4()
    mock_postgres.fetchval.side_effect = Exception(
        'foreign key constraint violation'
    )

    # Act
    result_id = await search_config_repo.create(sample_search_config_data)

    # Assert
    assert result_id is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_count_search_configs(search_config_repo, mock_postgres):
    """Test counting total search configurations."""
    # Arrange
    mock_postgres.fetchval.return_value = 87

    # Act
    count = await search_config_repo.count()

    # Assert
    assert count == 87


@pytest.mark.asyncio
@pytest.mark.unit
async def test_exists_search_config(search_config_repo, mock_postgres):
    """Test checking if search config exists."""
    # Arrange
    mock_postgres.fetchval.return_value = True

    # Act
    exists = await search_config_repo.exists(uuid4())

    # Assert
    assert exists is True


# ============================================================================
# CACHE BEHAVIOR TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_enabled_get_by_workflow(mock_postgres):
    """Test caching improves performance for workflow config queries."""
    try:
        from thoth.repositories.workflow_search_config_repository import (
            WorkflowSearchConfigRepository,
        )
    except ImportError:
        pytest.skip('WorkflowSearchConfigRepository not yet implemented')

    # Arrange
    repo_with_cache = WorkflowSearchConfigRepository(
        mock_postgres, use_cache=True, cache_ttl=60
    )
    workflow_id = uuid4()
    config = {'id': uuid4(), 'workflow_id': workflow_id, 'search_query': 'test'}
    mock_postgres.fetchrow.return_value = config

    # Act - First call should hit database
    result1 = await repo_with_cache.get_by_workflow_id(workflow_id)
    # Second call should hit cache
    result2 = await repo_with_cache.get_by_workflow_id(workflow_id)

    # Assert
    assert result1 == result2
    # Database should only be called once
    assert mock_postgres.fetchrow.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_invalidation_on_config_update(mock_postgres):
    """Test cache is invalidated after config update."""
    try:
        from thoth.repositories.workflow_search_config_repository import (
            WorkflowSearchConfigRepository,
        )
    except ImportError:
        pytest.skip('WorkflowSearchConfigRepository not yet implemented')

    # Arrange
    repo_with_cache = WorkflowSearchConfigRepository(mock_postgres, use_cache=True)
    config_id = uuid4()
    mock_postgres.fetchrow.return_value = {
        'id': config_id,
        'search_query': 'original',
    }

    # Act
    result1 = await repo_with_cache.get_by_id(config_id)
    await repo_with_cache.update(config_id, {'search_query': 'updated'})

    # Update mock for new data
    mock_postgres.fetchrow.return_value = {
        'id': config_id,
        'search_query': 'updated',
    }
    result2 = await repo_with_cache.get_by_id(config_id)

    # Assert
    # Cache should be invalidated, so second query hits DB
    assert mock_postgres.fetchrow.call_count == 2
