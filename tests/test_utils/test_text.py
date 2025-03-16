"""
Tests for the text utility module.
"""
import pytest

from thoth.utils.text import (
    clean_text,
    extract_metadata_from_text,
    split_into_sections,
    create_wikilink,
)


def test_clean_text():
    """Test clean_text function."""
    # Test with mixed line endings
    text = "Line 1\r\nLine 2\nLine 3\r\n\r\n\r\nLine 4  \t"
    expected = "Line 1\nLine 2\nLine 3\n\nLine 4\n"
    assert clean_text(text) == expected

    # Test with multiple empty lines
    text = "Line 1\n\n\n\n\nLine 2"
    expected = "Line 1\n\nLine 2\n"
    assert clean_text(text) == expected

    # Test with trailing whitespace
    text = "Line 1  \t\nLine 2\t  "
    expected = "Line 1\nLine 2\n"
    assert clean_text(text) == expected


def test_extract_metadata_from_text():
    """Test extract_metadata_from_text function."""
    # Test with complete metadata
    text = """# Paper Title

Authors: John Doe, Jane Smith
Year: 2023
DOI: 10.1234/5678

Abstract: This is the abstract of the paper. It contains a summary of the research.

## Introduction
This is the introduction section.
"""
    metadata = extract_metadata_from_text(text)
    assert metadata["title"] == "Paper Title"
    assert metadata["authors"] == ["John Doe", "Jane Smith"]
    assert metadata["year"] == 2023
    assert metadata["doi"] == "10.1234/5678"
    assert metadata["abstract"] == "This is the abstract of the paper. It contains a summary of the research."

    # Test with partial metadata
    text = """# Another Paper

By: John Doe

This paper discusses something interesting.

## Results
These are the results.
"""
    metadata = extract_metadata_from_text(text)
    assert metadata["title"] == "Another Paper"
    assert metadata["authors"] == ["John Doe"]
    assert "year" not in metadata
    assert "doi" not in metadata
    assert "abstract" not in metadata


def test_split_into_sections():
    """Test split_into_sections function."""
    # Test with multiple sections
    text = """# Introduction
This is the introduction.

## Methods
These are the methods.

### Subsection
This is a subsection.

## Results
These are the results.
"""
    sections = split_into_sections(text)
    assert len(sections) == 4
    assert sections[0][0] == "Introduction"
    assert sections[0][1] == "This is the introduction."
    assert sections[1][0] == "Methods"
    assert sections[1][1] == "These are the methods."
    assert sections[2][0] == "Subsection"
    assert sections[2][1] == "This is a subsection."
    assert sections[3][0] == "Results"
    assert sections[3][1] == "These are the results."

    # Test with no sections
    text = "This is just plain text without any headings."
    sections = split_into_sections(text)
    assert len(sections) == 1
    assert sections[0][0] == ""
    assert sections[0][1] == "This is just plain text without any headings."


def test_create_wikilink():
    """Test create_wikilink function."""
    # Test with simple text
    assert create_wikilink("Paper Title") == "[[Paper-Title]]"

    # Test with special characters
    assert create_wikilink("Paper: Title & Author!") == "[[Paper-Title-Author-]]"

    # Test with extra spaces
    assert create_wikilink("  Paper   Title  ") == "[[Paper-Title]]"
