"""
Unit tests for citation formatting - core business logic.

These tests validate the citation formatting functionality which is pure
business logic without external dependencies.
"""

from thoth.analyze.citations.formatter import CitationFormatter, CitationStyle
from thoth.utilities.schemas import Citation


class TestIEEEFormatting:
    """Test IEEE citation formatting."""

    def test_ieee_basic_formatting(self):
        """Test basic IEEE citation formatting."""
        citation = Citation(
            title='Advanced Signal Processing Techniques',
            authors=['A. Author', 'B. Coauthor'],
            year=2024,
            journal='IEEE Transactions on Signal Processing',
            volume='70',
            issue='5',
            pages='1234-1245',
            doi='10.1109/TSP.2024.123456',
        )

        formatted_citation = CitationFormatter.format_citation(
            citation, CitationStyle.IEEE
        )
        formatted_text = formatted_citation.formatted

        # Verify key IEEE formatting rules
        assert 'A. Author, and B. Coauthor,' in formatted_text
        assert '"Advanced Signal Processing Techniques,"' in formatted_text
        assert (
            '_Ieee Transactions On Signal Processing_' in formatted_text
        )  # Title case
        assert 'vol. 70, no. 5' in formatted_text
        assert 'pp. 1234-1245' in formatted_text
        assert '2024' in formatted_text
        assert 'doi: 10.1109/TSP.2024.123456' in formatted_text

    def test_ieee_single_author(self):
        """Test IEEE formatting with single author."""
        citation = Citation(
            title='Single Author Paper',
            authors=['Smith, J.'],
            year=2023,
            journal='Test Journal',
        )

        formatted_citation = CitationFormatter.format_citation(
            citation, CitationStyle.IEEE
        )
        formatted_text = formatted_citation.formatted

        assert 'Smith, J.,' in formatted_text
        assert ' and ' not in formatted_text  # No "and" for single author


class TestAPAFormatting:
    """Test APA citation formatting."""

    def test_apa_basic_formatting(self):
        """Test basic APA citation formatting."""
        citation = Citation(
            title='Sample Paper on Innovations',
            authors=['Smith, J.', 'Jones, A. B.', 'Williams, C.'],
            year=2023,
            journal='Journal of Advanced Research',
            volume='10',
            issue='2',
            pages='123-145',
            doi='10.1234/5678',
        )

        formatted_citation = CitationFormatter.format_citation(
            citation, CitationStyle.APA
        )
        formatted_text = formatted_citation.formatted

        # Verify key APA formatting rules
        assert 'Smith, J., Jones, A. B., & Williams, C.' in formatted_text
        assert '(2023)' in formatted_text
        assert 'Sample paper on innovations.' in formatted_text  # Sentence case
        assert '_Journal Of Advanced Research_' in formatted_text  # Title case
        assert '_10_(2)' in formatted_text  # Volume(issue)
        assert '123-145' in formatted_text
        assert 'https://doi.org/10.1234/5678' in formatted_text

    def test_apa_two_authors(self):
        """Test APA formatting with two authors."""
        citation = Citation(
            title='Two Author Paper', authors=['First, A.', 'Second, B.'], year=2023
        )

        formatted_citation = CitationFormatter.format_citation(
            citation, CitationStyle.APA
        )
        formatted_text = formatted_citation.formatted

        assert 'First, A. & Second, B.' in formatted_text
        assert ' and ' not in formatted_text  # APA uses "&" not "and"


class TestMLAFormatting:
    """Test MLA citation formatting."""

    def test_mla_basic_formatting(self):
        """Test basic MLA citation formatting."""
        citation = Citation(
            title='The Impact of Technology on Modern Education',
            authors=['Doe, John', 'Smith, Jane'],
            year=2023,
            journal='Educational Technology Quarterly',
            volume='15',
            issue='3',
            pages='34-45',
            doi='10.5678/9012',
        )

        formatted_citation = CitationFormatter.format_citation(
            citation, CitationStyle.MLA
        )
        formatted_text = formatted_citation.formatted

        # Verify key MLA formatting rules
        assert (
            'Doe, John, and Smith, Jane.' in formatted_text
        )  # Author format preserved as-is
        assert (
            '"The Impact Of Technology On Modern Education."' in formatted_text
        )  # Title case
        assert '_Educational Technology Quarterly_' in formatted_text
        assert 'vol. 15, no. 3, 2023' in formatted_text
        assert 'pp. 34-45' in formatted_text
        assert 'DOI: 10.5678/9012' in formatted_text

    def test_mla_three_plus_authors(self):
        """Test MLA formatting with three or more authors."""
        citation = Citation(
            title='Multi Author Paper',
            authors=['First, A.', 'Second, B.', 'Third, C.', 'Fourth, D.'],
            year=2023,
        )

        formatted_citation = CitationFormatter.format_citation(
            citation, CitationStyle.MLA
        )
        formatted_text = formatted_citation.formatted

        # MLA uses "et al." for 3+ authors
        assert 'First, A., et al.' in formatted_text
        assert 'Second, B.' not in formatted_text


class TestFormattingEdgeCases:
    """Test edge cases and error handling in formatting."""

    def test_missing_required_fields(self):
        """Test formatting with missing fields."""
        minimal_citation = Citation(title='Minimal Citation')

        # Should not raise exception, should handle gracefully
        formatted_citation = CitationFormatter.format_citation(
            minimal_citation, CitationStyle.IEEE
        )

        assert formatted_citation.formatted is not None
        assert 'Minimal Citation' in formatted_citation.formatted

    def test_empty_citation(self):
        """Test formatting completely empty citation."""
        empty_citation = Citation()

        # Should handle gracefully without crashing
        try:
            formatted_citation = CitationFormatter.format_citation(
                empty_citation, CitationStyle.IEEE
            )
            # If it doesn't crash, that's good
            assert formatted_citation is not None
        except Exception as e:
            # If it does crash, it should be a meaningful error
            assert 'citation' in str(e).lower()

    def test_doi_url_normalization(self):
        """Test DOI URL normalization in formatting."""
        citation_with_full_url = Citation(
            title='Test', doi='https://doi.org/10.1234/test'
        )

        citation_with_bare_doi = Citation(title='Test', doi='10.1234/test')

        formatted1 = CitationFormatter.format_citation(
            citation_with_full_url, CitationStyle.APA
        )
        formatted2 = CitationFormatter.format_citation(
            citation_with_bare_doi, CitationStyle.APA
        )

        # Both should result in the same DOI format
        assert 'https://doi.org/10.1234/test' in formatted1.formatted
        assert 'https://doi.org/10.1234/test' in formatted2.formatted


class TestCitationStyleSelection:
    """Test citation style selection and validation."""

    def test_all_supported_styles(self):
        """Test that all supported styles work."""
        citation = Citation(title='Test Paper', authors=['Author, A.'], year=2023)

        supported_styles = [
            CitationStyle.IEEE,
            CitationStyle.APA,
            CitationStyle.MLA,
            CitationStyle.CHICAGO,
            CitationStyle.HARVARD,
        ]

        for style in supported_styles:
            formatted_citation = CitationFormatter.format_citation(citation, style)
            assert formatted_citation.formatted is not None
            assert len(formatted_citation.formatted) > 0

    def test_convenience_function(self):
        """Test the convenience format_citation function."""
        from thoth.analyze.citations.formatter import format_citation

        citation = Citation(title='Test Paper', authors=['Author, A.'], year=2023)

        # Test string-based style selection
        ieee_result = format_citation(citation, 'ieee')
        apa_result = format_citation(citation, 'apa')

        assert isinstance(ieee_result, str)
        assert isinstance(apa_result, str)
        assert (
            ieee_result != apa_result
        )  # Different styles should produce different output
