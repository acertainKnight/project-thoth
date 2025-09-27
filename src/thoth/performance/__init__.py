"""
Thoth Performance Analysis Framework

This package provides comprehensive performance monitoring, analysis, and optimization
tools for the Thoth research assistant system.

Core Components:
- MetricsCollector: Real-time performance metrics collection
- PipelineAnalyzer: Data pipeline efficiency analysis
- WorkflowMonitor: Research workflow optimization monitoring
- ReliabilityAnalyzer: Error patterns and failure analysis
- OptimizationEngine: Performance recommendations and tuning

The framework integrates with all Thoth services to provide:
- Real-time performance monitoring
- Bottleneck identification
- Resource utilization analysis
- Cost optimization recommendations
- System reliability metrics
"""

from .benchmarking import BenchmarkResults, BenchmarkSuite
from .dashboard import PerformanceDashboard
from .metrics_collector import MetricsCollector, PerformanceMetrics
from .optimization_engine import OptimizationEngine, OptimizationRecommendations
from .pipeline_analyzer import PipelineAnalyzer, PipelineMetrics
from .reliability_analyzer import ReliabilityAnalyzer, ReliabilityMetrics
from .workflow_monitor import WorkflowMetrics, WorkflowMonitor

__all__ = [
    'BenchmarkResults',
    'BenchmarkSuite',
    'MetricsCollector',
    'OptimizationEngine',
    'OptimizationRecommendations',
    'PerformanceDashboard',
    'PerformanceMetrics',
    'PipelineAnalyzer',
    'PipelineMetrics',
    'ReliabilityAnalyzer',
    'ReliabilityMetrics',
    'WorkflowMetrics',
    'WorkflowMonitor',
]
