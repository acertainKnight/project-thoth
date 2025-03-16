"""
Tests for the configuration module.
"""
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from thoth.config import APIKeys, ThothConfig, load_config


def test_api_keys():
    """Test APIKeys model."""
    # Test with valid keys
    keys = APIKeys(mistral="test_mistral", openrouter="test_openrouter")
    assert keys.mistral == "test_mistral"
    assert keys.openrouter == "test_openrouter"

    # Test with missing keys
    with pytest.raises(ValueError):
        APIKeys(mistral="test_mistral")

    with pytest.raises(ValueError):
        APIKeys(openrouter="test_openrouter")


def test_thoth_config():
    """Test ThothConfig model."""
    # Test with valid config
    config = ThothConfig(
        workspace_dir=Path("/tmp/thoth"),
        pdf_dir=Path("/tmp/thoth/pdfs"),
        markdown_dir=Path("/tmp/thoth/markdown"),
        notes_dir=Path("/tmp/thoth/notes"),
        templates_dir=Path("/tmp/thoth/templates"),
        log_file=Path("/tmp/thoth/logs/thoth.log"),
        api_keys=APIKeys(mistral="test_mistral", openrouter="test_openrouter"),
    )

    assert config.workspace_dir == Path("/tmp/thoth")
    assert config.pdf_dir == Path("/tmp/thoth/pdfs")
    assert config.markdown_dir == Path("/tmp/thoth/markdown")
    assert config.notes_dir == Path("/tmp/thoth/notes")
    assert config.templates_dir == Path("/tmp/thoth/templates")
    assert config.log_file == Path("/tmp/thoth/logs/thoth.log")
    assert config.log_level == "INFO"  # Default value
    assert config.watch_interval == 5  # Default value
    assert config.bulk_process_chunk_size == 10  # Default value
    assert config.api_keys.mistral == "test_mistral"
    assert config.api_keys.openrouter == "test_openrouter"


@patch.dict(os.environ, {
    "WORKSPACE_DIR": "/tmp/thoth",
    "PDF_DIR": "/tmp/thoth/pdfs",
    "MARKDOWN_DIR": "/tmp/thoth/markdown",
    "NOTES_DIR": "/tmp/thoth/notes",
    "TEMPLATES_DIR": "/tmp/thoth/templates",
    "LOG_FILE": "/tmp/thoth/logs/thoth.log",
    "LOG_LEVEL": "DEBUG",
    "WATCH_INTERVAL": "10",
    "BULK_PROCESS_CHUNK_SIZE": "20",
    "API_MISTRAL_KEY": "test_mistral",
    "API_OPENROUTER_KEY": "test_openrouter",
})
def test_load_config():
    """Test load_config function."""
    config = load_config()

    assert config.workspace_dir == Path("/tmp/thoth")
    assert config.pdf_dir == Path("/tmp/thoth/pdfs")
    assert config.markdown_dir == Path("/tmp/thoth/markdown")
    assert config.notes_dir == Path("/tmp/thoth/notes")
    assert config.templates_dir == Path("/tmp/thoth/templates")
    assert config.log_file == Path("/tmp/thoth/logs/thoth.log")
    assert config.log_level == "DEBUG"
    assert config.watch_interval == 10
    assert config.bulk_process_chunk_size == 20
    assert config.api_keys.mistral == "test_mistral"
    assert config.api_keys.openrouter == "test_openrouter"
