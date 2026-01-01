"""
Unit tests for fuzzy matching strategies.

Tests:
- DOI exact matching
- Fuzzy title matching
- Author name normalization and matching
- Year validation with tolerance
- Journal matching with abbreviations
"""

import pytest

from thoth.analyze.citations.fuzzy_matcher import (
    normalize_text,
    normalize_author,
    is_abbreviation,
    match_title,
    match_authors,
    match_year,
    match_journal,
    calculate_fuzzy_score,
    WEIGHT_TITLE,
    WEIGHT_AUTHORS,
    WEIGHT_YEAR,
    WEIGHT_JOURNAL,
)


class TestTextNormalization:
    """Test text normalization functions."""

    def test_normalize_text_lowercase(self):
        """Test that text is converted to lowercase."""
        assert normalize_text("DeEp LeArNiNg") == "deep learning"

    def test_normalize_text_remove_punctuation(self):
        """Test that punctuation is removed."""
        result = normalize_text("Machine Learning: A Survey!")
        assert ":" not in result
        assert "!" not in result

    def test_normalize_text_collapse_whitespace(self):
        """Test that multiple spaces are collapsed."""
        result = normalize_text("Deep    Learning   Survey")
        assert result == "deep learning survey"

    def test_normalize_text_strip_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result = normalize_text("  Machine Learning  ")
        assert result == "machine learning"

    def test_normalize_text_empty_string(self):
        """Test normalization of empty string."""
        assert normalize_text("") == ""

    def test_normalize_text_none(self):
        """Test normalization of None."""
        assert normalize_text(None) == ""

    def test_normalize_author_removes_punctuation(self):
        """Test that author name punctuation is removed."""
        result = normalize_author("Smith, J.")
        assert "," not in result
        assert "." not in result

    def test_normalize_author_lowercase(self):
        """Test that author names are lowercased."""
        result = normalize_author("SMITH, John A.")
        assert result == "smith john a"

    def test_normalize_author_empty(self):
        """Test normalization of empty author name."""
        assert normalize_author("") == ""


class TestAbbreviationDetection:
    """Test journal abbreviation detection."""

    def test_is_abbreviation_with_periods(self):
        """Test detection of abbreviations with periods."""
        assert is_abbreviation("Proc. Natl. Acad. Sci.") is True
        assert is_abbreviation("J. Mach. Learn. Res.") is True

    def test_is_abbreviation_all_caps(self):
        """Test detection of all-caps abbreviations."""
        assert is_abbreviation("PNAS") is True
        assert is_abbreviation("IEEE") is True

    def test_is_abbreviation_short_with_caps(self):
        """Test detection of short names with capital letters."""
        assert is_abbreviation("NatComm") is True

    def test_is_abbreviation_full_name(self):
        """Test that full journal names are not detected as abbreviations."""
        assert is_abbreviation("Journal of Machine Learning Research") is False
        assert is_abbreviation("Nature Communications") is False

    def test_is_abbreviation_empty(self):
        """Test abbreviation detection with empty string."""
        assert is_abbreviation("") is False


class TestTitleMatching:
    """Test title fuzzy matching."""

    def test_match_title_exact_match(self):
        """Test exact title match."""
        title = "Deep Learning for Computer Vision"
        score = match_title(title, title)
        assert score == 1.0

    def test_match_title_case_insensitive(self):
        """Test that matching is case-insensitive."""
        title1 = "Deep Learning"
        title2 = "deep learning"
        score = match_title(title1, title2)
        assert score == 1.0

    def test_match_title_word_order(self):
        """Test matching with different word order."""
        title1 = "Deep Learning for Computer Vision"
        title2 = "Computer Vision using Deep Learning"
        score = match_title(title1, title2)

        # Should have high score (same words, different order)
        assert score > 0.7
        assert score < 1.0  # Not perfect due to order difference

    def test_match_title_with_subtitle(self):
        """Test matching titles with subtitles."""
        title1 = "Deep Learning"
        title2 = "Deep Learning: A Comprehensive Survey"
        score = match_title(title1, title2)

        # Should have good score (subset match)
        assert score > 0.8

    def test_match_title_completely_different(self):
        """Test matching completely different titles."""
        title1 = "Deep Learning for Vision"
        title2 = "Natural Language Processing Techniques"
        score = match_title(title1, title2)

        # Should have low score
        assert score < 0.3

    def test_match_title_empty_strings(self):
        """Test matching with empty strings."""
        assert match_title("", "Test") == 0.0
        assert match_title("Test", "") == 0.0
        assert match_title("", "") == 0.0

    def test_match_title_punctuation_ignored(self):
        """Test that punctuation doesn't affect matching."""
        title1 = "Machine Learning: A Survey!"
        title2 = "Machine Learning A Survey"
        score = match_title(title1, title2)

        # Should match well (same words, just punctuation)
        assert score > 0.95


class TestAuthorMatching:
    """Test author list fuzzy matching."""

    def test_match_authors_exact_match(self):
        """Test exact author match."""
        authors1 = ["Smith, J.", "Doe, A."]
        authors2 = ["Smith, J.", "Doe, A."]
        score = match_authors(authors1, authors2)
        assert score >= 0.9

    def test_match_authors_different_formats(self):
        """Test matching with different name formats."""
        authors1 = ["Smith, J.", "Doe, A."]
        authors2 = ["John Smith", "Alice Doe"]
        score = match_authors(authors1, authors2)

        # Should match reasonably well (same people, different format)
        assert score > 0.6

    def test_match_authors_first_author_priority(self):
        """Test that first author has higher weight."""
        # Same first author, different second
        authors1 = ["Smith, J.", "Doe, A."]
        authors2 = ["Smith, J.", "Brown, B."]
        score1 = match_authors(authors1, authors2)

        # Different first author, same second
        authors3 = ["Jones, K.", "Doe, A."]
        authors4 = ["Smith, J.", "Doe, A."]
        score2 = match_authors(authors3, authors4)

        # First author match should score higher
        assert score1 > score2

    def test_match_authors_initials_vs_full_names(self):
        """Test matching initials against full names."""
        authors1 = ["Smith, J."]
        authors2 = ["Smith, John"]
        score = match_authors(authors1, authors2)

        # Should match (same last name)
        assert score > 0.6

    def test_match_authors_additional_authors(self):
        """Test matching with different numbers of authors."""
        authors1 = ["Smith, J.", "Doe, A.", "Brown, B."]
        authors2 = ["Smith, J.", "Doe, A."]
        score = match_authors(authors1, authors2)

        # Should still have good score (first authors match)
        assert score > 0.7

    def test_match_authors_empty_lists(self):
        """Test matching with empty author lists."""
        assert match_authors([], ["Smith, J."]) == 0.0
        assert match_authors(["Smith, J."], []) == 0.0
        assert match_authors([], []) == 0.0

    def test_match_authors_completely_different(self):
        """Test matching completely different author lists."""
        authors1 = ["Smith, J.", "Doe, A."]
        authors2 = ["Johnson, K.", "Williams, L."]
        score = match_authors(authors1, authors2)

        # Should have low score
        assert score < 0.4


class TestYearMatching:
    """Test year matching with tolerance."""

    def test_match_year_exact(self):
        """Test exact year match."""
        score = match_year(2023, 2023)
        assert score == 1.0

    def test_match_year_off_by_one(self):
        """Test year match with ±1 difference."""
        score1 = match_year(2023, 2024)
        score2 = match_year(2023, 2022)

        assert score1 == 0.8
        assert score2 == 0.8

    def test_match_year_off_by_two(self):
        """Test year match with ±2 difference."""
        score1 = match_year(2023, 2025)
        score2 = match_year(2023, 2021)

        assert score1 == 0.4
        assert score2 == 0.4

    def test_match_year_off_by_more(self):
        """Test year match with >2 difference."""
        score = match_year(2023, 2019)
        assert score == 0.0

    def test_match_year_none_values(self):
        """Test year matching with None values."""
        assert match_year(None, 2023) == 0.0
        assert match_year(2023, None) == 0.0
        assert match_year(None, None) == 0.0


class TestJournalMatching:
    """Test journal name matching."""

    def test_match_journal_exact(self):
        """Test exact journal name match."""
        journal = "Nature"
        score = match_journal(journal, journal)
        assert score == 1.0

    def test_match_journal_abbreviation(self):
        """Test matching journal abbreviation."""
        journal1 = "Proc. Natl. Acad. Sci."
        journal2 = "Proceedings of the National Academy of Sciences"
        score = match_journal(journal1, journal2)

        # Should have reasonable score despite abbreviation
        assert score > 0.5

    def test_match_journal_similar_names(self):
        """Test matching similar journal names."""
        journal1 = "Nature Communications"
        journal2 = "Nature Comms"
        score = match_journal(journal1, journal2)

        assert score > 0.7

    def test_match_journal_different(self):
        """Test matching completely different journals."""
        journal1 = "Nature"
        journal2 = "Science"
        score = match_journal(journal1, journal2)

        assert score < 0.5

    def test_match_journal_empty_strings(self):
        """Test journal matching with empty strings."""
        assert match_journal("", "Nature") == 0.0
        assert match_journal("Nature", "") == 0.0
        assert match_journal("", "") == 0.0


class TestCalculateFuzzyScore:
    """Test overall fuzzy score calculation."""

    def test_calculate_fuzzy_score_perfect_match(self):
        """Test fuzzy score for perfect match."""
        score, components = calculate_fuzzy_score(
            title1="Deep Learning Survey",
            title2="Deep Learning Survey",
            authors1=["Smith, J.", "Doe, A."],
            authors2=["Smith, J.", "Doe, A."],
            year1=2023,
            year2=2023,
            journal1="Nature",
            journal2="Nature"
        )

        # Should be very high (near perfect)
        assert score >= 0.95
        assert score <= 1.0

        # Check component scores
        assert components['title'] == 1.0
        assert components['year'] == 1.0
        assert components['overall'] == score

    def test_calculate_fuzzy_score_good_match(self):
        """Test fuzzy score for good but not perfect match."""
        score, components = calculate_fuzzy_score(
            title1="Deep Learning for Computer Vision",
            title2="Computer Vision using Deep Learning",
            authors1=["Smith, J.", "Doe, A."],
            authors2=["Smith, John", "Doe, Alice"],
            year1=2023,
            year2=2024,  # Off by 1
            journal1="Nature",
            journal2="Nature Communications"
        )

        # Should be high confidence
        assert score > 0.75
        assert score < 0.95

        # Title should be good
        assert components['title'] > 0.7
        # Year should be 0.8 (off by 1)
        assert components['year'] == 0.8

    def test_calculate_fuzzy_score_poor_match(self):
        """Test fuzzy score for poor match."""
        score, components = calculate_fuzzy_score(
            title1="Deep Learning for Vision",
            title2="Natural Language Processing",
            authors1=["Smith, J."],
            authors2=["Johnson, K."],
            year1=2023,
            year2=2019,
            journal1="Nature",
            journal2="Science"
        )

        # Should be low score
        assert score < 0.5

        # Title should be low
        assert components['title'] < 0.3
        # Year should be 0.0 (>2 years difference)
        assert components['year'] == 0.0

    def test_calculate_fuzzy_score_weights(self):
        """Test that weights are applied correctly."""
        # Perfect title, poor other fields
        score1, _ = calculate_fuzzy_score(
            title1="Test Paper",
            title2="Test Paper",
            authors1=["A"],
            authors2=["B"],
            year1=2023,
            year2=2019,
            journal1="J1",
            journal2="J2"
        )

        # Poor title, perfect other fields
        score2, _ = calculate_fuzzy_score(
            title1="Paper A",
            title2="Paper B",
            authors1=["Smith, J."],
            authors2=["Smith, J."],
            year1=2023,
            year2=2023,
            journal1="Nature",
            journal2="Nature"
        )

        # Title weighted match should score higher (title has 45% weight)
        assert score1 > score2

    def test_calculate_fuzzy_score_component_breakdown(self):
        """Test that component scores are returned correctly."""
        score, components = calculate_fuzzy_score(
            title1="Test",
            title2="Test",
            authors1=["A"],
            authors2=["A"],
            year1=2023,
            year2=2023,
            journal1="J",
            journal2="J"
        )

        # Check all components are present
        assert 'title' in components
        assert 'authors' in components
        assert 'year' in components
        assert 'journal' in components
        assert 'overall' in components

        # Check that overall equals weighted sum
        calculated_overall = (
            WEIGHT_TITLE * components['title'] +
            WEIGHT_AUTHORS * components['authors'] +
            WEIGHT_YEAR * components['year'] +
            WEIGHT_JOURNAL * components['journal']
        )
        assert abs(components['overall'] - calculated_overall) < 0.001

    def test_calculate_fuzzy_score_missing_fields(self):
        """Test fuzzy score calculation with missing fields."""
        score, components = calculate_fuzzy_score(
            title1="Test Paper",
            title2="Test Paper",
            authors1=None,
            authors2=None,
            year1=None,
            year2=None,
            journal1="",
            journal2=""
        )

        # Should still calculate (based on title only)
        assert score > 0
        # Missing fields should score 0
        assert components['authors'] == 0.0
        assert components['year'] == 0.0
        assert components['journal'] == 0.0


class TestEdgeCases:
    """Test edge cases and special characters."""

    def test_normalize_text_unicode(self):
        """Test normalization of Unicode text."""
        result = normalize_text("深度学习")
        # Should not crash, should return something
        assert isinstance(result, str)

    def test_normalize_text_special_characters(self):
        """Test normalization with special characters."""
        text = "Machine Learning: A Survey (2023) — Part I"
        result = normalize_text(text)

        # Special characters should be removed or converted
        assert ":" not in result
        assert "—" not in result
        assert "(" not in result
        assert ")" not in result

    def test_match_title_very_long_titles(self):
        """Test matching very long titles."""
        title1 = "A" * 500
        title2 = "A" * 500
        score = match_title(title1, title2)

        # Should handle long titles without crashing
        assert score == 1.0

    def test_match_authors_many_authors(self):
        """Test matching with many authors."""
        authors1 = [f"Author{i}" for i in range(50)]
        authors2 = [f"Author{i}" for i in range(50)]
        score = match_authors(authors1, authors2)

        # Should handle many authors
        assert score > 0.9

    def test_match_journal_case_variations(self):
        """Test journal matching with case variations."""
        journal1 = "NATURE"
        journal2 = "nature"
        journal3 = "Nature"

        score1 = match_journal(journal1, journal2)
        score2 = match_journal(journal2, journal3)

        # Should be case-insensitive
        assert score1 == 1.0
        assert score2 == 1.0
