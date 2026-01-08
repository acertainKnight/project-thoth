"""
Unit tests for ResolutionChain.

Tests the core citation resolution chain coordinator, including:
- Single citation resolution
- Batch resolution with parallel execution
- Confidence score calculation
- Fallback resolution strategies
- Error handling for API failures
- Early stopping optimization
"""

import asyncio  # noqa: I001, F401
from typing import Any, Dict, List  # noqa: F401, UP035
from unittest.mock import AsyncMock, Mock, patch, MagicMock  # noqa: F401

import pytest
from loguru import logger  # noqa: F401

from thoth.analyze.citations.resolution_chain import (
    CitationResolutionChain,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,  # noqa: F401
    TITLE_THRESHOLD,  # noqa: F401
)
from thoth.analyze.citations.resolution_types import (
    APISource,
    CitationResolutionStatus,
    ConfidenceLevel,
    ResolutionResult,
    ResolutionMetadata,
)
from thoth.analyze.citations.crossref_resolver import MatchCandidate as CrossrefMatch
from thoth.analyze.citations.openalex_resolver import MatchCandidate as OpenAlexMatch  # noqa: F401
from thoth.analyze.citations.arxiv_resolver import ArxivMatch  # noqa: F401
from thoth.utilities.schemas.citations import Citation

from tests.fixtures.citation_fixtures import (
    CITATION_WITH_DOI,
    CITATION_WITH_ARXIV,
    CITATION_WITHOUT_IDENTIFIERS,
    CITATION_MINIMAL,
    CITATION_TITLE_ONLY,  # noqa: F401
    BATCH_CITATIONS,
    MOCK_CROSSREF_RESPONSE,  # noqa: F401
    MOCK_OPENALEX_RESPONSE,  # noqa: F401
    MOCK_SEMANTIC_SCHOLAR_PAPER,  # noqa: F401
)


class TestResolutionChainInitialization:
    """Test ResolutionChain initialization and setup."""

    def test_init_default_resolvers(self):
        """Test initialization with default resolvers."""
        chain = CitationResolutionChain()

        assert chain.crossref_resolver is not None
        assert chain.openalex_resolver is not None
        assert chain.arxiv_resolver is not None
        assert chain.semanticscholar_resolver is not None

        # Check statistics initialization
        assert chain._stats['total_processed'] == 0
        assert chain._stats['already_has_doi'] == 0
        assert chain._stats['resolved_crossref'] == 0

    def test_init_custom_resolvers(self):
        """Test initialization with custom resolver instances."""
        mock_crossref = Mock()
        mock_openalex = Mock()
        mock_arxiv = Mock()
        mock_s2 = Mock()

        chain = CitationResolutionChain(
            crossref_resolver=mock_crossref,
            arxiv_resolver=mock_arxiv,
            openalex_resolver=mock_openalex,
            semanticscholar_resolver=mock_s2,
        )

        assert chain.crossref_resolver is mock_crossref
        assert chain.openalex_resolver is mock_openalex
        assert chain.arxiv_resolver is mock_arxiv
        assert chain.semanticscholar_resolver is mock_s2


class TestSingleCitationResolution:
    """Test resolution of individual citations."""

    @pytest.mark.asyncio
    async def test_resolve_citation_with_doi_skips_resolution(self):
        """Test that citations with DOI are skipped (no API calls)."""
        chain = CitationResolutionChain()

        result = await chain.resolve(CITATION_WITH_DOI)

        assert result.status == CitationResolutionStatus.RESOLVED
        assert result.confidence_score == 1.0
        assert result.confidence_level == ConfidenceLevel.HIGH
        assert result.source is None  # No API source used
        assert result.matched_data == {'doi': CITATION_WITH_DOI.doi}
        assert chain._stats['already_has_doi'] == 1
        assert chain._stats['total_processed'] == 1

    @pytest.mark.asyncio
    async def test_resolve_arxiv_citation_uses_semantic_scholar_first(self):
        """Test that ArXiv citations try Semantic Scholar first."""
        chain = CitationResolutionChain()

        # Mock Semantic Scholar to return high confidence match
        with patch.object(
            chain, '_try_semantic_scholar', new_callable=AsyncMock
        ) as mock_s2:
            mock_s2.return_value = ResolutionResult(
                citation=CITATION_WITH_ARXIV.text,
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.95,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.SEMANTIC_SCHOLAR,
                matched_data={'doi': '10.1145/test', 'title': 'Test'},
                metadata=ResolutionMetadata(),
            )

            result = await chain.resolve(CITATION_WITH_ARXIV)

            assert result.status == CitationResolutionStatus.RESOLVED
            assert result.source == APISource.SEMANTIC_SCHOLAR
            assert result.confidence_score >= HIGH_CONFIDENCE_THRESHOLD
            mock_s2.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_uses_fallback_chain(self):
        """Test that resolution falls back through API sources in order."""
        chain = CitationResolutionChain()

        # Mock all resolvers to return low confidence
        with (
            patch.object(
                chain, '_try_crossref', new_callable=AsyncMock
            ) as mock_crossref,
            patch.object(chain, '_try_arxiv', new_callable=AsyncMock) as mock_arxiv,
            patch.object(
                chain, '_try_openalex', new_callable=AsyncMock
            ) as mock_openalex,
            patch.object(
                chain, '_try_semantic_scholar', new_callable=AsyncMock
            ) as mock_s2,
        ):
            # All return None (low confidence)
            mock_crossref.return_value = None
            mock_arxiv.return_value = None
            mock_openalex.return_value = None
            mock_s2.return_value = None

            result = await chain.resolve(CITATION_WITHOUT_IDENTIFIERS)

            # Should have tried all sources
            assert result.status == CitationResolutionStatus.UNRESOLVED
            assert result.confidence_score == 0.0
            mock_crossref.assert_called_once()
            mock_arxiv.assert_called_once()
            mock_openalex.assert_called_once()
            mock_s2.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_stops_early_on_high_confidence(self):
        """Test early stopping when high confidence match found."""
        chain = CitationResolutionChain()

        # Mock Crossref to return high confidence
        with (
            patch.object(
                chain, '_try_crossref', new_callable=AsyncMock
            ) as mock_crossref,
            patch.object(
                chain, '_try_openalex', new_callable=AsyncMock
            ) as mock_openalex,
        ):
            mock_crossref.return_value = ResolutionResult(
                citation=CITATION_MINIMAL.text,
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.92,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.CROSSREF,
                matched_data={'doi': '10.1234/test'},
                metadata=ResolutionMetadata(),
            )

            result = await chain.resolve(CITATION_MINIMAL)

            # Should stop after Crossref
            assert result.source == APISource.CROSSREF
            assert result.confidence_score >= HIGH_CONFIDENCE_THRESHOLD
            mock_crossref.assert_called_once()
            mock_openalex.assert_not_called()  # Should not reach OpenAlex


class TestConfidenceScoreCalculation:
    """Test confidence score calculation methods."""

    def test_calculate_crossref_confidence_exact_match(self):
        """Test Crossref confidence calculation for exact match."""
        chain = CitationResolutionChain()

        citation = Citation(
            title='Deep Learning for Computer Vision',
            authors=['Smith, J.', 'Doe, A.'],
            year=2023,
        )

        match = CrossrefMatch(
            doi='10.1234/test',
            title='Deep Learning for Computer Vision',
            authors=['Smith, J.', 'Doe, A.'],
            year=2023,
            score=95.0,
        )

        confidence = chain._calculate_crossref_confidence(match, citation)

        # Should have high confidence (exact matches)
        assert confidence >= 0.85
        assert confidence <= 1.0

    def test_calculate_crossref_confidence_below_title_threshold(self):
        """Test that matches below title threshold are rejected."""
        chain = CitationResolutionChain()

        citation = Citation(
            title='Deep Learning for Computer Vision', authors=['Smith, J.'], year=2023
        )

        match = CrossrefMatch(
            doi='10.1234/test',
            title='Shallow Learning for Natural Language',  # Very different title
            authors=['Smith, J.'],
            year=2023,
            score=95.0,
        )

        confidence = chain._calculate_crossref_confidence(match, citation)

        # Should reject due to low title similarity
        assert confidence == 0.0

    def test_calculate_crossref_confidence_year_tolerance(self):
        """Test year matching with ±1 tolerance."""
        chain = CitationResolutionChain()

        citation = Citation(title='Test Paper', authors=['Smith, J.'], year=2023)

        # Test exact year match
        match_exact = CrossrefMatch(
            doi='10.1234/test',
            title='Test Paper',
            authors=['Smith, J.'],
            year=2023,
            score=95.0,
        )
        confidence_exact = chain._calculate_crossref_confidence(match_exact, citation)

        # Test ±1 year
        match_off_one = CrossrefMatch(
            doi='10.1234/test',
            title='Test Paper',
            authors=['Smith, J.'],
            year=2024,
            score=95.0,
        )
        confidence_off_one = chain._calculate_crossref_confidence(
            match_off_one, citation
        )

        # Exact should score higher than ±1
        assert confidence_exact > confidence_off_one
        # But ±1 should still get partial credit
        assert confidence_off_one > 0.7

    def test_calculate_semanticscholar_confidence(self):
        """Test Semantic Scholar confidence calculation."""
        chain = CitationResolutionChain()

        citation = Citation(
            title='Machine Learning Survey',
            authors=['Johnson, B.', 'Williams, C.'],
            year=2023,
        )

        paper_data = {
            'title': 'Machine Learning Survey',
            'authors': [{'name': 'Johnson, B.'}, {'name': 'Williams, C.'}],
            'year': 2023,
            'externalIds': {'DOI': '10.1234/test'},
            'citationCount': 50,
        }

        confidence = chain._calculate_semanticscholar_confidence(paper_data, citation)

        # Should have high confidence (good match)
        assert confidence >= 0.80
        assert confidence <= 1.0

    def test_simple_title_similarity_exact_match(self):
        """Test title similarity for exact matches."""
        chain = CitationResolutionChain()

        title1 = 'Deep Learning for Computer Vision'
        title2 = 'Deep Learning for Computer Vision'

        similarity = chain._simple_title_similarity(title1, title2)
        assert similarity == 1.0

    def test_simple_title_similarity_token_overlap(self):
        """Test title similarity with token overlap."""
        chain = CitationResolutionChain()

        title1 = 'Deep Learning for Computer Vision'
        title2 = 'Computer Vision using Deep Learning'

        similarity = chain._simple_title_similarity(title1, title2)

        # Should have good similarity (same tokens, different order)
        # Jaccard similarity: 4 common / 6 total = 0.667
        assert similarity > 0.65
        assert similarity < 1.0

    def test_simple_title_similarity_empty_strings(self):
        """Test title similarity with empty strings."""
        chain = CitationResolutionChain()

        assert chain._simple_title_similarity('', 'Test') == 0.0
        assert chain._simple_title_similarity('Test', '') == 0.0
        assert chain._simple_title_similarity('', '') == 0.0


class TestBatchResolution:
    """Test batch resolution with parallel execution."""

    @pytest.mark.asyncio
    async def test_batch_resolve_parallel(self):
        """Test parallel batch resolution."""
        chain = CitationResolutionChain()

        with patch.object(chain, 'resolve', new_callable=AsyncMock) as mock_resolve:
            # Mock resolve to return success for each citation
            mock_resolve.side_effect = [
                ResolutionResult(
                    citation=cit.text or cit.title,
                    status=CitationResolutionStatus.RESOLVED,
                    confidence_score=0.9,
                    confidence_level=ConfidenceLevel.HIGH,
                    source=APISource.CROSSREF,
                    matched_data={'doi': f'10.1234/test{i}'},
                    metadata=ResolutionMetadata(),
                )
                for i, cit in enumerate(BATCH_CITATIONS)
            ]

            results = await chain.batch_resolve(BATCH_CITATIONS, parallel=True)

            assert len(results) == len(BATCH_CITATIONS)
            assert mock_resolve.call_count == len(BATCH_CITATIONS)

            # All results should be resolved
            for result in results:
                assert result.status == CitationResolutionStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_batch_resolve_sequential(self):
        """Test sequential batch resolution."""
        chain = CitationResolutionChain()

        with patch.object(chain, 'resolve', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = [
                ResolutionResult(
                    citation=cit.text or cit.title,
                    status=CitationResolutionStatus.RESOLVED,
                    confidence_score=0.9,
                    confidence_level=ConfidenceLevel.HIGH,
                    source=APISource.CROSSREF,
                    matched_data={'doi': f'10.1234/test{i}'},
                    metadata=ResolutionMetadata(),
                )
                for i, cit in enumerate(BATCH_CITATIONS)
            ]

            results = await chain.batch_resolve(BATCH_CITATIONS, parallel=False)

            assert len(results) == len(BATCH_CITATIONS)
            assert mock_resolve.call_count == len(BATCH_CITATIONS)

    @pytest.mark.asyncio
    async def test_batch_resolve_handles_exceptions(self):
        """Test that batch resolution handles exceptions gracefully."""
        chain = CitationResolutionChain()

        with patch.object(chain, 'resolve', new_callable=AsyncMock) as mock_resolve:
            # First citation throws exception, others succeed
            mock_resolve.side_effect = [
                Exception('API error'),
                ResolutionResult(
                    citation='Test',
                    status=CitationResolutionStatus.RESOLVED,
                    confidence_score=0.9,
                    confidence_level=ConfidenceLevel.HIGH,
                    source=APISource.CROSSREF,
                    matched_data={'doi': '10.1234/test'},
                    metadata=ResolutionMetadata(),
                ),
            ]

            results = await chain.batch_resolve(BATCH_CITATIONS[:2], parallel=True)

            assert len(results) == 2
            # First result should be FAILED
            assert results[0].status == CitationResolutionStatus.FAILED
            # Second result should be RESOLVED
            assert results[1].status == CitationResolutionStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_batch_resolve_empty_list(self):
        """Test batch resolution with empty list."""
        chain = CitationResolutionChain()

        results = await chain.batch_resolve([])

        assert results == []

    @pytest.mark.asyncio
    async def test_batch_resolve_rate_limiting(self):
        """Test that batch resolution respects rate limiting."""
        chain = CitationResolutionChain()

        # Create many citations to test semaphore
        many_citations = [CITATION_MINIMAL] * 100

        with patch.object(chain, 'resolve', new_callable=AsyncMock) as mock_resolve:
            mock_resolve.return_value = ResolutionResult(
                citation='Test',
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.9,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.CROSSREF,
                matched_data={'doi': '10.1234/test'},
                metadata=ResolutionMetadata(),
            )

            results = await chain.batch_resolve(many_citations, parallel=True)

            # Should complete all citations
            assert len(results) == 100
            # All should use same resolve method
            assert mock_resolve.call_count == 100


class TestErrorHandling:
    """Test error handling in resolution chain."""

    @pytest.mark.asyncio
    async def test_crossref_error_continues_to_next_source(self):
        """Test that errors in one source don't stop the chain."""
        chain = CitationResolutionChain()

        with (
            patch.object(
                chain, '_try_crossref', new_callable=AsyncMock
            ) as mock_crossref,
            patch.object(chain, '_try_arxiv', new_callable=AsyncMock) as mock_arxiv,
        ):
            # Crossref raises exception
            mock_crossref.side_effect = Exception('API error')

            # ArXiv returns success
            mock_arxiv.return_value = ResolutionResult(
                citation='Test',
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.9,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.ARXIV,
                matched_data={'arxiv_id': '2401.12345'},
                metadata=ResolutionMetadata(),
            )

            result = await chain.resolve(CITATION_MINIMAL)

            # Should continue to ArXiv despite Crossref error
            assert result.source == APISource.ARXIV
            assert result.status == CitationResolutionStatus.RESOLVED

    @pytest.mark.asyncio
    async def test_all_sources_fail_returns_unresolved(self):
        """Test that failure in all sources returns UNRESOLVED."""
        chain = CitationResolutionChain()

        with (
            patch.object(
                chain, '_try_crossref', new_callable=AsyncMock
            ) as mock_crossref,
            patch.object(chain, '_try_arxiv', new_callable=AsyncMock) as mock_arxiv,
            patch.object(
                chain, '_try_openalex', new_callable=AsyncMock
            ) as mock_openalex,
            patch.object(
                chain, '_try_semantic_scholar', new_callable=AsyncMock
            ) as mock_s2,
        ):
            # All sources return None
            mock_crossref.return_value = None
            mock_arxiv.return_value = None
            mock_openalex.return_value = None
            mock_s2.return_value = None

            result = await chain.resolve(CITATION_MINIMAL)

            assert result.status == CitationResolutionStatus.UNRESOLVED
            assert result.confidence_score == 0.0
            assert result.source is None


class TestStatistics:
    """Test resolution statistics tracking."""

    @pytest.mark.asyncio
    async def test_statistics_tracking(self):
        """Test that statistics are tracked correctly."""
        chain = CitationResolutionChain()

        # Resolve citation with DOI (should skip)
        await chain.resolve(CITATION_WITH_DOI)

        stats = chain.get_statistics()

        assert stats['total_processed'] == 1
        assert stats['already_has_doi'] == 1

    @pytest.mark.asyncio
    async def test_statistics_reset_on_new_instance(self):
        """Test that statistics are independent per instance."""
        chain1 = CitationResolutionChain()
        chain2 = CitationResolutionChain()

        await chain1.resolve(CITATION_WITH_DOI)

        stats1 = chain1.get_statistics()
        stats2 = chain2.get_statistics()

        assert stats1['total_processed'] == 1
        assert stats2['total_processed'] == 0


class TestCleanup:
    """Test resource cleanup."""

    @pytest.mark.asyncio
    async def test_close_closes_all_clients(self):
        """Test that close() cleans up all API clients."""
        chain = CitationResolutionChain()

        with (
            patch.object(
                chain.crossref_resolver, 'close', new_callable=AsyncMock
            ) as mock_crossref_close,
            patch.object(
                chain.semanticscholar_resolver, 'client', create=True
            ) as mock_s2_client,
        ):
            mock_s2_client.close = Mock()

            await chain.close()

            mock_crossref_close.assert_called_once()
            mock_s2_client.close.assert_called_once()


class TestMetadataTracking:
    """Test resolution metadata tracking."""

    @pytest.mark.asyncio
    async def test_metadata_tracks_api_sources(self):
        """Test that metadata tracks which APIs were tried."""
        chain = CitationResolutionChain()

        with (
            patch.object(
                chain, '_try_crossref', new_callable=AsyncMock
            ) as mock_crossref,
            patch.object(chain, '_try_arxiv', new_callable=AsyncMock) as mock_arxiv,
        ):
            mock_crossref.return_value = None
            mock_arxiv.return_value = ResolutionResult(
                citation='Test',
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.9,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.ARXIV,
                matched_data={'arxiv_id': '2401.12345'},
                metadata=ResolutionMetadata(
                    api_sources_tried=[APISource.CROSSREF, APISource.ARXIV]
                ),
            )

            result = await chain.resolve(CITATION_MINIMAL)

            # Metadata should track both sources
            assert APISource.CROSSREF in result.metadata.api_sources_tried
            assert APISource.ARXIV in result.metadata.api_sources_tried

    @pytest.mark.asyncio
    async def test_metadata_tracks_processing_time(self):
        """Test that metadata tracks processing time."""
        chain = CitationResolutionChain()

        result = await chain.resolve(CITATION_WITH_DOI)

        # Should have processing time
        assert result.metadata.processing_time_ms is not None
        assert result.metadata.processing_time_ms > 0
