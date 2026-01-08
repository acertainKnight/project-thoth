"""
Pipeline efficiency analysis for Thoth data processing workflows.

This module provides comprehensive analysis of data pipeline performance,
bottleneck identification, and optimization recommendations for document
processing, RAG operations, and knowledge graph construction.
"""

import statistics  # noqa: I001
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
from loguru import logger

from thoth.performance.metrics_collector import MetricsCollector
from thoth.services.service_manager import ServiceManager
from thoth.config import config, Config  # noqa: F401


@dataclass
class PipelineStage:
    """Represents a single stage in a processing pipeline."""

    name: str
    duration_ms: float
    input_size: int | None = None
    output_size: int | None = None
    errors: list[str] = field(default_factory=list)
    resource_usage: dict[str, float] = field(default_factory=dict)


@dataclass
class PipelineExecution:
    """Represents a complete pipeline execution."""

    pipeline_id: str
    start_time: datetime
    end_time: datetime | None = None
    stages: list[PipelineStage] = field(default_factory=list)
    total_duration_ms: float = 0.0
    success: bool = True
    error_message: str | None = None
    input_document: str | None = None
    output_artifacts: list[str] = field(default_factory=list)


@dataclass
class PipelineMetrics:
    """Aggregated pipeline performance metrics."""

    pipeline_type: str
    total_executions: int = 0
    successful_executions: int = 0
    failed_executions: int = 0

    # Timing statistics
    avg_duration_ms: float = 0.0
    median_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0

    # Throughput
    documents_per_hour: float = 0.0
    avg_throughput_mb_per_sec: float = 0.0

    # Stage breakdown
    stage_performance: dict[str, dict[str, float]] = field(default_factory=dict)
    bottleneck_stages: list[str] = field(default_factory=list)

    # Error analysis
    error_patterns: dict[str, int] = field(default_factory=dict)
    failure_rate: float = 0.0

    # Resource efficiency
    cpu_efficiency: float = 0.0
    memory_efficiency: float = 0.0
    parallel_efficiency: float = 0.0

    # Cost analysis
    processing_cost_per_doc: float = 0.0
    token_usage_per_doc: float = 0.0


class PipelineAnalyzer:
    """
    Comprehensive pipeline efficiency analyzer for Thoth data processing.

    Analyzes and optimizes:
    - Document processing pipelines (PDF → Markdown → Analysis)
    - RAG indexing and retrieval pipelines
    - Citation extraction and enhancement workflows
    - Agent reasoning and tool execution chains
    - Discovery system performance
    """

    def __init__(
        self,
        config: Config,  # noqa: F811
        service_manager: ServiceManager,
        metrics_collector: MetricsCollector | None = None,
    ):
        """
        Initialize the pipeline analyzer.

        Args:
            config: Thoth configuration
            service_manager: ServiceManager instance
            metrics_collector: Optional metrics collector for real-time data
        """
        self.config = config
        self.service_manager = service_manager
        self.metrics_collector = metrics_collector

        # Pipeline execution tracking
        self.active_executions: dict[str, PipelineExecution] = {}
        self.completed_executions: list[PipelineExecution] = []

        # Performance baselines
        self.baselines: dict[str, PipelineMetrics] = {}

        # Analysis results storage
        self.analysis_dir = config.workspace_dir / 'analysis' / 'pipelines'
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        logger.info('PipelineAnalyzer initialized')

    def start_pipeline_execution(
        self, pipeline_type: str, input_document: str | None = None
    ) -> str:
        """
        Start tracking a new pipeline execution.

        Args:
            pipeline_type: Type of pipeline (e.g., 'document_processing', 'rag_indexing')
            input_document: Optional input document path/identifier

        Returns:
            str: Unique execution ID for tracking
        """  # noqa: W505
        execution_id = f'{pipeline_type}_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}'

        execution = PipelineExecution(
            pipeline_id=execution_id,
            start_time=datetime.now(),
            input_document=input_document,
        )

        self.active_executions[execution_id] = execution

        logger.debug(f'Started pipeline execution: {execution_id}')
        return execution_id

    def add_pipeline_stage(
        self,
        execution_id: str,
        stage_name: str,
        duration_ms: float,
        input_size: int | None = None,
        output_size: int | None = None,
        errors: list[str] | None = None,
        resource_usage: dict[str, float] | None = None,
    ) -> None:
        """
        Add a completed stage to a pipeline execution.

        Args:
            execution_id: Pipeline execution ID
            stage_name: Name of the completed stage
            duration_ms: Stage execution time in milliseconds
            input_size: Optional input data size in bytes
            output_size: Optional output data size in bytes
            errors: Optional list of errors encountered
            resource_usage: Optional resource usage metrics
        """
        if execution_id not in self.active_executions:
            logger.warning(f'Unknown pipeline execution: {execution_id}')
            return

        stage = PipelineStage(
            name=stage_name,
            duration_ms=duration_ms,
            input_size=input_size,
            output_size=output_size,
            errors=errors or [],
            resource_usage=resource_usage or {},
        )

        self.active_executions[execution_id].stages.append(stage)
        logger.debug(f'Added stage {stage_name} to {execution_id}: {duration_ms:.2f}ms')

    def complete_pipeline_execution(
        self,
        execution_id: str,
        success: bool = True,
        error_message: str | None = None,
        output_artifacts: list[str] | None = None,
    ) -> PipelineExecution | None:
        """
        Complete a pipeline execution and move to completed list.

        Args:
            execution_id: Pipeline execution ID
            success: Whether the pipeline completed successfully
            error_message: Optional error message if failed
            output_artifacts: List of output artifact paths

        Returns:
            Optional[PipelineExecution]: The completed execution or None if not found
        """
        if execution_id not in self.active_executions:
            logger.warning(f'Unknown pipeline execution: {execution_id}')
            return None

        execution = self.active_executions.pop(execution_id)
        execution.end_time = datetime.now()
        execution.success = success
        execution.error_message = error_message
        execution.output_artifacts = output_artifacts or []

        # Calculate total duration
        if execution.end_time:
            total_duration = execution.end_time - execution.start_time
            execution.total_duration_ms = total_duration.total_seconds() * 1000

        self.completed_executions.append(execution)
        logger.info(
            f'Completed pipeline execution: {execution_id} ({"success" if success else "failed"})'
        )

        return execution

    def analyze_pipeline_performance(
        self, pipeline_type: str, time_window_hours: int = 24
    ) -> PipelineMetrics:
        """
        Analyze performance for a specific pipeline type.

        Args:
            pipeline_type: Type of pipeline to analyze
            time_window_hours: Time window for analysis in hours

        Returns:
            PipelineMetrics: Comprehensive performance analysis
        """
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

        # Filter executions by type and time window
        relevant_executions = [
            exec
            for exec in self.completed_executions
            if pipeline_type in exec.pipeline_id and exec.start_time > cutoff_time
        ]

        if not relevant_executions:
            logger.warning(
                f'No executions found for {pipeline_type} in the last {time_window_hours} hours'
            )
            return PipelineMetrics(pipeline_type=pipeline_type)

        metrics = self._calculate_pipeline_metrics(pipeline_type, relevant_executions)

        # Store as baseline for comparison
        self.baselines[pipeline_type] = metrics

        logger.info(
            f'Analyzed {len(relevant_executions)} executions for {pipeline_type}'
        )
        return metrics

    def _calculate_pipeline_metrics(
        self, pipeline_type: str, executions: list[PipelineExecution]
    ) -> PipelineMetrics:
        """Calculate comprehensive metrics for a set of pipeline executions."""
        metrics = PipelineMetrics(pipeline_type=pipeline_type)

        # Basic counts
        metrics.total_executions = len(executions)
        successful_executions = [e for e in executions if e.success]
        metrics.successful_executions = len(successful_executions)
        metrics.failed_executions = (
            metrics.total_executions - metrics.successful_executions
        )
        metrics.failure_rate = (
            metrics.failed_executions / metrics.total_executions
            if metrics.total_executions > 0
            else 0
        )

        if not successful_executions:
            return metrics

        # Duration statistics (only for successful executions)
        durations = [e.total_duration_ms for e in successful_executions]
        metrics.avg_duration_ms = statistics.mean(durations)
        metrics.median_duration_ms = statistics.median(durations)
        metrics.min_duration_ms = min(durations)
        metrics.max_duration_ms = max(durations)

        # Calculate percentiles
        durations_sorted = sorted(durations)
        metrics.p95_duration_ms = np.percentile(durations_sorted, 95)

        # Throughput calculations
        total_time_hours = sum(durations) / (1000 * 3600)  # Convert ms to hours
        metrics.documents_per_hour = len(successful_executions) / max(
            total_time_hours, 0.001
        )

        # Stage-level analysis
        metrics.stage_performance = self._analyze_stage_performance(
            successful_executions
        )
        metrics.bottleneck_stages = self._identify_bottleneck_stages(
            metrics.stage_performance
        )

        # Error analysis
        metrics.error_patterns = self._analyze_error_patterns(executions)

        # Resource efficiency analysis
        (
            metrics.cpu_efficiency,
            metrics.memory_efficiency,
            metrics.parallel_efficiency,
        ) = self._analyze_resource_efficiency(successful_executions)

        # Cost analysis (if metrics collector is available)
        if self.metrics_collector:
            metrics.processing_cost_per_doc, metrics.token_usage_per_doc = (
                self._analyze_cost_efficiency(successful_executions)
            )

        return metrics

    def _analyze_stage_performance(
        self, executions: list[PipelineExecution]
    ) -> dict[str, dict[str, float]]:
        """Analyze performance of individual pipeline stages."""
        stage_data: dict[str, list[float]] = {}

        # Collect stage durations
        for execution in executions:
            for stage in execution.stages:
                if stage.name not in stage_data:
                    stage_data[stage.name] = []
                stage_data[stage.name].append(stage.duration_ms)

        # Calculate statistics for each stage
        stage_performance = {}
        for stage_name, durations in stage_data.items():
            stage_performance[stage_name] = {
                'avg_duration_ms': statistics.mean(durations),
                'median_duration_ms': statistics.median(durations),
                'max_duration_ms': max(durations),
                'min_duration_ms': min(durations),
                'std_dev_ms': statistics.stdev(durations) if len(durations) > 1 else 0,
                'execution_count': len(durations),
            }

        return stage_performance

    def _identify_bottleneck_stages(
        self, stage_performance: dict[str, dict[str, float]]
    ) -> list[str]:
        """Identify bottleneck stages based on duration and variability."""
        bottlenecks = []

        if not stage_performance:
            return bottlenecks

        # Calculate relative performance metrics
        all_avg_durations = [
            stats['avg_duration_ms'] for stats in stage_performance.values()
        ]
        avg_threshold = np.percentile(all_avg_durations, 75)  # Top 25% of duration

        # Identify bottlenecks
        for stage_name, stats in stage_performance.items():
            avg_duration = stats['avg_duration_ms']
            std_dev = stats['std_dev_ms']

            # Bottleneck criteria:
            # 1. High average duration (top 25%)
            # 2. High variability (coefficient of variation > 0.5)
            is_slow = avg_duration >= avg_threshold
            is_variable = (std_dev / avg_duration) > 0.5 if avg_duration > 0 else False

            if is_slow or is_variable:
                bottlenecks.append(stage_name)

        return sorted(
            bottlenecks,
            key=lambda stage: stage_performance[stage]['avg_duration_ms'],
            reverse=True,
        )

    def _analyze_error_patterns(
        self, executions: list[PipelineExecution]
    ) -> dict[str, int]:
        """Analyze error patterns across pipeline executions."""
        error_patterns = {}

        for execution in executions:
            if execution.error_message:
                # Simple error categorization
                error_key = self._categorize_error(execution.error_message)
                error_patterns[error_key] = error_patterns.get(error_key, 0) + 1

            # Also analyze stage-level errors
            for stage in execution.stages:
                for error in stage.errors:
                    error_key = f'{stage.name}:{self._categorize_error(error)}'
                    error_patterns[error_key] = error_patterns.get(error_key, 0) + 1

        return error_patterns

    def _categorize_error(self, error_message: str) -> str:
        """Categorize errors into common patterns."""
        error_lower = error_message.lower()

        if 'timeout' in error_lower or 'timed out' in error_lower:
            return 'timeout'
        elif 'connection' in error_lower or 'network' in error_lower:
            return 'network'
        elif 'memory' in error_lower or 'out of memory' in error_lower:
            return 'memory'
        elif 'permission' in error_lower or 'access' in error_lower:
            return 'permissions'
        elif 'api' in error_lower or 'rate limit' in error_lower:
            return 'api_error'
        elif 'parsing' in error_lower or 'format' in error_lower:
            return 'parsing'
        elif 'file not found' in error_lower or 'no such file' in error_lower:
            return 'file_missing'
        else:
            return 'other'

    def _analyze_resource_efficiency(
        self,
        executions: list[PipelineExecution],  # noqa: ARG002
    ) -> tuple[float, float, float]:
        """
        Analyze resource efficiency metrics.

        Returns:
            Tuple of (cpu_efficiency, memory_efficiency, parallel_efficiency)
        """
        # This would require integration with system monitoring
        # For now, return placeholder values
        # TODO: Integrate with MetricsCollector for real resource usage data

        cpu_efficiency = 0.75  # Placeholder
        memory_efficiency = 0.80  # Placeholder
        parallel_efficiency = 0.65  # Placeholder

        return cpu_efficiency, memory_efficiency, parallel_efficiency

    def _analyze_cost_efficiency(
        self, executions: list[PipelineExecution]
    ) -> tuple[float, float]:
        """
        Analyze cost efficiency metrics.

        Returns:
            Tuple of (processing_cost_per_doc, token_usage_per_doc)
        """
        if not self.metrics_collector:
            return 0.0, 0.0

        # Get recent metrics for cost analysis
        summary = self.metrics_collector.get_summary_stats(minutes=60)
        resource_data = summary.get('resource_consumption', {})

        total_cost = sum(resource_data.get('api_costs_usd', {}).values())
        total_tokens = sum(resource_data.get('token_usage', {}).values())
        doc_count = len(executions)

        cost_per_doc = total_cost / max(1, doc_count)
        tokens_per_doc = total_tokens / max(1, doc_count)

        return cost_per_doc, tokens_per_doc

    def identify_optimization_opportunities(self, pipeline_type: str) -> dict[str, Any]:
        """
        Identify specific optimization opportunities for a pipeline.

        Args:
            pipeline_type: Type of pipeline to analyze

        Returns:
            Dict containing optimization recommendations
        """
        if pipeline_type not in self.baselines:
            logger.warning(f'No baseline metrics available for {pipeline_type}')
            return {}

        metrics = self.baselines[pipeline_type]
        opportunities = {
            'bottlenecks': [],
            'parallelization': [],
            'caching': [],
            'resource_optimization': [],
            'cost_optimization': [],
        }

        # Bottleneck identification
        for stage in metrics.bottleneck_stages:
            stage_stats = metrics.stage_performance.get(stage, {})
            avg_duration = stage_stats.get('avg_duration_ms', 0)
            std_dev = stage_stats.get('std_dev_ms', 0)

            opportunity = {
                'stage': stage,
                'avg_duration_ms': avg_duration,
                'variability': std_dev / avg_duration if avg_duration > 0 else 0,
                'recommendations': self._generate_stage_recommendations(
                    stage, stage_stats
                ),
            }
            opportunities['bottlenecks'].append(opportunity)

        # Parallelization opportunities
        if metrics.parallel_efficiency < 0.7:
            opportunities['parallelization'].append(
                {
                    'current_efficiency': metrics.parallel_efficiency,
                    'recommendation': 'Consider increasing worker pool sizes or implementing async processing',
                    'potential_improvement': f'{(0.9 - metrics.parallel_efficiency) * 100:.1f}% faster execution',
                }
            )

        # Caching opportunities
        cache_candidates = self._identify_cache_candidates(pipeline_type)
        opportunities['caching'].extend(cache_candidates)

        # Resource optimization
        if metrics.cpu_efficiency < 0.8 or metrics.memory_efficiency < 0.8:
            opportunities['resource_optimization'].append(
                {
                    'cpu_efficiency': metrics.cpu_efficiency,
                    'memory_efficiency': metrics.memory_efficiency,
                    'recommendations': self._generate_resource_recommendations(metrics),
                }
            )

        # Cost optimization
        if metrics.processing_cost_per_doc > 0.01:  # $0.01 threshold
            opportunities['cost_optimization'].append(
                {
                    'current_cost_per_doc': metrics.processing_cost_per_doc,
                    'token_usage_per_doc': metrics.token_usage_per_doc,
                    'recommendations': self._generate_cost_recommendations(metrics),
                }
            )

        return opportunities

    def _generate_stage_recommendations(
        self, stage_name: str, stage_stats: dict[str, float]
    ) -> list[str]:
        """Generate optimization recommendations for a specific stage."""
        recommendations = []

        avg_duration = stage_stats.get('avg_duration_ms', 0)
        variability = (
            stage_stats.get('std_dev_ms', 0) / avg_duration if avg_duration > 0 else 0
        )

        # Stage-specific recommendations
        if 'ocr' in stage_name.lower():
            if avg_duration > 30000:  # 30 seconds
                recommendations.append(
                    'Consider using faster OCR API or implement local OCR fallback'
                )
            if variability > 0.5:
                recommendations.append(
                    'Implement retry logic with exponential backoff for OCR API calls'
                )

        elif 'llm' in stage_name.lower() or 'analysis' in stage_name.lower():
            if avg_duration > 15000:  # 15 seconds
                recommendations.append(
                    'Consider using faster LLM model or implement prompt optimization'
                )
            recommendations.append(
                'Enable response caching for similar content analysis'
            )

        elif 'citation' in stage_name.lower():
            if avg_duration > 5000:  # 5 seconds
                recommendations.append('Implement parallel citation processing')
            recommendations.append('Cache citation enhancement results')

        elif 'embedding' in stage_name.lower() or 'rag' in stage_name.lower():
            recommendations.append('Batch embedding generation for improved efficiency')
            recommendations.append(
                'Consider using smaller embedding model for faster processing'
            )

        # General recommendations based on performance
        if variability > 0.6:
            recommendations.append(
                'High variability detected - investigate intermittent issues'
            )

        if avg_duration > 60000:  # 1 minute
            recommendations.append(
                'Consider breaking this stage into smaller, parallelizable sub-stages'
            )

        return recommendations

    def _identify_cache_candidates(self, pipeline_type: str) -> list[dict[str, Any]]:
        """Identify stages that would benefit from caching."""
        candidates = []

        # Common cache candidates by pipeline type
        if pipeline_type == 'document_processing':
            candidates.extend(
                [
                    {
                        'stage': 'ocr_processing',
                        'cache_type': 'content-based',
                        'expected_hit_rate': 0.3,
                        'potential_savings': '70% reduction in OCR API calls',
                    },
                    {
                        'stage': 'content_analysis',
                        'cache_type': 'semantic-hash',
                        'expected_hit_rate': 0.2,
                        'potential_savings': '50% reduction in LLM analysis calls',
                    },
                ]
            )

        elif pipeline_type == 'rag_indexing':
            candidates.append(
                {
                    'stage': 'embedding_generation',
                    'cache_type': 'chunk-based',
                    'expected_hit_rate': 0.4,
                    'potential_savings': '60% reduction in embedding API calls',
                }
            )

        return candidates

    def _generate_resource_recommendations(self, metrics: PipelineMetrics) -> list[str]:
        """Generate resource optimization recommendations."""
        recommendations = []

        if metrics.cpu_efficiency < 0.8:
            recommendations.append(
                'Increase worker pool sizes to utilize available CPU cores'
            )
            recommendations.append('Consider using asyncio for I/O-bound operations')

        if metrics.memory_efficiency < 0.8:
            recommendations.append('Implement streaming processing for large documents')
            recommendations.append('Add memory cleanup between processing stages')

        if metrics.parallel_efficiency < 0.7:
            recommendations.append('Review pipeline for serialization bottlenecks')
            recommendations.append(
                'Consider using process-based parallelism for CPU-bound tasks'
            )

        return recommendations

    def _generate_cost_recommendations(self, metrics: PipelineMetrics) -> list[str]:
        """Generate cost optimization recommendations."""
        recommendations = []

        if metrics.processing_cost_per_doc > 0.05:  # $0.05 threshold
            recommendations.append(
                'Consider using cheaper LLM models for initial processing'
            )
            recommendations.append(
                'Implement tiered processing with expensive models only for complex cases'
            )

        if metrics.token_usage_per_doc > 10000:
            recommendations.append('Optimize prompts to reduce token usage')
            recommendations.append(
                'Implement content summarization before LLM processing'
            )

        recommendations.append('Enable aggressive caching to reduce API calls')
        recommendations.append('Consider batch processing to get volume discounts')

        return recommendations

    async def generate_performance_report(
        self, output_path: Path | None = None
    ) -> dict[str, Any]:
        """
        Generate a comprehensive performance report.

        Args:
            output_path: Optional path to save the report

        Returns:
            Dict containing the complete performance report
        """
        report = {
            'generation_time': datetime.now().isoformat(),
            'analysis_period': '24 hours',
            'pipeline_types': list(self.baselines.keys()),
            'pipeline_metrics': {},
            'optimization_opportunities': {},
            'recommendations': {
                'immediate_actions': [],
                'medium_term_improvements': [],
                'long_term_optimizations': [],
            },
        }

        # Generate metrics for each pipeline type
        for pipeline_type in self.baselines.keys():
            metrics = self.analyze_pipeline_performance(pipeline_type)
            report['pipeline_metrics'][pipeline_type] = {
                'total_executions': metrics.total_executions,
                'success_rate': metrics.successful_executions
                / max(1, metrics.total_executions),
                'avg_duration_ms': metrics.avg_duration_ms,
                'p95_duration_ms': metrics.p95_duration_ms,
                'throughput_docs_per_hour': metrics.documents_per_hour,
                'bottleneck_stages': metrics.bottleneck_stages,
                'error_patterns': metrics.error_patterns,
                'cost_per_document': metrics.processing_cost_per_doc,
            }

            # Generate optimization opportunities
            opportunities = self.identify_optimization_opportunities(pipeline_type)
            report['optimization_opportunities'][pipeline_type] = opportunities

        # Generate prioritized recommendations
        report['recommendations'] = self._generate_prioritized_recommendations(
            report['optimization_opportunities']
        )

        # Save report if path provided
        if output_path:
            import json

            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f'Performance report saved to {output_path}')

        return report

    def _generate_prioritized_recommendations(
        self, opportunities: dict[str, Any]
    ) -> dict[str, list[str]]:
        """Generate prioritized recommendations based on impact and effort."""
        recommendations = {
            'immediate_actions': [],
            'medium_term_improvements': [],
            'long_term_optimizations': [],
        }

        # Analyze all opportunities across pipeline types
        all_bottlenecks = []
        for pipeline_ops in opportunities.values():
            all_bottlenecks.extend(pipeline_ops.get('bottlenecks', []))

        # Sort by impact (average duration)
        all_bottlenecks.sort(key=lambda x: x.get('avg_duration_ms', 0), reverse=True)

        # Categorize by effort/impact
        for bottleneck in all_bottlenecks[:3]:  # Top 3 bottlenecks
            stage = bottleneck.get('stage', '')
            duration = bottleneck.get('avg_duration_ms', 0)

            if duration > 30000:  # 30+ seconds - high impact
                recommendations['immediate_actions'].append(
                    f'Optimize {stage} stage (currently {duration / 1000:.1f}s average)'
                )
            elif duration > 10000:  # 10-30 seconds - medium impact
                recommendations['medium_term_improvements'].append(
                    f'Improve {stage} stage performance ({duration / 1000:.1f}s average)'
                )
            else:
                recommendations['long_term_optimizations'].append(
                    f'Fine-tune {stage} stage for consistency'
                )

        # Add caching recommendations
        for pipeline_ops in opportunities.values():
            cache_ops = pipeline_ops.get('caching', [])
            for cache_op in cache_ops:
                if cache_op.get('expected_hit_rate', 0) > 0.3:
                    recommendations['immediate_actions'].append(
                        f'Implement caching for {cache_op.get("stage", "unknown")} '
                        f'({cache_op.get("potential_savings", "significant savings")})'
                    )

        # Add resource optimization
        for pipeline_ops in opportunities.values():
            resource_ops = pipeline_ops.get('resource_optimization', [])
            for resource_op in resource_ops:
                if resource_op.get('cpu_efficiency', 1.0) < 0.7:
                    recommendations['medium_term_improvements'].append(
                        'Implement better CPU utilization through parallelization'
                    )

        return recommendations
