"""
Comprehensive tests for PaperRepository.

This module tests all CRUD operations, edge cases, and PostgreSQL integration
for the paper discovery and storage system.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from thoth.repositories.paper_repository import PaperRepository


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
def paper_repo(mock_postgres):
    """Create PaperRepository instance with mocked postgres."""
    return PaperRepository(mock_postgres, use_cache=False)


@pytest.fixture
def sample_paper_data():
    """Sample paper data for testing."""
    return {
        'title': 'Test Paper on Machine Learning',
        'authors': ['John Doe', 'Jane Smith'],
        'abstract': 'This is a test abstract about ML algorithms.',
        'doi': '10.1234/test.2024.001',
        'arxiv_id': '2024.01234',
        'url': 'https://arxiv.org/abs/2024.01234',
        'pdf_path': 'papers/pdfs/test_paper.pdf',
        'tags': ['machine-learning', 'neural-networks'],
        'source': 'arxiv',
        'published_date': '2024-01-15',
        'created_at': datetime.now().isoformat(),
    }


@pytest.fixture
def sample_paper_record():
    """Sample paper database record."""
    return {
        'id': 1,
        'title': 'Test Paper on Machine Learning',
        'authors': ['John Doe', 'Jane Smith'],
        'abstract': 'This is a test abstract about ML algorithms.',
        'doi': '10.1234/test.2024.001',
        'arxiv_id': '2024.01234',
        'url': 'https://arxiv.org/abs/2024.01234',
        'pdf_path': 'papers/pdfs/test_paper.pdf',
        'tags': ['machine-learning', 'neural-networks'],
        'source': 'arxiv',
        'published_date': '2024-01-15',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat(),
    }


# ============================================================================
# CREATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_paper_success(paper_repo, mock_postgres, sample_paper_data):
    """Test successful paper creation."""
    # Arrange
    expected_id = 42
    mock_postgres.fetchval.return_value = expected_id

    # Act
    result_id = await paper_repo.create(sample_paper_data)

    # Assert
    assert result_id == expected_id
    mock_postgres.fetchval.assert_called_once()

    # Verify SQL query contains expected columns
    call_args = mock_postgres.fetchval.call_args
    query = call_args[0][0]
    assert 'INSERT INTO papers' in query
    assert 'RETURNING id' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_paper_duplicate_doi(paper_repo, mock_postgres, sample_paper_data):
    """Test creating paper with duplicate DOI fails gracefully."""
    # Arrange
    mock_postgres.fetchval.side_effect = Exception('duplicate key value violates unique constraint')

    # Act
    result_id = await paper_repo.create(sample_paper_data)

    # Assert
    assert result_id is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_create_paper_missing_required_fields(paper_repo, mock_postgres):
    """Test creating paper with missing required fields."""
    # Arrange
    incomplete_data = {'title': 'Only Title'}
    mock_postgres.fetchval.side_effect = Exception('null value in column "source"')

    # Act
    result_id = await paper_repo.create(incomplete_data)

    # Assert
    assert result_id is None


# ============================================================================
# READ OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_success(paper_repo, mock_postgres, sample_paper_record):
    """Test successfully retrieving paper by ID."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_paper_record

    # Act
    result = await paper_repo.get_by_id(1)

    # Assert
    assert result is not None
    assert result['id'] == 1
    assert result['title'] == sample_paper_record['title']
    mock_postgres.fetchrow.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_id_not_found(paper_repo, mock_postgres):
    """Test retrieving non-existent paper."""
    # Arrange
    mock_postgres.fetchrow.return_value = None

    # Act
    result = await paper_repo.get_by_id(9999)

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_doi_success(paper_repo, mock_postgres, sample_paper_record):
    """Test retrieving paper by DOI."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_paper_record

    # Act
    result = await paper_repo.get_by_doi('10.1234/test.2024.001')

    # Assert
    assert result is not None
    assert result['doi'] == '10.1234/test.2024.001'
    mock_postgres.fetchrow.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_doi_not_found(paper_repo, mock_postgres):
    """Test retrieving paper by non-existent DOI."""
    # Arrange
    mock_postgres.fetchrow.return_value = None

    # Act
    result = await paper_repo.get_by_doi('10.9999/nonexistent')

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_arxiv_id_success(paper_repo, mock_postgres, sample_paper_record):
    """Test retrieving paper by arXiv ID."""
    # Arrange
    mock_postgres.fetchrow.return_value = sample_paper_record

    # Act
    result = await paper_repo.get_by_arxiv_id('2024.01234')

    # Assert
    assert result is not None
    assert result['arxiv_id'] == '2024.01234'


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_arxiv_id_with_version(paper_repo, mock_postgres, sample_paper_record):
    """Test retrieving paper with versioned arXiv ID."""
    # Arrange
    versioned_record = {**sample_paper_record, 'arxiv_id': '2024.01234v2'}
    mock_postgres.fetchrow.return_value = versioned_record

    # Act
    result = await paper_repo.get_by_arxiv_id('2024.01234v2')

    # Assert
    assert result is not None
    assert 'v2' in result['arxiv_id']


# ============================================================================
# SEARCH OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_by_title_exact_match(paper_repo, mock_postgres, sample_paper_record):
    """Test searching papers by exact title match."""
    # Arrange
    mock_postgres.fetch.return_value = [sample_paper_record]

    # Act
    results = await paper_repo.search_by_title('Machine Learning', limit=10)

    # Assert
    assert len(results) == 1
    assert results[0]['title'] == sample_paper_record['title']


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_by_title_partial_match(paper_repo, mock_postgres, sample_paper_record):
    """Test searching papers by partial title."""
    # Arrange
    mock_postgres.fetch.return_value = [sample_paper_record]

    # Act
    results = await paper_repo.search_by_title('Machine', limit=10)

    # Assert
    assert len(results) == 1
    # Verify ILIKE is used for case-insensitive search
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'ILIKE' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_by_title_no_results(paper_repo, mock_postgres):
    """Test searching with no matching results."""
    # Arrange
    mock_postgres.fetch.return_value = []

    # Act
    results = await paper_repo.search_by_title('Nonexistent Topic', limit=10)

    # Assert
    assert len(results) == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_by_title_with_limit(paper_repo, mock_postgres):
    """Test search respects limit parameter."""
    # Arrange
    mock_records = [
        {'id': i, 'title': f'Paper {i}'} for i in range(1, 101)
    ]
    mock_postgres.fetch.return_value = mock_records[:5]

    # Act
    results = await paper_repo.search_by_title('Paper', limit=5)

    # Assert
    assert len(results) == 5
    # Verify LIMIT is in query
    call_args = mock_postgres.fetch.call_args
    assert 5 in call_args[0]  # limit parameter passed


# ============================================================================
# TAG OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_tags_match_any(paper_repo, mock_postgres, sample_paper_record):
    """Test retrieving papers matching any tag."""
    # Arrange
    mock_postgres.fetch.return_value = [sample_paper_record]

    # Act
    results = await paper_repo.get_by_tags(['machine-learning'], match_all=False)

    # Assert
    assert len(results) == 1
    assert 'machine-learning' in results[0]['tags']

    # Verify && operator is used for ANY match
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert '&&' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_tags_match_all(paper_repo, mock_postgres, sample_paper_record):
    """Test retrieving papers matching all tags."""
    # Arrange
    mock_postgres.fetch.return_value = [sample_paper_record]

    # Act
    results = await paper_repo.get_by_tags(
        ['machine-learning', 'neural-networks'],
        match_all=True
    )

    # Assert
    assert len(results) == 1
    assert all(tag in results[0]['tags'] for tag in ['machine-learning', 'neural-networks'])

    # Verify @> operator is used for ALL match
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert '@>' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_by_tags_no_match(paper_repo, mock_postgres):
    """Test retrieving papers with non-matching tags."""
    # Arrange
    mock_postgres.fetch.return_value = []

    # Act
    results = await paper_repo.get_by_tags(['nonexistent-tag'])

    # Assert
    assert len(results) == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_tags_success(paper_repo, mock_postgres):
    """Test updating paper tags."""
    # Arrange
    new_tags = ['deep-learning', 'transformers', 'attention']

    # Act
    success = await paper_repo.update_tags(1, new_tags)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_all_tags_success(paper_repo, mock_postgres):
    """Test retrieving all unique tags."""
    # Arrange
    mock_postgres.fetch.return_value = [
        {'tag': 'machine-learning'},
        {'tag': 'neural-networks'},
        {'tag': 'deep-learning'},
    ]

    # Act
    tags = await paper_repo.get_all_tags()

    # Assert
    assert len(tags) == 3
    assert 'machine-learning' in tags
    assert 'deep-learning' in tags


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_all_tags_empty(paper_repo, mock_postgres):
    """Test retrieving tags when none exist."""
    # Arrange
    mock_postgres.fetch.return_value = []

    # Act
    tags = await paper_repo.get_all_tags()

    # Assert
    assert len(tags) == 0


# ============================================================================
# UPDATE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_paper_success(paper_repo, mock_postgres):
    """Test successfully updating paper."""
    # Arrange
    updates = {
        'abstract': 'Updated abstract with more details.',
        'tags': ['machine-learning', 'computer-vision'],
    }

    # Act
    success = await paper_repo.update(1, updates)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_paper_empty_data(paper_repo, mock_postgres):
    """Test updating with empty data succeeds without DB call."""
    # Act
    success = await paper_repo.update(1, {})

    # Assert
    assert success is True
    mock_postgres.execute.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_update_paper_nonexistent(paper_repo, mock_postgres):
    """Test updating non-existent paper."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await paper_repo.update(9999, {'title': 'New Title'})

    # Assert
    assert success is False


# ============================================================================
# DELETE OPERATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_paper_success(paper_repo, mock_postgres):
    """Test successfully deleting paper."""
    # Act
    success = await paper_repo.delete(1)

    # Assert
    assert success is True
    mock_postgres.execute.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_delete_paper_nonexistent(paper_repo, mock_postgres):
    """Test deleting non-existent paper fails gracefully."""
    # Arrange
    mock_postgres.execute.side_effect = Exception('Record not found')

    # Act
    success = await paper_repo.delete(9999)

    # Assert
    assert success is False


# ============================================================================
# FULL-TEXT SEARCH TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_full_text_search_success(paper_repo, mock_postgres, sample_paper_record):
    """Test full-text search across paper content."""
    # Arrange
    mock_postgres.fetch.return_value = [
        {**sample_paper_record, 'rank': 0.95}
    ]

    # Act
    results = await paper_repo.full_text_search('neural networks', limit=20)

    # Assert
    assert len(results) == 1
    assert 'rank' in results[0]

    # Verify PostgreSQL full-text search is used
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'to_tsvector' in query
    assert 'plainto_tsquery' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_full_text_search_multi_term(paper_repo, mock_postgres, sample_paper_record):
    """Test full-text search with multiple terms."""
    # Arrange
    mock_postgres.fetch.return_value = [sample_paper_record]

    # Act
    results = await paper_repo.full_text_search('machine learning algorithms', limit=20)

    # Assert
    assert len(results) > 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_full_text_search_no_results(paper_repo, mock_postgres):
    """Test full-text search with no results."""
    # Arrange
    mock_postgres.fetch.return_value = []

    # Act
    results = await paper_repo.full_text_search('quantum entanglement', limit=20)

    # Assert
    assert len(results) == 0


# ============================================================================
# PAGINATION TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_recent_papers(paper_repo, mock_postgres):
    """Test retrieving recent papers."""
    # Arrange
    recent_papers = [
        {'id': i, 'title': f'Paper {i}', 'created_at': datetime.now().isoformat()}
        for i in range(1, 11)
    ]
    mock_postgres.fetch.return_value = recent_papers

    # Act
    results = await paper_repo.get_recent(limit=10, offset=0)

    # Assert
    assert len(results) == 10

    # Verify ORDER BY created_at DESC
    call_args = mock_postgres.fetch.call_args
    query = call_args[0][0]
    assert 'ORDER BY created_at DESC' in query


@pytest.mark.asyncio
@pytest.mark.unit
async def test_get_recent_papers_with_offset(paper_repo, mock_postgres):
    """Test pagination with offset."""
    # Arrange
    mock_postgres.fetch.return_value = [
        {'id': i, 'title': f'Paper {i}'} for i in range(11, 21)
    ]

    # Act
    results = await paper_repo.get_recent(limit=10, offset=10)

    # Assert
    assert len(results) == 10

    # Verify OFFSET is used
    call_args = mock_postgres.fetch.call_args
    assert 10 in call_args[0]  # offset parameter


# ============================================================================
# CACHE BEHAVIOR TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_enabled_get_by_id(mock_postgres):
    """Test caching improves performance on repeated queries."""
    # Arrange
    repo_with_cache = PaperRepository(mock_postgres, use_cache=True, cache_ttl=60)
    mock_postgres.fetchrow.return_value = {'id': 1, 'title': 'Test'}

    # Act - First call should hit database
    result1 = await repo_with_cache.get_by_id(1)
    # Second call should hit cache
    result2 = await repo_with_cache.get_by_id(1)

    # Assert
    assert result1 == result2
    # Database should only be called once
    assert mock_postgres.fetchrow.call_count == 1


@pytest.mark.asyncio
@pytest.mark.unit
async def test_cache_invalidation_on_update(mock_postgres):
    """Test cache is invalidated after update."""
    # Arrange
    repo_with_cache = PaperRepository(mock_postgres, use_cache=True)
    mock_postgres.fetchrow.return_value = {'id': 1, 'title': 'Original'}

    # Act
    result1 = await repo_with_cache.get_by_id(1)
    await repo_with_cache.update(1, {'title': 'Updated'})

    # Update mock for new data
    mock_postgres.fetchrow.return_value = {'id': 1, 'title': 'Updated'}
    result2 = await repo_with_cache.get_by_id(1)

    # Assert
    # Cache should be invalidated, so second query hits DB
    assert mock_postgres.fetchrow.call_count == 2


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_database_connection_error(paper_repo, mock_postgres):
    """Test handling database connection errors."""
    # Arrange
    mock_postgres.fetchrow.side_effect = Exception('Connection refused')

    # Act
    result = await paper_repo.get_by_id(1)

    # Assert
    assert result is None


@pytest.mark.asyncio
@pytest.mark.unit
async def test_malformed_query_error(paper_repo, mock_postgres):
    """Test handling malformed query errors."""
    # Arrange
    mock_postgres.fetch.side_effect = Exception('syntax error at or near')

    # Act
    results = await paper_repo.search_by_title('test')

    # Assert
    assert len(results) == 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_count_papers(paper_repo, mock_postgres):
    """Test counting total papers."""
    # Arrange
    mock_postgres.fetchval.return_value = 42

    # Act
    count = await paper_repo.count()

    # Assert
    assert count == 42


@pytest.mark.asyncio
@pytest.mark.unit
async def test_exists_paper(paper_repo, mock_postgres):
    """Test checking if paper exists."""
    # Arrange
    mock_postgres.fetchval.return_value = True

    # Act
    exists = await paper_repo.exists(1)

    # Assert
    assert exists is True


@pytest.mark.asyncio
@pytest.mark.unit
async def test_list_all_papers(paper_repo, mock_postgres):
    """Test listing all papers."""
    # Arrange
    papers = [{'id': i, 'title': f'Paper {i}'} for i in range(1, 11)]
    mock_postgres.fetch.return_value = papers

    # Act
    results = await paper_repo.list_all(limit=10, offset=0)

    # Assert
    assert len(results) == 10
