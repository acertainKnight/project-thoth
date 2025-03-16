"""
Pytest configuration for Thoth tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from thoth.config import APIKeys, ThothSettings


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def workspace_dir(temp_dir):
    """Create a workspace directory for tests."""
    workspace_dir = temp_dir / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


@pytest.fixture
def pdf_dir(workspace_dir):
    """Create a PDF directory for tests."""
    pdf_dir = workspace_dir / "pdfs"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    return pdf_dir


@pytest.fixture
def markdown_dir(workspace_dir):
    """Create a Markdown directory for tests."""
    markdown_dir = workspace_dir / "markdown"
    markdown_dir.mkdir(parents=True, exist_ok=True)
    return markdown_dir


@pytest.fixture
def notes_dir(workspace_dir):
    """Create a notes directory for tests."""
    notes_dir = workspace_dir / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    return notes_dir


@pytest.fixture
def templates_dir(workspace_dir):
    """Create a templates directory for tests."""
    templates_dir = workspace_dir / "templates"
    templates_dir.mkdir(parents=True, exist_ok=True)
    return templates_dir


@pytest.fixture
def log_dir(workspace_dir):
    """Create a log directory for tests."""
    log_dir = workspace_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


@pytest.fixture
def api_keys():
    """Create API keys for tests."""
    return APIKeys(mistral="test_mistral_key", openrouter="test_openrouter_key")


@pytest.fixture
def config(
    workspace_dir, pdf_dir, markdown_dir, notes_dir, templates_dir, log_dir, api_keys
):
    """Create a configuration for tests."""
    return ThothSettings(
        workspace_dir=workspace_dir,
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        notes_dir=notes_dir,
        templates_dir=templates_dir,
        log_file=log_dir / "thoth.log",
        mistral_key=api_keys.mistral,
        openrouter_key=api_keys.openrouter,
    )


@pytest.fixture
def sample_pdf(pdf_dir):
    """Create a sample PDF for tests."""
    pdf_path = pdf_dir / "sample.pdf"
    pdf_path.touch()
    return pdf_path


@pytest.fixture
def sample_markdown(markdown_dir):
    """Create a sample Markdown file for tests."""
    markdown_path = markdown_dir / "sample.md"
    with open(markdown_path, "w") as f:
        f.write("# Sample Markdown\n\nThis is a sample Markdown file.")
    return markdown_path


@pytest.fixture
def sample_note(notes_dir):
    """Create a sample note for tests."""
    note_path = notes_dir / "sample.md"
    with open(note_path, "w") as f:
        f.write("# Sample Note\n\nThis is a sample note.")
    return note_path


@pytest.fixture
def mock_ocr_api():
    """Mock the OCR API for testing."""
    return MagicMock()


@pytest.fixture
def mock_llm_api():
    """Mock the LLM API for testing."""
    return MagicMock()
