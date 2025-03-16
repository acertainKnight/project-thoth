"""
Tests for the note generator module.
"""

from pathlib import Path
from unittest.mock import patch

import pytest
from jinja2 import TemplateNotFound

from thoth.core.note_generator import NoteGenerator


def test_init(temp_dir):
    """Test initialization of NoteGenerator."""
    # Given
    templates_dir = temp_dir / "templates"
    notes_dir = temp_dir / "notes"

    # When
    generator = NoteGenerator(templates_dir, notes_dir)

    # Then
    assert generator.templates_dir == templates_dir
    assert generator.notes_dir == notes_dir
    assert templates_dir.exists()
    assert notes_dir.exists()


def test_create_note(temp_dir):
    """Test creating a note from content."""
    # Given
    templates_dir = temp_dir / "templates"
    notes_dir = temp_dir / "notes"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Create a test template
    template_path = templates_dir / "note_template.md"
    with open(template_path, "w") as f:
        f.write(
            "# {{ title }}\n\n"
            "**Authors**: {{ authors | join(', ') }}\n"
            "{% if year %}**Year**: {{ year }}{% endif %}\n\n"
            "## Summary\n\n{{ summary }}\n\n"
            "## Source Files\n\n"
            "- [PDF]({{ source_files.pdf }})\n"
            "- [Markdown]({{ source_files.markdown }})\n"
        )

    generator = NoteGenerator(templates_dir, notes_dir)

    # Create test content
    content = {
        "title": "Test Paper",
        "authors": ["John Doe", "Jane Smith"],
        "year": 2023,
        "summary": "This is a test summary.",
        "source_files": {"pdf": "/path/to/test.pdf", "markdown": "/path/to/test.md"},
    }

    # When
    note_path = generator.create_note(content)

    # Then
    assert note_path.exists()
    assert note_path.name == "2023 - Test Paper.md"

    # Check content
    with open(note_path) as f:
        note_content = f.read()

    assert "# Test Paper" in note_content
    assert "**Authors**: John Doe, Jane Smith" in note_content
    assert "**Year**: 2023" in note_content
    assert "This is a test summary." in note_content
    assert "[PDF](/path/to/test.pdf)" in note_content
    assert "[Markdown](/path/to/test.md)" in note_content


def test_create_note_missing_template(temp_dir):
    """Test creating a note with a missing template."""
    # Given
    templates_dir = temp_dir / "templates"
    notes_dir = temp_dir / "notes"
    templates_dir.mkdir(parents=True, exist_ok=True)
    generator = NoteGenerator(templates_dir, notes_dir)

    content = {
        "title": "Test Paper",
        "authors": ["John Doe"],
        "source_files": {"pdf": "/path/to/test.pdf", "markdown": "/path/to/test.md"},
    }

    # When/Then
    with pytest.raises(TemplateNotFound):
        generator.create_note(content)


def test_create_note_missing_required_fields(temp_dir):
    """Test creating a note with missing required fields."""
    # Given
    templates_dir = temp_dir / "templates"
    notes_dir = temp_dir / "notes"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Create a test template
    template_path = templates_dir / "note_template.md"
    with open(template_path, "w") as f:
        f.write("# {{ title }}\n\n**Authors**: {{ authors | join(', ') }}\n")

    generator = NoteGenerator(templates_dir, notes_dir)

    # Missing title
    content1 = {
        "authors": ["John Doe"],
        "source_files": {"pdf": "/path/to/test.pdf", "markdown": "/path/to/test.md"},
    }

    # Missing authors
    content2 = {
        "title": "Test Paper",
        "source_files": {"pdf": "/path/to/test.pdf", "markdown": "/path/to/test.md"},
    }

    # Missing source_files
    content3 = {"title": "Test Paper", "authors": ["John Doe"]}

    # When/Then
    with pytest.raises(ValueError) as excinfo:
        generator.create_note(content1)
    assert "Missing required fields: title" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        generator.create_note(content2)
    assert "Missing required fields: authors" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        generator.create_note(content3)
    assert "Missing source_files in content" in str(excinfo.value)


def test_create_note_invalid_source_files(temp_dir):
    """Test creating a note with invalid source_files."""
    # Given
    templates_dir = temp_dir / "templates"
    notes_dir = temp_dir / "notes"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Create a test template
    template_path = templates_dir / "note_template.md"
    with open(template_path, "w") as f:
        f.write("# {{ title }}\n\n**Authors**: {{ authors | join(', ') }}\n")

    generator = NoteGenerator(templates_dir, notes_dir)

    # source_files is not a dict
    content1 = {
        "title": "Test Paper",
        "authors": ["John Doe"],
        "source_files": "not a dict",
    }

    # source_files missing required fields
    content2 = {
        "title": "Test Paper",
        "authors": ["John Doe"],
        "source_files": {
            "pdf": "/path/to/test.pdf"
            # Missing markdown
        },
    }

    # When/Then
    with pytest.raises(ValueError) as excinfo:
        generator.create_note(content1)
    assert "source_files must be a dictionary" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        generator.create_note(content2)
    assert "Missing required source files: markdown" in str(excinfo.value)


def test_create_basic_note(temp_dir):
    """Test creating a basic note when LLM processing fails."""
    # Given
    templates_dir = temp_dir / "templates"
    notes_dir = temp_dir / "notes"
    templates_dir.mkdir(parents=True, exist_ok=True)

    # Create a test template
    template_path = templates_dir / "note_template.md"
    with open(template_path, "w") as f:
        f.write(
            "# {{ title }}\n\n"
            "**Authors**: {{ authors | join(', ') }}\n"
            "{% if year %}**Year**: {{ year }}{% endif %}\n\n"
            "## Summary\n\n{{ summary }}\n\n"
            "## Source Files\n\n"
            "- [PDF]({{ source_files.pdf }})\n"
            "- [Markdown]({{ source_files.markdown }})\n"
        )

    generator = NoteGenerator(templates_dir, notes_dir)

    # Create test metadata
    metadata = {"title": "Test Paper", "authors": ["John Doe"], "year": 2023}

    pdf_path = Path("/path/to/test.pdf")
    markdown_path = Path("/path/to/test.md")

    # When
    note_path = generator.create_basic_note(metadata, pdf_path, markdown_path)

    # Then
    assert note_path.exists()
    assert note_path.name == "2023 - Test Paper.md"

    # Check content
    with open(note_path) as f:
        note_content = f.read()

    assert "# Test Paper" in note_content
    assert "**Authors**: John Doe" in note_content
    assert "**Year**: 2023" in note_content
    assert "Note: LLM processing failed. Basic note created." in note_content
    assert "[PDF](/path/to/test.pdf)" in note_content
    assert "[Markdown](/path/to/test.md)" in note_content


def test_clean_filename():
    """Test cleaning filenames."""
    # Given
    templates_dir = Path("/tmp/templates")
    notes_dir = Path("/tmp/notes")

    with patch("thoth.utils.file.ensure_directory"):
        generator = NoteGenerator(templates_dir, notes_dir)

    # When/Then
    assert generator._clean_filename("Test: Paper.md") == "Test_ Paper.md"
    assert generator._clean_filename("Test/Paper.md") == "Test_Paper.md"
    assert generator._clean_filename("Test\\Paper.md") == "Test_Paper.md"
    assert generator._clean_filename("Test?Paper.md") == "Test_Paper.md"
    assert generator._clean_filename("Test*Paper.md") == "Test_Paper.md"

    # Test long filename
    long_title = "A" * 300
    long_filename = f"{long_title}.md"
    cleaned = generator._clean_filename(long_filename)
    assert len(cleaned) <= 255
    assert cleaned.endswith(".md")


def test_get_note_filename():
    """Test generating note filenames."""
    # Given
    templates_dir = Path("/tmp/templates")
    notes_dir = Path("/tmp/notes")

    with patch("thoth.utils.file.ensure_directory"):
        generator = NoteGenerator(templates_dir, notes_dir)

    # When/Then
    # With year
    content1 = {"title": "Test Paper", "year": 2023}
    assert generator._get_note_filename(content1) == "2023 - Test Paper.md"

    # Without year
    content2 = {"title": "Test Paper"}
    assert generator._get_note_filename(content2) == "Test Paper.md"

    # With invalid characters
    content3 = {"title": "Test: Paper?", "year": 2023}
    assert generator._get_note_filename(content3) == "2023 - Test_ Paper_.md"

    # Missing title
    content4 = {}
    assert generator._get_note_filename(content4) == "Unknown Title.md"
