"""
Tests for IntelligentCache class.

This module tests the core caching functionality including:
- Basic get/put operations
- TTL expiration
- Hit/miss counting
- Metrics calculation
- Access pattern tracking
- Cache invalidation
"""

import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from tests.fixtures.performance_fixtures import (
    MockTimeProvider,
    assert_cache_entry_evicted,
    assert_cache_size,
    generate_cache_load,
    simulate_access_pattern,
)
from thoth.monitoring.performance_monitor import (
    CacheEntry,
    CacheStrategy,
    IntelligentCache,
)


class TestIntelligentCacheBasics:
    """Test basic cache operations."""

    def test_cache_initialization(self, lru_cache):
        """Test cache initializes with correct parameters."""
        assert lru_cache.name == 'test_lru'
        assert lru_cache.max_size == 10
        assert lru_cache.strategy == CacheStrategy.LRU
        assert len(lru_cache._cache) == 0

    def test_put_and_get(self, lru_cache):
        """Test basic put and get operations."""
        lru_cache.put('key1', 'value1')
        result = lru_cache.get('key1')

        assert result == 'value1'
        assert len(lru_cache._cache) == 1

    def test_get_nonexistent_key(self, lru_cache):
        """Test getting non-existent key returns None."""
        result = lru_cache.get('nonexistent')
        assert result is None

    def test_put_overwrites_existing(self, lru_cache):
        """Test putting same key overwrites value."""
        lru_cache.put('key1', 'value1')
        lru_cache.put('key1', 'value2')

        result = lru_cache.get('key1')
        assert result == 'value2'
        assert len(lru_cache._cache) == 1

    def test_multiple_entries(self, lru_cache):
        """Test cache handles multiple entries."""
        for i in range(5):
            lru_cache.put(f'key{i}', f'value{i}')

        assert len(lru_cache._cache) == 5

        for i in range(5):
            assert lru_cache.get(f'key{i}') == f'value{i}'

    def test_invalidate_removes_entry(self, lru_cache):
        """Test invalidate removes specific entry."""
        lru_cache.put('key1', 'value1')
        lru_cache.put('key2', 'value2')

        result = lru_cache.invalidate('key1')
        assert result is True
        assert lru_cache.get('key1') is None
        assert lru_cache.get('key2') == 'value2'

    def test_invalidate_nonexistent_returns_false(self, lru_cache):
        """Test invalidating non-existent key returns False."""
        result = lru_cache.invalidate('nonexistent')
        assert result is False

    def test_clear_removes_all_entries(self, lru_cache):
        """Test clear removes all cache entries."""
        for i in range(5):
            lru_cache.put(f'key{i}', f'value{i}')

        lru_cache.clear()

        assert len(lru_cache._cache) == 0
        assert lru_cache._hit_count == 0
        assert lru_cache._miss_count == 0

    def test_cache_respects_max_size(self, lru_cache):
        """Test cache never exceeds max size."""
        # lru_cache has max_size=10
        for i in range(15):
            lru_cache.put(f'key{i}', f'value{i}')

        assert len(lru_cache._cache) == 10


class TestCacheTTL:
    """Test TTL (Time To Live) functionality."""

    def test_ttl_expiration(self, ttl_cache):
        """Test entries expire after TTL."""
        with patch('thoth.monitoring.performance_monitor.datetime') as mock_dt:
            # Set initial time
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.now.return_value = initial_time

            # Put entry with 60 second TTL
            ttl_cache.put('key1', 'value1', ttl=60.0)

            # Should be available immediately
            assert ttl_cache.get('key1') == 'value1'

            # Advance time past TTL
            mock_dt.now.return_value = initial_time + timedelta(seconds=61)

            # Should be expired
            result = ttl_cache.get('key1')
            assert result is None

    def test_ttl_not_expired(self, ttl_cache):
        """Test entries are available before TTL expires."""
        with patch('thoth.monitoring.performance_monitor.datetime') as mock_dt:
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.now.return_value = initial_time

            ttl_cache.put('key1', 'value1', ttl=60.0)

            # Advance time but stay within TTL
            mock_dt.now.return_value = initial_time + timedelta(seconds=30)

            result = ttl_cache.get('key1')
            assert result == 'value1'

    def test_default_ttl(self, ttl_cache):
        """Test cache uses default TTL when not specified."""
        with patch('thoth.monitoring.performance_monitor.datetime') as mock_dt:
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.now.return_value = initial_time

            # ttl_cache has default_ttl=60.0
            ttl_cache.put('key1', 'value1')

            # Advance past default TTL
            mock_dt.now.return_value = initial_time + timedelta(seconds=61)

            result = ttl_cache.get('key1')
            assert result is None

    def test_custom_ttl_overrides_default(self, ttl_cache):
        """Test custom TTL overrides default TTL."""
        with patch('thoth.monitoring.performance_monitor.datetime') as mock_dt:
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.now.return_value = initial_time

            # Custom TTL of 120 seconds
            ttl_cache.put('key1', 'value1', ttl=120.0)

            # Advance past default TTL (60s) but within custom TTL
            mock_dt.now.return_value = initial_time + timedelta(seconds=90)

            result = ttl_cache.get('key1')
            assert result == 'value1'

    def test_no_ttl(self):
        """Test entries with no TTL never expire."""
        cache = IntelligentCache(
            name='no_ttl_cache',
            max_size=10,
            strategy=CacheStrategy.LRU,
            default_ttl=None,
        )

        with patch('thoth.monitoring.performance_monitor.datetime') as mock_dt:
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.now.return_value = initial_time

            cache.put('key1', 'value1')

            # Advance time significantly
            mock_dt.now.return_value = initial_time + timedelta(days=365)

            result = cache.get('key1')
            assert result == 'value1'


class TestCacheMetrics:
    """Test cache metrics calculation."""

    def test_hit_count_tracking(self, lru_cache):
        """Test cache hit count is tracked correctly."""
        lru_cache.put('key1', 'value1')

        # Generate hits
        for _ in range(5):
            lru_cache.get('key1')

        metrics = lru_cache.get_metrics()
        assert metrics.hit_count == 5

    def test_miss_count_tracking(self, lru_cache):
        """Test cache miss count is tracked correctly."""
        # Generate misses
        for _ in range(3):
            lru_cache.get('nonexistent')

        metrics = lru_cache.get_metrics()
        assert metrics.miss_count == 3

    def test_hit_ratio_calculation(self, lru_cache):
        """Test hit ratio is calculated correctly."""
        lru_cache.put('key1', 'value1')

        # 7 hits, 3 misses = 70% hit ratio
        for _ in range(7):
            lru_cache.get('key1')

        for _ in range(3):
            lru_cache.get('nonexistent')

        metrics = lru_cache.get_metrics()
        assert metrics.hit_count == 7
        assert metrics.miss_count == 3
        assert metrics.hit_ratio == 0.7

    def test_hit_ratio_zero_requests(self, lru_cache):
        """Test hit ratio is 0.0 when no requests made."""
        metrics = lru_cache.get_metrics()
        assert metrics.hit_ratio == 0.0

    def test_entry_count(self, lru_cache):
        """Test entry count is accurate."""
        for i in range(5):
            lru_cache.put(f'key{i}', f'value{i}')

        metrics = lru_cache.get_metrics()
        assert metrics.entry_count == 5

    def test_eviction_count(self, lru_cache):
        """Test eviction count is tracked."""
        # Fill cache beyond capacity (max_size=10)
        for i in range(15):
            lru_cache.put(f'key{i}', f'value{i}')

        metrics = lru_cache.get_metrics()
        assert metrics.eviction_count == 5  # 15 puts - 10 max = 5 evictions

    def test_memory_usage_calculation(self, lru_cache):
        """Test memory usage is estimated."""
        # Add entries of known size
        lru_cache.put('key1', 'x' * 1000)  # ~1KB
        lru_cache.put('key2', 'y' * 2000)  # ~2KB

        metrics = lru_cache.get_metrics()
        assert metrics.memory_usage_mb > 0
        # Should be roughly 3KB = 0.003MB
        assert 0.001 < metrics.memory_usage_mb < 0.01

    def test_cache_name_in_metrics(self, lru_cache):
        """Test cache name is included in metrics."""
        metrics = lru_cache.get_metrics()
        assert metrics.cache_name == 'test_lru'

    def test_total_and_used_size(self, lru_cache):
        """Test total and used size are reported correctly."""
        for i in range(3):
            lru_cache.put(f'key{i}', f'value{i}')

        metrics = lru_cache.get_metrics()
        assert metrics.total_size == 10  # max_size
        assert metrics.used_size == 3


class TestAccessPatternTracking:
    """Test access pattern tracking for adaptive strategy."""

    def test_access_pattern_recorded(self, adaptive_cache):
        """Test access patterns are recorded."""
        adaptive_cache.put('key1', 'value1')

        # Access multiple times
        for _ in range(3):
            adaptive_cache.get('key1')

        # Check access pattern was recorded
        assert 'key1' in adaptive_cache._access_patterns
        assert len(adaptive_cache._access_patterns['key1']) > 0

    def test_frequency_score_updated(self, adaptive_cache):
        """Test frequency scores are updated."""
        adaptive_cache.put('key1', 'value1')
        adaptive_cache.put('key2', 'value2')

        # Access key1 more frequently
        for _ in range(5):
            adaptive_cache.get('key1')

        for _ in range(2):
            adaptive_cache.get('key2')

        # Check frequency scores
        assert adaptive_cache._frequency_scores['key1'] > adaptive_cache._frequency_scores['key2']

    def test_old_access_patterns_pruned(self, adaptive_cache):
        """Test old access patterns are pruned after 1 hour."""
        with patch('thoth.monitoring.performance_monitor.datetime') as mock_dt:
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.now.return_value = initial_time

            adaptive_cache.put('key1', 'value1')
            adaptive_cache.get('key1')

            initial_patterns = len(adaptive_cache._access_patterns['key1'])
            assert initial_patterns > 0

            # Advance time past 1 hour
            mock_dt.now.return_value = initial_time + timedelta(hours=2)

            # Trigger pattern tracking
            adaptive_cache.get('key1')

            # Old patterns should be pruned
            # Only the new access should remain
            assert len(adaptive_cache._access_patterns['key1']) == 1

    def test_access_metadata_updated_on_get(self, lru_cache):
        """Test access metadata is updated on get."""
        with patch('thoth.monitoring.performance_monitor.datetime') as mock_dt:
            initial_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_dt.now.return_value = initial_time

            lru_cache.put('key1', 'value1')

            entry_before = lru_cache._cache['key1']
            initial_count = entry_before.access_count

            # Access the entry
            mock_dt.now.return_value = initial_time + timedelta(seconds=10)
            lru_cache.get('key1')

            entry_after = lru_cache._cache['key1']
            assert entry_after.access_count == initial_count + 1
            assert entry_after.last_accessed > entry_before.last_accessed


class TestMemoryEstimation:
    """Test memory size estimation for different data types."""

    def test_string_size_estimation(self, lru_cache):
        """Test string size is estimated correctly."""
        small_string = 'hello'
        large_string = 'x' * 10000

        lru_cache.put('small', small_string)
        lru_cache.put('large', large_string)

        small_entry = lru_cache._cache['small']
        large_entry = lru_cache._cache['large']

        assert small_entry.size_bytes < large_entry.size_bytes
        assert large_entry.size_bytes >= 10000

    def test_dict_size_estimation(self, lru_cache):
        """Test dictionary size is estimated."""
        small_dict = {'a': 1}
        large_dict = {f'key_{i}': i for i in range(1000)}

        lru_cache.put('small', small_dict)
        lru_cache.put('large', large_dict)

        small_entry = lru_cache._cache['small']
        large_entry = lru_cache._cache['large']

        assert small_entry.size_bytes < large_entry.size_bytes

    def test_number_size_estimation(self, lru_cache):
        """Test number size is estimated."""
        lru_cache.put('int', 42)
        lru_cache.put('float', 3.14159)

        int_entry = lru_cache._cache['int']
        float_entry = lru_cache._cache['float']

        assert int_entry.size_bytes == 8
        assert float_entry.size_bytes == 8

    def test_boolean_size_estimation(self, lru_cache):
        """Test boolean size is estimated."""
        lru_cache.put('bool', True)

        entry = lru_cache._cache['bool']
        assert entry.size_bytes == 1

    def test_complex_nested_size_estimation(self, lru_cache):
        """Test complex nested structures are estimated."""
        complex_data = {
            'level1': {
                'level2': {
                    'list': [1, 2, 3],
                    'string': 'nested',
                },
            },
        }

        lru_cache.put('complex', complex_data)
        entry = lru_cache._cache['complex']

        assert entry.size_bytes > 0


class TestCacheClearAndInvalidate:
    """Test cache clearing and invalidation operations."""

    def test_clear_resets_counters(self, lru_cache):
        """Test clear resets all counters."""
        # Add entries and generate hits/misses
        lru_cache.put('key1', 'value1')
        lru_cache.get('key1')  # Hit
        lru_cache.get('missing')  # Miss

        # Clear cache
        lru_cache.clear()

        # All counters should be reset
        assert len(lru_cache._cache) == 0
        assert lru_cache._hit_count == 0
        assert lru_cache._miss_count == 0
        assert lru_cache._eviction_count == 0

    def test_clear_resets_access_patterns(self, adaptive_cache):
        """Test clear resets access patterns."""
        adaptive_cache.put('key1', 'value1')
        adaptive_cache.get('key1')

        assert len(adaptive_cache._access_patterns) > 0
        assert len(adaptive_cache._frequency_scores) > 0

        adaptive_cache.clear()

        assert len(adaptive_cache._access_patterns) == 0
        assert len(adaptive_cache._frequency_scores) == 0

    def test_invalidate_preserves_other_entries(self, lru_cache):
        """Test invalidate only removes target entry."""
        for i in range(5):
            lru_cache.put(f'key{i}', f'value{i}')

        lru_cache.invalidate('key2')

        assert len(lru_cache._cache) == 4
        assert lru_cache.get('key2') is None

        for i in [0, 1, 3, 4]:
            assert lru_cache.get(f'key{i}') == f'value{i}'

    def test_multiple_invalidations(self, lru_cache):
        """Test multiple invalidations work correctly."""
        for i in range(5):
            lru_cache.put(f'key{i}', f'value{i}')

        lru_cache.invalidate('key1')
        lru_cache.invalidate('key3')

        assert len(lru_cache._cache) == 3
        assert lru_cache.get('key1') is None
        assert lru_cache.get('key3') is None


class TestCacheAccessTimes:
    """Test access time tracking."""

    def test_access_times_recorded(self, lru_cache):
        """Test access times are recorded on cache hits."""
        lru_cache.put('key1', 'value1')

        initial_len = len(lru_cache._access_times)

        with patch('thoth.monitoring.performance_monitor.time.time') as mock_time:
            mock_time.return_value = 1000.0
            lru_cache.get('key1')

        assert len(lru_cache._access_times) == initial_len + 1
        assert lru_cache._access_times[-1] == 1000.0

    def test_access_times_maxlen(self, lru_cache):
        """Test access times deque has maxlen."""
        lru_cache.put('key1', 'value1')

        # Generate many accesses
        for i in range(1500):
            with patch('thoth.monitoring.performance_monitor.time.time') as mock_time:
                mock_time.return_value = float(i)
                lru_cache.get('key1')

        # Should only keep last 1000
        assert len(lru_cache._access_times) == 1000

    def test_average_access_time_calculation(self, lru_cache):
        """Test average access time is calculated in metrics."""
        lru_cache.put('key1', 'value1')

        # Mock consistent access times
        with patch('thoth.monitoring.performance_monitor.time.time') as mock_time:
            mock_time.return_value = 100.0
            lru_cache.get('key1')

            mock_time.return_value = 200.0
            lru_cache.get('key1')

            mock_time.return_value = 300.0
            lru_cache.get('key1')

        metrics = lru_cache.get_metrics()
        # Average of 100, 200, 300 = 200
        assert metrics.average_access_time == 200.0
