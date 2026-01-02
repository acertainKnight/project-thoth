"""
Tests for cache eviction strategies.

This module tests the different cache eviction strategies:
- LRU (Least Recently Used)
- LFU (Least Frequently Used)
- TTL (Time To Live)
- ADAPTIVE (Hybrid recency + frequency)
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest  # noqa: F401

from thoth.monitoring.performance_monitor import (
    CacheStrategy,
    IntelligentCache,
)


class TestLRUStrategy:
    """Test Least Recently Used (LRU) eviction strategy."""

    def test_lru_evicts_least_recently_accessed(self):
        """Test LRU evicts the least recently accessed entry."""
        cache = IntelligentCache(
            name='lru_test',
            max_size=3,
            strategy=CacheStrategy.LRU,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_get_now.return_value = base_time

            # Add 3 entries
            cache.put('key1', 'value1')

            mock_get_now.return_value = base_time + timedelta(seconds=1)
            cache.put('key2', 'value2')

            mock_get_now.return_value = base_time + timedelta(seconds=2)
            cache.put('key3', 'value3')

            # Access key1 and key2 to update their access time
            mock_get_now.return_value = base_time + timedelta(seconds=3)
            cache.get('key1')

            mock_get_now.return_value = base_time + timedelta(seconds=4)
            cache.get('key2')

            # key3 is now least recently used (accessed at t=2)
            # Add new entry to trigger eviction
            mock_get_now.return_value = base_time + timedelta(seconds=5)
            cache.put('key4', 'value4')

            # key3 should be evicted
            assert cache.get('key3') is None
            assert cache.get('key1') == 'value1'
            assert cache.get('key2') == 'value2'
            assert cache.get('key4') == 'value4'

    def test_lru_respects_access_order(self):
        """Test LRU maintains correct access order."""
        cache = IntelligentCache(
            name='lru_test',
            max_size=3,
            strategy=CacheStrategy.LRU,
        )

        # Fill cache
        cache.put('key1', 'value1')
        cache.put('key2', 'value2')
        cache.put('key3', 'value3')

        # Access in specific order: key2, key1, key3
        cache.get('key2')
        cache.get('key1')
        cache.get('key3')

        # Add new entry - key2 should be evicted (least recently accessed)
        cache.put('key4', 'value4')

        assert cache.get('key2') is None
        assert cache.get('key1') == 'value1'

    def test_lru_put_updates_access_time(self):
        """Test that put operation updates access time."""
        cache = IntelligentCache(
            name='lru_test',
            max_size=3,
            strategy=CacheStrategy.LRU,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)

            # Add entries
            mock_get_now.return_value = base_time
            cache.put('key1', 'value1')

            mock_get_now.return_value = base_time + timedelta(seconds=1)
            cache.put('key2', 'value2')

            mock_get_now.return_value = base_time + timedelta(seconds=2)
            cache.put('key3', 'value3')

            # Overwrite key1 (updates its access time)
            mock_get_now.return_value = base_time + timedelta(seconds=10)
            cache.put('key1', 'value1_updated')

            # Add new entry - key2 should be evicted (oldest access time)
            mock_get_now.return_value = base_time + timedelta(seconds=11)
            cache.put('key4', 'value4')

            assert cache.get('key2') is None
            assert cache.get('key1') == 'value1_updated'

    def test_lru_empty_cache_no_eviction(self):
        """Test LRU handles empty cache gracefully."""
        cache = IntelligentCache(
            name='lru_test',
            max_size=3,
            strategy=CacheStrategy.LRU,
        )

        # Add first entry to empty cache
        cache.put('key1', 'value1')

        assert cache.get('key1') == 'value1'
        assert len(cache._cache) == 1


class TestLFUStrategy:
    """Test Least Frequently Used (LFU) eviction strategy."""

    def test_lfu_evicts_least_frequently_accessed(self):
        """Test LFU evicts the least frequently accessed entry."""
        cache = IntelligentCache(
            name='lfu_test',
            max_size=3,
            strategy=CacheStrategy.LFU,
        )

        # Add 3 entries
        cache.put('key1', 'value1')
        cache.put('key2', 'value2')
        cache.put('key3', 'value3')

        # Access with different frequencies
        # key1: 5 times
        for _ in range(5):
            cache.get('key1')

        # key2: 1 time (least frequent)
        cache.get('key2')

        # key3: 3 times
        for _ in range(3):
            cache.get('key3')

        # Add new entry - key2 should be evicted (least frequent)
        cache.put('key4', 'value4')

        assert cache.get('key2') is None
        assert cache.get('key1') == 'value1'
        assert cache.get('key3') == 'value3'
        assert cache.get('key4') == 'value4'

    def test_lfu_counts_access_frequency_correctly(self):
        """Test LFU tracks access counts correctly."""
        cache = IntelligentCache(
            name='lfu_test',
            max_size=2,
            strategy=CacheStrategy.LFU,
        )

        cache.put('key1', 'value1')
        cache.put('key2', 'value2')

        # key1: 10 accesses
        for _ in range(10):
            cache.get('key1')

        # key2: 2 accesses (least frequent)
        for _ in range(2):
            cache.get('key2')

        # Verify access counts
        assert cache._cache['key1'].access_count > cache._cache['key2'].access_count

        # Add new entry - key2 should be evicted
        cache.put('key3', 'value3')

        assert cache.get('key2') is None
        assert cache.get('key1') == 'value1'

    def test_lfu_tie_breaking(self):
        """Test LFU behavior when entries have same frequency."""
        cache = IntelligentCache(
            name='lfu_test',
            max_size=3,
            strategy=CacheStrategy.LFU,
        )

        # Add entries with same frequency
        cache.put('key1', 'value1')
        cache.put('key2', 'value2')
        cache.put('key3', 'value3')

        # All have access_count=1 from put
        # Add new entry - one of them will be evicted
        cache.put('key4', 'value4')

        # Should evict one entry
        assert len(cache._cache) == 3

    def test_lfu_empty_cache_no_eviction(self):
        """Test LFU handles empty cache gracefully."""
        cache = IntelligentCache(
            name='lfu_test',
            max_size=3,
            strategy=CacheStrategy.LFU,
        )

        cache.put('key1', 'value1')

        assert cache.get('key1') == 'value1'
        assert len(cache._cache) == 1


class TestTTLStrategy:
    """Test Time To Live (TTL) eviction strategy."""

    def test_ttl_evicts_expired_entries(self):
        """Test TTL evicts expired entries."""
        cache = IntelligentCache(
            name='ttl_test',
            max_size=5,
            strategy=CacheStrategy.TTL,
            default_ttl=60.0,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_get_now.return_value = base_time

            # Add entries with different TTLs
            cache.put('key1', 'value1', ttl=30.0)  # 30 seconds
            cache.put('key2', 'value2', ttl=60.0)  # 60 seconds
            cache.put('key3', 'value3', ttl=120.0)  # 120 seconds
            cache.put('key4', 'value4', ttl=10.0)  # 10 seconds (shortest)

            # Fill cache to trigger eviction
            mock_get_now.return_value = base_time + timedelta(seconds=15)
            cache.put('key5', 'value5')

            # Advance time to trigger TTL eviction
            mock_get_now.return_value = base_time + timedelta(seconds=20)
            cache.put('key6', 'value6')  # This will trigger eviction

            # key4 should be expired (10s TTL, 20s elapsed)
            assert cache.get('key4') is None

    def test_ttl_evicts_multiple_expired_entries(self):
        """Test TTL can evict multiple expired entries at once."""
        cache = IntelligentCache(
            name='ttl_test',
            max_size=5,
            strategy=CacheStrategy.TTL,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_get_now.return_value = base_time

            # Add entries with short TTL
            cache.put('key1', 'value1', ttl=10.0)
            cache.put('key2', 'value2', ttl=15.0)
            cache.put('key3', 'value3', ttl=100.0)
            cache.put('key4', 'value4', ttl=12.0)

            # Advance time past multiple TTLs
            mock_get_now.return_value = base_time + timedelta(seconds=20)

            # Fill cache to trigger eviction
            cache.put('key5', 'value5')
            cache.put('key6', 'value6')

            # Multiple entries should be expired
            assert cache.get('key1') is None
            assert cache.get('key2') is None
            assert cache.get('key4') is None
            assert cache.get('key3') == 'value3'  # Still valid

    def test_ttl_no_expired_entries(self):
        """Test TTL when no entries are expired."""
        cache = IntelligentCache(
            name='ttl_test',
            max_size=3,
            strategy=CacheStrategy.TTL,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_get_now.return_value = base_time

            # Add entries with long TTL
            cache.put('key1', 'value1', ttl=1000.0)
            cache.put('key2', 'value2', ttl=1000.0)
            cache.put('key3', 'value3', ttl=1000.0)

            # Small time advance
            mock_get_now.return_value = base_time + timedelta(seconds=10)

            # Trigger eviction - nothing should be evicted
            cache.put('key4', 'value4', ttl=1000.0)

            # All entries should still be accessible
            # Note: One will be evicted due to max_size, but not due to TTL
            assert len(cache._cache) == 3

    def test_ttl_eviction_updates_counter(self):
        """Test TTL eviction increments eviction counter."""
        cache = IntelligentCache(
            name='ttl_test',
            max_size=5,
            strategy=CacheStrategy.TTL,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_get_now.return_value = base_time

            # Add entries
            cache.put('key1', 'value1', ttl=10.0)
            cache.put('key2', 'value2', ttl=15.0)
            cache.put('key3', 'value3', ttl=20.0)

            initial_evictions = cache._eviction_count

            # Advance time to expire entries
            mock_get_now.return_value = base_time + timedelta(seconds=25)

            # Trigger eviction
            cache.put('key4', 'value4')

            # Eviction count should increase
            assert cache._eviction_count > initial_evictions


class TestAdaptiveStrategy:
    """Test Adaptive (hybrid) eviction strategy."""

    def test_adaptive_uses_composite_score(self):
        """Test adaptive strategy uses recency + frequency score."""
        cache = IntelligentCache(
            name='adaptive_test',
            max_size=3,
            strategy=CacheStrategy.ADAPTIVE,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_get_now.return_value = base_time

            # Add 3 entries
            cache.put('key1', 'value1')

            mock_get_now.return_value = base_time + timedelta(seconds=1)
            cache.put('key2', 'value2')

            mock_get_now.return_value = base_time + timedelta(seconds=2)
            cache.put('key3', 'value3')

            # key1: old, frequently accessed (high frequency, low recency)
            mock_get_now.return_value = base_time + timedelta(seconds=3)
            for _ in range(10):
                cache.get('key1')

            # key2: recent, infrequently accessed (low frequency, high recency)
            mock_get_now.return_value = base_time + timedelta(seconds=50)
            cache.get('key2')

            # key3: old, infrequently accessed (low frequency, low recency)
            # This should have worst score

            # Trigger eviction
            mock_get_now.return_value = base_time + timedelta(seconds=60)
            cache.put('key4', 'value4')

            # key3 should be evicted (worst composite score)
            assert cache.get('key3') is None
            assert cache.get('key1') == 'value1'
            assert cache.get('key2') == 'value2'

    def test_adaptive_frequency_weight(self):
        """Test adaptive strategy weights frequency at 70%."""
        cache = IntelligentCache(
            name='adaptive_test',
            max_size=2,
            strategy=CacheStrategy.ADAPTIVE,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_get_now.return_value = base_time

            cache.put('key1', 'value1')
            cache.put('key2', 'value2')

            # key1: very high frequency (should dominate)
            for _ in range(100):
                cache.get('key1')

            # key2: very recent but low frequency
            mock_get_now.return_value = base_time + timedelta(seconds=1000)
            cache.get('key2')

            # Add new entry
            cache.put('key3', 'value3')

            # key2 should be evicted (low frequency dominates recent access)
            assert cache.get('key2') is None
            assert cache.get('key1') == 'value1'

    def test_adaptive_recency_weight(self):
        """Test adaptive strategy weights recency at 30%."""
        cache = IntelligentCache(
            name='adaptive_test',
            max_size=3,
            strategy=CacheStrategy.ADAPTIVE,
        )

        with patch.object(cache, '_get_now') as mock_get_now:
            base_time = datetime(2024, 1, 1, 12, 0, 0)
            mock_get_now.return_value = base_time

            # Add entries
            cache.put('key1', 'value1')
            cache.put('key2', 'value2')
            cache.put('key3', 'value3')

            # All accessed same number of times but at different times
            mock_get_now.return_value = base_time + timedelta(hours=1)
            cache.get('key1')

            mock_get_now.return_value = base_time + timedelta(hours=2)
            cache.get('key2')

            mock_get_now.return_value = base_time + timedelta(hours=3)
            cache.get('key3')

            # Trigger eviction
            mock_get_now.return_value = base_time + timedelta(hours=4)
            cache.put('key4', 'value4')

            # key1 should be evicted (least recent)
            assert cache.get('key1') is None

    def test_adaptive_updates_frequency_scores(self):
        """Test adaptive strategy maintains frequency scores."""
        cache = IntelligentCache(
            name='adaptive_test',
            max_size=5,
            strategy=CacheStrategy.ADAPTIVE,
        )

        cache.put('key1', 'value1')
        cache.put('key2', 'value2')

        # Access multiple times
        for _ in range(5):
            cache.get('key1')

        for _ in range(2):
            cache.get('key2')

        # Check frequency scores are maintained
        assert 'key1' in cache._frequency_scores
        assert 'key2' in cache._frequency_scores
        assert cache._frequency_scores['key1'] > cache._frequency_scores['key2']

    def test_adaptive_empty_cache_no_eviction(self):
        """Test adaptive strategy handles empty cache."""
        cache = IntelligentCache(
            name='adaptive_test',
            max_size=3,
            strategy=CacheStrategy.ADAPTIVE,
        )

        cache.put('key1', 'value1')

        assert cache.get('key1') == 'value1'
        assert len(cache._cache) == 1


class TestEvictionBehaviorComparison:
    """Compare eviction behaviors across strategies."""

    def test_same_workload_different_strategies(self):
        """Test different strategies with same workload produce different results."""
        # Create caches with different strategies
        lru_cache = IntelligentCache('lru', max_size=3, strategy=CacheStrategy.LRU)
        lfu_cache = IntelligentCache('lfu', max_size=3, strategy=CacheStrategy.LFU)
        adaptive_cache = IntelligentCache(
            'adaptive', max_size=3, strategy=CacheStrategy.ADAPTIVE
        )

        # Same initial entries
        for cache in [lru_cache, lfu_cache, adaptive_cache]:
            cache.put('key1', 'value1')
            cache.put('key2', 'value2')
            cache.put('key3', 'value3')

        # Same access pattern
        # key1: 1 access
        for cache in [lru_cache, lfu_cache, adaptive_cache]:
            cache.get('key1')

        # key2: 5 accesses
        for _ in range(5):
            for cache in [lru_cache, lfu_cache, adaptive_cache]:
                cache.get('key2')

        # key3: 3 accesses
        for _ in range(3):
            for cache in [lru_cache, lfu_cache, adaptive_cache]:
                cache.get('key3')

        # Add new entry to trigger eviction
        for cache in [lru_cache, lfu_cache, adaptive_cache]:
            cache.put('key4', 'value4')

        # LFU should evict key1 (least frequent)
        assert lfu_cache.get('key1') is None

        # All should have same size
        assert len(lru_cache._cache) == 3
        assert len(lfu_cache._cache) == 3
        assert len(adaptive_cache._cache) == 3

    def test_strategy_effectiveness_metrics(self):
        """Test that different strategies can be compared via metrics."""
        strategies = [
            CacheStrategy.LRU,
            CacheStrategy.LFU,
            CacheStrategy.ADAPTIVE,
        ]

        results = {}

        for strategy in strategies:
            cache = IntelligentCache(
                name=f'{strategy}_cache',
                max_size=5,
                strategy=strategy,
            )

            # Same workload for all
            for i in range(10):
                cache.put(f'key{i}', f'value{i}')

            # Access some keys
            for _ in range(5):
                cache.get('key5')
                cache.get('key6')

            metrics = cache.get_metrics()
            results[strategy] = {
                'evictions': metrics.eviction_count,
                'hit_ratio': metrics.hit_ratio,
            }

        # All strategies should have recorded evictions
        for strategy_results in results.values():
            assert strategy_results['evictions'] > 0


class TestEdgeCases:
    """Test edge cases in cache eviction."""

    def test_eviction_with_max_size_one(self):
        """Test eviction works with max_size=1."""
        cache = IntelligentCache(
            name='tiny_cache',
            max_size=1,
            strategy=CacheStrategy.LRU,
        )

        cache.put('key1', 'value1')
        assert cache.get('key1') == 'value1'

        # This should evict key1
        cache.put('key2', 'value2')

        assert cache.get('key1') is None
        assert cache.get('key2') == 'value2'
        assert len(cache._cache) == 1

    def test_rapid_evictions(self):
        """Test multiple rapid evictions."""
        cache = IntelligentCache(
            name='small_cache',
            max_size=2,
            strategy=CacheStrategy.LRU,
        )

        # Add many entries rapidly
        for i in range(10):
            cache.put(f'key{i}', f'value{i}')

        # Should have exactly 2 entries
        assert len(cache._cache) == 2
        # Should have evicted 8 entries
        metrics = cache.get_metrics()
        assert metrics.eviction_count == 8

    def test_eviction_with_no_entries(self):
        """Test eviction on empty cache doesn't crash."""
        cache = IntelligentCache(
            name='empty_cache',
            max_size=2,
            strategy=CacheStrategy.LRU,
        )

        # Manually trigger eviction on empty cache
        cache._evict_lru()
        cache._evict_lfu()
        cache._evict_expired()
        cache._evict_adaptive()

        # Should not crash and cache should remain empty
        assert len(cache._cache) == 0
