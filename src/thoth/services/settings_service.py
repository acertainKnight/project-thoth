"""
Settings service for managing Thoth's JSON configuration file.

This service handles the non-sensitive configuration settings stored in
thoth.settings.json, while API keys and secrets remain in .env file.

Enhanced with vault-aware file location detection and environment variable overrides.
"""

import json
import os
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import jsonschema
from loguru import logger
from pydantic import BaseModel, Field
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from thoth.services.base import BaseService

# Import Docker integration utilities
try:
    from thoth.docker.container_utils import DockerEnvironmentDetector
    from thoth.docker.volume_manager import VolumeManager
    DOCKER_INTEGRATION_AVAILABLE = True
except ImportError:
    DOCKER_INTEGRATION_AVAILABLE = False
    logger.warning("Docker integration not available - running without container features")


@dataclass
class SnapshotInfo:
    """Information about a configuration snapshot."""

    snapshot_id: str
    timestamp: datetime
    description: str
    file_path: Path
    settings_version: str
    file_size: int


@dataclass
class RollbackTrigger:
    """Represents a condition that triggers automatic rollback."""

    trigger_type: str  # 'validation_failure', 'health_check_failure', 'service_failure'
    description: str
    threshold: Any | None = None
    enabled: bool = True


@dataclass
class RollbackResult:
    """Result of a rollback operation."""

    success: bool
    snapshot_id: str
    error_message: str | None = None
    files_restored: int = 0
    rollback_timestamp: datetime | None = None


@dataclass
class MigrationInfo:
    """Information about a configuration migration."""

    migration_id: str
    from_version: str
    to_version: str
    description: str
    migration_script: str
    backup_preserved: bool
    timestamp: datetime


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    success: bool
    migration_id: str
    from_version: str
    to_version: str
    backup_path: str | None = None
    error_message: str | None = None
    migration_timestamp: datetime | None = None
    changes_applied: list[str] = None


@dataclass
class SchemaVersion:
    """Schema version information."""

    version: str
    timestamp: datetime
    description: str
    breaking_changes: bool
    migration_required: bool
    compatibility_notes: list[str] = None


class ConfigurationMigrator:
    """Handles configuration migration between versions."""

    def __init__(self, settings_service: 'SettingsService'):
        """Initialize the migrator."""
        self.settings_service = settings_service
        self.migrations_dir = settings_service.settings_path.parent / 'migrations'
        self.migrations_dir.mkdir(exist_ok=True)

        # Available migrations
        self.migrations = self._build_migration_registry()

    def detect_migration_needs(self, current_config: dict[str, Any]) -> MigrationInfo | None:
        """Detect if migration is needed for the current configuration."""
        current_version = current_config.get('version', '1.0.0')
        target_version = self._get_latest_schema_version()

        if current_version == target_version:
            return None

        # Find migration path
        migration_path = self._find_migration_path(current_version, target_version)
        if not migration_path:
            logger.warning(f'No migration path found from {current_version} to {target_version}')
            return None

        return MigrationInfo(
            migration_id=f'migrate_{current_version}_to_{target_version}',
            from_version=current_version,
            to_version=target_version,
            description=f'Migrate configuration from version {current_version} to {target_version}',
            migration_script=migration_path,
            backup_preserved=True,
            timestamp=datetime.now()
        )

    def execute_migration(self, migration_info: MigrationInfo) -> MigrationResult:
        """Execute a configuration migration."""
        try:
            # Create backup
            backup_path = self.preserve_migration_backup()

            # Load current configuration
            current_config = self.settings_service.load_settings()

            # Apply migration
            migrated_config = self._apply_migration_script(
                current_config,
                migration_info.from_version,
                migration_info.to_version
            )

            # Validate migrated configuration
            is_valid, errors = self.settings_service.validate_settings(migrated_config)
            if not is_valid:
                raise ValueError(f'Migration resulted in invalid configuration: {errors}')

            # Save migrated configuration
            success = self.settings_service.save_settings(migrated_config, create_backup=False)
            if not success:
                raise ValueError('Failed to save migrated configuration')

            logger.info(f'Successfully migrated configuration from {migration_info.from_version} to {migration_info.to_version}')

            return MigrationResult(
                success=True,
                migration_id=migration_info.migration_id,
                from_version=migration_info.from_version,
                to_version=migration_info.to_version,
                backup_path=backup_path,
                migration_timestamp=datetime.now(),
                changes_applied=self._get_migration_changes(migration_info.from_version, migration_info.to_version)
            )

        except Exception as e:
            logger.error(f'Migration failed: {e}')
            return MigrationResult(
                success=False,
                migration_id=migration_info.migration_id,
                from_version=migration_info.from_version,
                to_version=migration_info.to_version,
                error_message=str(e)
            )

    def preserve_migration_backup(self) -> str:
        """Create a backup before migration."""
        backup_dir = self.settings_service.settings_path.parent / 'migration_backups'
        backup_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = backup_dir / f'pre_migration_backup_{timestamp}.json'

        if self.settings_service.settings_path.exists():
            shutil.copy2(self.settings_service.settings_path, backup_path)
            logger.info(f'Created migration backup: {backup_path}')

        return str(backup_path)

    def rollback_migration(self, backup_path: str) -> MigrationResult:
        """Rollback a failed migration."""
        try:
            backup_file = Path(backup_path)
            if not backup_file.exists():
                raise FileNotFoundError(f'Backup file not found: {backup_path}')

            # Restore from backup
            shutil.copy2(backup_file, self.settings_service.settings_path)

            # Clear cache to force reload
            self.settings_service._settings_cache = None
            self.settings_service._last_modified = None

            logger.info(f'Successfully rolled back migration from backup: {backup_path}')

            return MigrationResult(
                success=True,
                migration_id='rollback',
                from_version='unknown',
                to_version='restored',
                backup_path=backup_path,
                migration_timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f'Migration rollback failed: {e}')
            return MigrationResult(
                success=False,
                migration_id='rollback',
                from_version='unknown',
                to_version='restored',
                error_message=str(e)
            )

    def get_migration_history(self) -> list[MigrationInfo]:
        """Get history of applied migrations."""
        history = []

        # Read migration history from file
        history_file = self.migrations_dir / 'migration_history.json'
        if history_file.exists():
            try:
                with open(history_file) as f:
                    history_data = json.load(f)
                    for item in history_data.get('migrations', []):
                        history.append(MigrationInfo(
                            migration_id=item['migration_id'],
                            from_version=item['from_version'],
                            to_version=item['to_version'],
                            description=item['description'],
                            migration_script=item['migration_script'],
                            backup_preserved=item['backup_preserved'],
                            timestamp=datetime.fromisoformat(item['timestamp'])
                        ))
            except Exception as e:
                logger.warning(f'Failed to load migration history: {e}')

        return history

    def _build_migration_registry(self) -> dict[str, Any]:
        """Build registry of available migrations."""
        return {
            '1.0.0_to_1.1.0': {
                'description': 'Add performance monitoring settings',
                'changes': ['Add performance_config section', 'Add monitoring settings'],
                'script': self._migrate_1_0_0_to_1_1_0
            },
            '1.1.0_to_2.0.0': {
                'description': 'Major restructure with advanced organization',
                'changes': ['Reorganize field groups', 'Add conditional visibility', 'Enhanced validation'],
                'script': self._migrate_1_1_0_to_2_0_0
            }
        }

    def _get_latest_schema_version(self) -> str:
        """Get the latest schema version."""
        return '2.0.0'  # This should be configurable or auto-detected

    def _find_migration_path(self, from_version: str, to_version: str) -> str | None:
        """Find migration path between versions."""
        migration_key = f'{from_version}_to_{to_version}'
        if migration_key in self.migrations:
            return migration_key

        # For now, handle direct migrations only
        # In the future, this could handle multi-step migrations
        return None

    def _apply_migration_script(self, config: dict[str, Any], from_version: str, to_version: str) -> dict[str, Any]:
        """Apply migration script to transform configuration."""
        migration_key = f'{from_version}_to_{to_version}'
        migration = self.migrations.get(migration_key)

        if not migration:
            raise ValueError(f'No migration available for {migration_key}')

        # Execute migration script
        migration_script = migration['script']
        return migration_script(config)

    def _get_migration_changes(self, from_version: str, to_version: str) -> list[str]:
        """Get list of changes applied in migration."""
        migration_key = f'{from_version}_to_{to_version}'
        migration = self.migrations.get(migration_key, {})
        return migration.get('changes', [])

    def _migrate_1_0_0_to_1_1_0(self, config: dict[str, Any]) -> dict[str, Any]:
        """Migrate from version 1.0.0 to 1.1.0."""
        migrated = config.copy()

        # Update version
        migrated['version'] = '1.1.0'
        migrated['lastModified'] = datetime.now().isoformat()

        # Add performance configuration section
        if 'performance_config' not in migrated:
            migrated['performance_config'] = {
                'cache_enabled': True,
                'cache_size_mb': 100,
                'monitoring_enabled': True,
                'metrics_collection': True,
                'performance_tracking': True
            }

        # Add monitoring settings
        if 'monitoring' not in migrated:
            migrated['monitoring'] = {
                'health_checks': True,
                'performance_metrics': True,
                'error_tracking': True
            }

        logger.info('Applied migration 1.0.0 -> 1.1.0: Added performance and monitoring settings')
        return migrated

    def _migrate_1_1_0_to_2_0_0(self, config: dict[str, Any]) -> dict[str, Any]:
        """Migrate from version 1.1.0 to 2.0.0."""
        migrated = config.copy()

        # Update version
        migrated['version'] = '2.0.0'
        migrated['lastModified'] = datetime.now().isoformat()

        # Reorganize LLM configuration
        if 'llm' in migrated:
            llm_config = migrated['llm']
            if 'default' in llm_config:
                # Add new fields for advanced features
                llm_config['default']['conditional_visibility'] = True
                llm_config['default']['advanced_validation'] = True

        # Add schema metadata
        migrated['schema_metadata'] = {
            'version': '2.0.0',
            'migration_applied': True,
            'migration_timestamp': datetime.now().isoformat(),
            'features': ['auto_fix', 'conditional_visibility', 'advanced_organization']
        }

        logger.info('Applied migration 1.1.0 -> 2.0.0: Added advanced organization features')
        return migrated


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

        # Docker and container integration
        self._docker_detector = None
        self._volume_manager = None
        self._container_info = None
        self._use_container_optimizations = False

        # Rollback and snapshot management
        self.snapshots_dir = self.settings_path.parent / 'snapshots'
        self._snapshots_cache: list[SnapshotInfo] = []
        self._rollback_triggers: list[RollbackTrigger] = []
        self._auto_rollback_enabled = True

        # Migration and versioning
        self.migrator = ConfigurationMigrator(self)
        self._schema_versions: list[SchemaVersion] = []

        # Initialize Docker integration if available
        if DOCKER_INTEGRATION_AVAILABLE:
            self._init_docker_integration()

        logger.info(f'Settings service initialized with file: {self.settings_path}')
        if self._is_in_obsidian_vault():
            logger.info('Obsidian vault detected, using vault-relative settings path')
        if self._use_container_optimizations:
            logger.info('Container environment detected, using container-optimized file operations')

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

    def _init_docker_integration(self) -> None:
        """Initialize Docker integration features."""
        try:
            self._docker_detector = DockerEnvironmentDetector()
            self._container_info = self._docker_detector.detect_container_environment()
            self._use_container_optimizations = self._container_info.is_container

            if self._container_info.is_container:
                self._volume_manager = VolumeManager()
                logger.info(f'Detected container environment: {self._container_info.container_runtime}')

                # Set up default rollback triggers for container environments
                self._setup_default_rollback_triggers()

        except Exception as e:
            logger.warning(f'Failed to initialize Docker integration: {e}')
            self._use_container_optimizations = False

    def _setup_default_rollback_triggers(self) -> None:
        """Set up default rollback triggers for container environments."""
        self._rollback_triggers = [
            RollbackTrigger(
                trigger_type='validation_failure',
                description='Settings validation failed',
                enabled=True
            ),
            RollbackTrigger(
                trigger_type='health_check_failure',
                description='Service health check failed after settings change',
                threshold=3,  # Number of consecutive failures
                enabled=True
            ),
            RollbackTrigger(
                trigger_type='service_failure',
                description='Critical service failure detected',
                enabled=True
            )
        ]

    def initialize(self) -> None:
        """Initialize the settings service."""
        # Create backup directory if it doesn't exist
        self.backup_dir.mkdir(exist_ok=True)

        # Create snapshots directory
        self.snapshots_dir.mkdir(exist_ok=True)

        # Load or create default settings
        if not self.settings_path.exists():
            self._create_default_settings()

        # Load settings and schema
        self._load_settings(force=True)
        self._load_schema()

        # Create initial snapshot if in container environment
        if self._use_container_optimizations:
            self._create_initial_snapshot()

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
        """Start watching the settings file for changes with Docker-aware optimizations."""

        class DockerAwareSettingsFileHandler(FileSystemEventHandler):
            def __init__(self, settings_service):
                self.settings_service = settings_service
                self._last_event_time = 0
                self._debounce_interval = 1.0

                # Use container-optimized debounce if in container
                if settings_service._use_container_optimizations:
                    optimizations = settings_service._docker_detector.optimize_for_container_performance()
                    self._debounce_interval = optimizations['file_watching'].get('debounce_time', 1.0)

            def on_modified(self, event):
                if not event.is_directory and event.src_path.endswith('thoth.settings.json'):
                    current_time = time.time()

                    # Debounce file events (especially important in containers)
                    if current_time - self._last_event_time < self._debounce_interval:
                        return

                    self._last_event_time = current_time
                    logger.info('Settings file changed, reloading...')

                    # Create snapshot before loading new settings
                    if self.settings_service._use_container_optimizations:
                        self.settings_service._create_auto_snapshot('file_change')

                    settings = self.settings_service.load_settings(force=True)
                    self.settings_service._notify_callbacks('modified', settings)

        # Choose observer type based on container environment
        if self._use_container_optimizations:
            # Use polling observer in containers for better reliability
            optimizations = self._docker_detector.optimize_for_container_performance()
            poll_interval = optimizations['file_watching'].get('poll_interval', 2.0)

            self._file_observer = PollingObserver(timeout=poll_interval)
            logger.info(f'Using polling file observer with {poll_interval}s interval for container environment')
        else:
            # Use standard observer for native environments
            self._file_observer = Observer()
            logger.info('Using standard file observer for native environment')

        handler = DockerAwareSettingsFileHandler(self)
        self._file_observer.schedule(
            handler, path=str(self.settings_path.parent), recursive=False
        )
        self._file_observer.start()
        logger.info('Started Docker-aware settings file watcher')

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

    # Docker-aware rollback and snapshot methods

    def _create_initial_snapshot(self) -> None:
        """Create initial snapshot if in container environment."""
        try:
            if self.settings_path.exists():
                snapshot_id = self.create_configuration_snapshot('initial_container_setup')
                logger.info(f'Created initial container snapshot: {snapshot_id}')
        except Exception as e:
            logger.warning(f'Failed to create initial snapshot: {e}')

    def _create_auto_snapshot(self, description: str) -> str | None:
        """Create automatic snapshot before configuration changes."""
        try:
            return self.create_configuration_snapshot(f'auto_{description}_{int(time.time())}')
        except Exception as e:
            logger.warning(f'Failed to create auto snapshot: {e}')
            return None

    def create_configuration_snapshot(self, description: str = '') -> str:
        """
        Create a configuration snapshot for rollback capability.
        
        Args:
            description: Description of the snapshot
            
        Returns:
            Snapshot ID
        """
        try:
            # Ensure snapshots directory exists
            self.snapshots_dir.mkdir(parents=True, exist_ok=True)

            # Generate snapshot ID
            timestamp = datetime.now()
            snapshot_id = f'snapshot_{timestamp.strftime("%Y%m%d_%H%M%S")}_{len(self._snapshots_cache)}'

            # Create snapshot file
            snapshot_file = self.snapshots_dir / f'{snapshot_id}.json'

            if self.settings_path.exists():
                # Copy current settings to snapshot
                shutil.copy2(self.settings_path, snapshot_file)
                file_size = snapshot_file.stat().st_size

                # Get settings version
                settings = self.load_settings()
                settings_version = settings.get('version', 'unknown')
            else:
                # Create empty snapshot for missing file
                snapshot_file.touch()
                file_size = 0
                settings_version = 'missing'

            # Create snapshot info
            snapshot_info = SnapshotInfo(
                snapshot_id=snapshot_id,
                timestamp=timestamp,
                description=description or f'Snapshot created at {timestamp.isoformat()}',
                file_path=snapshot_file,
                settings_version=settings_version,
                file_size=file_size
            )

            # Add to cache
            self._snapshots_cache.append(snapshot_info)

            # Clean up old snapshots (keep last 20)
            self._cleanup_old_snapshots()

            logger.info(f'Created configuration snapshot: {snapshot_id}')
            return snapshot_id

        except Exception as e:
            logger.error(f'Failed to create configuration snapshot: {e}')
            raise

    def rollback_to_snapshot(self, snapshot_id: str) -> RollbackResult:
        """
        Rollback configuration to a specific snapshot.
        
        Args:
            snapshot_id: ID of the snapshot to rollback to
            
        Returns:
            RollbackResult with operation details
        """
        try:
            # Find snapshot
            snapshot_info = None
            for snapshot in self._snapshots_cache:
                if snapshot.snapshot_id == snapshot_id:
                    snapshot_info = snapshot
                    break

            if not snapshot_info:
                return RollbackResult(
                    success=False,
                    snapshot_id=snapshot_id,
                    error_message=f'Snapshot {snapshot_id} not found'
                )

            # Validate snapshot file exists
            if not snapshot_info.file_path.exists():
                return RollbackResult(
                    success=False,
                    snapshot_id=snapshot_id,
                    error_message=f'Snapshot file not found: {snapshot_info.file_path}'
                )

            # Create backup of current settings before rollback
            backup_snapshot_id = None
            if self.settings_path.exists():
                backup_snapshot_id = self._create_auto_snapshot('pre_rollback_backup')

            # Restore from snapshot
            if snapshot_info.file_size > 0:
                shutil.copy2(snapshot_info.file_path, self.settings_path)
                files_restored = 1
            else:
                # Snapshot represents missing file - remove current file
                if self.settings_path.exists():
                    self.settings_path.unlink()
                files_restored = 0

            # Clear cache to force reload
            self._settings_cache = None
            self._last_modified = None

            logger.info(f'Successfully rolled back to snapshot: {snapshot_id}')

            return RollbackResult(
                success=True,
                snapshot_id=snapshot_id,
                files_restored=files_restored,
                rollback_timestamp=datetime.now()
            )

        except Exception as e:
            logger.error(f'Failed to rollback to snapshot {snapshot_id}: {e}')
            return RollbackResult(
                success=False,
                snapshot_id=snapshot_id,
                error_message=str(e)
            )

    def detect_rollback_triggers(self) -> list[RollbackTrigger]:
        """
        Detect active rollback triggers.
        
        Returns:
            List of active rollback triggers
        """
        return [trigger for trigger in self._rollback_triggers if trigger.enabled]

    def execute_automatic_rollback(self, trigger: RollbackTrigger) -> RollbackResult:
        """
        Execute automatic rollback based on a trigger.
        
        Args:
            trigger: The rollback trigger that was activated
            
        Returns:
            RollbackResult with operation details
        """
        try:
            if not self._auto_rollback_enabled:
                return RollbackResult(
                    success=False,
                    snapshot_id='',
                    error_message='Automatic rollback is disabled'
                )

            # Find most recent snapshot (excluding auto backups)
            valid_snapshots = [
                s for s in self._snapshots_cache
                if not s.description.startswith('auto_pre_rollback')
            ]

            if not valid_snapshots:
                return RollbackResult(
                    success=False,
                    snapshot_id='',
                    error_message='No valid snapshots available for rollback'
                )

            # Use most recent snapshot
            latest_snapshot = max(valid_snapshots, key=lambda s: s.timestamp)

            logger.warning(f'Executing automatic rollback due to {trigger.trigger_type}: {trigger.description}')
            return self.rollback_to_snapshot(latest_snapshot.snapshot_id)

        except Exception as e:
            logger.error(f'Failed to execute automatic rollback: {e}')
            return RollbackResult(
                success=False,
                snapshot_id='',
                error_message=str(e)
            )

    def get_rollback_history(self) -> list[SnapshotInfo]:
        """
        Get rollback history (snapshots).
        
        Returns:
            List of available snapshots
        """
        # Refresh cache from disk
        self._refresh_snapshots_cache()
        return self._snapshots_cache.copy()

    def _refresh_snapshots_cache(self) -> None:
        """Refresh snapshots cache from disk."""
        self._snapshots_cache.clear()

        if not self.snapshots_dir.exists():
            return

        for snapshot_file in self.snapshots_dir.glob('snapshot_*.json'):
            try:
                # Parse snapshot ID and timestamp from filename
                filename = snapshot_file.stem
                parts = filename.split('_')
                if len(parts) >= 3:
                    date_str = parts[1]
                    time_str = parts[2]
                    timestamp = datetime.strptime(f'{date_str}_{time_str}', '%Y%m%d_%H%M%S')

                    # Get file info
                    file_size = snapshot_file.stat().st_size

                    # Try to get settings version
                    settings_version = 'unknown'
                    if file_size > 0:
                        try:
                            with open(snapshot_file) as f:
                                snapshot_settings = json.load(f)
                                settings_version = snapshot_settings.get('version', 'unknown')
                        except Exception:
                            pass

                    snapshot_info = SnapshotInfo(
                        snapshot_id=filename,
                        timestamp=timestamp,
                        description=f'Snapshot from {timestamp.isoformat()}',
                        file_path=snapshot_file,
                        settings_version=settings_version,
                        file_size=file_size
                    )

                    self._snapshots_cache.append(snapshot_info)

            except Exception as e:
                logger.warning(f'Failed to process snapshot file {snapshot_file}: {e}')

        # Sort by timestamp
        self._snapshots_cache.sort(key=lambda s: s.timestamp)

    def _cleanup_old_snapshots(self, keep_count: int = 20) -> None:
        """Clean up old snapshot files."""
        try:
            if len(self._snapshots_cache) <= keep_count:
                return

            # Sort by timestamp and remove oldest
            self._snapshots_cache.sort(key=lambda s: s.timestamp)
            snapshots_to_remove = self._snapshots_cache[:-keep_count]

            for snapshot in snapshots_to_remove:
                try:
                    snapshot.file_path.unlink()
                    logger.debug(f'Removed old snapshot: {snapshot.snapshot_id}')
                except Exception as e:
                    logger.warning(f'Failed to remove old snapshot {snapshot.snapshot_id}: {e}')

            # Update cache
            self._snapshots_cache = self._snapshots_cache[-keep_count:]

        except Exception as e:
            logger.warning(f'Failed to cleanup old snapshots: {e}')

    def get_docker_volume_info(self) -> dict[str, Any] | None:
        """
        Get Docker volume information for settings persistence.
        
        Returns:
            Volume information if in container, None otherwise
        """
        if not self._use_container_optimizations or not self._volume_manager:
            return None

        try:
            # Get volume info for settings path
            volume_info = self._docker_detector.get_volume_mount_info(str(self.settings_path.parent))

            if volume_info:
                return {
                    'host_path': volume_info.host_path,
                    'container_path': volume_info.container_path,
                    'volume_type': volume_info.volume_type,
                    'read_only': volume_info.read_only,
                    'volume_name': volume_info.volume_name
                }

            return None

        except Exception as e:
            logger.warning(f'Failed to get Docker volume info: {e}')
            return None

    def ensure_container_persistence(self) -> bool:
        """
        Ensure settings are persisted in container environment.
        
        Returns:
            True if persistence is ensured, False otherwise
        """
        if not self._use_container_optimizations or not self._volume_manager:
            return True  # Not in container, no action needed

        try:
            result = self._volume_manager.ensure_settings_persistence(str(self.settings_path))

            if result.success and result.volume_path != str(self.settings_path):
                # Settings were moved to a persistent volume
                self.settings_path = Path(result.volume_path)
                logger.info(f'Settings moved to persistent volume: {self.settings_path}')

                # Update related paths
                self.schema_path = self.settings_path.parent / 'thoth.settings.schema.json'
                self.backup_dir = self.settings_path.parent / 'settings_backups'
                self.snapshots_dir = self.settings_path.parent / 'snapshots'

                # Restart file watcher with new path
                if self._file_observer:
                    self._file_observer.stop()
                    self._file_observer.join()
                    self._file_observer = None

                if self._callbacks:
                    self._start_file_watcher()

            return result.success

        except Exception as e:
            logger.error(f'Failed to ensure container persistence: {e}')
            return False

    # Migration and versioning methods

    def check_migration_needs(self) -> MigrationInfo | None:
        """Check if configuration migration is needed."""
        try:
            current_config = self.load_settings()
            return self.migrator.detect_migration_needs(current_config)
        except Exception as e:
            logger.error(f'Failed to check migration needs: {e}')
            return None

    def execute_migration(self, migration_info: MigrationInfo) -> MigrationResult:
        """Execute a configuration migration."""
        return self.migrator.execute_migration(migration_info)

    def rollback_migration(self, backup_path: str) -> MigrationResult:
        """Rollback a failed migration."""
        return self.migrator.rollback_migration(backup_path)

    def get_migration_history(self) -> list[MigrationInfo]:
        """Get migration history."""
        return self.migrator.get_migration_history()

    def get_current_schema_version(self) -> str:
        """Get current schema version from settings."""
        try:
            settings = self.load_settings()
            return settings.get('version', '1.0.0')
        except Exception:
            return '1.0.0'

    def get_available_schema_versions(self) -> list[SchemaVersion]:
        """Get list of available schema versions."""
        return [
            SchemaVersion(
                version='1.0.0',
                timestamp=datetime(2024, 1, 1),
                description='Initial schema version',
                breaking_changes=False,
                migration_required=False,
                compatibility_notes=['Basic configuration structure']
            ),
            SchemaVersion(
                version='1.1.0',
                timestamp=datetime(2024, 6, 1),
                description='Added performance monitoring',
                breaking_changes=False,
                migration_required=True,
                compatibility_notes=['Added performance_config section', 'Added monitoring settings']
            ),
            SchemaVersion(
                version='2.0.0',
                timestamp=datetime(2024, 12, 1),
                description='Advanced organization and auto-fix features',
                breaking_changes=True,
                migration_required=True,
                compatibility_notes=[
                    'Reorganized field groups',
                    'Added conditional visibility',
                    'Enhanced validation with auto-fix',
                    'New schema metadata structure'
                ]
            )
        ]

    def is_migration_available(self, from_version: str, to_version: str) -> bool:
        """Check if migration is available between versions."""
        migration_key = f'{from_version}_to_{to_version}'
        return migration_key in self.migrator.migrations

    def validate_schema_compatibility(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate schema compatibility for current configuration."""
        issues = []

        current_version = config.get('version', '1.0.0')
        available_versions = [v.version for v in self.get_available_schema_versions()]

        if current_version not in available_versions:
            issues.append(f'Unknown schema version: {current_version}')

        # Check for required fields based on version
        if current_version >= '1.1.0':
            if 'performance_config' not in config:
                issues.append('Missing performance_config section (required in v1.1.0+)')

        if current_version >= '2.0.0':
            if 'schema_metadata' not in config:
                issues.append('Missing schema_metadata section (required in v2.0.0+)')

        return len(issues) == 0, issues

    def auto_migrate_if_needed(self) -> MigrationResult | None:
        """Automatically migrate configuration if needed and safe."""
        migration_info = self.check_migration_needs()

        if not migration_info:
            return None

        # Only auto-migrate for non-breaking changes
        from_schema = next((v for v in self.get_available_schema_versions() if v.version == migration_info.from_version), None)
        to_schema = next((v for v in self.get_available_schema_versions() if v.version == migration_info.to_version), None)

        if to_schema and to_schema.breaking_changes:
            logger.info(f'Migration {migration_info.from_version} -> {migration_info.to_version} requires manual intervention (breaking changes)')
            return None

        logger.info(f'Auto-migrating configuration from {migration_info.from_version} to {migration_info.to_version}')
        return self.execute_migration(migration_info)

    def export_configuration_for_migration(self) -> dict[str, Any]:
        """Export configuration with migration metadata."""
        config = self.load_settings()

        # Add migration metadata
        config['_migration_export'] = {
            'exported_at': datetime.now().isoformat(),
            'source_version': config.get('version', '1.0.0'),
            'export_format': 'thoth_settings_v2',
            'compatibility_info': {
                'requires_migration': True,
                'breaking_changes': False,
                'notes': 'Exported for migration purposes'
            }
        }

        return config

    def import_configuration_from_migration(self, imported_config: dict[str, Any]) -> bool:
        """Import configuration from migration export."""
        try:
            # Validate import format
            if '_migration_export' not in imported_config:
                raise ValueError('Invalid migration export format')

            # Remove migration metadata
            config = imported_config.copy()
            del config['_migration_export']

            # Check if migration is needed
            migration_info = self.migrator.detect_migration_needs(config)
            if migration_info:
                # Execute migration
                result = self.execute_migration(migration_info)
                if not result.success:
                    raise ValueError(f'Migration failed: {result.error_message}')
            else:
                # Save directly if no migration needed
                success = self.save_settings(config)
                if not success:
                    raise ValueError('Failed to save imported configuration')

            logger.info('Successfully imported configuration from migration')
            return True

        except Exception as e:
            logger.error(f'Failed to import configuration: {e}')
            return False

    def cleanup(self) -> None:
        """Clean up resources."""
        if self._file_observer and self._file_observer.is_alive():
            self._file_observer.stop()
            self._file_observer.join()
            logger.info('Stopped settings file watcher')
