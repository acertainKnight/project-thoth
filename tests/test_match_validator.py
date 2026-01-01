"""
Tests for match_validator module.

Tests cover:
1. ComponentScores representation
2. MatchCandidate functionality
3. MatchValidator.validate_match() - scoring and constraint checking
4. MatchValidator.check_hard_constraints() - individual constraint rules
5. MatchValidator.get_best_match() - candidate selection
"""

import pytest

from thoth.analyze.citations.match_validator import (
    ComponentScores,
    MatchCandidate,
    MatchValidator,
)
from thoth.utilities.schemas.citations import Citation


class TestComponentScores:
    """Tests for ComponentScores dataclass."""

    def test_default_initialization(self):
        """Test ComponentScores initializes with zeros."""
        scores = ComponentScores()
        assert scores.title == 0.0
        assert scores.authors == 0.0
        assert scores.year == 0.0
        assert scores.journal == 0.0
        assert scores.overall == 0.0

    def test_custom_initialization(self):
        """Test ComponentScores with custom values."""
        scores = ComponentScores(
            title=0.9, authors=0.8, year=1.0, journal=0.7, overall=0.85
        )
        assert scores.title == 0.9
        assert scores.authors == 0.8
        assert scores.year == 1.0
        assert scores.journal == 0.7
        assert scores.overall == 0.85

    def test_repr(self):
        """Test ComponentScores string representation."""
        scores = ComponentScores(
            title=0.9, authors=0.8, year=1.0, journal=0.7, overall=0.85
        )
        repr_str = repr(scores)
        assert "title=0.900" in repr_str
        assert "authors=0.800" in repr_str
        assert "overall=0.850" in repr_str


class TestMatchCandidate:
    """Tests for MatchCandidate dataclass."""

    def test_initialization(self):
        """Test MatchCandidate initialization."""
        citation = Citation(title="Test Paper", authors=["Smith, J."], year=2020)
        candidate = MatchCandidate(citation=citation, source="semantic_scholar")

        assert candidate.citation == citation
        assert candidate.source == "semantic_scholar"
        assert candidate.passed_constraints is True
        assert candidate.rejection_reason is None
        assert isinstance(candidate.component_scores, ComponentScores)

    def test_overall_score_property(self):
        """Test overall_score convenience property."""
        citation = Citation(title="Test Paper")
        candidate = MatchCandidate(citation=citation)
        candidate.component_scores.overall = 0.87

        assert candidate.overall_score == 0.87

    def test_repr(self):
        """Test MatchCandidate string representation."""
        citation = Citation(title="Test Paper")
        candidate = MatchCandidate(citation=citation, source="crossref")
        candidate.component_scores.overall = 0.75

        repr_str = repr(candidate)
        assert "✓" in repr_str  # Passed constraints symbol
        assert "0.75" in repr_str
        assert "crossref" in repr_str

    def test_repr_failed_constraints(self):
        """Test MatchCandidate repr when constraints failed."""
        citation = Citation(title="Test Paper")
        candidate = MatchCandidate(citation=citation)
        candidate.passed_constraints = False

        repr_str = repr(candidate)
        assert "✗" in repr_str  # Failed constraints symbol


class TestMatchValidator:
    """Tests for MatchValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a MatchValidator instance for tests."""
        return MatchValidator()

    @pytest.fixture
    def input_citation(self):
        """Create a sample input citation for testing."""
        return Citation(
            title="Machine Learning: A Probabilistic Perspective",
            authors=["Murphy, Kevin P."],
            year=2012,
            journal="MIT Press",
        )

    def test_initialization(self, validator):
        """Test MatchValidator initializes correctly."""
        assert validator is not None

    def test_validate_match_perfect_match(self, validator, input_citation):
        """Test validate_match with a perfect match."""
        # Create identical candidate
        candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning: A Probabilistic Perspective",
                authors=["Murphy, Kevin P."],
                year=2012,
                journal="MIT Press",
            ),
            source="test",
        )

        score = validator.validate_match(input_citation, candidate)

        assert score > 0.95  # Should be near perfect
        assert candidate.passed_constraints is True
        assert candidate.rejection_reason is None
        assert candidate.component_scores.overall > 0.95

    def test_validate_match_good_match(self, validator, input_citation):
        """Test validate_match with a good but not perfect match."""
        # Slightly different title, same authors/year
        candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning: Probabilistic Perspective",
                authors=["Murphy, K. P."],
                year=2012,
                journal="MIT Press",
            ),
            source="test",
        )

        score = validator.validate_match(input_citation, candidate)

        assert 0.7 < score < 1.0  # Should be high but not perfect
        assert candidate.passed_constraints is True
        assert candidate.component_scores.title > 0.8

    def test_validate_match_failed_year_constraint(self, validator, input_citation):
        """Test validate_match rejects candidate with year difference > 5."""
        # Year difference of 10 years
        candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning: A Probabilistic Perspective",
                authors=["Murphy, Kevin P."],
                year=2022,  # 10 years different
                journal="MIT Press",
            ),
            source="test",
        )

        score = validator.validate_match(input_citation, candidate)

        assert score == 0.0
        assert candidate.passed_constraints is False
        assert "Year difference too large" in candidate.rejection_reason

    def test_validate_match_failed_author_constraint(self, validator, input_citation):
        """Test validate_match rejects candidate with no author overlap."""
        # Completely different authors
        candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning: A Probabilistic Perspective",
                authors=["Smith, John", "Doe, Jane"],
                year=2012,
                journal="MIT Press",
            ),
            source="test",
        )

        score = validator.validate_match(input_citation, candidate)

        assert score == 0.0
        assert candidate.passed_constraints is False
        assert "No author overlap" in candidate.rejection_reason

    def test_validate_match_failed_journal_constraint(self, validator, input_citation):
        """Test validate_match rejects candidate with contradictory journal."""
        # Completely different journal (with no word overlap)
        candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning: A Probabilistic Perspective",
                authors=["Murphy, Kevin P."],
                year=2012,
                journal="Journal of Underwater Basket Weaving",  # Completely unrelated
            ),
            source="test",
        )

        score = validator.validate_match(input_citation, candidate)

        assert score == 0.0
        assert candidate.passed_constraints is False
        assert "Journal names contradictory" in candidate.rejection_reason

    def test_validate_match_missing_fields(self, validator):
        """Test validate_match handles missing fields gracefully."""
        input_cit = Citation(title="Test Paper")  # Minimal citation
        candidate = MatchCandidate(
            citation=Citation(title="Test Paper"), source="test"
        )

        score = validator.validate_match(input_cit, candidate)

        # Should still calculate a score based on available fields
        assert 0.0 <= score <= 1.0
        assert candidate.passed_constraints is True

    def test_check_hard_constraints_year_boundary(self, validator, input_citation):
        """Test year constraint at boundary (exactly 5 years)."""
        # Exactly 5 years difference should pass
        candidate = MatchCandidate(
            citation=Citation(
                title="Test",
                authors=["Murphy, Kevin P."],
                year=2017,  # Exactly 5 years
            ),
            source="test",
        )

        result = validator.check_hard_constraints(input_citation, candidate)

        assert result is True
        assert candidate.passed_constraints is True

    def test_check_hard_constraints_year_exceeds(self, validator, input_citation):
        """Test year constraint when just exceeding limit (6 years)."""
        # 6 years difference should fail
        candidate = MatchCandidate(
            citation=Citation(
                title="Test",
                authors=["Murphy, Kevin P."],
                year=2018,  # 6 years difference
            ),
            source="test",
        )

        result = validator.check_hard_constraints(input_citation, candidate)

        assert result is False
        assert candidate.passed_constraints is False

    def test_check_hard_constraints_author_normalization(self, validator, input_citation):
        """Test author constraint with name variations."""
        # Different format but same author (should pass)
        candidate = MatchCandidate(
            citation=Citation(
                title="Test",
                authors=["K. P. Murphy"],  # Different format
                year=2012,
            ),
            source="test",
        )

        result = validator.check_hard_constraints(input_citation, candidate)

        # This should pass because normalized names match
        # 'murphy kevin p' matches both formats
        assert result is True

    def test_check_hard_constraints_journal_abbreviation(self, validator):
        """Test journal constraint with abbreviations."""
        input_cit = Citation(
            title="Test",
            authors=["Smith, J."],
            year=2020,
            journal="Proceedings of the National Academy of Sciences",
        )

        # Abbreviated journal name
        candidate = MatchCandidate(
            citation=Citation(
                title="Test",
                authors=["Smith, J."],
                year=2020,
                journal="Proc. Natl. Acad. Sci.",
            ),
            source="test",
        )

        result = validator.check_hard_constraints(input_cit, candidate)

        # Should pass because fuzzy matching handles abbreviations
        assert result is True

    def test_get_best_match_single_candidate(self, validator, input_citation):
        """Test get_best_match with single valid candidate."""
        candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning: A Probabilistic Perspective",
                authors=["Murphy, K. P."],
                year=2012,
            ),
            source="s2",
        )

        validator.validate_match(input_citation, candidate)
        best = validator.get_best_match([candidate])

        assert best is candidate
        assert best.passed_constraints is True

    def test_get_best_match_multiple_candidates(self, validator, input_citation):
        """Test get_best_match selects highest scoring candidate."""
        # Create three candidates with different quality matches
        candidate1 = MatchCandidate(
            citation=Citation(
                title="Machine Learning Probabilistic",  # Partial match
                authors=["Murphy, K."],
                year=2012,
            ),
            source="crossref",
        )

        candidate2 = MatchCandidate(
            citation=Citation(
                title="Machine Learning: A Probabilistic Perspective",  # Perfect
                authors=["Murphy, Kevin P."],
                year=2012,
            ),
            source="s2",
        )

        candidate3 = MatchCandidate(
            citation=Citation(
                title="Machine Learning",  # Weak match
                authors=["Murphy, K."],
                year=2013,
            ),
            source="openalex",
        )

        candidates = [candidate1, candidate2, candidate3]

        # Validate all candidates
        for candidate in candidates:
            validator.validate_match(input_citation, candidate)

        best = validator.get_best_match(candidates)

        # Should select candidate2 (best match)
        assert best is candidate2
        assert best.source == "s2"
        assert best.overall_score > candidate1.overall_score
        assert best.overall_score > candidate3.overall_score

    def test_get_best_match_empty_list(self, validator):
        """Test get_best_match with empty candidate list."""
        best = validator.get_best_match([])
        assert best is None

    def test_get_best_match_all_failed_constraints(self, validator, input_citation):
        """Test get_best_match when all candidates fail constraints."""
        # Create candidates that all fail year constraint
        candidate1 = MatchCandidate(
            citation=Citation(
                title="Test",
                authors=["Murphy, K."],
                year=2000,  # 12 years difference
            ),
            source="s1",
        )

        candidate2 = MatchCandidate(
            citation=Citation(
                title="Test",
                authors=["Murphy, K."],
                year=2001,  # 11 years difference
            ),
            source="s2",
        )

        candidates = [candidate1, candidate2]

        # Validate all candidates
        for candidate in candidates:
            validator.validate_match(input_citation, candidate)

        best = validator.get_best_match(candidates)

        # Should return None since all failed
        assert best is None

    def test_get_best_match_mixed_constraints(self, validator, input_citation):
        """Test get_best_match with mix of passing and failing candidates."""
        # One passes, one fails
        good_candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning Probabilistic",
                authors=["Murphy, K."],
                year=2012,
            ),
            source="s2",
        )

        bad_candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning",
                authors=["Smith, J."],  # No author overlap
                year=2012,
            ),
            source="crossref",
        )

        candidates = [bad_candidate, good_candidate]

        # Validate all candidates
        for candidate in candidates:
            validator.validate_match(input_citation, candidate)

        best = validator.get_best_match(candidates)

        # Should select good_candidate
        assert best is good_candidate
        assert best.passed_constraints is True

    def test_component_scores_populated(self, validator, input_citation):
        """Test that component scores are properly populated."""
        candidate = MatchCandidate(
            citation=Citation(
                title="Machine Learning: Probabilistic Perspective",
                authors=["Murphy, Kevin"],
                year=2012,
                journal="MIT Press",
            ),
            source="test",
        )

        validator.validate_match(input_citation, candidate)

        # Check all components are populated
        assert 0.0 <= candidate.component_scores.title <= 1.0
        assert 0.0 <= candidate.component_scores.authors <= 1.0
        assert 0.0 <= candidate.component_scores.year <= 1.0
        assert 0.0 <= candidate.component_scores.journal <= 1.0
        assert 0.0 <= candidate.component_scores.overall <= 1.0

        # Overall should be weighted combination
        assert candidate.component_scores.overall > 0.0


class TestIntegrationScenarios:
    """Integration tests for realistic matching scenarios."""

    @pytest.fixture
    def validator(self):
        """Create a MatchValidator instance for tests."""
        return MatchValidator()

    def test_real_world_semantic_scholar_match(self, validator):
        """Test realistic scenario matching with Semantic Scholar data."""
        # Simulate an extracted citation
        input_cit = Citation(
            title="Attention Is All You Need",
            authors=["Vaswani, A.", "Shazeer, N.", "Parmar, N."],
            year=2017,
        )

        # Simulate Semantic Scholar API result
        s2_candidate = MatchCandidate(
            citation=Citation(
                title="Attention is All you Need",  # Slight capitalization difference
                authors=[
                    "Ashish Vaswani",
                    "Noam Shazeer",
                    "Niki Parmar",
                ],  # Full names
                year=2017,
                journal="NeurIPS",
            ),
            source="semantic_scholar",
        )

        score = validator.validate_match(input_cit, s2_candidate)

        # The title and year match perfectly, but author scoring is limited
        # because initials vs full names don't get credit in fuzzy_matcher
        # However, it should still pass constraints (shared last names)
        assert score > 0.5  # Should be reasonable match
        assert s2_candidate.passed_constraints is True
        assert s2_candidate.component_scores.title > 0.95  # Perfect title match

    def test_arxiv_vs_published_version(self, validator):
        """Test matching arXiv preprint to published version."""
        # arXiv version
        arxiv_cit = Citation(
            title="Deep Residual Learning for Image Recognition",
            authors=["He, K.", "Zhang, X.", "Ren, S.", "Sun, J."],
            year=2015,  # arXiv preprint year
        )

        # Published version
        published_candidate = MatchCandidate(
            citation=Citation(
                title="Deep Residual Learning for Image Recognition",
                authors=["Kaiming He", "Xiangyu Zhang", "Shaoqing Ren", "Jian Sun"],
                year=2016,  # Conference publication year
                journal="CVPR",
            ),
            source="crossref",
        )

        score = validator.validate_match(arxiv_cit, published_candidate)

        # Should match despite 1 year difference (within tolerance)
        # Author scoring limited due to initials vs full names
        assert score > 0.5
        assert published_candidate.passed_constraints is True
        assert published_candidate.component_scores.title > 0.95

    def test_journal_abbreviation_matching(self, validator):
        """Test matching with journal abbreviations."""
        input_cit = Citation(
            title="Quantum Computing Basics",
            authors=["Nielsen, M. A."],
            year=2010,
            journal="Physical Review Letters",
        )

        # Abbreviated journal
        abbreviated_candidate = MatchCandidate(
            citation=Citation(
                title="Quantum Computing Basics",
                authors=["Michael A. Nielsen"],
                year=2010,
                journal="Phys. Rev. Lett.",  # Common abbreviation
            ),
            source="crossref",
        )

        score = validator.validate_match(input_cit, abbreviated_candidate)

        # Author scoring limited due to initials vs full names
        assert score > 0.5  # Should be reasonable match
        assert abbreviated_candidate.passed_constraints is True
        assert abbreviated_candidate.component_scores.title > 0.95
