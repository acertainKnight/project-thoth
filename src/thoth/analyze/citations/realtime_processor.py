"""
Realtime Citation Resolution Processor

This module provides on-demand citation resolution with intelligent caching and
timeout handling for responsive user interactions.

Key Features:
    - Fast resolution with configurable timeout (default 10-15s)
    - LRU cache for resolved DOIs by normalized citation key
    - Negative result caching (1 hour TTL) to avoid hammering APIs
    - PENDING status for timeouts (marked for batch retry later)
    - Comprehensive statistics tracking and logging

Usage:
    processor = RealtimeCitationProcessor()
    result = await processor.resolve_citation(citation)

    # Check cache performance
    stats = processor.get_cache_stats()
    print(f"Cache hit rate: {stats['hit_rate']:.2%}")
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field  # noqa: F401
from datetime import datetime, timedelta  # noqa: F401
from typing import Any, Dict, Optional  # noqa: UP035

from cachetools import LRUCache, TTLCache
from loguru import logger

from thoth.analyze.citations.resolution_chain import CitationResolutionChain
from thoth.analyze.citations.resolution_types import (
    APISource,  # noqa: F401
    CitationResolutionStatus,
    ConfidenceLevel,
    ResolutionMetadata,
    ResolutionResult,
)
from thoth.utilities.schemas.citations import Citation


@dataclass
class RealTimeConfig:
    """
    Configuration for real-time citation resolution.

    Attributes:
        timeout_seconds: Maximum time to spend on resolution (default 15s)
        cache_size: Maximum number of entries in positive result cache
        negative_cache_ttl_hours: Time-to-live for negative cache entries
        enable_negative_cache: Whether to cache failed resolution attempts
    """

    timeout_seconds: int = 15
    cache_size: int = 1000
    negative_cache_ttl_hours: int = 1
    enable_negative_cache: bool = True


@dataclass
class CacheStatistics:
    """
    Statistics for cache performance tracking.

    Attributes:
        total_requests: Total number of resolution requests
        positive_cache_hits: Number of hits in positive result cache
        negative_cache_hits: Number of hits in negative result cache
        cache_misses: Number of cache misses requiring API calls
        timeouts: Number of resolution attempts that timed out
        errors: Number of resolution attempts that errored
        total_resolution_time_ms: Cumulative resolution time in milliseconds
    """

    total_requests: int = 0
    positive_cache_hits: int = 0
    negative_cache_hits: int = 0
    cache_misses: int = 0
    timeouts: int = 0
    errors: int = 0
    total_resolution_time_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate overall cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        hits = self.positive_cache_hits + self.negative_cache_hits
        return hits / self.total_requests

    @property
    def positive_hit_rate(self) -> float:
        """Calculate positive cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.positive_cache_hits / self.total_requests

    @property
    def negative_hit_rate(self) -> float:
        """Calculate negative cache hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.negative_cache_hits / self.total_requests

    @property
    def average_resolution_time_ms(self) -> float:
        """Calculate average resolution time."""
        resolved = self.cache_misses
        if resolved == 0:
            return 0.0
        return self.total_resolution_time_ms / resolved


class RealtimeCitationProcessor:
    """
    Real-time citation processor with caching and timeout handling.

    Provides fast, on-demand citation resolution optimized for interactive use cases.
    Uses intelligent caching strategies to minimize API calls and improve response times.

    Attributes:
        config: Configuration parameters for resolution and caching
        resolution_chain: Chain of API resolvers for citation lookup
        positive_cache: LRU cache for successfully resolved citations
        negative_cache: TTL cache for failed resolution attempts
        statistics: Performance and usage statistics
    """  # noqa: W505

    def __init__(
        self,
        config: Optional[RealTimeConfig] = None,  # noqa: UP007
        resolution_chain: Optional[CitationResolutionChain] = None,  # noqa: UP007
    ):
        """
        Initialize real-time citation processor.

        Args:
            config: Configuration parameters (uses defaults if None)
            resolution_chain: Resolution chain instance (creates new if None)
        """
        self.config = config or RealTimeConfig()
        self.resolution_chain = resolution_chain or CitationResolutionChain()

        # Initialize positive result cache (LRU)
        self.positive_cache: LRUCache = LRUCache(maxsize=self.config.cache_size)

        # Initialize negative result cache (TTL) - expires after N hours
        negative_cache_ttl_seconds = self.config.negative_cache_ttl_hours * 3600
        self.negative_cache: TTLCache = TTLCache(
            maxsize=self.config.cache_size, ttl=negative_cache_ttl_seconds
        )

        # Initialize statistics
        self.statistics = CacheStatistics()

        # Lock for thread-safe cache access
        self._cache_lock = asyncio.Lock()

        logger.info(
            f'RealtimeCitationProcessor initialized with timeout={self.config.timeout_seconds}s, '
            f'cache_size={self.config.cache_size}, '
            f'negative_cache_ttl={self.config.negative_cache_ttl_hours}h'
        )

    def _normalize_citation_key(self, citation: Citation) -> str:
        """
        Generate normalized cache key from citation.

        Creates a consistent key from title, year, and first author for cache lookups.
        Uses MD5 hash to keep keys manageable.

        Args:
            citation: Citation to generate key for

        Returns:
            Normalized cache key (MD5 hash)
        """
        # Extract components for key
        title = (citation.title or '').lower().strip()
        year = str(citation.year or '')
        author = ''
        if citation.authors and len(citation.authors) > 0:
            author = citation.authors[0].lower().strip()

        # Create stable key from normalized components
        key_components = f'{title}|{year}|{author}'

        # Use MD5 hash for consistent, manageable key length
        key_hash = hashlib.md5(key_components.encode('utf-8')).hexdigest()

        return key_hash

    async def _check_positive_cache(self, cache_key: str) -> Optional[ResolutionResult]:  # noqa: UP007
        """
        Check positive result cache.

        Args:
            cache_key: Normalized cache key

        Returns:
            Cached ResolutionResult if found, None otherwise
        """
        async with self._cache_lock:
            result = self.positive_cache.get(cache_key)
            if result:
                logger.debug(f'Positive cache HIT for key: {cache_key[:16]}...')
                self.statistics.positive_cache_hits += 1
                return result
            return None

    async def _check_negative_cache(self, cache_key: str) -> bool:
        """
        Check negative result cache.

        Args:
            cache_key: Normalized cache key

        Returns:
            True if key is in negative cache (known to fail), False otherwise
        """
        if not self.config.enable_negative_cache:
            return False

        async with self._cache_lock:
            is_negative = cache_key in self.negative_cache
            if is_negative:
                logger.debug(f'Negative cache HIT for key: {cache_key[:16]}...')
                self.statistics.negative_cache_hits += 1
                return True
            return False

    async def _store_positive_cache(
        self, cache_key: str, result: ResolutionResult
    ) -> None:
        """
        Store result in positive cache.

        Args:
            cache_key: Normalized cache key
            result: Resolution result to cache
        """
        async with self._cache_lock:
            self.positive_cache[cache_key] = result
            logger.debug(
                f'Stored in positive cache: {cache_key[:16]}... '
                f'(status={result.status}, confidence={result.confidence_score:.2f})'
            )

    async def _store_negative_cache(self, cache_key: str) -> None:
        """
        Store key in negative cache to avoid repeated failed lookups.

        Args:
            cache_key: Normalized cache key for failed resolution
        """
        if not self.config.enable_negative_cache:
            return

        async with self._cache_lock:
            self.negative_cache[cache_key] = datetime.utcnow()
            logger.debug(
                f'Stored in negative cache: {cache_key[:16]}... '
                f'(TTL={self.config.negative_cache_ttl_hours}h)'
            )

    async def resolve_citation(self, citation: Citation) -> ResolutionResult:
        """
        Resolve citation with caching and timeout handling.

        Resolution flow:
        1. Check positive cache for previous successful resolution
        2. Check negative cache to avoid repeated failures
        3. Attempt resolution with timeout
        4. Update appropriate cache based on result
        5. Return result with PENDING status if timeout occurs

        Args:
            citation: Citation to resolve

        Returns:
            ResolutionResult with resolution outcome and metadata
        """
        start_time = time.perf_counter()
        self.statistics.total_requests += 1

        # Generate cache key
        cache_key = self._normalize_citation_key(citation)

        logger.info(
            f"Resolving citation: '{citation.title or citation.text[:50]}...' "
            f'(cache_key: {cache_key[:16]}...)'
        )

        # Step 1: Check positive cache
        cached_result = await self._check_positive_cache(cache_key)
        if cached_result:
            return cached_result

        # Step 2: Check negative cache
        is_negative = await self._check_negative_cache(cache_key)
        if is_negative:
            # Return UNRESOLVED result from negative cache
            return ResolutionResult(
                citation=citation.text or str(citation),
                status=CitationResolutionStatus.UNRESOLVED,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                source=None,
                matched_data=None,
                metadata=ResolutionMetadata(
                    attempt_count=0,
                    last_attempt_time=datetime.utcnow(),
                    error_message='Previously failed resolution (negative cache)',
                    additional_info={'negative_cache_hit': True},
                ),
            )

        # Step 3: Attempt resolution with timeout
        self.statistics.cache_misses += 1

        try:
            logger.debug(
                f'Cache MISS - attempting resolution with {self.config.timeout_seconds}s timeout'
            )

            # Wrap resolution in timeout
            result = await asyncio.wait_for(
                self.resolution_chain.resolve(citation),
                timeout=self.config.timeout_seconds,
            )

            # Track resolution time
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.statistics.total_resolution_time_ms += elapsed_ms

            # Update result metadata with timing
            if result.metadata:
                result.metadata.processing_time_ms = elapsed_ms

            logger.info(
                f'Resolution completed: status={result.status}, '
                f'confidence={result.confidence_score:.2f}, '
                f'source={result.source}, '
                f'time={elapsed_ms:.1f}ms'
            )

            # Step 4: Cache the result
            if result.status == CitationResolutionStatus.RESOLVED:
                await self._store_positive_cache(cache_key, result)
            elif result.status == CitationResolutionStatus.UNRESOLVED:
                await self._store_negative_cache(cache_key)

            return result

        except asyncio.TimeoutError:  # noqa: UP041
            # Handle timeout - return PENDING for batch retry
            self.statistics.timeouts += 1
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.warning(
                f'Resolution TIMEOUT after {self.config.timeout_seconds}s '
                f'(actual: {elapsed_ms:.1f}ms) - marking as PENDING for batch retry'
            )

            result = ResolutionResult(
                citation=citation.text or str(citation),
                status=CitationResolutionStatus.PENDING,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                source=None,
                matched_data=None,
                metadata=ResolutionMetadata(
                    attempt_count=1,
                    last_attempt_time=datetime.utcnow(),
                    error_message=f'Timeout after {self.config.timeout_seconds}s',
                    processing_time_ms=elapsed_ms,
                    additional_info={'timeout': True, 'batch_retry_recommended': True},
                ),
            )

            return result

        except Exception as e:
            # Handle unexpected errors
            self.statistics.errors += 1
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            logger.error(
                f'Resolution ERROR: {type(e).__name__}: {str(e)} '  # noqa: RUF010
                f'(time={elapsed_ms:.1f}ms)',
                exc_info=True,
            )

            result = ResolutionResult(
                citation=citation.text or str(citation),
                status=CitationResolutionStatus.FAILED,
                confidence_score=0.0,
                confidence_level=ConfidenceLevel.LOW,
                source=None,
                matched_data=None,
                metadata=ResolutionMetadata(
                    attempt_count=1,
                    last_attempt_time=datetime.utcnow(),
                    error_message=f'{type(e).__name__}: {str(e)}',  # noqa: RUF010
                    processing_time_ms=elapsed_ms,
                    additional_info={'error_type': type(e).__name__},
                ),
            )

            # Cache error to avoid repeated failures
            await self._store_negative_cache(cache_key)

            return result

    def get_cache_stats(self) -> Dict[str, Any]:  # noqa: UP006
        """
        Get comprehensive cache and performance statistics.

        Returns:
            Dictionary containing:
                - Cache size information (current/max)
                - Hit rates (overall, positive, negative)
                - Performance metrics (timeouts, errors, avg time)
                - Request counts and breakdown
        """
        stats = {
            # Cache size
            'positive_cache_size': len(self.positive_cache),
            'positive_cache_maxsize': self.positive_cache.maxsize,
            'negative_cache_size': len(self.negative_cache),
            'negative_cache_maxsize': self.negative_cache.maxsize,
            # Hit rates
            'total_requests': self.statistics.total_requests,
            'cache_hit_rate': self.statistics.hit_rate,
            'positive_hit_rate': self.statistics.positive_hit_rate,
            'negative_hit_rate': self.statistics.negative_hit_rate,
            # Request breakdown
            'positive_cache_hits': self.statistics.positive_cache_hits,
            'negative_cache_hits': self.statistics.negative_cache_hits,
            'cache_misses': self.statistics.cache_misses,
            'timeouts': self.statistics.timeouts,
            'errors': self.statistics.errors,
            # Performance
            'average_resolution_time_ms': self.statistics.average_resolution_time_ms,
            'total_resolution_time_ms': self.statistics.total_resolution_time_ms,
            # Configuration
            'timeout_seconds': self.config.timeout_seconds,
            'negative_cache_ttl_hours': self.config.negative_cache_ttl_hours,
            'negative_cache_enabled': self.config.enable_negative_cache,
        }

        return stats

    async def clear_cache(self) -> Dict[str, int]:  # noqa: UP006
        """
        Clear all caches (positive and negative).

        Returns:
            Dictionary with counts of cleared entries:
                - positive_cleared: Number of entries cleared from positive cache
                - negative_cleared: Number of entries cleared from negative cache
        """
        async with self._cache_lock:
            positive_count = len(self.positive_cache)
            negative_count = len(self.negative_cache)

            self.positive_cache.clear()
            self.negative_cache.clear()

            logger.info(
                f'Caches cleared: positive={positive_count}, negative={negative_count}'
            )

            return {
                'positive_cleared': positive_count,
                'negative_cleared': negative_count,
            }

    async def clear_negative_cache(self) -> int:
        """
        Clear only the negative result cache.

        Useful for retrying previously failed citations without clearing successful results.

        Returns:
            Number of entries cleared from negative cache
        """  # noqa: W505
        async with self._cache_lock:
            count = len(self.negative_cache)
            self.negative_cache.clear()

            logger.info(f'Negative cache cleared: {count} entries removed')

            return count

    def get_cache_contents(self) -> Dict[str, Any]:  # noqa: UP006
        """
        Get detailed cache contents for debugging and inspection.

        Returns:
            Dictionary containing:
                - positive_entries: List of cached successful resolutions
                - negative_entries: List of cached failed resolutions
                - total_size: Combined cache size
        """
        positive_entries = []
        for key, result in self.positive_cache.items():
            positive_entries.append(
                {
                    'cache_key': key,
                    'status': result.status,
                    'confidence_score': result.confidence_score,
                    'source': result.source,
                    'resolved_at': result.resolved_at.isoformat()
                    if result.resolved_at
                    else None,
                    'citation_preview': result.citation[:100]
                    if result.citation
                    else None,
                }
            )

        negative_entries = []
        for key, timestamp in self.negative_cache.items():
            negative_entries.append(
                {
                    'cache_key': key,
                    'cached_at': timestamp.isoformat()
                    if isinstance(timestamp, datetime)
                    else str(timestamp),
                }
            )

        return {
            'positive_entries': positive_entries,
            'negative_entries': negative_entries,
            'total_size': len(positive_entries) + len(negative_entries),
        }

    async def warm_cache(self, citations: list[Citation]) -> Dict[str, int]:  # noqa: UP006
        """
        Pre-populate cache with a batch of citations.

        Useful for warming up the cache before interactive sessions.

        Args:
            citations: List of citations to pre-resolve

        Returns:
            Dictionary with warming statistics:
                - total: Total citations processed
                - resolved: Successfully resolved and cached
                - failed: Failed resolutions (added to negative cache)
                - errors: Errors during resolution
        """
        stats = {'total': len(citations), 'resolved': 0, 'failed': 0, 'errors': 0}

        logger.info(f'Cache warming started for {len(citations)} citations')

        for citation in citations:
            try:
                result = await self.resolve_citation(citation)

                if result.status == CitationResolutionStatus.RESOLVED:
                    stats['resolved'] += 1
                elif result.status in (
                    CitationResolutionStatus.UNRESOLVED,
                    CitationResolutionStatus.PENDING,
                ):
                    stats['failed'] += 1
                else:
                    stats['errors'] += 1

            except Exception as e:
                logger.error(f'Error warming cache for citation: {e}')
                stats['errors'] += 1

        logger.info(
            f'Cache warming completed: '
            f'resolved={stats["resolved"]}, '
            f'failed={stats["failed"]}, '
            f'errors={stats["errors"]}'
        )

        return stats
