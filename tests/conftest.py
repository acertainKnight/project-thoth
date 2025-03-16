"""
Test fixtures for Thoth.
"""
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from thoth.config import APIKeys, ThothConfig


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_pdf(temp_dir):
    """Provide a sample PDF for testing."""
    pdf_path = temp_dir / "sample.pdf"
    # Create an empty file for testing
    pdf_path.touch()
    return pdf_path


@pytest.fixture
def sample_markdown():
    """Provide sample Markdown content for testing."""
    return """# Sample Paper Title

Authors: John Doe, Jane Smith
Year: 2023
DOI: 10.1234/5678

Abstract: This is the abstract of the sample paper. It contains a summary of the research.

## Introduction

This is the introduction section of the paper.

## Methods

These are the methods used in the research.

## Results

These are the results of the research.

## Conclusion

This is the conclusion of the paper.

## References

1. Smith, J. (2022). Another paper. Journal of Research, 10(2), 123-145.
2. Doe, A. (2021). Yet another paper. Conference on Research, 45-67.
"""


@pytest.fixture
def mock_config():
    """Provide a mock configuration for testing."""
    return ThothConfig(
        workspace_dir=Path("/tmp/thoth"),
        pdf_dir=Path("/tmp/thoth/pdfs"),
        markdown_dir=Path("/tmp/thoth/markdown"),
        notes_dir=Path("/tmp/thoth/notes"),
        templates_dir=Path("/tmp/thoth/templates"),
        log_file=Path("/tmp/thoth/logs/thoth.log"),
        api_keys=APIKeys(mistral="test_mistral", openrouter="test_openrouter"),
    )


@pytest.fixture
def mock_ocr_api():
    """Mock the OCR API for testing."""
    with patch("thoth.core.ocr_manager.MistralClient") as mock:
        mock_client = MagicMock()
        mock_client.process_pdf.return_value = "Sample markdown content"
        mock.return_value = mock_client
        yield mock


@pytest.fixture
def mock_llm_api():
    """Mock the LLM API for testing."""
    with patch("thoth.core.llm_processor.OpenRouterClient") as mock:
        mock_client = MagicMock()
        mock_client.analyze_content.return_value = {
            "summary": "Sample summary",
            "key_points": ["point1", "point2"],
            "limitations": ["limitation1"],
            "research_question": "Sample research question",
        }
        mock_client.extract_citations.return_value = [
            {
                "text": "Smith, J. (2022). Another paper. Journal of Research, 10(2), 123-145.",
                "authors": ["J. Smith"],
                "title": "Another paper",
                "year": 2022,
                "journal": "Journal of Research",
                "context": "This is the context of the citation.",
            }
        ]
        mock.return_value = mock_client
        yield mock
