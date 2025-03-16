"""
Tests for the Citation class.
"""

from thoth.citation.citation import Citation


class TestCitation:
    """Tests for the Citation class."""

    def test_init(self):
        """Test Citation initialization."""
        citation = Citation(
            title="Sample Paper",
            authors=["J. Smith", "A. Jones"],
            year=2023,
            journal="Journal of Research",
            volume="10",
            issue="2",
            pages="123-145",
            doi="10.1234/5678",
            url="https://example.com/paper",
            context="This is the context",
        )

        assert citation.title == "Sample Paper"
        assert citation.authors == ["J. Smith", "A. Jones"]
        assert citation.year == 2023
        assert citation.journal == "Journal of Research"
        assert citation.volume == "10"
        assert citation.issue == "2"
        assert citation.pages == "123-145"
        assert citation.doi == "10.1234/5678"
        assert citation.url == "https://example.com/paper"
        assert citation.context == "This is the context"

    def test_to_ieee_format(self):
        """Test IEEE format conversion."""
        # Test with all fields
        citation = Citation(
            title="Sample Paper",
            authors=["J. Smith", "A. Jones"],
            year=2023,
            journal="Journal of Research",
            volume="10",
            issue="2",
            pages="123-145",
            doi="10.1234/5678",
        )
        ieee_format = citation.to_ieee_format()
        assert "J. Smith, A. Jones" in ieee_format
        assert '"Sample Paper"' in ieee_format
        assert "Journal of Research" in ieee_format
        assert "vol. 10" in ieee_format
        assert "no. 2" in ieee_format
        assert "pp. 123-145" in ieee_format
        assert "2023" in ieee_format
        assert "DOI: 10.1234/5678" in ieee_format

        # Test with minimal fields
        citation = Citation(
            title="Sample Paper",
            authors=["J. Smith"],
        )
        ieee_format = citation.to_ieee_format()
        assert ieee_format == 'J. Smith, "Sample Paper"'

    def test_to_dict(self):
        """Test conversion to dictionary."""
        citation = Citation(
            title="Sample Paper",
            authors=["J. Smith"],
            year=2023,
        )
        citation_dict = citation.to_dict()
        assert citation_dict["title"] == "Sample Paper"
        assert citation_dict["authors"] == ["J. Smith"]
        assert citation_dict["year"] == 2023
        assert citation_dict["journal"] is None
        assert citation_dict["doi"] is None

    def test_from_dict(self):
        """Test creation from dictionary."""
        # Test with all fields
        data = {
            "title": "Sample Paper",
            "authors": ["J. Smith", "A. Jones"],
            "year": 2023,
            "journal": "Journal of Research",
            "volume": "10",
            "issue": "2",
            "pages": "123-145",
            "doi": "10.1234/5678",
            "url": "https://example.com/paper",
            "context": "This is the context",
        }
        citation = Citation.from_dict(data)
        assert citation.title == "Sample Paper"
        assert citation.authors == ["J. Smith", "A. Jones"]
        assert citation.year == 2023
        assert citation.journal == "Journal of Research"
        assert citation.volume == "10"
        assert citation.issue == "2"
        assert citation.pages == "123-145"
        assert citation.doi == "10.1234/5678"
        assert citation.url == "https://example.com/paper"
        assert citation.context == "This is the context"

        # Test with minimal fields
        data = {
            "title": "Sample Paper",
            "authors": ["J. Smith"],
        }
        citation = Citation.from_dict(data)
        assert citation.title == "Sample Paper"
        assert citation.authors == ["J. Smith"]
        assert citation.year is None
        assert citation.journal is None
