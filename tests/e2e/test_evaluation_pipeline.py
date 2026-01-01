"""
End-to-End Evaluation Pipeline Tests.

This module tests the complete analysis evaluation workflow:
1. Ground truth generation from database papers
2. LLM-based paper analysis execution
3. Extraction accuracy measurement
4. Content quality evaluation
5. Strategy efficiency analysis
6. Report generation and export

Test Scenarios:
--------------
1. **Complete Evaluation Run**: Full pipeline with all metrics
2. **Ground Truth Generation**: Database sampling and annotation
3. **Analysis Execution**: LLM processing with strategy selection
4. **Metrics Calculation**: Accuracy, quality, and efficiency scoring
5. **Report Export**: JSON and human-readable formats

Success Criteria:
----------------
- Evaluation completes without errors
- All metrics within valid ranges (0-1)
- Ground truth properly structured
- Reports contain comprehensive results
- Performance meets targets
"""

import asyncio
import json
from pathlib import Path
from typing import List

import pytest
import pytest_asyncio
from loguru import logger

from thoth.analyze.evaluation.ground_truth import (
    AnalysisGroundTruthGenerator,
    AnalysisGroundTruthPair,
)
from thoth.analyze.evaluation.metrics import (
    AnalysisMetrics,
    calculate_analysis_metrics,
)
from thoth.analyze.evaluation.runner import run_analysis_evaluation
from thoth.config import Config
from thoth.services.postgres_service import PostgresService


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def ground_truth_generator(postgres_service: PostgresService):
    """Create ground truth generator with database connection."""
    return AnalysisGroundTruthGenerator(postgres_service)


@pytest.fixture
def mock_paper_data():
    """Create mock paper data for ground truth generation."""
    return {
        'paper_id': 'test_paper_001',
        'title': 'Property-Based Testing for Research Software',
        'content': '''
# Abstract
We present a comprehensive framework for property-based testing in research software.

# Introduction
Property-based testing validates code against universal properties rather than specific examples.

# Methods
We employed the Hypothesis framework for Python to generate test cases automatically.

# Results
Our approach discovered 15 edge cases that unit tests missed.

# Conclusion
Property-based testing significantly improves research software robustness.
        ''',
        'metadata': {
            'authors': ['John Doe', 'Jane Smith'],
            'year': 2023,
            'venue': 'Software Engineering Conference',
        },
    }


# ============================================================================
# Test Cases: Ground Truth Generation
# ============================================================================

@pytest.mark.e2e
@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_ground_truth_generation_from_database(
    ground_truth_generator: AnalysisGroundTruthGenerator,
    postgres_service: PostgresService,
    empty_database,
):
    """
    Test generating ground truth pairs from database papers.

    Validates:
    - Papers are sampled correctly
    - Content is extracted and formatted
    - Metadata is properly structured
    - Complexity scoring works
    """
    # Insert test papers into database
    async with postgres_service.pool.acquire() as conn:
        await conn.execute(
            '''
            INSERT INTO papers (title, content, authors, year)
            VALUES
                ('Paper 1', 'Test content 1', ARRAY['Author 1'], 2023),
                ('Paper 2', 'Test content 2 with more words and sentences', ARRAY['Author 2'], 2022),
                ('Paper 3', 'Very long content ' || repeat('test ', 1000), ARRAY['Author 3'], 2021)
            '''
        )

    # Generate ground truth
    ground_truth = await ground_truth_generator.generate_from_database(num_samples=3)

    # Validate structure
    assert len(ground_truth) == 3
    for gt_pair in ground_truth:
        assert isinstance(gt_pair, AnalysisGroundTruthPair)
        assert gt_pair.paper_id is not None
        assert gt_pair.paper_content is not None
        assert gt_pair.expected_analysis is not None
        assert 0 <= gt_pair.complexity <= 1.0
        assert gt_pair.content_length > 0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_ground_truth_save_and_load(
    ground_truth_generator: AnalysisGroundTruthGenerator,
    temp_directory: Path,
    mock_paper_data,
):
    """
    Test saving and loading ground truth to/from JSON.

    Ensures ground truth can be persisted and reused.
    """
    # Create ground truth pairs
    ground_truth = [
        AnalysisGroundTruthPair(
            paper_id=mock_paper_data['paper_id'],
            paper_content=mock_paper_data['content'],
            expected_analysis={
                'summary': 'Test summary',
                'key_points': ['Point 1', 'Point 2'],
                'tags': ['testing', 'software-engineering'],
            },
            complexity=0.6,
            content_length=len(mock_paper_data['content']),
            expected_strategy='direct',
        )
    ]

    # Save to file
    output_path = temp_directory / 'ground_truth.json'
    await ground_truth_generator.save_ground_truth(ground_truth, output_path)

    assert output_path.exists()

    # Load from file
    loaded_ground_truth = await ground_truth_generator.load_ground_truth(output_path)

    # Verify loaded data matches original
    assert len(loaded_ground_truth) == len(ground_truth)
    assert loaded_ground_truth[0].paper_id == ground_truth[0].paper_id
    assert loaded_ground_truth[0].complexity == ground_truth[0].complexity


# ============================================================================
# Test Cases: Metrics Calculation
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_extraction_metrics_calculation():
    """
    Test extraction accuracy metrics calculation.

    Validates:
    - Field completeness scoring
    - Required vs optional field handling
    - Field-wise accuracy computation
    """
    from thoth.utilities.schemas.analysis import AnalysisResponse

    # Create ground truth
    ground_truth = [
        AnalysisGroundTruthPair(
            paper_id='paper_1',
            paper_content='Test content',
            expected_analysis={
                'summary': 'Expected summary',
                'key_points': ['Point 1', 'Point 2', 'Point 3'],
                'methodology': 'Expected methodology',
                'tags': ['tag1', 'tag2'],
            },
            complexity=0.5,
            content_length=1000,
            expected_strategy='direct',
        )
    ]

    # Create predicted analysis
    predicted = [
        AnalysisResponse(
            summary='Predicted summary',
            key_points=['Point 1', 'Point 2'],  # Missing one point
            methodology='Predicted methodology',
            tags=['tag1', 'tag2', 'tag3'],  # Extra tag
        )
    ]

    # Calculate metrics
    metrics = calculate_analysis_metrics(
        ground_truth_list=ground_truth,
        predicted_list=predicted,
        timing_data=[],
    )

    # Validate extraction metrics
    assert 0.0 <= metrics.extraction.field_completeness <= 1.0
    assert 0.0 <= metrics.extraction.required_fields_completeness <= 1.0
    assert metrics.extraction.total_samples == 1


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_content_quality_metrics_calculation():
    """
    Test content quality metrics calculation.

    Validates:
    - Summary coherence scoring
    - Key points relevance measurement
    - Tag appropriateness evaluation
    """
    from thoth.utilities.schemas.analysis import AnalysisResponse

    ground_truth = [
        AnalysisGroundTruthPair(
            paper_id='paper_1',
            paper_content='Test content',
            expected_analysis={
                'summary': 'This paper presents a novel approach to testing.',
                'key_points': [
                    'Novel testing framework',
                    'Property-based validation',
                    'Edge case discovery',
                ],
                'tags': ['testing', 'software-engineering'],
            },
            complexity=0.5,
            content_length=1000,
            expected_strategy='direct',
        )
    ]

    predicted = [
        AnalysisResponse(
            summary='The paper introduces a new testing methodology.',
            key_points=[
                'Testing framework',
                'Property validation',
                'Edge cases',
            ],
            tags=['testing', 'engineering', 'validation'],
        )
    ]

    metrics = calculate_analysis_metrics(
        ground_truth_list=ground_truth,
        predicted_list=predicted,
        timing_data=[],
    )

    # Validate content quality metrics
    assert 0.0 <= metrics.content_quality.summary_coherence <= 1.0
    assert 0.0 <= metrics.content_quality.key_points_relevance <= 1.0
    assert 0.0 <= metrics.content_quality.tag_appropriateness <= 1.0


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_strategy_efficiency_metrics():
    """
    Test strategy efficiency metrics calculation.

    Validates:
    - Strategy selection accuracy
    - Processing time tracking
    - Quality-speed tradeoff analysis
    """
    from thoth.utilities.schemas.analysis import AnalysisResponse

    ground_truth = [
        AnalysisGroundTruthPair(
            paper_id='paper_1',
            paper_content='Short content',
            expected_analysis={'summary': 'Test'},
            complexity=0.3,
            content_length=500,
            expected_strategy='direct',  # Short paper should use direct
        ),
        AnalysisGroundTruthPair(
            paper_id='paper_2',
            paper_content='Long content ' * 1000,
            expected_analysis={'summary': 'Test'},
            complexity=0.8,
            content_length=10000,
            expected_strategy='map_reduce',  # Long paper should use map-reduce
        ),
    ]

    predicted = [
        AnalysisResponse(summary='Predicted 1'),
        AnalysisResponse(summary='Predicted 2'),
    ]

    timing_data = [
        {
            'paper_id': 'paper_1',
            'expected_strategy': 'direct',
            'processing_time_ms': 150.0,
        },
        {
            'paper_id': 'paper_2',
            'expected_strategy': 'map_reduce',
            'processing_time_ms': 850.0,
        },
    ]

    metrics = calculate_analysis_metrics(
        ground_truth_list=ground_truth,
        predicted_list=predicted,
        timing_data=timing_data,
    )

    # Validate strategy metrics
    assert 0.0 <= metrics.strategy_efficiency.strategy_selection_accuracy <= 1.0
    assert metrics.strategy_efficiency.total_samples == 2
    assert len(metrics.strategy_efficiency.avg_processing_time_by_strategy) > 0


# ============================================================================
# Test Cases: Complete Evaluation Pipeline
# ============================================================================

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_complete_evaluation_pipeline_run(
    postgres_service: PostgresService,
    temp_directory: Path,
    empty_database,
):
    """
    Test complete evaluation pipeline from start to finish.

    This is the main integration test covering:
    1. Ground truth generation
    2. Analysis execution
    3. Metrics calculation
    4. Report generation

    NOTE: This test uses mock LLM service to avoid API costs.
    """
    # Insert test papers
    async with postgres_service.pool.acquire() as conn:
        for i in range(5):
            await conn.execute(
                '''
                INSERT INTO papers (title, content, authors, year)
                VALUES ($1, $2, $3, $4)
                ''',
                f'Test Paper {i}',
                f'Abstract: Test content for paper {i}.\n\n'
                f'Introduction: Background information.\n\n'
                f'Methods: Methodology description.\n\n'
                f'Results: Key findings.\n\n'
                f'Conclusion: Summary of contributions.',
                [f'Author {i}'],
                2023 - i,
            )

    # Mock LLM service to avoid API calls
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            'thoth.analyze.llm_processor.LLMProcessor.analyze_content',
            lambda self, markdown_path: {
                'summary': f'Auto-generated summary for {markdown_path}',
                'key_points': ['Point 1', 'Point 2', 'Point 3'],
                'methodology': 'Test methodology',
                'tags': ['test', 'evaluation'],
            },
        )

        # Run evaluation
        metrics = await run_analysis_evaluation(
            num_samples=5,
            output_dir=temp_directory,
            use_existing_ground_truth=None,
        )

    # Validate metrics structure
    assert isinstance(metrics, AnalysisMetrics)
    assert metrics.extraction.total_samples == 5
    assert metrics.content_quality.total_samples == 5
    assert metrics.strategy_efficiency.total_samples == 5

    # Validate output files
    assert (temp_directory / 'ground_truth.json').exists()
    assert (temp_directory / 'evaluation_report.txt').exists()

    logger.info(f'✅ Complete evaluation pipeline test passed with {metrics}')


# ============================================================================
# Test Cases: Report Generation
# ============================================================================

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_evaluation_report_format(temp_directory: Path):
    """
    Test evaluation report generation and formatting.

    Validates:
    - Report contains all sections
    - Metrics are properly formatted
    - Human-readable output
    """
    from thoth.analyze.evaluation.metrics import (
        ExtractionMetrics,
        ContentQualityMetrics,
        StrategyEfficiencyMetrics,
    )

    # Create mock metrics
    metrics = AnalysisMetrics(
        extraction=ExtractionMetrics(
            total_samples=10,
            field_completeness=0.85,
            required_fields_completeness=0.95,
            optional_fields_completeness=0.75,
            avg_field_confidence=0.88,
            field_accuracy={'summary': 0.92, 'tags': 0.78},
        ),
        content_quality=ContentQualityMetrics(
            total_samples=10,
            summary_coherence=0.87,
            summary_completeness=0.82,
            key_points_relevance=0.79,
            key_points_coverage=0.84,
            methodology_extraction_quality=0.81,
            tag_appropriateness=0.76,
            avg_summary_length=150.5,
        ),
        strategy_efficiency=StrategyEfficiencyMetrics(
            total_samples=10,
            strategy_selection_accuracy=0.90,
            direct_strategy_usage=0.40,
            map_reduce_strategy_usage=0.50,
            refine_strategy_usage=0.10,
            avg_processing_time_by_strategy={
                'direct': 200.0,
                'map_reduce': 800.0,
                'refine': 1200.0,
            },
            quality_by_strategy={
                'direct': 0.85,
                'map_reduce': 0.88,
                'refine': 0.92,
            },
        ),
    )

    # Generate report
    report_path = temp_directory / 'test_report.txt'
    from thoth.analyze.evaluation.runner import _save_analysis_report

    await _save_analysis_report(metrics, temp_directory)

    # Verify report exists and contains expected sections
    assert (temp_directory / 'evaluation_report.txt').exists()

    report_content = (temp_directory / 'evaluation_report.txt').read_text()

    # Check for key sections
    assert 'ANALYSIS PIPELINE EVALUATION REPORT' in report_content
    assert 'EXTRACTION METRICS' in report_content
    assert 'CONTENT QUALITY METRICS' in report_content
    assert 'STRATEGY EFFICIENCY METRICS' in report_content

    # Check for metric values
    assert '0.85' in report_content  # Field completeness
    assert '0.87' in report_content  # Summary coherence
    assert '0.90' in report_content  # Strategy selection accuracy


# ============================================================================
# Test Cases: Error Handling
# ============================================================================

@pytest.mark.e2e
@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_evaluation_with_analysis_failures(
    postgres_service: PostgresService,
    temp_directory: Path,
    empty_database,
):
    """
    Test evaluation pipeline handles LLM analysis failures gracefully.

    Some papers may fail to analyze (API errors, timeouts, etc.).
    Pipeline should continue and report partial results.
    """
    # Insert test papers
    async with postgres_service.pool.acquire() as conn:
        await conn.execute(
            '''
            INSERT INTO papers (title, content, authors, year)
            VALUES
                ('Paper 1', 'Content 1', ARRAY['Author 1'], 2023),
                ('Paper 2', 'Content 2', ARRAY['Author 2'], 2022),
                ('Paper 3', 'Content 3', ARRAY['Author 3'], 2021)
            '''
        )

    # Mock LLM service to fail on second paper
    def mock_analyze(self, markdown_path):
        if '2' in markdown_path:
            raise Exception('LLM API timeout')
        return {
            'summary': 'Test summary',
            'key_points': ['Point 1'],
            'tags': ['test'],
        }

    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            'thoth.analyze.llm_processor.LLMProcessor.analyze_content',
            mock_analyze,
        )

        # Run evaluation (should handle failure gracefully)
        metrics = await run_analysis_evaluation(
            num_samples=3,
            output_dir=temp_directory,
        )

    # Should have partial results (2 successful, 1 failed)
    assert metrics.extraction.total_samples == 3
    # Metrics should be computed on successful samples only
    assert 0.0 <= metrics.extraction.field_completeness <= 1.0
