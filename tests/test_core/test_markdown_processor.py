"""
Tests for the Markdown Processor module.
"""

import shutil
from pathlib import Path

import pytest

from thoth.core.markdown_processor import MarkdownProcessingError, MarkdownProcessor


class TestMarkdownProcessor:
    """Tests for the MarkdownProcessor class."""

    @pytest.fixture
    def sample_markdown_path(self, tmp_path):
        """Create a temporary sample markdown file for testing."""
        # Copy the sample markdown file to a temporary location
        source_path = Path("tests/fixtures/markdown_processor/sample.md")
        dest_path = tmp_path / "sample.md"
        shutil.copy(source_path, dest_path)
        return dest_path

    @pytest.fixture
    def processor(self):
        """Create a MarkdownProcessor instance for testing."""
        return MarkdownProcessor()

    def test_init(self, processor):
        """Test initialization of MarkdownProcessor."""
        assert isinstance(processor, MarkdownProcessor)

    def test_process_markdown_file_not_found(self, processor):
        """Test process_markdown with a non-existent file."""
        with pytest.raises(FileNotFoundError):
            processor.process_markdown(Path("non_existent_file.md"))

    def test_process_markdown(self, processor, sample_markdown_path):
        """Test processing a markdown file."""
        result = processor.process_markdown(sample_markdown_path)

        # Check that the result has the expected structure
        assert "metadata" in result
        assert "text" in result
        assert "sections" in result

        # Check metadata
        metadata = result["metadata"]
        assert (
            metadata["title"]
            == "Machine Learning Approaches for Natural Language Processing"
        )
        assert len(metadata["authors"]) == 3
        assert "John Smith" in metadata["authors"]
        assert metadata["year"] == 2023
        assert metadata["journal"] == "Journal of Artificial Intelligence Research"
        assert metadata["doi"] == "10.1234/jair.2023.123"
        assert metadata["abstract"] is not None

        # Check sections
        sections = result["sections"]
        assert "Abstract" in sections
        assert "Introduction" in sections
        assert len(sections) >= 5  # At least 5 sections

    def test_extract_metadata(self, processor):
        """Test extracting metadata from markdown content."""
        content = """# Test Paper Title

**Authors:** John Doe, Jane Smith

**Year:** 2022

**Journal:** Test Journal

**DOI:** 10.1234/test

## Abstract

This is a test abstract.

## Introduction

This is the introduction.
"""
        metadata = processor.extract_metadata(content)

        assert metadata["title"] == "Test Paper Title"
        assert metadata["authors"] == ["John Doe", "Jane Smith"]
        assert metadata["year"] == 2022
        assert metadata["journal"] == "Test Journal"
        assert metadata["doi"] == "10.1234/test"
        assert metadata["abstract"] == "This is a test abstract."

    def test_extract_metadata_missing_fields(self, processor):
        """Test extracting metadata with missing fields."""
        content = """# Test Paper Title

## Abstract

This is a test abstract.

## Introduction

This is the introduction.
"""
        metadata = processor.extract_metadata(content)

        assert metadata["title"] == "Test Paper Title"
        assert metadata["authors"] == []
        assert metadata["year"] is None
        assert metadata["journal"] is None
        assert metadata["doi"] is None
        assert metadata["abstract"] == "This is a test abstract."

    def test_extract_sections(self, processor):
        """Test extracting sections from markdown content."""
        content = """# Test Paper

## Abstract

This is the abstract.

## Introduction

This is the introduction.

## Methods

This is the methods section.

## Results

These are the results.
"""
        sections = processor.extract_sections(content)

        assert len(sections) == 4
        assert sections["Abstract"] == "This is the abstract."
        assert sections["Introduction"] == "This is the introduction."
        assert sections["Methods"] == "This is the methods section."
        assert sections["Results"] == "These are the results."

    def test_clean_content(self, processor):
        """Test cleaning markdown content."""
        content = """# Title



## Section 1
Content 1
## Section 2

- Item 1
- Item 2
Content 2"""

        cleaned = processor.clean_content(content)

        # Check that excessive newlines are removed
        assert "Title\n\n\n\n## Section" not in cleaned

        # Check that headings have proper spacing
        assert "Content 1\n\n## Section 2" in cleaned

        # Check that list items have proper spacing
        assert "- Item 2\n\nContent 2" in cleaned

    def test_extract_citations(self, processor):
        """Test extracting citations from markdown content."""
        content = """# Test Paper

## Introduction

As shown in [1] and discussed by [2].

## References

[1] Smith, J. (2020). Test paper 1. Journal of Tests.

[2] Doe, J. (2021). Test paper 2. Journal of Tests.
"""
        citations = processor.extract_citations(content)

        assert len(citations) == 2
        assert citations[0]["ref_id"] == "[1]"
        assert "Smith, J. (2020)" in citations[0]["text"]
        assert citations[1]["ref_id"] == "[2]"
        assert "Doe, J. (2021)" in citations[1]["text"]

    def test_extract_citations_no_references(self, processor):
        """Test extracting citations when there's no references section."""
        content = """# Test Paper

## Introduction

This paper has no references.
"""
        citations = processor.extract_citations(content)
        assert len(citations) == 0

    def test_process_markdown_with_error(self, processor, monkeypatch):
        """Test process_markdown with an error during processing."""

        # Create a mock that raises an exception
        def mock_extract_metadata(self, content):  # noqa: ARG001
            raise ValueError("Test error")

        # Apply the mock
        monkeypatch.setattr(
            MarkdownProcessor, "extract_metadata", mock_extract_metadata
        )

        # Test that the error is properly caught and re-raised
        with pytest.raises(MarkdownProcessingError):
            processor.process_markdown(
                Path("tests/fixtures/markdown_processor/sample.md")
            )
