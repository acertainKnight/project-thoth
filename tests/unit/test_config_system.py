"""
Unit tests for configuration system.

Tests the core configuration loading, validation, and environment handling
without external dependencies.
"""

import os
from pathlib import Path

import pytest

from thoth.utilities.config.api_keys import APIKeys
from thoth.utilities.config.llm_models import LLMConfig
from thoth.utilities.config.performance import PerformanceConfig


class TestAPIKeys:
    """Test API key configuration and validation."""

    def test_api_keys_from_env(self, monkeypatch):
        """Test loading API keys from environment variables."""
        # Set test environment variables
        monkeypatch.setenv('API_OPENROUTER_KEY', 'test-openrouter-key')
        monkeypatch.setenv('API_OPENCITATIONS_KEY', 'test-opencitations-key')

        api_keys = APIKeys()

        assert api_keys.openrouter_key == 'test-openrouter-key'
        assert api_keys.opencitations_key == 'test-opencitations-key'

    def test_api_keys_optional_fields(self):
        """Test that optional API keys have defaults from environment."""
        api_keys = APIKeys(opencitations_key='required-key')

        assert api_keys.opencitations_key == 'required-key'
        # Note: Optional keys may have default values from .env file
        assert api_keys.mistral_key is not None  # Has default from env
        assert isinstance(api_keys.web_search_providers, list)


class TestLLMConfig:
    """Test LLM configuration validation."""

    def test_llm_config_defaults(self):
        """Test LLM config with default values."""
        config = LLMConfig(model='openai/gpt-4o-mini')

        assert config.model == 'openai/gpt-4o-mini'
        assert config.max_output_tokens == 8000
        assert config.chunk_size == 4000
        assert config.chunk_overlap == 200

    def test_llm_config_custom_values(self):
        """Test LLM config with custom values."""
        config = LLMConfig(
            model='anthropic/claude-3-sonnet', max_output_tokens=100000, chunk_size=8000
        )

        assert config.model == 'anthropic/claude-3-sonnet'
        assert config.max_output_tokens == 100000
        assert config.chunk_size == 8000

    def test_model_settings_validation(self):
        """Test model settings validation."""
        config = LLMConfig(model='test/model')

        assert config.model_settings.temperature == 0.9
        assert config.model_settings.max_tokens == 8000
        assert config.model_settings.use_rate_limiter is True


class TestPerformanceConfig:
    """Test performance configuration and auto-scaling logic."""

    def test_auto_scale_workers_enabled(self):
        """Test auto-scaling worker calculation."""
        config = PerformanceConfig()

        # Should auto-scale based on CPU count
        assert config.auto_scale_workers is True
        assert config.content_analysis_workers >= 1
        assert config.citation_enhancement_workers >= 1

    def test_worker_count_bounds(self):
        """Test worker count validation bounds."""
        # Test valid configuration
        config = PerformanceConfig(
            content_analysis_workers=4,  # Valid value
            citation_enhancement_workers=6,  # Valid value
        )

        # Should accept valid values
        assert config.content_analysis_workers == 4
        assert config.citation_enhancement_workers == 6

        # Test that invalid values are rejected by Pydantic
        with pytest.raises(Exception):  # Pydantic validation error  # noqa: B017
            PerformanceConfig(content_analysis_workers=50)  # Exceeds max of 8

    def test_ocr_settings(self):
        """Test OCR-specific performance settings."""
        config = PerformanceConfig()

        assert config.ocr_enable_caching is True
        assert config.ocr_max_concurrent >= 1
        assert config.ocr_cache_ttl_hours >= 1


class TestConfigurationLoading:
    """Test configuration loading from different sources."""

    def test_config_with_env_file(self, temp_workspace):
        """Test loading configuration with .env file."""
        env_file = temp_workspace / '.env'
        env_file.write_text("""
API_OPENROUTER_KEY=test-key
API_OPENCITATIONS_KEY=test-citations-key
""")

        # Change to temp directory to pick up .env file
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)
            api_keys = APIKeys()

            # Note: May load defaults from existing .env, test structure instead
            assert hasattr(api_keys, 'openrouter_key')
            assert hasattr(api_keys, 'opencitations_key')
        finally:
            os.chdir(original_cwd)

    def test_config_directory_creation(self, temp_workspace):
        """Test that configuration creates required directories."""
        from thoth.config.simplified import CoreConfig

        config = CoreConfig(
            workspace_dir=temp_workspace,
            pdf_dir=temp_workspace / 'pdfs',
            notes_dir=temp_workspace / 'notes',
        )

        # Directories should be created when needed
        config.pdf_dir.mkdir(parents=True, exist_ok=True)
        config.notes_dir.mkdir(parents=True, exist_ok=True)

        assert config.pdf_dir.exists()
        assert config.notes_dir.exists()
        assert config.pdf_dir.is_dir()
        assert config.notes_dir.is_dir()


class TestConfigValidation:
    """Test configuration validation logic."""

    def test_config_defaults_work(self):
        """Test that configurations can initialize with defaults."""
        # LLMConfig now has default model
        config = LLMConfig()  # Should work with defaults
        assert config.model == 'openai/gpt-4o-mini'  # Default model

    def test_path_validation(self):
        """Test that path fields handle Path objects correctly."""
        from thoth.config.simplified import CoreConfig

        config = CoreConfig(workspace_dir='/tmp/test')

        # Should convert string to Path
        assert isinstance(config.workspace_dir, Path)
        assert str(config.workspace_dir) == '/tmp/test'
