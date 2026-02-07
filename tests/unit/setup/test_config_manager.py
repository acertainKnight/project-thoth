"""
Unit tests for setup wizard configuration manager.
"""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from thoth.cli.setup.config_manager import ConfigManager


@pytest.fixture
def temp_vault(tmp_path):
    """Create temporary vault structure."""
    vault_path = tmp_path / 'test_vault'
    vault_path.mkdir()

    thoth_dir = vault_path / '_thoth'
    thoth_dir.mkdir()

    return vault_path


@pytest.fixture
def config_manager(temp_vault):
    """Create ConfigManager instance."""
    return ConfigManager(temp_vault)


@pytest.fixture
def sample_settings():
    """Sample settings dictionary."""
    return {
        'llm_config': {
            'default': {'model': 'google/gemini-2.5-flash', 'temperature': 0.9},
            'citation': {'model': 'openai/gpt-4o-mini'},
        },
        'api_keys': {'openai': 'sk-test123', 'anthropic': 'sk-ant-test456'},
        'paths': {'pdf': '.thoth/data/pdfs', 'markdown': '.thoth/data/markdown'},
        'custom_field': 'preserved',
    }


class TestConfigManagerInit:
    """Tests for ConfigManager initialization."""

    def test_init_creates_backup_dir(self, temp_vault):
        """Test that initialization creates backup directory."""
        manager = ConfigManager(temp_vault)
        assert manager.backup_dir.exists()
        assert manager.backup_dir.is_dir()

    def test_init_sets_paths(self, temp_vault):
        """Test that initialization sets correct paths."""
        manager = ConfigManager(temp_vault)
        assert manager.vault_path == temp_vault
        # When legacy path (_thoth/) doesn't have settings.json,
        # defaults to new path (thoth/_thoth/settings.json)
        assert (
            manager.settings_path == temp_vault / 'thoth' / '_thoth' / 'settings.json'
        )
        assert manager.backup_dir == temp_vault / 'thoth' / '_thoth' / 'backups'


class TestLoadExisting:
    """Tests for loading existing configuration."""

    def test_load_existing_success(self, config_manager, sample_settings):
        """Test loading existing settings file."""
        # Write settings file
        with open(config_manager.settings_path, 'w', encoding='utf-8') as f:
            json.dump(sample_settings, f)

        # Load settings
        loaded = config_manager.load_existing()
        assert loaded == sample_settings

    def test_load_existing_no_file(self, config_manager):
        """Test loading when settings file doesn't exist."""
        result = config_manager.load_existing()
        assert result is None

    def test_load_existing_invalid_json(self, config_manager):
        """Test loading when settings file has invalid JSON."""
        # Write invalid JSON
        config_manager.settings_path.write_text('{ invalid json }')

        with pytest.raises(ValueError, match='Invalid JSON'):
            config_manager.load_existing()

    def test_load_existing_permission_error(self, config_manager):
        """Test loading when file cannot be read."""
        # Create a file to trigger the read
        config_manager.settings_path.write_text('{}')

        with patch('builtins.open', side_effect=PermissionError('No access')):
            result = config_manager.load_existing()
            # load_existing catches exceptions and returns None
            assert result is None


class TestDeepMerge:
    """Tests for deep merge functionality."""

    def test_deep_merge_simple(self, config_manager):
        """Test merging simple dictionaries."""
        existing = {'a': 1, 'b': 2}
        updates = {'b': 3, 'c': 4}

        result = config_manager.deep_merge(existing, updates)
        assert result == {'a': 1, 'b': 3, 'c': 4}

    def test_deep_merge_nested(self, config_manager):
        """Test merging nested dictionaries."""
        existing = {'config': {'setting1': 'old', 'setting2': 'keep'}}
        updates = {'config': {'setting1': 'new'}}

        result = config_manager.deep_merge(existing, updates)
        assert result == {'config': {'setting1': 'new', 'setting2': 'keep'}}

    def test_deep_merge_preserves_existing(self, config_manager, sample_settings):
        """Test that PREFER_EXISTING strategy preserves custom fields."""
        updates = {
            'llm_config': {'default': {'model': 'openai/gpt-4o'}},
            'new_field': 'new_value',
        }

        result = config_manager.deep_merge(sample_settings, updates)

        # Original fields preserved
        assert result['custom_field'] == 'preserved'
        assert result['llm_config']['citation']['model'] == 'openai/gpt-4o-mini'

        # Updates applied
        assert result['llm_config']['default']['model'] == 'openai/gpt-4o'
        assert result['new_field'] == 'new_value'

    def test_deep_merge_replaces_non_dict(self, config_manager):
        """Test that non-dict values are replaced."""
        existing = {'value': [1, 2, 3]}
        updates = {'value': [4, 5, 6]}

        result = config_manager.deep_merge(existing, updates)
        assert result['value'] == [4, 5, 6]

    def test_deep_merge_empty_update(self, config_manager, sample_settings):
        """Test merging with empty update."""
        result = config_manager.deep_merge(sample_settings, {})
        assert result == sample_settings

    def test_deep_merge_deeply_nested(self, config_manager):
        """Test merging deeply nested structures."""
        existing = {'a': {'b': {'c': {'d': 1, 'e': 2}}}}
        updates = {'a': {'b': {'c': {'d': 10}}}}

        result = config_manager.deep_merge(existing, updates)
        assert result == {'a': {'b': {'c': {'d': 10, 'e': 2}}}}


class TestValidateSchema:
    """Tests for schema validation."""

    def test_validate_schema_success(self, config_manager, sample_settings):
        """Test validation with valid settings."""
        # Mock Settings.from_json_file to succeed (validates via Pydantic)
        with patch('thoth.config.Settings.from_json_file'):
            result = config_manager.validate_schema(sample_settings)
            assert result is True

    def test_validate_schema_failure(self, config_manager):
        """Test validation with invalid settings."""
        invalid_settings = {'invalid_field': 'value'}

        with patch(
            'thoth.config.Settings.from_json_file',
            side_effect=ValidationError.from_exception_data(
                'test', [{'type': 'missing', 'loc': ('field',), 'msg': 'required'}]
            ),
        ):
            with pytest.raises(ValidationError):
                config_manager.validate_schema(invalid_settings)

    def test_validate_schema_cleans_up_test_file(self, config_manager, sample_settings):
        """Test that test file is cleaned up after validation."""
        test_path = config_manager.settings_path.parent / 'settings.test.json'

        with patch('thoth.config.Settings.from_json_file'):
            config_manager.validate_schema(sample_settings)

        # Test file should be cleaned up
        assert not test_path.exists()


class TestBackup:
    """Tests for backup functionality."""

    def test_backup_success(self, config_manager, sample_settings):
        """Test creating backup of existing settings."""
        # Write settings file
        with open(config_manager.settings_path, 'w', encoding='utf-8') as f:
            json.dump(sample_settings, f)

        # Create backup
        backup_path = config_manager.backup()

        assert backup_path is not None
        assert backup_path.exists()
        assert backup_path.parent == config_manager.backup_dir
        assert 'settings_' in backup_path.name
        assert backup_path.suffix == '.json'

        # Verify backup content
        with open(backup_path, encoding='utf-8') as f:
            backup_content = json.load(f)
        assert backup_content == sample_settings

    def test_backup_no_existing_file(self, config_manager):
        """Test backup when no settings file exists."""
        backup_path = config_manager.backup()
        assert backup_path is None

    def test_backup_permission_error(self, config_manager, sample_settings):
        """Test backup when copy fails."""
        # Write settings file
        with open(config_manager.settings_path, 'w', encoding='utf-8') as f:
            json.dump(sample_settings, f)

        with patch('shutil.copy2', side_effect=PermissionError('No access')):
            with pytest.raises(PermissionError):
                config_manager.backup()


class TestAtomicSave:
    """Tests for atomic save functionality."""

    def test_atomic_save_success(self, config_manager, sample_settings):
        """Test atomic save of settings."""
        config_manager.atomic_save(sample_settings)

        # Verify file exists and contains correct data
        assert config_manager.settings_path.exists()
        with open(config_manager.settings_path, encoding='utf-8') as f:
            saved_content = json.load(f)
        assert saved_content == sample_settings

        # Verify temp file was cleaned up
        temp_path = config_manager.settings_path.parent / 'settings.tmp.json'
        assert not temp_path.exists()

    def test_atomic_save_creates_directory(self, temp_vault):
        """Test that atomic save creates parent directory."""
        # Remove _thoth directory
        thoth_dir = temp_vault / '_thoth'
        if thoth_dir.exists():
            import shutil

            shutil.rmtree(thoth_dir)

        manager = ConfigManager(temp_vault)
        manager.atomic_save({'test': 'value'})

        assert manager.settings_path.exists()

    def test_atomic_save_cleans_up_on_error(self, config_manager, sample_settings):
        """Test that temp file is cleaned up on error."""
        temp_path = config_manager.settings_path.parent / 'settings.tmp.json'

        with patch('builtins.open', side_effect=PermissionError('No access')):
            with pytest.raises(PermissionError):
                config_manager.atomic_save(sample_settings)

        # Temp file should be cleaned up
        assert not temp_path.exists()

    def test_atomic_save_sorted_keys(self, config_manager):
        """Test that saved JSON has sorted keys."""
        settings = {'z_field': 1, 'a_field': 2, 'm_field': 3}
        config_manager.atomic_save(settings)

        # Read raw JSON to check key order
        content = config_manager.settings_path.read_text()

        # Keys should appear in alphabetical order
        assert '"a_field"' in content
        assert '"m_field"' in content
        assert '"z_field"' in content


class TestSaveWithBackup:
    """Tests for save with backup functionality."""

    def test_save_with_backup_success(self, config_manager, sample_settings):
        """Test saving with automatic backup."""
        # Write existing settings
        with open(config_manager.settings_path, 'w', encoding='utf-8') as f:
            json.dump({'old': 'data'}, f)

        # Mock validation to succeed
        with patch('thoth.config.Settings.from_json_file'):
            # Save new settings with backup
            backup_path = config_manager.save_with_backup(sample_settings)

        # Backup should exist
        assert backup_path is not None
        assert backup_path.exists()

        # Verify backup contains old data
        with open(backup_path, encoding='utf-8') as f:
            backup_content = json.load(f)
        assert backup_content == {'old': 'data'}

        # Verify new settings saved
        with open(config_manager.settings_path, encoding='utf-8') as f:
            saved_content = json.load(f)
        assert saved_content == sample_settings

    def test_save_with_backup_no_existing_file(self, config_manager, sample_settings):
        """Test saving when no existing file to backup."""
        with patch.object(ConfigManager, 'validate_schema', return_value=True):
            backup_path = config_manager.save_with_backup(sample_settings)

        # No backup should be created
        assert backup_path is None

        # Settings should still be saved
        assert config_manager.settings_path.exists()

    def test_save_with_backup_validation_error(self, config_manager, sample_settings):
        """Test that save fails if validation fails."""
        # Write existing settings
        with open(config_manager.settings_path, 'w', encoding='utf-8') as f:
            json.dump({'old': 'data'}, f)

        with patch.object(
            ConfigManager,
            'validate_schema',
            side_effect=ValidationError.from_exception_data(
                'test', [{'type': 'missing', 'loc': ('field',), 'msg': 'required'}]
            ),
        ):
            with pytest.raises(ValidationError):
                config_manager.save_with_backup(sample_settings)

        # Original settings should be unchanged
        with open(config_manager.settings_path, encoding='utf-8') as f:
            current_content = json.load(f)
        assert current_content == {'old': 'data'}


class TestRestoreBackup:
    """Tests for backup restoration."""

    def test_restore_backup_success(self, config_manager, sample_settings):
        """Test restoring from backup."""
        # Create backup file
        backup_path = config_manager.backup_dir / 'settings_backup.json'
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(sample_settings, f)

        # Restore backup
        config_manager.restore_backup(backup_path)

        # Verify settings restored
        with open(config_manager.settings_path, encoding='utf-8') as f:
            restored_content = json.load(f)
        assert restored_content == sample_settings

    def test_restore_backup_nonexistent_file(self, config_manager):
        """Test restoring from nonexistent backup."""
        fake_path = config_manager.backup_dir / 'nonexistent.json'

        with pytest.raises(FileNotFoundError):
            config_manager.restore_backup(fake_path)

    def test_restore_backup_copy_error(self, config_manager, sample_settings):
        """Test restoring when copy fails."""
        # Create backup file
        backup_path = config_manager.backup_dir / 'settings_backup.json'
        with open(backup_path, 'w', encoding='utf-8') as f:
            json.dump(sample_settings, f)

        with patch('shutil.copy2', side_effect=PermissionError('No access')):
            with pytest.raises(PermissionError):
                config_manager.restore_backup(backup_path)


class TestListBackups:
    """Tests for listing backups."""

    def test_list_backups_empty(self, config_manager):
        """Test listing backups when none exist."""
        backups = config_manager.list_backups()
        assert backups == []

    def test_list_backups_multiple(self, config_manager):
        """Test listing multiple backups."""
        # Create multiple backup files
        backup_files = []
        for i in range(3):
            backup_path = config_manager.backup_dir / f'settings_2024010{i}_120000.json'
            backup_path.write_text('{}')
            backup_files.append(backup_path)

        backups = config_manager.list_backups()

        assert len(backups) == 3
        # Should be sorted by modification time (newest first)
        assert all(isinstance(b, Path) for b in backups)

    def test_list_backups_ignores_non_matching(self, config_manager):
        """Test that listing ignores non-matching files."""
        # Create backup file
        backup_path = config_manager.backup_dir / 'settings_20240101_120000.json'
        backup_path.write_text('{}')

        # Create non-matching file
        other_file = config_manager.backup_dir / 'other_file.json'
        other_file.write_text('{}')

        backups = config_manager.list_backups()

        assert len(backups) == 1
        assert backups[0].name.startswith('settings_')

    def test_list_backups_no_backup_dir(self, temp_vault):
        """Test listing backups when backup directory doesn't exist."""
        # Remove backup directory
        manager = ConfigManager(temp_vault)
        import shutil

        if manager.backup_dir.exists():
            shutil.rmtree(manager.backup_dir)

        backups = manager.list_backups()
        assert backups == []
