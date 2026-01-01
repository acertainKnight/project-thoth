"""
Integration tests for the complete citation resolution workflow.

Tests the end-to-end citation resolution process including:
- Resolution chain with real API clients
- Cache integration
- Error recovery
- Performance under load
- Async operation correctness
"""

import asyncio
import tempfile
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from thoth.analyze.citations.resolution_chain import CitationResolutionChain
from thoth.analyze.citations.resolution_types import (
    APISource,
    CitationResolutionStatus,
    ConfidenceLevel,
)
from thoth.analyze.citations.crossref_resolver import CrossrefResolver
from thoth.analyze.citations.openalex_resolver import OpenAlexResolver
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.utilities.schemas.citations import Citation

from tests.fixtures.citation_fixtures import (
    CITATION_WITH_DOI,
    CITATION_WITH_ARXIV,
    CITATION_WITHOUT_IDENTIFIERS,
    CITATION_MINIMAL,
    BATCH_CITATIONS,
    CACHE_TEST_CITATIONS,
    MOCK_CROSSREF_RESPONSE,
    MOCK_OPENALEX_RESPONSE,
    MOCK_SEMANTIC_SCHOLAR_PAPER,
)


class TestEndToEndResolution:
    """Test complete resolution workflow."""

    @pytest.mark.asyncio
    async def test_full_resolution_chain_with_doi(self):
        """Test complete resolution for citation with DOI."""
        chain = CitationResolutionChain()

        result = await chain.resolve(CITATION_WITH_DOI)

        # Should skip resolution and return immediately
        assert result.status == CitationResolutionStatus.RESOLVED
        assert result.confidence_score == 1.0
        assert result.source is None  # No API used
        assert result.matched_data['doi'] == CITATION_WITH_DOI.doi

    @pytest.mark.asyncio
    async def test_full_resolution_chain_with_arxiv(self):
        """Test complete resolution for citation with ArXiv ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock Semantic Scholar to return a result
            mock_s2 = Mock(spec=SemanticScholarAPI)

            def mock_paper_lookup(arxiv_id):
                return MOCK_SEMANTIC_SCHOLAR_PAPER

            mock_s2.paper_lookup_by_arxiv = mock_paper_lookup

            chain = CitationResolutionChain(semanticscholar_resolver=mock_s2)

            result = await chain.resolve(CITATION_WITH_ARXIV)

            # Should use Semantic Scholar for ArXiv
            assert result.status in [
                CitationResolutionStatus.RESOLVED,
                CitationResolutionStatus.PARTIAL
            ]

    @pytest.mark.asyncio
    async def test_full_resolution_chain_fallback(self):
        """Test that resolution falls back through all sources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create resolvers with mocked API calls
            mock_crossref = Mock(spec=CrossrefResolver)
            mock_crossref.resolve_citation = AsyncMock(return_value=[])

            mock_openalex = Mock(spec=OpenAlexResolver)
            mock_openalex.resolve_citation = AsyncMock(return_value=[])

            mock_s2 = Mock(spec=SemanticScholarAPI)
            mock_s2.paper_search = Mock(return_value=[])

            chain = CitationResolutionChain(
                crossref_resolver=mock_crossref,
                openalex_resolver=mock_openalex,
                semanticscholar_resolver=mock_s2
            )

            result = await chain.resolve(CITATION_MINIMAL)

            # Should try all sources and return unresolved
            assert result.status == CitationResolutionStatus.UNRESOLVED
            mock_crossref.resolve_citation.assert_called_once()
            mock_openalex.resolve_citation.assert_called_once()


class TestCacheIntegration:
    """Test cache integration across resolution chain."""

    @pytest.mark.asyncio
    async def test_cache_across_multiple_resolutions(self):
        """Test that cache is used across multiple resolutions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create resolver with caching
            crossref = CrossrefResolver(cache_dir=tmpdir, enable_caching=True)

            # Mock the HTTP client
            mock_response = Mock()
            mock_response.json.return_value = MOCK_CROSSREF_RESPONSE
            mock_response.raise_for_status = Mock()

            with patch.object(crossref, 'client') as mock_client:
                mock_client.get = AsyncMock(return_value=mock_response)

                # First resolution - should hit API
                matches1 = await crossref.resolve_citation(CITATION_MINIMAL)
                assert len(matches1) > 0
                assert mock_client.get.call_count == 1

                # Second resolution - should hit cache
                matches2 = await crossref.resolve_citation(CITATION_MINIMAL)
                assert len(matches2) > 0
                assert mock_client.get.call_count == 1  # No additional calls

                # Results should be identical
                assert matches1[0].doi == matches2[0].doi

    @pytest.mark.asyncio
    async def test_cache_eviction_on_error(self):
        """Test that failed requests don't poison cache."""
        with tempfile.TemporaryDirectory() as tmpdir:
            crossref = CrossrefResolver(
                cache_dir=tmpdir,
                enable_caching=True,
                max_retries=0
            )

            mock_error = Mock()
            mock_error.status_code = 500

            with patch.object(crossref, 'client') as mock_client:
                # First call fails
                mock_client.get = AsyncMock(
                    side_effect=Exception("API error")
                )

                matches1 = await crossref.resolve_citation(CITATION_MINIMAL)
                assert len(matches1) == 0

                # Second call should retry (not use cached error)
                mock_response = Mock()
                mock_response.json.return_value = MOCK_CROSSREF_RESPONSE
                mock_response.raise_for_status = Mock()
                mock_client.get = AsyncMock(return_value=mock_response)

                matches2 = await crossref.resolve_citation(CITATION_MINIMAL)
                assert len(matches2) > 0


class TestAsyncCorrectness:
    """Test async operation correctness and race conditions."""

    @pytest.mark.asyncio
    async def test_concurrent_resolutions_no_race_conditions(self):
        """Test that concurrent resolutions don't have race conditions."""
        chain = CitationResolutionChain()

        # Create many citations
        citations = [CITATION_MINIMAL] * 50

        with patch.object(chain, '_try_crossref', new_callable=AsyncMock) as mock:
            # Simulate varying response times
            async def delayed_response(*args, **kwargs):
                await asyncio.sleep(0.01)  # Small delay
                return None

            mock.side_effect = delayed_response

            # Resolve all concurrently
            results = await chain.batch_resolve(citations, parallel=True)

            # All should complete
            assert len(results) == 50
            # All should have results (even if unresolved)
            assert all(r.status is not None for r in results)

    @pytest.mark.asyncio
    async def test_batch_resolution_maintains_order(self):
        """Test that batch resolution maintains citation order."""
        chain = CitationResolutionChain()

        citations = [
            CITATION_WITH_DOI,
            CITATION_MINIMAL,
            CITATION_WITHOUT_IDENTIFIERS
        ]

        results = await chain.batch_resolve(citations, parallel=True)

        # Results should be in same order as input
        assert len(results) == len(citations)
        # First citation should have DOI result
        assert results[0].matched_data['doi'] == CITATION_WITH_DOI.doi

    @pytest.mark.asyncio
    async def test_no_deadlocks_under_load(self):
        """Test that system doesn't deadlock under heavy load."""
        chain = CitationResolutionChain()

        # Create many citations
        many_citations = [CITATION_MINIMAL] * 200

        with patch.object(chain, 'resolve', new_callable=AsyncMock) as mock:
            mock.return_value = Mock(
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.9
            )

            # Should complete without hanging
            try:
                results = await asyncio.wait_for(
                    chain.batch_resolve(many_citations, parallel=True),
                    timeout=30.0  # 30 second timeout
                )
                assert len(results) == 200
            except asyncio.TimeoutError:
                pytest.fail("Batch resolution deadlocked")


class TestErrorRecovery:
    """Test error recovery and resilience."""

    @pytest.mark.asyncio
    async def test_partial_batch_failure_recovery(self):
        """Test recovery when some citations fail in batch."""
        chain = CitationResolutionChain()

        with patch.object(chain, 'resolve', new_callable=AsyncMock) as mock:
            # Alternate between success and failure
            mock.side_effect = [
                Mock(status=CitationResolutionStatus.RESOLVED, confidence_score=0.9),
                Exception("API error"),
                Mock(status=CitationResolutionStatus.RESOLVED, confidence_score=0.9),
                Exception("API error"),
            ]

            results = await chain.batch_resolve(BATCH_CITATIONS[:4], parallel=True)

            # Should have results for all citations
            assert len(results) == 4
            # Failed ones should have FAILED status
            assert results[1].status == CitationResolutionStatus.FAILED
            assert results[3].status == CitationResolutionStatus.FAILED
            # Successful ones should be RESOLVED
            assert results[0].status == CitationResolutionStatus.RESOLVED
            assert results[2].status == CitationResolutionStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self):
        """Test handling of network timeouts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            crossref = CrossrefResolver(
                cache_dir=tmpdir,
                timeout=1,  # Short timeout
                max_retries=0  # No retries
            )

            with patch.object(crossref, 'client') as mock_client:
                # Simulate timeout
                mock_client.get = AsyncMock(side_effect=asyncio.TimeoutError())

                matches = await crossref.resolve_citation(CITATION_MINIMAL)

                # Should return empty list, not crash
                assert matches == []

    @pytest.mark.asyncio
    async def test_malformed_response_handling(self):
        """Test handling of malformed API responses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            crossref = CrossrefResolver(cache_dir=tmpdir)

            mock_response = Mock()
            mock_response.json.return_value = {"malformed": "data"}  # Missing 'message'
            mock_response.raise_for_status = Mock()

            with patch.object(crossref, 'client') as mock_client:
                mock_client.get = AsyncMock(return_value=mock_response)

                matches = await crossref.resolve_citation(CITATION_MINIMAL)

                # Should handle gracefully
                assert matches == []


class TestPerformanceCharacteristics:
    """Test performance characteristics and optimizations."""

    @pytest.mark.asyncio
    async def test_batch_faster_than_sequential(self):
        """Test that parallel batch is faster than sequential."""
        import time

        chain = CitationResolutionChain()

        # Create test citations
        test_citations = [CITATION_MINIMAL] * 10

        with patch.object(chain, 'resolve', new_callable=AsyncMock) as mock:
            # Simulate 0.1s per resolution
            async def delayed_resolve(*args, **kwargs):
                await asyncio.sleep(0.1)
                return Mock(status=CitationResolutionStatus.RESOLVED)

            mock.side_effect = delayed_resolve

            # Test parallel
            start = time.time()
            await chain.batch_resolve(test_citations, parallel=True)
            parallel_time = time.time() - start

            # Test sequential
            mock.side_effect = delayed_resolve  # Reset
            start = time.time()
            await chain.batch_resolve(test_citations, parallel=False)
            sequential_time = time.time() - start

            # Parallel should be significantly faster
            # (With perfect parallelization, would be 10x faster, but allow for overhead)
            assert parallel_time < sequential_time * 0.5

    @pytest.mark.asyncio
    async def test_early_stopping_reduces_api_calls(self):
        """Test that early stopping reduces unnecessary API calls."""
        chain = CitationResolutionChain()

        with patch.object(
            chain, '_try_crossref', new_callable=AsyncMock
        ) as mock_crossref, \
        patch.object(
            chain, '_try_openalex', new_callable=AsyncMock
        ) as mock_openalex, \
        patch.object(
            chain, '_try_semantic_scholar', new_callable=AsyncMock
        ) as mock_s2:

            # Crossref returns high confidence immediately
            mock_crossref.return_value = Mock(
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.95,
                source=APISource.CROSSREF
            )

            await chain.resolve(CITATION_MINIMAL)

            # Should stop after Crossref
            mock_crossref.assert_called_once()
            mock_openalex.assert_not_called()
            mock_s2.assert_not_called()

    @pytest.mark.asyncio
    async def test_statistics_tracking_performance(self):
        """Test that statistics tracking doesn't impact performance."""
        import time

        chain = CitationResolutionChain()

        with patch.object(chain, 'resolve', new_callable=AsyncMock) as mock:
            mock.return_value = Mock(status=CitationResolutionStatus.RESOLVED)

            # Time batch resolution
            start = time.time()
            await chain.batch_resolve([CITATION_MINIMAL] * 100, parallel=True)
            elapsed = time.time() - start

            # Should complete in reasonable time (< 5s with mocked resolver)
            assert elapsed < 5.0

            # Statistics should be tracked
            stats = chain.get_statistics()
            assert stats['total_processed'] > 0


class TestConfidenceScoreValidation:
    """Test confidence score validation and monotonic behavior."""

    @pytest.mark.asyncio
    async def test_confidence_scores_in_valid_range(self):
        """Test that all confidence scores are in [0, 1] range."""
        chain = CitationResolutionChain()

        # Test various scenarios
        citations = [
            CITATION_WITH_DOI,
            CITATION_WITH_ARXIV,
            CITATION_MINIMAL,
            CITATION_WITHOUT_IDENTIFIERS
        ]

        with patch.object(chain, '_try_crossref', new_callable=AsyncMock), \
             patch.object(chain, '_try_openalex', new_callable=AsyncMock), \
             patch.object(chain, '_try_semantic_scholar', new_callable=AsyncMock):

            for citation in citations:
                result = await chain.resolve(citation)

                # Confidence score should be in valid range
                assert 0.0 <= result.confidence_score <= 1.0

    @pytest.mark.asyncio
    async def test_confidence_level_matches_score(self):
        """Test that confidence level matches the score."""
        chain = CitationResolutionChain()

        # Mock various confidence scores
        test_scores = [0.95, 0.75, 0.50, 0.30]
        expected_levels = [
            ConfidenceLevel.HIGH,
            ConfidenceLevel.MEDIUM,
            ConfidenceLevel.LOW,
            ConfidenceLevel.LOW
        ]

        for score, expected_level in zip(test_scores, expected_levels):
            with patch.object(chain, '_try_crossref', new_callable=AsyncMock) as mock:
                mock.return_value = Mock(
                    status=CitationResolutionStatus.RESOLVED,
                    confidence_score=score,
                    confidence_level=expected_level,
                    source=APISource.CROSSREF
                )

                result = await chain.resolve(CITATION_MINIMAL)

                assert result.confidence_level == expected_level
                assert result.confidence_score == score
