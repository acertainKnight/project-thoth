"""
Unit tests for CitationRepository.

Tests citation relationship management, network traversal,
and citation counting functionality.
"""

import pytest  # noqa: I001
from unittest.mock import AsyncMock

from thoth.repositories.citation_repository import CitationRepository
from tests.fixtures.database_fixtures import (
    create_mock_record,
    sample_citation_data,  # noqa: F401
    sample_paper_data,  # noqa: F401
)


@pytest.mark.asyncio
class TestCitationRepository:
    """Test suite for CitationRepository."""

    async def test_initialization(self, mock_postgres_service):
        """Test repository initialization."""
        repo = CitationRepository(mock_postgres_service)

        assert repo.table_name == 'citations'
        assert repo.postgres == mock_postgres_service
        assert repo.use_cache is True

    async def test_create_citation(self, mock_postgres_service):
        """Test creating a citation relationship."""
        mock_postgres_service.fetchval.return_value = 1

        repo = CitationRepository(mock_postgres_service)
        citation_id = await repo.create_citation(
            citing_paper_id=1, cited_paper_id=2, metadata={'context': 'Related work'}
        )

        assert citation_id == 1

        query_info = mock_postgres_service.executed_queries[0]
        assert 'INSERT INTO citations' in query_info['query']
        assert 'ON CONFLICT' in query_info['query']  # Prevent duplicates

    async def test_create_citation_duplicate(self, mock_postgres_service):
        """Test that duplicate citations are handled gracefully."""
        # ON CONFLICT DO NOTHING returns None for duplicates
        mock_postgres_service.fetchval.return_value = None

        repo = CitationRepository(mock_postgres_service)
        citation_id = await repo.create_citation(citing_paper_id=1, cited_paper_id=2)

        assert citation_id is None

    async def test_get_citations_for_paper(
        self,
        mock_postgres_service,
        sample_citation_data,  # noqa: F811
        sample_paper_data,  # noqa: F811
    ):
        """Test getting all citations made by a paper."""
        # Mock citation with cited paper details
        combined_data = {**sample_citation_data, **sample_paper_data}
        mock_records = [create_mock_record(**combined_data)]
        mock_postgres_service.fetch.return_value = mock_records

        repo = CitationRepository(mock_postgres_service)
        citations = await repo.get_citations_for_paper(1)

        assert len(citations) == 1
        assert citations[0]['citing_paper_id'] == 1
        assert citations[0]['cited_paper_id'] == 2

        query_info = mock_postgres_service.executed_queries[0]
        assert 'JOIN papers' in query_info['query']
        assert 'citing_paper_id = $1' in query_info['query']

    async def test_get_citing_papers(
        self,
        mock_postgres_service,
        sample_citation_data,  # noqa: F811
        sample_paper_data,  # noqa: F811
    ):
        """Test getting all papers that cite a paper."""
        combined_data = {**sample_citation_data, **sample_paper_data}
        mock_records = [create_mock_record(**combined_data)]
        mock_postgres_service.fetch.return_value = mock_records

        repo = CitationRepository(mock_postgres_service)
        citing_papers = await repo.get_citing_papers(2)

        assert len(citing_papers) == 1
        assert citing_papers[0]['cited_paper_id'] == 2

        query_info = mock_postgres_service.executed_queries[0]
        assert 'cited_paper_id = $1' in query_info['query']

    async def test_get_citation_count(self, mock_postgres_service):
        """Test counting citations for a paper."""
        mock_postgres_service.fetchval.return_value = 42

        repo = CitationRepository(mock_postgres_service)
        count = await repo.get_citation_count(1)

        assert count == 42

        query_info = mock_postgres_service.executed_queries[0]
        assert 'COUNT(*)' in query_info['query']
        assert 'cited_paper_id = $1' in query_info['query']

    async def test_get_citation_count_zero(self, mock_postgres_service):
        """Test citation count for uncited paper."""
        mock_postgres_service.fetchval.return_value = 0

        repo = CitationRepository(mock_postgres_service)
        count = await repo.get_citation_count(999)

        assert count == 0

    async def test_get_citation_network_depth_1(self, mock_postgres_service):
        """Test getting citation network at depth 1."""
        mock_records = [
            create_mock_record(citing_paper_id=1, cited_paper_id=2, depth=1),
            create_mock_record(citing_paper_id=1, cited_paper_id=3, depth=1),
        ]
        mock_postgres_service.fetch.return_value = mock_records

        repo = CitationRepository(mock_postgres_service)
        network = await repo.get_citation_network(1, depth=1)

        assert len(network['nodes']) == 3  # Papers 1, 2, 3
        assert len(network['edges']) == 2
        assert 1 in network['nodes']
        assert 2 in network['nodes']
        assert 3 in network['nodes']

        query_info = mock_postgres_service.executed_queries[0]
        assert 'WITH RECURSIVE' in query_info['query']
        assert 'citation_tree' in query_info['query']

    async def test_get_citation_network_depth_2(self, mock_postgres_service):
        """Test getting citation network at depth 2."""
        mock_records = [
            create_mock_record(citing_paper_id=1, cited_paper_id=2, depth=1),
            create_mock_record(citing_paper_id=2, cited_paper_id=3, depth=2),
        ]
        mock_postgres_service.fetch.return_value = mock_records

        repo = CitationRepository(mock_postgres_service)
        network = await repo.get_citation_network(1, depth=2)

        assert len(network['nodes']) == 3
        assert len(network['edges']) == 2

        # Verify depth tracking
        depths = [edge['depth'] for edge in network['edges']]
        assert 1 in depths
        assert 2 in depths

    async def test_get_citation_network_empty(self, mock_postgres_service):
        """Test getting citation network for paper with no citations."""
        mock_postgres_service.fetch.return_value = []

        repo = CitationRepository(mock_postgres_service)
        network = await repo.get_citation_network(999, depth=1)

        assert network['nodes'] == []
        assert network['edges'] == []

    async def test_get_most_cited(
        self,
        mock_postgres_service,
        sample_paper_data,  # noqa: F811
    ):
        """Test getting most cited papers."""
        papers = [
            {**sample_paper_data, 'id': i, 'citation_count': 100 - i}
            for i in range(1, 6)
        ]
        mock_records = [create_mock_record(**paper) for paper in papers]
        mock_postgres_service.fetch.return_value = mock_records

        repo = CitationRepository(mock_postgres_service)
        most_cited = await repo.get_most_cited(limit=5)

        assert len(most_cited) == 5
        # Verify sorted by citation_count descending
        assert most_cited[0]['citation_count'] == 99
        assert most_cited[-1]['citation_count'] == 95

        query_info = mock_postgres_service.executed_queries[0]
        assert 'COUNT(c.id) as citation_count' in query_info['query']
        assert 'ORDER BY citation_count DESC' in query_info['query']
        assert 'LIMIT' in query_info['query']

    async def test_delete_citation(self, mock_postgres_service):
        """Test deleting a citation."""
        mock_postgres_service.execute.return_value = 'DELETE 1'

        repo = CitationRepository(mock_postgres_service)
        success = await repo.delete(1)

        assert success is True

        query_info = mock_postgres_service.executed_queries[0]
        assert 'DELETE FROM citations' in query_info['query']

    async def test_error_handling_create(self, mock_postgres_service):
        """Test error handling during citation creation."""
        mock_postgres_service.fetchval = AsyncMock(
            side_effect=Exception('Database error')
        )

        repo = CitationRepository(mock_postgres_service)
        result = await repo.create_citation(1, 2)

        assert result is None

    async def test_error_handling_network(self, mock_postgres_service):
        """Test error handling during network traversal."""
        mock_postgres_service.fetch = AsyncMock(side_effect=Exception('Database error'))

        repo = CitationRepository(mock_postgres_service)
        network = await repo.get_citation_network(1, depth=2)

        # Should return empty network on error
        assert network['nodes'] == []
        assert network['edges'] == []

    async def test_cache_invalidation(self, mock_postgres_service):
        """Test cache invalidation after creating citation."""
        mock_postgres_service.fetchval.return_value = 1

        repo = CitationRepository(mock_postgres_service, cache_ttl=60)

        # Create citation should invalidate cache
        await repo.create_citation(1, 2)

        # Cache should be cleared
        assert len(repo._cache) == 0
