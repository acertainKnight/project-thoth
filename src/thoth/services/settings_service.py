"""
Settings service for managing Thoth's JSON configuration file.

This service handles the non-sensitive configuration settings stored in
thoth.settings.json, while API keys and secrets remain in .env file.
"""

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
from loguru import logger
from pydantic import BaseModel, Field
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from thoth.services.base import BaseService


class SettingsUpdateRequest(BaseModel):
    """Request model for updating settings."""

    path: str = Field(
        ..., description="Setting path using dot notation (e.g., 'llm.default.model')"
    )
    value: Any = Field(..., description='New value for the setting')
    action: str = Field('set', description='Action to perform: set, append, remove')


class SettingsService(BaseService):
    """
    Manages the thoth.settings.json configuration file.

    This service provides:
    - Loading and parsing JSON settings
    - Writing and updating settings with validation
    - File watching for hot-reload capability
    - Migration utilities from legacy configs
    - Version management and compatibility

    Note: API keys and sensitive data remain in .env file for security.
    """

    def __init__(self, settings_path: Path | None = None, config=None):
        """
        Initialize the settings service.

        Args:
            settings_path: Path to the settings JSON file
            config: Optional ThothConfig instance
        """
        super().__init__(config)
        self.settings_path = settings_path or Path('thoth.settings.json')
        self.schema_path = Path('thoth.settings.schema.json')
        self.backup_dir = Path('settings_backups')
        self._settings_cache = None
        self._schema_cache = None
        self._file_observer = None
        self._callbacks = []
        self._last_modified = None

    def initialize(self) -> None:
        """Initialize the settings service."""
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(exist_ok=True)

        # Load or create default settings
        if not self.settings_path.exists():
            self._create_default_settings()

        # Load settings and schema
        self._load_settings(force=True)
        self._load_schema()

        logger.info(f'Settings service initialized with file: {self.settings_path}')

    def load_settings(self, force: bool = False) -> dict[str, Any]:
        """
        Load settings from JSON file.

        Args:
            force: Force reload even if cached

        Returns:
            Dictionary of settings
        """
        return self._load_settings(force)

    def _load_settings(self, force: bool = False) -> dict[str, Any]:
        """Internal method to load settings with caching."""
        if self._settings_cache is not None and not force:
            # Check if file has been modified
            current_mtime = self.settings_path.stat().st_mtime
            if self._last_modified and current_mtime <= self._last_modified:
                return self._settings_cache

        try:
            with open(self.settings_path) as f:
                self._settings_cache = json.load(f)
                self._last_modified = self.settings_path.stat().st_mtime
                return self._settings_cache
        except json.JSONDecodeError as e:
            logger.error(f'Invalid JSON in settings file: {e}')
            raise
        except FileNotFoundError:
            logger.warning('Settings file not found, creating default')
            return self._create_default_settings()

    def save_settings(
        self, settings: dict[str, Any], create_backup: bool = True
    ) -> bool:
        """
        Save settings to JSON file with validation.

        Args:
            settings: Settings dictionary to save
            create_backup: Whether to create a backup before saving

        Returns:
            True if successful, False otherwise
        """
        # Validate settings first
        is_valid, errors = self.validate_settings(settings)
        if not is_valid:
            logger.error(f'Settings validation failed: {errors}')
            return False

        # Create backup if requested
        if create_backup and self.settings_path.exists():
            self._create_backup()

        try:
            # Update metadata
            settings['lastModified'] = datetime.now().isoformat()

            # Write to temporary file first
            temp_path = self.settings_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(settings, f, indent=2, sort_keys=False)

            # Atomic replace
            temp_path.replace(self.settings_path)

            # Update cache
            self._settings_cache = settings
            self._last_modified = self.settings_path.stat().st_mtime

            # Notify callbacks
            self._notify_callbacks('save', settings)

            logger.info('Settings saved successfully')
            return True

        except Exception as e:
            logger.error(f'Failed to save settings: {e}')
            return False

    def update_setting(self, path: str, value: Any, action: str = 'set') -> bool:
        """
        Update a specific setting using dot notation.

        Args:
            path: Setting path (e.g., 'llm.default.model')
            value: New value for the setting
            action: Action to perform: 'set', 'append', or 'remove'

        Returns:
            True if successful, False otherwise
        """
        settings = self.load_settings(force=True)

        # Navigate to the target using dot notation
        keys = path.split('.')
        target = settings

        # Navigate to parent of target key
        for key in keys[:-1]:
            if key not in target:
                if action == 'set':
                    target[key] = {}
                else:
                    logger.error(f'Path not found: {path}')
                    return False
            target = target[key]

        # Perform the action
        final_key = keys[-1]

        if action == 'set':
            target[final_key] = value
            logger.info(f'Set {path} = {value}')

        elif action == 'append':
            if final_key not in target:
                target[final_key] = []
            if not isinstance(target[final_key], list):
                logger.error(f'Cannot append to non-list at {path}')
                return False
            target[final_key].append(value)
            logger.info(f'Appended {value} to {path}')

        elif action == 'remove':
            if final_key in target:
                if isinstance(target[final_key], list) and value in target[final_key]:
                    target[final_key].remove(value)
                    logger.info(f'Removed {value} from {path}')
                else:
                    del target[final_key]
                    logger.info(f'Removed {path}')
            else:
                logger.warning(f'Path not found for removal: {path}')
                return False

        # Save the updated settings
        return self.save_settings(settings)

    def get_setting(self, path: str, default: Any = None) -> Any:
        """
        Get a specific setting using dot notation.

        Args:
            path: Setting path (e.g., 'llm.default.model')
            default: Default value if setting not found

        Returns:
            Setting value or default
        """
        settings = self.load_settings()

        # Navigate using dot notation
        keys = path.split('.')
        target = settings

        for key in keys:
            if isinstance(target, dict) and key in target:
                target = target[key]
            else:
                return default

        return target

    def validate_settings(self, settings: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Validate settings against schema.

        Args:
            settings: Settings to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Load schema if not cached
        if self._schema_cache is None:
            self._load_schema()

        # If no schema available, just do basic validation
        if self._schema_cache is None:
            # Basic validation
            if not isinstance(settings, dict):
                errors.append('Settings must be a dictionary')
            if 'version' not in settings:
                errors.append('Settings must have a version field')
            return len(errors) == 0, errors

        # Validate against schema
        try:
            jsonschema.validate(instance=settings, schema=self._schema_cache)
            return True, []
        except jsonschema.exceptions.ValidationError as e:
            errors.append(str(e))
            return False, errors

    def _load_schema(self) -> dict[str, Any] | None:
        """Load JSON schema for validation."""
        if not self.schema_path.exists():
            logger.warning('Schema file not found, validation will be limited')
            return None

        try:
            with open(self.schema_path) as f:
                self._schema_cache = json.load(f)
                return self._schema_cache
        except Exception as e:
            logger.error(f'Failed to load schema: {e}')
            return None

    def migrate_from_env(self) -> dict[str, Any]:
        """
        Migrate settings from current environment/config to JSON format.

        Note: This only migrates non-sensitive settings. API keys remain in .env.

        Returns:
            Migrated settings dictionary
        """
        from thoth.utilities.config import get_config

        config = get_config()

        # Build settings structure from current config
        settings = {
            '$schema': './thoth.settings.schema.json',
            'version': '1.0.0',
            'lastModified': datetime.now().isoformat(),
            '_comment': 'Migrated from environment configuration. API keys remain in .env file.',
            'llm': {
                'default': {
                    'model': config.llm_config.model,
                    'temperature': config.llm_config.model_settings.temperature,
                    'maxTokens': config.llm_config.model_settings.max_tokens,
                    'topP': config.llm_config.model_settings.top_p,
                    'streaming': config.llm_config.model_settings.streaming,
                    'useRateLimiter': config.llm_config.model_settings.use_rate_limiter,
                    'maxOutputTokens': config.llm_config.max_output_tokens,
                    'maxContextLength': config.llm_config.max_context_length,
                    'chunkSize': config.llm_config.chunk_size,
                    'chunkOverlap': config.llm_config.chunk_overlap,
                }
            },
            'rag': {
                'embeddingModel': config.rag_config.embedding_model,
                'embeddingBatchSize': config.rag_config.embedding_batch_size,
                'skipFilesWithImages': config.rag_config.skip_files_with_images,
                'vectorDbPath': str(config.rag_config.vector_db_path),
                'collectionName': config.rag_config.collection_name,
                'chunkSize': config.rag_config.chunk_size,
                'chunkOverlap': config.rag_config.chunk_overlap,
                'qa': {
                    'model': config.rag_config.qa_model,
                    'temperature': config.rag_config.qa_temperature,
                    'maxTokens': config.rag_config.qa_max_tokens,
                    'retrievalK': config.rag_config.retrieval_k,
                },
            },
            'paths': {
                'workspace': str(config.workspace_dir),
                'pdf': str(config.pdf_dir),
                'markdown': str(config.markdown_dir),
                'notes': str(config.notes_dir),
                'prompts': str(config.prompts_dir),
                'templates': str(config.templates_dir),
                'output': str(config.output_dir),
                'knowledgeBase': str(config.knowledge_base_dir),
                'graphStorage': str(config.graph_storage_path),
                'queries': str(config.queries_dir),
                'agentStorage': str(config.agent_storage_dir),
            },
            'logging': {
                'level': config.logging_config.level,
                'format': config.logging_config.logformat,
                'dateFormat': config.logging_config.dateformat,
                'file': {
                    'enabled': True,
                    'path': config.logging_config.filename,
                    'mode': config.logging_config.filemode,
                    'level': config.logging_config.file_level,
                },
            },
        }

        # Add other configurations as needed
        # ... (citation, performance, servers, etc.)

        return settings

    def watch_settings_file(self, callback: Callable[[str, dict], None]) -> None:
        """
        Watch settings file for changes and trigger callback.

        Args:
            callback: Function to call when settings change
                     Receives (event_type, settings) as arguments
        """
        self._callbacks.append(callback)

        # Start file watcher if not already running
        if self._file_observer is None:
            self._start_file_watcher()

    def _start_file_watcher(self) -> None:
        """Start watching the settings file for changes."""

        class SettingsFileHandler(FileSystemEventHandler):
            def __init__(self, settings_service):
                self.settings_service = settings_service

            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith(
                    'thoth.settings.json'
                ):
                    logger.info('Settings file changed, reloading...')
                    settings = self.settings_service.load_settings(force=True)
                    self.settings_service._notify_callbacks('modified', settings)

        self._file_observer = Observer()
        handler = SettingsFileHandler(self)
        self._file_observer.schedule(
            handler, path=str(self.settings_path.parent), recursive=False
        )
        self._file_observer.start()
        logger.info('Started watching settings file for changes')

    def _notify_callbacks(self, event_type: str, settings: dict[str, Any]) -> None:
        """Notify all registered callbacks of settings change."""
        for callback in self._callbacks:
            try:
                callback(event_type, settings)
            except Exception as e:
                logger.error(f'Error in settings callback: {e}')

    def _create_backup(self) -> Path:
        """Create a backup of current settings."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'settings_backup_{timestamp}.json'

        try:
            import shutil

            shutil.copy2(self.settings_path, backup_path)
            logger.info(f'Created settings backup: {backup_path}')

            # Clean up old backups (keep last 10)
            self._cleanup_old_backups()

            return backup_path
        except Exception as e:
            logger.error(f'Failed to create backup: {e}')
            raise

    def _cleanup_old_backups(self, keep_count: int = 10) -> None:
        """Clean up old backup files."""
        backups = sorted(self.backup_dir.glob('settings_backup_*.json'))
        if len(backups) > keep_count:
            for backup in backups[:-keep_count]:
                backup.unlink()
                logger.debug(f'Removed old backup: {backup}')

    def _create_default_settings(self) -> dict[str, Any]:
        """Create default settings file."""
        # Try to load from example file first
        example_path = Path('thoth.settings.example.json')
        if example_path.exists():
            try:
                with open(example_path) as f:
                    settings = json.load(f)
                # Save as actual settings file
                self.save_settings(settings, create_backup=False)
                return settings
            except Exception as e:
                logger.error(f'Failed to load example settings: {e}')

        # Create minimal default settings
        settings = {
            '$schema': './thoth.settings.schema.json',
            'version': '1.0.0',
            'lastModified': datetime.now().isoformat(),
            '_comment': 'Default settings created. API keys should be in .env file.',
            'llm': {
                'default': {
                    'model': 'mistralai/Mixtral-8x7B-Instruct-v0.1',
                    'temperature': 0.7,
                    'maxTokens': 4096,
                }
            },
            'rag': {'chunkSize': 1000, 'retrievalK': 4},
            'paths': {'workspace': '.', 'pdf': 'data/pdf', 'notes': 'data/notes'},
        }

        self.save_settings(settings, create_backup=False)
        return settings

    def export_schema(self) -> dict[str, Any]:
        """Export the current settings schema."""
        if self._schema_cache is None:
            self._load_schema()
        return self._schema_cache or {}

    def get_all_settings_paths(self) -> list[str]:
        """
        Get all available setting paths in dot notation.

        Returns:
            List of all setting paths
        """
        settings = self.load_settings()
        paths = []

        def extract_paths(obj: dict, prefix: str = '') -> None:
            for key, value in obj.items():
                if key.startswith('_'):  # Skip comment fields
                    continue

                current_path = f'{prefix}.{key}' if prefix else key
                paths.append(current_path)

                if isinstance(value, dict):
                    extract_paths(value, current_path)

        extract_paths(settings)
        return sorted(paths)

    def health_check(self) -> dict[str, str]:
        """Check health of settings service."""
        try:
            # Check if settings file exists and is readable
            if not self.settings_path.exists():
                return {'status': 'warning', 'message': 'Settings file does not exist'}

            # Try to load settings
            settings = self.load_settings(force=True)

            # Validate settings
            is_valid, errors = self.validate_settings(settings)

            if is_valid:
                return {
                    'status': 'healthy',
                    'message': f'Settings loaded successfully from {self.settings_path}',
                    'version': settings.get('version', 'unknown'),
                    'last_modified': settings.get('lastModified', 'unknown'),
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': f'Settings validation failed: {errors[0] if errors else "Unknown error"}',
                }

        except Exception as e:
            return {
                'status': 'unhealthy',
                'message': f'Settings service error: {e!s}',
            }

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._file_observer and self._file_observer.is_alive():
            self._file_observer.stop()
            self._file_observer.join()
            logger.info('Stopped settings file watcher')
