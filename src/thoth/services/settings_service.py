"""
Settings service for managing Thoth's JSON configuration file.

This service handles the non-sensitive configuration settings stored in
thoth.settings.json, while API keys and secrets remain in .env file.

Enhanced with vault-aware file location detection and environment variable overrides.
"""

import json
import os
import shutil
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
            settings_path: Path to the settings JSON file (optional, will auto-detect)
            config: Optional ThothConfig instance (pass None to avoid circular deps)
        """
        # Only call super().__init__(config) if config is not explicitly None
        # This avoids circular dependency when used by HybridConfigLoader
        if config is not None:
            super().__init__(config)
        else:
            # Initialize minimal BaseService attributes without config
            self._config = None

        # Determine settings file path with vault awareness and env override
        self.settings_path = self._determine_settings_path(settings_path)
        self.schema_path = self.settings_path.parent / 'thoth.settings.schema.json'
        self.backup_dir = self.settings_path.parent / 'settings_backups'

        # Cache and state management
        self._settings_cache = None
        self._schema_cache = None
        self._file_observer = None
        self._callbacks = []
        self._last_modified = None

        # Environment variable override mappings
        self._env_override_map = self._build_env_override_map()

        logger.info(f'Settings service initialized with file: {self.settings_path}')
        if self._is_in_obsidian_vault():
            logger.info('Obsidian vault detected, using vault-relative settings path')

    def _determine_settings_path(self, provided_path: Path | None = None) -> Path:
        """
        Determine the settings file path with vault awareness and environment overrides.

        Priority:
        1. Environment variable THOTH_SETTINGS_FILE
        2. Provided path parameter
        3. Vault-aware detection (.obsidian directory present)
        4. Current directory fallback

        Args:
            provided_path: Explicitly provided settings path

        Returns:
            Path to the settings file
        """
        # 1. Check environment variable override
        env_path = os.getenv('THOTH_SETTINGS_FILE')
        if env_path:
            path = Path(env_path).expanduser().resolve()
            logger.info(f'Using settings file from THOTH_SETTINGS_FILE: {path}')
            return path

        # 2. Use provided path if given
        if provided_path:
            return provided_path.resolve()

        # 3. Check for Obsidian vault
        vault_root = self._detect_obsidian_vault()
        if vault_root:
            vault_settings = vault_root / '.thoth.settings.json'
            logger.info(
                f'Obsidian vault detected at {vault_root}, using {vault_settings}'
            )
            return vault_settings

        # 4. Default to current directory
        default_path = Path('.thoth.settings.json').resolve()
        logger.info(f'Using default settings path: {default_path}')
        return default_path

    def _detect_obsidian_vault(self) -> Path | None:
        """
        Detect if we're running within an Obsidian vault.

        Looks for .obsidian directory in current working directory or parent
        directories.

        Returns:
            Path to vault root if detected, None otherwise
        """
        current = Path.cwd()

        # Check current directory and up to 5 parent levels
        for _ in range(6):
            obsidian_dir = current / '.obsidian'
            if obsidian_dir.exists() and obsidian_dir.is_dir():
                logger.debug(f'Found .obsidian directory at: {current}')
                return current

            parent = current.parent
            if parent == current:  # Reached filesystem root
                break
            current = parent

        return None

    def _is_in_obsidian_vault(self) -> bool:
        """Check if currently running within an Obsidian vault."""
        return self._detect_obsidian_vault() is not None

    def _build_env_override_map(self) -> dict[str, str]:
        """
        Build mapping of JSON setting paths to environment variable names.

        This defines which settings can be overridden by environment variables,
        primarily focusing on sensitive settings like API keys.

        Returns:
            Dictionary mapping JSON paths to environment variable names
        """
        return {
            # API Keys (sensitive)
            'apiKeys.mistralKey': 'THOTH_MISTRAL_API_KEY',
            'apiKeys.openrouterKey': 'THOTH_OPENROUTER_API_KEY',
            'apiKeys.openaiKey': 'THOTH_OPENAI_API_KEY',
            'apiKeys.anthropicKey': 'THOTH_ANTHROPIC_API_KEY',
            'apiKeys.opencitationsKey': 'THOTH_OPENCITATIONS_API_KEY',
            'apiKeys.googleApiKey': 'THOTH_GOOGLE_API_KEY',
            'apiKeys.googleSearchEngineId': 'THOTH_GOOGLE_SEARCH_ENGINE_ID',
            'apiKeys.semanticScholarKey': 'THOTH_SEMANTIC_SCHOLAR_API_KEY',
            'apiKeys.webSearchKey': 'THOTH_WEB_SEARCH_API_KEY',
            'apiKeys.lettaApiKey': 'THOTH_LETTA_API_KEY',
            # Server configurations (deployment-sensitive)
            'servers.api.host': 'THOTH_API_HOST',
            'servers.api.port': 'THOTH_API_PORT',
            'servers.mcp.host': 'THOTH_MCP_HOST',
            'servers.mcp.port': 'THOTH_MCP_PORT',
            'memory.letta.serverUrl': 'THOTH_LETTA_SERVER_URL',
            # Database and external service URLs (sensitive)
            'rag.vectorDbPath': 'THOTH_VECTOR_DB_PATH',
            # File paths (environment-specific)
            'paths.workspace': 'THOTH_WORKSPACE_DIR',
            'paths.pdf': 'THOTH_PDF_DIR',
            'paths.notes': 'THOTH_NOTES_DIR',
            'paths.logs': 'THOTH_LOGS_DIR',
        }

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
        Load settings from JSON file with environment variable overrides.

        Args:
            force: Force reload even if cached

        Returns:
            Dictionary of settings with environment overrides applied
        """
        return self._load_settings(force)

    def _load_settings(self, force: bool = False) -> dict[str, Any]:
        """Internal method to load settings with caching and env overrides."""
        if self._settings_cache is not None and not force:
            # Check if file has been modified
            if self.settings_path.exists():
                current_mtime = self.settings_path.stat().st_mtime
                if self._last_modified and current_mtime <= self._last_modified:
                    # Apply environment overrides to cached settings
                    return self._apply_env_overrides(self._settings_cache.copy())

        try:
            with open(self.settings_path) as f:
                self._settings_cache = json.load(f)
                self._last_modified = self.settings_path.stat().st_mtime

                # Apply environment variable overrides
                settings_with_overrides = self._apply_env_overrides(
                    self._settings_cache.copy()
                )
                return settings_with_overrides

        except json.JSONDecodeError as e:
            logger.error(f'Invalid JSON in settings file: {e}')
            raise
        except FileNotFoundError:
            logger.warning('Settings file not found, creating default')
            return self._create_default_settings()

    def _apply_env_overrides(self, settings: dict[str, Any]) -> dict[str, Any]:
        """
        Apply environment variable overrides to settings.

        Args:
            settings: Base settings dictionary

        Returns:
            Settings with environment overrides applied
        """
        for json_path, env_var in self._env_override_map.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                self._set_nested_value(settings, json_path, env_value)
                logger.debug(
                    f'Applied environment override: {json_path} from {env_var}'
                )

        return settings

    def _set_nested_value(self, data: dict, path: str, value: Any) -> None:
        """
        Set a nested value in a dictionary using dot notation.

        Args:
            data: Dictionary to modify
            path: Dot-separated path (e.g., 'llm.default.model')
            value: Value to set
        """
        keys = path.split('.')
        current = data

        # Navigate to parent of target key, creating nested dicts as needed
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        # Set the final value, with type conversion for common cases
        final_key = keys[-1]
        current[final_key] = self._convert_env_value(value)

    def _convert_env_value(self, value: str) -> Any:
        """
        Convert environment variable string to appropriate type.

        Args:
            value: String value from environment variable

        Returns:
            Converted value (bool, int, float, or str)
        """
        # Boolean conversion
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'

        # Integer conversion
        try:
            if '.' not in value:
                return int(value)
        except ValueError:
            pass

        # Float conversion
        try:
            return float(value)
        except ValueError:
            pass

        # Return as string
        return value

    def save_settings(
        self, settings: dict[str, Any], create_backup: bool = True
    ) -> bool:
        """
        Save settings to JSON file with enhanced atomic operations and rollback.

        Args:
            settings: Settings dictionary to save
            create_backup: Whether to create a backup before saving

        Returns:
            True if successful, False otherwise
        """
        backup_path = None
        temp_path = None

        try:
            # Validate settings first
            is_valid, errors = self.validate_settings(settings)
            if not is_valid:
                logger.error(f'Settings validation failed: {errors}')
                return False

            # Create backup if requested and file exists
            if create_backup and self.settings_path.exists():
                backup_path = self._create_backup()

            # Ensure parent directory exists
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)

            # Update metadata
            settings['lastModified'] = datetime.now().isoformat()

            # Write to temporary file with atomic operations
            temp_path = self.settings_path.with_suffix('.tmp')
            self._atomic_write(temp_path, settings)

            # Validate the written file before replacing
            if not self._validate_written_file(temp_path):
                raise ValueError('Written file failed validation')

            # Atomic replace
            if os.name == 'nt':  # Windows
                # Windows doesn't support atomic replace if target exists
                if self.settings_path.exists():
                    backup_temp = self.settings_path.with_suffix('.backup_temp')
                    shutil.move(str(self.settings_path), str(backup_temp))
                    try:
                        shutil.move(str(temp_path), str(self.settings_path))
                        backup_temp.unlink()  # Remove temp backup
                    except Exception:
                        # Restore from temp backup
                        shutil.move(str(backup_temp), str(self.settings_path))
                        raise
                else:
                    shutil.move(str(temp_path), str(self.settings_path))
            else:  # Unix-like systems
                temp_path.replace(self.settings_path)

            # Update cache
            self._settings_cache = settings
            self._last_modified = self.settings_path.stat().st_mtime

            # Notify callbacks
            self._notify_callbacks('save', settings)

            logger.info('Settings saved successfully with atomic operations')
            return True

        except Exception as e:
            logger.error(f'Failed to save settings: {e}')

            # Cleanup temporary file
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as cleanup_error:
                    logger.warning(f'Failed to cleanup temp file: {cleanup_error}')

            # Attempt rollback if we have a backup
            if backup_path and create_backup:
                success = self._rollback_from_backup(backup_path)
                if success:
                    logger.info('Successfully rolled back to previous settings')
                else:
                    logger.error('Rollback failed - settings may be corrupted')

            return False

    def _atomic_write(self, file_path: Path, settings: dict[str, Any]) -> None:
        """
        Write settings to file atomically with proper error handling.

        Args:
            file_path: Path to write to
            settings: Settings to write
        """
        # Use a more secure temporary file approach
        temp_fd = None
        try:
            import tempfile

            # Create temporary file in same directory as target
            temp_fd, temp_name = tempfile.mkstemp(
                suffix='.tmp', prefix='thoth_settings_', dir=file_path.parent
            )

            # Write to temporary file descriptor
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                temp_fd = None  # Prevent double close
                json.dump(settings, f, indent=2, sort_keys=False, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk

            # Move temporary file to target location
            temp_path = Path(temp_name)
            temp_path.replace(file_path)

        except Exception:
            # Cleanup on failure
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except OSError:
                    pass
            raise

    def _validate_written_file(self, file_path: Path) -> bool:
        """
        Validate that a written settings file is valid JSON and meets requirements.

        Args:
            file_path: Path to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            with open(file_path, encoding='utf-8') as f:
                test_settings = json.load(f)

            # Basic validation - ensure it's a dict with required fields
            if not isinstance(test_settings, dict):
                return False

            # Check for required top-level fields
            required_fields = ['version', 'lastModified']
            for field in required_fields:
                if field not in test_settings:
                    logger.warning(f'Written file missing required field: {field}')
                    return False

            return True

        except (OSError, json.JSONDecodeError) as e:
            logger.error(f'Validation failed for written file: {e}')
            return False

    def _rollback_from_backup(self, backup_path: Path) -> bool:
        """
        Rollback settings from a backup file.

        Args:
            backup_path: Path to backup file

        Returns:
            True if rollback successful, False otherwise
        """
        try:
            if not backup_path.exists():
                logger.error(f'Backup file not found: {backup_path}')
                return False

            # Validate backup before restoring
            if not self._validate_written_file(backup_path):
                logger.error(f'Backup file is invalid: {backup_path}')
                return False

            # Copy backup to settings file
            shutil.copy2(backup_path, self.settings_path)

            # Clear cache to force reload
            self._settings_cache = None
            self._last_modified = None

            logger.info(f'Successfully rolled back from backup: {backup_path}')
            return True

        except Exception as e:
            logger.error(f'Rollback failed: {e}')
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
        """Create a backup of current settings with enhanced error handling."""
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f'settings_backup_{timestamp}.json'

        try:
            # Validate source file before backup
            if not self.settings_path.exists():
                raise FileNotFoundError(
                    f'Source settings file not found: {self.settings_path}'
                )

            # Create backup with metadata preservation
            shutil.copy2(self.settings_path, backup_path)

            # Verify backup was created successfully
            if not backup_path.exists():
                raise OSError(f'Backup file was not created: {backup_path}')

            # Verify backup file is valid JSON
            if not self._validate_written_file(backup_path):
                backup_path.unlink()  # Remove invalid backup
                raise ValueError('Created backup file is not valid JSON')

            logger.info(f'Created settings backup: {backup_path}')

            # Clean up old backups (keep last 10)
            self._cleanup_old_backups()

            return backup_path

        except Exception as e:
            logger.error(f'Failed to create backup: {e}')
            # Clean up partial backup
            if backup_path.exists():
                try:
                    backup_path.unlink()
                except Exception:
                    pass
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
