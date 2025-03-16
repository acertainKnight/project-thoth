"""
Tests for the configuration module.
"""

import os
from pathlib import Path
from unittest.mock import patch

from thoth.config import APIKeys, ThothSettings, load_config


def test_api_keys():
    """Test APIKeys model."""
    # Create APIKeys directly without loading from environment
    keys = APIKeys(mistral="test_mistral", openrouter="test_openrouter", _env_file=None)
    assert keys.mistral == "test_mistral"
    assert keys.openrouter == "test_openrouter"

    # Test with missing keys - this should now work since fields are optional
    keys_mistral_only = APIKeys(mistral="test_mistral", openrouter=None, _env_file=None)
    assert keys_mistral_only.mistral == "test_mistral"
    assert keys_mistral_only.openrouter is None

    keys_openrouter_only = APIKeys(
        mistral=None, openrouter="test_openrouter", _env_file=None
    )
    assert keys_openrouter_only.mistral is None
    assert keys_openrouter_only.openrouter == "test_openrouter"


@patch.dict(os.environ, {}, clear=True)
def test_thoth_settings():
    """Test ThothSettings model."""
    # Test with minimal configuration and explicit paths
    config = ThothSettings(
        workspace_dir=Path("/tmp/thoth"),
        pdf_dir=Path("/tmp/thoth/data/pdfs"),
        markdown_dir=Path("/tmp/thoth/data/markdown"),
        notes_dir=Path("/tmp/thoth/data/notes"),
        templates_dir=Path("/tmp/thoth/templates"),
        log_file=Path("/tmp/thoth/logs/thoth.log"),
        mistral_key="test_mistral",
        openrouter_key="test_openrouter",
        _env_file=None,
    )

    assert config.workspace_dir == Path("/tmp/thoth")
    assert config.pdf_dir == Path("/tmp/thoth/data/pdfs")
    assert config.markdown_dir == Path("/tmp/thoth/data/markdown")
    assert config.notes_dir == Path("/tmp/thoth/data/notes")
    assert config.templates_dir == Path("/tmp/thoth/templates")
    assert config.log_file == Path("/tmp/thoth/logs/thoth.log")
    assert config.log_level == "INFO"
    assert config.watch_interval == 5
    assert config.bulk_process_chunk_size == 10
    assert config.mistral_key == "test_mistral"
    assert config.openrouter_key == "test_openrouter"

    # Test with full configuration
    config = ThothSettings(
        workspace_dir=Path("/tmp/thoth"),
        pdf_dir=Path("/tmp/thoth/custom_pdfs"),
        markdown_dir=Path("/tmp/thoth/custom_markdown"),
        notes_dir=Path("/tmp/thoth/custom_notes"),
        templates_dir=Path("/tmp/thoth/custom_templates"),
        log_file=Path("/tmp/thoth/custom_logs/thoth.log"),
        log_level="DEBUG",
        watch_interval=10,
        bulk_process_chunk_size=20,
        mistral_key="test_mistral",
        openrouter_key="test_openrouter",
        _env_file=None,
    )
    assert config.workspace_dir == Path("/tmp/thoth")
    assert config.pdf_dir == Path("/tmp/thoth/custom_pdfs")
    assert config.markdown_dir == Path("/tmp/thoth/custom_markdown")
    assert config.notes_dir == Path("/tmp/thoth/custom_notes")
    assert config.templates_dir == Path("/tmp/thoth/custom_templates")
    assert config.log_file == Path("/tmp/thoth/custom_logs/thoth.log")
    assert config.log_level == "DEBUG"
    assert config.watch_interval == 10
    assert config.bulk_process_chunk_size == 20
    assert config.mistral_key == "test_mistral"
    assert config.openrouter_key == "test_openrouter"

    # Test api_keys property
    api_keys = config.api_keys
    assert api_keys.mistral == "test_mistral"
    assert api_keys.openrouter == "test_openrouter"


@patch.dict(
    os.environ,
    {
        "WORKSPACE_DIR": "/tmp/thoth_env",
        "PDF_DIR": "/tmp/thoth_env/custom_pdfs",
        "MARKDOWN_DIR": "/tmp/thoth_env/custom_markdown",
        "NOTES_DIR": "/tmp/thoth_env/custom_notes",
        "TEMPLATES_DIR": "/tmp/thoth_env/custom_templates",
        "LOG_FILE": "/tmp/thoth_env/custom_logs/thoth.log",
        "LOG_LEVEL": "DEBUG",
        "WATCH_INTERVAL": "10",
        "BULK_PROCESS_CHUNK_SIZE": "20",
        "MISTRAL_KEY": "env_mistral",
        "OPENROUTER_KEY": "env_openrouter",
    },
)
def test_load_config_from_env():
    """Test loading configuration from environment variables."""

    # Create a custom ThothSettings class for testing
    class TestThothSettings(ThothSettings):
        @classmethod
        @patch.object(ThothSettings, 'set_default_paths')
        def set_default_paths(cls, _mock, v, _info):
            """Override set_default_paths to return the value as is."""
            return v

    # Patch the ThothSettings class in the load_config function
    with patch('thoth.config.ThothSettings', TestThothSettings):
        config = load_config()
        assert config.workspace_dir == Path("/tmp/thoth_env")
        assert config.pdf_dir == Path("/tmp/thoth_env/custom_pdfs")
        assert config.markdown_dir == Path("/tmp/thoth_env/custom_markdown")
        assert config.notes_dir == Path("/tmp/thoth_env/custom_notes")
        assert config.templates_dir == Path("/tmp/thoth_env/custom_templates")
        assert config.log_file == Path("/tmp/thoth_env/custom_logs/thoth.log")
        assert config.log_level == "DEBUG"
        assert config.watch_interval == 10
        assert config.bulk_process_chunk_size == 20
        assert config.mistral_key == "env_mistral"
        assert config.openrouter_key == "env_openrouter"
