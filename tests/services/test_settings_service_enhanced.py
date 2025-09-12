"""
Tests for enhanced SettingsService features including vault detection and environment
overrides.
"""

import json
import os
from unittest.mock import patch

import pytest

from thoth.services.settings_service import SettingsService


class TestVaultDetection:
    """Test Obsidian vault detection functionality."""

    def test_detect_obsidian_vault_current_dir(self, tmp_path):
        """Test vault detection in current directory."""
        # Create .obsidian directory in temp path
        obsidian_dir = tmp_path / '.obsidian'
        obsidian_dir.mkdir()

        with patch('pathlib.Path.cwd', return_value=tmp_path):
            service = SettingsService()
            vault_path = service._detect_obsidian_vault()
            assert vault_path == tmp_path

    def test_detect_obsidian_vault_parent_dir(self, tmp_path):
        """Test vault detection in parent directory."""
        # Create nested structure
        vault_root = tmp_path / 'vault'
        vault_root.mkdir()
        (vault_root / '.obsidian').mkdir()

        nested_dir = vault_root / 'nested' / 'deep'
        nested_dir.mkdir(parents=True)

        with patch('pathlib.Path.cwd', return_value=nested_dir):
            service = SettingsService()
            vault_path = service._detect_obsidian_vault()
            assert vault_path == vault_root

    def test_no_vault_detected(self, tmp_path):
        """Test when no vault is detected."""
        with patch('pathlib.Path.cwd', return_value=tmp_path):
            service = SettingsService()
            vault_path = service._detect_obsidian_vault()
            assert vault_path is None

    def test_vault_aware_settings_path(self, tmp_path):
        """Test that vault detection affects settings path."""
        # Create vault structure
        vault_root = tmp_path / 'vault'
        vault_root.mkdir()
        (vault_root / '.obsidian').mkdir()

        with patch('pathlib.Path.cwd', return_value=vault_root):
            service = SettingsService()
            expected_path = vault_root / '.thoth.settings.json'
            assert service.settings_path == expected_path


class TestEnvironmentOverrides:
    """Test environment variable override functionality."""

    def test_env_override_api_keys(self, tmp_path):
        """Test environment override for API keys."""
        # Create test settings file
        settings_file = tmp_path / '.thoth.settings.json'
        test_settings = {
            'version': '1.0.0',
            'lastModified': '2024-01-01T00:00:00Z',
            'apiKeys': {'mistralKey': 'original_key', 'openaiKey': 'original_openai'},
        }

        with open(settings_file, 'w') as f:
            json.dump(test_settings, f)

        # Set environment variables
        with patch.dict(
            os.environ,
            {
                'THOTH_MISTRAL_API_KEY': 'env_mistral_key',
                'THOTH_OPENAI_API_KEY': 'env_openai_key',
            },
        ):
            service = SettingsService(settings_path=settings_file)
            loaded_settings = service.load_settings()

            # Verify environment overrides were applied
            assert loaded_settings['apiKeys']['mistralKey'] == 'env_mistral_key'
            assert loaded_settings['apiKeys']['openaiKey'] == 'env_openai_key'

    def test_env_override_server_config(self, tmp_path):
        """Test environment override for server configurations."""
        settings_file = tmp_path / '.thoth.settings.json'
        test_settings = {
            'version': '1.0.0',
            'lastModified': '2024-01-01T00:00:00Z',
            'servers': {'api': {'host': 'localhost', 'port': 8000}},
        }

        with open(settings_file, 'w') as f:
            json.dump(test_settings, f)

        with patch.dict(
            os.environ, {'THOTH_API_HOST': '0.0.0.0', 'THOTH_API_PORT': '9000'}
        ):
            service = SettingsService(settings_path=settings_file)
            loaded_settings = service.load_settings()

            assert loaded_settings['servers']['api']['host'] == '0.0.0.0'
            assert (
                loaded_settings['servers']['api']['port'] == 9000
            )  # Should be converted to int

    def test_env_override_type_conversion(self, tmp_path):
        """Test environment variable type conversion."""
        settings_file = tmp_path / '.thoth.settings.json'
        test_settings = {
            'version': '1.0.0',
            'lastModified': '2024-01-01T00:00:00Z',
            'servers': {'mcp': {'enabled': False, 'port': 8001}},
        }

        with open(settings_file, 'w') as f:
            json.dump(test_settings, f)

        with patch.dict(
            os.environ,
            {
                'THOTH_MCP_PORT': '9001',  # Should convert to int
                'THOTH_MCP_ENABLED': 'true',  # Should convert to bool
            },
        ):
            service = SettingsService(settings_path=settings_file)
            loaded_settings = service.load_settings()

            # Test type conversions
            assert loaded_settings['servers']['mcp']['port'] == 9001
            assert isinstance(loaded_settings['servers']['mcp']['port'], int)

            # Note: We're not testing boolean conversion here since 'servers.mcp.enabled'  #noqa: W505
            # is not in our override map, but the conversion function should work

    def test_convert_env_value_types(self):
        """Test environment value type conversion function."""
        service = SettingsService()

        # Test boolean conversion
        assert service._convert_env_value('true') is True
        assert service._convert_env_value('false') is False
        assert service._convert_env_value('TRUE') is True
        assert service._convert_env_value('FALSE') is False

        # Test integer conversion
        assert service._convert_env_value('123') == 123
        assert isinstance(service._convert_env_value('123'), int)

        # Test float conversion
        assert service._convert_env_value('123.45') == 123.45
        assert isinstance(service._convert_env_value('123.45'), float)

        # Test string fallback
        assert service._convert_env_value('not_a_number') == 'not_a_number'
        assert isinstance(service._convert_env_value('not_a_number'), str)


class TestSettingsFilePathDetermination:
    """Test settings file path determination logic."""

    def test_env_var_override_path(self, tmp_path):
        """Test THOTH_SETTINGS_FILE environment variable override."""
        custom_settings_path = tmp_path / 'custom_settings.json'

        with patch.dict(os.environ, {'THOTH_SETTINGS_FILE': str(custom_settings_path)}):
            service = SettingsService()
            assert service.settings_path == custom_settings_path

    def test_provided_path_priority(self, tmp_path):
        """Test that provided path takes priority over vault detection."""
        provided_path = tmp_path / 'provided.json'

        # Create vault structure
        vault_root = tmp_path / 'vault'
        vault_root.mkdir()
        (vault_root / '.obsidian').mkdir()

        with patch('pathlib.Path.cwd', return_value=vault_root):
            service = SettingsService(settings_path=provided_path)
            assert service.settings_path == provided_path

    def test_vault_path_over_default(self, tmp_path):
        """Test vault path takes priority over default."""
        vault_root = tmp_path / 'vault'
        vault_root.mkdir()
        (vault_root / '.obsidian').mkdir()

        with patch('pathlib.Path.cwd', return_value=vault_root):
            service = SettingsService()
            expected_path = vault_root / '.thoth.settings.json'
            assert service.settings_path == expected_path


class TestEnhancedBackupAndAtomic:
    """Test enhanced backup and atomic write operations."""

    def test_enhanced_backup_creation(self, tmp_path):
        """Test enhanced backup creation with validation."""
        settings_file = tmp_path / '.thoth.settings.json'
        test_settings = {
            'version': '1.0.0',
            'lastModified': '2024-01-01T00:00:00Z',
            'test': 'data',
        }

        with open(settings_file, 'w') as f:
            json.dump(test_settings, f)

        service = SettingsService(settings_path=settings_file)
        service.backup_dir = tmp_path / 'backups'

        # Create backup
        backup_path = service._create_backup()

        # Verify backup exists and is valid
        assert backup_path.exists()
        assert service.backup_dir.exists()

        # Verify backup content
        with open(backup_path) as f:
            backup_content = json.load(f)
        assert backup_content == test_settings

    def test_backup_validation_failure(self, tmp_path):
        """Test backup creation fails when source is invalid."""
        settings_file = tmp_path / '.thoth.settings.json'

        # Create invalid JSON file
        with open(settings_file, 'w') as f:
            f.write('invalid json content')

        service = SettingsService(settings_path=settings_file)
        service.backup_dir = tmp_path / 'backups'

        # Backup should fail due to validation
        with pytest.raises(ValueError, match='Created backup file is not valid JSON'):
            service._create_backup()

    def test_atomic_write_operations(self, tmp_path):
        """Test atomic write operations."""
        settings_file = tmp_path / '.thoth.settings.json'
        service = SettingsService(settings_path=settings_file)

        test_settings = {
            'version': '1.0.0',
            'lastModified': '2024-01-01T00:00:00Z',
            'test': 'atomic_write',
        }

        # Test atomic write
        temp_file = tmp_path / 'temp.json'
        service._atomic_write(temp_file, test_settings)

        # Verify file was written correctly
        assert temp_file.exists()
        with open(temp_file) as f:
            written_content = json.load(f)
        assert written_content == test_settings

    def test_rollback_functionality(self, tmp_path):
        """Test rollback from backup functionality."""
        settings_file = tmp_path / '.thoth.settings.json'
        backup_file = tmp_path / 'backup.json'

        # Create backup with known content
        backup_content = {
            'version': '1.0.0',
            'lastModified': '2024-01-01T00:00:00Z',
            'test': 'backup_content',
        }
        with open(backup_file, 'w') as f:
            json.dump(backup_content, f)

        service = SettingsService(settings_path=settings_file)

        # Test rollback
        success = service._rollback_from_backup(backup_file)
        assert success

        # Verify settings file was restored
        assert settings_file.exists()
        with open(settings_file) as f:
            restored_content = json.load(f)
        assert restored_content == backup_content

    def test_save_with_rollback_on_failure(self, tmp_path):
        """Test that save operations rollback on failure."""
        settings_file = tmp_path / '.thoth.settings.json'

        # Create initial valid settings
        initial_settings = {
            'version': '1.0.0',
            'lastModified': '2024-01-01T00:00:00Z',
            'test': 'initial',
        }
        with open(settings_file, 'w') as f:
            json.dump(initial_settings, f)

        service = SettingsService(settings_path=settings_file)

        # Mock _atomic_write to fail
        with patch.object(
            service, '_atomic_write', side_effect=Exception('Write failed')
        ):
            # Try to save invalid settings (should fail and rollback)
            invalid_settings = {
                'version': '1.0.0',
                'lastModified': '2024-01-01T00:00:00Z',
                'test': 'invalid',
            }

            result = service.save_settings(invalid_settings)
            assert result is False

            # Verify original file still exists and has original content
            assert settings_file.exists()
            with open(settings_file) as f:
                current_content = json.load(f)
            assert current_content == initial_settings


class TestBackwardCompatibility:
    """Test backward compatibility with existing functionality."""

    def test_existing_api_unchanged(self, tmp_path):
        """Test that existing API methods work unchanged."""
        settings_file = tmp_path / '.thoth.settings.json'
        test_settings = {
            'version': '1.0.0',
            'lastModified': '2024-01-01T00:00:00Z',
            'llm': {'default': {'model': 'test-model', 'temperature': 0.7}},
        }

        with open(settings_file, 'w') as f:
            json.dump(test_settings, f)

        service = SettingsService(settings_path=settings_file)

        # Test existing methods work
        loaded = service.load_settings()
        assert loaded['llm']['default']['model'] == 'test-model'

        # Test get_setting
        model = service.get_setting('llm.default.model')
        assert model == 'test-model'

        # Test update_setting
        success = service.update_setting('llm.default.temperature', 0.8)
        assert success

        updated = service.get_setting('llm.default.temperature')
        assert updated == 0.8

    def test_old_constructor_signature(self, tmp_path):
        """Test that old constructor signature still works."""
        settings_file = tmp_path / '.thoth.settings.json'

        # Old style constructor call should still work
        service = SettingsService(settings_path=settings_file)
        assert service.settings_path == settings_file

        # Default constructor should still work
        service2 = SettingsService()
        assert service2.settings_path is not None


if __name__ == '__main__':
    pytest.main([__file__])
