"""
Evaluation Runner for Citation Resolution System.

This script runs comprehensive evaluation of the citation resolution system:
1. Generates ground truth test set from database
2. Runs resolution on test citations
3. Calculates precision/recall/F1 metrics
4. Measures confidence calibration
5. Creates visualization reports

Usage:
    python -m thoth.analyze.citations.evaluation.runner \\
        --num-samples 500 \\
        --output-dir ./evaluation_results
"""

import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from loguru import logger

from thoth.config import Config
from thoth.services.postgres_service import PostgresService
from thoth.analyze.citations.resolution_chain import CitationResolutionChain
from thoth.analyze.citations.evaluation.ground_truth import GroundTruthGenerator
from thoth.analyze.citations.evaluation.metrics import (
    calculate_precision_recall_f1,
    calculate_metrics_by_confidence_threshold
)
from thoth.analyze.citations.evaluation.visualizations import (
    create_evaluation_report,
    plot_calibration_curve
)


async def run_evaluation(
    num_samples: int = 500,
    output_dir: Path = Path("./evaluation_results"),
    require_doi: bool = True,
    stratify: bool = True
):
    """
    Run comprehensive evaluation of citation resolution system.

    Args:
        num_samples: Number of test citations to generate
        output_dir: Where to save evaluation results
        require_doi: Only use papers with DOIs (higher quality ground truth)
        stratify: Balance easy/medium/hard cases

    Returns:
        CitationMetrics with evaluation results
    """
    logger.info("=" * 60)
    logger.info("Citation Resolution System Evaluation")
    logger.info("=" * 60)
    logger.info(f"Test samples: {num_samples}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Require DOI: {require_doi}")
    logger.info(f"Stratify by difficulty: {stratify}")
    logger.info("")

    # Initialize services
    logger.info("Initializing services...")
    config = Config()
    postgres = PostgresService(config)
    await postgres.initialize()

    # Initialize resolution chain (using default resolvers)
    resolution_chain = CitationResolutionChain()

    try:
        # Step 1: Generate ground truth test set
        logger.info("\n" + "=" * 60)
        logger.info("STEP 1: Generating Ground Truth Test Set")
        logger.info("=" * 60)

        gt_generator = GroundTruthGenerator(postgres)
        ground_truth = await gt_generator.generate_from_database(
            num_samples=num_samples,
            stratify_by_difficulty=stratify,
            require_doi=require_doi,
            require_cross_validation=False  # Set to True for highest quality
        )

        if not ground_truth:
            logger.error("Failed to generate ground truth test set")
            return None

        logger.info(f"✅ Generated {len(ground_truth)} test citations")
        logger.info(f"   Easy: {sum(1 for c in ground_truth if c.difficulty == 'easy')}")
        logger.info(f"   Medium: {sum(1 for c in ground_truth if c.difficulty == 'medium')}")
        logger.info(f"   Hard: {sum(1 for c in ground_truth if c.difficulty == 'hard')}")

        # Step 2: Run resolution on test citations
        logger.info("\n" + "=" * 60)
        logger.info("STEP 2: Running Citation Resolution")
        logger.info("=" * 60)

        citations = [gt.citation for gt in ground_truth]
        results = await resolution_chain.batch_resolve(citations, parallel=True)

        logger.info(f"✅ Resolved {len(results)} citations")
        resolved_count = sum(1 for r in results if r.status.name == "RESOLVED")
        logger.info(f"   Successfully resolved: {resolved_count}/{len(results)} ({resolved_count/len(results)*100:.1f}%)")

        # Step 3: Calculate metrics
        logger.info("\n" + "=" * 60)
        logger.info("STEP 3: Calculating Evaluation Metrics")
        logger.info("=" * 60)

        # Overall metrics
        logger.info("\nCalculating overall metrics...")
        metrics = calculate_precision_recall_f1(
            ground_truth,
            results,
            match_criteria="any"  # Use most lenient matching
        )

        logger.info("\n" + str(metrics))

        # Metrics by confidence threshold
        logger.info("\nCalculating metrics by confidence threshold...")
        metrics_by_threshold = calculate_metrics_by_confidence_threshold(
            ground_truth,
            results,
            thresholds=[0.3, 0.5, 0.6, 0.7, 0.8, 0.9]
        )

        # Step 4: Generate visualizations and reports
        logger.info("\n" + "=" * 60)
        logger.info("STEP 4: Generating Evaluation Reports")
        logger.info("=" * 60)

        output_dir = Path(output_dir)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        eval_dir = output_dir / f"evaluation_{timestamp}"
        eval_dir.mkdir(parents=True, exist_ok=True)

        # Create comprehensive report
        create_evaluation_report(
            metrics,
            metrics_by_threshold,
            eval_dir,
            system_name="Citation Resolution System"
        )

        # Create calibration curve
        plot_calibration_curve(
            ground_truth,
            results,
            eval_dir / "calibration_curve.png",
            title="Confidence Calibration"
        )

        # Save ground truth and results for further analysis
        import json

        # Save summary JSON
        summary = {
            "timestamp": timestamp,
            "num_samples": len(ground_truth),
            "metrics": {
                "precision": metrics.precision,
                "recall": metrics.recall,
                "f1_score": metrics.f1_score,
                "accuracy": metrics.accuracy,
                "mean_confidence": metrics.mean_confidence,
                "calibration_error": metrics.confidence_calibration_error,
                "api_calls_per_citation": metrics.api_calls_per_citation
            },
            "by_difficulty": {
                difficulty: {
                    "precision": cm.precision,
                    "recall": cm.recall,
                    "f1_score": cm.f1_score
                }
                for difficulty, cm in metrics.by_difficulty.items()
            },
            "by_threshold": {
                str(threshold): {
                    "precision": m.precision,
                    "recall": m.recall,
                    "f1_score": m.f1_score,
                    "resolved_count": m.resolved_citations
                }
                for threshold, m in metrics_by_threshold.items()
            }
        }

        with open(eval_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        logger.info(f"\n✅ Evaluation complete!")
        logger.info(f"📊 Results saved to: {eval_dir}")
        logger.info("\n" + "=" * 60)
        logger.info("KEY FINDINGS")
        logger.info("=" * 60)
        logger.info(f"Precision: {metrics.precision:.1%}")
        logger.info(f"Recall: {metrics.recall:.1%}")
        logger.info(f"F1 Score: {metrics.f1_score:.1%}")
        logger.info(f"Calibration Error: {metrics.confidence_calibration_error:.3f}")
        logger.info(f"API Efficiency: {metrics.api_calls_per_citation:.1f} calls/citation")
        logger.info("=" * 60)

        return metrics

    finally:
        # Cleanup
        await resolution_chain.close()
        await postgres.close()


def main():
    """CLI entry point for evaluation runner."""
    parser = argparse.ArgumentParser(
        description="Evaluate citation resolution system performance"
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=500,
        help="Number of test citations to generate (default: 500)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./evaluation_results",
        help="Directory to save evaluation results (default: ./evaluation_results)"
    )
    parser.add_argument(
        "--require-doi",
        action="store_true",
        default=True,
        help="Only use papers with DOIs for ground truth (default: True)"
    )
    parser.add_argument(
        "--no-stratify",
        action="store_true",
        help="Don't stratify by difficulty (default: stratify)"
    )

    args = parser.parse_args()

    # Run evaluation
    asyncio.run(
        run_evaluation(
            num_samples=args.num_samples,
            output_dir=Path(args.output_dir),
            require_doi=args.require_doi,
            stratify=not args.no_stratify
        )
    )


if __name__ == "__main__":
    main()
