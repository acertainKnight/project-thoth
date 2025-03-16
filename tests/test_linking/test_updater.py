"""
Tests for the note updater module.
"""

from pathlib import Path
from unittest.mock import mock_open, patch

from thoth.linking.updater import (
    extract_citations_from_section,
    find_citation_sections,
    update_note_citations,
)


def test_update_note_citations():
    """Test updating note citations."""
    # Given
    note_path = Path("/path/to/note.md")
    citations = [
        {
            "text": "J. Smith, \"Test Paper\", Journal, 2023",
            "wikilink": "[[Smith2023]]",
        }
    ]

    # Mock the note file
    note_content = """
    # Note

    ## Citations

    1. J. Smith, "Test Paper", Journal, 2023
    """

    # When
    with patch("builtins.open", mock_open(read_data=note_content)) as mock_file:
        result = update_note_citations(note_path, citations)

        # Then
        assert result
        # Check that write was called with updated content
        mock_file.return_value.write.assert_called_once()
        written_content = mock_file.return_value.write.call_args[0][0]
        assert (
            "J. Smith, \"Test Paper\", Journal, 2023 [[Smith2023]]" in written_content
        )


def test_update_note_citations_no_changes():
    """Test updating note citations when no changes are needed."""
    # Given
    note_path = Path("/path/to/note.md")
    citations = [
        {
            "text": "J. Smith, \"Test Paper\", Journal, 2023",
            "wikilink": "[[Smith2023]]",
        }
    ]

    # Mock the note file - citation already has a wikilink
    note_content = """
    # Note

    ## Citations

    1. J. Smith, "Test Paper", Journal, 2023 [[Smith2023]]
    """

    # When
    with patch("builtins.open", mock_open(read_data=note_content)) as mock_file:
        result = update_note_citations(note_path, citations)

        # Then
        assert not result
        # Check that write was not called
        mock_file.return_value.write.assert_not_called()


def test_update_note_citations_file_not_found():
    """Test updating note citations when the file doesn't exist."""
    # Given
    note_path = Path("/path/to/note.md")
    citations = [
        {
            "text": "J. Smith, \"Test Paper\", Journal, 2023",
            "wikilink": "[[Smith2023]]",
        }
    ]

    # When
    with patch("pathlib.Path.exists", return_value=False):
        result = update_note_citations(note_path, citations)

        # Then
        assert not result


def test_update_note_citations_no_citations():
    """Test updating note citations when no citations are provided."""
    # Given
    note_path = Path("/path/to/note.md")
    citations = []

    # When
    with patch("pathlib.Path.exists", return_value=True):
        result = update_note_citations(note_path, citations)

        # Then
        assert not result


def test_update_note_citations_invalid_citation():
    """Test updating note citations with invalid citation data."""
    # Given
    note_path = Path("/path/to/note.md")
    citations = [
        {
            "text": "J. Smith, \"Test Paper\", Journal, 2023",
            # Missing wikilink
        }
    ]

    # Mock the note file
    note_content = """
    # Note

    ## Citations

    1. J. Smith, "Test Paper", Journal, 2023
    """

    # When
    with patch("pathlib.Path.exists", return_value=True):
        with patch("builtins.open", mock_open(read_data=note_content)):
            result = update_note_citations(note_path, citations)

            # Then
            assert not result


def test_find_citation_sections():
    """Test finding citation sections in note content."""
    # Given
    content = """
    # Note

    ## Summary

    This is a summary.

    ## Citations

    1. Citation 1
    2. Citation 2

    ## Notes

    Some notes.
    """

    # When
    sections = find_citation_sections(content)

    # Then
    assert len(sections) == 1
    start, end = sections[0]
    assert "## Citations" in content[start:end]
    assert "1. Citation 1" in content[start:end]
    assert "2. Citation 2" in content[start:end]


def test_find_citation_sections_multiple():
    """Test finding multiple citation sections in note content."""
    # Given
    content = """
    # Note

    ## Citations

    1. Citation 1

    ## Notes

    Some notes.

    ## Citations

    2. Citation 2
    """

    # When
    sections = find_citation_sections(content)

    # Then
    assert len(sections) == 2
    assert "1. Citation 1" in content[sections[0][0] : sections[0][1]]
    assert "2. Citation 2" in content[sections[1][0] : sections[1][1]]


def test_find_citation_sections_none():
    """Test finding citation sections when none exist."""
    # Given
    content = """
    # Note

    ## Summary

    This is a summary.

    ## Notes

    Some notes.
    """

    # When
    sections = find_citation_sections(content)

    # Then
    assert len(sections) == 0


def test_extract_citations_from_section():
    """Test extracting citations from a section."""
    # Given
    section = """## Citations

    1. J. Smith, "Test Paper", Journal, 2023
    2. A. Johnson, "Another Paper", Conference, 2022
    """

    # When
    citations = extract_citations_from_section(section)

    # Then
    assert len(citations) == 2
    assert citations[0]["title"] == "Test Paper"
    assert citations[0]["authors"] == ["J. Smith"]
    assert citations[0]["year"] == 2023
    assert citations[0]["index"] == 1
    assert citations[1]["title"] == "Another Paper"
    assert citations[1]["authors"] == ["A. Johnson"]
    assert citations[1]["year"] == 2022
    assert citations[1]["index"] == 2


def test_extract_citations_from_section_empty():
    """Test extracting citations from an empty section."""
    # Given
    section = """## Citations

    """

    # When
    citations = extract_citations_from_section(section)

    # Then
    assert len(citations) == 0


def test_extract_citations_from_section_no_title():
    """Test extracting citations with no title."""
    # Given
    section = """## Citations

    1. J. Smith, Journal, 2023
    """

    # When
    citations = extract_citations_from_section(section)

    # Then
    assert len(citations) == 0  # No title, so no citation extracted
