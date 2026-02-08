"""Metrics calculation for Analysis pipeline evaluation."""

from dataclasses import dataclass  # noqa: I001
from typing import List, Dict  # noqa: UP035
import numpy as np
from loguru import logger  # noqa: F401

from thoth.utilities.schemas.analysis import AnalysisResponse


@dataclass
class ExtractionMetrics:
    """
    Extraction accuracy metrics for Analysis pipeline.

    Measures completeness and correctness of structured field extraction.
    """

    field_completeness: float  # % of fields populated
    field_accuracy: Dict[str, float]  # Accuracy per field  # noqa: UP006
    required_fields_completeness: float  # % of required fields populated
    optional_fields_completeness: float  # % of optional fields populated
    avg_field_confidence: float  # Average confidence in extractions
    total_samples: int


@dataclass
class ContentQualityMetrics:
    """
    Content quality metrics for Analysis pipeline.

    Measures quality of generated summaries and analyses.
    """

    summary_coherence: float  # Readability and logical flow
    summary_completeness: float  # Coverage of main points
    key_points_relevance: float  # Relevance of extracted key points
    key_points_coverage: float  # Coverage of paper content
    methodology_extraction_quality: float  # Quality of methodology description
    tag_appropriateness: float  # Relevance of assigned tags
    avg_summary_length: float  # Average summary length
    total_samples: int


@dataclass
class StrategyEfficiencyMetrics:
    """
    Strategy selection and efficiency metrics.
    """

    strategy_selection_accuracy: float  # % correct strategy chosen
    avg_processing_time_by_strategy: Dict[str, float]  # ms per strategy  # noqa: UP006
    quality_by_strategy: Dict[str, float]  # Quality score per strategy  # noqa: UP006
    direct_strategy_usage: float  # % using direct
    map_reduce_strategy_usage: float  # % using map-reduce
    refine_strategy_usage: float  # % using refine
    total_samples: int


@dataclass
class AnalysisMetrics:
    """
    Comprehensive Analysis pipeline evaluation metrics.
    """

    extraction: ExtractionMetrics
    content_quality: ContentQualityMetrics
    strategy_efficiency: StrategyEfficiencyMetrics
    by_complexity: Dict[str, 'AnalysisMetrics']  # Metrics by complexity  # noqa: UP006
    by_content_length: Dict[str, 'AnalysisMetrics']  # Metrics by length  # noqa: UP006


def calculate_field_completeness(
    predicted: AnalysisResponse, ground_truth: AnalysisResponse
) -> float:
    """
    Calculate field completeness: % of ground truth fields that are populated.

    Args:
        predicted: Predicted AnalysisResponse
        ground_truth: Ground truth AnalysisResponse

    Returns:
        Completeness score (0.0 to 1.0)
    """
    # Get all fields from ground truth that are not None
    gt_fields = {
        field: value
        for field, value in ground_truth.model_dump().items()
        if value is not None
    }

    if not gt_fields:
        return 1.0  # All fields complete if no ground truth

    # Count how many of those fields are populated in prediction
    pred_dict = predicted.model_dump()
    populated_count = sum(1 for field in gt_fields if pred_dict.get(field) is not None)

    return populated_count / len(gt_fields)


def calculate_field_accuracy(
    predicted: AnalysisResponse, ground_truth: AnalysisResponse, field_name: str
) -> float:
    """
    Calculate accuracy for a specific field.

    For simple fields (str, int): Exact match or token overlap
    For list fields: Overlap coefficient
    For text fields: Token F1 score

    Args:
        predicted: Predicted AnalysisResponse
        ground_truth: Ground truth AnalysisResponse
        field_name: Name of field to evaluate

    Returns:
        Accuracy score (0.0 to 1.0)
    """
    pred_value = getattr(predicted, field_name, None)
    gt_value = getattr(ground_truth, field_name, None)

    # If both None, consider correct
    if pred_value is None and gt_value is None:
        return 1.0

    # If one is None, incorrect
    if pred_value is None or gt_value is None:
        return 0.0

    # String fields: token overlap F1
    if isinstance(gt_value, str):
        return calculate_token_overlap_f1(str(pred_value), gt_value)

    # Integer fields: exact match
    if isinstance(gt_value, int):
        return 1.0 if pred_value == gt_value else 0.0

    # List fields: overlap coefficient
    if isinstance(gt_value, list):
        if not gt_value:
            return 1.0 if not pred_value else 0.0

        pred_set = set(pred_value) if pred_value else set()
        gt_set = set(gt_value)

        if not pred_set and not gt_set:
            return 1.0

        overlap = len(pred_set & gt_set)
        min_size = min(len(pred_set), len(gt_set))

        if min_size == 0:
            return 0.0

        return overlap / min_size

    return 0.0


def calculate_token_overlap_f1(prediction: str, reference: str) -> float:
    """
    Calculate F1 score based on token overlap.

    Args:
        prediction: Predicted text
        reference: Ground truth text

    Returns:
        F1 score (0.0 to 1.0)
    """
    # Tokenize (simple whitespace split + lowercase)
    pred_tokens = set(prediction.lower().split())
    ref_tokens = set(reference.lower().split())

    if not pred_tokens or not ref_tokens:
        return 0.0

    # Calculate overlap
    overlap = pred_tokens & ref_tokens

    if not overlap:
        return 0.0

    precision = len(overlap) / len(pred_tokens)
    recall = len(overlap) / len(ref_tokens)

    if precision + recall == 0:
        return 0.0

    f1 = 2 * (precision * recall) / (precision + recall)
    return f1


def calculate_summary_coherence(summary: str) -> float:
    """
    Estimate summary coherence using simple heuristics.

    Measures:
    - Sentence structure (has proper sentences)
    - Length appropriateness
    - Readability indicators

    Args:
        summary: Summary text to evaluate

    Returns:
        Coherence score (0.0 to 1.0)
    """
    if not summary or len(summary.strip()) == 0:
        return 0.0

    score = 0.0

    # Check for sentence structure
    sentences = summary.split('.')
    if len(sentences) >= 2:
        score += 0.3

    # Check length (should be substantial but not too long)
    word_count = len(summary.split())
    if 50 <= word_count <= 500:
        score += 0.3
    elif 20 <= word_count < 50 or 500 < word_count <= 1000:
        score += 0.15

    # Check for transition words (indicates logical flow)
    transition_words = [
        'however',
        'therefore',
        'furthermore',
        'additionally',
        'moreover',
        'consequently',
        'thus',
        'hence',
    ]
    if any(word in summary.lower() for word in transition_words):
        score += 0.2

    # Check for proper capitalization and punctuation
    if summary[0].isupper() and summary.rstrip()[-1] in '.!?':
        score += 0.2

    return min(score, 1.0)


def calculate_key_points_relevance(
    key_points: str | None,
    paper_content: str,
    abstract: str | None = None,
) -> float:
    """
    Calculate relevance of key points to paper content.

    Measures how well key points represent the actual content.

    Args:
        key_points: Extracted key points string
        paper_content: Full paper content
        abstract: Optional abstract for comparison

    Returns:
        Relevance score (0.0 to 1.0)
    """
    if not key_points:
        return 0.0

    # Split key points into individual points
    points = [p.strip() for p in key_points.split('\n') if p.strip()]

    if not points:
        return 0.0

    # Use abstract if available, otherwise use paper content
    reference_text = abstract if abstract else paper_content

    # Calculate average token overlap for each point
    relevance_scores = []
    for point in points:
        # Remove bullet point markers
        point_clean = point.lstrip('•-*').strip()
        if not point_clean:
            continue

        overlap_score = calculate_token_overlap_f1(point_clean, reference_text)
        relevance_scores.append(overlap_score)

    if not relevance_scores:
        return 0.0

    return np.mean(relevance_scores)


def calculate_analysis_metrics(
    ground_truth_list: List,  # noqa: UP006
    predicted_list: List,  # noqa: ARG001, UP006
    timing_data: List[Dict[str, any]] | None = None,  # noqa: ARG001, UP006
) -> AnalysisMetrics:
    """
    Calculate comprehensive Analysis pipeline metrics.

    Args:
        ground_truth_list: List of AnalysisGroundTruthPair objects
        predicted_list: List of predicted AnalysisResponse objects
        timing_data: Optional timing and strategy information

    Returns:
        AnalysisMetrics object with all metrics
    """
    # TODO: Implement full metrics calculation
    # This is a placeholder structure

    extraction_metrics = ExtractionMetrics(
        field_completeness=0.0,
        field_accuracy={},
        required_fields_completeness=0.0,
        optional_fields_completeness=0.0,
        avg_field_confidence=0.0,
        total_samples=len(ground_truth_list),
    )

    content_quality_metrics = ContentQualityMetrics(
        summary_coherence=0.0,
        summary_completeness=0.0,
        key_points_relevance=0.0,
        key_points_coverage=0.0,
        methodology_extraction_quality=0.0,
        tag_appropriateness=0.0,
        avg_summary_length=0.0,
        total_samples=len(ground_truth_list),
    )

    strategy_efficiency_metrics = StrategyEfficiencyMetrics(
        strategy_selection_accuracy=0.0,
        avg_processing_time_by_strategy={},
        quality_by_strategy={},
        direct_strategy_usage=0.0,
        map_reduce_strategy_usage=0.0,
        refine_strategy_usage=0.0,
        total_samples=len(ground_truth_list),
    )

    return AnalysisMetrics(
        extraction=extraction_metrics,
        content_quality=content_quality_metrics,
        strategy_efficiency=strategy_efficiency_metrics,
        by_complexity={},
        by_content_length={},
    )
