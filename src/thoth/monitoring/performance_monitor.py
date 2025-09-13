"""
Performance monitoring and caching system for settings operations.

This module provides comprehensive performance tracking, intelligent caching,
and optimization suggestions for configuration management operations.
"""

import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from loguru import logger
from pydantic import BaseModel


class CacheStrategy(str):
    """Cache strategy constants."""

    LRU = 'lru'  # Least Recently Used
    LFU = 'lfu'  # Least Frequently Used
    TTL = 'ttl'  # Time To Live
    ADAPTIVE = 'adaptive'  # Adaptive based on access patterns


class PerformanceMetrics(BaseModel):
    """Performance metrics for operations."""

    operation_name: str
    total_calls: int
    total_duration: float
    average_duration: float
    min_duration: float
    max_duration: float
    cache_hits: int
    cache_misses: int
    cache_hit_ratio: float
    memory_usage_mb: float
    optimization_opportunities: list[str]


class CacheMetrics(BaseModel):
    """Cache performance metrics."""

    cache_name: str
    total_size: int
    used_size: int
    hit_count: int
    miss_count: int
    hit_ratio: float
    eviction_count: int
    memory_usage_mb: float
    entry_count: int
    average_access_time: float


class OptimizationSuggestion(BaseModel):
    """Performance optimization suggestion."""

    suggestion_id: str
    type: str  # 'cache', 'performance', 'memory', 'network'
    severity: str  # 'low', 'medium', 'high', 'critical'
    title: str
    description: str
    impact_estimate: str
    implementation_effort: str
    code_changes_required: list[str]
    performance_gain_estimate: float  # Percentage improvement


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    value: Any
    timestamp: datetime
    access_count: int
    last_accessed: datetime
    ttl: float | None = None
    size_bytes: int = 0


class IntelligentCache:
    """Intelligent caching system with multiple strategies."""

    def __init__(
        self,
        name: str,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.ADAPTIVE,
        default_ttl: float | None = None,
    ):
        """Initialize the cache."""
        self.name = name
        self.max_size = max_size
        self.strategy = strategy
        self.default_ttl = default_ttl

        self._cache: dict[str, CacheEntry] = {}
        self._access_times: deque = deque(maxlen=1000)
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0

        # Access pattern tracking for adaptive strategy
        self._access_patterns: dict[str, list[datetime]] = defaultdict(list)
        self._frequency_scores: dict[str, float] = defaultdict(float)

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        entry = self._cache.get(key)

        if entry is None:
            self._miss_count += 1
            return None

        # Check TTL expiration
        if entry.ttl and (datetime.now() - entry.timestamp).total_seconds() > entry.ttl:
            self._cache.pop(key, None)
            self._miss_count += 1
            return None

        # Update access metadata
        entry.last_accessed = datetime.now()
        entry.access_count += 1

        # Track access patterns
        self._track_access_pattern(key)

        self._hit_count += 1
        self._access_times.append(time.time())

        return entry.value

    def put(self, key: str, value: Any, ttl: float | None = None) -> None:
        """Put value in cache."""
        # Calculate value size (rough estimate)
        size_bytes = self._estimate_size(value)

        # Create cache entry
        entry = CacheEntry(
            key=key,
            value=value,
            timestamp=datetime.now(),
            access_count=1,
            last_accessed=datetime.now(),
            ttl=ttl or self.default_ttl,
            size_bytes=size_bytes,
        )

        # Check if we need to evict entries
        if len(self._cache) >= self.max_size:
            self._evict_entries()

        self._cache[key] = entry
        self._track_access_pattern(key)

    def invalidate(self, key: str) -> bool:
        """Invalidate a specific cache entry."""
        return self._cache.pop(key, None) is not None

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._access_patterns.clear()
        self._frequency_scores.clear()
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0

    def get_metrics(self) -> CacheMetrics:
        """Get cache performance metrics."""
        total_requests = self._hit_count + self._miss_count
        hit_ratio = self._hit_count / total_requests if total_requests > 0 else 0.0

        # Calculate memory usage
        memory_usage = sum(entry.size_bytes for entry in self._cache.values()) / (
            1024 * 1024
        )

        # Calculate average access time
        avg_access_time = (
            sum(self._access_times) / len(self._access_times)
            if self._access_times
            else 0.0
        )

        return CacheMetrics(
            cache_name=self.name,
            total_size=self.max_size,
            used_size=len(self._cache),
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            hit_ratio=hit_ratio,
            eviction_count=self._eviction_count,
            memory_usage_mb=memory_usage,
            entry_count=len(self._cache),
            average_access_time=avg_access_time,
        )

    def _track_access_pattern(self, key: str) -> None:
        """Track access patterns for adaptive caching."""
        now = datetime.now()
        self._access_patterns[key].append(now)

        # Keep only recent accesses (last hour)
        cutoff = now - timedelta(hours=1)
        self._access_patterns[key] = [
            access_time
            for access_time in self._access_patterns[key]
            if access_time > cutoff
        ]

        # Update frequency score
        self._frequency_scores[key] = len(self._access_patterns[key])

    def _evict_entries(self) -> None:
        """Evict entries based on cache strategy."""
        if self.strategy == CacheStrategy.LRU:
            self._evict_lru()
        elif self.strategy == CacheStrategy.LFU:
            self._evict_lfu()
        elif self.strategy == CacheStrategy.TTL:
            self._evict_expired()
        elif self.strategy == CacheStrategy.ADAPTIVE:
            self._evict_adaptive()
        else:
            self._evict_lru()  # Default fallback

    def _evict_lru(self) -> None:
        """Evict least recently used entries."""
        if not self._cache:
            return

        # Find least recently used entry
        lru_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        self._cache.pop(lru_key, None)
        self._eviction_count += 1

    def _evict_lfu(self) -> None:
        """Evict least frequently used entries."""
        if not self._cache:
            return

        # Find least frequently used entry
        lfu_key = min(self._cache.keys(), key=lambda k: self._cache[k].access_count)
        self._cache.pop(lfu_key, None)
        self._eviction_count += 1

    def _evict_expired(self) -> None:
        """Evict expired TTL entries."""
        now = datetime.now()
        expired_keys = []

        for key, entry in self._cache.items():
            if entry.ttl and (now - entry.timestamp).total_seconds() > entry.ttl:
                expired_keys.append(key)

        for key in expired_keys:
            self._cache.pop(key, None)
            self._eviction_count += 1

    def _evict_adaptive(self) -> None:
        """Evict entries using adaptive strategy."""
        if not self._cache:
            return

        # Calculate composite score (recency + frequency)
        scores = {}
        now = datetime.now()

        for key, entry in self._cache.items():
            recency_score = 1.0 / max((now - entry.last_accessed).total_seconds(), 1.0)
            frequency_score = self._frequency_scores.get(key, 0.0)
            scores[key] = recency_score * 0.3 + frequency_score * 0.7

        # Evict entry with lowest score
        worst_key = min(scores.keys(), key=lambda k: scores[k])
        self._cache.pop(worst_key, None)
        self._eviction_count += 1

    def _estimate_size(self, value: Any) -> int:
        """Estimate memory size of value in bytes."""
        try:
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, dict | list):
                return len(json.dumps(value).encode('utf-8'))
            elif isinstance(value, int | float):
                return 8  # Rough estimate
            elif isinstance(value, bool):
                return 1
            else:
                return len(str(value).encode('utf-8'))
        except Exception:
            return 100  # Default estimate


class PerformanceMonitor:
    """Performance monitoring and optimization system for settings operations."""

    def __init__(self, enable_monitoring: bool = True):
        """Initialize the performance monitor."""
        self.enable_monitoring = enable_monitoring

        # Performance tracking
        self._operation_timings: dict[str, list[float]] = defaultdict(list)
        self._operation_metadata: dict[str, dict[str, Any]] = defaultdict(dict)
        self._start_times: dict[str, float] = {}

        # Cache management
        self._caches: dict[str, IntelligentCache] = {}

        # Optimization tracking
        self._optimization_history: list[OptimizationSuggestion] = []
        self._performance_baselines: dict[str, float] = {}

        # Initialize standard caches
        self._init_standard_caches()

    def _init_standard_caches(self) -> None:
        """Initialize standard caches for settings operations."""
        self._caches['schema'] = IntelligentCache(
            name='schema_cache',
            max_size=50,
            strategy=CacheStrategy.TTL,
            default_ttl=3600,  # 1 hour
        )

        self._caches['validation'] = IntelligentCache(
            name='validation_cache',
            max_size=200,
            strategy=CacheStrategy.ADAPTIVE,
            default_ttl=300,  # 5 minutes
        )

        self._caches['settings'] = IntelligentCache(
            name='settings_cache',
            max_size=100,
            strategy=CacheStrategy.LRU,
            default_ttl=1800,  # 30 minutes
        )

    def track_operation_performance(
        self, operation: str, duration: float, metadata: dict[str, Any] | None = None
    ) -> None:
        """Track performance of a settings operation."""
        if not self.enable_monitoring:
            return

        self._operation_timings[operation].append(duration)

        # Keep only recent timings (last 1000)
        if len(self._operation_timings[operation]) > 1000:
            self._operation_timings[operation] = self._operation_timings[operation][
                -1000:
            ]

        # Store metadata
        if metadata:
            self._operation_metadata[operation].update(metadata)

        # Check for performance issues
        self._check_performance_issues(operation, duration)

        logger.debug(f'Tracked operation {operation}: {duration:.3f}s')

    def start_operation_timing(self, operation_id: str) -> None:
        """Start timing an operation."""
        if self.enable_monitoring:
            self._start_times[operation_id] = time.time()

    def end_operation_timing(
        self,
        operation_id: str,
        operation_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> float | None:
        """End timing an operation and record the duration."""
        if not self.enable_monitoring or operation_id not in self._start_times:
            return None

        duration = time.time() - self._start_times.pop(operation_id)
        self.track_operation_performance(operation_name, duration, metadata)
        return duration

    def get_performance_metrics(self) -> dict[str, PerformanceMetrics]:
        """Get comprehensive performance metrics."""
        metrics = {}

        for operation, timings in self._operation_timings.items():
            if not timings:
                continue

            # Calculate cache metrics for this operation
            cache_hits = self._operation_metadata[operation].get('cache_hits', 0)
            cache_misses = self._operation_metadata[operation].get('cache_misses', 0)
            total_cache_requests = cache_hits + cache_misses
            cache_hit_ratio = (
                cache_hits / total_cache_requests if total_cache_requests > 0 else 0.0
            )

            # Generate optimization opportunities
            optimization_opportunities = self._generate_optimization_opportunities(
                operation, timings
            )

            metrics[operation] = PerformanceMetrics(
                operation_name=operation,
                total_calls=len(timings),
                total_duration=sum(timings),
                average_duration=sum(timings) / len(timings),
                min_duration=min(timings),
                max_duration=max(timings),
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                cache_hit_ratio=cache_hit_ratio,
                memory_usage_mb=self._estimate_memory_usage(),
                optimization_opportunities=optimization_opportunities,
            )

        return metrics

    def suggest_optimizations(self) -> list[OptimizationSuggestion]:
        """Generate performance optimization suggestions."""
        suggestions = []

        # Analyze performance metrics
        metrics = self.get_performance_metrics()

        for operation, metric in metrics.items():
            # Slow operations
            if metric.average_duration > 1.0:
                suggestions.append(
                    OptimizationSuggestion(
                        suggestion_id=f'optimize_slow_{operation}',
                        type='performance',
                        severity='high',
                        title=f'Optimize slow {operation} operation',
                        description=f'Operation {operation} averages {metric.average_duration:.2f}s which is slower than recommended',
                        impact_estimate='20-50% performance improvement',
                        implementation_effort='medium',
                        code_changes_required=[
                            f'Add caching for {operation}',
                            'Optimize database queries',
                            'Add async processing',
                        ],
                        performance_gain_estimate=30.0,
                    )
                )

            # Low cache hit ratio
            if metric.cache_hit_ratio < 0.5 and metric.total_calls > 10:
                suggestions.append(
                    OptimizationSuggestion(
                        suggestion_id=f'improve_cache_{operation}',
                        type='cache',
                        severity='medium',
                        title=f'Improve cache efficiency for {operation}',
                        description=f'Cache hit ratio is only {metric.cache_hit_ratio:.1%}',
                        impact_estimate='10-30% performance improvement',
                        implementation_effort='low',
                        code_changes_required=[
                            'Adjust cache TTL',
                            'Improve cache key strategy',
                        ],
                        performance_gain_estimate=20.0,
                    )
                )

        # Memory usage suggestions
        total_memory = self._estimate_memory_usage()
        if total_memory > 100:  # More than 100MB
            suggestions.append(
                OptimizationSuggestion(
                    suggestion_id='optimize_memory_usage',
                    type='memory',
                    severity='medium',
                    title='High memory usage detected',
                    description=f'Settings system using {total_memory:.1f}MB of memory',
                    impact_estimate='Reduce memory usage by 30-50%',
                    implementation_effort='medium',
                    code_changes_required=[
                        'Implement cache size limits',
                        'Add memory cleanup routines',
                    ],
                    performance_gain_estimate=40.0,
                )
            )

        return suggestions

    def monitor_cache_effectiveness(self) -> dict[str, CacheMetrics]:
        """Monitor effectiveness of all caches."""
        cache_metrics = {}

        for name, cache in self._caches.items():
            cache_metrics[name] = cache.get_metrics()

        return cache_metrics

    def get_cache(self, cache_name: str) -> IntelligentCache | None:
        """Get a specific cache by name."""
        return self._caches.get(cache_name)

    def create_cache(
        self,
        name: str,
        max_size: int = 1000,
        strategy: CacheStrategy = CacheStrategy.ADAPTIVE,
        ttl: float | None = None,
    ) -> IntelligentCache:
        """Create a new cache."""
        cache = IntelligentCache(name, max_size, strategy, ttl)
        self._caches[name] = cache
        return cache

    def optimize_cache_configuration(self, cache_name: str) -> dict[str, Any]:
        """Optimize cache configuration based on usage patterns."""
        cache = self._caches.get(cache_name)
        if not cache:
            return {'error': f'Cache {cache_name} not found'}

        metrics = cache.get_metrics()
        optimizations = {}

        # Optimize cache size
        if metrics.hit_ratio < 0.3 and metrics.used_size < metrics.total_size * 0.5:
            optimizations['suggested_max_size'] = max(metrics.used_size * 2, 50)
            optimizations['reason'] = 'Low hit ratio with underutilized cache'

        # Optimize strategy
        if metrics.hit_ratio < 0.5:
            if cache.strategy == CacheStrategy.LRU:
                optimizations['suggested_strategy'] = CacheStrategy.ADAPTIVE
                optimizations['strategy_reason'] = (
                    'LRU not effective, try adaptive strategy'
                )

        return optimizations

    def _check_performance_issues(self, operation: str, duration: float) -> None:
        """Check for performance issues in operations."""
        # Set performance baselines if not exist
        if operation not in self._performance_baselines:
            self._performance_baselines[operation] = duration
            return

        baseline = self._performance_baselines[operation]

        # Update baseline with moving average
        self._performance_baselines[operation] = baseline * 0.9 + duration * 0.1

        # Check for performance degradation
        if duration > baseline * 2.0:  # 100% slower than baseline
            logger.warning(
                f'Performance degradation detected in {operation}: {duration:.3f}s (baseline: {baseline:.3f}s)'
            )

    def _generate_optimization_opportunities(
        self, _operation: str, timings: list[float]
    ) -> list[str]:
        """Generate optimization opportunities for an operation."""
        opportunities = []

        avg_duration = sum(timings) / len(timings)

        if avg_duration > 0.5:
            opportunities.append('Consider adding caching')

        if avg_duration > 1.0:
            opportunities.append('Consider async processing')

        if len(timings) > 100 and max(timings) > avg_duration * 5:
            opportunities.append('Investigate performance outliers')

        return opportunities

    def _estimate_memory_usage(self) -> float:
        """Estimate total memory usage in MB."""
        total_size = 0

        for cache in self._caches.values():
            cache_size = sum(entry.size_bytes for entry in cache._cache.values())
            total_size += cache_size

        # Add overhead for tracking structures
        overhead = len(self._operation_timings) * 1000  # Rough estimate
        total_size += overhead

        return total_size / (1024 * 1024)


class SettingsPerformanceManager:
    """Performance manager specifically for settings operations."""

    def __init__(self, monitor: PerformanceMonitor):
        """Initialize the settings performance manager."""
        self.monitor = monitor
        self.settings_cache = monitor.get_cache('settings')
        self.validation_cache = monitor.get_cache('validation')
        self.schema_cache = monitor.get_cache('schema')

    def cache_settings(
        self, settings_key: str, settings: dict[str, Any], ttl: float | None = None
    ) -> None:
        """Cache settings with intelligent invalidation."""
        if self.settings_cache:
            self.settings_cache.put(settings_key, settings, ttl)

    def get_cached_settings(self, settings_key: str) -> dict[str, Any] | None:
        """Get cached settings."""
        if self.settings_cache:
            return self.settings_cache.get(settings_key)
        return None

    def cache_validation_result(
        self, config_hash: str, result: Any, ttl: float | None = None
    ) -> None:
        """Cache validation results."""
        if self.validation_cache:
            self.validation_cache.put(config_hash, result, ttl)

    def get_cached_validation(self, config_hash: str) -> Any | None:
        """Get cached validation result."""
        if self.validation_cache:
            return self.validation_cache.get(config_hash)
        return None

    def cache_schema(
        self, schema_version: str, schema: dict[str, Any], ttl: float | None = None
    ) -> None:
        """Cache schema with version-based invalidation."""
        if self.schema_cache:
            self.schema_cache.put(schema_version, schema, ttl)

    def get_cached_schema(self, schema_version: str) -> dict[str, Any] | None:
        """Get cached schema."""
        if self.schema_cache:
            return self.schema_cache.get(schema_version)
        return None

    def invalidate_settings_cache(self, settings_key: str | None = None) -> None:
        """Invalidate settings cache."""
        if self.settings_cache:
            if settings_key:
                self.settings_cache.invalidate(settings_key)
            else:
                self.settings_cache.clear()

    def invalidate_validation_cache(self) -> None:
        """Invalidate validation cache."""
        if self.validation_cache:
            self.validation_cache.clear()

    def generate_settings_performance_report(self) -> dict[str, Any]:
        """Generate comprehensive performance report for settings operations."""
        metrics = self.monitor.get_performance_metrics()
        cache_metrics = self.monitor.monitor_cache_effectiveness()
        suggestions = self.monitor.suggest_optimizations()

        # Filter for settings-related operations
        settings_metrics = {
            k: v
            for k, v in metrics.items()
            if any(
                keyword in k.lower()
                for keyword in ['settings', 'config', 'validation', 'schema']
            )
        }

        return {
            'performance_metrics': settings_metrics,
            'cache_metrics': cache_metrics,
            'optimization_suggestions': [s.dict() for s in suggestions],
            'memory_usage_mb': self.monitor._estimate_memory_usage(),
            'generated_at': datetime.now().isoformat(),
            'monitoring_enabled': self.monitor.enable_monitoring,
        }


# Decorator for automatic performance tracking
def track_performance(operation_name: str, monitor: PerformanceMonitor | None = None):
    """Decorator to automatically track performance of functions."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            if monitor and monitor.enable_monitoring:
                operation_id = f'{operation_name}_{id(func)}_{int(time.time())}'
                monitor.start_operation_timing(operation_id)

                try:
                    result = func(*args, **kwargs)
                    monitor.end_operation_timing(operation_id, operation_name)
                    return result
                except Exception as e:
                    monitor.end_operation_timing(
                        operation_id, operation_name, {'error': str(e)}
                    )
                    raise
            else:
                return func(*args, **kwargs)

        return wrapper

    return decorator


# Global performance monitor instance
_global_monitor: PerformanceMonitor | None = None


def get_global_performance_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor


def configure_performance_monitoring(
    enable: bool = True, cache_config: dict[str, Any] | None = None
) -> None:
    """Configure global performance monitoring."""
    global _global_monitor
    _global_monitor = PerformanceMonitor(enable)

    if cache_config:
        for cache_name, config in cache_config.items():
            _global_monitor.create_cache(
                name=cache_name,
                max_size=config.get('max_size', 1000),
                strategy=config.get('strategy', CacheStrategy.ADAPTIVE),
                ttl=config.get('ttl'),
            )
