"""
Performance optimization engine for Thoth system.

This module provides intelligent performance optimization recommendations
and automated tuning strategies based on comprehensive system analysis.
"""

import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from loguru import logger

from thoth.performance.metrics_collector import MetricsCollector
from thoth.performance.pipeline_analyzer import PipelineAnalyzer, PipelineMetrics
from thoth.performance.reliability_analyzer import (
    ReliabilityAnalyzer,
)
from thoth.performance.workflow_monitor import WorkflowMonitor
from thoth.services.service_manager import ServiceManager
from thoth.config import config, Config


class OptimizationPriority(Enum):
    """Priority levels for optimization recommendations."""

    CRITICAL = 'critical'  # System stability at risk
    HIGH = 'high'  # Significant performance impact
    MEDIUM = 'medium'  # Moderate improvement opportunity
    LOW = 'low'  # Nice-to-have optimization


class OptimizationType(Enum):
    """Types of optimizations available."""

    CONFIGURATION = 'configuration'  # Config parameter tuning
    ARCHITECTURE = 'architecture'  # System design changes
    CACHING = 'caching'  # Caching improvements
    PARALLELIZATION = 'parallelization'  # Concurrency improvements
    RESOURCE_ALLOCATION = 'resource_allocation'  # CPU/Memory optimization
    API_OPTIMIZATION = 'api_optimization'  # API usage optimization
    DATABASE_OPTIMIZATION = 'database_optimization'  # DB performance
    ALGORITHMIC = 'algorithmic'  # Algorithm improvements


@dataclass
class OptimizationRecommendation:
    """Individual optimization recommendation."""

    recommendation_id: str
    title: str
    description: str
    priority: OptimizationPriority
    optimization_type: OptimizationType

    # Impact analysis
    expected_improvement: str  # e.g., "30% faster processing"
    confidence_level: float  # 0.0 to 1.0
    implementation_effort: str  # Low, Medium, High

    # Implementation details
    implementation_steps: list[str] = field(default_factory=list)
    code_changes_required: bool = False
    config_changes: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)

    # Validation
    success_metrics: list[str] = field(default_factory=list)
    rollback_plan: str = ''

    # Context
    affected_services: set[str] = field(default_factory=set)
    target_metrics: dict[str, float] = field(default_factory=dict)


@dataclass
class OptimizationRecommendations:
    """Complete set of optimization recommendations."""

    generation_time: datetime
    analysis_period: str
    total_recommendations: int = 0

    # Recommendations by priority
    critical_recommendations: list[OptimizationRecommendation] = field(
        default_factory=list
    )
    high_priority_recommendations: list[OptimizationRecommendation] = field(
        default_factory=list
    )
    medium_priority_recommendations: list[OptimizationRecommendation] = field(
        default_factory=list
    )
    low_priority_recommendations: list[OptimizationRecommendation] = field(
        default_factory=list
    )

    # Summary statistics
    potential_performance_gain: float = 0.0  # Estimated overall improvement
    potential_cost_savings: float = 0.0  # Estimated cost reduction
    implementation_timeline: str = ''  # Estimated timeline

    # Quick wins
    quick_wins: list[OptimizationRecommendation] = field(default_factory=list)


class OptimizationEngine:
    """
    Intelligent performance optimization engine for Thoth system.

    Analyzes system performance across all components and generates
    prioritized, actionable optimization recommendations with:
    - Impact assessment and confidence levels
    - Implementation guidance and effort estimates
    - Success metrics and rollback plans
    - Automated tuning where possible
    """

    def __init__(
        self,
        config: Config,
        service_manager: ServiceManager,
        metrics_collector: MetricsCollector | None = None,
        pipeline_analyzer: PipelineAnalyzer | None = None,
        workflow_monitor: WorkflowMonitor | None = None,
        reliability_analyzer: ReliabilityAnalyzer | None = None,
    ):
        """
        Initialize the optimization engine.

        Args:
            config: Thoth configuration
            service_manager: ServiceManager instance
            metrics_collector: Optional metrics collector
            pipeline_analyzer: Optional pipeline analyzer
            workflow_monitor: Optional workflow monitor
            reliability_analyzer: Optional reliability analyzer
        """
        self.config = config
        self.service_manager = service_manager
        self.metrics_collector = metrics_collector
        self.pipeline_analyzer = pipeline_analyzer
        self.workflow_monitor = workflow_monitor
        self.reliability_analyzer = reliability_analyzer

        # Optimization history and tracking
        self.optimization_history: list[OptimizationRecommendations] = []
        self.applied_optimizations: dict[str, Any] = {}

        # Performance baselines
        self.performance_baselines: dict[str, Any] = {}

        # Storage
        self.optimization_dir = config.workspace_dir / 'optimizations'
        self.optimization_dir.mkdir(exist_ok=True)

        logger.info('OptimizationEngine initialized')

    async def analyze_and_optimize(
        self, time_window_hours: int = 24
    ) -> OptimizationRecommendations:
        """
        Perform comprehensive analysis and generate optimization recommendations.

        Args:
            time_window_hours: Time window for analysis

        Returns:
            OptimizationRecommendations: Complete optimization analysis
        """
        logger.info(
            f'Starting optimization analysis for {time_window_hours} hour window'
        )

        # Collect current system state
        system_analysis = await self._collect_system_analysis(time_window_hours)

        # Generate recommendations
        recommendations = OptimizationRecommendations(
            generation_time=datetime.now(), analysis_period=f'{time_window_hours} hours'
        )

        # Analyze different aspects of the system
        await self._analyze_performance_bottlenecks(system_analysis, recommendations)
        await self._analyze_resource_utilization(system_analysis, recommendations)
        await self._analyze_cost_optimization(system_analysis, recommendations)
        await self._analyze_reliability_improvements(system_analysis, recommendations)
        await self._analyze_workflow_optimizations(system_analysis, recommendations)

        # Prioritize and finalize recommendations
        self._prioritize_recommendations(recommendations)
        self._calculate_impact_estimates(recommendations)
        self._identify_quick_wins(recommendations)

        # Store in history
        self.optimization_history.append(recommendations)

        logger.info(
            f'Generated {recommendations.total_recommendations} optimization recommendations '
            f'({len(recommendations.critical_recommendations)} critical, '
            f'{len(recommendations.high_priority_recommendations)} high priority)'
        )

        return recommendations

    async def _collect_system_analysis(self, time_window_hours: int) -> dict[str, Any]:
        """Collect comprehensive system analysis data."""
        analysis = {'timestamp': datetime.now(), 'time_window_hours': time_window_hours}

        # Metrics collection analysis
        if self.metrics_collector:
            analysis['system_metrics'] = self.metrics_collector.get_summary_stats(
                minutes=time_window_hours * 60
            )

        # Pipeline performance analysis
        if self.pipeline_analyzer:
            pipeline_types = [
                'document_processing',
                'rag_indexing',
                'citation_extraction',
            ]
            analysis['pipeline_metrics'] = {}

            for pipeline_type in pipeline_types:
                try:
                    pipeline_metrics = (
                        self.pipeline_analyzer.analyze_pipeline_performance(
                            pipeline_type, time_window_hours
                        )
                    )
                    analysis['pipeline_metrics'][pipeline_type] = pipeline_metrics
                except Exception as e:
                    logger.warning(f'Failed to analyze {pipeline_type} pipeline: {e}')

        # Workflow analysis
        if self.workflow_monitor:
            try:
                analysis['workflow_metrics'] = (
                    self.workflow_monitor.analyze_workflow_performance(
                        time_window_hours
                    )
                )
            except Exception as e:
                logger.warning(f'Failed to analyze workflow metrics: {e}')

        # Reliability analysis
        if self.reliability_analyzer:
            try:
                analysis['reliability_metrics'] = (
                    self.reliability_analyzer.analyze_reliability(time_window_hours)
                )
            except Exception as e:
                logger.warning(f'Failed to analyze reliability metrics: {e}')

        return analysis

    async def _analyze_performance_bottlenecks(
        self,
        system_analysis: dict[str, Any],
        recommendations: OptimizationRecommendations,
    ) -> None:
        """Analyze performance bottlenecks and generate recommendations."""
        # System resource bottlenecks
        system_metrics = system_analysis.get('system_metrics', {})
        system_perf = system_metrics.get('system_performance', {})

        # CPU utilization analysis
        cpu_avg = system_perf.get('cpu_usage', {}).get('avg', 0)
        cpu_max = system_perf.get('cpu_usage', {}).get('max', 0)

        if cpu_max > 90:
            rec = OptimizationRecommendation(
                recommendation_id='cpu_optimization_001',
                title='High CPU Usage Optimization',
                description=f'System showing high CPU usage (peak: {cpu_max:.1f}%, avg: {cpu_avg:.1f}%)',
                priority=OptimizationPriority.HIGH,
                optimization_type=OptimizationType.RESOURCE_ALLOCATION,
                expected_improvement='20-40% reduction in CPU usage',
                confidence_level=0.8,
                implementation_effort='Medium',
                implementation_steps=[
                    'Review and optimize worker pool configurations',
                    'Implement async processing for I/O-bound operations',
                    'Consider CPU-bound task optimization',
                    'Monitor CPU usage patterns and adjust scaling',
                ],
                config_changes={
                    'performance.auto_scale_workers': True,
                    'performance.content_analysis_workers': min(
                        4, max(2, int(cpu_avg / 20))
                    ),
                    'performance.async_enabled': True,
                },
                success_metrics=['CPU usage < 75%', 'Processing throughput maintained'],
                affected_services={'processing', 'llm', 'citation'},
            )
            recommendations.high_priority_recommendations.append(rec)

        # Memory utilization analysis
        memory_avg = system_perf.get('memory_usage', {}).get('avg', 0)
        memory_max = system_perf.get('memory_usage', {}).get('max', 0)

        if memory_max > 85:
            rec = OptimizationRecommendation(
                recommendation_id='memory_optimization_001',
                title='Memory Usage Optimization',
                description=f'High memory usage detected (peak: {memory_max:.1f}%, avg: {memory_avg:.1f}%)',
                priority=OptimizationPriority.HIGH,
                optimization_type=OptimizationType.RESOURCE_ALLOCATION,
                expected_improvement='25-50% reduction in memory usage',
                confidence_level=0.7,
                implementation_effort='Medium',
                implementation_steps=[
                    'Enable memory optimization in pipelines',
                    'Implement document streaming for large files',
                    'Optimize cache sizes and TTL settings',
                    'Add memory cleanup between processing stages',
                ],
                config_changes={
                    'performance.memory_optimization_enabled': True,
                    'performance.chunk_processing_enabled': True,
                    'performance.max_document_size_mb': 30,
                },
                success_metrics=['Memory usage < 80%', 'No out-of-memory errors'],
                affected_services={'processing', 'rag', 'cache'},
            )
            recommendations.high_priority_recommendations.append(rec)

        # Pipeline bottleneck analysis
        pipeline_metrics = system_analysis.get('pipeline_metrics', {})
        for pipeline_type, metrics in pipeline_metrics.items():
            if hasattr(metrics, 'bottleneck_stages') and metrics.bottleneck_stages:
                for stage in metrics.bottleneck_stages[:2]:  # Top 2 bottlenecks
                    rec = self._create_pipeline_bottleneck_recommendation(
                        pipeline_type, stage, metrics
                    )
                    recommendations.high_priority_recommendations.append(rec)

    def _create_pipeline_bottleneck_recommendation(
        self, pipeline_type: str, bottleneck_stage: str, metrics: PipelineMetrics
    ) -> OptimizationRecommendation:
        """Create recommendation for pipeline bottleneck."""
        stage_performance = metrics.stage_performance.get(bottleneck_stage, {})
        avg_duration = stage_performance.get('avg_duration_ms', 0)

        return OptimizationRecommendation(
            recommendation_id=f'pipeline_{pipeline_type}_{bottleneck_stage}_001',
            title=f'Optimize {bottleneck_stage} in {pipeline_type}',
            description=f'Stage {bottleneck_stage} is a bottleneck (avg: {avg_duration / 1000:.1f}s)',
            priority=OptimizationPriority.HIGH
            if avg_duration > 30000
            else OptimizationPriority.MEDIUM,
            optimization_type=OptimizationType.PARALLELIZATION,
            expected_improvement=f'40-60% faster {bottleneck_stage} processing',
            confidence_level=0.75,
            implementation_effort='Medium',
            implementation_steps=self._generate_stage_optimization_steps(
                bottleneck_stage
            ),
            success_metrics=[
                f'{bottleneck_stage} duration < {avg_duration * 0.6:.0f}ms'
            ],
            affected_services={pipeline_type.split('_')[0]},
        )

    def _generate_stage_optimization_steps(self, stage: str) -> list[str]:
        """Generate optimization steps for specific pipeline stage."""
        steps = []

        if 'ocr' in stage.lower():
            steps.extend(
                [
                    'Implement OCR result caching',
                    'Use batch OCR processing',
                    'Consider faster OCR API or local processing',
                ]
            )
        elif 'analysis' in stage.lower():
            steps.extend(
                [
                    'Cache analysis results for similar content',
                    'Use faster LLM model for initial analysis',
                    'Implement hierarchical analysis approach',
                ]
            )
        elif 'citation' in stage.lower():
            steps.extend(
                [
                    'Implement parallel citation processing',
                    'Cache citation enhancement results',
                    'Optimize citation extraction algorithms',
                ]
            )
        else:
            steps.extend(
                [
                    'Implement parallel processing',
                    'Add result caching',
                    'Optimize algorithms and data structures',
                ]
            )

        return steps

    async def _analyze_resource_utilization(
        self,
        system_analysis: dict[str, Any],
        recommendations: OptimizationRecommendations,
    ) -> None:
        """Analyze resource utilization and generate optimization recommendations."""
        # API usage optimization
        system_metrics = system_analysis.get('system_metrics', {})
        resource_data = system_metrics.get('resource_consumption', {})

        api_costs = resource_data.get('api_costs_usd', {})
        token_usage = resource_data.get('token_usage', {})

        # High API cost optimization
        total_cost = sum(api_costs.values())
        if total_cost > 10.0:  # $10 threshold
            high_cost_apis = [
                (api, cost)
                for api, cost in api_costs.items()
                if cost > total_cost * 0.2
            ]

            for api, cost in high_cost_apis:
                rec = OptimizationRecommendation(
                    recommendation_id=f'api_cost_{api}_001',
                    title=f'Optimize {api} API Usage',
                    description=f'High API cost detected: ${cost:.2f}',
                    priority=OptimizationPriority.MEDIUM,
                    optimization_type=OptimizationType.API_OPTIMIZATION,
                    expected_improvement=f'30-50% reduction in {api} costs',
                    confidence_level=0.8,
                    implementation_effort='Low',
                    implementation_steps=[
                        f'Enable aggressive caching for {api} responses',
                        f'Optimize prompts to reduce {api} token usage',
                        f'Consider using cheaper models for simple {api} tasks',
                        'Implement batch processing where possible',
                    ],
                    success_metrics=[f'{api} cost reduction > 30%'],
                    affected_services={'llm', 'processing'},
                )
                recommendations.medium_priority_recommendations.append(rec)

        # Cache optimization
        if 'cache_hit_rates' in system_metrics:
            cache_rates = system_metrics.get('api_performance', {}).get(
                'cache_hit_rates', {}
            )

            for cache_type, hit_rate in cache_rates.items():
                if hit_rate < 0.6:  # Less than 60% hit rate
                    rec = OptimizationRecommendation(
                        recommendation_id=f'cache_{cache_type}_001',
                        title=f'Improve {cache_type} Cache Performance',
                        description=f'Low cache hit rate: {hit_rate:.1%}',
                        priority=OptimizationPriority.MEDIUM,
                        optimization_type=OptimizationType.CACHING,
                        expected_improvement=f'Increase {cache_type} hit rate to >80%',
                        confidence_level=0.7,
                        implementation_effort='Low',
                        implementation_steps=[
                            f'Increase {cache_type} cache size',
                            f'Optimize {cache_type} cache TTL settings',
                            f'Implement smarter {cache_type} cache key generation',
                            'Review cache eviction policies',
                        ],
                        config_changes={
                            f'cache.{cache_type}_size_limit': 'increased',
                            f'cache.{cache_type}_ttl_hours': 'optimized',
                        },
                        success_metrics=[f'{cache_type} hit rate > 80%'],
                        affected_services={'cache'},
                    )
                    recommendations.medium_priority_recommendations.append(rec)

    async def _analyze_cost_optimization(
        self,
        system_analysis: dict[str, Any],
        recommendations: OptimizationRecommendations,
    ) -> None:
        """Analyze cost optimization opportunities."""
        # Workflow cost analysis
        workflow_metrics = system_analysis.get('workflow_metrics')
        if workflow_metrics and hasattr(workflow_metrics, 'avg_cost_per_workflow'):
            avg_cost = workflow_metrics.avg_cost_per_workflow

            if avg_cost > 1.0:  # $1.00 per workflow threshold
                rec = OptimizationRecommendation(
                    recommendation_id='cost_optimization_001',
                    title='Reduce Per-Workflow Costs',
                    description=f'High average cost per workflow: ${avg_cost:.2f}',
                    priority=OptimizationPriority.MEDIUM,
                    optimization_type=OptimizationType.API_OPTIMIZATION,
                    expected_improvement='40-60% reduction in workflow costs',
                    confidence_level=0.75,
                    implementation_effort='Medium',
                    implementation_steps=[
                        'Implement tiered processing (cheap models first)',
                        'Cache expensive operation results',
                        'Optimize document discovery to reduce processing',
                        'Implement smart content filtering',
                    ],
                    success_metrics=['Average workflow cost < $0.60'],
                    affected_services={'llm', 'discovery', 'processing'},
                )
                recommendations.medium_priority_recommendations.append(rec)

        # Token usage optimization
        system_metrics = system_analysis.get('system_metrics', {})
        resource_data = system_metrics.get('resource_consumption', {})
        token_usage = resource_data.get('token_usage', {})

        total_tokens = sum(token_usage.values())
        if total_tokens > 1000000:  # 1M tokens threshold
            rec = OptimizationRecommendation(
                recommendation_id='token_optimization_001',
                title='Optimize Token Usage',
                description=f'High token usage detected: {total_tokens:,} tokens',
                priority=OptimizationPriority.MEDIUM,
                optimization_type=OptimizationType.ALGORITHMIC,
                expected_improvement='30-50% reduction in token usage',
                confidence_level=0.7,
                implementation_effort='Medium',
                implementation_steps=[
                    'Optimize prompts for conciseness',
                    'Implement content summarization before analysis',
                    'Use smaller models for simple tasks',
                    'Cache analysis results to avoid reprocessing',
                ],
                success_metrics=['Token usage reduction > 30%'],
                affected_services={'llm', 'processing'},
            )
            recommendations.medium_priority_recommendations.append(rec)

    async def _analyze_reliability_improvements(
        self,
        system_analysis: dict[str, Any],
        recommendations: OptimizationRecommendations,
    ) -> None:
        """Analyze reliability improvements."""
        reliability_metrics = system_analysis.get('reliability_metrics')
        if not reliability_metrics:
            return

        # Uptime optimization
        if reliability_metrics.uptime_percentage < 99.5:
            rec = OptimizationRecommendation(
                recommendation_id='uptime_improvement_001',
                title='Improve System Uptime',
                description=f'Uptime below target: {reliability_metrics.uptime_percentage:.2f}%',
                priority=OptimizationPriority.CRITICAL,
                optimization_type=OptimizationType.ARCHITECTURE,
                expected_improvement='Achieve >99.5% uptime',
                confidence_level=0.8,
                implementation_effort='High',
                implementation_steps=[
                    'Implement health checks and monitoring',
                    'Add circuit breaker patterns for external APIs',
                    'Implement graceful degradation mechanisms',
                    'Set up automated recovery procedures',
                ],
                success_metrics=['Uptime > 99.5%', 'MTBF > 48 hours'],
                affected_services={'all'},
            )
            recommendations.critical_recommendations.append(rec)

        # Error rate reduction
        if reliability_metrics.total_errors > 100:  # More than 100 errors in period
            rec = OptimizationRecommendation(
                recommendation_id='error_reduction_001',
                title='Reduce System Error Rate',
                description=f'High error count: {reliability_metrics.total_errors} errors',
                priority=OptimizationPriority.HIGH,
                optimization_type=OptimizationType.ARCHITECTURE,
                expected_improvement='50% reduction in error rate',
                confidence_level=0.7,
                implementation_effort='Medium',
                implementation_steps=[
                    'Implement comprehensive error handling',
                    'Add retry mechanisms with exponential backoff',
                    'Improve input validation and sanitization',
                    'Enhance logging and monitoring',
                ],
                success_metrics=['Error rate reduction > 50%'],
                affected_services={'all'},
            )
            recommendations.high_priority_recommendations.append(rec)

    async def _analyze_workflow_optimizations(
        self,
        system_analysis: dict[str, Any],
        recommendations: OptimizationRecommendations,
    ) -> None:
        """Analyze workflow optimization opportunities."""
        workflow_metrics = system_analysis.get('workflow_metrics')
        if not workflow_metrics:
            return

        # Query success rate optimization
        if workflow_metrics.query_success_rate < 0.8:
            rec = OptimizationRecommendation(
                recommendation_id='query_success_001',
                title='Improve Query Success Rate',
                description=f'Low query success rate: {workflow_metrics.query_success_rate:.1%}',
                priority=OptimizationPriority.HIGH,
                optimization_type=OptimizationType.ALGORITHMIC,
                expected_improvement='Achieve >90% query success rate',
                confidence_level=0.8,
                implementation_effort='High',
                implementation_steps=[
                    'Improve query understanding and parsing',
                    'Enhance document discovery algorithms',
                    'Implement query refinement suggestions',
                    'Add fallback search strategies',
                ],
                success_metrics=['Query success rate > 90%'],
                affected_services={'discovery', 'rag', 'llm'},
            )
            recommendations.high_priority_recommendations.append(rec)

        # User satisfaction optimization
        if (
            hasattr(workflow_metrics, 'user_satisfaction_avg')
            and workflow_metrics.user_satisfaction_avg > 0
            and workflow_metrics.user_satisfaction_avg < 4.0
        ):
            rec = OptimizationRecommendation(
                recommendation_id='user_satisfaction_001',
                title='Improve User Satisfaction',
                description=f'User satisfaction below optimal: {workflow_metrics.user_satisfaction_avg:.1f}/5',
                priority=OptimizationPriority.MEDIUM,
                optimization_type=OptimizationType.WORKFLOW_OPTIMIZATION,
                expected_improvement='Achieve >4.2/5 user satisfaction',
                confidence_level=0.6,
                implementation_effort='Medium',
                implementation_steps=[
                    'Reduce response times for common queries',
                    'Improve result relevance and quality',
                    'Add progress indicators for long operations',
                    'Implement better error messages and guidance',
                ],
                success_metrics=['User satisfaction > 4.2/5'],
                affected_services={'all'},
            )
            recommendations.medium_priority_recommendations.append(rec)

    def _prioritize_recommendations(
        self, recommendations: OptimizationRecommendations
    ) -> None:
        """Prioritize recommendations within each category."""

        # Sort by confidence level and expected impact
        def sort_key(rec: OptimizationRecommendation) -> float:
            impact_score = self._calculate_impact_score(rec)
            return rec.confidence_level * impact_score

        recommendations.critical_recommendations.sort(key=sort_key, reverse=True)
        recommendations.high_priority_recommendations.sort(key=sort_key, reverse=True)
        recommendations.medium_priority_recommendations.sort(key=sort_key, reverse=True)
        recommendations.low_priority_recommendations.sort(key=sort_key, reverse=True)

        # Update total count
        recommendations.total_recommendations = (
            len(recommendations.critical_recommendations)
            + len(recommendations.high_priority_recommendations)
            + len(recommendations.medium_priority_recommendations)
            + len(recommendations.low_priority_recommendations)
        )

    def _calculate_impact_score(
        self, recommendation: OptimizationRecommendation
    ) -> float:
        """Calculate impact score for recommendation prioritization."""
        base_score = 1.0

        # Adjust based on optimization type
        type_scores = {
            OptimizationType.CONFIGURATION: 0.8,
            OptimizationType.CACHING: 1.2,
            OptimizationType.PARALLELIZATION: 1.5,
            OptimizationType.API_OPTIMIZATION: 1.3,
            OptimizationType.RESOURCE_ALLOCATION: 1.4,
            OptimizationType.ARCHITECTURE: 2.0,
            OptimizationType.ALGORITHMIC: 1.8,
            OptimizationType.DATABASE_OPTIMIZATION: 1.6,
        }

        base_score *= type_scores.get(recommendation.optimization_type, 1.0)

        # Adjust based on implementation effort (easier = higher score)
        effort_multipliers = {'Low': 1.5, 'Medium': 1.0, 'High': 0.7}

        base_score *= effort_multipliers.get(recommendation.implementation_effort, 1.0)

        # Adjust based on affected services count
        service_multiplier = min(2.0, len(recommendation.affected_services) * 0.3 + 0.7)
        base_score *= service_multiplier

        return base_score

    def _calculate_impact_estimates(
        self, recommendations: OptimizationRecommendations
    ) -> None:
        """Calculate overall impact estimates."""
        all_recommendations = (
            recommendations.critical_recommendations
            + recommendations.high_priority_recommendations
            + recommendations.medium_priority_recommendations
            + recommendations.low_priority_recommendations
        )

        # Estimate performance gain (conservative calculation)
        performance_improvements = []
        cost_savings = []

        for rec in all_recommendations:
            # Extract percentage improvements from descriptions
            improvement_text = rec.expected_improvement.lower()

            # Performance improvements
            if 'faster' in improvement_text or 'reduction' in improvement_text:
                # Extract percentage if available
                import re

                percentages = re.findall(r'(\d+)[-–](\d+)%', improvement_text)
                if percentages:
                    min_perf, max_perf = map(int, percentages[0])
                    avg_improvement = (min_perf + max_perf) / 2
                    weighted_improvement = avg_improvement * rec.confidence_level
                    performance_improvements.append(weighted_improvement)

            # Cost savings
            if 'cost' in improvement_text and (
                'reduction' in improvement_text or 'saving' in improvement_text
            ):
                percentages = re.findall(r'(\d+)[-–](\d+)%', improvement_text)
                if percentages:
                    min_cost, max_cost = map(int, percentages[0])
                    avg_saving = (min_cost + max_cost) / 2
                    weighted_saving = avg_saving * rec.confidence_level
                    cost_savings.append(weighted_saving)

        if performance_improvements:
            # Conservative estimate: don't just add percentages
            recommendations.potential_performance_gain = min(
                80.0, statistics.mean(performance_improvements)
            )

        if cost_savings:
            recommendations.potential_cost_savings = min(
                70.0, statistics.mean(cost_savings)
            )

        # Implementation timeline estimate
        high_effort_count = sum(
            1 for rec in all_recommendations if rec.implementation_effort == 'High'
        )
        medium_effort_count = sum(
            1 for rec in all_recommendations if rec.implementation_effort == 'Medium'
        )
        low_effort_count = sum(
            1 for rec in all_recommendations if rec.implementation_effort == 'Low'
        )

        if high_effort_count > 3:
            recommendations.implementation_timeline = '3-6 months'
        elif high_effort_count > 0 or medium_effort_count > 5:
            recommendations.implementation_timeline = '6-12 weeks'
        else:
            recommendations.implementation_timeline = '2-6 weeks'

    def _identify_quick_wins(
        self, recommendations: OptimizationRecommendations
    ) -> None:
        """Identify quick win optimizations."""
        all_recommendations = (
            recommendations.high_priority_recommendations
            + recommendations.medium_priority_recommendations
        )

        # Quick wins: High confidence + Low effort + Good impact
        quick_wins = [
            rec
            for rec in all_recommendations
            if (
                rec.confidence_level > 0.7
                and rec.implementation_effort == 'Low'
                and not rec.code_changes_required
            )
        ]

        # Sort by impact score
        quick_wins.sort(key=self._calculate_impact_score, reverse=True)
        recommendations.quick_wins = quick_wins[:5]  # Top 5 quick wins

    async def apply_optimization(self, recommendation_id: str) -> dict[str, Any]:
        """
        Apply an optimization recommendation.

        Args:
            recommendation_id: ID of recommendation to apply

        Returns:
            Dict with application results
        """
        # Find the recommendation
        recommendation = self._find_recommendation(recommendation_id)
        if not recommendation:
            return {'success': False, 'error': 'Recommendation not found'}

        logger.info(f'Applying optimization: {recommendation.title}')

        try:
            result = {'success': True, 'changes_made': []}

            # Apply configuration changes
            if recommendation.config_changes:
                for config_key, config_value in recommendation.config_changes.items():
                    # This would integrate with config management system
                    logger.info(f'Would update config: {config_key} = {config_value}')
                    result['changes_made'].append(
                        f'Config: {config_key} = {config_value}'
                    )

            # Track applied optimization
            self.applied_optimizations[recommendation_id] = {
                'applied_at': datetime.now(),
                'recommendation': recommendation,
                'result': result,
            }

            return result

        except Exception as e:
            logger.error(f'Failed to apply optimization {recommendation_id}: {e}')
            return {'success': False, 'error': str(e)}

    def _find_recommendation(
        self, recommendation_id: str
    ) -> OptimizationRecommendation | None:
        """Find recommendation by ID in history."""
        for rec_set in self.optimization_history:
            all_recs = (
                rec_set.critical_recommendations
                + rec_set.high_priority_recommendations
                + rec_set.medium_priority_recommendations
                + rec_set.low_priority_recommendations
            )
            for rec in all_recs:
                if rec.recommendation_id == recommendation_id:
                    return rec
        return None

    async def save_optimization_data(
        self, recommendations: OptimizationRecommendations
    ) -> None:
        """Save optimization recommendations to disk."""
        try:
            timestamp = recommendations.generation_time.strftime('%Y%m%d_%H%M%S')
            opt_file = self.optimization_dir / f'optimization_report_{timestamp}.json'

            # Convert to serializable format
            report_data = {
                'generation_time': recommendations.generation_time.isoformat(),
                'analysis_period': recommendations.analysis_period,
                'total_recommendations': recommendations.total_recommendations,
                'potential_performance_gain': recommendations.potential_performance_gain,
                'potential_cost_savings': recommendations.potential_cost_savings,
                'implementation_timeline': recommendations.implementation_timeline,
                'recommendations': {
                    'critical': [
                        self._recommendation_to_dict(r)
                        for r in recommendations.critical_recommendations
                    ],
                    'high': [
                        self._recommendation_to_dict(r)
                        for r in recommendations.high_priority_recommendations
                    ],
                    'medium': [
                        self._recommendation_to_dict(r)
                        for r in recommendations.medium_priority_recommendations
                    ],
                    'low': [
                        self._recommendation_to_dict(r)
                        for r in recommendations.low_priority_recommendations
                    ],
                },
                'quick_wins': [
                    self._recommendation_to_dict(r) for r in recommendations.quick_wins
                ],
            }

            with open(opt_file, 'w') as f:
                json.dump(report_data, f, indent=2, default=str)

            logger.info(f'Optimization report saved to {opt_file}')

        except Exception as e:
            logger.error(f'Failed to save optimization report: {e}')

    def _recommendation_to_dict(
        self, recommendation: OptimizationRecommendation
    ) -> dict[str, Any]:
        """Convert recommendation to dictionary for serialization."""
        return {
            'recommendation_id': recommendation.recommendation_id,
            'title': recommendation.title,
            'description': recommendation.description,
            'priority': recommendation.priority.value,
            'optimization_type': recommendation.optimization_type.value,
            'expected_improvement': recommendation.expected_improvement,
            'confidence_level': recommendation.confidence_level,
            'implementation_effort': recommendation.implementation_effort,
            'implementation_steps': recommendation.implementation_steps,
            'config_changes': recommendation.config_changes,
            'success_metrics': recommendation.success_metrics,
            'rollback_plan': recommendation.rollback_plan,
            'affected_services': list(recommendation.affected_services),
            'target_metrics': recommendation.target_metrics,
        }
