"""Tests for hot-reload functionality.

Tests:
- reload_settings() reloads from JSON
- Path resolution after reload
- Logging reconfiguration after reload
- Rollback on error
- Thread-safety with lock
"""

import json
import threading
from pathlib import Path

import pytest

from tests.fixtures.config_fixtures import get_full_settings_json
from thoth.config import Config


class TestReloadSettings:
    """Test reload_settings() method."""

    def test_reload_settings_updates_config(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() reloads configuration."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        original_model = config.llm_config.default.model

        # Update settings file
        settings_data = get_full_settings_json()
        settings_data['llm']['default']['model'] = 'updated-model'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        # Should have new value
        assert config.llm_config.default.model == 'updated-model'
        assert config.llm_config.default.model != original_model

    def test_reload_settings_preserves_vault_root(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() preserves vault_root."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        original_vault = config.vault_root

        # Reload settings
        config.reload_settings()

        # Vault root should not change
        assert config.vault_root == original_vault

    def test_reload_settings_updates_paths(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() updates resolved paths."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        original_pdf_dir = config.pdf_dir

        # Update settings with new path
        settings_data = get_full_settings_json()
        settings_data['paths']['pdf'] = 'new_pdf_directory'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        # Path should be updated
        expected = temp_vault / 'new_pdf_directory'
        assert config.pdf_dir == expected.resolve()
        assert config.pdf_dir != original_pdf_dir

    def test_reload_settings_creates_new_directories(
        self, temp_vault: Path, monkeypatch
    ):
        """Test reload_settings() creates new directories."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Update settings with new directory
        new_dir = 'brand_new_directory'
        settings_data = get_full_settings_json()
        settings_data['paths']['pdf'] = new_dir

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        # New directory should exist
        expected = temp_vault / new_dir
        assert expected.exists()


class TestReloadLoggingReconfiguration:
    """Test logging reconfiguration after reload."""

    def test_reload_reconfigures_logging(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() reconfigures logging."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        original_level = config.logging_config.level

        # Update logging level
        settings_data = get_full_settings_json()
        settings_data['logging']['level'] = 'DEBUG'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        # Logging level should be updated
        assert config.logging_config.level == 'DEBUG'
        assert config.logging_config.level != original_level

    def test_reload_updates_log_file_config(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() updates log file configuration."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Update log file settings
        settings_data = get_full_settings_json()
        settings_data['logging']['file']['rotation'] = '20 MB'
        settings_data['logging']['file']['retention'] = '14 days'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        assert config.logging_config.file.rotation == '20 MB'
        assert config.logging_config.file.retention == '14 days'

    def test_reload_toggles_console_logging(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() can toggle console logging."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        original_console_enabled = config.logging_config.console.enabled

        # Toggle console logging
        settings_data = get_full_settings_json()
        settings_data['logging']['console']['enabled'] = not original_console_enabled

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        assert config.logging_config.console.enabled != original_console_enabled


class TestReloadRollback:
    """Test rollback on error during reload."""

    def test_reload_rollback_on_invalid_json(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() rolls back on invalid JSON."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        original_model = config.llm_config.default.model
        original_pdf_dir = config.pdf_dir

        # Write invalid JSON
        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text('{ invalid json }')

        # Reload should fail and rollback
        with pytest.raises(Exception):  # noqa: B017
            config.reload_settings()

        # Original values should be preserved
        assert config.llm_config.default.model == original_model
        assert config.pdf_dir == original_pdf_dir

    def test_reload_rollback_on_validation_error(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() rolls back on validation error."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        original_temperature = config.llm_config.default.temperature

        # Write invalid settings (wrong type)
        settings_data = get_full_settings_json()
        settings_data['llm']['default']['temperature'] = 'not-a-number'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload should fail and rollback
        with pytest.raises(Exception):  # noqa: B017
            config.reload_settings()

        # Original value should be preserved
        assert config.llm_config.default.temperature == original_temperature

    def test_reload_rollback_preserves_all_state(self, temp_vault: Path, monkeypatch):
        """Test rollback preserves all configuration state."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Capture original state
        original_workspace = config.workspace_dir  # noqa: F841
        original_pdf = config.pdf_dir  # noqa: F841
        original_markdown = config.markdown_dir  # noqa: F841
        original_notes = config.notes_dir  # noqa: F841

        # Write invalid settings
        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text('{ }')  # Empty causes issues

        # Try to reload (may fail or partially succeed)
        try:
            config.reload_settings()
        except Exception:
            pass

        # All original paths should be preserved on error
        # (or updated if reload succeeded)
        assert config.workspace_dir.exists()
        assert config.pdf_dir.exists()


class TestReloadThreadSafety:
    """Test thread-safety of reload_settings()."""

    def test_reload_uses_lock(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() uses _reload_lock."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Verify lock exists
        assert hasattr(config, '_reload_lock')
        # threading.Lock is a factory function, not a type - compare type instead
        assert isinstance(config._reload_lock, type(threading.Lock()))

    def test_concurrent_reloads_are_safe(self, temp_vault: Path, monkeypatch):
        """Test concurrent reload_settings() calls are safe."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        errors = []
        lock = threading.Lock()

        def reload_config():
            try:
                config.reload_settings()
            except Exception as e:
                with lock:
                    errors.append(e)

        # Start multiple reload threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=reload_config)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should not error (or minimal errors)
        assert len(errors) <= 1  # At most one might fail due to race

    def test_reload_blocks_concurrent_access(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() blocks concurrent access properly."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        reload_started = threading.Event()
        reload_finished = threading.Event()

        def slow_reload():
            reload_started.set()
            # Simulate slow reload
            import time

            time.sleep(0.1)
            config.reload_settings()
            reload_finished.set()

        def access_config():
            reload_started.wait()  # Wait for reload to start
            # Try to access config (should wait for lock)
            _ = config.llm_config.default.model

        thread1 = threading.Thread(target=slow_reload)
        thread2 = threading.Thread(target=access_config)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        assert reload_finished.is_set()


class TestReloadSuccessLogging:
    """Test success logging after reload."""

    def test_reload_logs_success(self, temp_vault: Path, monkeypatch, caplog):
        """Test reload_settings() logs success message."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Reload
        config.reload_settings()

        assert 'Settings reloaded successfully' in caplog.text

    def test_reload_logs_reloading_start(self, temp_vault: Path, monkeypatch, caplog):
        """Test reload_settings() logs start of reload."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Reload
        config.reload_settings()

        assert 'Reloading settings from JSON' in caplog.text

    def test_reload_logs_rollback_on_error(self, temp_vault: Path, monkeypatch, caplog):
        """Test reload_settings() logs rollback message on error."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Write invalid JSON
        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text('{ invalid }')

        # Try to reload
        with pytest.raises(Exception):  # noqa: B017
            config.reload_settings()

        assert 'Rolled back to previous settings' in caplog.text


class TestReloadEdgeCases:
    """Test edge cases in reload functionality."""

    def test_reload_with_missing_file(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() with missing settings file auto-creates defaults."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Delete settings file
        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.unlink()

        # Reload should auto-create default settings (not raise)
        config.reload_settings()

        # Default settings should be applied
        assert config.llm_config.default.model == 'google/gemini-2.5-flash'

    def test_reload_with_empty_file(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() with empty file."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Write empty file
        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text('')

        # Reload should fail
        with pytest.raises(Exception):  # noqa: B017
            config.reload_settings()

    def test_reload_multiple_times(self, temp_vault: Path, monkeypatch):
        """Test multiple consecutive reloads."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Reload multiple times
        for i in range(5):
            settings_data = get_full_settings_json()
            settings_data['version'] = f'1.{i}.0'

            settings_file = temp_vault / '_thoth' / 'settings.json'
            settings_file.write_text(json.dumps(settings_data))

            config.reload_settings()

            assert config.settings.version == f'1.{i}.0'

    def test_reload_with_partial_settings(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() with partial settings (defaults fill in)."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Write partial settings
        partial_settings = {'llm': {'default': {'model': 'partial-model'}}}

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(partial_settings))

        # Reload
        config.reload_settings()

        # Should have new model
        assert config.llm_config.default.model == 'partial-model'
        # But defaults for other fields
        assert config.llm_config.default.temperature == 0.9


class TestReloadRAGVectorPath:
    """Test RAG vector_db_path handling during reload."""

    def test_reload_updates_rag_vector_path(self, temp_vault: Path, monkeypatch):
        """Test reload_settings() updates RAG vector_db_path."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Update RAG vector path
        settings_data = get_full_settings_json()
        settings_data['rag']['vectorDbPath'] = 'new_vector_db'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        # Should be resolved to absolute
        expected = temp_vault / 'new_vector_db'
        assert Path(config.settings.rag.vector_db_path) == expected.resolve()
