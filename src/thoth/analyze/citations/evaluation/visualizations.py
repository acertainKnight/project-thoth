"""
Visualization tools for evaluation metrics.

Creates publication-quality plots for:
- Precision-Recall curves
- Confidence calibration curves
- Confusion matrices
- Performance by difficulty
"""

from typing import List, Dict
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

from thoth.analyze.citations.evaluation.metrics import CitationMetrics, ConfusionMatrix


def plot_precision_recall_curve(
    metrics_by_threshold: Dict[float, CitationMetrics],
    output_path: Path,
    title: str = "Precision-Recall Tradeoff"
):
    """
    Plot precision-recall curve showing tradeoff at different confidence thresholds.

    Args:
        metrics_by_threshold: Metrics at different confidence thresholds
        output_path: Where to save plot
        title: Plot title
    """
    thresholds = sorted(metrics_by_threshold.keys())
    precisions = [metrics_by_threshold[t].precision for t in thresholds]
    recalls = [metrics_by_threshold[t].recall for t in thresholds]

    plt.figure(figsize=(10, 6))
    plt.plot(recalls, precisions, 'b-o', linewidth=2, markersize=8)

    # Annotate with threshold values
    for i, threshold in enumerate(thresholds):
        plt.annotate(
            f'{threshold:.2f}',
            (recalls[i], precisions[i]),
            textcoords="offset points",
            xytext=(0, 10),
            ha='center',
            fontsize=9
        )

    plt.xlabel('Recall', fontsize=12)
    plt.ylabel('Precision', fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.xlim(0, 1.05)
    plt.ylim(0, 1.05)

    # Add reference line for F1 contours
    recall_range = np.linspace(0.01, 1, 100)
    for f1 in [0.2, 0.4, 0.6, 0.8]:
        precision_range = f1 * recall_range / (2 * recall_range - f1 + 1e-10)
        precision_range = np.clip(precision_range, 0, 1)
        plt.plot(recall_range, precision_range, '--', alpha=0.2, color='gray')
        plt.text(0.9, f1, f'F1={f1:.1f}', fontsize=8, alpha=0.5)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_calibration_curve(
    ground_truth: List,
    results: List,
    output_path: Path,
    num_bins: int = 10,
    title: str = "Confidence Calibration"
):
    """
    Plot confidence calibration curve.

    A well-calibrated system has predictions on the diagonal line.
    Above diagonal = overconfident, below = underconfident.

    Args:
        ground_truth: Ground truth citations
        results: Resolution results
        output_path: Where to save plot
        num_bins: Number of bins for calibration
        title: Plot title
    """
    from thoth.analyze.citations.evaluation.metrics import _is_match_correct

    # Group by confidence bins
    bins = [[] for _ in range(num_bins)]
    bin_confidences = []
    bin_accuracies = []

    for gt, result in zip(ground_truth, results):
        confidence = result.confidence_score
        is_correct = _is_match_correct(gt, result, match_criteria="any")

        bin_idx = min(int(confidence * num_bins), num_bins - 1)
        bins[bin_idx].append(is_correct)

    # Calculate average confidence and accuracy per bin
    for bin_idx, bin_predictions in enumerate(bins):
        if not bin_predictions:
            continue

        bin_confidence = (bin_idx + 0.5) / num_bins
        bin_accuracy = sum(bin_predictions) / len(bin_predictions)

        bin_confidences.append(bin_confidence)
        bin_accuracies.append(bin_accuracy)

    # Create plot
    plt.figure(figsize=(10, 10))

    # Plot calibration curve
    plt.plot(bin_confidences, bin_accuracies, 'b-o', linewidth=2, markersize=10, label='Model')

    # Plot perfect calibration line
    plt.plot([0, 1], [0, 1], 'r--', linewidth=2, label='Perfect Calibration')

    # Shade regions
    plt.fill_between([0, 1], [0, 1], [1, 1], alpha=0.1, color='red', label='Overconfident')
    plt.fill_between([0, 1], [0, 0], [0, 1], alpha=0.1, color='blue', label='Underconfident')

    plt.xlabel('Predicted Confidence', fontsize=12)
    plt.ylabel('Actual Accuracy', fontsize=12)
    plt.title(title, fontsize=14, fontweight='bold')
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.xlim(0, 1)
    plt.ylim(0, 1)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_confusion_matrix(
    confusion: ConfusionMatrix,
    output_path: Path,
    title: str = "Confusion Matrix"
):
    """
    Plot confusion matrix as heatmap.

    Args:
        confusion: Confusion matrix
        output_path: Where to save plot
        title: Plot title
    """
    # Create matrix
    matrix = np.array([
        [confusion.true_positives, confusion.false_positives],
        [confusion.false_negatives, confusion.true_negatives]
    ])

    plt.figure(figsize=(8, 6))
    sns.heatmap(
        matrix,
        annot=True,
        fmt='d',
        cmap='Blues',
        xticklabels=['Resolved', 'Not Resolved'],
        yticklabels=['Correct', 'Incorrect'],
        cbar_kws={'label': 'Count'}
    )

    plt.title(title, fontsize=14, fontweight='bold')
    plt.ylabel('Ground Truth', fontsize=12)
    plt.xlabel('Prediction', fontsize=12)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def plot_metrics_by_difficulty(
    metrics: CitationMetrics,
    output_path: Path,
    title: str = "Performance by Difficulty"
):
    """
    Plot precision/recall/F1 by difficulty level.

    Args:
        metrics: Citation metrics with breakdown by difficulty
        output_path: Where to save plot
        title: Plot title
    """
    difficulties = ['easy', 'medium', 'hard']
    precisions = [metrics.by_difficulty[d].precision for d in difficulties]
    recalls = [metrics.by_difficulty[d].recall for d in difficulties]
    f1_scores = [metrics.by_difficulty[d].f1_score for d in difficulties]

    x = np.arange(len(difficulties))
    width = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))

    bars1 = ax.bar(x - width, precisions, width, label='Precision', color='#1f77b4')
    bars2 = ax.bar(x, recalls, width, label='Recall', color='#ff7f0e')
    bars3 = ax.bar(x + width, f1_scores, width, label='F1 Score', color='#2ca02c')

    ax.set_xlabel('Difficulty Level', fontsize=12)
    ax.set_ylabel('Score', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(difficulties)
    ax.legend(fontsize=10)
    ax.set_ylim(0, 1.1)
    ax.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{height:.2f}',
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3),
                        textcoords="offset points",
                        ha='center', va='bottom',
                        fontsize=9)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    plt.close()


def create_evaluation_report(
    metrics: CitationMetrics,
    metrics_by_threshold: Dict[float, CitationMetrics],
    output_dir: Path,
    system_name: str = "Citation Resolution System"
):
    """
    Create comprehensive evaluation report with all visualizations.

    Args:
        metrics: Overall metrics
        metrics_by_threshold: Metrics at different thresholds
        output_dir: Directory to save reports
        system_name: Name of system being evaluated
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate all plots
    plot_precision_recall_curve(
        metrics_by_threshold,
        output_dir / "precision_recall_curve.png",
        title=f"{system_name} - Precision-Recall Tradeoff"
    )

    plot_confusion_matrix(
        metrics.confusion_matrix,
        output_dir / "confusion_matrix.png",
        title=f"{system_name} - Confusion Matrix"
    )

    plot_metrics_by_difficulty(
        metrics,
        output_dir / "performance_by_difficulty.png",
        title=f"{system_name} - Performance by Difficulty"
    )

    # Write text report
    report_path = output_dir / "evaluation_report.txt"
    with open(report_path, 'w') as f:
        f.write(f"{system_name} - Evaluation Report\n")
        f.write("=" * 60 + "\n\n")
        f.write(str(metrics))
        f.write("\n\nMetrics by Confidence Threshold:\n")
        f.write("-" * 60 + "\n")
        for threshold in sorted(metrics_by_threshold.keys()):
            m = metrics_by_threshold[threshold]
            f.write(f"\nThreshold: {threshold:.2f}\n")
            f.write(f"  Precision: {m.precision:.3f}\n")
            f.write(f"  Recall: {m.recall:.3f}\n")
            f.write(f"  F1 Score: {m.f1_score:.3f}\n")
            f.write(f"  Resolved: {m.resolved_citations}/{m.total_citations}\n")

    print(f"\n✅ Evaluation report saved to: {output_dir}")
    print(f"   - precision_recall_curve.png")
    print(f"   - confusion_matrix.png")
    print(f"   - performance_by_difficulty.png")
    print(f"   - evaluation_report.txt")
