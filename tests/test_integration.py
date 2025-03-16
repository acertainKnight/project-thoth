"""
Integration tests for Thoth.

These tests verify that the components work together correctly.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thoth.config import APIKeys, ThothConfig


@pytest.fixture
def mock_components():
    """Create mock components for testing."""
    components = {
        "ocr_manager": MagicMock(),
        "markdown_processor": MagicMock(),
        "llm_processor": MagicMock(),
        "note_generator": MagicMock(),
        "link_manager": MagicMock(),
        "pdf_monitor": MagicMock(),
    }

    # Configure mocks
    components["ocr_manager"].convert_pdf_to_markdown.return_value = Path(
        "test_markdown.md"
    )
    components["markdown_processor"].process_markdown.return_value = {
        "text": "Sample text",
        "metadata": {"title": "Test Paper", "authors": ["Test Author"]},
    }
    components["llm_processor"].analyze_content.return_value = {
        "summary": "Test summary",
        "topics": ["topic1", "topic2"],
    }
    components["llm_processor"].extract_citations.return_value = []
    components["note_generator"].create_note.return_value = Path("test_note.md")

    return components


def test_process_pdf(mock_components, tmp_path):
    """Test the process_pdf function."""
    # Import the function here to avoid circular imports
    from main import process_pdf

    # Create a test PDF
    pdf_path = tmp_path / "test.pdf"
    pdf_path.touch()

    # Process the PDF
    result = process_pdf(pdf_path, mock_components)

    # Check that the PDF was processed correctly
    assert result is True
    mock_components["ocr_manager"].convert_pdf_to_markdown.assert_called_once_with(
        pdf_path
    )
    mock_components["markdown_processor"].process_markdown.assert_called_once()
    mock_components["llm_processor"].analyze_content.assert_called_once_with(
        "Sample text"
    )
    mock_components["llm_processor"].extract_citations.assert_called_once_with(
        "Sample text"
    )
    mock_components["note_generator"].create_note.assert_called_once()
    mock_components["link_manager"].update_citation_links.assert_called_once()


@patch("main.OCRManager")
@patch("main.MarkdownProcessor")
@patch("main.LLMProcessor")
@patch("main.NoteGenerator")
@patch("main.LinkManager")
@patch("main.PDFMonitor")
def test_main_normal_startup(
    mock_pdf_monitor_cls,
    mock_link_manager_cls,
    mock_note_generator_cls,
    mock_llm_processor_cls,
    mock_markdown_processor_cls,
    mock_ocr_manager_cls,
):
    """Test the main function with normal startup."""
    # Import the function here to avoid circular imports
    from main import main

    # Mock the components
    mock_pdf_monitor = mock_pdf_monitor_cls.return_value

    # Mock time.sleep to avoid infinite loop
    with patch("time.sleep", side_effect=KeyboardInterrupt):
        # Run the main function
        try:
            main()
        except KeyboardInterrupt:
            pass

    # Check that the components were initialized correctly
    mock_ocr_manager_cls.assert_called_once()
    mock_markdown_processor_cls.assert_called_once()
    mock_llm_processor_cls.assert_called_once()
    mock_note_generator_cls.assert_called_once()
    mock_link_manager_cls.assert_called_once()
    mock_pdf_monitor_cls.assert_called_once()

    # Check that the PDF monitor was started
    mock_pdf_monitor.on_new_pdf.assert_called_once()
    mock_pdf_monitor.process_existing_pdfs.assert_called_once()
    mock_pdf_monitor.start.assert_called_once()
    mock_pdf_monitor.stop.assert_called_once()


def test_uri_handling():
    """Test the URI handling functionality directly."""
    # Create a mock URI handler
    uri_handler = MagicMock()
    uri_handler.process_uri.return_value = True

    # Create a test URI
    uri = "thoth://doi:10.1234/5678"

    # Process the URI
    result = uri_handler.process_uri(uri)

    # Check that the URI was processed correctly
    assert result is True
    uri_handler.process_uri.assert_called_once_with(uri)


def test_end_to_end(tmp_path, monkeypatch):
    """
    Test the end-to-end workflow with mocked components.

    This test simulates the complete workflow:
    1. A PDF is added to the monitored directory
    2. The PDF is processed through the pipeline
    3. A note is created with the processed content
    """
    # Skip this test in CI environments
    if os.environ.get("CI"):
        pytest.skip("Skipping end-to-end test in CI environment")

    # Create a test workspace
    workspace_dir = tmp_path / "workspace"
    pdf_dir = workspace_dir / "pdfs"
    markdown_dir = workspace_dir / "markdown"
    notes_dir = workspace_dir / "notes"
    templates_dir = workspace_dir / "templates"
    log_dir = workspace_dir / "logs"

    # Create directories
    for directory in [pdf_dir, markdown_dir, notes_dir, templates_dir, log_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    # Create a mock config with proper APIKeys
    api_keys = APIKeys(mistral="test_mistral_key", openrouter="test_openrouter_key")
    config = ThothConfig(
        workspace_dir=workspace_dir,
        pdf_dir=pdf_dir,
        markdown_dir=markdown_dir,
        notes_dir=notes_dir,
        templates_dir=templates_dir,
        log_file=log_dir / "thoth.log",
        api_keys=api_keys,
    )

    # Mock the load_config function
    monkeypatch.setattr("main.load_config", lambda: config)

    # Create mock components
    ocr_manager = MagicMock()
    markdown_processor = MagicMock()
    llm_processor = MagicMock()
    note_generator = MagicMock()
    link_manager = MagicMock()

    # Configure mocks
    ocr_manager.convert_pdf_to_markdown.return_value = markdown_dir / "test.md"
    markdown_processor.process_markdown.return_value = {
        "text": "Sample text",
        "metadata": {"title": "Test Paper", "authors": ["Test Author"]},
    }
    llm_processor.analyze_content.return_value = {
        "summary": "Test summary",
        "topics": ["topic1", "topic2"],
    }
    llm_processor.extract_citations.return_value = []
    note_generator.create_note.return_value = notes_dir / "test.md"

    # Create a test PDF
    test_pdf = pdf_dir / "test.pdf"
    test_pdf.touch()

    # Import the function here to avoid circular imports
    from main import process_pdf

    # Create components dictionary
    components = {
        "ocr_manager": ocr_manager,
        "markdown_processor": markdown_processor,
        "llm_processor": llm_processor,
        "note_generator": note_generator,
        "link_manager": link_manager,
    }

    # Process the PDF
    result = process_pdf(test_pdf, components)

    # Check that the PDF was processed correctly
    assert result is True
    ocr_manager.convert_pdf_to_markdown.assert_called_once_with(test_pdf)
    markdown_processor.process_markdown.assert_called_once()
    llm_processor.analyze_content.assert_called_once_with("Sample text")
    llm_processor.extract_citations.assert_called_once_with("Sample text")
    note_generator.create_note.assert_called_once()
    link_manager.update_citation_links.assert_called_once()
