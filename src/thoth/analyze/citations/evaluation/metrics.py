"""
Evaluation Metrics for Citation Resolution.

This module calculates precision, recall, F1, and confidence calibration
for citation resolution systems using ground truth data.
"""

from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
import numpy as np
from loguru import logger

from thoth.analyze.citations.resolution_chain import ResolutionResult, CitationResolutionStatus
from thoth.analyze.citations.evaluation.ground_truth import GroundTruthCitation


@dataclass
class ConfusionMatrix:
    """Confusion matrix for binary classification."""
    true_positives: int = 0
    false_positives: int = 0
    true_negatives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        """Precision = TP / (TP + FP)"""
        denominator = self.true_positives + self.false_positives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def recall(self) -> float:
        """Recall = TP / (TP + FN)"""
        denominator = self.true_positives + self.false_negatives
        if denominator == 0:
            return 0.0
        return self.true_positives / denominator

    @property
    def f1_score(self) -> float:
        """F1 = 2 * (precision * recall) / (precision + recall)"""
        if self.precision + self.recall == 0:
            return 0.0
        return 2 * (self.precision * self.recall) / (self.precision + self.recall)

    @property
    def accuracy(self) -> float:
        """Accuracy = (TP + TN) / (TP + TN + FP + FN)"""
        total = self.true_positives + self.true_negatives + self.false_positives + self.false_negatives
        if total == 0:
            return 0.0
        return (self.true_positives + self.true_negatives) / total


@dataclass
class CitationMetrics:
    """
    Comprehensive metrics for citation resolution evaluation.

    Metrics:
    - Precision: Of citations we resolved, what % were correct?
    - Recall: Of citations that should be found, what % did we find?
    - F1: Harmonic mean of precision and recall
    - Accuracy: Overall correctness rate
    - Mean Confidence: Average confidence score
    - API Efficiency: Average API calls per resolved citation
    """
    confusion_matrix: ConfusionMatrix
    mean_confidence: float
    confidence_calibration_error: float
    api_calls_per_citation: float
    total_citations: int
    resolved_citations: int
    unresolved_citations: int
    by_difficulty: Dict[str, ConfusionMatrix]
    by_degradation: Dict[str, ConfusionMatrix]

    @property
    def precision(self) -> float:
        return self.confusion_matrix.precision

    @property
    def recall(self) -> float:
        return self.confusion_matrix.recall

    @property
    def f1_score(self) -> float:
        return self.confusion_matrix.f1_score

    @property
    def accuracy(self) -> float:
        return self.confusion_matrix.accuracy

    def __str__(self) -> str:
        """Human-readable metrics summary."""
        return f"""
Citation Resolution Metrics:
============================
Precision: {self.precision:.3f}
Recall: {self.recall:.3f}
F1 Score: {self.f1_score:.3f}
Accuracy: {self.accuracy:.3f}

Total Citations: {self.total_citations}
Resolved: {self.resolved_citations} ({self.resolved_citations/self.total_citations*100:.1f}%)
Unresolved: {self.unresolved_citations} ({self.unresolved_citations/self.total_citations*100:.1f}%)

Confidence: {self.mean_confidence:.3f}
Calibration Error: {self.confidence_calibration_error:.3f}
API Calls/Citation: {self.api_calls_per_citation:.1f}

By Difficulty:
  Easy: P={self.by_difficulty.get('easy', ConfusionMatrix()).precision:.3f}, R={self.by_difficulty.get('easy', ConfusionMatrix()).recall:.3f}
  Medium: P={self.by_difficulty.get('medium', ConfusionMatrix()).precision:.3f}, R={self.by_difficulty.get('medium', ConfusionMatrix()).recall:.3f}
  Hard: P={self.by_difficulty.get('hard', ConfusionMatrix()).precision:.3f}, R={self.by_difficulty.get('hard', ConfusionMatrix()).recall:.3f}
"""


def calculate_precision_recall_f1(
    ground_truth: List[GroundTruthCitation],
    results: List[ResolutionResult],
    match_criteria: str = "doi"  # "doi", "title_author", or "any"
) -> CitationMetrics:
    """
    Calculate precision, recall, and F1 score for citation resolution.

    Args:
        ground_truth: List of citations with known ground truth
        results: Resolution results from the system
        match_criteria: How to determine if resolution is correct:
            - "doi": Must match DOI exactly (strictest)
            - "title_author": Title + primary author must match
            - "any": Any identifier match (DOI, OpenAlex, S2)

    Returns:
        Comprehensive citation metrics

    Ground Truth Matching Logic:
    - TRUE POSITIVE: System resolved citation and match is correct
    - FALSE POSITIVE: System resolved citation but match is incorrect
    - TRUE NEGATIVE: Not applicable for this task
    - FALSE NEGATIVE: System failed to resolve citation that should be found
    """
    if len(ground_truth) != len(results):
        raise ValueError(
            f"Ground truth and results must have same length: "
            f"{len(ground_truth)} vs {len(results)}"
        )

    logger.info(
        f"Calculating metrics for {len(ground_truth)} citations "
        f"(match_criteria={match_criteria})"
    )

    # Overall confusion matrix
    confusion = ConfusionMatrix()

    # Confusion matrices by difficulty and degradation type
    by_difficulty = {
        "easy": ConfusionMatrix(),
        "medium": ConfusionMatrix(),
        "hard": ConfusionMatrix()
    }
    by_degradation = {}

    # Tracking metrics
    confidences = []
    api_calls = []
    resolved_count = 0
    unresolved_count = 0

    # Evaluate each citation
    for gt, result in zip(ground_truth, results):
        # Track confidence and API usage
        confidences.append(result.confidence_score)
        if result.metadata and result.metadata.api_sources_tried:
            api_calls.append(len(result.metadata.api_sources_tried))

        # Determine if resolution was successful
        is_resolved = result.status == CitationResolutionStatus.RESOLVED

        if is_resolved:
            resolved_count += 1
        else:
            unresolved_count += 1

        # Determine if match is correct
        is_correct = _is_match_correct(gt, result, match_criteria)

        # Update confusion matrix
        if is_resolved and is_correct:
            # TRUE POSITIVE: Resolved and correct
            confusion.true_positives += 1
            by_difficulty[gt.difficulty].true_positives += 1
            if gt.degradation_type.value not in by_degradation:
                by_degradation[gt.degradation_type.value] = ConfusionMatrix()
            by_degradation[gt.degradation_type.value].true_positives += 1

        elif is_resolved and not is_correct:
            # FALSE POSITIVE: Resolved but incorrect
            confusion.false_positives += 1
            by_difficulty[gt.difficulty].false_positives += 1
            if gt.degradation_type.value not in by_degradation:
                by_degradation[gt.degradation_type.value] = ConfusionMatrix()
            by_degradation[gt.degradation_type.value].false_positives += 1

        elif not is_resolved:
            # FALSE NEGATIVE: Failed to resolve
            confusion.false_negatives += 1
            by_difficulty[gt.difficulty].false_negatives += 1
            if gt.degradation_type.value not in by_degradation:
                by_degradation[gt.degradation_type.value] = ConfusionMatrix()
            by_degradation[gt.degradation_type.value].false_negatives += 1

    # Calculate confidence calibration
    calibration_error = calculate_confidence_calibration(ground_truth, results)

    # Build metrics object
    metrics = CitationMetrics(
        confusion_matrix=confusion,
        mean_confidence=np.mean(confidences) if confidences else 0.0,
        confidence_calibration_error=calibration_error,
        api_calls_per_citation=np.mean(api_calls) if api_calls else 0.0,
        total_citations=len(ground_truth),
        resolved_citations=resolved_count,
        unresolved_citations=unresolved_count,
        by_difficulty=by_difficulty,
        by_degradation=by_degradation
    )

    logger.info(
        f"Evaluation complete: P={metrics.precision:.3f}, "
        f"R={metrics.recall:.3f}, F1={metrics.f1_score:.3f}"
    )

    return metrics


def _is_match_correct(
    gt: GroundTruthCitation,
    result: ResolutionResult,
    match_criteria: str
) -> bool:
    """
    Determine if resolution result matches ground truth.

    Args:
        gt: Ground truth citation
        result: Resolution result
        match_criteria: How to determine correctness

    Returns:
        True if match is correct according to criteria
    """
    if result.status != CitationResolutionStatus.RESOLVED:
        return False

    if not result.matched_data:
        return False

    matched_data = result.matched_data

    if match_criteria == "doi":
        # Strictest: DOI must match exactly
        if gt.ground_truth_doi and matched_data.get("doi"):
            return _normalize_doi(gt.ground_truth_doi) == _normalize_doi(
                matched_data["doi"]
            )
        return False

    elif match_criteria == "title_author":
        # Medium: Title and primary author must match
        title_match = _titles_match(
            gt.ground_truth_title,
            matched_data.get("title", "")
        )

        author_match = False
        if gt.ground_truth_authors and matched_data.get("authors"):
            # Check if primary author (first author) matches
            gt_primary = _normalize_author(gt.ground_truth_authors[0])
            matched_primary = _normalize_author(matched_data["authors"][0])
            author_match = gt_primary == matched_primary

        return title_match and author_match

    elif match_criteria == "any":
        # Most lenient: Any identifier match
        # Check DOI
        if gt.ground_truth_doi and matched_data.get("doi"):
            if _normalize_doi(gt.ground_truth_doi) == _normalize_doi(matched_data["doi"]):
                return True

        # Check OpenAlex ID
        if gt.ground_truth_openalex_id and matched_data.get("openalex_id"):
            if gt.ground_truth_openalex_id == matched_data["openalex_id"]:
                return True

        # Check Semantic Scholar ID
        if gt.ground_truth_s2_id and matched_data.get("s2_id"):
            if gt.ground_truth_s2_id == matched_data["s2_id"]:
                return True

        # Fallback to title+author matching
        return _is_match_correct(gt, result, "title_author")

    return False


def _normalize_doi(doi: str) -> str:
    """Normalize DOI for comparison."""
    doi = doi.lower().strip()
    # Remove common prefixes
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    doi = doi.replace("doi:", "")
    return doi


def _titles_match(title1: str, title2: str, threshold: float = 0.9) -> bool:
    """Check if two titles match using fuzzy matching."""
    from fuzzywuzzy import fuzz

    # Normalize titles
    t1 = title1.lower().strip()
    t2 = title2.lower().strip()

    # Use fuzzy matching for robustness
    similarity = fuzz.ratio(t1, t2) / 100.0
    return similarity >= threshold


def _normalize_author(author: str) -> str:
    """Normalize author name for comparison."""
    # Remove punctuation and extra spaces
    import re
    author = re.sub(r'[^\w\s]', ' ', author)
    author = ' '.join(author.split())
    return author.lower().strip()


def calculate_confidence_calibration(
    ground_truth: List[GroundTruthCitation],
    results: List[ResolutionResult],
    num_bins: int = 10
) -> float:
    """
    Calculate Expected Calibration Error (ECE) for confidence scores.

    This measures how well-calibrated the confidence scores are.
    If the system says 80% confidence, it should be correct 80% of the time.

    Args:
        ground_truth: Citations with known ground truth
        results: Resolution results with confidence scores
        num_bins: Number of bins for calibration curve

    Returns:
        Expected Calibration Error (ECE) - lower is better
        0.0 = perfectly calibrated
        1.0 = completely miscalibrated
    """
    if len(ground_truth) != len(results):
        raise ValueError("Ground truth and results must have same length")

    # Group predictions by confidence bin
    bins = [[] for _ in range(num_bins)]

    for gt, result in zip(ground_truth, results):
        confidence = result.confidence_score
        is_correct = _is_match_correct(gt, result, match_criteria="any")

        # Determine bin
        bin_idx = min(int(confidence * num_bins), num_bins - 1)
        bins[bin_idx].append(is_correct)

    # Calculate ECE
    ece = 0.0
    total_samples = len(ground_truth)

    for bin_idx, bin_predictions in enumerate(bins):
        if not bin_predictions:
            continue

        # Average confidence for this bin
        bin_confidence = (bin_idx + 0.5) / num_bins

        # Actual accuracy in this bin
        bin_accuracy = sum(bin_predictions) / len(bin_predictions)

        # Weighted difference
        bin_weight = len(bin_predictions) / total_samples
        ece += bin_weight * abs(bin_confidence - bin_accuracy)

    logger.debug(f"Calculated ECE: {ece:.4f}")
    return ece


def calculate_metrics_by_confidence_threshold(
    ground_truth: List[GroundTruthCitation],
    results: List[ResolutionResult],
    thresholds: List[float] = None
) -> Dict[float, CitationMetrics]:
    """
    Calculate metrics at different confidence thresholds.

    This is useful for understanding the precision/recall tradeoff.
    Higher thresholds → Higher precision, lower recall

    Args:
        ground_truth: Citations with known ground truth
        results: Resolution results
        thresholds: Confidence thresholds to evaluate (default: 0.5, 0.6, 0.7, 0.8, 0.9)

    Returns:
        Dictionary mapping threshold to metrics
    """
    if thresholds is None:
        thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]

    logger.info(f"Calculating metrics at thresholds: {thresholds}")

    metrics_by_threshold = {}

    for threshold in thresholds:
        # Filter results by confidence threshold
        filtered_gt = []
        filtered_results = []

        for gt, result in zip(ground_truth, results):
            if result.confidence_score >= threshold:
                # Keep result as-is
                filtered_gt.append(gt)
                filtered_results.append(result)
            else:
                # Mark as unresolved if below threshold
                low_conf_result = ResolutionResult(
                    citation=result.citation,
                    status=CitationResolutionStatus.FAILED,
                    confidence_score=result.confidence_score,
                    confidence_level=result.confidence_level,
                    source=result.source,
                    matched_data=None,
                    metadata=result.metadata
                )
                filtered_gt.append(gt)
                filtered_results.append(low_conf_result)

        # Calculate metrics for this threshold
        metrics = calculate_precision_recall_f1(
            filtered_gt,
            filtered_results,
            match_criteria="any"
        )

        metrics_by_threshold[threshold] = metrics

        logger.info(
            f"Threshold {threshold}: P={metrics.precision:.3f}, "
            f"R={metrics.recall:.3f}, F1={metrics.f1_score:.3f}"
        )

    return metrics_by_threshold
