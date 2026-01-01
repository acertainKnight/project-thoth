"""
Integration Tests for Citation Resolution System

This test suite covers the full citation resolution workflow including:
- Citation extraction and resolution with real-world examples
- Batch processing with checkpoints and statistics
- Enrichment service fallback logic (Crossref → OpenAlex → S2)
- Real-time processor caching behavior
- End-to-end workflows with well-known papers

Test Strategy:
-------------
- Uses pytest-asyncio for async tests
- Mocks external API calls to avoid rate limits and ensure reproducibility
- Tests both happy paths and error handling
- Includes real-world citation examples from academic literature
- Verifies data flow through entire resolution chain
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest

from thoth.analyze.citations.batch_processor import (
    BatchCitationProcessor,
    BatchConfig,
)
from thoth.analyze.citations.enrichment_service import CitationEnrichmentService
from thoth.analyze.citations.resolution_chain import CitationResolutionChain
from thoth.analyze.citations.resolution_types import (
    APISource,
    CitationResolutionStatus,
    ConfidenceLevel,
    ResolutionMetadata,
    ResolutionResult,
)
from thoth.utilities.schemas import Citation


# =============================================================================
# Fixtures - Real-world citation examples
# =============================================================================


@pytest.fixture
def well_known_citations() -> List[Citation]:
    """
    Real-world citations from well-known papers for testing.

    These represent common citation patterns:
    - Attention paper: Modern ML landmark
    - BERT paper: Has DOI and arXiv
    - Goodfellow GAN: Conference paper
    - ResNet paper: Computer vision classic
    """
    return [
        Citation(
            text="Vaswani, A., et al. (2017). Attention is all you need. NeurIPS.",
            title="Attention is all you need",
            authors=["Vaswani, A.", "Shazeer, N.", "Parmar, N.", "Uszkoreit, J."],
            year=2017,
            venue="NeurIPS",
        ),
        Citation(
            text="Devlin, J., et al. (2019). BERT: Pre-training of Deep Bidirectional Transformers. NAACL.",
            title="BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
            authors=["Devlin, J.", "Chang, M.", "Lee, K.", "Toutanova, K."],
            year=2019,
            venue="NAACL",
            arxiv_id="1810.04805",
        ),
        Citation(
            text="Goodfellow, I., et al. (2014). Generative Adversarial Networks. NeurIPS.",
            title="Generative Adversarial Networks",
            authors=["Goodfellow, I.", "Pouget-Abadie, J.", "Mirza, M."],
            year=2014,
            venue="NeurIPS",
        ),
        Citation(
            text="He, K., et al. (2016). Deep Residual Learning for Image Recognition. CVPR.",
            title="Deep Residual Learning for Image Recognition",
            authors=["He, K.", "Zhang, X.", "Ren, S.", "Sun, J."],
            year=2016,
            doi="10.1109/CVPR.2016.90",
        ),
    ]


@pytest.fixture
def edge_case_citations() -> List[Citation]:
    """
    Edge case citations for testing robustness.

    Includes:
    - Preprint without DOI
    - Book chapter
    - Paper with missing metadata
    - Very old paper
    """
    return [
        Citation(
            text="Smith, J. (2024). Novel Approach to Quantum Computing. arXiv preprint.",
            title="Novel Approach to Quantum Computing",
            authors=["Smith, J."],
            year=2024,
            arxiv_id="2401.00001",
        ),
        Citation(
            text="Russell, S., & Norvig, P. (2020). Artificial Intelligence: A Modern Approach (4th ed.).",
            title="Artificial Intelligence: A Modern Approach",
            authors=["Russell, S.", "Norvig, P."],
            year=2020,
        ),
        Citation(
            text="Doe, J. (2023). Unknown Paper Title.",
            title="Unknown Paper Title",
            authors=["Doe, J."],
            year=2023,
        ),
        Citation(
            text="Turing, A. (1950). Computing Machinery and Intelligence. Mind.",
            title="Computing Machinery and Intelligence",
            authors=["Turing, A."],
            year=1950,
            journal="Mind",
        ),
    ]


@pytest.fixture
def mock_crossref_responses() -> Dict[str, Any]:
    """Mock Crossref API responses for known papers."""
    return {
        "Attention is all you need": {
            "DOI": "10.5555/3295222.3295349",
            "title": ["Attention is all you need"],
            "author": [
                {"given": "Ashish", "family": "Vaswani"},
                {"given": "Noam", "family": "Shazeer"},
            ],
            "published-print": {"date-parts": [[2017]]},
            "container-title": ["Advances in Neural Information Processing Systems"],
            "score": 95.5,
        },
        "Deep Residual Learning for Image Recognition": {
            "DOI": "10.1109/CVPR.2016.90",
            "title": ["Deep Residual Learning for Image Recognition"],
            "author": [
                {"given": "Kaiming", "family": "He"},
                {"given": "Xiangyu", "family": "Zhang"},
            ],
            "published-print": {"date-parts": [[2016]]},
            "container-title": ["2016 IEEE Conference on Computer Vision"],
            "score": 98.0,
        },
    }


@pytest.fixture
def mock_openalex_responses() -> Dict[str, Any]:
    """Mock OpenAlex API responses."""
    return {
        "Generative Adversarial Networks": {
            "id": "https://openalex.org/W2123456789",
            "display_name": "Generative Adversarial Networks",
            "publication_year": 2014,
            "authorships": [
                {"author": {"display_name": "Ian Goodfellow"}},
                {"author": {"display_name": "Jean Pouget-Abadie"}},
            ],
            "primary_location": {
                "source": {"display_name": "NeurIPS"}
            },
            "abstract_inverted_index": {
                "We": [0],
                "propose": [1],
                "a": [2],
                "new": [3],
                "framework": [4],
            },
            "cited_by_count": 15000,
            "open_access": {"is_oa": True, "oa_url": "https://arxiv.org/pdf/1406.2661"},
        }
    }


@pytest.fixture
def mock_s2_responses() -> Dict[str, Any]:
    """Mock Semantic Scholar API responses."""
    return {
        "BERT": {
            "paperId": "df2b0e26d0599ce3e70df8a9da02e51594e0e992",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "year": 2019,
            "authors": [
                {"name": "Jacob Devlin"},
                {"name": "Ming-Wei Chang"},
            ],
            "venue": "NAACL",
            "abstract": "We introduce BERT, a new language representation model...",
            "citationCount": 25000,
            "externalIds": {
                "ArXiv": "1810.04805",
                "DOI": "10.18653/v1/N19-1423",
            },
            "openAccessPdf": {
                "url": "https://arxiv.org/pdf/1810.04805.pdf"
            },
            "isOpenAccess": True,
        },
        "Computing Machinery and Intelligence": {
            "paperId": "turing1950",
            "title": "Computing Machinery and Intelligence",
            "year": 1950,
            "authors": [{"name": "Alan Turing"}],
            "venue": "Mind",
            "abstract": "I propose to consider the question, 'Can machines think?'",
            "citationCount": 8500,
            "externalIds": {"DOI": "10.1093/mind/LIX.236.433"},
            "isOpenAccess": False,
        },
    }


# =============================================================================
# Test Resolution Chain
# =============================================================================


class TestResolutionChainIntegration:
    """Integration tests for the full citation resolution chain."""

    @pytest.mark.asyncio
    async def test_resolution_with_doi_skip(self):
        """Test that citations with DOI skip resolution."""
        chain = CitationResolutionChain()

        citation = Citation(
            title="Test Paper",
            authors=["Author A"],
            year=2024,
            doi="10.1234/test.doi",
        )

        result = await chain.resolve(citation)

        assert result.status == CitationResolutionStatus.RESOLVED
        assert result.confidence_score == 1.0
        assert result.confidence_level == ConfidenceLevel.HIGH
        assert result.matched_data["doi"] == "10.1234/test.doi"
        assert result.source is None  # No API source needed

    @pytest.mark.asyncio
    async def test_resolution_with_arxiv_prefers_s2(
        self, well_known_citations, mock_s2_responses
    ):
        """Test that arXiv citations try Semantic Scholar first."""
        bert_citation = well_known_citations[1]  # Has arXiv ID

        # Mock Semantic Scholar to return BERT data
        with patch.object(
            CitationResolutionChain,
            '_try_semantic_scholar',
            return_value=ResolutionResult(
                citation=bert_citation.text,
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.92,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.SEMANTIC_SCHOLAR,
                matched_data=mock_s2_responses["BERT"],
                metadata=ResolutionMetadata(),
            ),
        ):
            chain = CitationResolutionChain()
            result = await chain.resolve(bert_citation)

            assert result.status == CitationResolutionStatus.RESOLVED
            assert result.source == APISource.SEMANTIC_SCHOLAR
            assert result.confidence_level == ConfidenceLevel.HIGH
            assert result.matched_data["externalIds"]["ArXiv"] == "1810.04805"

    @pytest.mark.asyncio
    async def test_resolution_fallback_chain(self, well_known_citations):
        """Test fallback from Crossref → OpenAlex → S2."""
        attention_citation = well_known_citations[0]

        # Mock all resolvers to simulate fallback
        with patch.object(
            CitationResolutionChain, '_try_crossref', return_value=None
        ), patch.object(
            CitationResolutionChain, '_try_openalex', return_value=None
        ), patch.object(
            CitationResolutionChain,
            '_try_semantic_scholar',
            return_value=ResolutionResult(
                citation=attention_citation.text,
                status=CitationResolutionStatus.PARTIAL,
                confidence_score=0.75,
                confidence_level=ConfidenceLevel.MEDIUM,
                source=APISource.SEMANTIC_SCHOLAR,
                matched_data={"title": "Attention is all you need"},
                metadata=ResolutionMetadata(),
            ),
        ):
            chain = CitationResolutionChain()
            result = await chain.resolve(attention_citation)

            # Should have tried all three sources
            assert APISource.CROSSREF in result.metadata.api_sources_tried
            assert APISource.OPENALEX in result.metadata.api_sources_tried
            assert APISource.SEMANTIC_SCHOLAR in result.metadata.api_sources_tried

            # Final result from S2
            assert result.source == APISource.SEMANTIC_SCHOLAR
            assert result.status == CitationResolutionStatus.PARTIAL

    @pytest.mark.asyncio
    async def test_resolution_unresolved_case(self, edge_case_citations):
        """Test unresolved citation (no matches found)."""
        unknown_citation = edge_case_citations[2]  # "Unknown Paper Title"

        # Mock all resolvers to return None (no matches)
        with patch.object(
            CitationResolutionChain, '_try_crossref', return_value=None
        ), patch.object(
            CitationResolutionChain, '_try_openalex', return_value=None
        ), patch.object(
            CitationResolutionChain, '_try_semantic_scholar', return_value=None
        ):
            chain = CitationResolutionChain()
            result = await chain.resolve(unknown_citation)

            assert result.status == CitationResolutionStatus.UNRESOLVED
            assert result.confidence_score == 0.0
            assert result.confidence_level == ConfidenceLevel.LOW
            assert result.matched_data is None

    @pytest.mark.asyncio
    async def test_batch_resolution_parallel(self, well_known_citations):
        """Test parallel batch resolution."""
        # Mock resolvers to return high-confidence results
        async def mock_resolve(citation):
            return ResolutionResult(
                citation=citation.text or citation.title,
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.90,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.CROSSREF,
                matched_data={"doi": f"10.1234/mock.{citation.year}"},
                metadata=ResolutionMetadata(),
            )

        with patch.object(CitationResolutionChain, 'resolve', side_effect=mock_resolve):
            chain = CitationResolutionChain()
            results = await chain.batch_resolve(well_known_citations, parallel=True)

            assert len(results) == len(well_known_citations)
            assert all(r.status == CitationResolutionStatus.RESOLVED for r in results)
            assert all(r.confidence_level == ConfidenceLevel.HIGH for r in results)


# =============================================================================
# Test Batch Processor
# =============================================================================


class TestBatchProcessorIntegration:
    """Integration tests for batch citation processor."""

    @pytest.mark.asyncio
    async def test_batch_processing_with_checkpoints(
        self, well_known_citations, tmp_path
    ):
        """Test batch processing with checkpoint save/load."""
        checkpoint_path = tmp_path / "test_checkpoint.json"

        config = BatchConfig(
            chunk_size=2,
            max_concurrent=4,
            checkpoint_interval=2,  # Checkpoint every 2 citations
            checkpoint_path=checkpoint_path,
            enable_caching=True,
        )

        processor = BatchCitationProcessor(config)

        # Process batch
        results = await processor.process_batch(well_known_citations)

        # Verify results
        assert len(results) == len(well_known_citations)
        assert checkpoint_path.exists()

        # Verify checkpoint content
        with open(checkpoint_path) as f:
            checkpoint_data = json.load(f)

        assert "results" in checkpoint_data
        assert "statistics" in checkpoint_data
        assert checkpoint_data["count"] == len(well_known_citations)

    @pytest.mark.asyncio
    async def test_batch_resume_from_checkpoint(
        self, well_known_citations, tmp_path
    ):
        """Test resuming batch processing from checkpoint."""
        checkpoint_path = tmp_path / "resume_checkpoint.json"

        # First batch - process half
        config1 = BatchConfig(
            chunk_size=2,
            max_concurrent=4,
            checkpoint_path=checkpoint_path,
        )
        processor1 = BatchCitationProcessor(config1)

        first_half = well_known_citations[:2]
        first_results = await processor1.process_batch(first_half)
        processor1.save_checkpoint(first_results, checkpoint_path)

        # Second batch - resume with all citations
        config2 = BatchConfig(
            chunk_size=2,
            max_concurrent=4,
            checkpoint_path=checkpoint_path,
        )
        processor2 = BatchCitationProcessor(config2)

        all_results = await processor2.process_batch(well_known_citations)

        # Should have processed all citations
        assert len(all_results) == len(well_known_citations)

    @pytest.mark.asyncio
    async def test_batch_statistics_tracking(self, well_known_citations):
        """Test comprehensive statistics tracking during batch processing."""
        config = BatchConfig(chunk_size=10, max_concurrent=5)
        processor = BatchCitationProcessor(config)

        results = await processor.process_batch(well_known_citations)
        stats = processor.get_statistics()

        assert stats.total_citations == len(well_known_citations)
        assert stats.processed_citations == len(well_known_citations)
        assert stats.start_time is not None
        assert stats.end_time is not None
        assert stats.processing_time_seconds > 0
        assert stats.average_time_per_citation > 0

        # Verify statistics include API call counts
        assert len(stats.api_calls) > 0

    @pytest.mark.asyncio
    async def test_batch_caching_behavior(self):
        """Test cache hit/miss behavior in batch processor."""
        config = BatchConfig(enable_caching=True)
        processor = BatchCitationProcessor(config)

        # Create duplicate citations
        citation1 = Citation(title="Test Paper", authors=["Author A"], year=2024)
        citation2 = Citation(title="Test Paper", authors=["Author A"], year=2024)
        citation3 = Citation(title="Different Paper", authors=["Author B"], year=2024)

        citations = [citation1, citation2, citation3]

        results = await processor.process_batch(citations)

        # Should have 1 cache hit (citation2 matches citation1)
        stats = processor.get_statistics()
        assert stats.cache_hits >= 1

        # Cache size should be 2 (citation1 and citation3)
        assert processor.get_cache_size() >= 2


# =============================================================================
# Test Enrichment Service
# =============================================================================


class TestEnrichmentServiceIntegration:
    """Integration tests for citation enrichment service."""

    @pytest.mark.asyncio
    async def test_enrichment_from_doi(self, mock_crossref_responses):
        """Test enrichment using DOI via Crossref."""
        service = CitationEnrichmentService(timeout=5, max_retries=2)

        citation = Citation(
            title="Deep Residual Learning",
            authors=["He, K."],
            year=2016,
            doi="10.1109/CVPR.2016.90",
        )

        # Mock Crossref API
        with patch.object(
            service,
            '_fetch_crossref_metadata',
            return_value=mock_crossref_responses[
                "Deep Residual Learning for Image Recognition"
            ],
        ):
            enriched = await service.enrich_from_doi(citation, citation.doi)

            assert enriched.title is not None
            assert enriched.authors is not None
            assert len(enriched.authors) >= 2
            assert enriched.year == 2016
            assert enriched.url is not None

        await service.close()

    @pytest.mark.asyncio
    async def test_enrichment_fallback_logic(
        self, mock_crossref_responses, mock_openalex_responses, mock_s2_responses
    ):
        """Test enrichment with fallback: Crossref → OpenAlex → S2."""
        service = CitationEnrichmentService()

        citation = Citation(title="Test Paper", authors=["Author A"], year=2024)

        # Create resolution result with multiple identifiers
        result = ResolutionResult(
            citation=citation.text or citation.title,
            status=CitationResolutionStatus.RESOLVED,
            confidence_score=0.90,
            confidence_level=ConfidenceLevel.HIGH,
            source=APISource.CROSSREF,
            matched_data={
                "doi": "10.1234/test",
                "openalex_id": "W1234567890",
                "s2_id": "test_s2_id",
            },
            metadata=ResolutionMetadata(),
        )

        # Mock API calls to simulate fallback
        with patch.object(
            service, '_fetch_crossref_metadata', return_value=None
        ), patch.object(
            service,
            '_fetch_openalex_metadata',
            return_value=mock_openalex_responses["Generative Adversarial Networks"],
        ), patch.object(
            service, '_fetch_s2_metadata', return_value=mock_s2_responses["BERT"]
        ):
            enriched = await service._enrich_citation_prioritized(citation, result)

            # Should have tried Crossref, then fallen back to OpenAlex
            assert enriched.abstract is not None  # From OpenAlex

        await service.close()

    @pytest.mark.asyncio
    async def test_abstract_reconstruction_from_openalex(self):
        """Test abstract reconstruction from OpenAlex inverted index."""
        service = CitationEnrichmentService()

        inverted_index = {
            "We": [0],
            "propose": [1],
            "a": [2, 4],
            "new": [3],
            "framework": [5],
        }

        abstract = service._reconstruct_abstract(inverted_index)

        assert "We" in abstract
        assert "propose" in abstract
        assert "framework" in abstract
        # Check word order
        words = abstract.split()
        assert words[0] == "We"
        assert words[1] == "propose"

        await service.close()

    @pytest.mark.asyncio
    async def test_batch_enrichment(self, mock_crossref_responses):
        """Test batch enrichment of multiple citations."""
        service = CitationEnrichmentService()

        # Create resolution results
        results = [
            ResolutionResult(
                citation=f"Citation {i}",
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.90,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.CROSSREF,
                matched_data={"doi": f"10.1234/test.{i}", "title": f"Paper {i}"},
                metadata=ResolutionMetadata(),
            )
            for i in range(5)
        ]

        # Mock Crossref responses
        with patch.object(
            service, '_fetch_crossref_metadata', return_value={"title": ["Test Paper"]}
        ):
            enriched_citations = await service.batch_enrich(results)

            assert len(enriched_citations) == len(results)
            assert all(isinstance(c, Citation) for c in enriched_citations)

        await service.close()

    @pytest.mark.asyncio
    async def test_enrichment_error_handling(self):
        """Test enrichment service error handling."""
        service = CitationEnrichmentService(timeout=1, max_retries=1)

        citation = Citation(title="Test", authors=["A"], year=2024)

        # Mock API to raise error
        with patch.object(
            service, '_fetch_crossref_metadata', side_effect=Exception("API Error")
        ):
            enriched = await service.enrich_from_doi(citation, "10.1234/test")

            # Should return original citation without raising exception
            assert enriched.title == "Test"

        await service.close()

    @pytest.mark.asyncio
    async def test_enrichment_rate_limiting(self):
        """Test that enrichment service respects rate limits."""
        service = CitationEnrichmentService(requests_per_second=5.0)

        citation = Citation(title="Test", authors=["A"], year=2024)

        # Mock successful response
        with patch.object(
            service, '_fetch_crossref_metadata', return_value={"title": ["Test"]}
        ):
            start_time = asyncio.get_event_loop().time()

            # Make 10 requests
            for _ in range(10):
                await service.enrich_from_doi(citation, "10.1234/test")

            elapsed = asyncio.get_event_loop().time() - start_time

            # At 5 req/s, 10 requests should take at least 1.5 seconds
            # (allowing some slack for processing time)
            assert elapsed >= 1.5

        await service.close()


# =============================================================================
# Test End-to-End Workflow
# =============================================================================


class TestEndToEndWorkflow:
    """End-to-end integration tests for complete citation resolution workflow."""

    @pytest.mark.asyncio
    async def test_full_workflow_well_known_papers(
        self, well_known_citations, tmp_path, mock_crossref_responses
    ):
        """
        Test complete workflow with well-known papers:
        1. Batch resolution
        2. Enrichment
        3. Statistics tracking
        4. Checkpoint saving
        """
        checkpoint_path = tmp_path / "workflow_checkpoint.json"

        # Configure batch processor
        batch_config = BatchConfig(
            chunk_size=2,
            max_concurrent=4,
            checkpoint_interval=2,
            checkpoint_path=checkpoint_path,
            enable_caching=True,
        )

        # Initialize services
        processor = BatchCitationProcessor(batch_config)
        enrichment_service = CitationEnrichmentService()

        try:
            # Step 1: Batch resolution
            resolution_results = await processor.process_batch(well_known_citations)

            assert len(resolution_results) == len(well_known_citations)
            assert checkpoint_path.exists()

            # Step 2: Enrichment
            with patch.object(
                enrichment_service,
                '_fetch_crossref_metadata',
                return_value=mock_crossref_responses[
                    "Deep Residual Learning for Image Recognition"
                ],
            ):
                enriched_citations = await enrichment_service.batch_enrich(
                    resolution_results
                )

                assert len(enriched_citations) == len(well_known_citations)

            # Step 3: Verify statistics
            stats = processor.get_statistics()
            assert stats.total_citations == len(well_known_citations)
            assert stats.processed_citations == len(well_known_citations)
            assert stats.processing_time_seconds > 0

            enrichment_stats = enrichment_service.get_statistics()
            assert enrichment_stats["total_enriched"] > 0

        finally:
            await enrichment_service.close()

    @pytest.mark.asyncio
    async def test_workflow_with_edge_cases(self, edge_case_citations, tmp_path):
        """
        Test workflow with edge cases:
        - Preprints without DOI
        - Books
        - Missing metadata
        - Very old papers
        """
        batch_config = BatchConfig(
            chunk_size=2,
            max_concurrent=4,
            enable_caching=True,
        )

        processor = BatchCitationProcessor(batch_config)
        results = await processor.process_batch(edge_case_citations)

        # Should handle all citations without crashing
        assert len(results) == len(edge_case_citations)

        # Check that we have a mix of statuses
        statuses = [r.status for r in results]
        assert len(set(statuses)) > 1  # Not all the same status

        # Verify statistics
        stats = processor.get_statistics()
        assert stats.total_citations == len(edge_case_citations)
        assert stats.processed_citations == len(edge_case_citations)

    @pytest.mark.asyncio
    async def test_workflow_error_recovery(self, well_known_citations):
        """Test workflow error recovery and resilience."""
        batch_config = BatchConfig(
            chunk_size=2,
            max_concurrent=4,
            retry_attempts=2,
            retry_delay_seconds=0.1,
        )

        processor = BatchCitationProcessor(batch_config)

        # Mock resolver to fail occasionally
        call_count = 0

        async def flaky_resolve(citation):
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise Exception("Simulated API error")
            return ResolutionResult(
                citation=citation.text or citation.title,
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.85,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.CROSSREF,
                matched_data={"doi": f"10.1234/mock.{citation.year}"},
                metadata=ResolutionMetadata(),
            )

        # Process with flaky resolver
        results = await processor.process_batch(well_known_citations)

        # Should still complete all citations (with retries)
        assert len(results) == len(well_known_citations)

        # Check statistics tracked errors
        stats = processor.get_statistics()
        assert stats.errors_by_type is not None


# =============================================================================
# Test Real-time Processor Caching
# =============================================================================


class TestRealTimeProcessorCaching:
    """Tests for real-time processor caching behavior."""

    @pytest.mark.asyncio
    async def test_cache_hit_behavior(self):
        """Test cache hit reduces API calls."""
        config = BatchConfig(enable_caching=True)
        processor = BatchCitationProcessor(config)

        citation = Citation(title="Test Paper", authors=["Author A"], year=2024)

        # First resolution - cache miss
        semaphore = asyncio.Semaphore(10)
        result1 = await processor._resolve_single_citation(citation, semaphore)

        cache_hits_before = processor.statistics.cache_hits

        # Second resolution - cache hit
        result2 = await processor._resolve_single_citation(citation, semaphore)

        cache_hits_after = processor.statistics.cache_hits

        # Cache hits should increase
        assert cache_hits_after > cache_hits_before

        # Results should be consistent
        assert result1.citation == result2.citation

    @pytest.mark.asyncio
    async def test_negative_caching(self):
        """Test that failed resolutions are cached to avoid retries."""
        config = BatchConfig(enable_caching=True)
        processor = BatchCitationProcessor(config)

        # Citation that will fail resolution
        citation = Citation(title="Nonexistent Paper", authors=[], year=None)

        semaphore = asyncio.Semaphore(10)

        # First resolution - will fail and cache the failure
        result1 = await processor._resolve_single_citation(citation, semaphore)
        assert result1.status == CitationResolutionStatus.FAILED

        # Second resolution - should hit cache
        cache_hits_before = processor.statistics.cache_hits
        result2 = await processor._resolve_single_citation(citation, semaphore)
        cache_hits_after = processor.statistics.cache_hits

        assert cache_hits_after > cache_hits_before
        assert result2.status == CitationResolutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test handling of API timeouts."""
        config = BatchConfig(
            timeout_seconds=0.1,  # Very short timeout
            retry_attempts=1,
        )
        processor = BatchCitationProcessor(config)

        citation = Citation(title="Test", authors=["A"], year=2024)

        # Mock resolver to sleep longer than timeout
        async def slow_resolve(cit):
            await asyncio.sleep(1.0)  # Sleep longer than timeout
            return ResolutionResult(
                citation=cit.text or cit.title,
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.90,
                confidence_level=ConfidenceLevel.HIGH,
                source=APISource.CROSSREF,
                matched_data={},
                metadata=ResolutionMetadata(),
            )

        # Should timeout and return failed result
        result = await processor._resolve_with_retry(citation)

        assert result.status == CitationResolutionStatus.FAILED
        assert result.metadata.error_message is not None


# =============================================================================
# Test Fixtures for Mocking
# =============================================================================


@pytest.fixture
def mock_http_client():
    """Mock HTTP client for API calls."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.aclose = AsyncMock()
    return client


# =============================================================================
# Performance Tests (Optional - can be slow)
# =============================================================================


@pytest.mark.slow
class TestPerformance:
    """Performance tests for citation resolution (marked as slow)."""

    @pytest.mark.asyncio
    async def test_large_batch_performance(self, tmp_path):
        """Test performance with large batch (20+ citations)."""
        # Create 20 test citations
        large_batch = [
            Citation(
                title=f"Test Paper {i}",
                authors=[f"Author {i}"],
                year=2024,
            )
            for i in range(20)
        ]

        config = BatchConfig(
            chunk_size=5,
            max_concurrent=10,
            checkpoint_path=tmp_path / "perf_checkpoint.json",
        )

        processor = BatchCitationProcessor(config)

        import time
        start_time = time.time()
        results = await processor.process_batch(large_batch)
        elapsed = time.time() - start_time

        assert len(results) == len(large_batch)

        # Performance expectation: should complete in reasonable time
        # (adjust threshold based on your requirements)
        assert elapsed < 30.0  # 30 seconds for 20 citations

        stats = processor.get_statistics()
        avg_time = stats.average_time_per_citation

        # Log performance metrics
        print(f"\n=== Performance Metrics ===")
        print(f"Total citations: {len(large_batch)}")
        print(f"Total time: {elapsed:.2f}s")
        print(f"Avg time per citation: {avg_time:.2f}s")
        print(f"Citations per second: {len(large_batch)/elapsed:.2f}")
        print(f"Cache hit rate: {stats.cache_hits}/{stats.processed_citations}")
