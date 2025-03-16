"""
Tests for the Citation Formatter module.
"""

import pytest

from thoth.citation.citation import Citation
from thoth.citation.formatter import (
    CitationFormatError,
    CitationFormatter,
    CitationStyle,
    format_citation,
)


class TestCitationFormatter:
    """Tests for the CitationFormatter class."""

    @pytest.fixture
    def sample_citation(self):
        """Create a sample citation for testing."""
        return Citation(
            title="Sample Paper",
            authors=["J. Smith", "A. Jones"],
            year=2023,
            journal="Journal of Research",
            volume="10",
            issue="2",
            pages="123-145",
            doi="10.1234/5678",
            url="https://example.com/paper",
        )

    @pytest.fixture
    def minimal_citation(self):
        """Create a minimal citation for testing."""
        return Citation(
            title="Sample Paper",
            authors=["J. Smith"],
        )

    def test_format_citation_ieee(self, sample_citation):
        """Test IEEE format conversion."""
        formatted = CitationFormatter.format_citation(
            sample_citation, CitationStyle.IEEE
        )
        assert "J. Smith, A. Jones" in formatted
        assert '"Sample Paper"' in formatted
        assert "Journal of Research" in formatted
        assert "vol. 10" in formatted
        assert "no. 2" in formatted
        assert "pp. 123-145" in formatted
        assert "2023" in formatted
        assert "DOI: 10.1234/5678" in formatted

    def test_format_citation_apa(self, sample_citation):
        """Test APA format conversion."""
        formatted = CitationFormatter.format_citation(
            sample_citation, CitationStyle.APA
        )
        assert "Smith, J., & Jones, A." in formatted
        assert "(2023)" in formatted
        assert "Sample Paper" in formatted
        assert "Journal of Research" in formatted
        assert "10(2)" in formatted
        assert "123-145" in formatted
        assert "https://doi.org/10.1234/5678" in formatted

    def test_format_citation_mla(self, sample_citation):
        """Test MLA format conversion."""
        formatted = CitationFormatter.format_citation(
            sample_citation, CitationStyle.MLA
        )
        assert "Smith, J., and A. Jones." in formatted
        assert '"Sample Paper."' in formatted
        assert "Journal of Research" in formatted
        assert "vol. 10" in formatted
        assert "no. 2" in formatted
        assert "2023" in formatted
        assert "pp. 123-145" in formatted
        assert "DOI: 10.1234/5678" in formatted

    def test_format_citation_chicago(self, sample_citation):
        """Test Chicago format conversion."""
        formatted = CitationFormatter.format_citation(
            sample_citation, CitationStyle.CHICAGO
        )
        assert "Smith, J., and A. Jones." in formatted
        assert '"Sample Paper."' in formatted
        assert "Journal of Research" in formatted
        assert "10" in formatted
        assert "no. 2" in formatted
        assert "(2023)" in formatted
        assert "123-145" in formatted
        assert "https://doi.org/10.1234/5678" in formatted

    def test_format_citation_harvard(self, sample_citation):
        """Test Harvard format conversion."""
        formatted = CitationFormatter.format_citation(
            sample_citation, CitationStyle.HARVARD
        )
        assert "Smith, J. and Jones, A." in formatted
        assert "(2023)" in formatted
        assert '"Sample Paper"' in formatted
        assert "Journal of Research" in formatted
        assert "10(2)" in formatted
        assert "pp. 123-145" in formatted
        assert "doi: 10.1234/5678" in formatted

    def test_minimal_citation_formatting(self, minimal_citation):
        """Test formatting with minimal citation information."""
        ieee = CitationFormatter.format_citation(minimal_citation, CitationStyle.IEEE)
        apa = CitationFormatter.format_citation(minimal_citation, CitationStyle.APA)
        mla = CitationFormatter.format_citation(minimal_citation, CitationStyle.MLA)
        chicago = CitationFormatter.format_citation(
            minimal_citation, CitationStyle.CHICAGO
        )
        harvard = CitationFormatter.format_citation(
            minimal_citation, CitationStyle.HARVARD
        )

        # Check that all formats contain the basic information
        for formatted in [ieee, apa, mla, chicago, harvard]:
            assert "Smith" in formatted
            assert "Sample Paper" in formatted

    def test_unsupported_style(self, sample_citation):
        """Test handling of unsupported citation styles."""

        # Create a mock style that's not a real CitationStyle enum value
        class MockStyle:
            pass

        mock_style = MockStyle()

        with pytest.raises(CitationFormatError):
            CitationFormatter.format_citation(sample_citation, mock_style)

    def test_convenience_function(self, sample_citation):
        """Test the convenience function for formatting citations."""
        # Test with string style names
        ieee = format_citation(sample_citation, "ieee")
        apa = format_citation(sample_citation, "apa")
        mla = format_citation(sample_citation, "mla")
        chicago = format_citation(sample_citation, "chicago")
        harvard = format_citation(sample_citation, "harvard")

        # Check that all formats contain the basic information
        for formatted in [ieee, apa, mla, chicago, harvard]:
            assert "Smith" in formatted
            assert "Sample Paper" in formatted
            assert "Journal of Research" in formatted

        # Test default style (IEEE)
        default = format_citation(sample_citation)
        assert default == ieee

        # Test case insensitivity
        assert format_citation(sample_citation, "APA") == apa

    def test_invalid_style_string(self, sample_citation):
        """Test handling of invalid style strings."""
        with pytest.raises(CitationFormatError):
            format_citation(sample_citation, "invalid_style")

    def test_error_handling(self, monkeypatch):
        """Test error handling during formatting."""
        # Create a citation that will cause an error
        citation = Citation(
            title="Sample Paper",
            authors=["J. Smith"],
        )

        # Patch the _format_apa method to raise an exception
        def mock_format_apa(*_args, **_kwargs):
            raise ValueError("Test error")

        monkeypatch.setattr(CitationFormatter, "_format_apa", mock_format_apa)

        # Test that the error is properly caught and wrapped
        with pytest.raises(CitationFormatError) as excinfo:
            CitationFormatter.format_citation(citation, CitationStyle.APA)
        assert "Failed to format citation" in str(excinfo.value)
        assert "Test error" in str(excinfo.value)
