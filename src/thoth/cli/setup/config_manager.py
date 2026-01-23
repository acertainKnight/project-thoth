"""
Configuration manager for setup wizard.

Handles loading, merging, validating, and saving configuration files
with atomic writes and automatic backups.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from pydantic import ValidationError


class ConfigManager:
    """Manages configuration loading, merging, and saving."""

    def __init__(self, vault_path: Path):
        """
        Initialize configuration manager.

        Args:
            vault_path: Path to Obsidian vault root
        """
        self.vault_path = vault_path
        self.settings_path = vault_path / '_thoth' / 'settings.json'
        self.backup_dir = vault_path / '_thoth' / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def load_existing(self) -> Optional[Dict[str, Any]]:
        """
        Load existing settings.json file.

        Returns:
            Dictionary of settings, or None if file doesn't exist or cannot be read

        Raises:
            ValueError: If file contains invalid JSON
        """
        if not self.settings_path.exists():
            logger.info('No existing settings.json found')
            return None

        try:
            with open(self.settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            logger.info(f'Loaded existing settings from {self.settings_path}')
            return settings
        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse settings.json: {e}')
            raise ValueError(f'Invalid JSON in settings.json: {e}')
        except PermissionError as e:
            logger.error(f'Permission denied reading settings.json: {e}')
            return None
        except Exception as e:
            logger.error(f'Failed to load settings.json: {e}')
            return None

    def deep_merge(
        self, existing: Dict[str, Any], updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Deep merge two dictionaries, preserving existing values.

        Strategy: PREFER_EXISTING
        - Updates only override if explicitly provided in wizard
        - Preserves all custom fields not touched by wizard
        - Recursively merges nested dictionaries

        Args:
            existing: Existing configuration
            updates: Updates from wizard

        Returns:
            Merged configuration dictionary
        """
        result = existing.copy()

        for key, value in updates.items():
            if key not in result:
                # New key from wizard
                result[key] = value
            elif isinstance(value, dict) and isinstance(result[key], dict):
                # Recursively merge nested dicts
                result[key] = self.deep_merge(result[key], value)
            else:
                # Override with wizard value
                result[key] = value

        return result

    def validate_schema(self, settings: Dict[str, Any]) -> bool:
        """
        Validate settings against Pydantic models.

        Args:
            settings: Settings dictionary to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If validation fails
        """
        try:
            # Temporarily write to test file for Settings to load
            test_path = self.settings_path.parent / 'settings.test.json'
            with open(test_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)

            # Try loading with Settings.from_json_file (validates via Pydantic)
            try:
                # Load with Settings.from_json_file which validates all Pydantic models
                from thoth.config import Settings

                Settings.from_json_file(test_path)  # Validates via Pydantic
                logger.info('Settings validation successful')
                return True
            finally:
                # Clean up test file
                if test_path.exists():
                    test_path.unlink()

        except ValidationError as e:
            logger.error(f'Settings validation failed: {e}')
            raise
        except Exception as e:
            logger.error(f'Unexpected validation error: {e}')
            raise

    def backup(self) -> Optional[Path]:
        """
        Create timestamped backup of existing settings.

        Returns:
            Path to backup file, or None if no settings exist
        """
        if not self.settings_path.exists():
            return None

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'settings_{timestamp}.json'

        try:
            shutil.copy2(self.settings_path, backup_path)
            logger.info(f'Created backup: {backup_path}')
            return backup_path
        except Exception as e:
            logger.error(f'Failed to create backup: {e}')
            raise

    def atomic_save(self, settings: Dict[str, Any]) -> None:
        """
        Save settings atomically using temp file + rename pattern.

        This ensures settings.json is never left in a corrupted state.

        Args:
            settings: Settings dictionary to save
        """
        # Ensure directory exists
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first
        temp_path = self.settings_path.parent / 'settings.tmp.json'

        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, sort_keys=True)

            # Atomic rename (POSIX guarantees atomicity)
            temp_path.replace(self.settings_path)
            logger.info(f'Settings saved to {self.settings_path}')

        except Exception as e:
            # Clean up temp file on error
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f'Failed to save settings: {e}')
            raise

    def save_with_backup(self, settings: Dict[str, Any]) -> Path:
        """
        Save settings with automatic backup of existing file.

        Args:
            settings: Settings dictionary to save

        Returns:
            Path to backup file (if created)
        """
        # Create backup before making changes
        backup_path = self.backup()

        try:
            # Validate before saving
            self.validate_schema(settings)

            # Atomic save
            self.atomic_save(settings)

            return backup_path

        except Exception as e:
            # If save fails and we have a backup, we can restore
            logger.error(f'Save failed: {e}')
            if backup_path and backup_path.exists():
                logger.info(f'Backup available at {backup_path} for manual recovery')
            raise

    def restore_backup(self, backup_path: Path) -> None:
        """
        Restore settings from a backup file.

        Args:
            backup_path: Path to backup file
        """
        if not backup_path.exists():
            raise FileNotFoundError(f'Backup not found: {backup_path}')

        try:
            shutil.copy2(backup_path, self.settings_path)
            logger.info(f'Restored settings from backup: {backup_path}')
        except Exception as e:
            logger.error(f'Failed to restore backup: {e}')
            raise

    def list_backups(self) -> list[Path]:
        """
        List all available backup files, sorted by timestamp (newest first).

        Returns:
            List of backup file paths
        """
        if not self.backup_dir.exists():
            return []

        backups = sorted(
            self.backup_dir.glob('settings_*.json'), key=lambda p: p.stat().st_mtime, reverse=True
        )
        return backups
