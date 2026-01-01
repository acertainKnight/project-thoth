"""
Test fixtures for workflow monitoring tests.

Provides reusable test data and factory functions for workflow monitoring components.
"""

from datetime import datetime, timedelta
from typing import Any

from thoth.performance.workflow_monitor import (
    ResearchWorkflow,
    WorkflowStage,
    WorkflowStatus,
    WorkflowStep,
    WorkflowMetrics,
)


def create_workflow_step(
    step_id: str = 'test_step_1',
    stage: WorkflowStage = WorkflowStage.DISCOVERY,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    duration_ms: float | None = None,
    success: bool = True,
    error_message: str | None = None,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    resources_used: set[str] | None = None,
    tokens_consumed: int = 0,
    api_calls_made: int = 0,
    cache_hits: int = 0,
    cache_misses: int = 0,
) -> WorkflowStep:
    """
    Create a workflow step for testing.

    Args:
        step_id: Step identifier
        stage: Workflow stage
        start_time: Step start time (defaults to now)
        end_time: Step end time (optional)
        duration_ms: Step duration in milliseconds (optional)
        success: Whether step succeeded
        error_message: Error message if failed
        input_data: Input data dictionary
        output_data: Output data dictionary
        resources_used: Set of resources used
        tokens_consumed: Number of tokens consumed
        api_calls_made: Number of API calls made
        cache_hits: Number of cache hits
        cache_misses: Number of cache misses

    Returns:
        WorkflowStep: Test workflow step
    """
    if start_time is None:
        start_time = datetime.now()

    return WorkflowStep(
        step_id=step_id,
        stage=stage,
        start_time=start_time,
        end_time=end_time,
        duration_ms=duration_ms,
        success=success,
        error_message=error_message,
        input_data=input_data or {},
        output_data=output_data or {},
        resources_used=resources_used or set(),
        tokens_consumed=tokens_consumed,
        api_calls_made=api_calls_made,
        cache_hits=cache_hits,
        cache_misses=cache_misses,
    )


def create_research_workflow(
    workflow_id: str = 'test_workflow_1',
    user_id: str | None = 'test_user',
    initial_query: str = 'Test research query',
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    status: WorkflowStatus = WorkflowStatus.ACTIVE,
    steps: list[WorkflowStep] | None = None,
    documents_discovered: list[str] | None = None,
    documents_processed: list[str] | None = None,
    knowledge_artifacts: list[str] | None = None,
    final_response: str | None = None,
    total_duration_ms: float | None = None,
    total_tokens_used: int = 0,
    total_api_calls: int = 0,
    total_cost_usd: float = 0.0,
    user_satisfaction: float | None = None,
    query_iterations: int = 1,
    abandoned_at_stage: WorkflowStage | None = None,
) -> ResearchWorkflow:
    """
    Create a research workflow for testing.

    Args:
        workflow_id: Workflow identifier
        user_id: User identifier
        initial_query: Initial research query
        start_time: Workflow start time (defaults to now)
        end_time: Workflow end time (optional)
        status: Workflow status
        steps: List of workflow steps
        documents_discovered: List of discovered documents
        documents_processed: List of processed documents
        knowledge_artifacts: List of knowledge artifacts
        final_response: Final response
        total_duration_ms: Total duration in milliseconds
        total_tokens_used: Total tokens consumed
        total_api_calls: Total API calls made
        total_cost_usd: Total cost in USD
        user_satisfaction: User satisfaction rating (1-5)
        query_iterations: Number of query iterations
        abandoned_at_stage: Stage where workflow was abandoned

    Returns:
        ResearchWorkflow: Test research workflow
    """
    if start_time is None:
        start_time = datetime.now()

    return ResearchWorkflow(
        workflow_id=workflow_id,
        user_id=user_id,
        initial_query=initial_query,
        start_time=start_time,
        end_time=end_time,
        status=status,
        steps=steps or [],
        documents_discovered=documents_discovered or [],
        documents_processed=documents_processed or [],
        knowledge_artifacts=knowledge_artifacts or [],
        final_response=final_response,
        total_duration_ms=total_duration_ms,
        total_tokens_used=total_tokens_used,
        total_api_calls=total_api_calls,
        total_cost_usd=total_cost_usd,
        user_satisfaction=user_satisfaction,
        query_iterations=query_iterations,
        abandoned_at_stage=abandoned_at_stage,
    )


def create_completed_workflow(
    workflow_id: str = 'completed_workflow_1',
    duration_seconds: float = 120.0,
    num_steps: int = 5,
    tokens_per_step: int = 100,
    api_calls_per_step: int = 2,
    user_satisfaction: float = 4.5,
) -> ResearchWorkflow:
    """
    Create a completed workflow with multiple steps.

    Args:
        workflow_id: Workflow identifier
        duration_seconds: Total duration in seconds
        num_steps: Number of steps to create
        tokens_per_step: Tokens consumed per step
        api_calls_per_step: API calls per step
        user_satisfaction: User satisfaction rating

    Returns:
        ResearchWorkflow: Completed workflow with steps
    """
    start_time = datetime.now() - timedelta(seconds=duration_seconds)
    end_time = datetime.now()

    stages = [
        WorkflowStage.QUERY_INITIATION,
        WorkflowStage.DISCOVERY,
        WorkflowStage.DOCUMENT_RETRIEVAL,
        WorkflowStage.CONTENT_ANALYSIS,
        WorkflowStage.KNOWLEDGE_SYNTHESIS,
        WorkflowStage.RESULT_GENERATION,
        WorkflowStage.USER_INTERACTION,
    ]

    steps = []
    step_duration = duration_seconds / num_steps
    step_start = start_time

    for i in range(num_steps):
        step_end = step_start + timedelta(seconds=step_duration)
        stage = stages[i % len(stages)]

        step = create_workflow_step(
            step_id=f'{workflow_id}_step_{i}',
            stage=stage,
            start_time=step_start,
            end_time=step_end,
            duration_ms=step_duration * 1000,
            success=True,
            tokens_consumed=tokens_per_step,
            api_calls_made=api_calls_per_step,
            cache_hits=1,
            cache_misses=1,
            resources_used={'llm_service', 'document_service'},
        )
        steps.append(step)
        step_start = step_end

    return create_research_workflow(
        workflow_id=workflow_id,
        start_time=start_time,
        end_time=end_time,
        status=WorkflowStatus.COMPLETED,
        steps=steps,
        documents_discovered=['doc1', 'doc2', 'doc3'],
        documents_processed=['doc1', 'doc2'],
        knowledge_artifacts=['summary1', 'note1'],
        final_response='Test research results',
        total_duration_ms=duration_seconds * 1000,
        total_tokens_used=tokens_per_step * num_steps,
        total_api_calls=api_calls_per_step * num_steps,
        total_cost_usd=0.05,
        user_satisfaction=user_satisfaction,
    )


def create_abandoned_workflow(
    workflow_id: str = 'abandoned_workflow_1',
    abandoned_at_stage: WorkflowStage = WorkflowStage.DOCUMENT_RETRIEVAL,
    num_steps: int = 3,
) -> ResearchWorkflow:
    """
    Create an abandoned workflow.

    Args:
        workflow_id: Workflow identifier
        abandoned_at_stage: Stage where workflow was abandoned
        num_steps: Number of steps before abandonment

    Returns:
        ResearchWorkflow: Abandoned workflow
    """
    start_time = datetime.now() - timedelta(seconds=60)
    end_time = datetime.now()

    stages = [
        WorkflowStage.QUERY_INITIATION,
        WorkflowStage.DISCOVERY,
        WorkflowStage.DOCUMENT_RETRIEVAL,
    ]

    steps = []
    for i in range(num_steps):
        step = create_workflow_step(
            step_id=f'{workflow_id}_step_{i}',
            stage=stages[i % len(stages)],
            start_time=start_time + timedelta(seconds=i * 20),
            end_time=start_time + timedelta(seconds=(i + 1) * 20),
            duration_ms=20000,
            success=True,
            tokens_consumed=50,
            api_calls_made=1,
        )
        steps.append(step)

    return create_research_workflow(
        workflow_id=workflow_id,
        start_time=start_time,
        end_time=end_time,
        status=WorkflowStatus.ABANDONED,
        steps=steps,
        documents_discovered=['doc1'],
        abandoned_at_stage=abandoned_at_stage,
        total_duration_ms=60000,
    )


def create_failed_workflow(
    workflow_id: str = 'failed_workflow_1',
    failed_at_step: int = 2,
    error_message: str = 'Test error message',
) -> ResearchWorkflow:
    """
    Create a failed workflow.

    Args:
        workflow_id: Workflow identifier
        failed_at_step: Step number where failure occurred
        error_message: Error message

    Returns:
        ResearchWorkflow: Failed workflow
    """
    start_time = datetime.now() - timedelta(seconds=30)
    end_time = datetime.now()

    stages = [
        WorkflowStage.QUERY_INITIATION,
        WorkflowStage.DISCOVERY,
        WorkflowStage.DOCUMENT_RETRIEVAL,
    ]

    steps = []
    for i in range(failed_at_step + 1):
        success = i < failed_at_step
        step_error = None if success else error_message

        step = create_workflow_step(
            step_id=f'{workflow_id}_step_{i}',
            stage=stages[i % len(stages)],
            start_time=start_time + timedelta(seconds=i * 10),
            end_time=start_time + timedelta(seconds=(i + 1) * 10),
            duration_ms=10000,
            success=success,
            error_message=step_error,
            tokens_consumed=50,
            api_calls_made=1,
        )
        steps.append(step)

    return create_research_workflow(
        workflow_id=workflow_id,
        start_time=start_time,
        end_time=end_time,
        status=WorkflowStatus.FAILED,
        steps=steps,
        total_duration_ms=30000,
    )


def create_workflow_metrics(
    time_period: str = '24 hours',
    total_workflows: int = 10,
    completed_workflows: int = 8,
    abandoned_workflows: int = 1,
    failed_workflows: int = 1,
    avg_workflow_duration_ms: float = 120000.0,
    median_workflow_duration_ms: float = 100000.0,
    avg_documents_per_workflow: float = 5.0,
    avg_cost_per_workflow: float = 0.05,
    query_success_rate: float = 0.8,
    document_relevance_rate: float = 0.9,
    user_satisfaction_avg: float = 4.2,
    stage_completion_rates: dict[WorkflowStage, float] | None = None,
    stage_avg_durations: dict[WorkflowStage, float] | None = None,
    most_used_services: list[str] | None = None,
    peak_usage_hours: list[int] | None = None,
    bottleneck_stages: list[WorkflowStage] | None = None,
) -> WorkflowMetrics:
    """
    Create workflow metrics for testing.

    Args:
        time_period: Time period for metrics
        total_workflows: Total number of workflows
        completed_workflows: Number of completed workflows
        abandoned_workflows: Number of abandoned workflows
        failed_workflows: Number of failed workflows
        avg_workflow_duration_ms: Average workflow duration
        median_workflow_duration_ms: Median workflow duration
        avg_documents_per_workflow: Average documents per workflow
        avg_cost_per_workflow: Average cost per workflow
        query_success_rate: Query success rate
        document_relevance_rate: Document relevance rate
        user_satisfaction_avg: Average user satisfaction
        stage_completion_rates: Completion rates by stage
        stage_avg_durations: Average durations by stage
        most_used_services: Most frequently used services
        peak_usage_hours: Peak usage hours
        bottleneck_stages: Bottleneck stages

    Returns:
        WorkflowMetrics: Test workflow metrics
    """
    if stage_completion_rates is None:
        stage_completion_rates = {
            WorkflowStage.QUERY_INITIATION: 0.95,
            WorkflowStage.DISCOVERY: 0.90,
            WorkflowStage.DOCUMENT_RETRIEVAL: 0.85,
            WorkflowStage.CONTENT_ANALYSIS: 0.80,
            WorkflowStage.KNOWLEDGE_SYNTHESIS: 0.75,
            WorkflowStage.RESULT_GENERATION: 0.85,
            WorkflowStage.USER_INTERACTION: 0.90,
        }

    if stage_avg_durations is None:
        stage_avg_durations = {
            WorkflowStage.QUERY_INITIATION: 5000.0,
            WorkflowStage.DISCOVERY: 15000.0,
            WorkflowStage.DOCUMENT_RETRIEVAL: 25000.0,
            WorkflowStage.CONTENT_ANALYSIS: 30000.0,
            WorkflowStage.KNOWLEDGE_SYNTHESIS: 20000.0,
            WorkflowStage.RESULT_GENERATION: 15000.0,
            WorkflowStage.USER_INTERACTION: 10000.0,
        }

    return WorkflowMetrics(
        time_period=time_period,
        total_workflows=total_workflows,
        completed_workflows=completed_workflows,
        abandoned_workflows=abandoned_workflows,
        failed_workflows=failed_workflows,
        stage_completion_rates=stage_completion_rates,
        stage_avg_durations=stage_avg_durations,
        avg_workflow_duration_ms=avg_workflow_duration_ms,
        median_workflow_duration_ms=median_workflow_duration_ms,
        avg_documents_per_workflow=avg_documents_per_workflow,
        avg_cost_per_workflow=avg_cost_per_workflow,
        query_success_rate=query_success_rate,
        document_relevance_rate=document_relevance_rate,
        user_satisfaction_avg=user_satisfaction_avg,
        most_used_services=most_used_services or ['llm_service', 'document_service'],
        peak_usage_hours=peak_usage_hours or [9, 14, 16],
        bottleneck_stages=bottleneck_stages or [WorkflowStage.CONTENT_ANALYSIS],
    )
