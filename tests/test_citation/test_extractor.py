"""
Tests for the Citation Extractor.
"""

from unittest.mock import MagicMock, patch

import pytest

from thoth.citation.citation import Citation
from thoth.citation.extractor import (
    CitationExtractor,
    extract_citations,
)
from thoth.core.llm_processor import LLMError, LLMProcessor


class TestCitationExtractor:
    """Tests for the CitationExtractor class."""

    @pytest.fixture
    def mock_llm_processor(self):
        """Provide a mock LLM processor for testing."""
        mock = MagicMock(spec=LLMProcessor)
        mock.extract_citations.return_value = [
            {
                "title": "Sample Paper",
                "authors": ["J. Smith"],
                "year": 2023,
                "journal": "Journal of Research",
                "context": "This is the context",
            }
        ]
        return mock

    @pytest.fixture
    def sample_content_with_references(self):
        """Provide sample content with references for testing."""
        return """# Sample Paper

## Abstract

This is the abstract.

## Introduction

This is the introduction, citing Smith et al. [1].

## Methods

These are the methods.

## Results

These are the results.

## Conclusion

This is the conclusion.

## References

[1] Smith, J. (2023). "Sample Paper". Journal of Research, 10(2), 123-145.
[2] Doe, A. (2022). "Another Paper". Conference Proceedings, 45-67.
"""

    def test_init(self, mock_llm_processor):
        """Test CitationExtractor initialization."""
        extractor = CitationExtractor(mock_llm_processor)
        assert extractor.llm_processor == mock_llm_processor

    def test_extract_citations(
        self, mock_llm_processor, sample_content_with_references
    ):
        """Test citation extraction."""
        extractor = CitationExtractor(mock_llm_processor)
        citations = extractor.extract_citations(sample_content_with_references)

        assert len(citations) == 1
        assert citations[0].title == "Sample Paper"
        assert citations[0].authors == ["J. Smith"]
        assert citations[0].year == 2023
        assert citations[0].journal == "Journal of Research"
        assert citations[0].context == "This is the context"

        # Verify LLM processor was called
        mock_llm_processor.extract_citations.assert_called_once_with(
            sample_content_with_references
        )

    def test_extract_citations_no_references(self, mock_llm_processor):
        """Test citation extraction with no references section."""
        content = "# Sample Paper\n\n## Abstract\n\nThis is the abstract."
        extractor = CitationExtractor(mock_llm_processor)
        citations = extractor.extract_citations(content)

        assert len(citations) == 0
        # Verify LLM processor was not called
        mock_llm_processor.extract_citations.assert_not_called()

    def test_extract_citations_llm_error(
        self, mock_llm_processor, sample_content_with_references
    ):
        """Test citation extraction with LLM error."""
        # Set up LLM processor to raise an error
        mock_llm_processor.extract_citations.side_effect = LLMError("Test error")

        extractor = CitationExtractor(mock_llm_processor)

        # Should fall back to regex extraction
        with patch.object(
            extractor,
            "_extract_citations_with_regex",
            return_value=[Citation(title="Fallback", authors=["A. Author"])],
        ) as mock_regex:
            citations = extractor.extract_citations(sample_content_with_references)

            assert len(citations) == 1
            assert citations[0].title == "Fallback"
            assert citations[0].authors == ["A. Author"]

            # Verify regex fallback was called
            mock_regex.assert_called_once_with(sample_content_with_references)

    def test_extract_citations_with_regex(
        self, mock_llm_processor, sample_content_with_references
    ):
        """Test regex-based citation extraction."""
        extractor = CitationExtractor(mock_llm_processor)
        citations = extractor._extract_citations_with_regex(
            sample_content_with_references
        )

        assert len(citations) >= 1
        # Check that at least one citation was extracted with some basic info
        assert any(c.title and c.authors for c in citations)

    def test_extract_references_section(
        self, mock_llm_processor, sample_content_with_references
    ):
        """Test extraction of references section."""
        extractor = CitationExtractor(mock_llm_processor)
        references = extractor._extract_references_section(
            sample_content_with_references
        )

        assert references is not None
        assert "[1] Smith, J. (2023)" in references
        assert "[2] Doe, A. (2022)" in references

    def test_extract_references_section_alternative_heading(self, mock_llm_processor):
        """Test extraction of references section with alternative heading."""
        content = """# Sample Paper

## Bibliography

[1] Smith, J. (2023). "Sample Paper". Journal of Research.
"""
        extractor = CitationExtractor(mock_llm_processor)
        references = extractor._extract_references_section(content)

        assert references is not None
        assert "[1] Smith, J. (2023)" in references

    def test_find_citation_contexts(
        self, mock_llm_processor, sample_content_with_references
    ):
        """Test finding citation contexts."""
        extractor = CitationExtractor(mock_llm_processor)
        citations = [
            Citation(
                title="Sample Paper",
                authors=["J. Smith"],
                year=2023,
                journal="Journal of Research",
            )
        ]

        citations_with_context = extractor.find_citation_contexts(
            sample_content_with_references, citations
        )

        assert len(citations_with_context) == 1
        # The sample content contains "Smith et al. [1]" which should be found
        assert citations_with_context[0].context is not None
        assert "Smith" in citations_with_context[0].context

    def test_convenience_function(
        self, mock_llm_processor, sample_content_with_references
    ):
        """Test the extract_citations convenience function."""
        with patch(
            "thoth.citation.extractor.CitationExtractor",
            return_value=MagicMock(
                extract_citations=MagicMock(
                    return_value=[Citation(title="Test", authors=["Author"])]
                )
            ),
        ):
            citations = extract_citations(
                sample_content_with_references, mock_llm_processor
            )

            assert len(citations) == 1
            assert citations[0].title == "Test"
            assert citations[0].authors == ["Author"]
