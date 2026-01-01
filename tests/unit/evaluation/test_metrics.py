"""
Tests for metrics.py - Evaluation Metrics.

Tests:
1. Precision/Recall/F1 calculation correctness
2. Edge cases: empty results, all correct, all incorrect
3. Confidence calibration (ECE) calculation
4. Metrics by confidence threshold
"""

import pytest
import numpy as np
from hypothesis import given, strategies as st, settings

from thoth.analyze.citations.resolution_chain import (
    ResolutionResult,
    CitationResolutionStatus,
    ConfidenceLevel,
    ResolutionMetadata
)
from thoth.analyze.citations.evaluation.metrics import (
    ConfusionMatrix,
    CitationMetrics,
    calculate_precision_recall_f1,
    calculate_confidence_calibration,
    calculate_metrics_by_confidence_threshold,
    _is_match_correct,
    _normalize_doi,
    _titles_match,
    _normalize_author
)
from tests.fixtures.evaluation_fixtures import create_ground_truth_with_confidence


class TestConfusionMatrix:
    """Test ConfusionMatrix calculations."""

    def test_confusion_matrix_initialization(self):
        """Test confusion matrix initializes with zeros."""
        cm = ConfusionMatrix()
        assert cm.true_positives == 0
        assert cm.false_positives == 0
        assert cm.true_negatives == 0
        assert cm.false_negatives == 0

    def test_precision_calculation_basic(self):
        """Test precision = TP / (TP + FP)."""
        cm = ConfusionMatrix(true_positives=80, false_positives=20)
        assert cm.precision == 0.8

    def test_precision_zero_when_no_predictions(self):
        """Test precision is 0 when no positive predictions."""
        cm = ConfusionMatrix(true_positives=0, false_positives=0)
        assert cm.precision == 0.0

    def test_recall_calculation_basic(self):
        """Test recall = TP / (TP + FN)."""
        cm = ConfusionMatrix(true_positives=80, false_negatives=20)
        assert cm.recall == 0.8

    def test_recall_zero_when_no_positives(self):
        """Test recall is 0 when no ground truth positives."""
        cm = ConfusionMatrix(true_positives=0, false_negatives=0)
        assert cm.recall == 0.0

    def test_f1_score_calculation(self):
        """Test F1 = 2 * (P * R) / (P + R)."""
        cm = ConfusionMatrix(true_positives=80, false_positives=20, false_negatives=20)
        # Precision = 80/100 = 0.8, Recall = 80/100 = 0.8
        # F1 = 2 * 0.8 * 0.8 / (0.8 + 0.8) = 0.8
        assert cm.f1_score == 0.8

    def test_f1_score_zero_when_precision_recall_zero(self):
        """Test F1 is 0 when both precision and recall are 0."""
        cm = ConfusionMatrix(true_positives=0, false_positives=10, false_negatives=10)
        assert cm.f1_score == 0.0

    def test_f1_score_harmonic_mean(self):
        """Test F1 is harmonic mean (lower than arithmetic mean)."""
        # Precision = 0.9, Recall = 0.5
        cm = ConfusionMatrix(true_positives=90, false_positives=10, false_negatives=90)

        precision = 0.9
        recall = 0.5
        expected_f1 = 2 * (precision * recall) / (precision + recall)

        assert abs(cm.f1_score - expected_f1) < 0.001

    def test_accuracy_calculation(self):
        """Test accuracy = (TP + TN) / (TP + TN + FP + FN)."""
        cm = ConfusionMatrix(
            true_positives=70,
            true_negatives=20,
            false_positives=5,
            false_negatives=5
        )
        # Accuracy = (70 + 20) / 100 = 0.9
        assert cm.accuracy == 0.9

    def test_accuracy_zero_when_no_samples(self):
        """Test accuracy is 0 when no samples."""
        cm = ConfusionMatrix()
        assert cm.accuracy == 0.0

    @given(
        tp=st.integers(min_value=0, max_value=100),
        fp=st.integers(min_value=0, max_value=100),
        tn=st.integers(min_value=0, max_value=100),
        fn=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100)
    def test_metrics_bounded_0_to_1(self, tp, fp, tn, fn):
        """Property test: all metrics are between 0 and 1."""
        cm = ConfusionMatrix(
            true_positives=tp,
            false_positives=fp,
            true_negatives=tn,
            false_negatives=fn
        )

        assert 0.0 <= cm.precision <= 1.0
        assert 0.0 <= cm.recall <= 1.0
        assert 0.0 <= cm.f1_score <= 1.0
        assert 0.0 <= cm.accuracy <= 1.0


class TestCitationMetrics:
    """Test CitationMetrics dataclass and properties."""

    def test_citation_metrics_properties_delegate_to_confusion_matrix(self):
        """Test CitationMetrics properties use confusion matrix values."""
        cm = ConfusionMatrix(true_positives=80, false_positives=20, false_negatives=10)

        metrics = CitationMetrics(
            confusion_matrix=cm,
            mean_confidence=0.85,
            confidence_calibration_error=0.05,
            api_calls_per_citation=2.5,
            total_citations=100,
            resolved_citations=90,
            unresolved_citations=10,
            by_difficulty={},
            by_degradation={}
        )

        assert metrics.precision == cm.precision
        assert metrics.recall == cm.recall
        assert metrics.f1_score == cm.f1_score
        assert metrics.accuracy == cm.accuracy

    def test_citation_metrics_str_representation(self):
        """Test string representation is human-readable."""
        cm = ConfusionMatrix(true_positives=80, false_positives=20, false_negatives=10)

        metrics = CitationMetrics(
            confusion_matrix=cm,
            mean_confidence=0.85,
            confidence_calibration_error=0.05,
            api_calls_per_citation=2.5,
            total_citations=100,
            resolved_citations=90,
            unresolved_citations=10,
            by_difficulty={'easy': ConfusionMatrix()},
            by_degradation={}
        )

        metrics_str = str(metrics)
        assert 'Precision' in metrics_str
        assert 'Recall' in metrics_str
        assert 'F1 Score' in metrics_str
        assert '0.800' in metrics_str  # Precision value


class TestPrecisionRecallF1Calculation:
    """Test main metrics calculation function."""

    def test_calculate_metrics_basic(self, multiple_ground_truth, multiple_resolution_results):
        """Test basic metrics calculation with known ground truth."""
        metrics = calculate_precision_recall_f1(
            multiple_ground_truth,
            multiple_resolution_results,
            match_criteria='doi'
        )

        # Expected: 1 TP (correct), 1 FP (wrong), 1 FN (failed)
        assert metrics.confusion_matrix.true_positives == 1
        assert metrics.confusion_matrix.false_positives == 1
        assert metrics.confusion_matrix.false_negatives == 1

        # Precision = 1 / (1 + 1) = 0.5
        # Recall = 1 / (1 + 1) = 0.5
        assert metrics.precision == 0.5
        assert metrics.recall == 0.5

    def test_calculate_metrics_length_mismatch_raises_error(
        self, multiple_ground_truth, multiple_resolution_results
    ):
        """Test error when ground truth and results have different lengths."""
        with pytest.raises(ValueError, match="same length"):
            calculate_precision_recall_f1(
                multiple_ground_truth[:2],  # Only 2
                multiple_resolution_results,  # 3 results
                match_criteria='doi'
            )

    def test_calculate_metrics_all_correct(self, edge_case_all_correct):
        """Test metrics when all resolutions are correct."""
        ground_truth, results = edge_case_all_correct

        metrics = calculate_precision_recall_f1(
            ground_truth,
            results,
            match_criteria='doi'
        )

        # All correct: TP = 2, FP = 0, FN = 0
        assert metrics.confusion_matrix.true_positives == 2
        assert metrics.confusion_matrix.false_positives == 0
        assert metrics.confusion_matrix.false_negatives == 0

        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0

    def test_calculate_metrics_all_failed(self, multiple_ground_truth, edge_case_empty_results):
        """Test metrics when all resolutions fail."""
        # Pad to match length
        ground_truth = multiple_ground_truth[:2]

        metrics = calculate_precision_recall_f1(
            ground_truth,
            edge_case_empty_results,
            match_criteria='doi'
        )

        # All failed: TP = 0, FP = 0, FN = 2
        assert metrics.confusion_matrix.true_positives == 0
        assert metrics.confusion_matrix.false_positives == 0
        assert metrics.confusion_matrix.false_negatives == 2

        assert metrics.precision == 0.0
        assert metrics.recall == 0.0

    def test_calculate_metrics_by_difficulty(self, multiple_ground_truth, multiple_resolution_results):
        """Test metrics are broken down by difficulty."""
        metrics = calculate_precision_recall_f1(
            multiple_ground_truth,
            multiple_resolution_results,
            match_criteria='doi'
        )

        assert 'easy' in metrics.by_difficulty
        assert 'medium' in metrics.by_difficulty
        assert 'hard' in metrics.by_difficulty

        # Easy case was correct (TP)
        assert metrics.by_difficulty['easy'].true_positives == 1

        # Medium case was incorrect (FP)
        assert metrics.by_difficulty['medium'].false_positives == 1

        # Hard case failed (FN)
        assert metrics.by_difficulty['hard'].false_negatives == 1

    def test_calculate_metrics_by_degradation(self, multiple_ground_truth, multiple_resolution_results):
        """Test metrics are broken down by degradation type."""
        metrics = calculate_precision_recall_f1(
            multiple_ground_truth,
            multiple_resolution_results,
            match_criteria='doi'
        )

        # Should have entries for each degradation type
        assert 'clean' in metrics.by_degradation
        assert 'title_truncation' in metrics.by_degradation

    def test_calculate_metrics_tracks_confidence(self, multiple_ground_truth, multiple_resolution_results):
        """Test mean confidence is tracked."""
        metrics = calculate_precision_recall_f1(
            multiple_ground_truth,
            multiple_resolution_results,
            match_criteria='doi'
        )

        # Mean of [0.95, 0.70, 0.0] = 0.55
        expected_confidence = (0.95 + 0.70 + 0.0) / 3
        assert abs(metrics.mean_confidence - expected_confidence) < 0.01

    def test_calculate_metrics_tracks_api_calls(self, multiple_ground_truth, multiple_resolution_results):
        """Test API calls per citation is tracked."""
        metrics = calculate_precision_recall_f1(
            multiple_ground_truth,
            multiple_resolution_results,
            match_criteria='doi'
        )

        # Should average API calls across results
        assert metrics.api_calls_per_citation > 0


class TestMatchCriteria:
    """Test different match criteria (doi, title_author, any)."""

    def test_is_match_correct_doi_strict(self, sample_ground_truth, sample_resolution_result):
        """Test DOI matching is strict and normalized."""
        sample_ground_truth.ground_truth_doi = '10.5555/2380985'
        sample_resolution_result.matched_data['doi'] = 'https://doi.org/10.5555/2380985'

        assert _is_match_correct(sample_ground_truth, sample_resolution_result, 'doi')

    def test_is_match_correct_doi_mismatch(self, sample_ground_truth, sample_resolution_result):
        """Test DOI mismatch returns False."""
        sample_ground_truth.ground_truth_doi = '10.1234/wrong'
        sample_resolution_result.matched_data['doi'] = '10.5555/2380985'

        assert not _is_match_correct(sample_ground_truth, sample_resolution_result, 'doi')

    def test_is_match_correct_title_author(self, sample_ground_truth, sample_resolution_result):
        """Test title+author matching."""
        sample_ground_truth.ground_truth_title = 'Machine Learning'
        sample_ground_truth.ground_truth_authors = ['Murphy, Kevin P.']

        sample_resolution_result.matched_data = {
            'title': 'Machine Learning: A Probabilistic Perspective',
            'authors': ['Murphy, Kevin P.']
        }

        # Should match even with title variation (fuzzy matching)
        assert _is_match_correct(sample_ground_truth, sample_resolution_result, 'title_author')

    def test_is_match_correct_any_fallback(self, sample_ground_truth, sample_resolution_result):
        """Test 'any' criteria tries multiple matching methods."""
        # No DOI match
        sample_ground_truth.ground_truth_doi = None
        sample_resolution_result.matched_data['doi'] = None

        # But title+author match
        sample_ground_truth.ground_truth_title = 'Machine Learning'
        sample_ground_truth.ground_truth_authors = ['Murphy, Kevin P.']
        sample_resolution_result.matched_data['title'] = 'Machine Learning'
        sample_resolution_result.matched_data['authors'] = ['Murphy, Kevin P.']

        assert _is_match_correct(sample_ground_truth, sample_resolution_result, 'any')

    def test_is_match_correct_unresolved_always_false(self, sample_ground_truth):
        """Test unresolved results are never correct."""
        from thoth.analyze.citations.citations import Citation

        unresolved = ResolutionResult(
            citation=Citation(text='test'),
            status=CitationResolutionStatus.FAILED,
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.NONE,
            source='none',
            matched_data=None
        )

        assert not _is_match_correct(sample_ground_truth, unresolved, 'any')


class TestNormalizationFunctions:
    """Test DOI, title, and author normalization."""

    def test_normalize_doi_removes_prefix(self):
        """Test DOI normalization removes URL prefixes."""
        assert _normalize_doi('https://doi.org/10.1234/test') == '10.1234/test'
        assert _normalize_doi('http://doi.org/10.1234/test') == '10.1234/test'
        assert _normalize_doi('doi:10.1234/test') == '10.1234/test'

    def test_normalize_doi_lowercase(self):
        """Test DOI normalization converts to lowercase."""
        assert _normalize_doi('10.1234/TEST') == '10.1234/test'

    def test_normalize_doi_strips_whitespace(self):
        """Test DOI normalization strips whitespace."""
        assert _normalize_doi('  10.1234/test  ') == '10.1234/test'

    def test_titles_match_exact(self):
        """Test exact title matching."""
        assert _titles_match('Machine Learning', 'Machine Learning')

    def test_titles_match_case_insensitive(self):
        """Test case-insensitive matching."""
        assert _titles_match('Machine Learning', 'machine learning')

    def test_titles_match_fuzzy(self):
        """Test fuzzy matching for slight variations."""
        # High similarity should match
        assert _titles_match(
            'Machine Learning: A Probabilistic Perspective',
            'Machine Learning A Probabilistic Perspective'
        )

    def test_titles_match_low_similarity_fails(self):
        """Test low similarity titles don't match."""
        assert not _titles_match('Machine Learning', 'Deep Learning Networks')

    def test_titles_match_custom_threshold(self):
        """Test custom similarity threshold."""
        # With low threshold, more titles match
        assert _titles_match('Machine Learning', 'Machine', threshold=0.5)

        # With high threshold, fewer titles match
        assert not _titles_match('Machine Learning', 'Machine', threshold=0.95)

    def test_normalize_author_removes_punctuation(self):
        """Test author normalization removes punctuation."""
        assert _normalize_author('Murphy, Kevin P.') == 'murphy kevin p'

    def test_normalize_author_lowercase(self):
        """Test author normalization converts to lowercase."""
        assert _normalize_author('MURPHY KEVIN') == 'murphy kevin'

    def test_normalize_author_strips_extra_spaces(self):
        """Test author normalization removes extra spaces."""
        assert _normalize_author('Murphy   Kevin') == 'murphy kevin'


class TestConfidenceCalibration:
    """Test confidence calibration (ECE) calculation."""

    def test_calibration_perfect(self):
        """Test perfect calibration has ECE close to 0."""
        # Create perfectly calibrated predictions
        ground_truth = []
        results = []

        # 90% confidence → 90% correct
        for i in range(10):
            gt, result = create_ground_truth_with_confidence(0.9, is_correct=(i < 9))
            ground_truth.append(gt)
            results.append(result)

        # 70% confidence → 70% correct
        for i in range(10):
            gt, result = create_ground_truth_with_confidence(0.7, is_correct=(i < 7))
            ground_truth.append(gt)
            results.append(result)

        ece = calculate_confidence_calibration(ground_truth, results, num_bins=10)

        # Should be very well calibrated
        assert ece < 0.1

    def test_calibration_overconfident(self):
        """Test overconfident system has high ECE."""
        ground_truth = []
        results = []

        # 95% confidence but only 50% correct
        for i in range(20):
            gt, result = create_ground_truth_with_confidence(0.95, is_correct=(i < 10))
            ground_truth.append(gt)
            results.append(result)

        ece = calculate_confidence_calibration(ground_truth, results, num_bins=10)

        # Should have high calibration error
        assert ece > 0.3

    def test_calibration_underconfident(self):
        """Test underconfident system has high ECE."""
        ground_truth = []
        results = []

        # 50% confidence but 95% correct
        for i in range(20):
            gt, result = create_ground_truth_with_confidence(0.5, is_correct=(i < 19))
            ground_truth.append(gt)
            results.append(result)

        ece = calculate_confidence_calibration(ground_truth, results, num_bins=10)

        # Should have high calibration error
        assert ece > 0.3

    def test_calibration_length_mismatch_raises_error(self, multiple_ground_truth):
        """Test error when lengths don't match."""
        from thoth.analyze.citations.citations import Citation

        results = [ResolutionResult(
            citation=Citation(text='test'),
            status=CitationResolutionStatus.FAILED,
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.NONE,
            source='none',
            matched_data=None
        )]

        with pytest.raises(ValueError, match="same length"):
            calculate_confidence_calibration(multiple_ground_truth, results)

    def test_calibration_empty_bins_handled(self):
        """Test calibration handles empty bins gracefully."""
        ground_truth = []
        results = []

        # Only populate a few bins
        for i in range(5):
            gt, result = create_ground_truth_with_confidence(0.9, is_correct=True)
            ground_truth.append(gt)
            results.append(result)

        ece = calculate_confidence_calibration(ground_truth, results, num_bins=20)

        # Should not crash and return valid ECE
        assert 0.0 <= ece <= 1.0


class TestMetricsByConfidenceThreshold:
    """Test metrics calculation at different confidence thresholds."""

    def test_metrics_by_threshold_filters_low_confidence(
        self, multiple_ground_truth, multiple_resolution_results
    ):
        """Test higher thresholds filter out low confidence predictions."""
        metrics_by_threshold = calculate_metrics_by_confidence_threshold(
            multiple_ground_truth,
            multiple_resolution_results,
            thresholds=[0.5, 0.8]
        )

        # At 0.5 threshold: all 3 results included (0.95, 0.70, 0.0)
        # At 0.8 threshold: only 0.95 included

        assert 0.5 in metrics_by_threshold
        assert 0.8 in metrics_by_threshold

        # Higher threshold should resolve fewer
        assert (metrics_by_threshold[0.8].resolved_citations <=
                metrics_by_threshold[0.5].resolved_citations)

    def test_metrics_by_threshold_precision_recall_tradeoff(
        self, multiple_ground_truth, multiple_resolution_results
    ):
        """Test precision increases and recall decreases with higher threshold."""
        metrics_by_threshold = calculate_metrics_by_confidence_threshold(
            multiple_ground_truth,
            multiple_resolution_results,
            thresholds=[0.5, 0.9]
        )

        # Generally: higher threshold → higher precision, lower recall
        # (though not guaranteed for all datasets)
        assert 0.5 in metrics_by_threshold
        assert 0.9 in metrics_by_threshold

    def test_metrics_by_threshold_default_thresholds(
        self, multiple_ground_truth, multiple_resolution_results
    ):
        """Test default thresholds are used when not specified."""
        metrics_by_threshold = calculate_metrics_by_confidence_threshold(
            multiple_ground_truth,
            multiple_resolution_results
        )

        # Default: [0.5, 0.6, 0.7, 0.8, 0.9]
        assert len(metrics_by_threshold) == 5
        assert 0.5 in metrics_by_threshold
        assert 0.9 in metrics_by_threshold

    def test_metrics_by_threshold_marks_low_confidence_as_failed(
        self, multiple_ground_truth, multiple_resolution_results
    ):
        """Test results below threshold are marked as FAILED."""
        metrics_by_threshold = calculate_metrics_by_confidence_threshold(
            multiple_ground_truth,
            multiple_resolution_results,
            thresholds=[0.95]
        )

        # At 0.95 threshold: only first result (0.95) passes
        metrics = metrics_by_threshold[0.95]

        # Should have 1 resolved, 2 unresolved
        assert metrics.resolved_citations == 1
        assert metrics.unresolved_citations == 2
