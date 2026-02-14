"""Unit tests for CRAG tri-level retrieval evaluation."""

import pytest

from thoth.rag.document_grader import DocumentGrader, RetrievalConfidence


class TestRetrievalConfidence:
    """Test CRAG tri-level confidence evaluation."""

    @pytest.fixture
    def grader(self):
        """Create document grader instance."""
        from unittest.mock import Mock

        llm = Mock()
        return DocumentGrader(llm_client=llm, threshold=0.5)

    def test_correct_assessment(self, grader):
        """Test CORRECT assessment for high confidence."""
        result = grader.evaluate_retrieval_confidence(
            confidence=0.85, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.CORRECT

    def test_correct_at_threshold(self, grader):
        """Test CORRECT assessment at exact upper threshold."""
        result = grader.evaluate_retrieval_confidence(
            confidence=0.7, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.CORRECT

    def test_ambiguous_assessment(self, grader):
        """Test AMBIGUOUS assessment for mid-range confidence."""
        result = grader.evaluate_retrieval_confidence(
            confidence=0.55, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.AMBIGUOUS

    def test_ambiguous_at_lower_boundary(self, grader):
        """Test AMBIGUOUS at lower threshold boundary."""
        result = grader.evaluate_retrieval_confidence(
            confidence=0.4, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.AMBIGUOUS

    def test_ambiguous_just_below_upper(self, grader):
        """Test AMBIGUOUS just below upper threshold."""
        result = grader.evaluate_retrieval_confidence(
            confidence=0.69, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.AMBIGUOUS

    def test_incorrect_assessment(self, grader):
        """Test INCORRECT assessment for low confidence."""
        result = grader.evaluate_retrieval_confidence(
            confidence=0.25, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.INCORRECT

    def test_incorrect_just_below_lower(self, grader):
        """Test INCORRECT just below lower threshold."""
        result = grader.evaluate_retrieval_confidence(
            confidence=0.39, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.INCORRECT

    def test_incorrect_zero_confidence(self, grader):
        """Test INCORRECT for zero confidence."""
        result = grader.evaluate_retrieval_confidence(
            confidence=0.0, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.INCORRECT

    def test_correct_perfect_confidence(self, grader):
        """Test CORRECT for perfect confidence."""
        result = grader.evaluate_retrieval_confidence(
            confidence=1.0, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result == RetrievalConfidence.CORRECT

    def test_custom_thresholds(self, grader):
        """Test with custom threshold values."""
        # Stricter thresholds
        result = grader.evaluate_retrieval_confidence(
            confidence=0.75, upper_threshold=0.8, lower_threshold=0.5
        )
        assert result == RetrievalConfidence.AMBIGUOUS

        # More lenient thresholds
        result = grader.evaluate_retrieval_confidence(
            confidence=0.55, upper_threshold=0.6, lower_threshold=0.3
        )
        assert result == RetrievalConfidence.AMBIGUOUS

    def test_narrow_ambiguous_range(self, grader):
        """Test with narrow ambiguous range."""
        # Upper and lower close together
        result1 = grader.evaluate_retrieval_confidence(
            confidence=0.51, upper_threshold=0.6, lower_threshold=0.5
        )
        assert result1 == RetrievalConfidence.AMBIGUOUS

        result2 = grader.evaluate_retrieval_confidence(
            confidence=0.49, upper_threshold=0.6, lower_threshold=0.5
        )
        assert result2 == RetrievalConfidence.INCORRECT

        result3 = grader.evaluate_retrieval_confidence(
            confidence=0.61, upper_threshold=0.6, lower_threshold=0.5
        )
        assert result3 == RetrievalConfidence.CORRECT

    def test_enum_values(self):
        """Test enum string values."""
        assert RetrievalConfidence.CORRECT.value == 'correct'
        assert RetrievalConfidence.AMBIGUOUS.value == 'ambiguous'
        assert RetrievalConfidence.INCORRECT.value == 'incorrect'

    def test_default_thresholds(self, grader):
        """Test with default threshold values from plan."""
        # Default: upper=0.7, lower=0.4
        assert grader.evaluate_retrieval_confidence(0.75) == RetrievalConfidence.CORRECT
        assert (
            grader.evaluate_retrieval_confidence(0.55) == RetrievalConfidence.AMBIGUOUS
        )
        assert (
            grader.evaluate_retrieval_confidence(0.35) == RetrievalConfidence.INCORRECT
        )

    def test_boundary_precision(self, grader):
        """Test precise boundary conditions."""
        # Very close to thresholds
        result1 = grader.evaluate_retrieval_confidence(
            confidence=0.7000001, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result1 == RetrievalConfidence.CORRECT

        result2 = grader.evaluate_retrieval_confidence(
            confidence=0.6999999, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result2 == RetrievalConfidence.AMBIGUOUS

        result3 = grader.evaluate_retrieval_confidence(
            confidence=0.4000001, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result3 == RetrievalConfidence.AMBIGUOUS

        result4 = grader.evaluate_retrieval_confidence(
            confidence=0.3999999, upper_threshold=0.7, lower_threshold=0.4
        )
        assert result4 == RetrievalConfidence.INCORRECT
