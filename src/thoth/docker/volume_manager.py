"""
Docker volume manager for handling container persistence and volume operations.

This module provides comprehensive volume management for Docker containers,
ensuring data persistence across container lifecycles.
"""

import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from loguru import logger

from .container_utils import DockerEnvironmentDetector, VolumeInfo


@dataclass
class VolumeHealthStatus:
    """Health status information for a volume."""

    is_healthy: bool
    volume_path: str
    is_accessible: bool = False
    is_writable: bool = False
    free_space_mb: float | None = None
    total_space_mb: float | None = None
    mount_type: str | None = None
    error_message: str | None = None


@dataclass
class PersistenceResult:
    """Result of a persistence operation."""

    success: bool
    volume_path: str
    backup_path: str | None = None
    error_message: str | None = None
    bytes_written: int | None = None


@dataclass
class BackupResult:
    """Result of a backup operation."""

    success: bool
    backup_path: str
    source_path: str
    backup_size_bytes: int | None = None
    error_message: str | None = None


@dataclass
class MigrationResult:
    """Result of a volume migration operation."""

    success: bool
    source_volume: str
    target_volume: str
    files_migrated: int = 0
    bytes_migrated: int = 0
    error_message: str | None = None


class VolumeManager:
    """
    Manages Docker volumes for settings persistence and data management.

    This class provides comprehensive volume management including:
    - Volume discovery and health monitoring
    - Settings persistence across container restarts
    - Backup and restore operations
    - Volume migration capabilities
    """

    def __init__(self):
        """Initialize the volume manager."""
        self.detector = DockerEnvironmentDetector()
        self._volume_cache: list[VolumeInfo] | None = None
        self._health_cache: dict[str, VolumeHealthStatus] = {}
        self._cache_timeout = 60  # seconds
        self._last_cache_update = 0

    def discover_settings_volumes(self) -> list[VolumeInfo]:
        """
        Discover Docker volumes that might contain settings data.

        Returns:
            List of VolumeInfo objects for potential settings volumes
        """
        current_time = time.time()

        # Use cache if it's still valid
        if (
            self._volume_cache is not None
            and current_time - self._last_cache_update < self._cache_timeout
        ):
            return self._volume_cache

        all_volumes = self.detector.get_all_volume_mounts()
        settings_volumes = []

        # Look for volumes that might contain settings
        settings_indicators = [
            'config',
            'settings',
            'data',
            'app',
            'workspace',
            'thoth',
            'persistent',
            'storage',
        ]

        for volume in all_volumes:
            # Check if volume path contains settings indicators
            path_lower = volume.container_path.lower()
            if any(indicator in path_lower for indicator in settings_indicators):
                settings_volumes.append(volume)
                logger.debug(
                    f'Found potential settings volume: {volume.container_path}'
                )

            # Also check if volume is writable and not a system mount
            elif not volume.read_only and not volume.container_path.startswith(
                ('/proc', '/sys', '/dev', '/tmp')
            ):
                settings_volumes.append(volume)

        self._volume_cache = settings_volumes
        self._last_cache_update = current_time

        logger.info(f'Discovered {len(settings_volumes)} potential settings volumes')
        return settings_volumes

    def ensure_settings_persistence(self, settings_path: str) -> PersistenceResult:
        """
        Ensure settings file is stored on a persistent volume.

        Args:
            settings_path: Path to the settings file

        Returns:
            PersistenceResult indicating success and details
        """
        try:
            settings_file = Path(settings_path)

            # Check if settings file is already on a persistent volume
            volume_info = self.detector.get_volume_mount_info(str(settings_file.parent))

            if volume_info and not volume_info.read_only:
                logger.info(
                    f'Settings file already on persistent volume: {volume_info.container_path}'
                )
                return PersistenceResult(
                    success=True,
                    volume_path=volume_info.container_path,
                    error_message=None,
                )

            # Find best volume for settings persistence
            best_volume = self._find_best_volume_for_settings()

            if not best_volume:
                return PersistenceResult(
                    success=False,
                    volume_path='',
                    error_message='No suitable persistent volume found for settings',
                )

            # Move settings to persistent volume
            persistent_settings_path = (
                Path(best_volume.container_path) / 'thoth.settings.json'
            )

            # Create directory if needed
            persistent_settings_path.parent.mkdir(parents=True, exist_ok=True)

            # Copy current settings if they exist
            bytes_written = 0
            if settings_file.exists():
                shutil.copy2(settings_file, persistent_settings_path)
                bytes_written = persistent_settings_path.stat().st_size
                logger.info(
                    f'Moved settings to persistent volume: {persistent_settings_path}'
                )
            else:
                # Create empty settings file on persistent volume
                persistent_settings_path.touch()
                logger.info(
                    f'Created settings file on persistent volume: {persistent_settings_path}'
                )

            return PersistenceResult(
                success=True,
                volume_path=str(persistent_settings_path),
                bytes_written=bytes_written,
            )

        except Exception as e:
            logger.error(f'Failed to ensure settings persistence: {e}')
            return PersistenceResult(
                success=False, volume_path='', error_message=str(e)
            )

    def _find_best_volume_for_settings(self) -> VolumeInfo | None:
        """Find the best volume for storing settings."""
        volumes = self.discover_settings_volumes()

        if not volumes:
            return None

        # Score volumes based on suitability for settings
        scored_volumes = []

        for volume in volumes:
            if volume.read_only:
                continue  # Skip read-only volumes

            score = 0
            path_lower = volume.container_path.lower()

            # Prefer volumes with specific indicators
            if 'config' in path_lower or 'settings' in path_lower:
                score += 100
            elif 'data' in path_lower or 'persistent' in path_lower:
                score += 50
            elif 'app' in path_lower or 'workspace' in path_lower:
                score += 30

            # Prefer bind mounts over volumes for settings (easier to access)
            if volume.volume_type == 'bind':
                score += 20
            elif volume.volume_type == 'volume':
                score += 10

            # Check volume health
            health = self.monitor_volume_health(volume.container_path)
            if health.is_healthy and health.is_writable:
                score += 25

            scored_volumes.append((score, volume))

        if scored_volumes:
            # Return volume with highest score
            scored_volumes.sort(key=lambda x: x[0], reverse=True)
            return scored_volumes[0][1]

        return None

    def monitor_volume_health(self, volume_path: str) -> VolumeHealthStatus:
        """
        Monitor the health of a specific volume.

        Args:
            volume_path: Path to the volume to monitor

        Returns:
            VolumeHealthStatus with health information
        """
        # Check cache first
        if volume_path in self._health_cache:
            cached_health = self._health_cache[volume_path]
            # Use cache for 30 seconds
            if time.time() - self._last_cache_update < 30:
                return cached_health

        try:
            path_obj = Path(volume_path)

            # Check if path exists and is accessible
            is_accessible = path_obj.exists()
            is_writable = False
            free_space_mb = None
            total_space_mb = None
            error_message = None

            if is_accessible:
                try:
                    # Test write access
                    test_file = path_obj / '.thoth_write_test'
                    test_file.touch()
                    test_file.unlink()
                    is_writable = True
                except Exception as write_error:
                    error_message = f'Write test failed: {write_error}'

                # Get disk space information
                try:
                    import shutil

                    total_bytes, used_bytes, free_bytes = shutil.disk_usage(path_obj)
                    free_space_mb = free_bytes / (1024 * 1024)
                    total_space_mb = total_bytes / (1024 * 1024)
                except Exception as space_error:
                    logger.debug(
                        f'Could not get disk space for {volume_path}: {space_error}'
                    )
            else:
                error_message = f'Volume path {volume_path} is not accessible'

            # Get mount type
            volume_info = self.detector.get_volume_mount_info(volume_path)
            mount_type = volume_info.volume_type if volume_info else 'unknown'

            is_healthy = (
                is_accessible
                and is_writable
                and (free_space_mb is None or free_space_mb > 100)
            )

            health_status = VolumeHealthStatus(
                is_healthy=is_healthy,
                volume_path=volume_path,
                is_accessible=is_accessible,
                is_writable=is_writable,
                free_space_mb=free_space_mb,
                total_space_mb=total_space_mb,
                mount_type=mount_type,
                error_message=error_message,
            )

            # Cache the result
            self._health_cache[volume_path] = health_status

            return health_status

        except Exception as e:
            logger.error(f'Error monitoring volume health for {volume_path}: {e}')
            return VolumeHealthStatus(
                is_healthy=False, volume_path=volume_path, error_message=str(e)
            )

    def backup_settings_to_volume(
        self, settings_path: str, volume_info: VolumeInfo
    ) -> BackupResult:
        """
        Backup settings to a specific volume.

        Args:
            settings_path: Path to the settings file to backup
            volume_info: Volume to backup to

        Returns:
            BackupResult with backup operation details
        """
        try:
            source_path = Path(settings_path)

            if not source_path.exists():
                return BackupResult(
                    success=False,
                    backup_path='',
                    source_path=str(source_path),
                    error_message='Source settings file does not exist',
                )

            # Create backup directory on volume
            backup_dir = Path(volume_info.container_path) / 'backups' / 'settings'
            backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename with timestamp
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            backup_filename = f'thoth_settings_backup_{timestamp}.json'
            backup_path = backup_dir / backup_filename

            # Copy settings file to backup location
            shutil.copy2(source_path, backup_path)
            backup_size = backup_path.stat().st_size

            logger.info(f'Settings backed up to: {backup_path}')

            # Clean up old backups (keep last 10)
            self._cleanup_old_backups(backup_dir, keep_count=10)

            return BackupResult(
                success=True,
                backup_path=str(backup_path),
                source_path=str(source_path),
                backup_size_bytes=backup_size,
            )

        except Exception as e:
            logger.error(f'Failed to backup settings to volume: {e}')
            return BackupResult(
                success=False,
                backup_path='',
                source_path=str(settings_path),
                error_message=str(e),
            )

    def _cleanup_old_backups(self, backup_dir: Path, keep_count: int = 10) -> None:
        """Clean up old backup files."""
        try:
            backup_files = list(backup_dir.glob('thoth_settings_backup_*.json'))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Remove old backups
            for old_backup in backup_files[keep_count:]:
                old_backup.unlink()
                logger.debug(f'Removed old backup: {old_backup}')

        except Exception as e:
            logger.warning(f'Failed to cleanup old backups: {e}')

    def migrate_settings_between_volumes(
        self, source_volume: VolumeInfo, target_volume: VolumeInfo
    ) -> MigrationResult:
        """
        Migrate settings and data between volumes.

        Args:
            source_volume: Source volume to migrate from
            target_volume: Target volume to migrate to

        Returns:
            MigrationResult with migration details
        """
        try:
            source_path = Path(source_volume.container_path)
            target_path = Path(target_volume.container_path)

            # Check if source exists
            if not source_path.exists():
                return MigrationResult(
                    success=False,
                    source_volume=source_volume.container_path,
                    target_volume=target_volume.container_path,
                    error_message='Source volume path does not exist',
                )

            # Check if target is writable
            target_health = self.monitor_volume_health(target_volume.container_path)
            if not target_health.is_writable:
                return MigrationResult(
                    success=False,
                    source_volume=source_volume.container_path,
                    target_volume=target_volume.container_path,
                    error_message='Target volume is not writable',
                )

            # Create target directory
            target_path.mkdir(parents=True, exist_ok=True)

            files_migrated = 0
            bytes_migrated = 0

            # Find settings files to migrate
            settings_patterns = [
                'thoth.settings.json',
                '*.thoth.settings.json',
                'settings_backup_*.json',
                'config.json',
                'thoth_config.*',
            ]

            for pattern in settings_patterns:
                for source_file in source_path.glob(pattern):
                    if source_file.is_file():
                        target_file = target_path / source_file.name

                        # Copy file
                        shutil.copy2(source_file, target_file)
                        file_size = target_file.stat().st_size

                        files_migrated += 1
                        bytes_migrated += file_size

                        logger.info(f'Migrated: {source_file} -> {target_file}')

            # Also migrate any backup directories
            backup_dirs = [
                d
                for d in source_path.iterdir()
                if d.is_dir() and 'backup' in d.name.lower()
            ]

            for backup_dir in backup_dirs:
                target_backup_dir = target_path / backup_dir.name
                if not target_backup_dir.exists():
                    shutil.copytree(backup_dir, target_backup_dir)

                    # Count files and sizes
                    for file_path in target_backup_dir.rglob('*'):
                        if file_path.is_file():
                            files_migrated += 1
                            bytes_migrated += file_path.stat().st_size

            logger.info(
                f'Migration completed: {files_migrated} files, {bytes_migrated} bytes'
            )

            return MigrationResult(
                success=True,
                source_volume=source_volume.container_path,
                target_volume=target_volume.container_path,
                files_migrated=files_migrated,
                bytes_migrated=bytes_migrated,
            )

        except Exception as e:
            logger.error(f'Failed to migrate settings between volumes: {e}')
            return MigrationResult(
                success=False,
                source_volume=source_volume.container_path,
                target_volume=target_volume.container_path,
                error_message=str(e),
            )

    def get_volume_usage_report(self) -> dict[str, Any]:
        """
        Generate a comprehensive volume usage report.

        Returns:
            Dictionary with volume usage information
        """
        volumes = self.discover_settings_volumes()
        report = {
            'total_volumes': len(volumes),
            'healthy_volumes': 0,
            'volumes': [],
            'recommendations': [],
        }

        for volume in volumes:
            health = self.monitor_volume_health(volume.container_path)

            volume_report = {
                'path': volume.container_path,
                'type': volume.volume_type,
                'read_only': volume.read_only,
                'is_healthy': health.is_healthy,
                'is_writable': health.is_writable,
                'free_space_mb': health.free_space_mb,
                'total_space_mb': health.total_space_mb,
                'usage_percent': None,
            }

            if health.free_space_mb and health.total_space_mb:
                used_space = health.total_space_mb - health.free_space_mb
                volume_report['usage_percent'] = (
                    used_space / health.total_space_mb
                ) * 100

            if health.is_healthy:
                report['healthy_volumes'] += 1

            report['volumes'].append(volume_report)

        # Generate recommendations
        if report['healthy_volumes'] == 0:
            report['recommendations'].append(
                'No healthy volumes found for settings persistence'
            )
        elif report['healthy_volumes'] == 1:
            report['recommendations'].append(
                'Consider adding additional volumes for redundancy'
            )

        # Check for high usage volumes
        for volume_info in report['volumes']:
            if volume_info['usage_percent'] and volume_info['usage_percent'] > 90:
                report['recommendations'].append(
                    f'Volume {volume_info["path"]} is {volume_info["usage_percent"]:.1f}% full'
                )

        return report
