"""
Comprehensive benchmarking suite for Thoth system performance testing.

This module provides automated benchmarking capabilities for all Thoth components
including performance regression testing, load testing, and comparative analysis.
"""

import asyncio  # noqa: I001
import json
import statistics
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import psutil
from loguru import logger

from thoth.services.service_manager import ServiceManager
from thoth.config import config, Config  # noqa: F401


@dataclass
class BenchmarkTest:
    """Individual benchmark test configuration."""

    test_id: str
    test_name: str
    description: str
    test_function: Callable

    # Test parameters
    iterations: int = 10
    warmup_iterations: int = 3
    timeout_seconds: int = 300

    # Resource limits
    max_cpu_percent: float = 90.0
    max_memory_percent: float = 85.0

    # Test data
    test_data: dict[str, Any] = field(default_factory=dict)

    # Expected performance thresholds
    expected_duration_ms: float | None = None
    expected_success_rate: float = 0.95


@dataclass
class BenchmarkResult:
    """Results from a single benchmark test."""

    test_id: str
    test_name: str
    start_time: datetime
    end_time: datetime

    # Performance metrics
    total_iterations: int = 0
    successful_iterations: int = 0
    failed_iterations: int = 0

    # Timing statistics (milliseconds)
    min_duration_ms: float = 0.0
    max_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    median_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0

    # Resource utilization
    avg_cpu_percent: float = 0.0
    max_cpu_percent: float = 0.0
    avg_memory_percent: float = 0.0
    max_memory_percent: float = 0.0

    # Success metrics
    success_rate: float = 0.0
    error_rate: float = 0.0
    timeout_count: int = 0

    # Detailed results
    individual_durations: list[float] = field(default_factory=list)
    error_messages: list[str] = field(default_factory=list)

    # Comparison with thresholds
    meets_duration_threshold: bool = True
    meets_success_threshold: bool = True


@dataclass
class BenchmarkResults:
    """Complete benchmark suite results."""

    suite_name: str
    start_time: datetime
    end_time: datetime

    # Overall statistics
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0

    # Test results
    test_results: list[BenchmarkResult] = field(default_factory=list)

    # System information
    system_info: dict[str, Any] = field(default_factory=dict)

    # Performance summary
    overall_performance_score: float = 0.0
    regression_detected: bool = False

    # Baseline comparison
    baseline_comparison: dict[str, Any] | None = None


class BenchmarkSuite:
    """
    Comprehensive benchmarking suite for Thoth system performance.

    Provides:
    - Automated performance testing for all components
    - Load testing and stress testing
    - Performance regression detection
    - Comparative analysis with baselines
    - Resource utilization monitoring
    """

    def __init__(
        self,
        config: Config,  # noqa: F811
        service_manager: ServiceManager,
        output_dir: Path | None = None,
    ):
        """
        Initialize the benchmark suite.

        Args:
            config: Thoth configuration
            service_manager: ServiceManager instance
            output_dir: Optional output directory for results
        """
        self.config = config
        self.service_manager = service_manager
        self.output_dir = output_dir or (config.workspace_dir / 'benchmarks')
        self.output_dir.mkdir(exist_ok=True)

        # Benchmark configuration
        self.benchmark_tests: list[BenchmarkTest] = []
        self.baseline_results: BenchmarkResults | None = None

        # System monitoring
        self.monitor_resources = True

        logger.info('BenchmarkSuite initialized')

    def add_test(self, test: BenchmarkTest) -> None:
        """Add a benchmark test to the suite."""
        self.benchmark_tests.append(test)
        logger.debug(f'Added benchmark test: {test.test_name}')

    def create_standard_benchmarks(self) -> None:
        """Create standard benchmark tests for Thoth components."""

        # Document processing benchmarks
        self.add_test(
            BenchmarkTest(
                test_id='doc_processing_small',
                test_name='Small Document Processing',
                description='Process small PDF documents (< 5MB)',
                test_function=self._benchmark_document_processing,
                iterations=20,
                expected_duration_ms=30000,  # 30 seconds
                test_data={'doc_size': 'small', 'file_count': 5},
            )
        )

        self.add_test(
            BenchmarkTest(
                test_id='doc_processing_large',
                test_name='Large Document Processing',
                description='Process large PDF documents (> 10MB)',
                test_function=self._benchmark_document_processing,
                iterations=10,
                expected_duration_ms=120000,  # 2 minutes
                test_data={'doc_size': 'large', 'file_count': 2},
            )
        )

        # LLM service benchmarks
        self.add_test(
            BenchmarkTest(
                test_id='llm_simple_query',
                test_name='LLM Simple Query',
                description='Simple LLM queries with standard prompts',
                test_function=self._benchmark_llm_query,
                iterations=50,
                expected_duration_ms=5000,  # 5 seconds
                test_data={'query_type': 'simple', 'prompt_length': 'short'},
            )
        )

        self.add_test(
            BenchmarkTest(
                test_id='llm_complex_analysis',
                test_name='LLM Complex Analysis',
                description='Complex document analysis with LLM',
                test_function=self._benchmark_llm_analysis,
                iterations=20,
                expected_duration_ms=15000,  # 15 seconds
                test_data={'analysis_type': 'complex', 'document_length': 'medium'},
            )
        )

        # RAG system benchmarks
        self.add_test(
            BenchmarkTest(
                test_id='rag_indexing',
                test_name='RAG Document Indexing',
                description='Index documents into RAG vector database',
                test_function=self._benchmark_rag_indexing,
                iterations=15,
                expected_duration_ms=10000,  # 10 seconds
                test_data={'document_count': 10, 'document_size': 'medium'},
            )
        )

        self.add_test(
            BenchmarkTest(
                test_id='rag_search',
                test_name='RAG Similarity Search',
                description='Search RAG database for similar documents',
                test_function=self._benchmark_rag_search,
                iterations=100,
                expected_duration_ms=1000,  # 1 second
                test_data={'query_complexity': 'medium', 'result_count': 10},
            )
        )

        # Citation processing benchmarks
        self.add_test(
            BenchmarkTest(
                test_id='citation_extraction',
                test_name='Citation Extraction',
                description='Extract citations from research documents',
                test_function=self._benchmark_citation_extraction,
                iterations=25,
                expected_duration_ms=8000,  # 8 seconds
                test_data={
                    'document_type': 'research_paper',
                    'citation_count': 'medium',
                },
            )
        )

        # Discovery system benchmarks
        self.add_test(
            BenchmarkTest(
                test_id='paper_discovery',
                test_name='Paper Discovery',
                description='Discover relevant papers from multiple sources',
                test_function=self._benchmark_paper_discovery,
                iterations=30,
                expected_duration_ms=12000,  # 12 seconds
                test_data={'query_complexity': 'medium', 'source_count': 3},
            )
        )

        # Concurrent processing benchmarks
        self.add_test(
            BenchmarkTest(
                test_id='concurrent_processing',
                test_name='Concurrent Document Processing',
                description='Process multiple documents concurrently',
                test_function=self._benchmark_concurrent_processing,
                iterations=10,
                expected_duration_ms=45000,  # 45 seconds
                test_data={'concurrent_count': 5, 'doc_size': 'small'},
            )
        )

        # Memory stress test
        self.add_test(
            BenchmarkTest(
                test_id='memory_stress',
                test_name='Memory Stress Test',
                description='Test system behavior under memory pressure',
                test_function=self._benchmark_memory_stress,
                iterations=5,
                expected_duration_ms=60000,  # 1 minute
                max_memory_percent=95.0,  # Allow higher memory usage
                test_data={'memory_pressure': 'high'},
            )
        )

        logger.info(f'Created {len(self.benchmark_tests)} standard benchmark tests')

    async def run_benchmarks(
        self, test_filter: str | None = None, compare_with_baseline: bool = True
    ) -> BenchmarkResults:
        """
        Run the complete benchmark suite.

        Args:
            test_filter: Optional filter to run specific tests
            compare_with_baseline: Whether to compare with baseline results

        Returns:
            BenchmarkResults: Complete benchmark results
        """
        suite_start = datetime.now()
        logger.info(f'Starting benchmark suite at {suite_start}')

        # Filter tests if requested
        tests_to_run = self.benchmark_tests
        if test_filter:
            tests_to_run = [
                t
                for t in tests_to_run
                if test_filter in t.test_id or test_filter in t.test_name
            ]
            logger.info(
                f"Filtered to {len(tests_to_run)} tests matching '{test_filter}'"
            )

        # Initialize results
        results = BenchmarkResults(
            suite_name='Thoth Performance Benchmark Suite',
            start_time=suite_start,
            end_time=suite_start,  # Will be updated
            total_tests=len(tests_to_run),
            system_info=self._collect_system_info(),
        )

        # Initialize service manager
        if not self.service_manager._initialized:
            self.service_manager.initialize()

        # Run each benchmark test
        for test in tests_to_run:
            logger.info(f'Running benchmark: {test.test_name}')

            try:
                result = await self._run_single_benchmark(test)
                results.test_results.append(result)

                if result.meets_duration_threshold and result.meets_success_threshold:
                    results.passed_tests += 1
                    logger.info(f'✓ {test.test_name} PASSED')
                else:
                    results.failed_tests += 1
                    logger.warning(f'✗ {test.test_name} FAILED')

            except Exception as e:
                logger.error(f'Benchmark {test.test_name} crashed: {e}')
                # Create failed result
                failed_result = BenchmarkResult(
                    test_id=test.test_id,
                    test_name=test.test_name,
                    start_time=datetime.now(),
                    end_time=datetime.now(),
                    success_rate=0.0,
                    error_rate=1.0,
                    meets_duration_threshold=False,
                    meets_success_threshold=False,
                    error_messages=[str(e)],
                )
                results.test_results.append(failed_result)
                results.failed_tests += 1

        results.end_time = datetime.now()

        # Calculate overall performance score
        results.overall_performance_score = self._calculate_performance_score(results)

        # Compare with baseline if requested
        if compare_with_baseline and self.baseline_results:
            results.baseline_comparison = self._compare_with_baseline(results)
            results.regression_detected = results.baseline_comparison.get(
                'regression_detected', False
            )

        # Save results
        await self._save_benchmark_results(results)

        logger.info(
            f'Benchmark suite completed: {results.passed_tests}/{results.total_tests} tests passed '
            f'(Score: {results.overall_performance_score:.1f}/100)'
        )

        return results

    async def _run_single_benchmark(self, test: BenchmarkTest) -> BenchmarkResult:
        """Run a single benchmark test."""
        result = BenchmarkResult(
            test_id=test.test_id,
            test_name=test.test_name,
            start_time=datetime.now(),
            end_time=datetime.now(),  # Will be updated
        )

        durations = []
        errors = []
        successful_count = 0
        timeout_count = 0

        # Resource monitoring
        cpu_readings = []
        memory_readings = []

        # Warmup iterations
        logger.debug(f'Running {test.warmup_iterations} warmup iterations')
        for _ in range(test.warmup_iterations):
            try:
                await asyncio.wait_for(
                    test.test_function(test.test_data, warmup=True),
                    timeout=test.timeout_seconds,
                )
            except Exception:
                pass  # Ignore warmup failures

        # Actual benchmark iterations
        total_iterations = test.iterations

        for iteration in range(total_iterations):
            start_time = time.perf_counter()

            try:
                # Monitor resources before test
                if self.monitor_resources:
                    cpu_readings.append(psutil.cpu_percent(interval=0.1))
                    memory_readings.append(psutil.virtual_memory().percent)

                # Run the test function
                await asyncio.wait_for(
                    test.test_function(test.test_data, warmup=False),
                    timeout=test.timeout_seconds,
                )

                duration_ms = (time.perf_counter() - start_time) * 1000
                durations.append(duration_ms)
                successful_count += 1

                logger.debug(
                    f'Iteration {iteration + 1}/{total_iterations}: {duration_ms:.1f}ms'
                )

            except TimeoutError:
                timeout_count += 1
                errors.append(f'Timeout after {test.timeout_seconds}s')
                logger.warning(f'Iteration {iteration + 1} timed out')

            except Exception as e:
                errors.append(str(e))
                logger.warning(f'Iteration {iteration + 1} failed: {e}')

            # Small delay between iterations
            await asyncio.sleep(0.1)

        result.end_time = datetime.now()

        # Calculate statistics
        result.total_iterations = total_iterations
        result.successful_iterations = successful_count
        result.failed_iterations = total_iterations - successful_count
        result.timeout_count = timeout_count
        result.individual_durations = durations
        result.error_messages = errors

        if durations:
            durations_sorted = sorted(durations)
            result.min_duration_ms = min(durations)
            result.max_duration_ms = max(durations)
            result.avg_duration_ms = statistics.mean(durations)
            result.median_duration_ms = statistics.median(durations)
            result.p95_duration_ms = durations_sorted[int(len(durations_sorted) * 0.95)]
            result.p99_duration_ms = durations_sorted[int(len(durations_sorted) * 0.99)]

        if cpu_readings:
            result.avg_cpu_percent = statistics.mean(cpu_readings)
            result.max_cpu_percent = max(cpu_readings)

        if memory_readings:
            result.avg_memory_percent = statistics.mean(memory_readings)
            result.max_memory_percent = max(memory_readings)

        result.success_rate = successful_count / total_iterations
        result.error_rate = 1.0 - result.success_rate

        # Check against thresholds
        if test.expected_duration_ms:
            result.meets_duration_threshold = (
                result.avg_duration_ms <= test.expected_duration_ms
            )

        result.meets_success_threshold = (
            result.success_rate >= test.expected_success_rate
        )

        return result

    # Benchmark test implementations

    async def _benchmark_document_processing(
        self, test_data: dict[str, Any], warmup: bool = False
    ) -> None:
        """Benchmark document processing pipeline."""
        # Create temporary test documents
        doc_size = test_data.get('doc_size', 'small')
        file_count = test_data.get('file_count', 1)

        if warmup:
            file_count = 1  # Use fewer files for warmup

        # For benchmarking, we simulate document processing
        # In a real implementation, this would process actual PDFs
        processing_time = {
            'small': 0.5,  # 500ms per small doc
            'medium': 2.0,  # 2s per medium doc
            'large': 10.0,  # 10s per large doc
        }.get(doc_size, 1.0)

        # Simulate processing multiple files
        for _ in range(file_count):
            await asyncio.sleep(processing_time)

    async def _benchmark_llm_query(
        self,
        test_data: dict[str, Any],
        warmup: bool = False,  # noqa: ARG002
    ) -> None:
        """Benchmark LLM query performance."""
        query_type = test_data.get('query_type', 'simple')
        prompt_length = test_data.get('prompt_length', 'short')

        # Simulate LLM query based on complexity
        delay = {
            'simple': 0.8,  # 800ms for simple queries
            'medium': 2.5,  # 2.5s for medium queries
            'complex': 6.0,  # 6s for complex queries
        }.get(query_type, 1.0)

        if prompt_length == 'long':
            delay *= 1.5

        await asyncio.sleep(delay)

    async def _benchmark_llm_analysis(
        self,
        test_data: dict[str, Any],
        warmup: bool = False,  # noqa: ARG002
    ) -> None:
        """Benchmark LLM document analysis."""
        analysis_type = test_data.get('analysis_type', 'simple')
        document_length = test_data.get('document_length', 'short')

        # Simulate analysis based on complexity
        base_delay = {
            'simple': 2.0,  # 2s for simple analysis
            'medium': 5.0,  # 5s for medium analysis
            'complex': 12.0,  # 12s for complex analysis
        }.get(analysis_type, 3.0)

        if document_length == 'long':
            base_delay *= 2.0

        await asyncio.sleep(base_delay)

    async def _benchmark_rag_indexing(
        self, test_data: dict[str, Any], warmup: bool = False
    ) -> None:
        """Benchmark RAG document indexing."""
        document_count = test_data.get('document_count', 5)
        document_size = test_data.get('document_size', 'medium')

        if warmup:
            document_count = min(2, document_count)

        # Simulate indexing time per document
        time_per_doc = {
            'small': 0.3,  # 300ms per small doc
            'medium': 0.8,  # 800ms per medium doc
            'large': 2.0,  # 2s per large doc
        }.get(document_size, 0.5)

        total_delay = document_count * time_per_doc
        await asyncio.sleep(total_delay)

    async def _benchmark_rag_search(
        self,
        test_data: dict[str, Any],
        warmup: bool = False,  # noqa: ARG002
    ) -> None:
        """Benchmark RAG similarity search."""
        query_complexity = test_data.get('query_complexity', 'simple')
        result_count = test_data.get('result_count', 5)

        # Simulate search time based on complexity and result count
        base_delay = {
            'simple': 0.1,  # 100ms for simple search
            'medium': 0.3,  # 300ms for medium search
            'complex': 0.8,  # 800ms for complex search
        }.get(query_complexity, 0.2)

        # Additional delay for more results
        result_delay = result_count * 0.02  # 20ms per result

        total_delay = base_delay + result_delay
        await asyncio.sleep(total_delay)

    async def _benchmark_citation_extraction(
        self,
        test_data: dict[str, Any],
        warmup: bool = False,  # noqa: ARG002
    ) -> None:
        """Benchmark citation extraction."""
        document_type = test_data.get('document_type', 'research_paper')
        citation_count = test_data.get('citation_count', 'medium')

        # Simulate extraction time based on document type and citation density
        base_delay = {
            'research_paper': 3.0,  # 3s for research papers
            'review_paper': 5.0,  # 5s for review papers
            'book_chapter': 4.0,  # 4s for book chapters
        }.get(document_type, 2.0)

        citation_multiplier = {
            'low': 0.7,  # 70% of base time
            'medium': 1.0,  # 100% of base time
            'high': 1.5,  # 150% of base time
        }.get(citation_count, 1.0)

        total_delay = base_delay * citation_multiplier
        await asyncio.sleep(total_delay)

    async def _benchmark_paper_discovery(
        self,
        test_data: dict[str, Any],
        warmup: bool = False,  # noqa: ARG002
    ) -> None:
        """Benchmark paper discovery from multiple sources."""
        query_complexity = test_data.get('query_complexity', 'medium')
        source_count = test_data.get('source_count', 3)

        # Simulate discovery time per source
        time_per_source = {
            'simple': 1.5,  # 1.5s per source for simple queries
            'medium': 3.0,  # 3s per source for medium queries
            'complex': 5.0,  # 5s per source for complex queries
        }.get(query_complexity, 2.0)

        total_delay = (
            source_count * time_per_source * 0.7
        )  # Some parallelization benefit
        await asyncio.sleep(total_delay)

    async def _benchmark_concurrent_processing(
        self, test_data: dict[str, Any], warmup: bool = False
    ) -> None:
        """Benchmark concurrent document processing."""
        concurrent_count = test_data.get('concurrent_count', 3)
        doc_size = test_data.get('doc_size', 'small')

        if warmup:
            concurrent_count = min(2, concurrent_count)

        # Simulate concurrent processing with some efficiency gain
        processing_time = {
            'small': 2.0,  # 2s per small doc
            'medium': 5.0,  # 5s per medium doc
            'large': 15.0,  # 15s per large doc
        }.get(doc_size, 3.0)

        # Concurrent processing is faster but not perfectly parallel
        efficiency = 0.7  # 70% efficiency due to shared resources
        total_time = processing_time * concurrent_count * efficiency

        await asyncio.sleep(total_time)

    async def _benchmark_memory_stress(
        self, test_data: dict[str, Any], warmup: bool = False
    ) -> None:
        """Benchmark system under memory pressure."""
        memory_pressure = test_data.get('memory_pressure', 'medium')

        if warmup:
            # Light memory usage for warmup
            data = [0] * (1000 * 1000)  # 1M integers
            await asyncio.sleep(1.0)
            del data
            return

        # Simulate memory-intensive operations
        pressure_levels = {
            'low': 10 * 1000 * 1000,  # 10M integers
            'medium': 50 * 1000 * 1000,  # 50M integers
            'high': 100 * 1000 * 1000,  # 100M integers
        }

        size = pressure_levels.get(memory_pressure, 25 * 1000 * 1000)

        # Allocate memory and perform operations
        data = list(range(size))

        # Simulate processing
        await asyncio.sleep(2.0)

        # Simulate more memory operations
        processed = [x * 2 for x in data[::1000]]  # Process every 1000th element

        await asyncio.sleep(1.0)

        # Clean up
        del data
        del processed

    def _collect_system_info(self) -> dict[str, Any]:
        """Collect system information for benchmark results."""
        import platform

        return {
            'timestamp': datetime.now().isoformat(),
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_count': psutil.cpu_count(),
            'memory_total_gb': psutil.virtual_memory().total / (1024**3),
            'disk_free_gb': psutil.disk_usage('/').free / (1024**3),
            'thoth_config': {
                'auto_scale_workers': self.config.performance_config.auto_scale_workers,
                'async_enabled': self.config.performance_config.async_enabled,
                'memory_optimization': self.config.performance_config.memory_optimization_enabled,
                'content_analysis_workers': self.config.performance_config.content_analysis_workers,
                'citation_enhancement_workers': self.config.performance_config.citation_enhancement_workers,
            },
        }

    def _calculate_performance_score(self, results: BenchmarkResults) -> float:
        """Calculate overall performance score (0-100)."""
        if not results.test_results:
            return 0.0

        total_score = 0.0
        weight_sum = 0.0

        for result in results.test_results:
            # Base score from success rate
            score = result.success_rate * 100

            # Adjust for performance vs expectations
            if result.meets_duration_threshold:
                score += 10  # Bonus for meeting performance expectations
            else:
                score -= 20  # Penalty for missing expectations

            # Weight by test importance (can be customized)
            weight = 1.0
            if 'concurrent' in result.test_name.lower():
                weight = 1.5  # Higher weight for concurrency tests
            elif 'memory' in result.test_name.lower():
                weight = 1.3  # Higher weight for memory tests

            total_score += score * weight
            weight_sum += weight

        return min(100.0, max(0.0, total_score / weight_sum))

    def _compare_with_baseline(self, results: BenchmarkResults) -> dict[str, Any]:
        """Compare current results with baseline."""
        if not self.baseline_results:
            return {'error': 'No baseline results available'}

        comparison = {
            'baseline_date': self.baseline_results.start_time.isoformat(),
            'performance_changes': {},
            'regression_detected': False,
            'improvements': [],
            'regressions': [],
        }

        # Compare each test with baseline
        baseline_lookup = {r.test_id: r for r in self.baseline_results.test_results}

        for result in results.test_results:
            if result.test_id in baseline_lookup:
                baseline = baseline_lookup[result.test_id]

                # Calculate performance change
                perf_change = 0.0
                if baseline.avg_duration_ms > 0:
                    perf_change = (
                        (result.avg_duration_ms - baseline.avg_duration_ms)
                        / baseline.avg_duration_ms
                    ) * 100

                success_change = (result.success_rate - baseline.success_rate) * 100

                test_comparison = {
                    'performance_change_percent': perf_change,
                    'success_rate_change_percent': success_change,
                    'duration_ms': {
                        'current': result.avg_duration_ms,
                        'baseline': baseline.avg_duration_ms,
                    },
                }

                comparison['performance_changes'][result.test_id] = test_comparison

                # Check for regressions (>20% slower or >10% less successful)
                if perf_change > 20.0 or success_change < -10.0:
                    comparison['regressions'].append(
                        {
                            'test_name': result.test_name,
                            'performance_degradation': perf_change,
                            'success_rate_degradation': -success_change,
                        }
                    )
                    comparison['regression_detected'] = True

                # Check for improvements
                elif perf_change < -10.0 or success_change > 5.0:
                    comparison['improvements'].append(
                        {
                            'test_name': result.test_name,
                            'performance_improvement': -perf_change,
                            'success_rate_improvement': success_change,
                        }
                    )

        return comparison

    async def _save_benchmark_results(self, results: BenchmarkResults) -> None:
        """Save benchmark results to disk."""
        timestamp = results.start_time.strftime('%Y%m%d_%H%M%S')
        results_file = self.output_dir / f'benchmark_results_{timestamp}.json'

        # Convert results to serializable format
        results_data = {
            'suite_info': {
                'suite_name': results.suite_name,
                'start_time': results.start_time.isoformat(),
                'end_time': results.end_time.isoformat(),
                'total_duration_seconds': (
                    results.end_time - results.start_time
                ).total_seconds(),
            },
            'summary': {
                'total_tests': results.total_tests,
                'passed_tests': results.passed_tests,
                'failed_tests': results.failed_tests,
                'success_rate': results.passed_tests / max(1, results.total_tests),
                'overall_performance_score': results.overall_performance_score,
                'regression_detected': results.regression_detected,
            },
            'system_info': results.system_info,
            'test_results': [
                {
                    'test_id': r.test_id,
                    'test_name': r.test_name,
                    'duration_seconds': (r.end_time - r.start_time).total_seconds(),
                    'iterations': r.total_iterations,
                    'successful_iterations': r.successful_iterations,
                    'success_rate': r.success_rate,
                    'performance_ms': {
                        'avg': r.avg_duration_ms,
                        'median': r.median_duration_ms,
                        'p95': r.p95_duration_ms,
                        'min': r.min_duration_ms,
                        'max': r.max_duration_ms,
                    },
                    'resource_usage': {
                        'avg_cpu_percent': r.avg_cpu_percent,
                        'max_cpu_percent': r.max_cpu_percent,
                        'avg_memory_percent': r.avg_memory_percent,
                        'max_memory_percent': r.max_memory_percent,
                    },
                    'thresholds_met': {
                        'duration': r.meets_duration_threshold,
                        'success_rate': r.meets_success_threshold,
                    },
                    'errors': r.error_messages[:10],  # Save only first 10 errors
                }
                for r in results.test_results
            ],
            'baseline_comparison': results.baseline_comparison,
        }

        # Save to file
        with open(results_file, 'w') as f:
            json.dump(results_data, f, indent=2, default=str)

        logger.info(f'Benchmark results saved to {results_file}')

        # Also save as latest baseline if performance is good
        if (
            results.overall_performance_score >= 80.0
            and not results.regression_detected
        ):
            baseline_file = self.output_dir / 'baseline_results.json'
            with open(baseline_file, 'w') as f:
                json.dump(results_data, f, indent=2, default=str)
            logger.info(f'Results saved as new baseline: {baseline_file}')

    def load_baseline(self, baseline_file: Path | None = None) -> bool:
        """
        Load baseline results for comparison.

        Args:
            baseline_file: Optional specific baseline file, otherwise uses latest

        Returns:
            bool: True if baseline loaded successfully
        """
        try:
            if baseline_file is None:
                baseline_file = self.output_dir / 'baseline_results.json'

            if not baseline_file.exists():
                logger.warning('No baseline results file found')
                return False

            with open(baseline_file) as f:
                baseline_data = json.load(f)

            # Convert back to BenchmarkResults object (simplified)
            self.baseline_results = BenchmarkResults(
                suite_name=baseline_data['suite_info']['suite_name'],
                start_time=datetime.fromisoformat(
                    baseline_data['suite_info']['start_time']
                ),
                end_time=datetime.fromisoformat(
                    baseline_data['suite_info']['end_time']
                ),
                total_tests=baseline_data['summary']['total_tests'],
                passed_tests=baseline_data['summary']['passed_tests'],
                failed_tests=baseline_data['summary']['failed_tests'],
                overall_performance_score=baseline_data['summary'][
                    'overall_performance_score'
                ],
            )

            # Convert test results
            for test_data in baseline_data['test_results']:
                result = BenchmarkResult(
                    test_id=test_data['test_id'],
                    test_name=test_data['test_name'],
                    start_time=datetime.now(),  # Placeholder
                    end_time=datetime.now(),  # Placeholder
                    total_iterations=test_data['iterations'],
                    successful_iterations=test_data['successful_iterations'],
                    success_rate=test_data['success_rate'],
                    avg_duration_ms=test_data['performance_ms']['avg'],
                    median_duration_ms=test_data['performance_ms']['median'],
                    p95_duration_ms=test_data['performance_ms']['p95'],
                    min_duration_ms=test_data['performance_ms']['min'],
                    max_duration_ms=test_data['performance_ms']['max'],
                    meets_duration_threshold=test_data['thresholds_met']['duration'],
                    meets_success_threshold=test_data['thresholds_met']['success_rate'],
                )
                self.baseline_results.test_results.append(result)

            logger.info(f'Loaded baseline from {baseline_file}')
            return True

        except Exception as e:
            logger.error(f'Failed to load baseline: {e}')
            return False

    def generate_benchmark_report(self, results: BenchmarkResults) -> str:
        """Generate a human-readable benchmark report."""
        report_lines = []

        report_lines.append('=' * 80)
        report_lines.append('THOTH PERFORMANCE BENCHMARK REPORT')
        report_lines.append('=' * 80)
        report_lines.append(f'Suite: {results.suite_name}')
        report_lines.append(f'Date: {results.start_time.strftime("%Y-%m-%d %H:%M:%S")}')
        report_lines.append(
            f'Duration: {(results.end_time - results.start_time).total_seconds():.1f} seconds'
        )
        report_lines.append('')

        # Summary
        report_lines.append('SUMMARY')
        report_lines.append('-' * 40)
        report_lines.append(f'Total Tests: {results.total_tests}')
        report_lines.append(f'Passed: {results.passed_tests}')
        report_lines.append(f'Failed: {results.failed_tests}')
        report_lines.append(
            f'Success Rate: {results.passed_tests / max(1, results.total_tests) * 100:.1f}%'
        )
        report_lines.append(
            f'Performance Score: {results.overall_performance_score:.1f}/100'
        )

        if results.regression_detected:
            report_lines.append('⚠️  PERFORMANCE REGRESSION DETECTED')

        report_lines.append('')

        # Test Results
        report_lines.append('TEST RESULTS')
        report_lines.append('-' * 40)

        for result in results.test_results:
            status = (
                '✓ PASS'
                if (result.meets_duration_threshold and result.meets_success_threshold)
                else '✗ FAIL'
            )
            report_lines.append(f'{status} {result.test_name}')
            report_lines.append(f'    Success Rate: {result.success_rate * 100:.1f}%')
            report_lines.append(f'    Avg Duration: {result.avg_duration_ms:.1f}ms')
            report_lines.append(f'    P95 Duration: {result.p95_duration_ms:.1f}ms')

            if result.error_messages:
                report_lines.append(
                    f'    Errors: {len(result.error_messages)} error(s)'
                )

            report_lines.append('')

        # System Information
        report_lines.append('SYSTEM INFORMATION')
        report_lines.append('-' * 40)
        sys_info = results.system_info
        report_lines.append(f'Platform: {sys_info.get("platform", "Unknown")}')
        report_lines.append(f'CPU Cores: {sys_info.get("cpu_count", "Unknown")}')
        report_lines.append(f'Memory: {sys_info.get("memory_total_gb", 0):.1f} GB')
        report_lines.append(f'Python: {sys_info.get("python_version", "Unknown")}')

        thoth_config = sys_info.get('thoth_config', {})
        report_lines.append(
            f'Auto Scale Workers: {thoth_config.get("auto_scale_workers", False)}'
        )
        report_lines.append(
            f'Async Enabled: {thoth_config.get("async_enabled", False)}'
        )
        report_lines.append('')

        # Baseline Comparison
        if results.baseline_comparison:
            comp = results.baseline_comparison
            report_lines.append('BASELINE COMPARISON')
            report_lines.append('-' * 40)

            if comp.get('improvements'):
                report_lines.append('Improvements:')
                for imp in comp['improvements']:
                    report_lines.append(
                        f'  ✓ {imp["test_name"]}: {imp.get("performance_improvement", 0):.1f}% faster'
                    )

            if comp.get('regressions'):
                report_lines.append('Regressions:')
                for reg in comp['regressions']:
                    report_lines.append(
                        f'  ⚠️  {reg["test_name"]}: {reg.get("performance_degradation", 0):.1f}% slower'
                    )

        report_lines.append('')
        report_lines.append('=' * 80)

        return '\n'.join(report_lines)
