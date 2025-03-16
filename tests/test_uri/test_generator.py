"""
Tests for the URI generator module.
"""

import urllib.parse

import pytest

from thoth.citation.citation import Citation
from thoth.uri.generator import URIGenerator, generate_markdown_link, generate_uri


@pytest.fixture
def sample_citation_with_doi():
    """Create a sample citation with DOI for testing."""
    return Citation(
        title="Sample Paper",
        authors=["J. Smith", "A. Jones"],
        year=2023,
        doi="10.1234/5678",
        journal="Journal of Research",
    )


@pytest.fixture
def sample_citation_with_url():
    """Create a sample citation with URL for testing."""
    return Citation(
        title="Sample Paper",
        authors=["J. Smith", "A. Jones"],
        year=2023,
        url="https://example.com/paper.pdf",
        journal="Journal of Research",
    )


@pytest.fixture
def sample_citation_without_doi_or_url():
    """Create a sample citation without DOI or URL for testing."""
    return Citation(
        title="Sample Paper",
        authors=["J. Smith", "A. Jones"],
        year=2023,
        journal="Journal of Research",
    )


class TestURIGenerator:
    """Tests for the URIGenerator class."""

    def test_init(self):
        """Test initialization of URIGenerator."""
        generator = URIGenerator()
        assert generator.URI_SCHEME == "thoth"

    def test_generate_uri_with_doi(self, sample_citation_with_doi):
        """Test generating a URI for a citation with DOI."""
        generator = URIGenerator()
        uri = generator.generate_uri(sample_citation_with_doi)
        assert uri == "thoth://doi:10.1234/5678"

    def test_generate_uri_with_url(self, sample_citation_with_url):
        """Test generating a URI for a citation with URL."""
        generator = URIGenerator()
        uri = generator.generate_uri(sample_citation_with_url)
        assert uri == "thoth://url:https://example.com/paper.pdf"

    def test_generate_uri_with_url_special_chars(self):
        """Test generating a URI for a citation with URL containing special
        characters."""
        citation = Citation(
            title="Sample Paper",
            authors=["J. Smith"],
            url="https://example.com/paper with spaces.pdf?query=test&param=value",
        )
        generator = URIGenerator()
        uri = generator.generate_uri(citation)

        # The URL should be encoded
        expected_url = urllib.parse.quote(
            "https://example.com/paper with spaces.pdf?query=test&param=value",
            safe=":/?&=",
        )
        assert uri == f"thoth://url:{expected_url}"

    def test_generate_uri_without_doi_or_url(self, sample_citation_without_doi_or_url):
        """Test generating a URI for a citation without DOI or URL."""
        generator = URIGenerator()
        uri = generator.generate_uri(sample_citation_without_doi_or_url)

        # The title and authors should be encoded
        title_part = urllib.parse.quote("Sample Paper")
        authors_part = urllib.parse.quote("J. Smith,A. Jones")
        assert uri == f"thoth://search?title={title_part}&authors={authors_part}"

    def test_generate_markdown_link_with_doi(self, sample_citation_with_doi):
        """Test generating a Markdown link for a citation with DOI."""
        generator = URIGenerator()
        link = generator.generate_markdown_link(sample_citation_with_doi)
        assert link == "[Sample Paper](thoth://doi:10.1234/5678)"

    def test_generate_markdown_link_with_custom_text(self, sample_citation_with_doi):
        """Test generating a Markdown link with custom text."""
        generator = URIGenerator()
        link = generator.generate_markdown_link(sample_citation_with_doi, "Custom Text")
        assert link == "[Custom Text](thoth://doi:10.1234/5678)"


def test_generate_uri_function(sample_citation_with_doi):
    """Test the generate_uri function."""
    uri = generate_uri(sample_citation_with_doi)
    assert uri == "thoth://doi:10.1234/5678"


def test_generate_markdown_link_function(sample_citation_with_doi):
    """Test the generate_markdown_link function."""
    link = generate_markdown_link(sample_citation_with_doi)
    assert link == "[Sample Paper](thoth://doi:10.1234/5678)"


def test_generate_markdown_link_function_with_custom_text(sample_citation_with_doi):
    """Test the generate_markdown_link function with custom text."""
    link = generate_markdown_link(sample_citation_with_doi, "Custom Text")
    assert link == "[Custom Text](thoth://doi:10.1234/5678)"
