"""
Comprehensive tests for workflow monitoring system.

Tests workflow step tracking, research workflow management, metrics aggregation,
and performance analysis.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from thoth.config import Config
from thoth.performance.metrics_collector import MetricsCollector
from thoth.performance.workflow_monitor import (
    ResearchWorkflow,
    WorkflowMetrics,
    WorkflowMonitor,
    WorkflowStage,
    WorkflowStatus,
    WorkflowStep,
)
from thoth.services.service_manager import ServiceManager
from tests.fixtures.workflow_fixtures import (
    create_abandoned_workflow,
    create_completed_workflow,
    create_failed_workflow,
    create_research_workflow,
    create_workflow_metrics,
    create_workflow_step,
)


class TestWorkflowStepDataclass:
    """Tests for WorkflowStep dataclass."""

    def test_workflow_step_initialization_required_fields(self):
        """Test WorkflowStep initialization with required fields only."""
        start_time = datetime(2025, 1, 1, 10, 0, 0)

        step = WorkflowStep(
            step_id='step_1',
            stage=WorkflowStage.DISCOVERY,
            start_time=start_time,
        )

        assert step.step_id == 'step_1'
        assert step.stage == WorkflowStage.DISCOVERY
        assert step.start_time == start_time
        assert step.end_time is None
        assert step.duration_ms is None
        assert step.success is True
        assert step.error_message is None

    def test_workflow_step_initialization_all_fields(self):
        """Test WorkflowStep initialization with all fields."""
        start_time = datetime(2025, 1, 1, 10, 0, 0)
        end_time = datetime(2025, 1, 1, 10, 0, 30)

        step = WorkflowStep(
            step_id='step_1',
            stage=WorkflowStage.CONTENT_ANALYSIS,
            start_time=start_time,
            end_time=end_time,
            duration_ms=30000.0,
            success=False,
            error_message='Analysis failed',
            input_data={'query': 'test'},
            output_data={'result': 'error'},
            resources_used={'llm_service', 'cache'},
            tokens_consumed=500,
            api_calls_made=3,
            cache_hits=2,
            cache_misses=1,
        )

        assert step.step_id == 'step_1'
        assert step.stage == WorkflowStage.CONTENT_ANALYSIS
        assert step.start_time == start_time
        assert step.end_time == end_time
        assert step.duration_ms == 30000.0
        assert step.success is False
        assert step.error_message == 'Analysis failed'
        assert step.input_data == {'query': 'test'}
        assert step.output_data == {'result': 'error'}
        assert step.resources_used == {'llm_service', 'cache'}
        assert step.tokens_consumed == 500
        assert step.api_calls_made == 3
        assert step.cache_hits == 2
        assert step.cache_misses == 1

    def test_workflow_step_default_values(self):
        """Test WorkflowStep default field values."""
        step = WorkflowStep(
            step_id='step_1',
            stage=WorkflowStage.DISCOVERY,
            start_time=datetime.now(),
        )

        assert step.input_data == {}
        assert step.output_data == {}
        assert step.resources_used == set()
        assert step.tokens_consumed == 0
        assert step.api_calls_made == 0
        assert step.cache_hits == 0
        assert step.cache_misses == 0

    def test_workflow_step_metadata_tracking(self):
        """Test WorkflowStep metadata tracking."""
        input_data = {'query': 'machine learning', 'filters': ['year > 2020']}
        output_data = {'documents': ['doc1', 'doc2'], 'count': 2}
        resources = {'semantic_scholar', 'arxiv', 'llm_service'}

        step = WorkflowStep(
            step_id='step_1',
            stage=WorkflowStage.DISCOVERY,
            start_time=datetime.now(),
            input_data=input_data,
            output_data=output_data,
            resources_used=resources,
        )

        assert step.input_data == input_data
        assert step.output_data == output_data
        assert step.resources_used == resources

    def test_workflow_step_performance_metrics(self):
        """Test WorkflowStep performance metrics tracking."""
        step = WorkflowStep(
            step_id='step_1',
            stage=WorkflowStage.CONTENT_ANALYSIS,
            start_time=datetime.now(),
            tokens_consumed=1500,
            api_calls_made=5,
            cache_hits=10,
            cache_misses=3,
        )

        assert step.tokens_consumed == 1500
        assert step.api_calls_made == 5
        assert step.cache_hits == 10
        assert step.cache_misses == 3

    def test_workflow_step_error_handling(self):
        """Test WorkflowStep error tracking."""
        step = WorkflowStep(
            step_id='step_1',
            stage=WorkflowStage.DOCUMENT_RETRIEVAL,
            start_time=datetime.now(),
            success=False,
            error_message='Failed to retrieve document: connection timeout',
        )

        assert step.success is False
        assert 'connection timeout' in step.error_message


class TestResearchWorkflowDataclass:
    """Tests for ResearchWorkflow dataclass."""

    def test_research_workflow_initialization_required_fields(self):
        """Test ResearchWorkflow initialization with required fields."""
        start_time = datetime(2025, 1, 1, 10, 0, 0)

        workflow = ResearchWorkflow(
            workflow_id='wf_1',
            user_id='user_123',
            initial_query='deep learning overview',
            start_time=start_time,
        )

        assert workflow.workflow_id == 'wf_1'
        assert workflow.user_id == 'user_123'
        assert workflow.initial_query == 'deep learning overview'
        assert workflow.start_time == start_time
        assert workflow.end_time is None
        assert workflow.status == WorkflowStatus.ACTIVE

    def test_research_workflow_lifecycle_active_to_completed(self):
        """Test workflow lifecycle: ACTIVE → COMPLETED."""
        workflow = create_research_workflow(status=WorkflowStatus.ACTIVE)

        assert workflow.status == WorkflowStatus.ACTIVE

        # Simulate completion
        workflow.status = WorkflowStatus.COMPLETED
        workflow.end_time = datetime.now()

        assert workflow.status == WorkflowStatus.COMPLETED
        assert workflow.end_time is not None

    def test_research_workflow_lifecycle_active_to_abandoned(self):
        """Test workflow lifecycle: ACTIVE → ABANDONED."""
        workflow = create_research_workflow(status=WorkflowStatus.ACTIVE)
        workflow.status = WorkflowStatus.ABANDONED
        workflow.abandoned_at_stage = WorkflowStage.DOCUMENT_RETRIEVAL

        assert workflow.status == WorkflowStatus.ABANDONED
        assert workflow.abandoned_at_stage == WorkflowStage.DOCUMENT_RETRIEVAL

    def test_research_workflow_lifecycle_active_to_failed(self):
        """Test workflow lifecycle: ACTIVE → FAILED."""
        workflow = create_research_workflow(status=WorkflowStatus.ACTIVE)
        workflow.status = WorkflowStatus.FAILED
        workflow.end_time = datetime.now()

        assert workflow.status == WorkflowStatus.FAILED
        assert workflow.end_time is not None

    def test_research_workflow_steps_collection(self):
        """Test workflow steps collection management."""
        workflow = create_research_workflow()

        step1 = create_workflow_step(
            step_id='step_1', stage=WorkflowStage.QUERY_INITIATION
        )
        step2 = create_workflow_step(step_id='step_2', stage=WorkflowStage.DISCOVERY)
        step3 = create_workflow_step(
            step_id='step_3', stage=WorkflowStage.DOCUMENT_RETRIEVAL
        )

        workflow.steps.extend([step1, step2, step3])

        assert len(workflow.steps) == 3
        assert workflow.steps[0].stage == WorkflowStage.QUERY_INITIATION
        assert workflow.steps[1].stage == WorkflowStage.DISCOVERY
        assert workflow.steps[2].stage == WorkflowStage.DOCUMENT_RETRIEVAL

    def test_research_workflow_documents_tracking(self):
        """Test workflow documents tracking."""
        workflow = create_research_workflow()

        workflow.documents_discovered = ['doc1', 'doc2', 'doc3', 'doc4']
        workflow.documents_processed = ['doc1', 'doc2', 'doc3']

        assert len(workflow.documents_discovered) == 4
        assert len(workflow.documents_processed) == 3
        assert set(workflow.documents_processed).issubset(
            set(workflow.documents_discovered)
        )

    def test_research_workflow_knowledge_artifacts(self):
        """Test workflow knowledge artifacts tracking."""
        workflow = create_research_workflow()

        workflow.knowledge_artifacts = ['summary_1', 'note_1', 'graph_1']

        assert len(workflow.knowledge_artifacts) == 3
        assert 'summary_1' in workflow.knowledge_artifacts

    def test_research_workflow_total_metrics_calculation(self):
        """Test workflow total metrics calculation."""
        workflow = create_completed_workflow(
            duration_seconds=120,
            num_steps=5,
            tokens_per_step=100,
            api_calls_per_step=2,
        )

        assert workflow.total_tokens_used == 500
        assert workflow.total_api_calls == 10
        assert workflow.total_duration_ms == 120000.0

    def test_research_workflow_user_experience_metrics(self):
        """Test workflow user experience metrics."""
        workflow = create_research_workflow(
            user_satisfaction=4.5, query_iterations=3
        )

        assert workflow.user_satisfaction == 4.5
        assert workflow.query_iterations == 3

    def test_research_workflow_default_values(self):
        """Test ResearchWorkflow default field values."""
        workflow = ResearchWorkflow(
            workflow_id='wf_1',
            user_id='user_123',
            initial_query='test query',
            start_time=datetime.now(),
        )

        assert workflow.steps == []
        assert workflow.documents_discovered == []
        assert workflow.documents_processed == []
        assert workflow.knowledge_artifacts == []
        assert workflow.final_response is None
        assert workflow.total_duration_ms is None
        assert workflow.total_tokens_used == 0
        assert workflow.total_api_calls == 0
        assert workflow.total_cost_usd == 0.0
        assert workflow.user_satisfaction is None
        assert workflow.query_iterations == 1
        assert workflow.abandoned_at_stage is None


class TestWorkflowEnums:
    """Tests for WorkflowStage and WorkflowStatus enums."""

    def test_workflow_stage_enum_values(self):
        """Test all WorkflowStage enum values."""
        stages = list(WorkflowStage)

        assert WorkflowStage.QUERY_INITIATION in stages
        assert WorkflowStage.DISCOVERY in stages
        assert WorkflowStage.DOCUMENT_RETRIEVAL in stages
        assert WorkflowStage.CONTENT_ANALYSIS in stages
        assert WorkflowStage.KNOWLEDGE_SYNTHESIS in stages
        assert WorkflowStage.RESULT_GENERATION in stages
        assert WorkflowStage.USER_INTERACTION in stages

    def test_workflow_stage_string_representation(self):
        """Test WorkflowStage string representation."""
        assert WorkflowStage.QUERY_INITIATION.value == 'query_initiation'
        assert WorkflowStage.DISCOVERY.value == 'discovery'
        assert WorkflowStage.DOCUMENT_RETRIEVAL.value == 'document_retrieval'
        assert WorkflowStage.CONTENT_ANALYSIS.value == 'content_analysis'
        assert WorkflowStage.KNOWLEDGE_SYNTHESIS.value == 'knowledge_synthesis'
        assert WorkflowStage.RESULT_GENERATION.value == 'result_generation'
        assert WorkflowStage.USER_INTERACTION.value == 'user_interaction'

    def test_workflow_status_enum_values(self):
        """Test all WorkflowStatus enum values."""
        statuses = list(WorkflowStatus)

        assert WorkflowStatus.ACTIVE in statuses
        assert WorkflowStatus.COMPLETED in statuses
        assert WorkflowStatus.ABANDONED in statuses
        assert WorkflowStatus.FAILED in statuses

    def test_workflow_status_string_representation(self):
        """Test WorkflowStatus string representation."""
        assert WorkflowStatus.ACTIVE.value == 'active'
        assert WorkflowStatus.COMPLETED.value == 'completed'
        assert WorkflowStatus.ABANDONED.value == 'abandoned'
        assert WorkflowStatus.FAILED.value == 'failed'


class TestWorkflowMonitorInitialization:
    """Tests for WorkflowMonitor initialization."""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock configuration."""
        config = Mock(spec=Config)
        config.workspace_dir = tmp_path / 'workspace'
        config.workspace_dir.mkdir(exist_ok=True)
        return config

    @pytest.fixture
    def mock_service_manager(self):
        """Create mock service manager."""
        return Mock(spec=ServiceManager)

    @pytest.fixture
    def mock_metrics_collector(self):
        """Create mock metrics collector."""
        return Mock(spec=MetricsCollector)

    def test_workflow_monitor_initialization(
        self, mock_config, mock_service_manager
    ):
        """Test WorkflowMonitor initialization."""
        monitor = WorkflowMonitor(
            config=mock_config, service_manager=mock_service_manager
        )

        assert monitor.config == mock_config
        assert monitor.service_manager == mock_service_manager
        assert monitor.active_workflows == {}
        assert monitor.completed_workflows == []
        assert monitor.workflow_patterns == {}
        assert monitor.user_behavior_analytics == {}

    def test_workflow_monitor_creates_workflow_directory(
        self, mock_config, mock_service_manager
    ):
        """Test WorkflowMonitor creates workflow directory."""
        monitor = WorkflowMonitor(
            config=mock_config, service_manager=mock_service_manager
        )

        assert monitor.workflow_dir.exists()
        assert monitor.workflow_dir.is_dir()

    def test_workflow_monitor_with_metrics_collector(
        self, mock_config, mock_service_manager, mock_metrics_collector
    ):
        """Test WorkflowMonitor initialization with metrics collector."""
        monitor = WorkflowMonitor(
            config=mock_config,
            service_manager=mock_service_manager,
            metrics_collector=mock_metrics_collector,
        )

        assert monitor.metrics_collector == mock_metrics_collector


class TestWorkflowCreation:
    """Tests for workflow creation and management."""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create WorkflowMonitor instance."""
        config = Mock(spec=Config)
        config.workspace_dir = tmp_path / 'workspace'
        config.workspace_dir.mkdir(exist_ok=True)

        service_manager = Mock(spec=ServiceManager)

        return WorkflowMonitor(config=config, service_manager=service_manager)

    def test_start_workflow(self, monitor):
        """Test starting a new workflow."""
        workflow_id = monitor.start_workflow(
            initial_query='deep learning overview', user_id='user_123'
        )

        assert workflow_id.startswith('workflow_')
        assert workflow_id in monitor.active_workflows

        workflow = monitor.active_workflows[workflow_id]
        assert workflow.initial_query == 'deep learning overview'
        assert workflow.user_id == 'user_123'
        assert workflow.status == WorkflowStatus.ACTIVE

    def test_start_workflow_without_user_id(self, monitor):
        """Test starting workflow without user ID."""
        workflow_id = monitor.start_workflow(initial_query='test query')

        workflow = monitor.active_workflows[workflow_id]
        assert workflow.user_id is None

    def test_start_multiple_workflows(self, monitor):
        """Test starting multiple workflows."""
        workflow_id1 = monitor.start_workflow(initial_query='query 1')
        workflow_id2 = monitor.start_workflow(initial_query='query 2')
        workflow_id3 = monitor.start_workflow(initial_query='query 3')

        assert len(monitor.active_workflows) == 3
        assert workflow_id1 != workflow_id2
        assert workflow_id2 != workflow_id3


class TestWorkflowStepManagement:
    """Tests for workflow step management."""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create WorkflowMonitor instance with active workflow."""
        config = Mock(spec=Config)
        config.workspace_dir = tmp_path / 'workspace'
        config.workspace_dir.mkdir(exist_ok=True)

        service_manager = Mock(spec=ServiceManager)

        monitor = WorkflowMonitor(config=config, service_manager=service_manager)
        monitor.workflow_id = monitor.start_workflow(
            initial_query='test query', user_id='user_123'
        )

        return monitor

    def test_add_workflow_step(self, monitor):
        """Test adding a workflow step."""
        step_id = monitor.add_workflow_step(
            workflow_id=monitor.workflow_id,
            stage=WorkflowStage.DISCOVERY,
            input_data={'query': 'machine learning'},
            resources_used={'semantic_scholar'},
        )

        assert step_id != ''
        workflow = monitor.active_workflows[monitor.workflow_id]
        assert len(workflow.steps) == 1

        step = workflow.steps[0]
        assert step.stage == WorkflowStage.DISCOVERY
        assert step.input_data == {'query': 'machine learning'}
        assert step.resources_used == {'semantic_scholar'}

    def test_add_workflow_step_unknown_workflow(self, monitor):
        """Test adding step to unknown workflow."""
        step_id = monitor.add_workflow_step(
            workflow_id='unknown_workflow', stage=WorkflowStage.DISCOVERY
        )

        assert step_id == ''

    def test_add_multiple_workflow_steps(self, monitor):
        """Test adding multiple workflow steps."""
        step_id1 = monitor.add_workflow_step(
            workflow_id=monitor.workflow_id, stage=WorkflowStage.QUERY_INITIATION
        )
        step_id2 = monitor.add_workflow_step(
            workflow_id=monitor.workflow_id, stage=WorkflowStage.DISCOVERY
        )
        step_id3 = monitor.add_workflow_step(
            workflow_id=monitor.workflow_id, stage=WorkflowStage.DOCUMENT_RETRIEVAL
        )

        workflow = monitor.active_workflows[monitor.workflow_id]
        assert len(workflow.steps) == 3
        assert step_id1 != step_id2
        assert step_id2 != step_id3

    def test_complete_workflow_step(self, monitor):
        """Test completing a workflow step."""
        step_id = monitor.add_workflow_step(
            workflow_id=monitor.workflow_id, stage=WorkflowStage.CONTENT_ANALYSIS
        )

        monitor.complete_workflow_step(
            workflow_id=monitor.workflow_id,
            step_id=step_id,
            success=True,
            output_data={'result': 'analysis complete'},
            tokens_consumed=500,
            api_calls_made=2,
            cache_hits=5,
            cache_misses=1,
        )

        workflow = monitor.active_workflows[monitor.workflow_id]
        step = workflow.steps[0]

        assert step.end_time is not None
        assert step.duration_ms is not None
        assert step.duration_ms > 0
        assert step.success is True
        assert step.output_data == {'result': 'analysis complete'}
        assert step.tokens_consumed == 500
        assert step.api_calls_made == 2
        assert step.cache_hits == 5
        assert step.cache_misses == 1

    def test_complete_workflow_step_with_error(self, monitor):
        """Test completing a workflow step with error."""
        step_id = monitor.add_workflow_step(
            workflow_id=monitor.workflow_id, stage=WorkflowStage.DOCUMENT_RETRIEVAL
        )

        error_message = 'Failed to retrieve document'
        monitor.complete_workflow_step(
            workflow_id=monitor.workflow_id,
            step_id=step_id,
            success=False,
            error_message=error_message,
        )

        workflow = monitor.active_workflows[monitor.workflow_id]
        step = workflow.steps[0]

        assert step.success is False
        assert step.error_message == error_message

    def test_complete_workflow_step_updates_workflow_totals(self, monitor):
        """Test completing step updates workflow totals."""
        step_id1 = monitor.add_workflow_step(
            workflow_id=monitor.workflow_id, stage=WorkflowStage.DISCOVERY
        )
        step_id2 = monitor.add_workflow_step(
            workflow_id=monitor.workflow_id, stage=WorkflowStage.CONTENT_ANALYSIS
        )

        monitor.complete_workflow_step(
            workflow_id=monitor.workflow_id,
            step_id=step_id1,
            tokens_consumed=300,
            api_calls_made=2,
        )

        monitor.complete_workflow_step(
            workflow_id=monitor.workflow_id,
            step_id=step_id2,
            tokens_consumed=500,
            api_calls_made=3,
        )

        workflow = monitor.active_workflows[monitor.workflow_id]
        assert workflow.total_tokens_used == 800
        assert workflow.total_api_calls == 5


class TestDurationCalculation:
    """Tests for duration calculation."""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create WorkflowMonitor instance."""
        config = Mock(spec=Config)
        config.workspace_dir = tmp_path / 'workspace'
        config.workspace_dir.mkdir(exist_ok=True)

        service_manager = Mock(spec=ServiceManager)

        return WorkflowMonitor(config=config, service_manager=service_manager)

    @patch('thoth.performance.workflow_monitor.datetime')
    def test_step_duration_calculation(self, mock_datetime, monitor):
        """Test workflow step duration calculation."""
        start_time = datetime(2025, 1, 1, 10, 0, 0)
        end_time = datetime(2025, 1, 1, 10, 0, 30)

        mock_datetime.now.side_effect = [start_time, end_time, end_time]

        workflow_id = monitor.start_workflow(initial_query='test query')
        step_id = monitor.add_workflow_step(
            workflow_id=workflow_id, stage=WorkflowStage.DISCOVERY
        )
        monitor.complete_workflow_step(workflow_id=workflow_id, step_id=step_id)

        workflow = monitor.active_workflows[workflow_id]
        step = workflow.steps[0]

        assert step.duration_ms == 30000.0

    @patch('thoth.performance.workflow_monitor.datetime')
    def test_workflow_duration_calculation(self, mock_datetime, monitor):
        """Test workflow total duration calculation."""
        start_time = datetime(2025, 1, 1, 10, 0, 0)
        end_time = datetime(2025, 1, 1, 10, 2, 0)

        mock_datetime.now.side_effect = [start_time, end_time, end_time]

        workflow_id = monitor.start_workflow(initial_query='test query')
        completed_workflow = monitor.complete_workflow(
            workflow_id=workflow_id, status=WorkflowStatus.COMPLETED
        )

        assert completed_workflow.total_duration_ms == 120000.0


class TestWorkflowCompletion:
    """Tests for workflow completion."""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create WorkflowMonitor instance."""
        config = Mock(spec=Config)
        config.workspace_dir = tmp_path / 'workspace'
        config.workspace_dir.mkdir(exist_ok=True)

        service_manager = Mock(spec=ServiceManager)

        return WorkflowMonitor(config=config, service_manager=service_manager)

    def test_complete_workflow_successfully(self, monitor):
        """Test completing workflow successfully."""
        workflow_id = monitor.start_workflow(initial_query='test query')

        completed = monitor.complete_workflow(
            workflow_id=workflow_id,
            status=WorkflowStatus.COMPLETED,
            final_response='Research results',
            user_satisfaction=4.5,
        )

        assert completed is not None
        assert completed.status == WorkflowStatus.COMPLETED
        assert completed.final_response == 'Research results'
        assert completed.user_satisfaction == 4.5
        assert completed.end_time is not None
        assert workflow_id not in monitor.active_workflows
        assert completed in monitor.completed_workflows

    def test_complete_workflow_abandoned(self, monitor):
        """Test completing abandoned workflow."""
        workflow_id = monitor.start_workflow(initial_query='test query')

        step_id = monitor.add_workflow_step(
            workflow_id=workflow_id, stage=WorkflowStage.DOCUMENT_RETRIEVAL
        )
        monitor.complete_workflow_step(workflow_id=workflow_id, step_id=step_id)

        completed = monitor.complete_workflow(
            workflow_id=workflow_id, status=WorkflowStatus.ABANDONED
        )

        assert completed.status == WorkflowStatus.ABANDONED
        assert completed.abandoned_at_stage == WorkflowStage.DOCUMENT_RETRIEVAL

    def test_complete_workflow_failed(self, monitor):
        """Test completing failed workflow."""
        workflow_id = monitor.start_workflow(initial_query='test query')

        completed = monitor.complete_workflow(
            workflow_id=workflow_id, status=WorkflowStatus.FAILED
        )

        assert completed.status == WorkflowStatus.FAILED
        assert completed in monitor.completed_workflows

    def test_complete_unknown_workflow(self, monitor):
        """Test completing unknown workflow."""
        result = monitor.complete_workflow(
            workflow_id='unknown_workflow', status=WorkflowStatus.COMPLETED
        )

        assert result is None


class TestWorkflowAggregation:
    """Tests for workflow aggregation and metrics."""

    def test_total_duration_from_steps(self):
        """Test calculating total duration from steps."""
        workflow = create_completed_workflow(duration_seconds=120, num_steps=5)

        assert workflow.total_duration_ms == 120000.0
        assert len(workflow.steps) == 5

        # Verify individual step durations sum up correctly
        total_step_duration = sum(
            step.duration_ms for step in workflow.steps if step.duration_ms
        )
        assert abs(total_step_duration - 120000.0) < 100  # Allow small rounding error

    def test_total_tokens_across_steps(self):
        """Test aggregating tokens across all steps."""
        workflow = create_completed_workflow(
            num_steps=5, tokens_per_step=100
        )

        assert workflow.total_tokens_used == 500

        # Verify token calculation
        total_tokens = sum(step.tokens_consumed for step in workflow.steps)
        assert total_tokens == 500

    def test_total_api_calls(self):
        """Test aggregating API calls across steps."""
        workflow = create_completed_workflow(num_steps=5, api_calls_per_step=2)

        assert workflow.total_api_calls == 10

        # Verify API call calculation
        total_api_calls = sum(step.api_calls_made for step in workflow.steps)
        assert total_api_calls == 10

    def test_cost_estimation(self):
        """Test workflow cost estimation."""
        workflow = create_completed_workflow(duration_seconds=120, num_steps=5)
        workflow.total_cost_usd = 0.05

        assert workflow.total_cost_usd == 0.05


class TestResourceTracking:
    """Tests for resource tracking accuracy."""

    def test_step_resource_tracking(self):
        """Test tracking resources used in a step."""
        resources = {'llm_service', 'semantic_scholar', 'arxiv', 'cache'}

        step = create_workflow_step(resources_used=resources)

        assert len(step.resources_used) == 4
        assert 'llm_service' in step.resources_used
        assert 'semantic_scholar' in step.resources_used
        assert 'arxiv' in step.resources_used
        assert 'cache' in step.resources_used

    def test_workflow_resource_aggregation(self):
        """Test aggregating resources across workflow steps."""
        workflow = create_completed_workflow(num_steps=5)

        all_resources = set()
        for step in workflow.steps:
            all_resources.update(step.resources_used)

        assert len(all_resources) > 0
        assert 'llm_service' in all_resources
        assert 'document_service' in all_resources


class TestUserExperienceMetrics:
    """Tests for user experience metric validation."""

    def test_user_satisfaction_tracking(self):
        """Test user satisfaction tracking."""
        workflow = create_completed_workflow(user_satisfaction=4.5)

        assert workflow.user_satisfaction == 4.5
        assert 1.0 <= workflow.user_satisfaction <= 5.0

    def test_query_iterations_tracking(self):
        """Test query iterations tracking."""
        workflow = create_research_workflow(query_iterations=3)

        assert workflow.query_iterations == 3

    def test_abandonment_stage_tracking(self):
        """Test tracking where workflow was abandoned."""
        workflow = create_abandoned_workflow(
            abandoned_at_stage=WorkflowStage.CONTENT_ANALYSIS
        )

        assert workflow.status == WorkflowStatus.ABANDONED
        assert workflow.abandoned_at_stage == WorkflowStage.CONTENT_ANALYSIS


class TestWorkflowPerformanceAnalysis:
    """Tests for workflow performance analysis."""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create WorkflowMonitor with completed workflows."""
        config = Mock(spec=Config)
        config.workspace_dir = tmp_path / 'workspace'
        config.workspace_dir.mkdir(exist_ok=True)

        service_manager = Mock(spec=ServiceManager)
        monitor = WorkflowMonitor(config=config, service_manager=service_manager)

        # Add completed workflows
        for i in range(8):
            workflow = create_completed_workflow(
                workflow_id=f'completed_{i}',
                duration_seconds=120 + i * 10,
                user_satisfaction=4.0 + i * 0.1,
            )
            monitor.completed_workflows.append(workflow)

        # Add abandoned workflow
        workflow = create_abandoned_workflow()
        monitor.completed_workflows.append(workflow)

        # Add failed workflow
        workflow = create_failed_workflow()
        monitor.completed_workflows.append(workflow)

        return monitor

    def test_analyze_workflow_performance_basic_counts(self, monitor):
        """Test workflow performance analysis basic counts."""
        metrics = monitor.analyze_workflow_performance(time_window_hours=24)

        assert metrics.total_workflows == 10
        assert metrics.completed_workflows == 8
        assert metrics.abandoned_workflows == 1
        assert metrics.failed_workflows == 1

    def test_analyze_workflow_performance_success_rate(self, monitor):
        """Test workflow success rate calculation."""
        metrics = monitor.analyze_workflow_performance(time_window_hours=24)

        assert metrics.query_success_rate == 0.8

    def test_analyze_workflow_performance_duration_analysis(self, monitor):
        """Test workflow duration analysis."""
        metrics = monitor.analyze_workflow_performance(time_window_hours=24)

        assert metrics.avg_workflow_duration_ms > 0
        assert metrics.median_workflow_duration_ms > 0

    def test_analyze_workflow_performance_user_satisfaction(self, monitor):
        """Test user satisfaction analysis."""
        metrics = monitor.analyze_workflow_performance(time_window_hours=24)

        assert metrics.user_satisfaction_avg > 0
        assert metrics.user_satisfaction_avg <= 5.0

    def test_analyze_workflow_performance_with_user_filter(self, monitor):
        """Test workflow performance analysis with user filter."""
        # Add user-specific workflow
        workflow = create_completed_workflow(workflow_id='user_workflow')
        workflow.user_id = 'specific_user'
        monitor.completed_workflows.append(workflow)

        metrics = monitor.analyze_workflow_performance(
            time_window_hours=24, user_id='specific_user'
        )

        assert metrics.total_workflows == 1


class TestWorkflowSerialization:
    """Tests for workflow serialization."""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create WorkflowMonitor instance."""
        config = Mock(spec=Config)
        config.workspace_dir = tmp_path / 'workspace'
        config.workspace_dir.mkdir(exist_ok=True)

        service_manager = Mock(spec=ServiceManager)

        return WorkflowMonitor(config=config, service_manager=service_manager)

    def test_workflow_to_dict_conversion(self, monitor):
        """Test converting workflow to dictionary."""
        workflow = create_completed_workflow()

        workflow_dict = monitor._workflow_to_dict(workflow)

        assert workflow_dict['workflow_id'] == workflow.workflow_id
        assert workflow_dict['user_id'] == workflow.user_id
        assert workflow_dict['initial_query'] == workflow.initial_query
        assert workflow_dict['status'] == workflow.status.value
        assert 'start_time' in workflow_dict
        assert 'end_time' in workflow_dict
        assert 'steps' in workflow_dict

    @pytest.mark.asyncio
    async def test_save_workflow_data(self, monitor):
        """Test saving workflow data to disk."""
        workflow = create_completed_workflow()
        monitor.completed_workflows.append(workflow)

        await monitor.save_workflow_data()

        # Check file was created
        workflow_files = list(monitor.workflow_dir.glob('workflows_*.json'))
        assert len(workflow_files) > 0

        # Verify file content
        with open(workflow_files[0]) as f:
            data = json.load(f)

        assert 'collection_time' in data
        assert 'total_workflows' in data
        assert 'workflows' in data
        assert len(data['workflows']) > 0
