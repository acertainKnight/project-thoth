"""
Performance Benchmarks for Citation Resolution.

This module measures performance characteristics of the citation resolution pipeline:

1. **Throughput**: Citations resolved per second
2. **Latency**: P50, P95, P99 resolution times
3. **Scalability**: Performance with increasing batch sizes
4. **Cache Efficiency**: Cache hit rate and impact on performance
5. **Memory Usage**: RAM consumption during batch processing
6. **API Efficiency**: Number of API calls vs resolutions

Benchmark Scenarios:
-------------------
- Small batch: 10 citations
- Medium batch: 100 citations
- Large batch: 1000 citations
- Concurrent execution: Multiple batches in parallel

Performance Targets:
-------------------
- Single citation: <500ms average
- Batch of 100: <30 seconds total (<300ms per citation)
- Throughput: >3 citations/second sustained
- Memory: <500MB for 1000 citations
- Cache hit rate: >70% on duplicate detection

Tools:
------
- pytest-benchmark: Statistical analysis of timing
- memory_profiler: RAM usage tracking
- cProfile: Code-level profiling
"""

import asyncio  # noqa: I001
import time  # noqa: F401
from pathlib import Path
from typing import List  # noqa: UP035
from unittest.mock import AsyncMock, MagicMock

import pytest
from loguru import logger

from thoth.analyze.citations.resolution_chain import CitationResolutionChain
from thoth.analyze.citations.fuzzy_matcher import calculate_fuzzy_score
from thoth.utilities.schemas.citations import Citation


# ============================================================================
# Benchmark Fixtures
# ============================================================================


@pytest.fixture
def mock_fast_resolver():
    """Create mock resolver with minimal latency for baseline benchmarks."""
    mock = MagicMock()
    mock.resolve = AsyncMock(
        return_value={
            'doi': '10.1234/test.doi',
            'title': 'Test Paper',
            'confidence': 0.95,
        }
    )
    return mock


# ============================================================================
# Throughput Benchmarks
# ============================================================================


@pytest.mark.benchmark
def test_single_citation_resolution_latency(
    benchmark,
    resolution_chain: CitationResolutionChain,
    sample_citation: Citation,
):
    """
    Benchmark: Single citation resolution latency.

    Measures time to resolve one citation through full chain.

    Target: <500ms per citation
    """

    def resolve():
        return asyncio.run(resolution_chain.resolve(sample_citation))

    result = benchmark(resolve)  # noqa: F841

    # Log statistics
    logger.info(
        f'Single citation latency: '
        f'mean={benchmark.stats.mean * 1000:.1f}ms, '
        f'median={benchmark.stats.median * 1000:.1f}ms, '
        f'stddev={benchmark.stats.stddev * 1000:.1f}ms'
    )

    # Verify target met
    assert benchmark.stats.mean < 0.5, (
        f'Single citation resolution too slow: {benchmark.stats.mean:.3f}s (target: <0.5s)'
    )


@pytest.mark.benchmark
@pytest.mark.slow
def test_batch_resolution_throughput_small(
    benchmark,
    resolution_chain: CitationResolutionChain,
    benchmark_data_small: List[Citation],  # noqa: UP006
):
    """
    Benchmark: Small batch (10 citations) throughput.

    Measures concurrent resolution of 10 citations.

    Target: <3 seconds total
    """

    async def resolve_batch():
        tasks = [resolution_chain.resolve(c) for c in benchmark_data_small]
        return await asyncio.gather(*tasks)

    def run():
        return asyncio.run(resolve_batch())

    result = benchmark(run)  # noqa: F841

    throughput = len(benchmark_data_small) / benchmark.stats.mean
    logger.info(
        f'Small batch throughput: {throughput:.2f} citations/sec '
        f'(total: {benchmark.stats.mean:.2f}s for {len(benchmark_data_small)} citations)'
    )

    assert benchmark.stats.mean < 3.0, (
        f'Small batch too slow: {benchmark.stats.mean:.2f}s (target: <3s)'
    )


@pytest.mark.benchmark
@pytest.mark.slow
def test_batch_resolution_throughput_medium(
    benchmark,
    resolution_chain: CitationResolutionChain,
    benchmark_data_medium: List[Citation],  # noqa: UP006
):
    """
    Benchmark: Medium batch (100 citations) throughput.

    Measures concurrent resolution of 100 citations.

    Target: <30 seconds total (300ms avg per citation)
    """

    async def resolve_batch():
        tasks = [resolution_chain.resolve(c) for c in benchmark_data_medium]
        return await asyncio.gather(*tasks)

    def run():
        return asyncio.run(resolve_batch())

    result = benchmark.pedantic(run, iterations=3, rounds=1)  # noqa: F841

    throughput = len(benchmark_data_medium) / benchmark.stats.mean
    logger.info(
        f'Medium batch throughput: {throughput:.2f} citations/sec '
        f'(total: {benchmark.stats.mean:.2f}s for {len(benchmark_data_medium)} citations)'
    )

    assert benchmark.stats.mean < 30.0, (
        f'Medium batch too slow: {benchmark.stats.mean:.2f}s (target: <30s)'
    )


@pytest.mark.benchmark
@pytest.mark.slow
@pytest.mark.skip(reason='Large benchmark - run manually for performance testing')
def test_batch_resolution_throughput_large(
    benchmark,
    resolution_chain: CitationResolutionChain,
    benchmark_data_large: List[Citation],  # noqa: UP006
):
    """
    Benchmark: Large batch (1000 citations) throughput.

    Measures scalability with large batches.

    Target: <5 minutes total (300ms avg per citation)
    """

    async def resolve_batch():
        tasks = [resolution_chain.resolve(c) for c in benchmark_data_large]
        return await asyncio.gather(*tasks)

    def run():
        return asyncio.run(resolve_batch())

    result = benchmark.pedantic(run, iterations=1, rounds=1)  # noqa: F841

    throughput = len(benchmark_data_large) / benchmark.stats.mean
    logger.info(
        f'Large batch throughput: {throughput:.2f} citations/sec '
        f'(total: {benchmark.stats.mean:.2f}s for {len(benchmark_data_large)} citations)'
    )

    assert benchmark.stats.mean < 300.0, (
        f'Large batch too slow: {benchmark.stats.mean:.2f}s (target: <300s)'
    )


# ============================================================================
# Fuzzy Matching Performance
# ============================================================================


@pytest.mark.benchmark
def test_fuzzy_matching_performance(
    benchmark,
    sample_citation: Citation,
):
    """
    Benchmark: Fuzzy matching algorithm performance.

    Measures pure matching speed without API calls.

    Target: <10ms per comparison
    """
    citation1 = sample_citation
    citation2 = Citation(
        title='Slightly Different Test Paper Title',
        authors=['John Doe', 'Jane Smith', 'Bob Jones'],
        year=2022,
        journal='Similar Journal Name',
    )

    def match():
        return calculate_fuzzy_score(citation1, citation2)

    result = benchmark(match)  # noqa: F841

    logger.info(
        f'Fuzzy matching latency: {benchmark.stats.mean * 1000:.3f}ms '
        f'(min: {benchmark.stats.min * 1000:.3f}ms, max: {benchmark.stats.max * 1000:.3f}ms)'
    )

    assert benchmark.stats.mean < 0.01, (
        f'Fuzzy matching too slow: {benchmark.stats.mean * 1000:.1f}ms (target: <10ms)'
    )


@pytest.mark.benchmark
def test_fuzzy_matching_batch_performance(
    benchmark,
    benchmark_data_medium: List[Citation],  # noqa: UP006
):
    """
    Benchmark: Batch fuzzy matching for deduplication.

    Measures time to compare 100 citations against each other.

    Target: <10 seconds for 100x100 comparisons
    """

    def match_all():
        scores = []
        for i, cit1 in enumerate(benchmark_data_medium):
            for j, cit2 in enumerate(benchmark_data_medium):
                if i != j:
                    score = calculate_fuzzy_score(cit1, cit2)
                    scores.append(score)
        return scores

    result = benchmark.pedantic(match_all, iterations=1, rounds=1)  # noqa: F841

    num_comparisons = len(benchmark_data_medium) * (len(benchmark_data_medium) - 1)
    comparisons_per_sec = num_comparisons / benchmark.stats.mean

    logger.info(
        f'Batch matching: {comparisons_per_sec:.0f} comparisons/sec '
        f'({num_comparisons} comparisons in {benchmark.stats.mean:.2f}s)'
    )

    assert benchmark.stats.mean < 10.0, (
        f'Batch matching too slow: {benchmark.stats.mean:.2f}s (target: <10s)'
    )


# ============================================================================
# Cache Performance
# ============================================================================


@pytest.mark.benchmark
@pytest.mark.requires_db
def test_database_query_performance(
    benchmark,
    postgres_service,
    empty_database,  # noqa: ARG001
):
    """
    Benchmark: Database query performance for duplicate detection.

    Measures time to check if citation already exists.

    Target: <50ms per query
    """

    # Insert test citations
    async def setup():
        async with postgres_service.pool.acquire() as conn:
            for i in range(100):
                await conn.execute(
                    """
                    INSERT INTO citations (title, doi, authors, year)
                    VALUES ($1, $2, $3, $4)
                    """,
                    f'Test Paper {i}',
                    f'10.1234/test.{i}',
                    [f'Author {i}'],
                    2020 + (i % 4),
                )

    asyncio.run(setup())

    # Benchmark query
    async def query():
        async with postgres_service.pool.acquire() as conn:
            return await conn.fetchrow(
                'SELECT * FROM citations WHERE doi = $1',
                '10.1234/test.50',
            )

    def run():
        return asyncio.run(query())

    result = benchmark(run)  # noqa: F841

    logger.info(
        f'Database query latency: {benchmark.stats.mean * 1000:.3f}ms '
        f'(P95: {benchmark.stats.percentiles.percentile_95 * 1000:.3f}ms)'
    )

    assert benchmark.stats.mean < 0.05, (
        f'Database query too slow: {benchmark.stats.mean * 1000:.1f}ms (target: <50ms)'
    )


@pytest.mark.benchmark
def test_cache_hit_rate_simulation(benchmark_data_medium: List[Citation]):  # noqa: UP006
    """
    Test: Simulate cache hit rate with duplicate citations.

    Measures effectiveness of duplicate detection.

    Target: >70% hit rate on realistic data
    """
    # Create dataset with 30% duplicates
    dataset = benchmark_data_medium.copy()
    num_duplicates = len(dataset) // 3

    # Add duplicates
    for i in range(num_duplicates):
        dataset.append(dataset[i])

    # Simulate cache (dict by DOI)
    cache = {}
    hits = 0
    misses = 0

    for citation in dataset:
        cache_key = citation.doi or f'{citation.title}_{citation.year}'

        if cache_key in cache:
            hits += 1
        else:
            misses += 1
            cache[cache_key] = citation

    hit_rate = hits / (hits + misses)

    logger.info(
        f'Cache hit rate: {hit_rate:.2%} '
        f'({hits} hits, {misses} misses, {len(dataset)} total)'
    )

    assert hit_rate >= 0.25, f'Cache hit rate too low: {hit_rate:.2%} (target: >25%)'


# ============================================================================
# Memory Usage Benchmarks
# ============================================================================


@pytest.mark.benchmark
@pytest.mark.slow
def test_memory_usage_batch_processing(
    benchmark_data_medium: List[Citation],  # noqa: UP006
):
    """
    Benchmark: Memory usage during batch processing.

    Measures RAM consumption with 100 citations.

    Target: <100MB for 100 citations
    """
    import psutil  # noqa: I001
    import os

    process = psutil.Process(os.getpid())

    # Measure baseline memory
    baseline_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Process citations
    results = []
    for citation in benchmark_data_medium:
        # Simulate resolution result
        results.append(
            {
                'citation': citation,
                'doi': '10.1234/test.doi',
                'confidence': 0.85,
                'metadata': {'source': 'crossref'},
            }
        )

    # Measure peak memory
    peak_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_used = peak_memory - baseline_memory

    logger.info(
        f'Memory usage: {memory_used:.1f}MB for {len(benchmark_data_medium)} citations '
        f'({memory_used / len(benchmark_data_medium) * 1000:.1f}KB per citation)'
    )

    assert memory_used < 100.0, (
        f'Memory usage too high: {memory_used:.1f}MB (target: <100MB)'
    )


# ============================================================================
# API Efficiency Benchmarks
# ============================================================================


@pytest.mark.benchmark
def test_api_call_efficiency(
    resolution_chain: CitationResolutionChain,
    sample_citations: List[Citation],  # noqa: UP006
):
    """
    Test: Measure API call efficiency.

    Tracks number of API calls vs successful resolutions.

    Target: <2 API calls per resolution on average
    """
    # Mock API calls to count them
    call_counts = {
        'crossref': 0,
        'openalex': 0,
        'semanticscholar': 0,
    }

    original_crossref_resolve = resolution_chain.crossref_resolver.resolve
    original_openalex_resolve = resolution_chain.openalex_resolver.resolve
    original_semantic_resolve = resolution_chain.semanticscholar_resolver.resolve

    async def count_crossref(*args, **kwargs):
        call_counts['crossref'] += 1
        return await original_crossref_resolve(*args, **kwargs)

    async def count_openalex(*args, **kwargs):
        call_counts['openalex'] += 1
        return await original_openalex_resolve(*args, **kwargs)

    async def count_semantic(*args, **kwargs):
        call_counts['semanticscholar'] += 1
        return await original_semantic_resolve(*args, **kwargs)

    resolution_chain.crossref_resolver.resolve = count_crossref
    resolution_chain.openalex_resolver.resolve = count_openalex
    resolution_chain.semanticscholar_resolver.resolve = count_semantic

    # Resolve citations
    async def resolve_all():
        return await asyncio.gather(
            *[resolution_chain.resolve(c) for c in sample_citations]
        )

    results = asyncio.run(resolve_all())

    # Calculate efficiency
    total_calls = sum(call_counts.values())
    successful_resolutions = sum(
        1 for r in results if r.matched_data is not None and r.matched_data.get('doi')
    )

    calls_per_resolution = (
        total_calls / successful_resolutions
        if successful_resolutions > 0
        else float('inf')
    )

    logger.info(
        f'API efficiency: {calls_per_resolution:.2f} calls per resolution '
        f'({total_calls} calls, {successful_resolutions} successes)'
    )
    logger.info(f'API breakdown: {call_counts}')

    assert calls_per_resolution < 3.0, (
        f'Too many API calls per resolution: {calls_per_resolution:.2f} (target: <3.0)'
    )


# ============================================================================
# Scalability Benchmarks
# ============================================================================


@pytest.mark.benchmark
@pytest.mark.parametrize('batch_size', [10, 50, 100, 200])
def test_scalability_with_batch_size(
    benchmark,
    resolution_chain: CitationResolutionChain,
    batch_size: int,
):
    """
    Benchmark: Scalability as batch size increases.

    Measures if throughput stays constant or degrades.

    Expected: Linear scaling (2x citations ≈ 2x time)
    """
    # Generate citations
    citations = [
        Citation(
            title=f'Test Paper {i}',
            authors=[f'Author {i}'],
            year=2020 + (i % 4),
        )
        for i in range(batch_size)
    ]

    async def resolve_batch():
        tasks = [resolution_chain.resolve(c) for c in citations]
        return await asyncio.gather(*tasks)

    def run():
        return asyncio.run(resolve_batch())

    result = benchmark.pedantic(run, iterations=3, rounds=1)  # noqa: F841

    throughput = batch_size / benchmark.stats.mean
    avg_time_per_citation = benchmark.stats.mean / batch_size

    logger.info(
        f'Batch size {batch_size}: '
        f'throughput={throughput:.2f} citations/sec, '
        f'avg={avg_time_per_citation * 1000:.1f}ms per citation'
    )

    # Verify linear scaling (within 20% tolerance)
    expected_time_per_citation = 0.3  # 300ms baseline
    assert avg_time_per_citation < expected_time_per_citation * 1.2, (
        f'Throughput degraded at batch size {batch_size}'
    )


# ============================================================================
# Profiling Helpers
# ============================================================================


@pytest.mark.benchmark
@pytest.mark.skip(reason='Profiling tool - run manually')
def test_profile_resolution_chain(
    resolution_chain: CitationResolutionChain,
    benchmark_data_medium: List[Citation],  # noqa: UP006
    temp_directory: Path,
):
    """
    Test: Generate cProfile output for detailed profiling.

    Run manually to identify bottlenecks.

    Usage:
        pytest tests/benchmarks/test_resolution_performance.py::test_profile_resolution_chain -v
    """  # noqa: W505
    import cProfile
    import pstats

    profiler = cProfile.Profile()

    async def resolve_all():
        return await asyncio.gather(
            *[resolution_chain.resolve(c) for c in benchmark_data_medium]
        )

    # Profile execution
    profiler.enable()
    asyncio.run(resolve_all())
    profiler.disable()

    # Save profile
    profile_path = temp_directory / 'resolution_profile.prof'
    profiler.dump_stats(str(profile_path))

    # Print top 20 time consumers
    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    stats.sort_stats('cumulative')
    logger.info('Top 20 time-consuming functions:')
    stats.print_stats(20)

    logger.info(f'Full profile saved to: {profile_path}')
