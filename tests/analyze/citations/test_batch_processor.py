"""
Tests for batch citation processor.

Tests cover:
- Batch processing with chunking
- Concurrent execution with rate limiting
- Checkpoint save/load functionality
- Statistics tracking and reporting
- Cache behavior
- Error handling and retry logic
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from thoth.analyze.citations.batch_processor import (
    BatchCitationProcessor,
    BatchConfig,
    BatchStatistics,
    RateLimiter,
)
from thoth.analyze.citations.resolution_types import (
    APISource,
    CitationResolutionStatus,
    ResolutionMetadata,
    ResolutionResult,
)
from thoth.utilities.schemas import Citation


@pytest.fixture
def sample_citations():
    """Create sample citations for testing."""
    return [
        Citation(
            title=f"Test Paper {i}",
            authors=[f"Author {i}"],
            year=2024,
            text=f"Author {i}. (2024). Test Paper {i}. Journal {i}."
        )
        for i in range(10)
    ]


@pytest.fixture
def batch_config(tmp_path):
    """Create test batch configuration."""
    return BatchConfig(
        chunk_size=3,
        max_concurrent=5,
        checkpoint_interval=5,
        checkpoint_path=tmp_path / "test_checkpoint.json",
        enable_caching=True,
        timeout_seconds=5.0,
        retry_attempts=2,
        retry_delay_seconds=0.1
    )


@pytest.fixture
def batch_processor(batch_config):
    """Create batch processor instance."""
    return BatchCitationProcessor(batch_config)


class TestBatchConfig:
    """Tests for BatchConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = BatchConfig()

        assert config.chunk_size == 100
        assert config.max_concurrent == 10
        assert config.checkpoint_interval == 500
        assert config.checkpoint_path is None
        assert config.enable_caching is True
        assert 'crossref' in config.rate_limits
        assert config.rate_limits['crossref'] == 50.0

    def test_config_validation(self):
        """Test configuration validation."""
        # Invalid chunk_size
        with pytest.raises(ValueError, match="chunk_size must be at least 1"):
            BatchConfig(chunk_size=0)

        # Invalid max_concurrent
        with pytest.raises(ValueError, match="max_concurrent must be at least 1"):
            BatchConfig(max_concurrent=0)

        # Invalid checkpoint_interval
        with pytest.raises(ValueError, match="checkpoint_interval cannot be negative"):
            BatchConfig(checkpoint_interval=-1)

        # Invalid timeout
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            BatchConfig(timeout_seconds=0)

    def test_custom_rate_limits(self):
        """Test custom rate limits."""
        custom_limits = {
            'crossref': 100.0,
            'custom_api': 25.0
        }
        config = BatchConfig(rate_limits=custom_limits)

        assert config.rate_limits['crossref'] == 100.0
        assert config.rate_limits['custom_api'] == 25.0


class TestBatchStatistics:
    """Tests for BatchStatistics tracking."""

    def test_initial_statistics(self):
        """Test initial statistics state."""
        stats = BatchStatistics()

        assert stats.total_citations == 0
        assert stats.processed_citations == 0
        assert stats.successful_resolutions == 0
        assert stats.cache_hits == 0
        assert len(stats.api_calls) == 0

    def test_update_from_result_success(self):
        """Test statistics update from successful result."""
        stats = BatchStatistics()
        result = ResolutionResult(
            citation="Test citation",
            status=CitationResolutionStatus.RESOLVED,
            confidence_score=0.9,
            confidence_level="high",
            source=APISource.CROSSREF,
            metadata=ResolutionMetadata()
        )

        stats.update_from_result(result)

        assert stats.processed_citations == 1
        assert stats.successful_resolutions == 1
        assert stats.api_calls[APISource.CROSSREF.value] == 1

    def test_update_from_result_failure(self):
        """Test statistics update from failed result."""
        stats = BatchStatistics()
        result = ResolutionResult(
            citation="Test citation",
            status=CitationResolutionStatus.FAILED,
            confidence_score=0.0,
            confidence_level="low",
            metadata=ResolutionMetadata(error_message="API timeout")
        )

        stats.update_from_result(result)

        assert stats.processed_citations == 1
        assert stats.failed_resolutions == 1
        assert "API timeout" in stats.errors_by_type

    def test_finalize_statistics(self):
        """Test statistics finalization."""
        stats = BatchStatistics()
        stats.start_time = datetime.utcnow()
        stats.processed_citations = 10

        # Simulate some processing time
        import time
        time.sleep(0.1)

        stats.finalize()

        assert stats.end_time is not None
        assert stats.processing_time_seconds > 0
        assert stats.average_time_per_citation > 0

    def test_to_dict(self):
        """Test statistics conversion to dictionary."""
        stats = BatchStatistics()
        stats.total_citations = 100
        stats.processed_citations = 90
        stats.successful_resolutions = 80

        stats_dict = stats.to_dict()

        assert stats_dict['total_citations'] == 100
        assert stats_dict['processed_citations'] == 90
        assert stats_dict['successful_resolutions'] == 80
        assert 'success_rate' in stats_dict
        assert stats_dict['success_rate'] == pytest.approx(88.89, rel=0.01)


class TestRateLimiter:
    """Tests for RateLimiter implementation."""

    @pytest.mark.asyncio
    async def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = RateLimiter(rate=10.0)  # 10 requests/second

        # Should allow immediate requests up to burst
        start_time = asyncio.get_event_loop().time()
        for _ in range(10):
            await limiter.acquire()
        elapsed = asyncio.get_event_loop().time() - start_time

        # Should be very fast (< 0.1s for burst)
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiter_enforces_rate(self):
        """Test that rate limiter enforces rate limits."""
        limiter = RateLimiter(rate=5.0, burst=1)  # 5 requests/second, burst of 1

        start_time = asyncio.get_event_loop().time()

        # First request should be immediate
        await limiter.acquire()

        # Second request should wait ~0.2s
        await limiter.acquire()

        elapsed = asyncio.get_event_loop().time() - start_time

        # Should take at least 0.15s (accounting for some timing variance)
        assert elapsed >= 0.15


class TestBatchCitationProcessor:
    """Tests for BatchCitationProcessor."""

    def test_initialization(self, batch_processor):
        """Test processor initialization."""
        assert batch_processor.config is not None
        assert len(batch_processor.rate_limiters) > 0
        assert batch_processor.get_cache_size() == 0

    def test_cache_key_generation(self, batch_processor):
        """Test cache key generation."""
        citation1 = Citation(
            title="Test Paper",
            authors=["Author A"],
            year=2024
        )
        citation2 = Citation(
            title="Test Paper",
            authors=["Author A"],
            year=2024
        )
        citation3 = Citation(
            title="Different Paper",
            authors=["Author A"],
            year=2024
        )

        key1 = batch_processor._get_cache_key(citation1)
        key2 = batch_processor._get_cache_key(citation2)
        key3 = batch_processor._get_cache_key(citation3)

        # Same citations should have same key
        assert key1 == key2

        # Different citations should have different keys
        assert key1 != key3

    @pytest.mark.asyncio
    async def test_mock_resolution(self, batch_processor):
        """Test mock resolution functionality."""
        citation = Citation(
            title="Test Paper",
            authors=["Author A"],
            year=2024
        )

        result = batch_processor._mock_resolution(citation)

        assert isinstance(result, ResolutionResult)
        assert result.citation is not None
        assert result.status in [
            CitationResolutionStatus.RESOLVED,
            CitationResolutionStatus.UNRESOLVED
        ]

    @pytest.mark.asyncio
    async def test_resolve_single_citation_caching(self, batch_processor):
        """Test single citation resolution with caching."""
        citation = Citation(
            title="Test Paper",
            authors=["Author A"],
            year=2024
        )

        semaphore = asyncio.Semaphore(10)

        # First resolution
        result1 = await batch_processor._resolve_single_citation(citation, semaphore)
        assert batch_processor.statistics.cache_hits == 0

        # Second resolution (should hit cache)
        result2 = await batch_processor._resolve_single_citation(citation, semaphore)
        assert batch_processor.statistics.cache_hits == 1

        # Results should be identical
        assert result1.citation == result2.citation

    @pytest.mark.asyncio
    async def test_process_batch_small(self, batch_processor, sample_citations):
        """Test processing small batch of citations."""
        # Use only 5 citations for quick test
        citations = sample_citations[:5]

        results = await batch_processor.process_batch(citations)

        assert len(results) == len(citations)
        assert batch_processor.statistics.processed_citations == len(citations)
        assert batch_processor.statistics.total_citations == len(citations)

    @pytest.mark.asyncio
    async def test_process_batch_with_chunks(self, batch_processor, sample_citations):
        """Test batch processing with chunking."""
        # Config has chunk_size=3, so 10 citations should be processed in 4 chunks
        results = await batch_processor.process_batch(sample_citations)

        assert len(results) == len(sample_citations)
        assert batch_processor.statistics.processed_citations == len(sample_citations)

    @pytest.mark.asyncio
    async def test_checkpoint_save_load(self, batch_processor, sample_citations, tmp_path):
        """Test checkpoint save and load functionality."""
        checkpoint_path = tmp_path / "checkpoint.json"
        batch_processor.config.checkpoint_path = checkpoint_path

        # Process first half
        half = len(sample_citations) // 2
        first_half = sample_citations[:half]

        results = await batch_processor.process_batch(first_half)

        # Save checkpoint
        batch_processor.save_checkpoint(results, checkpoint_path)

        # Verify checkpoint file exists
        assert checkpoint_path.exists()

        # Load checkpoint
        loaded_results = batch_processor.load_checkpoint(checkpoint_path)

        assert loaded_results is not None
        assert len(loaded_results) == len(results)

    @pytest.mark.asyncio
    async def test_checkpoint_resume(self, batch_processor, sample_citations, tmp_path):
        """Test resuming from checkpoint."""
        checkpoint_path = tmp_path / "resume_checkpoint.json"
        batch_processor.config.checkpoint_path = checkpoint_path

        # Process first 3 citations
        first_batch = sample_citations[:3]
        first_results = await batch_processor.process_batch(first_batch)

        # Save checkpoint manually
        batch_processor.save_checkpoint(first_results, checkpoint_path)

        # Create new processor with same checkpoint path
        new_processor = BatchCitationProcessor(batch_processor.config)

        # Process all citations (should resume from checkpoint)
        all_results = await new_processor.process_batch(sample_citations)

        # Should have processed all citations
        assert len(all_results) == len(sample_citations)

    @pytest.mark.asyncio
    async def test_cache_clearing(self, batch_processor):
        """Test cache clearing."""
        citation = Citation(title="Test", authors=["A"], year=2024)
        semaphore = asyncio.Semaphore(10)

        # Populate cache
        await batch_processor._resolve_single_citation(citation, semaphore)
        assert batch_processor.get_cache_size() > 0

        # Clear cache
        batch_processor.clear_cache()
        assert batch_processor.get_cache_size() == 0

    @pytest.mark.asyncio
    async def test_error_handling(self, batch_processor):
        """Test error handling during resolution."""
        # Create citation that will fail
        citation = Citation(title="Error Test", authors=[], year=None)

        # Mock resolver to raise exception
        async def failing_resolver(cit):
            raise ValueError("Simulated error")

        batch_processor.resolver = Mock()
        batch_processor.resolver.resolve = failing_resolver

        result = await batch_processor._resolve_with_retry(citation)

        # Should return failed result, not raise exception
        assert result.status == CitationResolutionStatus.FAILED
        assert result.metadata.error_message is not None

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, batch_processor, sample_citations):
        """Test comprehensive statistics tracking."""
        results = await batch_processor.process_batch(sample_citations)

        stats = batch_processor.get_statistics()

        assert stats.total_citations == len(sample_citations)
        assert stats.processed_citations == len(sample_citations)
        assert stats.start_time is not None
        assert stats.end_time is not None
        assert stats.processing_time_seconds > 0
        assert stats.successful_resolutions + stats.failed_resolutions == len(sample_citations)

    def test_get_statistics(self, batch_processor):
        """Test getting current statistics."""
        stats = batch_processor.get_statistics()

        assert isinstance(stats, BatchStatistics)
        assert stats.total_citations == 0  # No processing done yet


class TestIntegration:
    """Integration tests for batch processor."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, tmp_path):
        """Test complete workflow with checkpointing and resuming."""
        # Create config
        checkpoint_path = tmp_path / "workflow_checkpoint.json"
        config = BatchConfig(
            chunk_size=5,
            max_concurrent=10,
            checkpoint_interval=5,
            checkpoint_path=checkpoint_path,
            enable_caching=True
        )

        # Create citations
        citations = [
            Citation(
                title=f"Paper {i}",
                authors=[f"Author {i}"],
                year=2024
            )
            for i in range(15)
        ]

        # Process batch
        processor = BatchCitationProcessor(config)
        results = await processor.process_batch(citations)

        # Verify results
        assert len(results) == len(citations)
        assert checkpoint_path.exists()

        # Check statistics
        stats = processor.get_statistics()
        assert stats.processed_citations == len(citations)
        assert stats.checkpoints_saved > 0

        # Verify checkpoint content
        with open(checkpoint_path) as f:
            checkpoint_data = json.load(f)

        assert 'results' in checkpoint_data
        assert 'statistics' in checkpoint_data
        assert checkpoint_data['count'] == len(citations)
