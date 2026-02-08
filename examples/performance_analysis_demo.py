#!/usr/bin/env python3
"""
Thoth Performance Analysis System Demonstration

This script demonstrates the comprehensive performance analysis capabilities
of the Thoth system, including real-time monitoring, pipeline analysis,
workflow optimization, and reliability assessment.

Usage:
    python examples/performance_analysis_demo.py [--demo-mode] [--generate-report]

Features demonstrated:
- Real-time metrics collection
- Pipeline performance analysis
- Workflow monitoring and optimization
- Reliability analysis and error pattern detection
- Automated optimization recommendations
- Interactive performance dashboard
- Comprehensive benchmarking suite
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from loguru import logger
from thoth.utilities.config import get_config

from thoth.performance.benchmarking import BenchmarkSuite
from thoth.performance.dashboard import PerformanceDashboard

# Import performance analysis components
from thoth.performance.metrics_collector import MetricsCollector
from thoth.performance.optimization_engine import OptimizationEngine
from thoth.performance.pipeline_analyzer import PipelineAnalyzer
from thoth.performance.reliability_analyzer import (
    FailureCategory,
    FailureSeverity,
    ReliabilityAnalyzer,
)
from thoth.performance.workflow_monitor import (
    WorkflowMonitor,
    WorkflowStage,
    WorkflowStatus,
)
from thoth.services.service_manager import ServiceManager


class PerformanceAnalysisDemo:
    """
    Comprehensive demonstration of Thoth performance analysis capabilities.
    """

    def __init__(self, demo_mode: bool = False):
        """
        Initialize the performance analysis demo.

        Args:
            demo_mode: If True, generates synthetic data for demonstration
        """
        self.demo_mode = demo_mode
        self.config = get_config()
        self.service_manager = ServiceManager(self.config)

        # Initialize performance analysis components
        self.metrics_collector = MetricsCollector(
            self.config,
            self.service_manager,
            collection_interval=5,  # 5-second intervals for demo
            retention_hours=2,  # 2-hour retention for demo
        )

        self.pipeline_analyzer = PipelineAnalyzer(
            self.config, self.service_manager, self.metrics_collector
        )

        self.workflow_monitor = WorkflowMonitor(
            self.config, self.service_manager, self.metrics_collector
        )

        self.reliability_analyzer = ReliabilityAnalyzer(
            self.config, self.service_manager, self.metrics_collector
        )

        self.optimization_engine = OptimizationEngine(
            self.config,
            self.service_manager,
            self.metrics_collector,
            self.pipeline_analyzer,
            self.workflow_monitor,
            self.reliability_analyzer,
        )

        self.dashboard = PerformanceDashboard(
            self.config,
            self.service_manager,
            self.metrics_collector,
            self.pipeline_analyzer,
            self.workflow_monitor,
            self.reliability_analyzer,
            self.optimization_engine,
        )

        self.benchmark_suite = BenchmarkSuite(self.config, self.service_manager)

        logger.info('Performance Analysis Demo initialized')

    async def run_comprehensive_demo(self) -> None:
        """Run the complete performance analysis demonstration."""
        logger.info('🚀 Starting Thoth Performance Analysis Comprehensive Demo')

        print('\n' + '=' * 80)
        print('THOTH PERFORMANCE ANALYSIS SYSTEM DEMONSTRATION')
        print('=' * 80)
        print('This demo showcases the comprehensive performance monitoring,')
        print('analysis, and optimization capabilities of the Thoth system.')
        print('=' * 80 + '\n')

        # Phase 1: System Initialization and Metrics Collection
        await self._demo_metrics_collection()

        # Phase 2: Pipeline Performance Analysis
        await self._demo_pipeline_analysis()

        # Phase 3: Workflow Monitoring
        await self._demo_workflow_monitoring()

        # Phase 4: Reliability Analysis
        await self._demo_reliability_analysis()

        # Phase 5: Optimization Engine
        await self._demo_optimization_engine()

        # Phase 6: Performance Dashboard
        await self._demo_performance_dashboard()

        # Phase 7: Benchmarking Suite
        await self._demo_benchmarking_suite()

        # Phase 8: Generate Comprehensive Report
        await self._generate_final_report()

        print('\n' + '=' * 80)
        print('🎉 DEMONSTRATION COMPLETED SUCCESSFULLY!')
        print('=' * 80)
        print('Check the workspace/dashboard and workspace/analysis directories')
        print('for generated reports, dashboards, and detailed analysis results.')
        print('=' * 80 + '\n')

    async def _demo_metrics_collection(self) -> None:
        """Demonstrate real-time metrics collection."""
        print('📊 PHASE 1: Real-time Metrics Collection')
        print('-' * 50)

        # Start metrics collection
        await self.metrics_collector.start_collection()
        print('✓ Started real-time metrics collection')

        if self.demo_mode:
            # Simulate system activity
            print('📈 Simulating system activity...')

            # Simulate various operations with metrics tracking
            await self._simulate_system_activity()

            # Let metrics collect for a bit
            await asyncio.sleep(10)

            # Show current metrics summary
            summary = self.metrics_collector.get_summary_stats(minutes=5)
            print('✓ Collected metrics over 5 minutes:')
            print(
                f'  - System Performance: CPU avg {summary.get("system_performance", {}).get("cpu_usage", {}).get("avg", 0):.1f}%'
            )
            print(
                f'  - API Requests: {summary.get("api_performance", {}).get("total_requests", 0)}'
            )
            print(
                f'  - Total Operations: {summary.get("resource_consumption", {}).get("total_operations", 0)}'
            )

        print('📊 Metrics collection active in background...\n')

    async def _simulate_system_activity(self) -> None:
        """Simulate various system operations for demonstration."""
        operations = [
            ('llm', 'query_processing', 2.5),
            ('pipeline', 'pdf_processing', 5.0),
            ('pipeline', 'ocr_processing', 3.2),
            ('agent', 'reasoning', 1.8),
            ('rag', 'query', 0.8),
            ('database', 'chroma_query', 0.3),
            ('api', 'openai_completion', 4.2),
            ('pipeline', 'citation_extraction', 2.1),
        ]

        for category, operation, duration in operations:
            with self.metrics_collector.measure_operation(operation, category):
                await asyncio.sleep(duration * 0.1)  # Speed up for demo

            # Record successes and API calls
            self.metrics_collector.record_success(
                'document_processed' if 'processing' in operation else 'query_executed'
            )
            if 'api' in category or operation in [
                'query_processing',
                'openai_completion',
            ]:
                self.metrics_collector.record_api_call(
                    operation, tokens_used=1500, cost=0.003
                )

    async def _demo_pipeline_analysis(self) -> None:
        """Demonstrate pipeline performance analysis."""
        print('🔄 PHASE 2: Pipeline Performance Analysis')
        print('-' * 50)

        if self.demo_mode:
            # Simulate pipeline executions
            await self._simulate_pipeline_executions()

        # Analyze pipeline performance
        pipeline_types = ['document_processing', 'rag_indexing', 'citation_extraction']

        for pipeline_type in pipeline_types:
            try:
                metrics = self.pipeline_analyzer.analyze_pipeline_performance(
                    pipeline_type, 1
                )
                print(f'✓ {pipeline_type.replace("_", " ").title()} Pipeline:')
                print(f'  - Total executions: {metrics.total_executions}')
                print(
                    f'  - Success rate: {metrics.successful_executions / max(1, metrics.total_executions) * 100:.1f}%'
                )
                print(f'  - Average duration: {metrics.avg_duration_ms:.1f}ms')
                print(
                    f'  - Bottleneck stages: {", ".join(metrics.bottleneck_stages) if metrics.bottleneck_stages else "None"}'
                )

                # Identify optimization opportunities
                opportunities = (
                    self.pipeline_analyzer.identify_optimization_opportunities(
                        pipeline_type
                    )
                )
                if opportunities.get('bottlenecks'):
                    print(
                        f'  - Optimization opportunities: {len(opportunities["bottlenecks"])} identified'
                    )

            except Exception as e:
                print(f'  ⚠️  Analysis failed: {e}')

        print('🔄 Pipeline analysis complete\n')

    async def _simulate_pipeline_executions(self) -> None:
        """Simulate pipeline executions for analysis."""
        # Document processing pipeline
        for i in range(15):
            execution_id = self.pipeline_analyzer.start_pipeline_execution(
                'document_processing', f'document_{i}.pdf'
            )

            # Add stages with varying performance
            base_duration = 2000 + (i % 5) * 500  # Vary duration
            self.pipeline_analyzer.add_pipeline_stage(
                execution_id,
                'ocr_processing',
                base_duration + 1000,
                1024 * 1024,
                500 * 1024,
            )
            self.pipeline_analyzer.add_pipeline_stage(
                execution_id,
                'content_analysis',
                base_duration + 3000,
                500 * 1024,
                50 * 1024,
            )
            self.pipeline_analyzer.add_pipeline_stage(
                execution_id,
                'citation_extraction',
                base_duration + 800,
                50 * 1024,
                10 * 1024,
            )

            success = i % 10 != 0  # 10% failure rate
            self.pipeline_analyzer.complete_pipeline_execution(
                execution_id, success, None if success else 'Timeout during analysis'
            )

        # Similar for other pipeline types
        for pipeline_type in ['rag_indexing', 'citation_extraction']:
            for i in range(8):
                execution_id = self.pipeline_analyzer.start_pipeline_execution(
                    pipeline_type, f'item_{i}'
                )
                duration = 1000 + (i % 3) * 300
                self.pipeline_analyzer.add_pipeline_stage(
                    execution_id, 'processing', duration
                )
                self.pipeline_analyzer.complete_pipeline_execution(
                    execution_id, i % 8 != 0
                )

    async def _demo_workflow_monitoring(self) -> None:
        """Demonstrate workflow monitoring capabilities."""
        print('📈 PHASE 3: Workflow Monitoring and Optimization')
        print('-' * 50)

        if self.demo_mode:
            # Simulate research workflows
            await self._simulate_research_workflows()

        # Analyze workflow performance
        workflow_metrics = self.workflow_monitor.analyze_workflow_performance(1)

        print('✓ Workflow Analysis Results:')
        print(f'  - Total workflows: {workflow_metrics.total_workflows}')
        print(
            f'  - Completion rate: {workflow_metrics.completed_workflows / max(1, workflow_metrics.total_workflows) * 100:.1f}%'
        )
        print(
            f'  - Average duration: {workflow_metrics.avg_workflow_duration_ms / 1000:.1f} seconds'
        )
        print(
            f'  - User satisfaction: {workflow_metrics.user_satisfaction_avg:.1f}/5.0'
        )
        print(f'  - Peak usage hours: {workflow_metrics.peak_usage_hours}')

        # Identify optimization opportunities
        opportunities = self.workflow_monitor.identify_optimization_opportunities()
        print('✓ Optimization opportunities identified:')
        print(
            f'  - Workflow efficiency: {len(opportunities.get("workflow_efficiency", []))}'
        )
        print(f'  - User experience: {len(opportunities.get("user_experience", []))}')
        print(
            f'  - Stage improvements: {len(opportunities.get("stage_improvements", []))}'
        )

        print('📈 Workflow monitoring complete\n')

    async def _simulate_research_workflows(self) -> None:
        """Simulate research workflows for monitoring."""
        queries = [
            'Recent advances in machine learning interpretability',
            'Neural network architectures for natural language processing',
            'Performance optimization techniques for distributed systems',
            'Comparative analysis of vector databases',
            'Research methodology in AI safety',
        ]

        for i, query in enumerate(queries):
            # Start workflow
            workflow_id = self.workflow_monitor.start_workflow(query, f'user_{i % 3}')

            # Simulate workflow stages
            stages = [
                (WorkflowStage.QUERY_INITIATION, 500),
                (WorkflowStage.DISCOVERY, 3000),
                (WorkflowStage.DOCUMENT_RETRIEVAL, 2500),
                (WorkflowStage.CONTENT_ANALYSIS, 8000),
                (WorkflowStage.KNOWLEDGE_SYNTHESIS, 4000),
                (WorkflowStage.RESULT_GENERATION, 2000),
            ]

            for stage, duration in stages:
                step_id = self.workflow_monitor.add_workflow_step(
                    workflow_id, stage, {'stage_input': f'data_for_{stage.value}'}
                )

                # Simulate processing time
                await asyncio.sleep(duration * 0.001)  # Speed up for demo

                # Complete step
                success = (i + len(stages)) % 15 != 0  # Some failures
                self.workflow_monitor.complete_workflow_step(
                    workflow_id,
                    step_id,
                    success,
                    {'stage_output': f'result_from_{stage.value}'},
                    tokens_consumed=200,
                    api_calls_made=1
                    if stage in [WorkflowStage.CONTENT_ANALYSIS]
                    else 0,
                )

            # Complete workflow
            status = (
                WorkflowStatus.COMPLETED if i % 8 != 0 else WorkflowStatus.ABANDONED
            )
            satisfaction = 4.2 if status == WorkflowStatus.COMPLETED else None
            self.workflow_monitor.complete_workflow(
                workflow_id, status, 'Research completed', satisfaction
            )

    async def _demo_reliability_analysis(self) -> None:
        """Demonstrate reliability analysis and error pattern detection."""
        print('🛡️ PHASE 4: Reliability Analysis and Error Pattern Detection')
        print('-' * 50)

        if self.demo_mode:
            # Simulate various error conditions
            await self._simulate_error_conditions()

        # Analyze reliability
        reliability_metrics = self.reliability_analyzer.analyze_reliability(1)

        print('✓ Reliability Analysis Results:')
        print(f'  - System uptime: {reliability_metrics.uptime_percentage:.2f}%')
        print(f'  - Total errors: {reliability_metrics.total_errors}')
        print(
            f'  - MTBF: {reliability_metrics.mean_time_between_failures_hours:.1f} hours'
        )
        print(f'  - MTTR: {reliability_metrics.mean_time_to_recovery_ms:.1f}ms')
        print(
            f'  - Recovery success rate: {reliability_metrics.recovery_success_rate:.1%}'
        )

        # Show error patterns
        if reliability_metrics.top_failure_patterns:
            print('✓ Top failure patterns:')
            for pattern in reliability_metrics.top_failure_patterns[:3]:
                print(f'  - {pattern.pattern_name}: {pattern.occurrences} occurrences')

        print('🛡️ Reliability analysis complete\n')

    async def _simulate_error_conditions(self) -> None:
        """Simulate various error conditions for reliability analysis."""
        error_scenarios = [
            (
                'llm',
                'RateLimitError',
                'Rate limit exceeded for OpenAI API',
                FailureCategory.RATE_LIMITING,
                FailureSeverity.MEDIUM,
            ),
            (
                'rag',
                'DatabaseConnectionError',
                'Failed to connect to ChromaDB',
                FailureCategory.DATABASE_FAILURE,
                FailureSeverity.HIGH,
            ),
            (
                'processing',
                'TimeoutError',
                'OCR processing timed out after 60 seconds',
                FailureCategory.TIMEOUT,
                FailureSeverity.MEDIUM,
            ),
            (
                'discovery',
                'NetworkError',
                'Failed to connect to Semantic Scholar API',
                FailureCategory.NETWORK_FAILURE,
                FailureSeverity.LOW,
            ),
            (
                'citation',
                'ParsingError',
                'Failed to parse citation format',
                FailureCategory.PROCESSING_FAILURE,
                FailureSeverity.LOW,
            ),
            (
                'llm',
                'AuthenticationError',
                'Invalid API key for Anthropic Claude',
                FailureCategory.AUTHENTICATION_FAILURE,
                FailureSeverity.HIGH,
            ),
        ]

        for i, (service, error_type, error_message, category, severity) in enumerate(
            error_scenarios
        ):
            # Create multiple instances of some errors
            count = 3 if i % 3 == 0 else 1

            for _ in range(count):
                event_id = self.reliability_analyzer.record_error(
                    service,
                    error_type,
                    error_message,
                    user_id=f'user_{i % 3}',
                    operation='test_operation',
                )

                # Simulate some recovery attempts
                if i % 2 == 0:
                    recovery_time = 1000 + (i * 200)  # Varying recovery times
                    success = i % 4 != 0  # Most recoveries succeed
                    self.reliability_analyzer.record_recovery_attempt(
                        event_id, success, recovery_time
                    )

    async def _demo_optimization_engine(self) -> None:
        """Demonstrate optimization recommendation engine."""
        print('🚀 PHASE 5: Optimization Engine and Recommendations')
        print('-' * 50)

        # Generate optimization recommendations
        recommendations = await self.optimization_engine.analyze_and_optimize(1)

        print('✓ Optimization Analysis Complete:')
        print(f'  - Total recommendations: {recommendations.total_recommendations}')
        print(f'  - Critical issues: {len(recommendations.critical_recommendations)}')
        print(
            f'  - High priority: {len(recommendations.high_priority_recommendations)}'
        )
        print(f'  - Quick wins: {len(recommendations.quick_wins)}')
        print(
            f'  - Potential performance gain: {recommendations.potential_performance_gain:.1f}%'
        )
        print(
            f'  - Potential cost savings: {recommendations.potential_cost_savings:.1f}%'
        )

        # Show top recommendations
        print('\n✓ Top Recommendations:')
        all_recs = (
            recommendations.critical_recommendations
            + recommendations.high_priority_recommendations
        )

        for i, rec in enumerate(all_recs[:5]):
            print(f'  {i + 1}. {rec.title}')
            print(f'     Priority: {rec.priority.value.title()}')
            print(f'     Expected improvement: {rec.expected_improvement}')
            print(f'     Implementation effort: {rec.implementation_effort}')

        # Save optimization report
        await self.optimization_engine.save_optimization_data(recommendations)
        print('✓ Optimization recommendations saved')

        print('🚀 Optimization engine complete\n')

    async def _demo_performance_dashboard(self) -> None:
        """Demonstrate performance dashboard generation."""
        print('📊 PHASE 6: Performance Dashboard Generation')
        print('-' * 50)

        # Generate comprehensive dashboard
        dashboard_file = await self.dashboard.generate_dashboard(
            time_window_hours=1, output_format='html'
        )

        print(f'✓ Performance dashboard generated: {dashboard_file}')

        # Generate JSON data export
        json_file = await self.dashboard.generate_dashboard(
            time_window_hours=1, output_format='json'
        )

        print(f'✓ Dashboard data exported: {json_file}')

        # Get dashboard summary
        summary = self.dashboard.get_dashboard_summary()
        print('✓ Dashboard Summary:')
        print(f'  - System health: {summary.get("system_health", "unknown").title()}')
        print(
            f'  - CPU usage: {summary.get("key_metrics", {}).get("cpu_usage", "N/A")}'
        )
        print(
            f'  - Memory usage: {summary.get("key_metrics", {}).get("memory_usage", "N/A")}'
        )
        print(
            f'  - Total cost: {summary.get("key_metrics", {}).get("total_cost", "$0.00")}'
        )
        print(f'  - Recommendations: {summary.get("recommendations_count", 0)}')

        print('📊 Dashboard generation complete\n')

    async def _demo_benchmarking_suite(self) -> None:
        """Demonstrate comprehensive benchmarking capabilities."""
        print('⚡ PHASE 7: Performance Benchmarking Suite')
        print('-' * 50)

        # Create standard benchmarks
        self.benchmark_suite.create_standard_benchmarks()
        print(f'✓ Created {len(self.benchmark_suite.benchmark_tests)} benchmark tests')

        # Run a subset of benchmarks for demo (to save time)
        benchmark_results = await self.benchmark_suite.run_benchmarks(
            test_filter='simple',  # Run only simple tests
            compare_with_baseline=False,
        )

        print('✓ Benchmark Results:')
        print(f'  - Total tests: {benchmark_results.total_tests}')
        print(f'  - Passed: {benchmark_results.passed_tests}')
        print(f'  - Failed: {benchmark_results.failed_tests}')
        print(
            f'  - Performance score: {benchmark_results.overall_performance_score:.1f}/100'
        )

        # Show individual test results
        print('\n✓ Individual Test Results:')
        for result in benchmark_results.test_results:
            status = (
                '✓'
                if result.meets_duration_threshold and result.meets_success_threshold
                else '✗'
            )
            print(f'  {status} {result.test_name}')
            print(f'    Success rate: {result.success_rate * 100:.1f}%')
            print(f'    Avg duration: {result.avg_duration_ms:.1f}ms')

        # Generate benchmark report
        report = self.benchmark_suite.generate_benchmark_report(benchmark_results)
        report_file = (
            self.config.workspace_dir / 'benchmarks' / 'latest_benchmark_report.txt'
        )
        with open(report_file, 'w') as f:
            f.write(report)

        print(f'✓ Detailed benchmark report saved: {report_file}')
        print('⚡ Benchmarking suite complete\n')

    async def _generate_final_report(self) -> None:
        """Generate a comprehensive final report."""
        print('📋 PHASE 8: Comprehensive Analysis Report Generation')
        print('-' * 50)

        # Stop metrics collection
        await self.metrics_collector.stop_collection()

        # Generate final comprehensive report
        report_lines = []

        report_lines.extend(
            [
                '=' * 100,
                'THOTH PERFORMANCE ANALYSIS - COMPREHENSIVE REPORT',
                '=' * 100,
                f'Generated: {time.strftime("%Y-%m-%d %H:%M:%S")}',
                'Analysis Duration: Comprehensive system evaluation',
                '',
            ]
        )

        # System overview
        system_summary = self.dashboard.get_dashboard_summary()
        report_lines.extend(
            [
                'EXECUTIVE SUMMARY',
                '-' * 50,
                f'Overall System Health: {system_summary.get("system_health", "unknown").upper()}',
                f'Performance Recommendations: {system_summary.get("recommendations_count", 0)} identified',
                'Key Performance Indicators:',
                f'  • CPU Utilization: {system_summary.get("key_metrics", {}).get("cpu_usage", "N/A")}',
                f'  • Memory Usage: {system_summary.get("key_metrics", {}).get("memory_usage", "N/A")}',
                f'  • Total Processing Cost: {system_summary.get("key_metrics", {}).get("total_cost", "$0.00")}',
                '',
            ]
        )

        # Performance insights
        report_lines.extend(
            [
                'KEY PERFORMANCE INSIGHTS',
                '-' * 50,
                '• Real-time metrics collection successfully implemented',
                '• Pipeline bottleneck identification operational',
                '• Workflow optimization monitoring active',
                '• Reliability analysis and error pattern detection functional',
                '• Automated optimization recommendations generated',
                '• Interactive performance dashboard created',
                '• Comprehensive benchmarking suite validated',
                '',
            ]
        )

        # Recommendations
        report_lines.extend(
            [
                'NEXT STEPS & RECOMMENDATIONS',
                '-' * 50,
                '1. Deploy performance monitoring in production environment',
                '2. Establish baseline performance metrics and SLAs',
                '3. Implement automated alerting for critical performance issues',
                '4. Schedule regular performance benchmark testing',
                '5. Integrate optimization recommendations into CI/CD pipeline',
                '6. Set up automated performance regression detection',
                '',
            ]
        )

        # File locations
        workspace_dir = self.config.workspace_dir
        report_lines.extend(
            [
                'GENERATED ARTIFACTS',
                '-' * 50,
                f'• Performance Dashboard: {workspace_dir}/dashboard/',
                f'• Pipeline Analysis: {workspace_dir}/analysis/pipelines/',
                f'• Workflow Data: {workspace_dir}/workflows/',
                f'• Reliability Reports: {workspace_dir}/reliability/',
                f'• Optimization Reports: {workspace_dir}/optimizations/',
                f'• Benchmark Results: {workspace_dir}/benchmarks/',
                f'• Metrics Data: {workspace_dir}/metrics/',
                '',
            ]
        )

        report_lines.extend(
            ['=' * 100, 'END OF COMPREHENSIVE ANALYSIS REPORT', '=' * 100]
        )

        # Save comprehensive report
        report_content = '\n'.join(report_lines)
        report_file = workspace_dir / 'comprehensive_performance_analysis_report.txt'

        with open(report_file, 'w') as f:
            f.write(report_content)

        print(f'✓ Comprehensive analysis report generated: {report_file}')
        print('✓ All performance analysis artifacts saved to workspace')
        print('📋 Final report generation complete\n')

        # Print summary to console
        print('\n' + report_content)


async def main():
    """Main demonstration function."""
    parser = argparse.ArgumentParser(
        description='Thoth Performance Analysis System Demonstration'
    )
    parser.add_argument(
        '--demo-mode', action='store_true', help='Run in demo mode with simulated data'
    )
    parser.add_argument(
        '--generate-report',
        action='store_true',
        help='Generate comprehensive report only',
    )

    args = parser.parse_args()

    try:
        # Initialize demo
        demo = PerformanceAnalysisDemo(demo_mode=args.demo_mode)

        if args.generate_report:
            print('Generating comprehensive performance analysis report...')
            await demo._generate_final_report()
        else:
            # Run full demonstration
            await demo.run_comprehensive_demo()

    except KeyboardInterrupt:
        logger.info('Demo interrupted by user')
        print(
            '\n⚠️  Demo interrupted. Partial results may be available in workspace directory.'
        )

    except Exception as e:
        logger.error(f'Demo failed: {e}')
        print(f'\n❌ Demo failed with error: {e}')
        print('Check logs for detailed error information.')
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
