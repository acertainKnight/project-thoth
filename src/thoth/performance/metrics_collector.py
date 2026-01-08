"""
Comprehensive performance metrics collection for Thoth system.

This module provides real-time collection and analysis of system performance
metrics across all Thoth services and pipelines.
"""

import asyncio  # noqa: I001
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import psutil
from loguru import logger

from thoth.services.service_manager import ServiceManager
from thoth.config import config, Config  # noqa: F401


@dataclass
class PerformanceMetrics:
    """Container for comprehensive performance metrics."""

    # System metrics
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_usage: float = 0.0
    memory_usage_gb: float = 0.0
    memory_available_gb: float = 0.0
    memory_percent: float = 0.0
    disk_usage_percent: float = 0.0

    # Service response times (milliseconds)
    api_response_times: dict[str, list[float]] = field(default_factory=dict)
    llm_response_times: dict[str, list[float]] = field(default_factory=dict)
    rag_query_times: list[float] = field(default_factory=list)
    cache_hit_rates: dict[str, float] = field(default_factory=dict)

    # Pipeline performance
    pdf_processing_times: list[float] = field(default_factory=list)
    ocr_processing_times: list[float] = field(default_factory=list)
    citation_extraction_times: list[float] = field(default_factory=list)
    content_analysis_times: list[float] = field(default_factory=list)

    # Agent performance
    agent_reasoning_times: list[float] = field(default_factory=list)
    mcp_tool_execution_times: dict[str, list[float]] = field(default_factory=dict)
    memory_operation_times: list[float] = field(default_factory=list)

    # Database performance
    chroma_db_query_times: list[float] = field(default_factory=list)
    chroma_db_insert_times: list[float] = field(default_factory=list)

    # Error rates
    error_rates: dict[str, int] = field(default_factory=dict)
    failure_counts: dict[str, int] = field(default_factory=dict)

    # Throughput metrics
    documents_processed: int = 0
    queries_executed: int = 0
    api_calls_made: dict[str, int] = field(default_factory=dict)

    # Resource consumption
    token_usage: dict[str, int] = field(default_factory=dict)
    api_costs: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary for serialization."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'system': {
                'cpu_usage': self.cpu_usage,
                'memory_usage_gb': self.memory_usage_gb,
                'memory_available_gb': self.memory_available_gb,
                'memory_percent': self.memory_percent,
                'disk_usage_percent': self.disk_usage_percent,
            },
            'api_performance': {
                'response_times': self.api_response_times,
                'llm_response_times': self.llm_response_times,
                'rag_query_times': self.rag_query_times,
                'cache_hit_rates': self.cache_hit_rates,
            },
            'pipeline_performance': {
                'pdf_processing_times': self.pdf_processing_times,
                'ocr_processing_times': self.ocr_processing_times,
                'citation_extraction_times': self.citation_extraction_times,
                'content_analysis_times': self.content_analysis_times,
            },
            'agent_performance': {
                'reasoning_times': self.agent_reasoning_times,
                'tool_execution_times': self.mcp_tool_execution_times,
                'memory_operation_times': self.memory_operation_times,
            },
            'database_performance': {
                'chroma_query_times': self.chroma_db_query_times,
                'chroma_insert_times': self.chroma_db_insert_times,
            },
            'reliability': {
                'error_rates': self.error_rates,
                'failure_counts': self.failure_counts,
            },
            'throughput': {
                'documents_processed': self.documents_processed,
                'queries_executed': self.queries_executed,
                'api_calls_made': self.api_calls_made,
            },
            'resources': {
                'token_usage': self.token_usage,
                'api_costs': self.api_costs,
            },
        }


class MetricsCollector:
    """
    Real-time performance metrics collector for Thoth system.

    Provides comprehensive monitoring of:
    - System resource utilization
    - Service performance metrics
    - Pipeline execution times
    - Error rates and reliability
    - Cost tracking and optimization
    """

    def __init__(
        self,
        config: Config,  # noqa: F811
        service_manager: ServiceManager | None = None,
        collection_interval: int = 10,
        retention_hours: int = 24,
    ):
        """
        Initialize the metrics collector.

        Args:
            config: Thoth configuration
            service_manager: Optional ServiceManager instance
            collection_interval: Metrics collection interval in seconds
            retention_hours: Hours to retain metrics data
        """
        self.config = config
        self.service_manager = service_manager
        self.collection_interval = collection_interval
        self.retention_hours = retention_hours

        # Storage for metrics
        self.current_metrics = PerformanceMetrics()
        self.metrics_history: list[PerformanceMetrics] = []

        # Performance counters
        self._operation_start_times: dict[str, float] = {}
        self._active_operations: dict[str, int] = {}

        # Storage directory
        self.metrics_dir = config.workspace_dir / 'metrics'
        self.metrics_dir.mkdir(exist_ok=True)

        # Collection state
        self._collecting = False
        self._collection_task: asyncio.Task | None = None

        logger.info(
            f'MetricsCollector initialized with {collection_interval}s interval'
        )

    async def start_collection(self) -> None:
        """Start continuous metrics collection."""
        if self._collecting:
            return

        self._collecting = True
        self._collection_task = asyncio.create_task(self._collection_loop())
        logger.info('Started performance metrics collection')

    async def stop_collection(self) -> None:
        """Stop metrics collection and save data."""
        self._collecting = False

        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass

        await self._save_metrics()
        logger.info('Stopped performance metrics collection')

    async def _collection_loop(self) -> None:
        """Main collection loop."""
        while self._collecting:
            try:
                await self._collect_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f'Error collecting metrics: {e}')
                await asyncio.sleep(self.collection_interval)

    async def _collect_metrics(self) -> None:
        """Collect all performance metrics."""
        metrics = PerformanceMetrics()

        # System metrics
        metrics.cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        metrics.memory_usage_gb = (memory.total - memory.available) / (1024**3)
        metrics.memory_available_gb = memory.available / (1024**3)
        metrics.memory_percent = memory.percent

        disk = psutil.disk_usage(str(self.config.workspace_dir))
        metrics.disk_usage_percent = (disk.used / disk.total) * 100

        # Service-specific metrics
        if self.service_manager:
            await self._collect_service_metrics(metrics)

        # Update current metrics and history
        self.current_metrics = metrics
        self.metrics_history.append(metrics)

        # Cleanup old metrics
        self._cleanup_old_metrics()

        # Log summary
        logger.debug(
            f'Metrics: CPU={metrics.cpu_usage:.1f}% '
            f'Memory={metrics.memory_percent:.1f}% '
            f'Disk={metrics.disk_usage_percent:.1f}%'
        )

    async def _collect_service_metrics(self, metrics: PerformanceMetrics) -> None:
        """Collect service-specific performance metrics."""
        try:
            # Cache service metrics
            if hasattr(self.service_manager, 'cache'):
                cache_stats = self.service_manager.cache.get_cache_statistics()
                metrics.cache_hit_rates.update(
                    self._calculate_cache_hit_rates(cache_stats)
                )

            # RAG service metrics
            if hasattr(self.service_manager, 'rag'):
                # Could collect ChromaDB query performance here
                pass

            # LLM service metrics
            if hasattr(self.service_manager, 'llm'):
                # Could collect token usage and costs here
                pass

        except Exception as e:
            logger.warning(f'Failed to collect service metrics: {e}')

    def _calculate_cache_hit_rates(
        self, cache_stats: dict[str, Any]
    ) -> dict[str, float]:
        """Calculate cache hit rates from cache statistics."""
        hit_rates = {}

        for cache_type, stats in cache_stats.get('cache_directories', {}).items():
            # This would need cache hit/miss counters in the cache service
            # For now, estimate based on cache size
            files = stats.get('files', 0)
            if files > 0:
                hit_rates[cache_type] = min(1.0, files / 100.0)  # Simple estimation

        return hit_rates

    def _cleanup_old_metrics(self) -> None:
        """Remove old metrics beyond retention period."""
        cutoff_time = datetime.now() - timedelta(hours=self.retention_hours)
        self.metrics_history = [
            m for m in self.metrics_history if m.timestamp > cutoff_time
        ]

    @contextmanager
    def measure_operation(self, operation_name: str, category: str = 'general'):
        """
        Context manager for measuring operation duration.

        Args:
            operation_name: Name of the operation
            category: Category for grouping (llm, pipeline, api, etc.)
        """
        start_time = time.perf_counter()
        operation_key = f'{category}:{operation_name}'

        # Track active operations
        self._active_operations[operation_key] = (
            self._active_operations.get(operation_key, 0) + 1
        )

        try:
            yield
        finally:
            duration = (
                time.perf_counter() - start_time
            ) * 1000  # Convert to milliseconds

            # Record timing based on category
            if category == 'llm':
                if operation_name not in self.current_metrics.llm_response_times:
                    self.current_metrics.llm_response_times[operation_name] = []
                self.current_metrics.llm_response_times[operation_name].append(duration)

            elif category == 'pipeline':
                if operation_name == 'pdf_processing':
                    self.current_metrics.pdf_processing_times.append(duration)
                elif operation_name == 'ocr_processing':
                    self.current_metrics.ocr_processing_times.append(duration)
                elif operation_name == 'citation_extraction':
                    self.current_metrics.citation_extraction_times.append(duration)
                elif operation_name == 'content_analysis':
                    self.current_metrics.content_analysis_times.append(duration)

            elif category == 'agent':
                if operation_name == 'reasoning':
                    self.current_metrics.agent_reasoning_times.append(duration)
                elif operation_name == 'memory_operation':
                    self.current_metrics.memory_operation_times.append(duration)
                else:  # MCP tools
                    if (
                        operation_name
                        not in self.current_metrics.mcp_tool_execution_times
                    ):
                        self.current_metrics.mcp_tool_execution_times[
                            operation_name
                        ] = []
                    self.current_metrics.mcp_tool_execution_times[
                        operation_name
                    ].append(duration)

            elif category == 'rag':
                if operation_name == 'query':
                    self.current_metrics.rag_query_times.append(duration)

            elif category == 'database':
                if operation_name == 'chroma_query':
                    self.current_metrics.chroma_db_query_times.append(duration)
                elif operation_name == 'chroma_insert':
                    self.current_metrics.chroma_db_insert_times.append(duration)

            elif category == 'api':
                if operation_name not in self.current_metrics.api_response_times:
                    self.current_metrics.api_response_times[operation_name] = []
                self.current_metrics.api_response_times[operation_name].append(duration)

            # Update active operations counter
            self._active_operations[operation_key] -= 1
            if self._active_operations[operation_key] <= 0:
                del self._active_operations[operation_key]

            logger.debug(f'Operation {operation_key} completed in {duration:.2f}ms')

    def record_error(self, service: str, error_type: str) -> None:
        """Record an error occurrence."""
        key = f'{service}:{error_type}'
        self.current_metrics.error_rates[key] = (
            self.current_metrics.error_rates.get(key, 0) + 1
        )
        logger.debug(f'Recorded error: {key}')

    def record_success(self, operation: str) -> None:
        """Record a successful operation."""
        if operation == 'document_processed':
            self.current_metrics.documents_processed += 1
        elif operation == 'query_executed':
            self.current_metrics.queries_executed += 1

    def record_api_call(
        self, api_name: str, tokens_used: int = 0, cost: float = 0.0
    ) -> None:
        """Record API call metrics."""
        self.current_metrics.api_calls_made[api_name] = (
            self.current_metrics.api_calls_made.get(api_name, 0) + 1
        )

        if tokens_used > 0:
            self.current_metrics.token_usage[api_name] = (
                self.current_metrics.token_usage.get(api_name, 0) + tokens_used
            )

        if cost > 0:
            self.current_metrics.api_costs[api_name] = (
                self.current_metrics.api_costs.get(api_name, 0) + cost
            )

    def get_summary_stats(self, minutes: int = 60) -> dict[str, Any]:
        """Get performance summary for the last N minutes."""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        recent_metrics = [m for m in self.metrics_history if m.timestamp > cutoff_time]

        if not recent_metrics:
            return {'error': 'No metrics available for the specified time period'}

        # Calculate aggregated statistics
        summary = {
            'time_period_minutes': minutes,
            'metrics_count': len(recent_metrics),
            'system_performance': self._aggregate_system_metrics(recent_metrics),
            'api_performance': self._aggregate_api_metrics(recent_metrics),
            'pipeline_performance': self._aggregate_pipeline_metrics(recent_metrics),
            'error_summary': self._aggregate_error_metrics(recent_metrics),
            'resource_consumption': self._aggregate_resource_metrics(recent_metrics),
        }

        return summary

    def _aggregate_system_metrics(
        self, metrics: list[PerformanceMetrics]
    ) -> dict[str, Any]:
        """Aggregate system performance metrics."""
        cpu_values = [m.cpu_usage for m in metrics]
        memory_values = [m.memory_percent for m in metrics]
        disk_values = [m.disk_usage_percent for m in metrics]

        return {
            'cpu_usage': {
                'avg': sum(cpu_values) / len(cpu_values),
                'max': max(cpu_values),
                'min': min(cpu_values),
            },
            'memory_usage': {
                'avg': sum(memory_values) / len(memory_values),
                'max': max(memory_values),
                'min': min(memory_values),
            },
            'disk_usage': {
                'avg': sum(disk_values) / len(disk_values),
                'max': max(disk_values),
                'min': min(disk_values),
            },
        }

    def _aggregate_api_metrics(
        self, metrics: list[PerformanceMetrics]
    ) -> dict[str, Any]:
        """Aggregate API performance metrics."""
        all_api_times = []
        for m in metrics:
            for api_name, times in m.api_response_times.items():  # noqa: B007
                all_api_times.extend(times)

        if not all_api_times:
            return {'no_data': True}

        all_api_times.sort()
        n = len(all_api_times)

        return {
            'response_time_ms': {
                'avg': sum(all_api_times) / n,
                'median': all_api_times[n // 2],
                'p95': all_api_times[int(n * 0.95)],
                'p99': all_api_times[int(n * 0.99)],
                'max': max(all_api_times),
                'min': min(all_api_times),
            },
            'total_requests': n,
        }

    def _aggregate_pipeline_metrics(
        self, metrics: list[PerformanceMetrics]
    ) -> dict[str, Any]:
        """Aggregate pipeline performance metrics."""
        pipeline_data = {}

        for metric_name in [
            'pdf_processing_times',
            'ocr_processing_times',
            'citation_extraction_times',
            'content_analysis_times',
        ]:
            all_times = []
            for m in metrics:
                times = getattr(m, metric_name, [])
                all_times.extend(times)

            if all_times:
                all_times.sort()
                n = len(all_times)
                pipeline_data[metric_name.replace('_times', '')] = {
                    'avg_ms': sum(all_times) / n,
                    'median_ms': all_times[n // 2],
                    'p95_ms': all_times[int(n * 0.95)],
                    'max_ms': max(all_times),
                    'min_ms': min(all_times),
                    'operations': n,
                }

        return pipeline_data

    def _aggregate_error_metrics(
        self, metrics: list[PerformanceMetrics]
    ) -> dict[str, Any]:
        """Aggregate error and reliability metrics."""
        total_errors = {}
        total_operations = sum(
            m.documents_processed + m.queries_executed for m in metrics
        )

        for m in metrics:
            for error_key, count in m.error_rates.items():
                total_errors[error_key] = total_errors.get(error_key, 0) + count

        return {
            'total_errors': sum(total_errors.values()),
            'error_breakdown': total_errors,
            'total_operations': total_operations,
            'error_rate': sum(total_errors.values()) / max(1, total_operations),
        }

    def _aggregate_resource_metrics(
        self, metrics: list[PerformanceMetrics]
    ) -> dict[str, Any]:
        """Aggregate resource consumption metrics."""
        total_tokens = {}
        total_costs = {}
        total_api_calls = {}

        for m in metrics:
            for api, tokens in m.token_usage.items():
                total_tokens[api] = total_tokens.get(api, 0) + tokens

            for api, cost in m.api_costs.items():
                total_costs[api] = total_costs.get(api, 0) + cost

            for api, calls in m.api_calls_made.items():
                total_api_calls[api] = total_api_calls.get(api, 0) + calls

        return {
            'token_usage': total_tokens,
            'api_costs_usd': total_costs,
            'api_calls': total_api_calls,
            'total_cost_usd': sum(total_costs.values()),
        }

    async def _save_metrics(self) -> None:
        """Save metrics to disk."""
        try:
            metrics_file = (
                self.metrics_dir
                / f'metrics_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            )

            data = {
                'collection_info': {
                    'start_time': self.metrics_history[0].timestamp.isoformat()
                    if self.metrics_history
                    else None,
                    'end_time': self.current_metrics.timestamp.isoformat(),
                    'total_metrics': len(self.metrics_history),
                    'collection_interval': self.collection_interval,
                },
                'summary': self.get_summary_stats(minutes=60),
                'metrics_history': [
                    m.to_dict() for m in self.metrics_history[-100:]
                ],  # Save last 100 entries
            }

            with open(metrics_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f'Saved metrics to {metrics_file}')

        except Exception as e:
            logger.error(f'Failed to save metrics: {e}')
