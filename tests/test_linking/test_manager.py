"""
Tests for the link manager module.
"""

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from thoth.linking.manager import LinkManager


def test_init():
    """Test initialization of LinkManager."""
    # Given
    notes_dir = Path("/path/to/notes")

    # When
    manager = LinkManager(notes_dir)

    # Then
    assert manager.notes_dir == notes_dir


def test_validate_new_paper():
    """Test validation of new paper dictionary."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))
    valid_paper = {
        "path": Path("/path/to/notes/paper.md"),
        "title": "Test Paper",
        "authors": ["John Doe"],
    }
    invalid_paper1 = {
        "title": "Test Paper",
        "authors": ["John Doe"],
    }
    invalid_paper2 = {
        "path": Path("/path/to/notes/paper.md"),
        "authors": ["John Doe"],
    }

    # When/Then
    # Valid paper should not raise an exception
    manager._validate_new_paper(valid_paper)

    # Invalid papers should raise ValueError
    with pytest.raises(ValueError) as excinfo:
        manager._validate_new_paper(invalid_paper1)
    assert "Missing required fields in paper: path" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        manager._validate_new_paper(invalid_paper2)
    assert "Missing required fields in paper: title" in str(excinfo.value)


def test_validate_paper():
    """Test validation of paper dictionary."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))
    valid_paper = {
        "title": "Test Paper",
        "authors": ["John Doe"],
    }
    invalid_paper1 = {
        "authors": ["John Doe"],
    }
    invalid_paper2 = {
        "title": "Test Paper",
    }

    # When/Then
    # Valid paper should not raise an exception
    manager._validate_paper(valid_paper)

    # Invalid papers should raise ValueError
    with pytest.raises(ValueError) as excinfo:
        manager._validate_paper(invalid_paper1)
    assert "Missing required fields in paper: title" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        manager._validate_paper(invalid_paper2)
    assert "Missing required fields in paper: authors" in str(excinfo.value)


def test_is_title_match():
    """Test title matching."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))

    # When/Then
    # Exact match
    assert manager._is_title_match("test paper", "test paper")

    # Substring match
    assert manager._is_title_match("test", "test paper")
    assert manager._is_title_match("test paper", "test")

    # No match
    assert not manager._is_title_match("test", "paper")


def test_is_author_match():
    """Test author matching."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))

    # When/Then
    # Exact match
    assert manager._is_author_match(["john doe"], ["john doe"])

    # Substring match
    assert manager._is_author_match(["john"], ["john doe"])
    assert manager._is_author_match(["john doe"], ["john"])

    # Multiple authors, one match
    assert manager._is_author_match(["john doe", "jane smith"], ["john"])
    assert manager._is_author_match(["john"], ["john doe", "jane smith"])

    # No match
    assert not manager._is_author_match(["john"], ["jane"])


def test_citation_matches_paper():
    """Test citation matching."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))
    citation = {
        "title": "Test Paper",
        "authors": ["John Doe", "Jane Smith"],
        "year": 2023,
    }

    # When/Then
    # Exact match
    assert manager._citation_matches_paper(
        citation, "test paper", ["john doe", "jane smith"], 2023
    )

    # Title and author match, year mismatch
    assert manager._citation_matches_paper(
        citation, "test paper", ["john doe", "jane smith"], 2022
    )

    # Title and year match, author mismatch
    assert manager._citation_matches_paper(
        citation, "test paper", ["alice johnson"], 2023
    )

    # Title mismatch
    assert not manager._citation_matches_paper(
        citation, "different paper", ["john doe", "jane smith"], 2023
    )


def test_extract_citations_from_content():
    """Test extracting citations from content."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))
    content = """
# Test Paper

## Summary

This is a summary.

## Citations

1. J. Smith, "Test Paper", Journal, 2023
2. A. Johnson, "Another Paper", Conference, 2022

## Notes

Some notes.
"""

    # When
    citations = manager._extract_citations_from_content(content)

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


def test_find_citations_to_paper():
    """Test finding citations to a paper."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))
    paper = {
        "title": "Test Paper",
        "authors": ["J. Smith"],
        "year": 2023,
    }

    # Mock the glob method to return a list of files
    with patch("pathlib.Path.glob") as mock_glob:
        mock_glob.return_value = [
            Path("/path/to/notes/note1.md"),
            Path("/path/to/notes/note2.md"),
        ]

        # Mock the open function to return different content for each file
        note1_content = """
        # Note 1

        ## Citations

        1. J. Smith, "Test Paper", Journal, 2023
        """

        note2_content = """
        # Note 2

        ## Citations

        1. A. Johnson, "Another Paper", Conference, 2022
        """

        # Use side_effect to return different content for different files
        mock_open_obj = mock_open()
        mock_open_obj.side_effect = [
            mock_open(read_data=note1_content).return_value,
            mock_open(read_data=note2_content).return_value,
        ]

        # When
        with patch("builtins.open", mock_open_obj):
            citations = manager.find_citations_to_paper(paper)

        # Then
        assert len(citations) == 1
        assert citations[0][0] == Path("/path/to/notes/note1.md")
        assert len(citations[0][1]) == 1
        assert citations[0][1][0]["title"] == "Test Paper"


def test_update_note_citations():
    """Test updating note citations."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))
    note_path = Path("/path/to/notes/note.md")
    citations = [
        {
            "text": "J. Smith, \"Test Paper\", Journal, 2023",
            "start": 50,
            "end": 90,
        }
    ]
    paper = {
        "path": Path("/path/to/notes/paper.md"),
        "title": "Test Paper",
        "authors": ["J. Smith"],
        "year": 2023,
    }

    # Mock the open function
    note_content = """
    # Note

    ## Citations

    1. J. Smith, "Test Paper", Journal, 2023
    """

    # When
    with patch("builtins.open", mock_open(read_data=note_content)) as mock_file:
        result = manager._update_note_citations(note_path, citations, paper)

        # Then
        assert result
        # Check that write was called with updated content
        mock_file.return_value.write.assert_called_once()
        written_content = mock_file.return_value.write.call_args[0][0]
        assert "J. Smith, \"Test Paper\", Journal, 2023 [[paper]]" in written_content


def test_update_citation_links():
    """Test updating citation links."""
    # Given
    manager = LinkManager(Path("/path/to/notes"))
    new_paper = {
        "path": Path("/path/to/notes/paper.md"),
        "title": "Test Paper",
        "authors": ["J. Smith"],
        "year": 2023,
    }

    # Mock find_citations_to_paper to return a list of citations
    with patch.object(manager, "find_citations_to_paper") as mock_find_citations:
        mock_find_citations.return_value = [
            (
                Path("/path/to/notes/note.md"),
                [
                    {
                        "text": "J. Smith, \"Test Paper\", Journal, 2023",
                        "start": 50,
                        "end": 90,
                    }
                ],
            )
        ]

        # Mock _update_note_citations to return True
        with patch.object(manager, "_update_note_citations") as mock_update_citations:
            mock_update_citations.return_value = True

            # When
            manager.update_citation_links(new_paper)

            # Then
            mock_find_citations.assert_called_once_with(
                new_paper, Path("/path/to/notes")
            )
            mock_update_citations.assert_called_once()
