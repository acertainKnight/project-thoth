"""
Research workflow optimization monitoring for Thoth system.

This module provides end-to-end monitoring and optimization of research workflows,
tracking user interactions, query patterns, and research task completion metrics.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from loguru import logger

from thoth.performance.metrics_collector import MetricsCollector
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import ThothConfig


class WorkflowStage(Enum):
    """Stages in a research workflow."""

    QUERY_INITIATION = 'query_initiation'
    DISCOVERY = 'discovery'
    DOCUMENT_RETRIEVAL = 'document_retrieval'
    CONTENT_ANALYSIS = 'content_analysis'
    KNOWLEDGE_SYNTHESIS = 'knowledge_synthesis'
    RESULT_GENERATION = 'result_generation'
    USER_INTERACTION = 'user_interaction'


class WorkflowStatus(Enum):
    """Status of workflow execution."""

    ACTIVE = 'active'
    COMPLETED = 'completed'
    ABANDONED = 'abandoned'
    FAILED = 'failed'


@dataclass
class WorkflowStep:
    """Individual step within a research workflow."""

    step_id: str
    stage: WorkflowStage
    start_time: datetime
    end_time: datetime | None = None
    duration_ms: float | None = None
    success: bool = True
    error_message: str | None = None

    # Step-specific metadata
    input_data: dict[str, Any] = field(default_factory=dict)
    output_data: dict[str, Any] = field(default_factory=dict)
    resources_used: set[str] = field(default_factory=set)  # Services/APIs used

    # Performance metrics
    tokens_consumed: int = 0
    api_calls_made: int = 0
    cache_hits: int = 0
    cache_misses: int = 0


@dataclass
class ResearchWorkflow:
    """Complete research workflow tracking."""

    workflow_id: str
    user_id: str | None
    initial_query: str
    start_time: datetime
    end_time: datetime | None = None
    status: WorkflowStatus = WorkflowStatus.ACTIVE

    # Workflow steps
    steps: list[WorkflowStep] = field(default_factory=list)

    # Results and artifacts
    documents_discovered: list[str] = field(default_factory=list)
    documents_processed: list[str] = field(default_factory=list)
    knowledge_artifacts: list[str] = field(
        default_factory=list
    )  # Notes, summaries, etc.
    final_response: str | None = None

    # Performance metrics
    total_duration_ms: float | None = None
    total_tokens_used: int = 0
    total_api_calls: int = 0
    total_cost_usd: float = 0.0

    # User experience metrics
    user_satisfaction: float | None = None  # 1-5 scale
    query_iterations: int = 1
    abandoned_at_stage: WorkflowStage | None = None


@dataclass
class WorkflowMetrics:
    """Aggregated workflow performance metrics."""

    time_period: str
    total_workflows: int = 0
    completed_workflows: int = 0
    abandoned_workflows: int = 0
    failed_workflows: int = 0

    # Completion rates by stage
    stage_completion_rates: dict[WorkflowStage, float] = field(default_factory=dict)
    stage_avg_durations: dict[WorkflowStage, float] = field(default_factory=dict)

    # Overall performance
    avg_workflow_duration_ms: float = 0.0
    median_workflow_duration_ms: float = 0.0
    avg_documents_per_workflow: float = 0.0
    avg_cost_per_workflow: float = 0.0

    # Efficiency metrics
    query_success_rate: float = 0.0
    document_relevance_rate: float = 0.0
    user_satisfaction_avg: float = 0.0

    # Resource utilization
    most_used_services: list[str] = field(default_factory=list)
    peak_usage_hours: list[int] = field(default_factory=list)
    bottleneck_stages: list[WorkflowStage] = field(default_factory=list)


class WorkflowMonitor:
    """
    Comprehensive research workflow monitoring and optimization system.

    Tracks end-to-end research workflows to identify:
    - User behavior patterns
    - Workflow efficiency bottlenecks
    - Resource utilization optimization opportunities
    - User experience improvements
    """

    def __init__(
        self,
        config: ThothConfig,
        service_manager: ServiceManager,
        metrics_collector: MetricsCollector | None = None,
    ):
        """
        Initialize the workflow monitor.

        Args:
            config: Thoth configuration
            service_manager: ServiceManager instance
            metrics_collector: Optional metrics collector for system metrics
        """
        self.config = config
        self.service_manager = service_manager
        self.metrics_collector = metrics_collector

        # Active workflow tracking
        self.active_workflows: dict[str, ResearchWorkflow] = {}
        self.completed_workflows: list[ResearchWorkflow] = []

        # Workflow patterns and analytics
        self.workflow_patterns: dict[str, Any] = {}
        self.user_behavior_analytics: dict[str, Any] = {}

        # Storage
        self.workflow_dir = config.workspace_dir / 'workflows'
        self.workflow_dir.mkdir(exist_ok=True)

        # Performance baselines
        self.baseline_metrics: dict[str, WorkflowMetrics] = {}

        logger.info('WorkflowMonitor initialized')

    def start_workflow(self, initial_query: str, user_id: str | None = None) -> str:
        """
        Start tracking a new research workflow.

        Args:
            initial_query: User's initial research query
            user_id: Optional user identifier

        Returns:
            str: Unique workflow ID
        """
        workflow_id = f'workflow_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}'

        workflow = ResearchWorkflow(
            workflow_id=workflow_id,
            user_id=user_id,
            initial_query=initial_query,
            start_time=datetime.now(),
        )

        self.active_workflows[workflow_id] = workflow

        logger.info(f'Started workflow tracking: {workflow_id}')
        return workflow_id

    def add_workflow_step(
        self,
        workflow_id: str,
        stage: WorkflowStage,
        input_data: dict[str, Any] | None = None,
        resources_used: set[str] | None = None,
    ) -> str:
        """
        Start a new step in the workflow.

        Args:
            workflow_id: Workflow identifier
            stage: Current workflow stage
            input_data: Input data for this step
            resources_used: Services/APIs being used

        Returns:
            str: Step identifier
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f'Unknown workflow: {workflow_id}')
            return ''

        step_id = f'{workflow_id}_step_{len(self.active_workflows[workflow_id].steps)}'

        step = WorkflowStep(
            step_id=step_id,
            stage=stage,
            start_time=datetime.now(),
            input_data=input_data or {},
            resources_used=resources_used or set(),
        )

        self.active_workflows[workflow_id].steps.append(step)

        logger.debug(f'Added workflow step: {step_id} ({stage.value})')
        return step_id

    def complete_workflow_step(
        self,
        workflow_id: str,
        step_id: str,
        success: bool = True,
        output_data: dict[str, Any] | None = None,
        error_message: str | None = None,
        tokens_consumed: int = 0,
        api_calls_made: int = 0,
        cache_hits: int = 0,
        cache_misses: int = 0,
    ) -> None:
        """
        Complete a workflow step with results and metrics.

        Args:
            workflow_id: Workflow identifier
            step_id: Step identifier
            success: Whether step completed successfully
            output_data: Output data from the step
            error_message: Optional error message if failed
            tokens_consumed: Number of tokens used
            api_calls_made: Number of API calls made
            cache_hits: Number of cache hits
            cache_misses: Number of cache misses
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f'Unknown workflow: {workflow_id}')
            return

        workflow = self.active_workflows[workflow_id]

        # Find the step
        step = None
        for s in workflow.steps:
            if s.step_id == step_id:
                step = s
                break

        if not step:
            logger.warning(f'Unknown step: {step_id}')
            return

        # Complete the step
        step.end_time = datetime.now()
        step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000
        step.success = success
        step.output_data = output_data or {}
        step.error_message = error_message
        step.tokens_consumed = tokens_consumed
        step.api_calls_made = api_calls_made
        step.cache_hits = cache_hits
        step.cache_misses = cache_misses

        # Update workflow totals
        workflow.total_tokens_used += tokens_consumed
        workflow.total_api_calls += api_calls_made

        logger.debug(
            f'Completed workflow step: {step_id} ({"success" if success else "failed"})'
        )

    def complete_workflow(
        self,
        workflow_id: str,
        status: WorkflowStatus = WorkflowStatus.COMPLETED,
        final_response: str | None = None,
        user_satisfaction: float | None = None,
    ) -> ResearchWorkflow | None:
        """
        Complete a research workflow.

        Args:
            workflow_id: Workflow identifier
            status: Final workflow status
            final_response: Final response/result
            user_satisfaction: User satisfaction rating (1-5)

        Returns:
            Optional[ResearchWorkflow]: Completed workflow or None if not found
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f'Unknown workflow: {workflow_id}')
            return None

        workflow = self.active_workflows.pop(workflow_id)
        workflow.end_time = datetime.now()
        workflow.status = status
        workflow.final_response = final_response
        workflow.user_satisfaction = user_satisfaction

        # Calculate total duration
        if workflow.end_time:
            workflow.total_duration_ms = (
                workflow.end_time - workflow.start_time
            ).total_seconds() * 1000

        # Analyze abandonment if applicable
        if status == WorkflowStatus.ABANDONED and workflow.steps:
            last_step = workflow.steps[-1]
            workflow.abandoned_at_stage = last_step.stage

        self.completed_workflows.append(workflow)

        # Update analytics
        self._update_workflow_analytics(workflow)

        logger.info(f'Completed workflow: {workflow_id} ({status.value})')
        return workflow

    def _update_workflow_analytics(self, workflow: ResearchWorkflow) -> None:
        """Update workflow patterns and user behavior analytics."""
        # Update query patterns
        query_key = self._extract_query_pattern(workflow.initial_query)
        if query_key not in self.workflow_patterns:
            self.workflow_patterns[query_key] = {
                'count': 0,
                'avg_duration_ms': 0,
                'success_rate': 0,
                'common_stages': [],
            }

        pattern = self.workflow_patterns[query_key]
        pattern['count'] += 1

        # Update user behavior analytics
        if workflow.user_id:
            if workflow.user_id not in self.user_behavior_analytics:
                self.user_behavior_analytics[workflow.user_id] = {
                    'total_workflows': 0,
                    'avg_satisfaction': 0,
                    'preferred_stages': [],
                    'abandonment_patterns': {},
                }

            user_analytics = self.user_behavior_analytics[workflow.user_id]
            user_analytics['total_workflows'] += 1

            if workflow.user_satisfaction:
                current_avg = user_analytics['avg_satisfaction']
                total_workflows = user_analytics['total_workflows']
                new_avg = (
                    current_avg * (total_workflows - 1) + workflow.user_satisfaction
                ) / total_workflows
                user_analytics['avg_satisfaction'] = new_avg

    def _extract_query_pattern(self, query: str) -> str:
        """Extract pattern from query for analytics."""
        # Simple pattern extraction - could be enhanced with NLP
        query_lower = query.lower()

        if any(word in query_lower for word in ['review', 'survey', 'overview']):
            return 'literature_review'
        elif any(word in query_lower for word in ['methodology', 'method', 'approach']):
            return 'methodology_inquiry'
        elif any(word in query_lower for word in ['comparison', 'compare', 'versus']):
            return 'comparison_analysis'
        elif any(
            word in query_lower for word in ['recent', 'latest', 'new', 'current']
        ):
            return 'current_research'
        elif '?' in query:
            return 'specific_question'
        else:
            return 'general_inquiry'

    def analyze_workflow_performance(
        self, time_window_hours: int = 24, user_id: str | None = None
    ) -> WorkflowMetrics:
        """
        Analyze workflow performance metrics.

        Args:
            time_window_hours: Time window for analysis
            user_id: Optional user ID to filter workflows

        Returns:
            WorkflowMetrics: Performance analysis results
        """
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)

        # Filter workflows
        relevant_workflows = [
            w
            for w in self.completed_workflows
            if w.start_time > cutoff_time and (user_id is None or w.user_id == user_id)
        ]

        metrics = WorkflowMetrics(time_period=f'{time_window_hours} hours')

        if not relevant_workflows:
            return metrics

        # Basic counts
        metrics.total_workflows = len(relevant_workflows)
        metrics.completed_workflows = len(
            [w for w in relevant_workflows if w.status == WorkflowStatus.COMPLETED]
        )
        metrics.abandoned_workflows = len(
            [w for w in relevant_workflows if w.status == WorkflowStatus.ABANDONED]
        )
        metrics.failed_workflows = len(
            [w for w in relevant_workflows if w.status == WorkflowStatus.FAILED]
        )

        # Success rate
        metrics.query_success_rate = (
            metrics.completed_workflows / metrics.total_workflows
        )

        # Duration analysis
        completed_durations = [
            w.total_duration_ms
            for w in relevant_workflows
            if w.total_duration_ms and w.status == WorkflowStatus.COMPLETED
        ]
        if completed_durations:
            metrics.avg_workflow_duration_ms = sum(completed_durations) / len(
                completed_durations
            )
            completed_durations.sort()
            metrics.median_workflow_duration_ms = completed_durations[
                len(completed_durations) // 2
            ]

        # Document analysis
        doc_counts = [
            len(w.documents_processed)
            for w in relevant_workflows
            if w.status == WorkflowStatus.COMPLETED
        ]
        if doc_counts:
            metrics.avg_documents_per_workflow = sum(doc_counts) / len(doc_counts)

        # Cost analysis
        costs = [
            w.total_cost_usd
            for w in relevant_workflows
            if w.status == WorkflowStatus.COMPLETED
        ]
        if costs:
            metrics.avg_cost_per_workflow = sum(costs) / len(costs)

        # User satisfaction
        satisfactions = [
            w.user_satisfaction
            for w in relevant_workflows
            if w.user_satisfaction is not None
        ]
        if satisfactions:
            metrics.user_satisfaction_avg = sum(satisfactions) / len(satisfactions)

        # Stage analysis
        metrics.stage_completion_rates = self._analyze_stage_completion_rates(
            relevant_workflows
        )
        metrics.stage_avg_durations = self._analyze_stage_durations(relevant_workflows)
        metrics.bottleneck_stages = self._identify_workflow_bottlenecks(
            metrics.stage_avg_durations
        )

        # Service utilization
        metrics.most_used_services = self._analyze_service_usage(relevant_workflows)

        # Peak usage analysis
        metrics.peak_usage_hours = self._analyze_peak_usage(relevant_workflows)

        return metrics

    def _analyze_stage_completion_rates(
        self, workflows: list[ResearchWorkflow]
    ) -> dict[WorkflowStage, float]:
        """Analyze completion rates for each workflow stage."""
        stage_attempts = {stage: 0 for stage in WorkflowStage}
        stage_completions = {stage: 0 for stage in WorkflowStage}

        for workflow in workflows:
            stages_reached = set()
            for step in workflow.steps:
                stages_reached.add(step.stage)
                stage_attempts[step.stage] += 1
                if step.success:
                    stage_completions[step.stage] += 1

        completion_rates = {}
        for stage in WorkflowStage:
            if stage_attempts[stage] > 0:
                completion_rates[stage] = (
                    stage_completions[stage] / stage_attempts[stage]
                )
            else:
                completion_rates[stage] = 0.0

        return completion_rates

    def _analyze_stage_durations(
        self, workflows: list[ResearchWorkflow]
    ) -> dict[WorkflowStage, float]:
        """Analyze average durations for each workflow stage."""
        stage_durations = {stage: [] for stage in WorkflowStage}

        for workflow in workflows:
            for step in workflow.steps:
                if step.duration_ms is not None and step.success:
                    stage_durations[step.stage].append(step.duration_ms)

        avg_durations = {}
        for stage, durations in stage_durations.items():
            if durations:
                avg_durations[stage] = sum(durations) / len(durations)
            else:
                avg_durations[stage] = 0.0

        return avg_durations

    def _identify_workflow_bottlenecks(
        self, stage_durations: dict[WorkflowStage, float]
    ) -> list[WorkflowStage]:
        """Identify workflow stages that are bottlenecks."""
        if not stage_durations:
            return []

        # Find stages with above-average duration
        all_durations = [d for d in stage_durations.values() if d > 0]
        if not all_durations:
            return []

        avg_duration = sum(all_durations) / len(all_durations)
        threshold = avg_duration * 1.5  # 50% above average

        bottlenecks = [
            stage for stage, duration in stage_durations.items() if duration > threshold
        ]

        # Sort by duration (descending)
        bottlenecks.sort(key=lambda stage: stage_durations[stage], reverse=True)

        return bottlenecks

    def _analyze_service_usage(self, workflows: list[ResearchWorkflow]) -> list[str]:
        """Analyze most frequently used services."""
        service_usage = {}

        for workflow in workflows:
            for step in workflow.steps:
                for service in step.resources_used:
                    service_usage[service] = service_usage.get(service, 0) + 1

        # Sort by usage count
        sorted_services = sorted(
            service_usage.items(), key=lambda x: x[1], reverse=True
        )
        return [service for service, count in sorted_services[:10]]

    def _analyze_peak_usage(self, workflows: list[ResearchWorkflow]) -> list[int]:
        """Analyze peak usage hours."""
        hourly_usage = {hour: 0 for hour in range(24)}

        for workflow in workflows:
            start_hour = workflow.start_time.hour
            hourly_usage[start_hour] += 1

        # Find top 3 peak hours
        sorted_hours = sorted(hourly_usage.items(), key=lambda x: x[1], reverse=True)
        return [hour for hour, count in sorted_hours[:3]]

    def identify_optimization_opportunities(self) -> dict[str, Any]:
        """Identify workflow optimization opportunities."""
        if not self.completed_workflows:
            return {}

        recent_metrics = self.analyze_workflow_performance()
        opportunities = {
            'workflow_efficiency': [],
            'user_experience': [],
            'resource_optimization': [],
            'stage_improvements': [],
        }

        # Workflow efficiency opportunities
        if recent_metrics.query_success_rate < 0.8:
            opportunities['workflow_efficiency'].append(
                {
                    'issue': 'Low query success rate',
                    'current_rate': recent_metrics.query_success_rate,
                    'recommendation': 'Improve query understanding and document discovery',
                }
            )

        # User experience opportunities
        if (
            recent_metrics.user_satisfaction_avg < 4.0
            and recent_metrics.user_satisfaction_avg > 0
        ):
            opportunities['user_experience'].append(
                {
                    'issue': 'User satisfaction below optimal',
                    'current_satisfaction': recent_metrics.user_satisfaction_avg,
                    'recommendation': 'Focus on result quality and response time improvements',
                }
            )

        if (
            recent_metrics.abandoned_workflows / max(1, recent_metrics.total_workflows)
            > 0.2
        ):
            opportunities['user_experience'].append(
                {
                    'issue': 'High abandonment rate',
                    'abandonment_rate': recent_metrics.abandoned_workflows
                    / recent_metrics.total_workflows,
                    'recommendation': 'Reduce workflow complexity and improve intermediate feedback',
                }
            )

        # Stage improvement opportunities
        for stage in recent_metrics.bottleneck_stages:
            opportunities['stage_improvements'].append(
                {
                    'stage': stage.value,
                    'avg_duration_ms': recent_metrics.stage_avg_durations.get(stage, 0),
                    'recommendations': self._generate_stage_optimization_recommendations(
                        stage
                    ),
                }
            )

        # Resource optimization
        if recent_metrics.avg_cost_per_workflow > 0.50:  # $0.50 threshold
            opportunities['resource_optimization'].append(
                {
                    'issue': 'High cost per workflow',
                    'current_cost': recent_metrics.avg_cost_per_workflow,
                    'recommendation': 'Optimize API usage and implement better caching',
                }
            )

        return opportunities

    def _generate_stage_optimization_recommendations(
        self, stage: WorkflowStage
    ) -> list[str]:
        """Generate optimization recommendations for specific workflow stages."""
        recommendations = []

        if stage == WorkflowStage.DISCOVERY:
            recommendations.extend(
                [
                    'Implement parallel source querying',
                    'Cache discovery results for similar queries',
                    'Optimize query refinement algorithms',
                ]
            )

        elif stage == WorkflowStage.DOCUMENT_RETRIEVAL:
            recommendations.extend(
                [
                    'Implement batch document downloading',
                    'Use CDN for frequently accessed papers',
                    'Optimize PDF parsing and extraction',
                ]
            )

        elif stage == WorkflowStage.CONTENT_ANALYSIS:
            recommendations.extend(
                [
                    'Use faster LLM models for initial analysis',
                    'Implement hierarchical analysis (summary first)',
                    'Cache analysis results for similar content',
                ]
            )

        elif stage == WorkflowStage.KNOWLEDGE_SYNTHESIS:
            recommendations.extend(
                [
                    'Optimize knowledge graph construction',
                    'Use incremental synthesis approaches',
                    'Implement smart relevance filtering',
                ]
            )

        elif stage == WorkflowStage.USER_INTERACTION:
            recommendations.extend(
                [
                    'Reduce response generation latency',
                    'Implement progressive result loading',
                    'Optimize UI/UX for faster interaction',
                ]
            )

        return recommendations

    async def save_workflow_data(self) -> None:
        """Save workflow data to disk for persistence."""
        try:
            # Save completed workflows
            workflow_file = (
                self.workflow_dir
                / f'workflows_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            )

            data = {
                'collection_time': datetime.now().isoformat(),
                'total_workflows': len(self.completed_workflows),
                'workflow_patterns': self.workflow_patterns,
                'user_behavior_analytics': self.user_behavior_analytics,
                'workflows': [
                    self._workflow_to_dict(w) for w in self.completed_workflows[-100:]
                ],  # Save last 100
            }

            with open(workflow_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            logger.info(f'Saved workflow data to {workflow_file}')

        except Exception as e:
            logger.error(f'Failed to save workflow data: {e}')

    def _workflow_to_dict(self, workflow: ResearchWorkflow) -> dict[str, Any]:
        """Convert workflow to dictionary for serialization."""
        return {
            'workflow_id': workflow.workflow_id,
            'user_id': workflow.user_id,
            'initial_query': workflow.initial_query,
            'start_time': workflow.start_time.isoformat(),
            'end_time': workflow.end_time.isoformat() if workflow.end_time else None,
            'status': workflow.status.value,
            'total_duration_ms': workflow.total_duration_ms,
            'total_tokens_used': workflow.total_tokens_used,
            'total_api_calls': workflow.total_api_calls,
            'total_cost_usd': workflow.total_cost_usd,
            'user_satisfaction': workflow.user_satisfaction,
            'query_iterations': workflow.query_iterations,
            'documents_discovered': len(workflow.documents_discovered),
            'documents_processed': len(workflow.documents_processed),
            'knowledge_artifacts': len(workflow.knowledge_artifacts),
            'abandoned_at_stage': workflow.abandoned_at_stage.value
            if workflow.abandoned_at_stage
            else None,
            'steps': [
                {
                    'step_id': step.step_id,
                    'stage': step.stage.value,
                    'duration_ms': step.duration_ms,
                    'success': step.success,
                    'tokens_consumed': step.tokens_consumed,
                    'api_calls_made': step.api_calls_made,
                    'cache_hits': step.cache_hits,
                    'cache_misses': step.cache_misses,
                    'resources_used': list(step.resources_used),
                }
                for step in workflow.steps
            ],
        }
