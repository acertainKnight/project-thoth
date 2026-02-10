"""
Evaluation runner for Analysis pipeline.

This module orchestrates Analysis evaluation including:
- Ground truth generation
- Paper analysis execution
- Extraction accuracy measurement
- Content quality evaluation
- Strategy efficiency analysis
- Report generation
"""

import asyncio  # noqa: I001
from pathlib import Path
import time

from loguru import logger

from thoth.config import Config
from thoth.services.postgres_service import PostgresService
from thoth.services.llm_service import LLMService
from thoth.analyze.llm_processor import LLMProcessor
from thoth.analyze.evaluation.ground_truth import AnalysisGroundTruthGenerator
from thoth.analyze.evaluation.metrics import calculate_analysis_metrics, AnalysisMetrics


async def run_analysis_evaluation(
    num_samples: int = 50,
    output_dir: Path = Path('./analysis_evaluation_results'),
    use_existing_ground_truth: Path | None = None,
) -> AnalysisMetrics:
    """
    Run comprehensive Analysis pipeline evaluation.

    Steps:
    1. Generate or load ground truth paper-analysis pairs
    2. Run analysis on test papers
    3. Calculate extraction metrics (field completeness, accuracy)
    4. Calculate content quality metrics (coherence, relevance)
    5. Calculate strategy efficiency (selection accuracy, timing)
    6. Generate evaluation report

    Args:
        num_samples: Number of test papers to evaluate
        output_dir: Directory for evaluation results
        use_existing_ground_truth: Path to existing ground truth file

    Returns:
        AnalysisMetrics object with comprehensive evaluation results
    """
    logger.info(f'Starting Analysis evaluation with {num_samples} samples...')
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize services
    config = Config()
    postgres = PostgresService(config)
    await postgres.initialize()

    llm_service = LLMService(config)
    prompts_dir = Path(__file__).resolve().parents[3] / 'data' / 'prompts'

    llm_processor = LLMProcessor(
        llm_service=llm_service,
        model=config.llm_config.model,
        prompts_dir=prompts_dir,
        max_output_tokens=config.llm_config.max_output_tokens,
        max_context_length=config.llm_config.max_context_length,
    )

    try:
        # Step 1: Generate or load ground truth
        gt_generator = AnalysisGroundTruthGenerator(postgres)

        if use_existing_ground_truth:
            logger.info(f'Loading ground truth from {use_existing_ground_truth}')
            ground_truth = await gt_generator.load_ground_truth(
                use_existing_ground_truth
            )
        else:
            logger.info('Generating ground truth from database papers...')
            ground_truth = await gt_generator.generate_from_database(
                num_samples=num_samples
            )
            # Save generated ground truth
            gt_path = output_dir / 'ground_truth.json'
            await gt_generator.save_ground_truth(ground_truth, gt_path)

        logger.info(f'Evaluating {len(ground_truth)} paper analyses...')

        # Step 2: Run analysis on test papers
        predicted_analyses = []
        timing_data = []

        for i, gt_pair in enumerate(ground_truth):
            if (i + 1) % 5 == 0:
                logger.info(f'Processing paper {i + 1}/{len(ground_truth)}...')

            # Measure processing time
            start_time = time.time()

            try:
                # Analyze paper content
                analysis_result = llm_processor.analyze_content(
                    markdown_path=gt_pair.paper_content  # Pass content directly
                )

                processing_time = (time.time() - start_time) * 1000  # ms

                predicted_analyses.append(analysis_result)

                # Record timing and strategy info
                timing_data.append(
                    {
                        'paper_id': gt_pair.paper_id,
                        'complexity': gt_pair.complexity,
                        'content_length': gt_pair.content_length,
                        'expected_strategy': gt_pair.expected_strategy,
                        'processing_time_ms': processing_time,
                    }
                )

            except Exception as e:
                logger.error(f'Error analyzing paper {gt_pair.paper_id}: {e}')
                # Add None for failed analysis
                predicted_analyses.append(None)
                timing_data.append(
                    {
                        'paper_id': gt_pair.paper_id,
                        'complexity': gt_pair.complexity,
                        'content_length': gt_pair.content_length,
                        'expected_strategy': gt_pair.expected_strategy,
                        'processing_time_ms': 0,
                        'failed': True,
                    }
                )

        # Step 3-5: Calculate metrics
        logger.info('Calculating metrics...')
        metrics = calculate_analysis_metrics(
            ground_truth_list=ground_truth,
            predicted_list=predicted_analyses,
            timing_data=timing_data,
        )

        # Step 6: Generate report
        logger.info('Generating evaluation report...')
        await _save_analysis_report(metrics, output_dir)

        logger.info(f'✅ Analysis evaluation complete! Results saved to {output_dir}')
        return metrics

    finally:
        await postgres.close()


async def _save_analysis_report(metrics: AnalysisMetrics, output_dir: Path) -> None:
    """Save evaluation report to file."""
    report_path = output_dir / 'evaluation_report.txt'

    with open(report_path, 'w') as f:
        f.write('=' * 80 + '\n')
        f.write('ANALYSIS PIPELINE EVALUATION REPORT\n')
        f.write('=' * 80 + '\n\n')

        # Extraction Metrics
        f.write('EXTRACTION METRICS\n')
        f.write('-' * 80 + '\n')
        f.write(f'Total Samples: {metrics.extraction.total_samples}\n')
        f.write(f'Field Completeness: {metrics.extraction.field_completeness:.4f}\n')
        f.write(
            f'Required Fields Completeness: {metrics.extraction.required_fields_completeness:.4f}\n'
        )
        f.write(
            f'Optional Fields Completeness: {metrics.extraction.optional_fields_completeness:.4f}\n'
        )
        f.write(
            f'Avg Field Confidence: {metrics.extraction.avg_field_confidence:.4f}\n\n'
        )

        if metrics.extraction.field_accuracy:
            f.write('Field-wise Accuracy:\n')
            for field, accuracy in sorted(metrics.extraction.field_accuracy.items()):
                f.write(f'  {field}: {accuracy:.4f}\n')
        f.write('\n')

        # Content Quality Metrics
        f.write('CONTENT QUALITY METRICS\n')
        f.write('-' * 80 + '\n')
        f.write(f'Total Samples: {metrics.content_quality.total_samples}\n')
        f.write(f'Summary Coherence: {metrics.content_quality.summary_coherence:.4f}\n')
        f.write(
            f'Summary Completeness: {metrics.content_quality.summary_completeness:.4f}\n'
        )
        f.write(
            f'Key Points Relevance: {metrics.content_quality.key_points_relevance:.4f}\n'
        )
        f.write(
            f'Key Points Coverage: {metrics.content_quality.key_points_coverage:.4f}\n'
        )
        f.write(
            f'Methodology Extraction Quality: {metrics.content_quality.methodology_extraction_quality:.4f}\n'
        )
        f.write(
            f'Tag Appropriateness: {metrics.content_quality.tag_appropriateness:.4f}\n'
        )
        f.write(
            f'Avg Summary Length (tokens): {metrics.content_quality.avg_summary_length:.1f}\n\n'
        )

        # Strategy Efficiency Metrics
        f.write('STRATEGY EFFICIENCY METRICS\n')
        f.write('-' * 80 + '\n')
        f.write(f'Total Samples: {metrics.strategy_efficiency.total_samples}\n')
        f.write(
            f'Strategy Selection Accuracy: {metrics.strategy_efficiency.strategy_selection_accuracy:.4f}\n'
        )
        f.write(
            f'Direct Strategy Usage: {metrics.strategy_efficiency.direct_strategy_usage:.4f}\n'
        )
        f.write(
            f'Map-Reduce Strategy Usage: {metrics.strategy_efficiency.map_reduce_strategy_usage:.4f}\n'
        )
        f.write(
            f'Refine Strategy Usage: {metrics.strategy_efficiency.refine_strategy_usage:.4f}\n\n'
        )

        if metrics.strategy_efficiency.avg_processing_time_by_strategy:
            f.write('Avg Processing Time by Strategy:\n')
            for strategy, time_ms in sorted(
                metrics.strategy_efficiency.avg_processing_time_by_strategy.items()
            ):
                f.write(f'  {strategy}: {time_ms:.1f} ms\n')
        f.write('\n')

        if metrics.strategy_efficiency.quality_by_strategy:
            f.write('Quality Score by Strategy:\n')
            for strategy, quality in sorted(
                metrics.strategy_efficiency.quality_by_strategy.items()
            ):
                f.write(f'  {strategy}: {quality:.4f}\n')
        f.write('\n')

        f.write('=' * 80 + '\n')

    logger.info(f'Report saved to {report_path}')


def main():
    """CLI entry point for Analysis evaluation."""
    import argparse

    parser = argparse.ArgumentParser(description='Run Analysis pipeline evaluation')
    parser.add_argument(
        '--samples', type=int, default=50, help='Number of test samples to evaluate'
    )
    parser.add_argument(
        '--output',
        type=Path,
        default=Path('./analysis_evaluation_results'),
        help='Output directory for results',
    )
    parser.add_argument(
        '--ground-truth',
        type=Path,
        default=None,
        help='Path to existing ground truth file',
    )

    args = parser.parse_args()

    asyncio.run(
        run_analysis_evaluation(
            num_samples=args.samples,
            output_dir=args.output,
            use_existing_ground_truth=args.ground_truth,
        )
    )


if __name__ == '__main__':
    main()
