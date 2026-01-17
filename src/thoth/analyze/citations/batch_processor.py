"""
Batch Citation Processor for Large-Scale Citation Resolution

This module provides efficient batch processing capabilities for resolving large
numbers of citations with features including:
- Chunked processing with configurable batch sizes
- Parallel/concurrent execution with rate limiting
- Checkpoint/resume functionality for long-running operations
- Progress tracking and statistics reporting
- Caching to avoid duplicate API calls
"""

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional  # noqa: UP035

from loguru import logger

try:
    from tqdm.asyncio import tqdm_asyncio

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    logger.warning('tqdm not available - progress bars disabled')

from thoth.analyze.citations.resolution_types import (
    APISource,
    CitationResolutionStatus,
    ResolutionMetadata,
    ResolutionResult,
)
from thoth.utilities.schemas import Citation


@dataclass
class BatchConfig:
    """
    Configuration for batch citation processing.

    Attributes:
        chunk_size: Number of citations to process per chunk (100-500 recommended)
        max_concurrent: Maximum concurrent API requests (10-20 recommended)
        checkpoint_interval: Save checkpoint every N citations (0 = disabled)
        checkpoint_path: Path to save checkpoints (None = disabled)
        enable_caching: Enable in-memory caching of API responses
        rate_limits: API-specific rate limits (requests per second)
        timeout_seconds: Timeout for individual citation resolution
        retry_attempts: Number of retry attempts for failed resolutions
        retry_delay_seconds: Delay between retry attempts
    """

    chunk_size: int = 100
    max_concurrent: int = 10
    checkpoint_interval: int = 500
    checkpoint_path: Optional[Path] = None  # noqa: UP007
    enable_caching: bool = True
    rate_limits: dict[str, float] = field(
        default_factory=lambda: {
            'crossref': 50.0,  # 50 requests/second
            'openalex': 10.0,  # 10 requests/second
            'semantic_scholar': 100.0,  # 100 requests/second
            'arxiv': 3.0,  # 3 requests/second
        }
    )
    timeout_seconds: float = 30.0
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.chunk_size < 1:
            raise ValueError('chunk_size must be at least 1')
        if self.max_concurrent < 1:
            raise ValueError('max_concurrent must be at least 1')
        if self.checkpoint_interval < 0:
            raise ValueError('checkpoint_interval cannot be negative')
        if self.timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be positive')
        if self.retry_attempts < 0:
            raise ValueError('retry_attempts cannot be negative')


@dataclass
class BatchStatistics:
    """
    Statistics for batch processing operations.

    Tracks comprehensive metrics about the batch processing run including
    success rates, timing, API usage, and error patterns.
    """

    total_citations: int = 0
    processed_citations: int = 0
    successful_resolutions: int = 0
    failed_resolutions: int = 0
    partial_resolutions: int = 0
    cache_hits: int = 0
    api_calls: dict[str, int] = field(default_factory=dict)
    start_time: Optional[datetime] = None  # noqa: UP007
    end_time: Optional[datetime] = None  # noqa: UP007
    processing_time_seconds: float = 0.0
    average_time_per_citation: float = 0.0
    checkpoints_saved: int = 0
    errors_by_type: dict[str, int] = field(default_factory=dict)

    def update_from_result(self, result: ResolutionResult):
        """Update statistics from a resolution result."""
        self.processed_citations += 1

        if result.status == CitationResolutionStatus.RESOLVED:
            self.successful_resolutions += 1
        elif result.status == CitationResolutionStatus.PARTIAL:
            self.partial_resolutions += 1
        elif result.status == CitationResolutionStatus.FAILED:
            self.failed_resolutions += 1

        # Track API usage
        if result.source:
            source_key = result.source.value
            self.api_calls[source_key] = self.api_calls.get(source_key, 0) + 1

        # Track errors
        if result.metadata.error_message:
            error_key = result.metadata.error_message[:50]  # Truncate long errors
            self.errors_by_type[error_key] = self.errors_by_type.get(error_key, 0) + 1

    def finalize(self):
        """Finalize statistics at the end of processing."""
        if self.start_time and not self.end_time:
            self.end_time = datetime.utcnow()
            self.processing_time_seconds = (
                self.end_time - self.start_time
            ).total_seconds()

        if self.processed_citations > 0:
            self.average_time_per_citation = (
                self.processing_time_seconds / self.processed_citations
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert statistics to dictionary format."""
        return {
            'total_citations': self.total_citations,
            'processed_citations': self.processed_citations,
            'successful_resolutions': self.successful_resolutions,
            'failed_resolutions': self.failed_resolutions,
            'partial_resolutions': self.partial_resolutions,
            'cache_hits': self.cache_hits,
            'api_calls': self.api_calls,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'processing_time_seconds': self.processing_time_seconds,
            'average_time_per_citation': self.average_time_per_citation,
            'checkpoints_saved': self.checkpoints_saved,
            'errors_by_type': self.errors_by_type,
            'success_rate': (
                self.successful_resolutions / self.processed_citations * 100
                if self.processed_citations > 0
                else 0.0
            ),
        }


class RateLimiter:
    """
    Token bucket rate limiter for API calls.

    Implements a token bucket algorithm to enforce per-API rate limits
    while allowing burst capacity.
    """

    def __init__(self, rate: float, burst: Optional[int] = None):  # noqa: UP007
        """
        Initialize rate limiter.

        Args:
            rate: Maximum requests per second
            burst: Maximum burst size (defaults to rate)
        """
        self.rate = rate
        self.burst = burst or int(rate)
        self.tokens = self.burst
        self.last_update = time.monotonic()
        self._lock: Optional[asyncio.Lock] = None  # Lazy init to avoid event loop binding

    def _get_lock(self) -> asyncio.Lock:
        """Get or create the lock (lazy init to avoid event loop binding)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def acquire(self):
        """Acquire permission to make a request (blocks if rate limit reached)."""
        async with self._get_lock():
            now = time.monotonic()
            elapsed = now - self.last_update

            # Refill tokens based on elapsed time
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now

            # Wait if no tokens available
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 1

            self.tokens -= 1


class BatchCitationProcessor:
    """
    Large-scale citation resolution with batch processing capabilities.

    This processor handles efficient resolution of large citation datasets with:
    - Chunked processing to manage memory and API limits
    - Configurable parallelization for optimal throughput
    - Automatic checkpointing for resume capability
    - Comprehensive progress tracking and statistics
    - Intelligent caching and rate limiting

    Example:
        >>> config = BatchConfig(
        ...     chunk_size=100,
        ...     max_concurrent=10,
        ...     checkpoint_path=Path('checkpoints/citations.json'),
        ... )
        >>> processor = BatchCitationProcessor(config, resolver)
        >>> results = await processor.process_batch(citations, config)
    """

    def __init__(self, config: BatchConfig, resolver=None):
        """
        Initialize batch processor.

        Args:
            config: Batch processing configuration
            resolver: Citation resolver instance (optional for testing)
        """
        self.config = config
        self.resolver = resolver

        # Initialize rate limiters for each API
        self.rate_limiters = {
            api: RateLimiter(rate) for api, rate in config.rate_limits.items()
        }

        # In-memory cache for resolved citations with bounded size
        # Using LRUCache to prevent unbounded growth during batch processing
        from cachetools import LRUCache

        self._cache: LRUCache = LRUCache(maxsize=5000)  # 5000 citations max

        # Statistics tracking
        self.statistics = BatchStatistics()

    def _get_cache_key(self, citation: Citation) -> str:
        """Generate cache key for a citation."""
        # Use title + first author + year as key
        key_parts = [
            citation.title or '',
            citation.authors[0] if citation.authors else '',
            str(citation.year or ''),
        ]
        key_string = '|'.join(key_parts).lower()
        return hashlib.md5(key_string.encode()).hexdigest()

    async def _resolve_single_citation(
        self, citation: Citation, semaphore: asyncio.Semaphore
    ) -> ResolutionResult:
        """
        Resolve a single citation with rate limiting and caching.

        Args:
            citation: Citation to resolve
            semaphore: Semaphore for concurrency control

        Returns:
            Resolution result with metadata
        """
        start_time = time.monotonic()
        cache_key = self._get_cache_key(citation)

        # Check cache if enabled
        if self.config.enable_caching and cache_key in self._cache:
            self.statistics.cache_hits += 1
            title_preview = citation.title[:50] if citation.title else 'Unknown'
            logger.debug(f'Cache hit for citation: {title_preview}')
            return self._cache[cache_key]

        async with semaphore:
            # Rate limiting (use first available API limiter as default)
            if self.rate_limiters:
                limiter = next(iter(self.rate_limiters.values()))
                await limiter.acquire()

            # Perform resolution with retry logic
            result = await self._resolve_with_retry(citation)

            # Add timing metadata
            processing_time = (time.monotonic() - start_time) * 1000
            result.metadata.processing_time_ms = processing_time

            # Cache the result
            if self.config.enable_caching:
                self._cache[cache_key] = result

            return result

    async def _resolve_with_retry(self, citation: Citation) -> ResolutionResult:
        """
        Resolve citation with retry logic.

        Args:
            citation: Citation to resolve

        Returns:
            Resolution result
        """
        last_error = None

        for attempt in range(self.config.retry_attempts):
            try:
                # Mock resolution for testing if no resolver provided
                if self.resolver is None:
                    result = self._mock_resolution(citation)
                else:
                    # Call actual resolver (would be implemented by caller)
                    result = await self._call_resolver(citation)

                return result

            except Exception as e:
                last_error = e
                title_preview = citation.title[:50] if citation.title else 'Unknown'
                logger.warning(
                    f'Resolution attempt {attempt + 1}/{self.config.retry_attempts} '
                    f"failed for '{title_preview}': {e}"
                )

                if attempt < self.config.retry_attempts - 1:
                    await asyncio.sleep(self.config.retry_delay_seconds)

        # All retries failed - return failed result
        return ResolutionResult(
            citation=citation.text or citation.title or 'Unknown citation',
            status=CitationResolutionStatus.FAILED,
            confidence_score=0.0,
            confidence_level='low',
            metadata=ResolutionMetadata(
                attempt_count=self.config.retry_attempts,
                error_message=str(last_error),
                last_attempt_time=datetime.utcnow(),
            ),
        )

    def _mock_resolution(self, citation: Citation) -> ResolutionResult:
        """Mock resolution for testing purposes."""
        # Simulate varying success rates
        import random

        success = random.random() > 0.1  # 90% success rate

        if success:
            return ResolutionResult(
                citation=citation.text or citation.title or 'Unknown',
                status=CitationResolutionStatus.RESOLVED,
                confidence_score=0.85,
                confidence_level='high',
                source=APISource.CROSSREF,
                matched_data={
                    'doi': citation.doi
                    or f'10.1234/mock-{hash(citation.title) % 10000}',
                    'title': citation.title,
                    'authors': citation.authors or [],
                    'year': citation.year,
                },
                metadata=ResolutionMetadata(
                    attempt_count=1, api_sources_tried=[APISource.CROSSREF]
                ),
            )
        else:
            return ResolutionResult(
                citation=citation.text or citation.title or 'Unknown',
                status=CitationResolutionStatus.UNRESOLVED,
                confidence_score=0.3,
                confidence_level='low',
                metadata=ResolutionMetadata(
                    attempt_count=1, error_message='No match found'
                ),
            )

    async def _call_resolver(self, citation: Citation) -> ResolutionResult:
        """
        Call the actual citation resolver.

        This would be implemented to call whatever resolver is provided,
        with timeout handling.
        """
        try:
            # Wrap resolver call with timeout
            result = await asyncio.wait_for(
                self.resolver.resolve(citation), timeout=self.config.timeout_seconds
            )
            return result
        except asyncio.TimeoutError:  # noqa: UP041
            return ResolutionResult(
                citation=citation.text or citation.title or 'Unknown',
                status=CitationResolutionStatus.FAILED,
                confidence_score=0.0,
                confidence_level='low',
                metadata=ResolutionMetadata(
                    error_message=f'Resolution timeout after {self.config.timeout_seconds}s'
                ),
            )

    async def process_batch(
        self,
        citations: List[Citation],  # noqa: UP006
        config: Optional[BatchConfig] = None,  # noqa: UP007
    ) -> List[ResolutionResult]:  # noqa: UP006
        """
        Process a batch of citations with chunking, parallelization, and checkpointing.

        Args:
            citations: List of citations to resolve
            config: Optional config override (uses instance config if not provided)

        Returns:
            List of resolution results
        """
        if config is None:
            config = self.config

        # Initialize statistics
        self.statistics = BatchStatistics()
        self.statistics.total_citations = len(citations)
        self.statistics.start_time = datetime.utcnow()

        logger.info(f'Starting batch processing of {len(citations)} citations')
        logger.info(
            f'Config: chunk_size={config.chunk_size}, '
            f'max_concurrent={config.max_concurrent}'
        )

        # Check for existing checkpoint to resume from
        results = []
        start_index = 0

        if config.checkpoint_path and config.checkpoint_path.exists():
            checkpoint_data = self.load_checkpoint(config.checkpoint_path)
            if checkpoint_data:
                results = checkpoint_data
                start_index = len(results)
                logger.info(
                    f'Resuming from checkpoint: {start_index} citations already processed'
                )

        # Process citations in chunks
        semaphore = asyncio.Semaphore(config.max_concurrent)

        for chunk_start in range(start_index, len(citations), config.chunk_size):
            chunk_end = min(chunk_start + config.chunk_size, len(citations))
            chunk = citations[chunk_start:chunk_end]

            logger.info(
                f'Processing chunk {chunk_start}-{chunk_end} ({len(chunk)} citations)'
            )

            # Process chunk with progress bar if available
            if TQDM_AVAILABLE:
                chunk_results = await tqdm_asyncio.gather(
                    *[self._resolve_single_citation(cit, semaphore) for cit in chunk],
                    desc=f'Chunk {chunk_start // config.chunk_size + 1}',
                    return_exceptions=True,
                )
            else:
                chunk_results = await asyncio.gather(
                    *[self._resolve_single_citation(cit, semaphore) for cit in chunk],
                    return_exceptions=True,
                )

            # Handle exceptions and update statistics
            for result in chunk_results:
                if isinstance(result, Exception):
                    logger.error(f'Unexpected error during resolution: {result}')
                    # Create failed result
                    failed_result = ResolutionResult(
                        citation='Error',
                        status=CitationResolutionStatus.FAILED,
                        confidence_score=0.0,
                        confidence_level='low',
                        metadata=ResolutionMetadata(error_message=str(result)),
                    )
                    results.append(failed_result)
                    self.statistics.update_from_result(failed_result)
                else:
                    results.append(result)
                    self.statistics.update_from_result(result)

            # Save checkpoint if configured
            if (
                config.checkpoint_path
                and config.checkpoint_interval > 0
                and len(results) % config.checkpoint_interval == 0
            ):
                self.save_checkpoint(results, config.checkpoint_path)
                self.statistics.checkpoints_saved += 1
                logger.info(f'Checkpoint saved: {len(results)} results')

            # Log progress
            self._log_progress_stats()

        # Final checkpoint save
        if config.checkpoint_path:
            self.save_checkpoint(results, config.checkpoint_path)
            self.statistics.checkpoints_saved += 1

        # Finalize statistics
        self.statistics.finalize()
        self._log_final_stats()

        return results

    def save_checkpoint(
        self,
        results: List[ResolutionResult],  # noqa: UP006
        path: Path,
    ) -> None:
        """
        Save processing checkpoint to disk.

        Args:
            results: Resolution results to save
            path: Path to checkpoint file
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            checkpoint_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'count': len(results),
                'results': [result.model_dump() for result in results],
                'statistics': self.statistics.to_dict(),
            }

            with open(path, 'w') as f:
                json.dump(checkpoint_data, f, indent=2)

            logger.debug(f'Checkpoint saved to {path}')

        except Exception as e:
            logger.error(f'Failed to save checkpoint: {e}')

    def load_checkpoint(self, path: Path) -> Optional[List[ResolutionResult]]:  # noqa: UP006, UP007
        """
        Load processing checkpoint from disk.

        Args:
            path: Path to checkpoint file

        Returns:
            List of resolution results, or None if load fails
        """
        try:
            with open(path, 'r') as f:  # noqa: UP015
                checkpoint_data = json.load(f)

            results = [
                ResolutionResult(**result_data)
                for result_data in checkpoint_data['results']
            ]

            logger.info(f'Loaded checkpoint from {path}: {len(results)} results')
            return results

        except Exception as e:
            logger.warning(f'Failed to load checkpoint from {path}: {e}')
            return None

    def _log_progress_stats(self):
        """Log progress statistics during processing."""
        stats = self.statistics
        logger.info(
            f'Progress: {stats.processed_citations}/{stats.total_citations} '
            f'({stats.processed_citations / stats.total_citations * 100:.1f}%) - '
            f'Success: {stats.successful_resolutions}, '
            f'Failed: {stats.failed_resolutions}, '
            f'Cache hits: {stats.cache_hits}'
        )

    def _log_final_stats(self):
        """Log final statistics after processing completion."""
        stats = self.statistics
        stats_dict = stats.to_dict()

        logger.info('=' * 60)
        logger.info('Batch Processing Complete - Final Statistics')
        logger.info('=' * 60)
        logger.info(f'Total citations: {stats.total_citations}')
        logger.info(f'Processed: {stats.processed_citations}')
        logger.info(
            f'Successful: {stats.successful_resolutions} '
            f'({stats_dict["success_rate"]:.1f}%)'
        )
        logger.info(f'Partial: {stats.partial_resolutions}')
        logger.info(f'Failed: {stats.failed_resolutions}')
        logger.info(f'Cache hits: {stats.cache_hits}')
        logger.info(f'Processing time: {stats.processing_time_seconds:.2f}s')
        logger.info(f'Average per citation: {stats.average_time_per_citation:.3f}s')
        logger.info(f'Checkpoints saved: {stats.checkpoints_saved}')

        if stats.api_calls:
            logger.info('API calls by source:')
            for api, count in stats.api_calls.items():
                logger.info(f'  {api}: {count}')

        if stats.errors_by_type:
            logger.info('Top errors:')
            for error, count in sorted(
                stats.errors_by_type.items(), key=lambda x: x[1], reverse=True
            )[:5]:
                logger.info(f'  {error}: {count}')

        logger.info('=' * 60)

    def get_statistics(self) -> BatchStatistics:
        """Get current processing statistics."""
        return self.statistics

    def clear_cache(self):
        """Clear the resolution cache."""
        self._cache.clear()
        logger.info('Resolution cache cleared')

    def get_cache_size(self) -> int:
        """Get current cache size."""
        return len(self._cache)
