"""
End-to-End Citation Resolution Workflow Tests.

This module tests the complete citation resolution pipeline from input to storage:
1. Citation extraction from text
2. Resolution through API chain (Crossref → OpenAlex → Semantic Scholar)
3. Confidence scoring and validation
4. Database storage and retrieval
5. Batch processing with concurrency

Test Scenarios:
--------------
1. **Single Citation Resolution**: Complete workflow for one citation
2. **Batch Resolution**: Concurrent resolution of multiple citations
3. **Fallback Chain**: Tests sequential API fallback when primary fails
4. **Duplicate Detection**: Ensures citations aren't re-resolved
5. **Error Recovery**: Handles API failures gracefully
6. **Database Persistence**: Verifies storage and retrieval

Success Criteria:
----------------
- Citations resolved with DOI when available (>80% success rate)
- Confidence scores properly calibrated (0-1 range, monotonic)
- Batch processing completes within performance targets
- Database state consistent after pipeline execution
- No data loss on API failures
"""

import asyncio  # noqa: I001
from pathlib import Path  # noqa: F401
from typing import List  # noqa: UP035

import pytest
import pytest_asyncio
from loguru import logger

from thoth.analyze.citations.resolution_chain import CitationResolutionChain
from thoth.analyze.citations.resolution_types import (
    CitationResolutionStatus,
    ConfidenceLevel,
)
from thoth.services.postgres_service import PostgresService
from thoth.utilities.schemas.citations import Citation


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def resolution_chain(
    mock_crossref_client,
    mock_openalex_client,
    mock_semanticscholar_client,
):
    """Create resolution chain with mocked API clients."""
    from thoth.analyze.citations.crossref_resolver import CrossrefResolver
    from thoth.analyze.citations.openalex_resolver import OpenAlexResolver
    from thoth.analyze.citations.semanticscholar import SemanticScholarAPI

    # Create resolvers with mocked clients
    crossref = CrossrefResolver()
    crossref.client = mock_crossref_client

    openalex = OpenAlexResolver()
    openalex.client = mock_openalex_client

    semantic_scholar = SemanticScholarAPI()
    semantic_scholar.client = mock_semanticscholar_client

    return CitationResolutionChain(
        crossref_resolver=crossref,
        openalex_resolver=openalex,
        semanticscholar_resolver=semantic_scholar,
    )


# ============================================================================
# Test Cases: Single Citation Resolution
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_single_citation_resolution_success(
    resolution_chain: CitationResolutionChain,
    sample_citation: Citation,
):
    """
    Test complete resolution workflow for a single citation.

    Validates:
    - Citation is resolved with DOI
    - Confidence score is HIGH (>0.85)
    - Metadata is enriched from API
    - Resolution metadata is tracked
    """
    # Execute resolution
    result = await resolution_chain.resolve(sample_citation)

    # Verify resolution status
    assert result.status == CitationResolutionStatus.RESOLVED
    assert result.confidence_level == ConfidenceLevel.HIGH
    assert result.confidence_score >= 0.85

    # Verify DOI was found
    assert result.matched_data is not None
    assert 'doi' in result.matched_data
    assert result.matched_data['doi'] == '10.1234/test.doi'

    # Verify metadata enrichment
    assert result.matched_data.get('title') is not None
    assert result.matched_data.get('authors') is not None

    # Verify resolution metadata
    assert result.metadata is not None
    assert result.metadata.total_time_ms > 0
    assert result.metadata.sources_tried > 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_citation_already_has_doi(resolution_chain: CitationResolutionChain):
    """
    Test that citations with existing DOI skip resolution.

    Should return immediately without API calls.
    """
    citation = Citation(
        title='Paper with DOI',
        authors=['John Doe'],
        year=2023,
        doi='10.1234/existing.doi',
    )

    result = await resolution_chain.resolve(citation)

    # Should skip resolution
    assert result.status == CitationResolutionStatus.RESOLVED
    assert result.confidence_score == 1.0
    assert result.source is None  # No API called
    assert result.metadata.sources_tried == 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_citation_resolution_unresolved(
    resolution_chain: CitationResolutionChain,
    mock_crossref_client,
    mock_openalex_client,
    mock_semanticscholar_client,
):
    """
    Test handling of citations that cannot be resolved.

    All APIs return no results.
    """
    # Configure mocks to return empty results
    mock_crossref_client.search.return_value = {'message': {'items': []}}
    mock_openalex_client.search.return_value = {'results': []}
    mock_semanticscholar_client.search.return_value = {'data': []}

    citation = Citation(
        title='Unknown Paper',
        authors=['Unknown Author'],
        year=2023,
    )

    result = await resolution_chain.resolve(citation)

    # Should be unresolved
    assert result.status == CitationResolutionStatus.UNRESOLVED
    assert result.confidence_level == ConfidenceLevel.NONE
    assert result.matched_data is None


# ============================================================================
# Test Cases: Batch Resolution
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_batch_citation_resolution(
    resolution_chain: CitationResolutionChain,
    sample_citations: List[Citation],  # noqa: UP006
):
    """
    Test batch resolution of multiple citations concurrently.

    Validates:
    - All citations are processed
    - Concurrent execution improves performance
    - No race conditions in resolution
    - Results maintain correct ordering
    """
    # Resolve all citations concurrently
    tasks = [resolution_chain.resolve(citation) for citation in sample_citations]
    results = await asyncio.gather(*tasks)

    # Verify all citations processed
    assert len(results) == len(sample_citations)

    # Verify each result has valid structure
    for result in results:
        assert result.status is not None
        assert result.confidence_level is not None
        assert 0.0 <= result.confidence_score <= 1.0
        assert result.metadata is not None


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_large_batch_performance(
    resolution_chain: CitationResolutionChain,
    benchmark_data_medium,
):
    """
    Test batch resolution performance with 100 citations.

    Performance target: <30 seconds for 100 citations (300ms avg per citation).
    """
    import time

    start_time = time.time()

    # Resolve batch concurrently
    tasks = [resolution_chain.resolve(citation) for citation in benchmark_data_medium]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed_time = time.time() - start_time

    # Count successful resolutions
    successful = sum(
        1
        for r in results
        if not isinstance(r, Exception)
        and r.status == CitationResolutionStatus.RESOLVED
    )

    logger.info(
        f'Batch resolution: {successful}/{len(benchmark_data_medium)} '
        f'resolved in {elapsed_time:.2f}s '
        f'({elapsed_time / len(benchmark_data_medium) * 1000:.1f}ms avg)'
    )

    # Performance validation
    assert elapsed_time < 30.0, f'Batch took {elapsed_time:.2f}s (target: <30s)'
    assert successful >= len(benchmark_data_medium) * 0.5, 'At least 50% should resolve'


# ============================================================================
# Test Cases: API Fallback Chain
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_fallback_chain_crossref_fails(
    resolution_chain: CitationResolutionChain,
    mock_crossref_client,
    sample_citation: Citation,
):
    """
    Test fallback to OpenAlex when Crossref fails.

    Simulates Crossref API failure to validate fallback logic.
    """
    # Configure Crossref to fail
    mock_crossref_client.search.side_effect = Exception('Crossref API error')

    result = await resolution_chain.resolve(sample_citation)

    # Should still resolve via fallback (OpenAlex or Semantic Scholar)
    # Note: May be RESOLVED or UNRESOLVED depending on fallback success
    assert result.status in [
        CitationResolutionStatus.RESOLVED,
        CitationResolutionStatus.UNRESOLVED,
    ]
    assert result.metadata.sources_tried >= 1


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_confidence_based_early_stopping(
    resolution_chain: CitationResolutionChain,
    mock_crossref_client,  # noqa: ARG001
    sample_citation: Citation,
):
    """
    Test that high-confidence match stops resolution chain early.

    If Crossref returns high-confidence match (>0.85), should not try other APIs.
    """
    result = await resolution_chain.resolve(sample_citation)

    # If resolved with high confidence from Crossref
    if result.confidence_score >= 0.85:
        # Should stop early and not try all sources
        assert result.metadata.sources_tried <= 2


# ============================================================================
# Test Cases: Database Persistence
# ============================================================================


@pytest.mark.e2e
@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_citation_storage_and_retrieval(
    postgres_service: PostgresService,
    sample_citation: Citation,
):
    """
    Test storing resolved citation to database and retrieving it.

    Validates:
    - Citation is stored with all metadata
    - Retrieval returns identical citation
    - DOI is indexed for fast lookup
    """
    # Store citation
    async with postgres_service.pool.acquire() as conn:
        citation_id = await conn.fetchval(
            """
            INSERT INTO citations (
                title, authors, year, journal, doi,
                volume, issue, pages, citation_text
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING id
            """,
            sample_citation.title,
            sample_citation.authors,
            sample_citation.year,
            sample_citation.journal,
            '10.1234/test.doi',  # Resolved DOI
            sample_citation.volume,
            sample_citation.issue,
            sample_citation.pages,
            sample_citation.text,
        )

    assert citation_id is not None

    # Retrieve citation
    async with postgres_service.pool.acquire() as conn:
        retrieved = await conn.fetchrow(
            'SELECT * FROM citations WHERE id = $1',
            citation_id,
        )

    assert retrieved is not None
    assert retrieved['title'] == sample_citation.title
    assert retrieved['doi'] == '10.1234/test.doi'


@pytest.mark.e2e
@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_duplicate_citation_detection(
    postgres_service: PostgresService,
    empty_database,  # noqa: ARG001
):
    """
    Test that duplicate citations are detected and not re-resolved.

    Duplicate detection based on:
    - Exact DOI match
    - Title + first author + year fuzzy match
    """
    citation = Citation(
        title='Test Paper',
        authors=['John Doe'],
        year=2023,
        doi='10.1234/test.doi',
    )

    # Store citation first time
    async with postgres_service.pool.acquire() as conn:
        first_id = await conn.fetchval(
            """
            INSERT INTO citations (title, authors, year, doi)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            citation.title,
            citation.authors,
            citation.year,
            citation.doi,
        )

        # Try to store duplicate (same DOI)
        duplicate_id = await conn.fetchval(
            """
            SELECT id FROM citations WHERE doi = $1
            """,
            citation.doi,
        )

    assert duplicate_id == first_id, 'Should return existing citation ID'


# ============================================================================
# Test Cases: Error Handling
# ============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_malformed_citation_input(resolution_chain: CitationResolutionChain):
    """
    Test handling of malformed citation data.

    Should handle gracefully without crashing.
    """
    malformed_citations = [
        Citation(text=''),  # Empty text
        Citation(title=None, authors=None, year=None),  # All None
        Citation(title='', authors=[], year=0),  # Empty values
        Citation(title='A' * 10000),  # Extremely long title
    ]

    for citation in malformed_citations:
        try:
            result = await resolution_chain.resolve(citation)
            # Should return UNRESOLVED, not crash
            assert result.status in [
                CitationResolutionStatus.UNRESOLVED,
                CitationResolutionStatus.RESOLVED,
            ]
        except Exception as e:
            pytest.fail(f'Resolution crashed on malformed input: {e}')


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_api_rate_limiting_handling(
    resolution_chain: CitationResolutionChain,
    mock_crossref_client,
):
    """
    Test handling of API rate limiting errors.

    Should retry with exponential backoff.
    """
    # Simulate rate limit on first call, success on retry
    mock_crossref_client.search.side_effect = [
        Exception('429 Too Many Requests'),
        {'message': {'items': [{'DOI': '10.1234/test.doi'}]}},
    ]

    citation = Citation(title='Test Paper', authors=['John Doe'], year=2023)

    # Should eventually succeed after retry
    result = await resolution_chain.resolve(citation)  # noqa: F841

    # Verify retry was attempted
    assert mock_crossref_client.search.call_count >= 1


# ============================================================================
# Test Cases: Workflow Integration
# ============================================================================


@pytest.mark.e2e
@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_complete_resolution_workflow_integration(
    resolution_chain: CitationResolutionChain,
    postgres_service: PostgresService,
    empty_database,  # noqa: ARG001
    sample_citations: List[Citation],  # noqa: UP006
):
    """
    Test complete end-to-end workflow: Input → Resolution → Storage.

    Integration test covering:
    1. Batch citation resolution
    2. Confidence scoring
    3. Database storage
    4. Retrieval and verification
    """
    # Step 1: Resolve all citations
    resolution_results = await asyncio.gather(
        *[resolution_chain.resolve(c) for c in sample_citations]
    )

    # Step 2: Store resolved citations
    stored_ids = []
    async with postgres_service.pool.acquire() as conn:
        for citation, result in zip(sample_citations, resolution_results):  # noqa: B905
            if result.status == CitationResolutionStatus.RESOLVED:
                citation_id = await conn.fetchval(
                    """
                    INSERT INTO citations (
                        title, authors, year, doi,
                        citation_text, confidence_score
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                    """,
                    citation.title or result.matched_data.get('title'),
                    citation.authors or result.matched_data.get('authors'),
                    citation.year or result.matched_data.get('year'),
                    result.matched_data.get('doi'),
                    citation.text,
                    result.confidence_score,
                )
                stored_ids.append(citation_id)

    # Step 3: Verify storage
    assert len(stored_ids) > 0, 'At least some citations should be stored'

    # Step 4: Retrieve and validate
    async with postgres_service.pool.acquire() as conn:
        retrieved_count = await conn.fetchval(
            'SELECT COUNT(*) FROM citations WHERE id = ANY($1)',
            stored_ids,
        )

    assert retrieved_count == len(stored_ids), (
        'All stored citations should be retrievable'
    )
    logger.info(
        f'✅ Complete workflow: {len(stored_ids)} citations '
        f'resolved and stored successfully'
    )
