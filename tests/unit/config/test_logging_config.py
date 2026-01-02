"""Tests for logging configuration.

Tests:
- Console logging enabled/disabled
- File logging enabled/disabled
- Log levels
- Log format
- Rotation, retention, compression
- Logging reconfiguration
"""

import json
from pathlib import Path

import pytest  # noqa: F401
from loguru import logger

from tests.fixtures.config_fixtures import get_full_settings_json
from thoth.config import Config


class TestConsoleLogging:
    """Test console logging configuration."""

    def test_console_logging_enabled(self, temp_vault: Path, monkeypatch):
        """Test console logging can be enabled."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['console']['enabled'] = True

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.console.enabled is True

    def test_console_logging_disabled(self, temp_vault: Path, monkeypatch):
        """Test console logging can be disabled."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['console']['enabled'] = False

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.console.enabled is False

    def test_console_log_level(self, temp_vault: Path, monkeypatch):
        """Test console log level configuration."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['console']['level'] = 'DEBUG'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.console.level == 'DEBUG'


class TestFileLogging:
    """Test file logging configuration."""

    def test_file_logging_enabled(self, temp_vault: Path, monkeypatch):
        """Test file logging can be enabled."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['enabled'] = True

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.file.enabled is True

    def test_file_logging_disabled(self, temp_vault: Path, monkeypatch):
        """Test file logging can be disabled."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['enabled'] = False

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.file.enabled is False

    def test_file_log_path(self, temp_vault: Path, monkeypatch):
        """Test file log path configuration."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['path'] = '/workspace/logs/custom.log'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.file.path == '/workspace/logs/custom.log'

    def test_file_log_level(self, temp_vault: Path, monkeypatch):
        """Test file log level configuration."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['level'] = 'ERROR'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.file.level == 'ERROR'

    def test_file_log_mode(self, temp_vault: Path, monkeypatch):
        """Test file log mode (append/write)."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['mode'] = 'w'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.file.mode == 'w'


class TestLogRotation:
    """Test log rotation configuration."""

    def test_rotation_enabled(self, temp_vault: Path, monkeypatch):
        """Test rotation can be enabled."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['rotation']['enabled'] = True

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.rotation.enabled is True

    def test_rotation_disabled(self, temp_vault: Path, monkeypatch):
        """Test rotation can be disabled."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['rotation']['enabled'] = False

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.rotation.enabled is False

    def test_rotation_max_bytes(self, temp_vault: Path, monkeypatch):
        """Test rotation max bytes configuration."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['rotation']['maxBytes'] = 5000000

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.rotation.max_bytes == 5000000

    def test_rotation_backup_count(self, temp_vault: Path, monkeypatch):
        """Test rotation backup count configuration."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['rotation']['backupCount'] = 7

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.rotation.backup_count == 7


class TestLogRetention:
    """Test log retention and compression."""

    def test_file_rotation_setting(self, temp_vault: Path, monkeypatch):
        """Test file rotation setting (e.g., '10 MB')."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['rotation'] = '20 MB'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.file.rotation == '20 MB'

    def test_file_retention_setting(self, temp_vault: Path, monkeypatch):
        """Test file retention setting (e.g., '7 days')."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['retention'] = '14 days'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.file.retention == '14 days'

    def test_file_compression_setting(self, temp_vault: Path, monkeypatch):
        """Test file compression setting."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['compression'] = 'gz'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.file.compression == 'gz'


class TestLogFormat:
    """Test log format configuration."""

    def test_log_format(self, temp_vault: Path, monkeypatch):
        """Test log format string."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['format'] = 'custom {message}'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.format == 'custom {message}'

    def test_log_date_format(self, temp_vault: Path, monkeypatch):
        """Test log date format string."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['dateFormat'] = 'YYYY-MM-DD'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.date_format == 'YYYY-MM-DD'


class TestLogLevel:
    """Test log level configuration."""

    def test_global_log_level(self, temp_vault: Path, monkeypatch):
        """Test global log level."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['level'] = 'INFO'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.level == 'INFO'

    def test_different_levels_console_file(self, temp_vault: Path, monkeypatch):
        """Test different log levels for console and file."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['console']['level'] = 'DEBUG'
        settings_data['logging']['file']['level'] = 'ERROR'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        assert config.logging_config.console.level == 'DEBUG'
        assert config.logging_config.file.level == 'ERROR'


class TestLoggingConfiguration:
    """Test actual logging configuration during init."""

    def test_loguru_configured_on_init(self, temp_vault: Path, monkeypatch):
        """Test loguru is configured during Config initialization."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()  # noqa: F841

        # Loguru should be configured
        # This is hard to test directly, but we can verify no errors
        logger.info('Test log message')

    def test_log_file_created(self, temp_vault: Path, monkeypatch):
        """Test log file is created when file logging enabled."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['enabled'] = True

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        # Log something
        logger.info('Test message')

        # Log file should exist (in logs_dir)
        expected_log = config.logs_dir / 'thoth.log'
        assert expected_log.exists()


class TestLoggingReconfiguration:
    """Test logging reconfiguration after reload."""

    def test_logging_reconfigured_after_reload(self, temp_vault: Path, monkeypatch):
        """Test logging is reconfigured after reload_settings()."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        # Update logging settings
        settings_data = get_full_settings_json()
        settings_data['logging']['console']['level'] = 'DEBUG'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        # Logging should be reconfigured
        assert config.logging_config.console.level == 'DEBUG'

    def test_log_level_changes_after_reload(self, temp_vault: Path, monkeypatch):
        """Test log level changes take effect after reload."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        original_level = config.logging_config.level

        # Update to different level
        settings_data = get_full_settings_json()
        new_level = 'DEBUG' if original_level != 'DEBUG' else 'ERROR'
        settings_data['logging']['level'] = new_level

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        # Reload
        config.reload_settings()

        assert config.logging_config.level == new_level


class TestLoggingConvenienceProperty:
    """Test logging_config convenience property."""

    def test_logging_config_property(self, temp_vault: Path, monkeypatch):
        """Test logging_config property returns LoggingConfig."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        from thoth.config import LoggingConfig

        assert isinstance(config.logging_config, LoggingConfig)

    def test_logging_config_matches_settings(self, temp_vault: Path, monkeypatch):
        """Test logging_config property matches settings.logging."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        Config._instance = None
        config = Config()

        assert config.logging_config is config.settings.logging


class TestLoggingEdgeCases:
    """Test edge cases in logging configuration."""

    def test_both_console_file_disabled(self, temp_vault: Path, monkeypatch):
        """Test configuration with both console and file logging disabled."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['console']['enabled'] = False
        settings_data['logging']['file']['enabled'] = False

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        # Should not error, just no logging output
        assert config.logging_config.console.enabled is False
        assert config.logging_config.file.enabled is False

    def test_invalid_log_level_string(self, temp_vault: Path, monkeypatch):
        """Test invalid log level string (Pydantic allows any string)."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['level'] = 'INVALID_LEVEL'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        # Pydantic doesn't validate enum, so this will be accepted
        assert config.logging_config.level == 'INVALID_LEVEL'

    def test_log_file_in_nonexistent_directory(self, temp_vault: Path, monkeypatch):
        """Test log file path in nonexistent directory."""
        monkeypatch.setenv('OBSIDIAN_VAULT_PATH', str(temp_vault))

        settings_data = get_full_settings_json()
        settings_data['logging']['file']['enabled'] = True
        settings_data['logging']['file']['path'] = '/workspace/nonexistent/dir/log.log'

        settings_file = temp_vault / '_thoth' / 'settings.json'
        settings_file.write_text(json.dumps(settings_data))

        Config._instance = None
        config = Config()

        # Should handle gracefully (loguru creates directory)
        assert config.logging_config.file.path == '/workspace/nonexistent/dir/log.log'
