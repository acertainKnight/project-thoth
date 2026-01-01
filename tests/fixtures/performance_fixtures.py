"""
Fixtures for performance monitoring tests.

This module provides reusable fixtures, mock data, and test utilities
for testing the performance monitoring system.
"""

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock

import pytest

from thoth.monitoring.performance_monitor import (
    CacheEntry,
    CacheStrategy,
    IntelligentCache,
    PerformanceMonitor,
    SettingsPerformanceManager,
)


@pytest.fixture
def cache_strategies():
    """Provide all cache strategy types."""
    return [
        CacheStrategy.LRU,
        CacheStrategy.LFU,
        CacheStrategy.TTL,
        CacheStrategy.ADAPTIVE,
    ]


@pytest.fixture
def sample_cache_entries():
    """Create sample cache entries with various access patterns."""
    now = datetime.now()

    return {
        'frequently_accessed': CacheEntry(
            key='freq_key',
            value={'data': 'frequently accessed'},
            timestamp=now - timedelta(minutes=30),
            access_count=50,
            last_accessed=now - timedelta(seconds=5),
            ttl=3600,
            size_bytes=1024,
        ),
        'recently_accessed': CacheEntry(
            key='recent_key',
            value={'data': 'recently accessed'},
            timestamp=now - timedelta(minutes=5),
            access_count=5,
            last_accessed=now - timedelta(seconds=1),
            ttl=3600,
            size_bytes=512,
        ),
        'stale_entry': CacheEntry(
            key='stale_key',
            value={'data': 'stale'},
            timestamp=now - timedelta(hours=2),
            access_count=1,
            last_accessed=now - timedelta(hours=1),
            ttl=3600,
            size_bytes=256,
        ),
        'expired_entry': CacheEntry(
            key='expired_key',
            value={'data': 'expired'},
            timestamp=now - timedelta(hours=3),
            access_count=10,
            last_accessed=now - timedelta(hours=2),
            ttl=60,  # 1 minute TTL (expired)
            size_bytes=128,
        ),
        'infrequent_entry': CacheEntry(
            key='infreq_key',
            value={'data': 'infrequent'},
            timestamp=now - timedelta(minutes=15),
            access_count=2,
            last_accessed=now - timedelta(minutes=10),
            ttl=3600,
            size_bytes=768,
        ),
    }


@pytest.fixture
def lru_cache():
    """Create a cache with LRU strategy."""
    return IntelligentCache(
        name='test_lru',
        max_size=10,
        strategy=CacheStrategy.LRU,
        default_ttl=None,
    )


@pytest.fixture
def lfu_cache():
    """Create a cache with LFU strategy."""
    return IntelligentCache(
        name='test_lfu',
        max_size=10,
        strategy=CacheStrategy.LFU,
        default_ttl=None,
    )


@pytest.fixture
def ttl_cache():
    """Create a cache with TTL strategy."""
    return IntelligentCache(
        name='test_ttl',
        max_size=10,
        strategy=CacheStrategy.TTL,
        default_ttl=60.0,  # 60 seconds
    )


@pytest.fixture
def adaptive_cache():
    """Create a cache with adaptive strategy."""
    return IntelligentCache(
        name='test_adaptive',
        max_size=10,
        strategy=CacheStrategy.ADAPTIVE,
        default_ttl=300.0,  # 5 minutes
    )


@pytest.fixture
def performance_monitor():
    """Create a performance monitor instance."""
    return PerformanceMonitor(enable_monitoring=True)


@pytest.fixture
def disabled_performance_monitor():
    """Create a disabled performance monitor."""
    return PerformanceMonitor(enable_monitoring=False)


@pytest.fixture
def settings_performance_manager(performance_monitor):
    """Create a settings performance manager."""
    return SettingsPerformanceManager(performance_monitor)


@pytest.fixture
def sample_settings_data():
    """Provide sample settings data for testing."""
    return {
        'simple_settings': {
            'database': {
                'host': 'localhost',
                'port': 5432,
                'name': 'testdb',
            },
            'logging': {
                'level': 'INFO',
                'file': '/var/log/app.log',
            },
        },
        'complex_settings': {
            'services': [
                {'name': 'api', 'port': 8000, 'workers': 4},
                {'name': 'worker', 'port': 8001, 'workers': 8},
            ],
            'cache': {
                'type': 'redis',
                'host': 'redis.local',
                'ttl': 3600,
            },
            'features': {
                'feature_a': True,
                'feature_b': False,
                'feature_c': {'enabled': True, 'config': {'key': 'value'}},
            },
        },
        'nested_settings': {
            'level1': {
                'level2': {
                    'level3': {
                        'level4': {'value': 'deep_nested'},
                    },
                },
            },
        },
    }


@pytest.fixture
def sample_validation_results():
    """Provide sample validation results."""
    return {
        'valid_result': {
            'valid': True,
            'errors': [],
            'warnings': [],
        },
        'invalid_result': {
            'valid': False,
            'errors': [
                'Field "host" is required',
                'Port must be between 1 and 65535',
            ],
            'warnings': ['Deprecated configuration option used'],
        },
        'partial_result': {
            'valid': True,
            'errors': [],
            'warnings': [
                'Configuration could be optimized',
                'Missing optional field "timeout"',
            ],
        },
    }


@pytest.fixture
def sample_schemas():
    """Provide sample JSON schemas."""
    return {
        'simple_schema': {
            'type': 'object',
            'properties': {
                'name': {'type': 'string'},
                'age': {'type': 'integer'},
            },
            'required': ['name'],
        },
        'complex_schema': {
            'type': 'object',
            'properties': {
                'config': {
                    'type': 'object',
                    'properties': {
                        'database': {
                            'type': 'object',
                            'properties': {
                                'host': {'type': 'string'},
                                'port': {'type': 'integer', 'minimum': 1},
                            },
                            'required': ['host', 'port'],
                        },
                    },
                },
            },
        },
    }


@pytest.fixture
def mock_time_series():
    """Create a mock time series for testing performance tracking."""
    base_time = 100.0
    return {
        'fast_operations': [0.001, 0.002, 0.0015, 0.003, 0.0025],
        'slow_operations': [1.5, 2.0, 1.8, 2.2, 1.9],
        'variable_operations': [0.1, 0.5, 2.0, 0.2, 5.0, 0.15, 3.0],
        'consistent_operations': [0.5, 0.51, 0.49, 0.50, 0.52, 0.48],
        'timestamps': [base_time + i * 10 for i in range(10)],
    }


class MockTimeProvider:
    """Mock time provider for testing TTL and time-based operations."""

    def __init__(self, initial_time: float = 0.0):
        """Initialize with an initial time."""
        self.current_time = initial_time
        self.current_datetime = datetime.fromtimestamp(initial_time)

    def advance(self, seconds: float):
        """Advance time by specified seconds."""
        self.current_time += seconds
        self.current_datetime = datetime.fromtimestamp(self.current_time)

    def time(self) -> float:
        """Return current timestamp."""
        return self.current_time

    def now(self) -> datetime:
        """Return current datetime."""
        return self.current_datetime

    def reset(self):
        """Reset to initial time."""
        self.current_time = 0.0
        self.current_datetime = datetime.fromtimestamp(0.0)


@pytest.fixture
def mock_time():
    """Provide a mock time provider."""
    return MockTimeProvider(initial_time=1000000.0)


def create_cache_with_entries(
    cache: IntelligentCache,
    entries: dict[str, Any],
) -> IntelligentCache:
    """Helper to populate a cache with test entries."""
    for key, value in entries.items():
        cache.put(key, value)
    return cache


def simulate_access_pattern(
    cache: IntelligentCache,
    pattern: dict[str, int],
) -> dict[str, int]:
    """
    Simulate access patterns on cache.

    Args:
        cache: Cache to access
        pattern: Dict mapping keys to number of accesses

    Returns:
        Dict with hit/miss counts
    """
    hits = 0
    misses = 0

    for key, access_count in pattern.items():
        for _ in range(access_count):
            result = cache.get(key)
            if result is not None:
                hits += 1
            else:
                misses += 1

    return {'hits': hits, 'misses': misses}


def assert_cache_entry_evicted(cache: IntelligentCache, key: str) -> bool:
    """Assert that a specific cache entry was evicted."""
    return key not in cache._cache


def assert_cache_size(cache: IntelligentCache, expected_size: int) -> None:
    """Assert cache has expected number of entries."""
    assert len(cache._cache) == expected_size, (
        f'Expected cache size {expected_size}, got {len(cache._cache)}'
    )


def create_performance_scenario(
    monitor: PerformanceMonitor,
    operations: dict[str, list[float]],
) -> None:
    """
    Create a performance scenario with specific operation timings.

    Args:
        monitor: Performance monitor to track operations
        operations: Dict mapping operation names to list of durations
    """
    for operation_name, durations in operations.items():
        for duration in durations:
            monitor.track_operation_performance(operation_name, duration)


def generate_cache_load(
    cache: IntelligentCache,
    num_entries: int,
    key_prefix: str = 'key',
) -> list[str]:
    """
    Generate load on cache by adding many entries.

    Args:
        cache: Cache to populate
        num_entries: Number of entries to add
        key_prefix: Prefix for generated keys

    Returns:
        List of generated keys
    """
    keys = []
    for i in range(num_entries):
        key = f'{key_prefix}_{i}'
        cache.put(key, f'value_{i}')
        keys.append(key)
    return keys


@pytest.fixture
def cache_eviction_scenarios():
    """Provide scenarios for testing cache eviction."""
    return {
        'lru_scenario': {
            'strategy': CacheStrategy.LRU,
            'entries': [
                ('key1', 'val1'),
                ('key2', 'val2'),
                ('key3', 'val3'),
            ],
            'access_order': ['key1', 'key2', 'key1', 'key3'],
            'expected_eviction': 'key2',  # Least recently used
        },
        'lfu_scenario': {
            'strategy': CacheStrategy.LFU,
            'entries': [
                ('key1', 'val1'),
                ('key2', 'val2'),
                ('key3', 'val3'),
            ],
            'access_counts': {'key1': 5, 'key2': 1, 'key3': 3},
            'expected_eviction': 'key2',  # Least frequently used
        },
        'adaptive_scenario': {
            'strategy': CacheStrategy.ADAPTIVE,
            'entries': [
                ('key1', 'val1'),  # Old but frequently accessed
                ('key2', 'val2'),  # Recent but infrequently accessed
                ('key3', 'val3'),  # Old and infrequently accessed
            ],
            'expected_eviction': 'key3',  # Worst composite score
        },
    }


@pytest.fixture
def performance_optimization_scenarios():
    """Provide scenarios for testing optimization suggestions."""
    return {
        'slow_operations': {
            'operation': 'slow_query',
            'durations': [1.5, 2.0, 1.8, 2.2, 1.9],  # > 1.0s average
            'expected_suggestions': ['performance'],
        },
        'low_cache_hit': {
            'operation': 'cached_operation',
            'durations': [0.1] * 20,
            'cache_hits': 5,
            'cache_misses': 15,  # 25% hit ratio
            'expected_suggestions': ['cache'],
        },
        'high_memory': {
            'memory_usage_mb': 150,  # > 100MB
            'expected_suggestions': ['memory'],
        },
        'all_issues': {
            'operations': {
                'slow_op': [1.5, 2.0, 1.8],
                'cached_op': [0.1] * 20,
            },
            'cache_hits': 3,
            'cache_misses': 17,
            'memory_usage_mb': 120,
            'expected_suggestions': ['performance', 'cache', 'memory'],
        },
    }


@pytest.fixture
def memory_estimation_data():
    """Provide data for testing memory estimation."""
    return {
        'small_string': 'hello',
        'large_string': 'x' * 10000,
        'small_dict': {'a': 1, 'b': 2},
        'large_dict': {f'key_{i}': f'value_{i}' for i in range(1000)},
        'small_list': [1, 2, 3, 4, 5],
        'large_list': list(range(10000)),
        'integer': 42,
        'float': 3.14159,
        'boolean': True,
        'complex_nested': {
            'level1': {
                'level2': {
                    'list': [1, 2, 3],
                    'dict': {'a': 'b'},
                    'string': 'nested',
                },
            },
        },
    }
