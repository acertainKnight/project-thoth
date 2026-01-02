"""Tests for path resolution in configuration.

Tests all path resolution scenarios:
- Vault-relative paths
- Absolute Docker paths (/workspace, /thoth/notes)
- Relative paths
- Path creation (mkdir -p)
- Special cases and edge cases
"""

from pathlib import Path  # noqa: I001
from unittest.mock import patch  # noqa: F401

import pytest  # noqa: F401

from tests.fixtures.config_fixtures import (
    get_full_settings_json,
    get_minimal_settings_json,
)  # noqa: F401
from thoth.config import Config


class TestVaultRelativePaths:
    """Test paths relative to vault root."""

    def test_relative_paths_resolved_to_vault(self, temp_vault: Path, monkeypatch):
        """Test relative paths are resolved relative to vault."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        # Reset singleton
        Config._instance = None

        config = Config()

        # Relative paths should be under vault_root
        assert config.pdf_dir.is_relative_to(temp_vault)
        assert config.markdown_dir.is_relative_to(temp_vault)
        assert config.output_dir.is_relative_to(temp_vault)

    def test_paths_are_absolute(self, temp_vault: Path, monkeypatch):
        """Test all resolved paths are absolute."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        assert config.pdf_dir.is_absolute()
        assert config.markdown_dir.is_absolute()
        assert config.notes_dir.is_absolute()
        assert config.workspace_dir.is_absolute()
        assert config.logs_dir.is_absolute()

    def test_nested_relative_paths(self, temp_vault: Path, monkeypatch):
        """Test nested relative paths are resolved correctly."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # data/pdf should resolve to vault_root/data/pdf
        expected_pdf = temp_vault / 'data' / 'pdf'
        assert config.pdf_dir == expected_pdf.resolve()


class TestDockerAbsolutePaths:
    """Test special handling of Docker absolute paths."""

    def test_workspace_maps_to_vault_root(self, temp_vault: Path, monkeypatch):
        """Test /workspace maps to vault root."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # /workspace should map to vault_root
        assert config.workspace_dir == temp_vault.resolve()

    def test_thoth_notes_maps_to_vault_notes(self, temp_vault: Path, monkeypatch):
        """Test /thoth/notes maps to vault_root/notes."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # /thoth/notes should map to vault_root/notes
        expected_notes = temp_vault / 'notes'
        assert config.notes_dir == expected_notes.resolve()

    def test_workspace_logs_maps_to_vault_logs(self, temp_vault: Path, monkeypatch):
        """Test /workspace/logs maps to vault_root/logs."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # logs path should be under vault
        expected_logs = temp_vault / 'logs'
        assert config.logs_dir == expected_logs.resolve()

    def test_thoth_prefix_stripped(self, temp_vault: Path, monkeypatch):
        """Test /thoth/ prefix is properly stripped."""
        import json

        # Create custom settings with /thoth/ paths
        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {
            'workspace': '/workspace',
            'notes': '/thoth/notes',
            'pdf': '/thoth/data/pdf',
            'markdown': '/thoth/data/markdown',
        }

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Should strip /thoth/ and resolve to vault
        assert config.notes_dir == (temp_vault / 'notes').resolve()
        assert config.pdf_dir == (temp_vault / 'data' / 'pdf').resolve()


class TestAbsolutePathsOutsideVault:
    """Test handling of absolute paths outside vault."""

    def test_absolute_path_outside_vault_warning(
        self, temp_vault: Path, monkeypatch, caplog
    ):
        """Test warning logged for absolute path outside vault."""
        import json

        outside_path = '/absolute/outside/vault'

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {'workspace': '/workspace', 'pdf': outside_path}

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()  # noqa: F841

        # Should log warning
        assert 'Absolute path outside vault' in caplog.text

    def test_absolute_path_used_as_is(self, temp_vault: Path, monkeypatch):
        """Test absolute path outside vault is used as-is."""
        import json

        outside_path = '/tmp/outside_vault'

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {'workspace': '/workspace', 'pdf': outside_path}

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Should use path as-is
        assert str(config.pdf_dir) == Path(outside_path).resolve().as_posix()


class TestPathCreation:
    """Test automatic directory creation."""

    def test_directories_created_on_init(self, temp_vault: Path, monkeypatch):
        """Test all configured directories are created."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # All directories should exist
        assert config.workspace_dir.exists()
        assert config.pdf_dir.exists()
        assert config.markdown_dir.exists()
        assert config.notes_dir.exists()
        assert config.logs_dir.exists()
        assert config.discovery_sources_dir.exists()
        assert config.discovery_results_dir.exists()

    def test_nested_directories_created(self, temp_vault: Path, monkeypatch):
        """Test nested directories are created with parents=True."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {
            'workspace': '/workspace',
            'pdf': 'data/nested/deep/pdf',
        }

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Nested path should exist
        expected_path = temp_vault / 'data' / 'nested' / 'deep' / 'pdf'
        assert expected_path.exists()
        assert config.pdf_dir == expected_path.resolve()

    def test_existing_directories_not_error(self, temp_vault: Path, monkeypatch):
        """Test existing directories don't cause errors."""
        # Pre-create some directories
        (temp_vault / 'data' / 'pdf').mkdir(parents=True)
        (temp_vault / 'logs').mkdir(parents=True)

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Should not error
        assert config.pdf_dir.exists()
        assert config.logs_dir.exists()


class TestRAGVectorDBPath:
    """Test special handling of RAG vector_db_path."""

    def test_rag_vector_db_path_resolved(self, temp_vault: Path, monkeypatch):
        """Test RAG vector_db_path is resolved to absolute."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # vector_db_path should be absolute string
        vector_path = Path(config.settings.rag.vector_db_path)
        assert vector_path.is_absolute()
        assert vector_path.is_relative_to(temp_vault)

    def test_rag_vector_db_relative_to_vault(self, temp_vault: Path, monkeypatch):
        """Test relative RAG vector_db_path resolves to vault."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['rag'] = {'vectorDbPath': 'custom/vector_db'}

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        expected_path = temp_vault / 'custom' / 'vector_db'
        assert Path(config.settings.rag.vector_db_path) == expected_path.resolve()


class TestGraphStoragePath:
    """Test graph storage path resolution."""

    def test_graph_storage_path_resolved(self, temp_vault: Path, monkeypatch):
        """Test graph storage path is resolved correctly."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        assert config.graph_storage_path.is_absolute()
        assert config.graph_storage_path.is_relative_to(temp_vault)

    def test_graph_storage_custom_path(self, temp_vault: Path, monkeypatch):
        """Test custom graph storage path."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {
            'workspace': '/workspace',
            'graphStorage': 'custom/citations.graphml',
        }

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        expected = temp_vault / 'custom' / 'citations.graphml'
        assert config.graph_storage_path == expected.resolve()


class TestDiscoveryPaths:
    """Test discovery-specific paths."""

    def test_discovery_paths_resolved(self, temp_vault: Path, monkeypatch):
        """Test all discovery paths are resolved."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        assert config.discovery_sources_dir.is_absolute()
        assert config.discovery_results_dir.is_absolute()
        assert config.discovery_chrome_configs_dir.is_absolute()

        assert config.discovery_sources_dir.is_relative_to(temp_vault)
        assert config.discovery_results_dir.is_relative_to(temp_vault)
        assert config.discovery_chrome_configs_dir.is_relative_to(temp_vault)

    def test_discovery_paths_created(self, temp_vault: Path, monkeypatch):
        """Test discovery directories are created."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        assert config.discovery_sources_dir.exists()
        assert config.discovery_results_dir.exists()
        assert config.discovery_chrome_configs_dir.exists()


class TestPathResolutionEdgeCases:
    """Test edge cases in path resolution."""

    def test_empty_path_string(self, temp_vault: Path, monkeypatch):
        """Test empty path string handling."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {
            'workspace': '',  # Empty path
            'pdf': 'data/pdf',
        }

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Empty path should resolve to vault root
        assert config.workspace_dir == temp_vault.resolve()

    def test_dot_path(self, temp_vault: Path, monkeypatch):
        """Test . path resolves to vault root."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {'workspace': '.', 'pdf': 'data/pdf'}

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        assert config.workspace_dir == temp_vault.resolve()

    def test_double_dot_path(self, temp_vault: Path, monkeypatch):
        """Test .. in path is resolved correctly."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {'workspace': '/workspace', 'pdf': 'data/../other/pdf'}

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Should resolve to vault_root/other/pdf
        expected = temp_vault / 'other' / 'pdf'
        assert config.pdf_dir == expected.resolve()

    def test_trailing_slash_handled(self, temp_vault: Path, monkeypatch):
        """Test trailing slash in path is handled."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {'workspace': '/workspace', 'pdf': 'data/pdf/'}

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Trailing slash should be handled
        expected = temp_vault / 'data' / 'pdf'
        assert config.pdf_dir == expected.resolve()


class TestPathResolutionCaseSensitivity:
    """Test case sensitivity in path resolution."""

    def test_workspace_lowercase(self, temp_vault: Path, monkeypatch):
        """Test /workspace in lowercase."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Default /workspace should map to vault
        assert config.workspace_dir == temp_vault.resolve()

    def test_thoth_lowercase(self, temp_vault: Path, monkeypatch):
        """Test /thoth/ prefix in lowercase."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {'workspace': '/workspace', 'notes': '/thoth/notes'}

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        assert config.notes_dir == (temp_vault / 'notes').resolve()


class TestPathResolutionLogging:
    """Test logging during path resolution."""

    def test_directory_creation_logged(self, temp_vault: Path, monkeypatch, caplog):
        """Test directory creation is logged."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()  # noqa: F841

        # Should log directory ensured messages
        assert 'Ensured directory exists' in caplog.text

    def test_absolute_path_warning_logged(self, temp_vault: Path, monkeypatch, caplog):
        """Test warning for absolute paths outside vault."""
        import json

        settings_data = get_minimal_settings_json()
        settings_data['paths'] = {
            'workspace': '/workspace',
            'pdf': '/absolute/outside/path',
        }

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()  # noqa: F841

        assert 'Absolute path outside vault' in caplog.text
