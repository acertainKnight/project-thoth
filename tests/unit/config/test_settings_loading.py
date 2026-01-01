"""Tests for Settings loading from JSON files.

Tests Settings.from_json_file() with various scenarios:
- Valid JSON files
- Missing files
- Invalid JSON syntax
- Partial settings (defaults fill in)
- CamelCase alias parsing
- Error handling
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tests.fixtures.config_fixtures import (
    get_full_settings_json,
    get_invalid_settings_json,
    get_minimal_settings_json,
)
from thoth.config import Settings


class TestSettingsFromJsonFile:
    """Test Settings.from_json_file() class method."""

    def test_load_minimal_settings(self, minimal_settings_file: Path):
        """Test loading minimal valid settings.json."""
        settings = Settings.from_json_file(minimal_settings_file)

        assert isinstance(settings, Settings)
        assert settings.version == "1.0.0"
        # Defaults should be populated
        assert settings.llm.default.model == "google/gemini-2.5-flash"

    def test_load_full_settings(self, full_settings_file: Path):
        """Test loading complete settings.json."""
        settings = Settings.from_json_file(full_settings_file)

        assert settings.version == "1.0.0"
        assert settings.api_keys.openai_key == "test-openai-key"
        assert settings.llm.default.model == "google/gemini-2.5-flash"
        assert settings.llm.citation.model == "openai/gpt-4o-mini"
        assert settings.rag.embedding_model == "openai/text-embedding-3-small"

    def test_load_partial_settings(self, partial_settings_file: Path):
        """Test loading partial settings (defaults fill in missing)."""
        settings = Settings.from_json_file(partial_settings_file)

        # Provided values
        assert settings.api_keys.openai_key == "test-key"
        assert settings.llm.default.model == "test-model"

        # Defaults for missing values
        assert settings.llm.default.temperature == 0.9
        assert settings.rag.embedding_model == "openai/text-embedding-3-small"

    def test_load_missing_file(self, temp_vault: Path):
        """Test loading nonexistent settings file raises FileNotFoundError."""
        nonexistent_file = temp_vault / "_thoth" / "nonexistent.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            Settings.from_json_file(nonexistent_file)

        error_msg = str(exc_info.value)
        assert "Settings file not found" in error_msg
        assert str(nonexistent_file) in error_msg

    def test_load_malformed_json(self, malformed_json_file: Path):
        """Test loading malformed JSON raises exception."""
        with pytest.raises(Exception):  # json.JSONDecodeError
            Settings.from_json_file(malformed_json_file)

    def test_load_invalid_data_types(self, invalid_settings_file: Path):
        """Test loading settings with invalid data types."""
        with pytest.raises((ValidationError, ValueError)):
            Settings.from_json_file(invalid_settings_file)


class TestCamelCaseAliases:
    """Test camelCase alias parsing in settings."""

    def test_api_keys_camel_case(self, temp_vault: Path):
        """Test API keys with camelCase names."""
        settings_data = {
            "apiKeys": {
                "openaiKey": "camel-openai",
                "anthropicKey": "camel-anthropic",
                "googleApiKey": "camel-google"
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.api_keys.openai_key == "camel-openai"
        assert settings.api_keys.anthropic_key == "camel-anthropic"
        assert settings.api_keys.google_api_key == "camel-google"

    def test_llm_config_camel_case(self, temp_vault: Path):
        """Test LLM config with camelCase names."""
        settings_data = {
            "llm": {
                "default": {
                    "maxTokens": 10000,
                    "maxOutputTokens": 8000,
                    "useRateLimiter": False
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.llm.default.max_tokens == 10000
        assert settings.llm.default.max_output_tokens == 8000
        assert settings.llm.default.use_rate_limiter is False

    def test_paths_config_camel_case(self, temp_vault: Path):
        """Test paths config with camelCase names."""
        settings_data = {
            "paths": {
                "knowledgeBase": "custom/knowledge",
                "graphStorage": "custom/graph.xml",
                "agentStorage": "custom/agent"
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.paths.knowledge_base == "custom/knowledge"
        assert settings.paths.graph_storage == "custom/graph.xml"
        assert settings.paths.agent_storage == "custom/agent"

    def test_nested_camel_case(self, temp_vault: Path):
        """Test deeply nested camelCase aliases."""
        settings_data = {
            "memory": {
                "letta": {
                    "serverUrl": "http://custom:8000",
                    "agentName": "custom-agent",
                    "coreMemoryLimit": 20000,
                    "consolidationIntervalHours": 48
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.memory.letta.server_url == "http://custom:8000"
        assert settings.memory.letta.agent_name == "custom-agent"
        assert settings.memory.letta.core_memory_limit == 20000
        assert settings.memory.letta.consolidation_interval_hours == 48


class TestDefaultValues:
    """Test that default values are properly applied."""

    def test_empty_settings_uses_all_defaults(self, temp_vault: Path):
        """Test empty settings JSON uses all default values."""
        settings_data = {}

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        # Check various defaults
        assert settings.llm.default.model == "google/gemini-2.5-flash"
        assert settings.llm.default.temperature == 0.9
        assert settings.rag.embedding_model == "openai/text-embedding-3-small"
        assert settings.servers.api.port == 8000
        assert settings.citation.style == "IEEE"

    def test_partial_llm_config_defaults(self, temp_vault: Path):
        """Test partial LLM config fills in defaults."""
        settings_data = {
            "llm": {
                "default": {
                    "model": "custom-model"
                    # Other fields should use defaults
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.llm.default.model == "custom-model"
        assert settings.llm.default.temperature == 0.9  # Default
        assert settings.llm.default.max_tokens == 500000  # Default

    def test_empty_api_keys_defaults(self, temp_vault: Path):
        """Test empty API keys use default empty strings."""
        settings_data = {
            "apiKeys": {}
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.api_keys.openai_key == ""
        assert settings.api_keys.anthropic_key == ""
        assert settings.api_keys.web_search_providers == []


class TestSchemaFields:
    """Test special schema fields like $schema and _comment."""

    def test_schema_field_parsing(self, temp_vault: Path):
        """Test $schema field is parsed correctly."""
        settings_data = {
            "$schema": "./custom.schema.json",
            "version": "2.0.0"
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.schema_ == "./custom.schema.json"
        assert settings.version == "2.0.0"

    def test_comment_field_parsing(self, temp_vault: Path):
        """Test _comment field is parsed correctly."""
        settings_data = {
            "_comment": "This is a test comment"
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.comment_ == "This is a test comment"

    def test_last_modified_field(self, temp_vault: Path):
        """Test lastModified field is parsed correctly."""
        settings_data = {
            "lastModified": "2025-12-31T12:00:00Z"
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.last_modified == "2025-12-31T12:00:00Z"


class TestNestedStructures:
    """Test complex nested structures in settings."""

    def test_memory_scheduler_jobs(self, temp_vault: Path):
        """Test nested memory scheduler jobs."""
        settings_data = {
            "memory": {
                "scheduler": {
                    "jobs": {
                        "episodic": {
                            "enabled": True,
                            "intervalHours": 12,
                            "timeOfDay": "02:00",
                            "parameters": {
                                "analysisWindowHours": 168,
                                "minMemoriesThreshold": 5
                            }
                        },
                        "weekly": {
                            "enabled": False,
                            "intervalHours": 168
                        }
                    }
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert "episodic" in settings.memory.scheduler.jobs
        assert "weekly" in settings.memory.scheduler.jobs
        episodic = settings.memory.scheduler.jobs["episodic"]
        assert episodic.enabled is True
        assert episodic.interval_hours == 12

    def test_discovery_paths_nested(self, temp_vault: Path):
        """Test nested discovery paths."""
        settings_data = {
            "paths": {
                "discovery": {
                    "sources": "custom/sources",
                    "results": "custom/results",
                    "chromeConfigs": "custom/chrome"
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.paths.discovery.sources == "custom/sources"
        assert settings.paths.discovery.results == "custom/results"
        assert settings.paths.discovery.chrome_configs == "custom/chrome"

    def test_citation_models_nested(self, temp_vault: Path):
        """Test nested citation models."""
        settings_data = {
            "llm": {
                "citation": {
                    "models": {
                        "documentCitation": "doc-model",
                        "referenceCleaning": "ref-model",
                        "structuredExtraction": "extract-model"
                    }
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        models = settings.llm.citation.models
        assert models.document_citation == "doc-model"
        assert models.reference_cleaning == "ref-model"
        assert models.structured_extraction == "extract-model"


class TestErrorHandling:
    """Test error handling in settings loading."""

    def test_file_not_found_error_message(self, temp_vault: Path):
        """Test FileNotFoundError has helpful message."""
        missing_file = temp_vault / "_thoth" / "missing.json"

        with pytest.raises(FileNotFoundError) as exc_info:
            Settings.from_json_file(missing_file)

        error_msg = str(exc_info.value)
        assert "Settings file not found" in error_msg
        assert str(missing_file) in error_msg
        assert "_thoth" in error_msg

    def test_json_decode_error(self, temp_vault: Path):
        """Test JSON decode error is raised with invalid syntax."""
        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text("{ invalid json }")

        with pytest.raises(json.JSONDecodeError):
            Settings.from_json_file(settings_file)

    def test_validation_error_for_invalid_types(self, temp_vault: Path):
        """Test ValidationError for invalid field types."""
        settings_data = {
            "llm": {
                "default": {
                    "temperature": "not-a-number"
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        with pytest.raises(ValidationError):
            Settings.from_json_file(settings_file)

    def test_unicode_in_json(self, temp_vault: Path):
        """Test loading settings with unicode characters."""
        settings_data = {
            "_comment": "Test with unicode: 中文 🚀 café"
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data, ensure_ascii=False))

        settings = Settings.from_json_file(settings_file)

        assert "中文" in settings.comment_
        assert "🚀" in settings.comment_


class TestExtraFieldsAllowed:
    """Test that extra fields are allowed in settings."""

    def test_extra_top_level_fields(self, temp_vault: Path):
        """Test extra fields at top level are allowed."""
        settings_data = {
            "version": "1.0.0",
            "customField": "custom-value",
            "anotherField": 123
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        # Should not raise error due to extra='allow'
        settings = Settings.from_json_file(settings_file)

        assert settings.version == "1.0.0"

    def test_extra_nested_fields_ignored(self, temp_vault: Path):
        """Test extra fields in nested models may be ignored or cause error."""
        settings_data = {
            "llm": {
                "default": {
                    "model": "test",
                    "unknownField": "should-be-ignored"
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        # Nested models don't have extra='allow', may raise error
        try:
            settings = Settings.from_json_file(settings_file)
            # If it succeeds, field should be ignored
            assert not hasattr(settings.llm.default, "unknownField")
        except ValidationError:
            # Expected if extra fields not allowed in nested models
            pass


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    def test_load_production_like_config(self, temp_vault: Path):
        """Test loading a production-like configuration."""
        from tests.fixtures.config_fixtures import get_full_settings_json

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(get_full_settings_json(), indent=2))

        settings = Settings.from_json_file(settings_file)

        # Verify all major sections are present
        assert settings.api_keys is not None
        assert settings.llm is not None
        assert settings.rag is not None
        assert settings.memory is not None
        assert settings.paths is not None
        assert settings.servers is not None
        assert settings.discovery is not None
        assert settings.citation is not None
        assert settings.performance is not None
        assert settings.logging is not None
        assert settings.environment is not None
        assert settings.postgres is not None
        assert settings.feature_flags is not None

    def test_migrate_from_old_format(self, temp_vault: Path):
        """Test loading settings with old field names still works."""
        settings_data = {
            "llm": {
                "default": {
                    # Mix old and new formats (both should work)
                    "model": "test-model",
                    "max_tokens": 5000,  # Snake case
                    "topP": 0.95  # Camel case
                }
            }
        }

        settings_file = temp_vault / "_thoth" / "settings.json"
        settings_file.write_text(json.dumps(settings_data))

        settings = Settings.from_json_file(settings_file)

        assert settings.llm.default.model == "test-model"
        assert settings.llm.default.max_tokens == 5000
        assert settings.llm.default.top_p == 0.95
