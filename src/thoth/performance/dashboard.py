"""
Performance dashboard for Thoth system visualization and monitoring.

This module provides real-time performance visualization, monitoring dashboards,
and interactive analysis tools for the Thoth research assistant system.
"""

import json
import webbrowser
from datetime import datetime
from typing import Any

from loguru import logger

from thoth.performance.metrics_collector import MetricsCollector
from thoth.performance.optimization_engine import OptimizationEngine
from thoth.performance.pipeline_analyzer import PipelineAnalyzer
from thoth.performance.reliability_analyzer import ReliabilityAnalyzer
from thoth.performance.workflow_monitor import WorkflowMonitor
from thoth.services.service_manager import ServiceManager
from thoth.config import config, Config


class PerformanceDashboard:
    """
    Interactive performance dashboard for Thoth system monitoring.

    Provides:
    - Real-time system metrics visualization
    - Pipeline performance analysis
    - Workflow optimization insights
    - Reliability monitoring
    - Optimization recommendations
    """

    def __init__(
        self,
        config: Config,
        service_manager: ServiceManager,
        metrics_collector: MetricsCollector | None = None,
        pipeline_analyzer: PipelineAnalyzer | None = None,
        workflow_monitor: WorkflowMonitor | None = None,
        reliability_analyzer: ReliabilityAnalyzer | None = None,
        optimization_engine: OptimizationEngine | None = None,
    ):
        """
        Initialize the performance dashboard.

        Args:
            config: Thoth configuration
            service_manager: ServiceManager instance
            metrics_collector: Optional metrics collector
            pipeline_analyzer: Optional pipeline analyzer
            workflow_monitor: Optional workflow monitor
            reliability_analyzer: Optional reliability analyzer
            optimization_engine: Optional optimization engine
        """
        self.config = config
        self.service_manager = service_manager
        self.metrics_collector = metrics_collector
        self.pipeline_analyzer = pipeline_analyzer
        self.workflow_monitor = workflow_monitor
        self.reliability_analyzer = reliability_analyzer
        self.optimization_engine = optimization_engine

        # Dashboard data
        self.dashboard_data: dict[str, Any] = {}
        self.last_update: datetime | None = None

        # Output directory
        self.dashboard_dir = config.workspace_dir / 'dashboard'
        self.dashboard_dir.mkdir(exist_ok=True)

        logger.info('PerformanceDashboard initialized')

    async def generate_dashboard(
        self, time_window_hours: int = 24, output_format: str = 'html'
    ) -> str:
        """
        Generate comprehensive performance dashboard.

        Args:
            time_window_hours: Time window for analysis
            output_format: Output format (html, json)

        Returns:
            str: Path to generated dashboard file
        """
        logger.info(
            f'Generating performance dashboard for {time_window_hours} hour window'
        )

        # Collect all performance data
        await self._collect_dashboard_data(time_window_hours)

        # Generate dashboard
        if output_format.lower() == 'html':
            return await self._generate_html_dashboard()
        elif output_format.lower() == 'json':
            return await self._generate_json_dashboard()
        else:
            raise ValueError(f'Unsupported output format: {output_format}')

    async def _collect_dashboard_data(self, time_window_hours: int) -> None:
        """Collect all data needed for the dashboard."""
        self.dashboard_data = {
            'generation_time': datetime.now(),
            'time_window_hours': time_window_hours,
            'system_overview': {},
            'performance_metrics': {},
            'pipeline_analysis': {},
            'workflow_analysis': {},
            'reliability_analysis': {},
            'optimization_recommendations': {},
        }

        # System overview
        self.dashboard_data['system_overview'] = await self._collect_system_overview()

        # Performance metrics
        if self.metrics_collector:
            self.dashboard_data['performance_metrics'] = (
                self.metrics_collector.get_summary_stats(minutes=time_window_hours * 60)
            )

        # Pipeline analysis
        if self.pipeline_analyzer:
            pipeline_data = {}
            for pipeline_type in [
                'document_processing',
                'rag_indexing',
                'citation_extraction',
            ]:
                try:
                    metrics = self.pipeline_analyzer.analyze_pipeline_performance(
                        pipeline_type, time_window_hours
                    )
                    pipeline_data[pipeline_type] = self._pipeline_metrics_to_dict(
                        metrics
                    )
                except Exception as e:
                    logger.warning(f'Failed to analyze {pipeline_type}: {e}')

            self.dashboard_data['pipeline_analysis'] = pipeline_data

        # Workflow analysis
        if self.workflow_monitor:
            try:
                workflow_metrics = self.workflow_monitor.analyze_workflow_performance(
                    time_window_hours
                )
                self.dashboard_data['workflow_analysis'] = (
                    self._workflow_metrics_to_dict(workflow_metrics)
                )
            except Exception as e:
                logger.warning(f'Failed to analyze workflows: {e}')

        # Reliability analysis
        if self.reliability_analyzer:
            try:
                reliability_metrics = self.reliability_analyzer.analyze_reliability(
                    time_window_hours
                )
                self.dashboard_data['reliability_analysis'] = (
                    self._reliability_metrics_to_dict(reliability_metrics)
                )
            except Exception as e:
                logger.warning(f'Failed to analyze reliability: {e}')

        # Optimization recommendations
        if self.optimization_engine:
            try:
                recommendations = await self.optimization_engine.analyze_and_optimize(
                    time_window_hours
                )
                self.dashboard_data['optimization_recommendations'] = (
                    self._optimization_to_dict(recommendations)
                )
            except Exception as e:
                logger.warning(f'Failed to generate optimizations: {e}')

        self.last_update = datetime.now()

    async def _collect_system_overview(self) -> dict[str, Any]:
        """Collect system overview information."""
        import os

        import psutil

        overview = {
            'timestamp': datetime.now().isoformat(),
            'system_info': {
                'cpu_count': os.cpu_count(),
                'cpu_usage': psutil.cpu_percent(interval=1),
                'memory_total_gb': psutil.virtual_memory().total / (1024**3),
                'memory_usage_percent': psutil.virtual_memory().percent,
                'disk_usage_percent': psutil.disk_usage(
                    str(self.config.workspace_dir)
                ).percent,
            },
            'thoth_info': {
                'workspace_dir': str(self.config.workspace_dir),
                'services_initialized': len(self.service_manager.get_all_services())
                if self.service_manager
                else 0,
                'performance_config': {
                    'auto_scale_workers': self.config.performance_config.auto_scale_workers,
                    'async_enabled': self.config.performance_config.async_enabled,
                    'memory_optimization': self.config.performance_config.memory_optimization_enabled,
                },
            },
        }

        return overview

    def _pipeline_metrics_to_dict(self, metrics) -> dict[str, Any]:
        """Convert pipeline metrics to dictionary."""
        return {
            'pipeline_type': metrics.pipeline_type,
            'total_executions': metrics.total_executions,
            'success_rate': metrics.successful_executions
            / max(1, metrics.total_executions),
            'avg_duration_ms': metrics.avg_duration_ms,
            'p95_duration_ms': metrics.p95_duration_ms,
            'documents_per_hour': metrics.documents_per_hour,
            'bottleneck_stages': metrics.bottleneck_stages,
            'stage_performance': metrics.stage_performance,
            'error_patterns': metrics.error_patterns,
            'processing_cost_per_doc': metrics.processing_cost_per_doc,
        }

    def _workflow_metrics_to_dict(self, metrics) -> dict[str, Any]:
        """Convert workflow metrics to dictionary."""
        return {
            'time_period': metrics.time_period,
            'total_workflows': metrics.total_workflows,
            'completion_rate': metrics.completed_workflows
            / max(1, metrics.total_workflows),
            'abandonment_rate': metrics.abandoned_workflows
            / max(1, metrics.total_workflows),
            'avg_duration_ms': metrics.avg_workflow_duration_ms,
            'avg_documents_per_workflow': metrics.avg_documents_per_workflow,
            'avg_cost_per_workflow': metrics.avg_cost_per_workflow,
            'user_satisfaction_avg': metrics.user_satisfaction_avg,
            'stage_completion_rates': {
                stage.value: rate
                for stage, rate in metrics.stage_completion_rates.items()
            },
            'bottleneck_stages': [stage.value for stage in metrics.bottleneck_stages],
            'most_used_services': metrics.most_used_services,
            'peak_usage_hours': metrics.peak_usage_hours,
        }

    def _reliability_metrics_to_dict(self, metrics) -> dict[str, Any]:
        """Convert reliability metrics to dictionary."""
        return {
            'analysis_period': metrics.analysis_period,
            'uptime_percentage': metrics.uptime_percentage,
            'total_errors': metrics.total_errors,
            'mtbf_hours': metrics.mean_time_between_failures_hours,
            'mttr_ms': metrics.mean_time_to_recovery_ms,
            'recovery_success_rate': metrics.recovery_success_rate,
            'error_by_category': {
                cat.value: count for cat, count in metrics.error_by_category.items()
            },
            'error_by_severity': {
                sev.value: count for sev, count in metrics.error_by_severity.items()
            },
            'error_by_service': metrics.error_by_service,
            'recurring_issues': metrics.recurring_issues,
            'error_trend': metrics.error_trend,
            'peak_error_hours': metrics.peak_error_hours,
        }

    def _optimization_to_dict(self, recommendations) -> dict[str, Any]:
        """Convert optimization recommendations to dictionary."""
        return {
            'generation_time': recommendations.generation_time.isoformat(),
            'total_recommendations': recommendations.total_recommendations,
            'potential_performance_gain': recommendations.potential_performance_gain,
            'potential_cost_savings': recommendations.potential_cost_savings,
            'implementation_timeline': recommendations.implementation_timeline,
            'critical_count': len(recommendations.critical_recommendations),
            'high_priority_count': len(recommendations.high_priority_recommendations),
            'quick_wins_count': len(recommendations.quick_wins),
            'top_recommendations': [
                {
                    'title': rec.title,
                    'description': rec.description,
                    'priority': rec.priority.value,
                    'expected_improvement': rec.expected_improvement,
                    'confidence_level': rec.confidence_level,
                    'implementation_effort': rec.implementation_effort,
                }
                for rec in (
                    recommendations.critical_recommendations[:3]
                    + recommendations.high_priority_recommendations[:3]
                )
            ],
        }

    async def _generate_html_dashboard(self) -> str:
        """Generate HTML dashboard."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = self.dashboard_dir / f'performance_dashboard_{timestamp}.html'

        html_content = self._create_html_content()

        with open(html_file, 'w') as f:
            f.write(html_content)

        logger.info(f'HTML dashboard generated: {html_file}')
        return str(html_file)

    def _create_html_content(self) -> str:
        """Create HTML content for the dashboard."""
        data = self.dashboard_data
        system_overview = data.get('system_overview', {})
        performance_metrics = data.get('performance_metrics', {})
        pipeline_analysis = data.get('pipeline_analysis', {})
        workflow_analysis = data.get('workflow_analysis', {})
        reliability_analysis = data.get('reliability_analysis', {})
        optimization_recs = data.get('optimization_recommendations', {})

        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Thoth Performance Dashboard</title>
    <style>
        {self._get_dashboard_css()}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="dashboard">
        <header class="dashboard-header">
            <h1>🧠 Thoth Performance Dashboard</h1>
            <div class="timestamp">Generated: {data.get('generation_time', '').strftime('%Y-%m-%d %H:%M:%S') if isinstance(data.get('generation_time'), datetime) else data.get('generation_time', 'N/A')}</div>
        </header>

        <div class="dashboard-grid">
            {self._create_system_overview_section(system_overview)}
            {self._create_performance_metrics_section(performance_metrics)}
            {self._create_pipeline_analysis_section(pipeline_analysis)}
            {self._create_workflow_analysis_section(workflow_analysis)}
            {self._create_reliability_analysis_section(reliability_analysis)}
            {self._create_optimization_section(optimization_recs)}
        </div>
    </div>

    <script>
        {self._get_dashboard_javascript()}
    </script>
</body>
</html>
        """

        return html

    def _get_dashboard_css(self) -> str:
        """Get CSS styles for the dashboard."""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #f5f7fa;
            color: #333;
        }

        .dashboard {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        .dashboard-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }

        .dashboard-header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        .timestamp {
            font-size: 1.1em;
            opacity: 0.9;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
        }

        .dashboard-section {
            background: white;
            border-radius: 10px;
            padding: 25px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            border: 1px solid #e1e5e9;
        }

        .section-header {
            font-size: 1.4em;
            font-weight: bold;
            margin-bottom: 20px;
            color: #2d3748;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 10px;
        }

        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .metric-card {
            background: #f8fafc;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e2e8f0;
        }

        .metric-value {
            font-size: 1.8em;
            font-weight: bold;
            color: #2b6cb0;
            margin-bottom: 5px;
        }

        .metric-label {
            font-size: 0.9em;
            color: #64748b;
        }

        .status-good { color: #059669; }
        .status-warning { color: #d97706; }
        .status-error { color: #dc2626; }

        .chart-container {
            margin: 20px 0;
            height: 300px;
        }

        .recommendation-list {
            list-style: none;
        }

        .recommendation-item {
            background: #f8fafc;
            margin: 10px 0;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #3b82f6;
        }

        .recommendation-title {
            font-weight: bold;
            color: #1f2937;
            margin-bottom: 5px;
        }

        .recommendation-description {
            color: #6b7280;
            font-size: 0.9em;
        }

        .priority-critical { border-left-color: #dc2626; }
        .priority-high { border-left-color: #ea580c; }
        .priority-medium { border-left-color: #d97706; }
        .priority-low { border-left-color: #65a30d; }

        .error-list {
            max-height: 200px;
            overflow-y: auto;
        }

        .error-item {
            padding: 8px;
            margin: 5px 0;
            background: #fef2f2;
            border-radius: 4px;
            font-size: 0.9em;
            color: #991b1b;
        }

        .stage-performance {
            margin: 15px 0;
        }

        .stage-bar {
            background: #e5e7eb;
            height: 20px;
            border-radius: 10px;
            margin: 5px 0;
            overflow: hidden;
        }

        .stage-bar-fill {
            background: linear-gradient(90deg, #3b82f6, #1d4ed8);
            height: 100%;
            border-radius: 10px;
            transition: width 0.3s ease;
        }

        .stage-label {
            font-size: 0.9em;
            margin-bottom: 3px;
            color: #374151;
        }

        @media (max-width: 768px) {
            .dashboard-grid {
                grid-template-columns: 1fr;
            }

            .metric-grid {
                grid-template-columns: repeat(2, 1fr);
            }
        }
        """

    def _create_system_overview_section(self, system_overview: dict[str, Any]) -> str:
        """Create system overview section."""
        system_info = system_overview.get('system_info', {})
        thoth_info = system_overview.get('thoth_info', {})

        cpu_status = (
            'status-good'
            if system_info.get('cpu_usage', 0) < 70
            else 'status-warning'
            if system_info.get('cpu_usage', 0) < 90
            else 'status-error'
        )
        memory_status = (
            'status-good'
            if system_info.get('memory_usage_percent', 0) < 80
            else 'status-warning'
            if system_info.get('memory_usage_percent', 0) < 95
            else 'status-error'
        )

        return f"""
        <div class="dashboard-section">
            <div class="section-header">📊 System Overview</div>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value {cpu_status}">{system_info.get('cpu_usage', 0):.1f}%</div>
                    <div class="metric-label">CPU Usage</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value {memory_status}">{system_info.get('memory_usage_percent', 0):.1f}%</div>
                    <div class="metric-label">Memory Usage</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{system_info.get('cpu_count', 0)}</div>
                    <div class="metric-label">CPU Cores</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{system_info.get('memory_total_gb', 0):.1f}GB</div>
                    <div class="metric-label">Total Memory</div>
                </div>
            </div>

            <h4>Thoth Configuration</h4>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value">{thoth_info.get('services_initialized', 0)}</div>
                    <div class="metric-label">Services</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{'✓' if thoth_info.get('performance_config', {}).get('auto_scale_workers') else '✗'}</div>
                    <div class="metric-label">Auto Scaling</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{'✓' if thoth_info.get('performance_config', {}).get('async_enabled') else '✗'}</div>
                    <div class="metric-label">Async Processing</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{'✓' if thoth_info.get('performance_config', {}).get('memory_optimization') else '✗'}</div>
                    <div class="metric-label">Memory Optimization</div>
                </div>
            </div>
        </div>
        """

    def _create_performance_metrics_section(
        self, performance_metrics: dict[str, Any]
    ) -> str:
        """Create performance metrics section."""
        if not performance_metrics:
            return '<div class="dashboard-section"><div class="section-header">⚡ Performance Metrics</div><p>No performance data available</p></div>'

        system_perf = performance_metrics.get('system_performance', {})
        api_perf = performance_metrics.get('api_performance', {})
        resource_consumption = performance_metrics.get('resource_consumption', {})

        return f"""
        <div class="dashboard-section">
            <div class="section-header">⚡ Performance Metrics</div>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value">{system_perf.get('cpu_usage', {}).get('avg', 0):.1f}%</div>
                    <div class="metric-label">Avg CPU</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{system_perf.get('memory_usage', {}).get('avg', 0):.1f}%</div>
                    <div class="metric-label">Avg Memory</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{api_perf.get('total_requests', 0)}</div>
                    <div class="metric-label">API Requests</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${sum(resource_consumption.get('api_costs_usd', {}).values()):.2f}</div>
                    <div class="metric-label">Total Cost</div>
                </div>
            </div>

            <h4>API Response Times</h4>
            <div class="stage-performance">
                <div class="stage-label">Average: {api_perf.get('response_time_ms', {}).get('avg', 0):.1f}ms</div>
                <div class="stage-bar">
                    <div class="stage-bar-fill" style="width: {min(100, api_perf.get('response_time_ms', {}).get('avg', 0) / 20)}%"></div>
                </div>
                <div class="stage-label">P95: {api_perf.get('response_time_ms', {}).get('p95', 0):.1f}ms</div>
                <div class="stage-bar">
                    <div class="stage-bar-fill" style="width: {min(100, api_perf.get('response_time_ms', {}).get('p95', 0) / 20)}%"></div>
                </div>
            </div>
        </div>
        """

    def _create_pipeline_analysis_section(
        self, pipeline_analysis: dict[str, Any]
    ) -> str:
        """Create pipeline analysis section."""
        if not pipeline_analysis:
            return '<div class="dashboard-section"><div class="section-header">🔄 Pipeline Analysis</div><p>No pipeline data available</p></div>'

        sections = []
        for pipeline_type, data in pipeline_analysis.items():
            success_rate = data.get('success_rate', 0) * 100
            status_class = (
                'status-good'
                if success_rate > 95
                else 'status-warning'
                if success_rate > 85
                else 'status-error'
            )

            sections.append(f"""
            <h4>{pipeline_type.replace('_', ' ').title()}</h4>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value {status_class}">{success_rate:.1f}%</div>
                    <div class="metric-label">Success Rate</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{data.get('avg_duration_ms', 0) / 1000:.1f}s</div>
                    <div class="metric-label">Avg Duration</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{data.get('documents_per_hour', 0):.1f}</div>
                    <div class="metric-label">Docs/Hour</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${data.get('processing_cost_per_doc', 0):.3f}</div>
                    <div class="metric-label">Cost/Doc</div>
                </div>
            </div>
            """)

        return f"""
        <div class="dashboard-section">
            <div class="section-header">🔄 Pipeline Analysis</div>
            {''.join(sections)}
        </div>
        """

    def _create_workflow_analysis_section(
        self, workflow_analysis: dict[str, Any]
    ) -> str:
        """Create workflow analysis section."""
        if not workflow_analysis:
            return '<div class="dashboard-section"><div class="section-header">📈 Workflow Analysis</div><p>No workflow data available</p></div>'

        completion_rate = workflow_analysis.get('completion_rate', 0) * 100
        status_class = (
            'status-good'
            if completion_rate > 85
            else 'status-warning'
            if completion_rate > 70
            else 'status-error'
        )

        return f"""
        <div class="dashboard-section">
            <div class="section-header">📈 Workflow Analysis</div>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value">{workflow_analysis.get('total_workflows', 0)}</div>
                    <div class="metric-label">Total Workflows</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value {status_class}">{completion_rate:.1f}%</div>
                    <div class="metric-label">Completion Rate</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{workflow_analysis.get('avg_duration_ms', 0) / 1000:.1f}s</div>
                    <div class="metric-label">Avg Duration</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{workflow_analysis.get('user_satisfaction_avg', 0):.1f}/5</div>
                    <div class="metric-label">User Satisfaction</div>
                </div>
            </div>

            <h4>Peak Usage Hours</h4>
            <p>{', '.join(map(str, workflow_analysis.get('peak_usage_hours', [])))}</p>

            <h4>Most Used Services</h4>
            <p>{', '.join(workflow_analysis.get('most_used_services', []))}</p>
        </div>
        """

    def _create_reliability_analysis_section(
        self, reliability_analysis: dict[str, Any]
    ) -> str:
        """Create reliability analysis section."""
        if not reliability_analysis:
            return '<div class="dashboard-section"><div class="section-header">🛡️ Reliability Analysis</div><p>No reliability data available</p></div>'

        uptime = reliability_analysis.get('uptime_percentage', 0)
        uptime_status = (
            'status-good'
            if uptime > 99
            else 'status-warning'
            if uptime > 95
            else 'status-error'
        )

        return f"""
        <div class="dashboard-section">
            <div class="section-header">🛡️ Reliability Analysis</div>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value {uptime_status}">{uptime:.2f}%</div>
                    <div class="metric-label">Uptime</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{reliability_analysis.get('total_errors', 0)}</div>
                    <div class="metric-label">Total Errors</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{reliability_analysis.get('mtbf_hours', 0):.1f}h</div>
                    <div class="metric-label">MTBF</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{reliability_analysis.get('mttr_ms', 0) / 1000:.1f}s</div>
                    <div class="metric-label">MTTR</div>
                </div>
            </div>

            <h4>Recent Issues</h4>
            <div class="error-list">
                {''.join(f'<div class="error-item">{issue}</div>' for issue in reliability_analysis.get('recurring_issues', [])[:5])}
            </div>
        </div>
        """

    def _create_optimization_section(self, optimization_recs: dict[str, Any]) -> str:
        """Create optimization recommendations section."""
        if not optimization_recs:
            return '<div class="dashboard-section"><div class="section-header">🚀 Optimization Recommendations</div><p>No optimization data available</p></div>'

        return f"""
        <div class="dashboard-section">
            <div class="section-header">🚀 Optimization Recommendations</div>
            <div class="metric-grid">
                <div class="metric-card">
                    <div class="metric-value">{optimization_recs.get('total_recommendations', 0)}</div>
                    <div class="metric-label">Total Recommendations</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{optimization_recs.get('critical_count', 0)}</div>
                    <div class="metric-label">Critical Issues</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{optimization_recs.get('potential_performance_gain', 0):.1f}%</div>
                    <div class="metric-label">Potential Gain</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">{optimization_recs.get('quick_wins_count', 0)}</div>
                    <div class="metric-label">Quick Wins</div>
                </div>
            </div>

            <h4>Top Recommendations</h4>
            <ul class="recommendation-list">
                {''.join(self._format_recommendation(rec) for rec in optimization_recs.get('top_recommendations', [])[:5])}
            </ul>
        </div>
        """

    def _format_recommendation(self, rec: dict[str, Any]) -> str:
        """Format a single recommendation for HTML display."""
        priority_class = f'priority-{rec.get("priority", "low")}'
        return f"""
        <li class="recommendation-item {priority_class}">
            <div class="recommendation-title">{rec.get('title', 'Unknown')}</div>
            <div class="recommendation-description">{rec.get('description', 'No description')}</div>
            <small>Expected improvement: {rec.get('expected_improvement', 'Unknown')} |
            Effort: {rec.get('implementation_effort', 'Unknown')} |
            Confidence: {rec.get('confidence_level', 0) * 100:.0f}%</small>
        </li>
        """

    def _get_dashboard_javascript(self) -> str:
        """Get JavaScript for dashboard interactivity."""
        return """
        // Dashboard interactivity
        document.addEventListener('DOMContentLoaded', function() {
            // Add hover effects and animations
            const cards = document.querySelectorAll('.metric-card');
            cards.forEach(card => {
                card.addEventListener('mouseenter', function() {
                    this.style.transform = 'translateY(-2px)';
                    this.style.boxShadow = '0 6px 12px rgba(0, 0, 0, 0.15)';
                });

                card.addEventListener('mouseleave', function() {
                    this.style.transform = 'translateY(0)';
                    this.style.boxShadow = '0 4px 6px rgba(0, 0, 0, 0.1)';
                });
            });

            // Animate progress bars
            const bars = document.querySelectorAll('.stage-bar-fill');
            bars.forEach(bar => {
                const width = bar.style.width;
                bar.style.width = '0%';
                setTimeout(() => {
                    bar.style.width = width;
                }, 100);
            });

            // Auto-refresh functionality (commented out for static dashboard)
            // setInterval(() => {
            //     location.reload();
            // }, 300000); // Refresh every 5 minutes
        });
        """

    async def _generate_json_dashboard(self) -> str:
        """Generate JSON dashboard data."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = self.dashboard_dir / f'dashboard_data_{timestamp}.json'

        with open(json_file, 'w') as f:
            json.dump(self.dashboard_data, f, indent=2, default=str)

        logger.info(f'JSON dashboard data saved: {json_file}')
        return str(json_file)

    async def serve_dashboard(self, port: int = 8080) -> None:
        """
        Serve dashboard via simple HTTP server.

        Args:
            port: Port to serve on
        """
        try:
            # Generate dashboard
            dashboard_file = await self.generate_dashboard()

            # Open in browser
            webbrowser.open(f'file://{dashboard_file}')
            logger.info(f'Dashboard opened in browser: {dashboard_file}')

        except Exception as e:
            logger.error(f'Failed to serve dashboard: {e}')

    def get_dashboard_summary(self) -> dict[str, Any]:
        """Get a summary of current dashboard data."""
        if not self.dashboard_data:
            return {'error': 'No dashboard data available'}

        summary = {
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'system_health': 'unknown',
            'key_metrics': {},
            'top_issues': [],
            'recommendations_count': 0,
        }

        # Determine system health
        system_overview = self.dashboard_data.get('system_overview', {})
        system_info = system_overview.get('system_info', {})

        cpu_usage = system_info.get('cpu_usage', 0)
        memory_usage = system_info.get('memory_usage_percent', 0)

        if cpu_usage < 70 and memory_usage < 80:
            summary['system_health'] = 'good'
        elif cpu_usage < 90 and memory_usage < 95:
            summary['system_health'] = 'warning'
        else:
            summary['system_health'] = 'critical'

        # Key metrics
        performance_metrics = self.dashboard_data.get('performance_metrics', {})
        summary['key_metrics'] = {
            'cpu_usage': f'{cpu_usage:.1f}%',
            'memory_usage': f'{memory_usage:.1f}%',
            'total_cost': f'${sum(performance_metrics.get("resource_consumption", {}).get("api_costs_usd", {}).values()):.2f}',
            'api_requests': performance_metrics.get('api_performance', {}).get(
                'total_requests', 0
            ),
        }

        # Top issues from reliability analysis
        reliability_analysis = self.dashboard_data.get('reliability_analysis', {})
        summary['top_issues'] = reliability_analysis.get('recurring_issues', [])[:3]

        # Recommendations count
        optimization_recs = self.dashboard_data.get('optimization_recommendations', {})
        summary['recommendations_count'] = optimization_recs.get(
            'total_recommendations', 0
        )

        return summary
