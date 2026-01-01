"""
Unit tests for PaperRepository.

Tests CRUD operations, caching behavior, search functionality,
and error handling for the paper repository layer.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime

from thoth.repositories.paper_repository import PaperRepository
from tests.fixtures.database_fixtures import (
    create_mock_record,
    sample_paper_data,
    sample_papers_batch
)


@pytest.mark.asyncio
class TestPaperRepository:
    """Test suite for PaperRepository."""

    async def test_initialization(self, mock_postgres_service):
        """Test repository initialization."""
        repo = PaperRepository(mock_postgres_service)

        assert repo.table_name == 'papers'
        assert repo.postgres == mock_postgres_service
        assert repo.use_cache is True
        assert repo._cache is not None

    async def test_initialization_no_cache(self, mock_postgres_service):
        """Test repository initialization without caching."""
        repo = PaperRepository(mock_postgres_service, use_cache=False)

        assert repo.use_cache is False
        assert repo._cache is None

    async def test_create_paper(self, mock_postgres_service, sample_paper_data):
        """Test creating a new paper record."""
        # Remove id from input data
        input_data = {k: v for k, v in sample_paper_data.items() if k != 'id'}

        # Mock fetchval to return new ID
        mock_postgres_service.fetchval = AsyncMock(return_value=1)

        repo = PaperRepository(mock_postgres_service)
        paper_id = await repo.create(input_data)

        assert paper_id == 1
        assert len(mock_postgres_service.executed_queries) == 1

        query_info = mock_postgres_service.executed_queries[0]
        assert 'INSERT INTO papers' in query_info['query']
        assert 'RETURNING id' in query_info['query']

    async def test_get_by_id(self, mock_postgres_service, sample_paper_data):
        """Test retrieving paper by ID."""
        mock_record = create_mock_record(**sample_paper_data)
        mock_postgres_service.fetchrow = AsyncMock(return_value=mock_record)

        repo = PaperRepository(mock_postgres_service)
        paper = await repo.get_by_id(1)

        assert paper is not None
        assert paper['id'] == 1
        assert paper['title'] == 'Test Paper'
        assert paper['doi'] == '10.1000/test.123'

    async def test_get_by_id_not_found(self, mock_postgres_service):
        """Test retrieving non-existent paper."""
        mock_postgres_service.fetchrow = AsyncMock(return_value=None)

        repo = PaperRepository(mock_postgres_service)
        paper = await repo.get_by_id(999)

        assert paper is None

    async def test_get_by_doi(self, mock_postgres_service, sample_paper_data):
        """Test retrieving paper by DOI."""
        mock_record = create_mock_record(**sample_paper_data)
        mock_postgres_service.fetchrow = AsyncMock(return_value=mock_record)

        repo = PaperRepository(mock_postgres_service)
        paper = await repo.get_by_doi('10.1000/test.123')

        assert paper is not None
        assert paper['doi'] == '10.1000/test.123'

        # Verify query
        query_info = mock_postgres_service.executed_queries[0]
        assert 'WHERE doi = $1' in query_info['query']

    async def test_get_by_arxiv_id(self, mock_postgres_service, sample_paper_data):
        """Test retrieving paper by arXiv ID."""
        mock_record = create_mock_record(**sample_paper_data)
        mock_postgres_service.fetchrow = AsyncMock(return_value=mock_record)

        repo = PaperRepository(mock_postgres_service)
        paper = await repo.get_by_arxiv_id('2024.12345')

        assert paper is not None
        assert paper['arxiv_id'] == '2024.12345'

        # Verify query
        query_info = mock_postgres_service.executed_queries[0]
        assert 'WHERE arxiv_id = $1' in query_info['query']

    async def test_update_paper(self, mock_postgres_service):
        """Test updating paper record."""
        mock_postgres_service.execute = AsyncMock(return_value='UPDATE 1')

        repo = PaperRepository(mock_postgres_service)
        success = await repo.update(1, {'title': 'Updated Title'})

        assert success is True

        query_info = mock_postgres_service.executed_queries[0]
        assert 'UPDATE papers' in query_info['query']
        assert 'WHERE id = $1' in query_info['query']

    async def test_delete_paper(self, mock_postgres_service):
        """Test deleting paper record."""
        mock_postgres_service.execute = AsyncMock(return_value='DELETE 1')

        repo = PaperRepository(mock_postgres_service)
        success = await repo.delete(1)

        assert success is True

        query_info = mock_postgres_service.executed_queries[0]
        assert 'DELETE FROM papers' in query_info['query']
        assert 'WHERE id = $1' in query_info['query']

    async def test_search_by_title(self, mock_postgres_service, sample_papers_batch):
        """Test searching papers by title."""
        mock_records = [create_mock_record(**paper) for paper in sample_papers_batch[:3]]
        mock_postgres_service.fetch = AsyncMock(return_value=mock_records)

        repo = PaperRepository(mock_postgres_service)
        papers = await repo.search_by_title('Test', limit=10)

        assert len(papers) == 3
        assert all('Test Paper' in p['title'] for p in papers)

        query_info = mock_postgres_service.executed_queries[0]
        assert 'ILIKE' in query_info['query']
        assert 'LIMIT' in query_info['query']

    async def test_get_by_tags_match_all(self, mock_postgres_service, sample_papers_batch):
        """Test getting papers matching all tags."""
        mock_records = [create_mock_record(**paper) for paper in sample_papers_batch[:2]]
        mock_postgres_service.fetch = AsyncMock(return_value=mock_records)

        repo = PaperRepository(mock_postgres_service)
        papers = await repo.get_by_tags(['machine-learning', 'nlp'], match_all=True)

        assert len(papers) == 2

        query_info = mock_postgres_service.executed_queries[0]
        assert '@>' in query_info['query']  # Contains operator for match_all

    async def test_get_by_tags_match_any(self, mock_postgres_service, sample_papers_batch):
        """Test getting papers matching any tag."""
        mock_records = [create_mock_record(**paper) for paper in sample_papers_batch[:5]]
        mock_postgres_service.fetch = AsyncMock(return_value=mock_records)

        repo = PaperRepository(mock_postgres_service)
        papers = await repo.get_by_tags(['machine-learning', 'nlp'], match_all=False)

        assert len(papers) == 5

        query_info = mock_postgres_service.executed_queries[0]
        assert '&&' in query_info['query']  # Overlaps operator for match_any

    async def test_get_recent(self, mock_postgres_service, sample_papers_batch):
        """Test getting recent papers."""
        mock_records = [create_mock_record(**paper) for paper in sample_papers_batch[:10]]
        mock_postgres_service.fetch = AsyncMock(return_value=mock_records)

        repo = PaperRepository(mock_postgres_service)
        papers = await repo.get_recent(limit=10, offset=0)

        assert len(papers) == 10

        query_info = mock_postgres_service.executed_queries[0]
        assert 'ORDER BY created_at DESC' in query_info['query']
        assert 'LIMIT' in query_info['query']
        assert 'OFFSET' in query_info['query']

    async def test_update_tags(self, mock_postgres_service):
        """Test updating paper tags."""
        mock_postgres_service.execute = AsyncMock(return_value='UPDATE 1')

        repo = PaperRepository(mock_postgres_service)
        success = await repo.update_tags(1, ['new-tag', 'another-tag'])

        assert success is True

        query_info = mock_postgres_service.executed_queries[0]
        assert 'UPDATE papers SET tags' in query_info['query']

    async def test_get_all_tags(self, mock_postgres_service):
        """Test getting all unique tags."""
        mock_records = [
            create_mock_record(tag='machine-learning'),
            create_mock_record(tag='nlp'),
            create_mock_record(tag='computer-vision')
        ]
        mock_postgres_service.fetch = AsyncMock(return_value=mock_records)

        repo = PaperRepository(mock_postgres_service)
        tags = await repo.get_all_tags()

        assert len(tags) == 3
        assert 'machine-learning' in tags

        query_info = mock_postgres_service.executed_queries[0]
        assert 'DISTINCT unnest(tags)' in query_info['query']

    async def test_full_text_search(self, mock_postgres_service, sample_papers_batch):
        """Test full-text search functionality."""
        mock_records = [
            create_mock_record(**{**paper, 'rank': 0.5})
            for paper in sample_papers_batch[:3]
        ]
        mock_postgres_service.fetch = AsyncMock(return_value=mock_records)

        repo = PaperRepository(mock_postgres_service)
        papers = await repo.full_text_search('machine learning', limit=20)

        assert len(papers) == 3

        query_info = mock_postgres_service.executed_queries[0]
        assert 'to_tsvector' in query_info['query']
        assert 'plainto_tsquery' in query_info['query']
        assert 'ts_rank' in query_info['query']

    async def test_cache_behavior(self, mock_postgres_service, sample_paper_data):
        """Test that caching reduces database queries."""
        mock_record = create_mock_record(**sample_paper_data)
        mock_postgres_service.fetchrow = AsyncMock(return_value=mock_record)

        repo = PaperRepository(mock_postgres_service, cache_ttl=60)

        # First call should hit database
        paper1 = await repo.get_by_id(1)
        assert len(mock_postgres_service.executed_queries) == 1

        # Second call should use cache
        paper2 = await repo.get_by_id(1)
        assert len(mock_postgres_service.executed_queries) == 1  # No new query

        assert paper1 == paper2

    async def test_cache_invalidation_on_update(
        self, mock_postgres_service, sample_paper_data
    ):
        """Test that cache is invalidated after updates."""
        mock_record = create_mock_record(**sample_paper_data)
        mock_postgres_service.fetchrow = AsyncMock(return_value=mock_record)
        mock_postgres_service.execute = AsyncMock(return_value='UPDATE 1')

        repo = PaperRepository(mock_postgres_service, cache_ttl=60)

        # Populate cache
        await repo.get_by_id(1)
        assert len(mock_postgres_service.executed_queries) == 1

        # Update should invalidate cache
        await repo.update(1, {'title': 'Updated'})

        # Next read should hit database again
        mock_postgres_service.executed_queries.clear()
        await repo.get_by_id(1)
        assert len(mock_postgres_service.executed_queries) == 1

    async def test_error_handling_create(self, mock_postgres_service):
        """Test error handling during create."""
        mock_postgres_service.fetchval = AsyncMock(
            side_effect=Exception('Database error')
        )

        repo = PaperRepository(mock_postgres_service)
        result = await repo.create({'title': 'Test'})

        assert result is None

    async def test_error_handling_fetch(self, mock_postgres_service):
        """Test error handling during fetch."""
        mock_postgres_service.fetchrow = AsyncMock(
            side_effect=Exception('Database error')
        )

        repo = PaperRepository(mock_postgres_service)
        result = await repo.get_by_id(1)

        assert result is None

    async def test_count_papers(self, mock_postgres_service):
        """Test counting total papers."""
        mock_postgres_service.fetchval = AsyncMock(return_value=100)

        repo = PaperRepository(mock_postgres_service)
        count = await repo.count()

        assert count == 100

        query_info = mock_postgres_service.executed_queries[0]
        assert 'COUNT(*)' in query_info['query']

    async def test_exists_check(self, mock_postgres_service):
        """Test checking if paper exists."""
        mock_postgres_service.fetchval = AsyncMock(return_value=True)

        repo = PaperRepository(mock_postgres_service)
        exists = await repo.exists(1)

        assert exists is True

        query_info = mock_postgres_service.executed_queries[0]
        assert 'EXISTS' in query_info['query']
