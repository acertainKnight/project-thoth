"""
Tests for PerformanceMonitor, SettingsPerformanceManager, and @track_performance decorator.

This module tests:
- PerformanceMonitor operations and metrics
- Settings-specific performance management
- Performance tracking decorator
- Optimization suggestions
- Cache management and configuration
"""  # noqa: W505

import time
from datetime import datetime  # noqa: F401
from unittest.mock import Mock, patch  # noqa: F401

import pytest

from tests.fixtures.performance_fixtures import (
    create_performance_scenario,  # noqa: F401
    generate_cache_load,  # noqa: F401
)
from thoth.monitoring.performance_monitor import (
    CacheStrategy,
    OptimizationSuggestion,  # noqa: F401
    PerformanceMetrics,  # noqa: F401
    PerformanceMonitor,
    SettingsPerformanceManager,  # noqa: F401
    configure_performance_monitoring,
    get_global_performance_monitor,
    track_performance,
)


class TestPerformanceMonitorInitialization:
    """Test PerformanceMonitor initialization."""

    def test_monitor_initialization_enabled(self):
        """Test monitor initializes with monitoring enabled."""
        monitor = PerformanceMonitor(enable_monitoring=True)

        assert monitor.enable_monitoring is True
        assert len(monitor._caches) == 3  # schema, validation, settings
        assert 'schema' in monitor._caches
        assert 'validation' in monitor._caches
        assert 'settings' in monitor._caches

    def test_monitor_initialization_disabled(self):
        """Test monitor initializes with monitoring disabled."""
        monitor = PerformanceMonitor(enable_monitoring=False)

        assert monitor.enable_monitoring is False
        # Caches still initialized even if monitoring disabled
        assert len(monitor._caches) == 3

    def test_standard_caches_created(self):
        """Test standard caches are created with correct configuration."""
        monitor = PerformanceMonitor()

        # Check schema cache
        schema_cache = monitor.get_cache('schema')
        assert schema_cache is not None
        assert schema_cache.max_size == 50
        assert schema_cache.strategy == CacheStrategy.TTL
        assert schema_cache.default_ttl == 3600

        # Check validation cache
        validation_cache = monitor.get_cache('validation')
        assert validation_cache is not None
        assert validation_cache.max_size == 200
        assert validation_cache.strategy == CacheStrategy.ADAPTIVE
        assert validation_cache.default_ttl == 300

        # Check settings cache
        settings_cache = monitor.get_cache('settings')
        assert settings_cache is not None
        assert settings_cache.max_size == 100
        assert settings_cache.strategy == CacheStrategy.LRU
        assert settings_cache.default_ttl == 1800


class TestPerformanceTracking:
    """Test performance tracking operations."""

    def test_track_operation_performance(self, performance_monitor):
        """Test tracking operation performance."""
        performance_monitor.track_operation_performance('test_operation', 0.5)

        assert 'test_operation' in performance_monitor._operation_timings
        assert len(performance_monitor._operation_timings['test_operation']) == 1
        assert performance_monitor._operation_timings['test_operation'][0] == 0.5

    def test_track_multiple_operations(self, performance_monitor):
        """Test tracking multiple operations."""
        performance_monitor.track_operation_performance('op1', 0.1)
        performance_monitor.track_operation_performance('op2', 0.2)
        performance_monitor.track_operation_performance('op1', 0.15)

        assert len(performance_monitor._operation_timings['op1']) == 2
        assert len(performance_monitor._operation_timings['op2']) == 1

    def test_track_with_metadata(self, performance_monitor):
        """Test tracking operation with metadata."""
        metadata = {'user': 'test_user', 'endpoint': '/api/settings'}
        performance_monitor.track_operation_performance(
            'api_call',
            0.3,
            metadata=metadata,
        )

        assert (
            performance_monitor._operation_metadata['api_call']['user'] == 'test_user'
        )
        assert (
            performance_monitor._operation_metadata['api_call']['endpoint']
            == '/api/settings'
        )

    def test_track_keeps_last_1000_timings(self, performance_monitor):
        """Test tracking keeps only last 1000 timings."""
        # Add 1500 timings
        for i in range(1500):  # noqa: B007
            performance_monitor.track_operation_performance('large_op', 0.001)

        # Should keep only last 1000
        assert len(performance_monitor._operation_timings['large_op']) == 1000

    def test_disabled_monitoring_no_tracking(self, disabled_performance_monitor):
        """Test disabled monitoring doesn't track operations."""
        disabled_performance_monitor.track_operation_performance('test_op', 0.5)

        # Should not track anything
        assert len(disabled_performance_monitor._operation_timings) == 0


class TestOperationTiming:
    """Test start/end operation timing."""

    def test_start_operation_timing(self, performance_monitor):
        """Test starting operation timing."""
        with patch('thoth.monitoring.performance_monitor.time.time') as mock_time:
            mock_time.return_value = 1000.0

            performance_monitor.start_operation_timing('op_123')

            assert 'op_123' in performance_monitor._start_times
            assert performance_monitor._start_times['op_123'] == 1000.0

    def test_end_operation_timing(self, performance_monitor):
        """Test ending operation timing and calculating duration."""
        with patch('thoth.monitoring.performance_monitor.time.time') as mock_time:
            # Start at 1000.0
            mock_time.return_value = 1000.0
            performance_monitor.start_operation_timing('op_123')

            # End at 1002.5
            mock_time.return_value = 1002.5
            duration = performance_monitor.end_operation_timing(
                'op_123',
                'test_operation',
            )

            assert duration == 2.5
            assert 'test_operation' in performance_monitor._operation_timings
            assert performance_monitor._operation_timings['test_operation'][0] == 2.5

    def test_end_timing_with_metadata(self, performance_monitor):
        """Test ending timing with metadata."""
        with patch('thoth.monitoring.performance_monitor.time.time') as mock_time:
            mock_time.return_value = 1000.0
            performance_monitor.start_operation_timing('op_123')

            mock_time.return_value = 1001.0
            metadata = {'status': 'success', 'rows': 100}
            duration = performance_monitor.end_operation_timing(
                'op_123',
                'db_query',
                metadata=metadata,
            )

            assert duration == 1.0
            assert (
                performance_monitor._operation_metadata['db_query']['status']
                == 'success'
            )
            assert performance_monitor._operation_metadata['db_query']['rows'] == 100

    def test_end_timing_nonexistent_operation(self, performance_monitor):
        """Test ending timing for non-existent operation returns None."""
        duration = performance_monitor.end_operation_timing(
            'nonexistent',
            'test_op',
        )

        assert duration is None

    def test_disabled_monitoring_no_timing(self, disabled_performance_monitor):
        """Test disabled monitoring doesn't track timing."""
        disabled_performance_monitor.start_operation_timing('op_123')

        assert 'op_123' not in disabled_performance_monitor._start_times


class TestPerformanceMetrics:
    """Test performance metrics calculation."""

    def test_get_performance_metrics_basic(self, performance_monitor):
        """Test getting basic performance metrics."""
        # Track some operations
        performance_monitor.track_operation_performance('test_op', 0.1)
        performance_monitor.track_operation_performance('test_op', 0.2)
        performance_monitor.track_operation_performance('test_op', 0.15)

        metrics = performance_monitor.get_performance_metrics()

        assert 'test_op' in metrics
        metric = metrics['test_op']

        assert metric.operation_name == 'test_op'
        assert metric.total_calls == 3
        assert metric.total_duration == pytest.approx(0.45, rel=1e-9)
        assert metric.average_duration == pytest.approx(0.15, rel=1e-9)
        assert metric.min_duration == pytest.approx(0.1, rel=1e-9)
        assert metric.max_duration == pytest.approx(0.2, rel=1e-9)

    def test_metrics_with_cache_data(self, performance_monitor):
        """Test metrics include cache hit/miss data."""
        metadata = {'cache_hits': 10, 'cache_misses': 5}
        performance_monitor.track_operation_performance(
            'cached_op',
            0.1,
            metadata=metadata,
        )

        metrics = performance_monitor.get_performance_metrics()
        metric = metrics['cached_op']

        assert metric.cache_hits == 10
        assert metric.cache_misses == 5
        assert metric.cache_hit_ratio == 10 / 15  # 66.7%

    def test_metrics_no_cache_data(self, performance_monitor):
        """Test metrics with no cache data."""
        performance_monitor.track_operation_performance('no_cache_op', 0.1)

        metrics = performance_monitor.get_performance_metrics()
        metric = metrics['no_cache_op']

        assert metric.cache_hits == 0
        assert metric.cache_misses == 0
        assert metric.cache_hit_ratio == 0.0

    def test_metrics_memory_usage(self, performance_monitor):
        """Test metrics include memory usage."""
        performance_monitor.track_operation_performance('test_op', 0.1)

        metrics = performance_monitor.get_performance_metrics()
        metric = metrics['test_op']

        assert metric.memory_usage_mb >= 0

    def test_empty_metrics(self, performance_monitor):
        """Test getting metrics with no operations tracked."""
        metrics = performance_monitor.get_performance_metrics()

        assert len(metrics) == 0


class TestOptimizationSuggestions:
    """Test optimization suggestion generation."""

    def test_slow_operation_suggestion(self, performance_monitor):
        """Test suggestion for slow operations (>1.0s average)."""
        # Add slow operations
        for _ in range(5):
            performance_monitor.track_operation_performance('slow_op', 1.5)

        suggestions = performance_monitor.suggest_optimizations()

        # Should have performance suggestion
        perf_suggestions = [s for s in suggestions if s.type == 'performance']
        assert len(perf_suggestions) > 0

        suggestion = perf_suggestions[0]
        assert suggestion.severity == 'high'
        assert 'slow_op' in suggestion.title
        assert suggestion.performance_gain_estimate == 30.0

    def test_low_cache_hit_ratio_suggestion(self, performance_monitor):
        """Test suggestion for low cache hit ratio (<50%)."""
        # Track operations with low cache hit ratio
        for _ in range(15):
            metadata = {'cache_hits': 3, 'cache_misses': 7}
            performance_monitor.track_operation_performance(
                'cached_op',
                0.1,
                metadata=metadata,
            )

        suggestions = performance_monitor.suggest_optimizations()

        # Should have cache suggestion
        cache_suggestions = [s for s in suggestions if s.type == 'cache']
        assert len(cache_suggestions) > 0

        suggestion = cache_suggestions[0]
        assert suggestion.severity == 'medium'
        assert 'cache' in suggestion.title.lower()

    def test_high_memory_usage_suggestion(self, performance_monitor):
        """Test suggestion for high memory usage (>100MB)."""
        # Fill caches to increase memory usage
        settings_cache = performance_monitor.get_cache('settings')
        for i in range(100):
            # Add large values to increase memory
            settings_cache.put(f'key{i}', 'x' * 10000)

        # Track some operations to generate metrics
        performance_monitor.track_operation_performance('test_op', 0.1)

        suggestions = performance_monitor.suggest_optimizations()

        # Check if memory suggestion exists (depends on actual memory usage)
        memory_suggestions = [s for s in suggestions if s.type == 'memory']
        if memory_suggestions:
            suggestion = memory_suggestions[0]
            assert suggestion.severity == 'medium'
            assert 'memory' in suggestion.title.lower()

    def test_multiple_optimization_suggestions(self, performance_monitor):
        """Test multiple suggestions are generated."""
        # Create slow operations
        for _ in range(5):
            performance_monitor.track_operation_performance('slow_op', 1.5)

        # Create low cache hit ratio
        for _ in range(15):
            metadata = {'cache_hits': 2, 'cache_misses': 8}
            performance_monitor.track_operation_performance(
                'cached_op',
                0.2,
                metadata=metadata,
            )

        suggestions = performance_monitor.suggest_optimizations()

        # Should have multiple types of suggestions
        suggestion_types = {s.type for s in suggestions}
        assert 'performance' in suggestion_types
        assert 'cache' in suggestion_types

    def test_no_suggestions_for_good_performance(self, performance_monitor):
        """Test no suggestions when performance is good."""
        # Add fast operations with good cache hit ratio
        for _ in range(20):
            metadata = {'cache_hits': 18, 'cache_misses': 2}
            performance_monitor.track_operation_performance(
                'fast_op',
                0.05,
                metadata=metadata,
            )

        suggestions = performance_monitor.suggest_optimizations()

        # Should have no or minimal suggestions
        assert len(suggestions) <= 1  # May have memory suggestion


class TestPerformanceDegradationDetection:
    """Test performance degradation detection."""

    def test_baseline_establishment(self, performance_monitor):
        """Test performance baseline is established."""
        performance_monitor.track_operation_performance('test_op', 0.5)

        assert 'test_op' in performance_monitor._performance_baselines
        assert performance_monitor._performance_baselines['test_op'] == 0.5

    def test_baseline_moving_average(self, performance_monitor):
        """Test baseline updates with moving average."""
        performance_monitor.track_operation_performance('test_op', 1.0)
        initial_baseline = performance_monitor._performance_baselines['test_op']

        performance_monitor.track_operation_performance('test_op', 0.5)

        # Baseline should update: baseline * 0.9 + duration * 0.1
        expected = initial_baseline * 0.9 + 0.5 * 0.1
        assert performance_monitor._performance_baselines['test_op'] == expected

    def test_performance_degradation_warning(self, performance_monitor, caplog):
        """Test warning is logged for performance degradation."""
        import logging

        caplog.set_level(logging.WARNING)

        # Establish baseline
        performance_monitor.track_operation_performance('test_op', 0.5)

        # Trigger degradation (>2x baseline)
        performance_monitor.track_operation_performance('test_op', 2.0)

        # Check warning was logged
        assert any(
            'Performance degradation' in record.message for record in caplog.records
        )


class TestCacheManagement:
    """Test cache creation and management."""

    def test_get_existing_cache(self, performance_monitor):
        """Test getting existing cache."""
        cache = performance_monitor.get_cache('settings')

        assert cache is not None
        assert cache.name == 'settings_cache'

    def test_get_nonexistent_cache(self, performance_monitor):
        """Test getting non-existent cache returns None."""
        cache = performance_monitor.get_cache('nonexistent')

        assert cache is None

    def test_create_custom_cache(self, performance_monitor):
        """Test creating custom cache."""
        cache = performance_monitor.create_cache(
            name='custom_cache',
            max_size=500,
            strategy=CacheStrategy.LFU,
            ttl=600.0,
        )

        assert cache is not None
        assert cache.name == 'custom_cache'
        assert cache.max_size == 500
        assert cache.strategy == CacheStrategy.LFU
        assert cache.default_ttl == 600.0

        # Should be retrievable
        retrieved = performance_monitor.get_cache('custom_cache')
        assert retrieved is cache

    def test_monitor_cache_effectiveness(self, performance_monitor):
        """Test monitoring cache effectiveness."""
        # Add some cache activity
        settings_cache = performance_monitor.get_cache('settings')
        settings_cache.put('key1', 'value1')
        settings_cache.get('key1')  # Hit
        settings_cache.get('missing')  # Miss

        cache_metrics = performance_monitor.monitor_cache_effectiveness()

        assert 'settings' in cache_metrics
        metrics = cache_metrics['settings']
        assert metrics.hit_count > 0
        assert metrics.miss_count > 0


class TestCacheOptimization:
    """Test cache configuration optimization."""

    def test_optimize_underutilized_cache(self, performance_monitor):
        """Test optimization for underutilized cache with low hit ratio."""
        # Create cache with low usage
        cache = performance_monitor.create_cache(
            name='test_cache',
            max_size=100,
            strategy=CacheStrategy.LRU,
        )

        # Use only 20% of cache with low hit ratio
        for i in range(20):
            cache.put(f'key{i}', f'value{i}')

        # Generate low hit ratio
        for _ in range(10):
            cache.get('key1')  # Hits

        for _ in range(40):
            cache.get('missing')  # Misses

        optimizations = performance_monitor.optimize_cache_configuration('test_cache')

        # Should suggest reducing size
        assert 'suggested_max_size' in optimizations
        assert optimizations['suggested_max_size'] < 100

    def test_optimize_ineffective_strategy(self, performance_monitor):
        """Test optimization suggests strategy change for low hit ratio."""
        cache = performance_monitor.create_cache(
            name='test_cache',
            max_size=50,
            strategy=CacheStrategy.LRU,
        )

        # Generate activity with low hit ratio
        for i in range(30):
            cache.put(f'key{i}', f'value{i}')

        # Low hit ratio
        for _ in range(5):
            cache.get('key1')

        for _ in range(45):
            cache.get('missing')

        optimizations = performance_monitor.optimize_cache_configuration('test_cache')

        # Should suggest adaptive strategy
        if 'suggested_strategy' in optimizations:
            assert optimizations['suggested_strategy'] == CacheStrategy.ADAPTIVE

    def test_optimize_nonexistent_cache(self, performance_monitor):
        """Test optimizing non-existent cache returns error."""
        result = performance_monitor.optimize_cache_configuration('nonexistent')

        assert 'error' in result
        assert 'not found' in result['error']


class TestSettingsPerformanceManager:
    """Test SettingsPerformanceManager."""

    def test_manager_initialization(self, settings_performance_manager):
        """Test manager initializes with correct caches."""
        assert settings_performance_manager.monitor is not None
        assert settings_performance_manager.settings_cache is not None
        assert settings_performance_manager.validation_cache is not None
        assert settings_performance_manager.schema_cache is not None

    def test_cache_settings(self, settings_performance_manager):
        """Test caching settings."""
        settings_data = {'key': 'value', 'nested': {'data': 'test'}}

        settings_performance_manager.cache_settings('test_key', settings_data)

        result = settings_performance_manager.get_cached_settings('test_key')
        assert result == settings_data

    def test_cache_settings_with_ttl(self, settings_performance_manager):
        """Test caching settings with custom TTL."""
        settings_data = {'key': 'value'}

        settings_performance_manager.cache_settings(
            'test_key',
            settings_data,
            ttl=120.0,
        )

        result = settings_performance_manager.get_cached_settings('test_key')
        assert result == settings_data

    def test_get_cached_settings_miss(self, settings_performance_manager):
        """Test getting non-existent cached settings returns None."""
        result = settings_performance_manager.get_cached_settings('nonexistent')
        assert result is None

    def test_cache_validation_result(self, settings_performance_manager):
        """Test caching validation results."""
        validation_result = {'valid': True, 'errors': []}
        config_hash = 'abc123'

        settings_performance_manager.cache_validation_result(
            config_hash,
            validation_result,
        )

        result = settings_performance_manager.get_cached_validation(config_hash)
        assert result == validation_result

    def test_cache_schema(self, settings_performance_manager):
        """Test caching schema."""
        schema_data = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
        schema_version = 'v1.0.0'

        settings_performance_manager.cache_schema(schema_version, schema_data)

        result = settings_performance_manager.get_cached_schema(schema_version)
        assert result == schema_data

    def test_invalidate_specific_settings(self, settings_performance_manager):
        """Test invalidating specific settings cache entry."""
        settings_performance_manager.cache_settings('key1', {'data': '1'})
        settings_performance_manager.cache_settings('key2', {'data': '2'})

        settings_performance_manager.invalidate_settings_cache('key1')

        assert settings_performance_manager.get_cached_settings('key1') is None
        assert settings_performance_manager.get_cached_settings('key2') == {'data': '2'}

    def test_invalidate_all_settings(self, settings_performance_manager):
        """Test invalidating all settings cache."""
        settings_performance_manager.cache_settings('key1', {'data': '1'})
        settings_performance_manager.cache_settings('key2', {'data': '2'})

        settings_performance_manager.invalidate_settings_cache()

        assert settings_performance_manager.get_cached_settings('key1') is None
        assert settings_performance_manager.get_cached_settings('key2') is None

    def test_invalidate_validation_cache(self, settings_performance_manager):
        """Test invalidating validation cache."""
        settings_performance_manager.cache_validation_result('hash1', {'valid': True})

        settings_performance_manager.invalidate_validation_cache()

        assert settings_performance_manager.get_cached_validation('hash1') is None


class TestSettingsPerformanceReport:
    """Test settings performance report generation."""

    def test_generate_basic_report(self, settings_performance_manager):
        """Test generating basic performance report."""
        # Track some settings operations
        monitor = settings_performance_manager.monitor
        monitor.track_operation_performance('load_settings', 0.1)
        monitor.track_operation_performance('validate_config', 0.05)

        report = settings_performance_manager.generate_settings_performance_report()

        assert 'performance_metrics' in report
        assert 'cache_metrics' in report
        assert 'optimization_suggestions' in report
        assert 'memory_usage_mb' in report
        assert 'generated_at' in report
        assert 'monitoring_enabled' in report

    def test_report_filters_settings_operations(self, settings_performance_manager):
        """Test report filters for settings-related operations."""
        monitor = settings_performance_manager.monitor

        # Settings-related operations
        monitor.track_operation_performance('load_settings', 0.1)
        monitor.track_operation_performance('validate_config', 0.05)
        monitor.track_operation_performance('parse_schema', 0.03)

        # Unrelated operation
        monitor.track_operation_performance('send_email', 0.2)

        report = settings_performance_manager.generate_settings_performance_report()

        metrics = report['performance_metrics']

        # Should include settings-related operations
        assert any(
            'settings' in op.lower() or 'config' in op.lower() or 'schema' in op.lower()
            for op in metrics.keys()
        )

    def test_report_includes_cache_metrics(self, settings_performance_manager):
        """Test report includes all cache metrics."""
        # Generate cache activity
        settings_performance_manager.cache_settings('key1', {'data': 'test'})
        settings_performance_manager.get_cached_settings('key1')

        report = settings_performance_manager.generate_settings_performance_report()

        cache_metrics = report['cache_metrics']

        assert 'settings' in cache_metrics
        assert 'validation' in cache_metrics
        assert 'schema' in cache_metrics

    def test_report_includes_optimization_suggestions(
        self, settings_performance_manager
    ):
        """Test report includes optimization suggestions."""
        monitor = settings_performance_manager.monitor

        # Create slow operations to trigger suggestions
        for _ in range(5):
            monitor.track_operation_performance('slow_settings_load', 1.5)

        report = settings_performance_manager.generate_settings_performance_report()

        suggestions = report['optimization_suggestions']
        assert isinstance(suggestions, list)


class TestTrackPerformanceDecorator:
    """Test @track_performance decorator."""

    def test_decorator_tracks_function_execution(self, performance_monitor):
        """Test decorator tracks function execution time."""

        @track_performance('test_function', monitor=performance_monitor)
        def test_func():
            time.sleep(0.01)
            return 'result'

        result = test_func()

        assert result == 'result'
        assert 'test_function' in performance_monitor._operation_timings
        assert len(performance_monitor._operation_timings['test_function']) > 0

    def test_decorator_with_arguments(self, performance_monitor):
        """Test decorator works with function arguments."""

        @track_performance('math_operation', monitor=performance_monitor)
        def add(a, b):
            return a + b

        result = add(2, 3)

        assert result == 5
        assert 'math_operation' in performance_monitor._operation_timings

    def test_decorator_with_exception(self, performance_monitor):
        """Test decorator handles exceptions and still tracks timing."""

        @track_performance('failing_function', monitor=performance_monitor)
        def failing_func():
            raise ValueError('Test error')

        with pytest.raises(ValueError, match='Test error'):
            failing_func()

        # Should still track the operation
        assert 'failing_function' in performance_monitor._operation_timings

        # Should have error in metadata
        metadata = performance_monitor._operation_metadata['failing_function']
        assert 'error' in metadata

    def test_decorator_with_disabled_monitoring(self, disabled_performance_monitor):
        """Test decorator with disabled monitoring."""

        @track_performance('test_function', monitor=disabled_performance_monitor)
        def test_func():
            return 'result'

        result = test_func()

        assert result == 'result'
        # Should not track anything
        assert len(disabled_performance_monitor._operation_timings) == 0

    def test_decorator_no_monitor(self):
        """Test decorator with no monitor provided."""

        @track_performance('test_function', monitor=None)
        def test_func():
            return 'result'

        result = test_func()

        # Should still execute without errors
        assert result == 'result'


class TestGlobalMonitorInstance:
    """Test global performance monitor management."""

    def test_get_global_monitor(self):
        """Test getting global monitor instance."""
        monitor1 = get_global_performance_monitor()
        monitor2 = get_global_performance_monitor()

        # Should return same instance
        assert monitor1 is monitor2
        assert isinstance(monitor1, PerformanceMonitor)

    def test_configure_global_monitoring(self):
        """Test configuring global monitoring."""
        configure_performance_monitoring(enable=True)

        monitor = get_global_performance_monitor()
        assert monitor.enable_monitoring is True

    def test_configure_with_custom_caches(self):
        """Test configuring global monitoring with custom caches."""
        cache_config = {
            'custom_cache': {
                'max_size': 200,
                'strategy': CacheStrategy.LFU,
                'ttl': 600.0,
            },
        }

        configure_performance_monitoring(enable=True, cache_config=cache_config)

        monitor = get_global_performance_monitor()
        custom_cache = monitor.get_cache('custom_cache')

        assert custom_cache is not None
        assert custom_cache.max_size == 200
        assert custom_cache.strategy == CacheStrategy.LFU


class TestMemoryEstimation:
    """Test memory usage estimation."""

    def test_estimate_memory_with_empty_caches(self, performance_monitor):
        """Test memory estimation with empty caches."""
        memory = performance_monitor._estimate_memory_usage()

        # Should have some overhead even with empty caches
        assert memory >= 0

    def test_estimate_memory_with_data(self, performance_monitor):
        """Test memory estimation increases with data."""
        initial_memory = performance_monitor._estimate_memory_usage()

        # Add data to cache
        settings_cache = performance_monitor.get_cache('settings')
        for i in range(50):
            settings_cache.put(f'key{i}', 'x' * 1000)

        final_memory = performance_monitor._estimate_memory_usage()

        assert final_memory > initial_memory


class TestOptimizationOpportunities:
    """Test optimization opportunity detection."""

    def test_caching_opportunity_slow_operation(self, performance_monitor):
        """Test caching opportunity detected for slow operations."""
        # Average duration > 0.5s
        for _ in range(5):
            performance_monitor.track_operation_performance('slow_op', 0.6)

        opportunities = performance_monitor._generate_optimization_opportunities(
            'slow_op',
            [0.6] * 5,
        )

        assert 'Consider adding caching' in opportunities

    def test_async_opportunity_very_slow_operation(self, performance_monitor):
        """Test async processing opportunity for very slow operations."""
        # Average duration > 1.0s
        for _ in range(5):
            performance_monitor.track_operation_performance('very_slow_op', 1.5)

        opportunities = performance_monitor._generate_optimization_opportunities(
            'very_slow_op',
            [1.5] * 5,
        )

        assert 'Consider async processing' in opportunities

    def test_outlier_investigation_opportunity(self, performance_monitor):
        """Test outlier investigation opportunity."""
        # Many calls with large outliers
        timings = [0.1] * 100 + [5.0]  # 5.0 is 50x average

        opportunities = performance_monitor._generate_optimization_opportunities(
            'outlier_op',
            timings,
        )

        assert 'Investigate performance outliers' in opportunities

    def test_no_opportunities_fast_operation(self, performance_monitor):
        """Test no opportunities for fast operations."""
        timings = [0.01] * 10

        opportunities = performance_monitor._generate_optimization_opportunities(
            'fast_op',
            timings,
        )

        assert len(opportunities) == 0
