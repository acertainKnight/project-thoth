"""
Transaction-based rollback system for wizard operations.

Provides error recovery by reversing actions in case of failure.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


class ActionType(Enum):
    """Types of reversible actions."""

    CREATE_DIRECTORY = 'create_directory'
    WRITE_FILE = 'write_file'
    BACKUP_FILE = 'backup_file'
    START_DOCKER_SERVICE = 'start_docker_service'
    MODIFY_CONFIG = 'modify_config'


@dataclass
class Action:
    """Record of a reversible action."""

    type: ActionType
    data: dict[str, Any]
    timestamp: datetime
    description: str

    def __str__(self) -> str:
        """String representation of action."""
        return f'[{self.timestamp.isoformat()}] {self.type.value}: {self.description}'


class Transaction:
    """Transaction manager for rollback capability."""

    def __init__(self) -> None:
        """Initialize transaction."""
        self.actions: list[Action] = []
        self.completed = False

    def record_create_directory(self, path: Path) -> None:
        """
        Record directory creation.

        Args:
            path: Directory path that was created
        """
        action = Action(
            type=ActionType.CREATE_DIRECTORY,
            data={'path': str(path)},
            timestamp=datetime.now(),
            description=f'Created directory {path}',
        )
        self.actions.append(action)
        logger.debug(f'Recorded action: {action}')

    def record_write_file(self, path: Path, backup_path: Path | None = None) -> None:
        """
        Record file write.

        Args:
            path: File path that was written
            backup_path: Optional backup file location
        """
        action = Action(
            type=ActionType.WRITE_FILE,
            data={
                'path': str(path),
                'backup_path': str(backup_path) if backup_path else None,
            },
            timestamp=datetime.now(),
            description=f'Wrote file {path}',
        )
        self.actions.append(action)
        logger.debug(f'Recorded action: {action}')

    def record_backup_file(self, original: Path, backup: Path) -> None:
        """
        Record file backup.

        Args:
            original: Original file path
            backup: Backup file path
        """
        action = Action(
            type=ActionType.BACKUP_FILE,
            data={'original': str(original), 'backup': str(backup)},
            timestamp=datetime.now(),
            description=f'Backed up {original} to {backup}',
        )
        self.actions.append(action)
        logger.debug(f'Recorded action: {action}')

    def record_start_docker_service(self, service: str, compose_file: Path) -> None:
        """
        Record Docker service start.

        Args:
            service: Service name
            compose_file: Docker Compose file path
        """
        action = Action(
            type=ActionType.START_DOCKER_SERVICE,
            data={'service': service, 'compose_file': str(compose_file)},
            timestamp=datetime.now(),
            description=f'Started Docker service {service}',
        )
        self.actions.append(action)
        logger.debug(f'Recorded action: {action}')

    def record_modify_config(self, config_path: Path, backup_path: Path) -> None:
        """
        Record configuration modification.

        Args:
            config_path: Configuration file path
            backup_path: Backup of original config
        """
        action = Action(
            type=ActionType.MODIFY_CONFIG,
            data={'config_path': str(config_path), 'backup_path': str(backup_path)},
            timestamp=datetime.now(),
            description=f'Modified config {config_path}',
        )
        self.actions.append(action)
        logger.debug(f'Recorded action: {action}')

    def commit(self) -> None:
        """Mark transaction as successfully completed."""
        self.completed = True
        logger.info(f'Transaction committed with {len(self.actions)} actions')

    def rollback(self) -> None:
        """
        Rollback all actions in reverse order.

        Attempts to undo all recorded actions. Logs errors but continues
        rolling back remaining actions.
        """
        if self.completed:
            logger.warning('Attempted to rollback completed transaction')
            return

        logger.warning(f'Rolling back transaction with {len(self.actions)} actions')

        # Reverse actions
        for action in reversed(self.actions):
            try:
                self._rollback_action(action)
            except Exception as e:
                logger.error(f'Failed to rollback action {action}: {e}')
                # Continue with remaining rollbacks

        self.actions.clear()
        logger.info('Transaction rollback complete')

    def _rollback_action(self, action: Action) -> None:
        """
        Rollback a single action.

        Args:
            action: Action to rollback
        """
        logger.info(f'Rolling back: {action}')

        if action.type == ActionType.CREATE_DIRECTORY:
            self._rollback_create_directory(action)
        elif action.type == ActionType.WRITE_FILE:
            self._rollback_write_file(action)
        elif action.type == ActionType.BACKUP_FILE:
            self._rollback_backup_file(action)
        elif action.type == ActionType.START_DOCKER_SERVICE:
            self._rollback_start_docker_service(action)
        elif action.type == ActionType.MODIFY_CONFIG:
            self._rollback_modify_config(action)
        else:
            logger.warning(f'Unknown action type: {action.type}')

    def _rollback_create_directory(self, action: Action) -> None:
        """
        Rollback directory creation.

        Args:
            action: Create directory action
        """
        path = Path(action.data['path'])
        if path.exists() and path.is_dir():
            # Only remove if empty
            if not any(path.iterdir()):
                path.rmdir()
                logger.info(f'Removed directory: {path}')
            else:
                logger.warning(f'Directory not empty, skipping removal: {path}')

    def _rollback_write_file(self, action: Action) -> None:
        """
        Rollback file write.

        Args:
            action: Write file action
        """
        path = Path(action.data['path'])
        backup_path_str = action.data.get('backup_path')

        if backup_path_str:
            # Restore from backup
            backup_path = Path(backup_path_str)
            if backup_path.exists():
                shutil.copy2(backup_path, path)
                logger.info(f'Restored {path} from backup')
            else:
                logger.warning(f'Backup not found: {backup_path}')
        else:
            # No backup, just remove the file
            if path.exists():
                path.unlink()
                logger.info(f'Removed file: {path}')

    def _rollback_backup_file(self, action: Action) -> None:
        """
        Rollback file backup (remove backup).

        Args:
            action: Backup file action
        """
        backup_path = Path(action.data['backup'])
        if backup_path.exists():
            backup_path.unlink()
            logger.info(f'Removed backup: {backup_path}')

    def _rollback_start_docker_service(self, action: Action) -> None:
        """
        Rollback Docker service start (stop service).

        Args:
            action: Start Docker service action
        """
        import subprocess

        service = action.data['service']
        compose_file = Path(action.data['compose_file'])

        if compose_file.exists():
            try:
                result = subprocess.run(
                    ['docker', 'compose', '-f', str(compose_file), 'stop', service],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )

                if result.returncode == 0:
                    logger.info(f'Stopped Docker service: {service}')
                else:
                    logger.warning(f'Failed to stop service {service}: {result.stderr}')

            except subprocess.TimeoutExpired:
                logger.error(f'Timeout stopping Docker service: {service}')
            except Exception as e:
                logger.error(f'Error stopping Docker service {service}: {e}')

    def _rollback_modify_config(self, action: Action) -> None:
        """
        Rollback configuration modification (restore backup).

        Args:
            action: Modify config action
        """
        config_path = Path(action.data['config_path'])
        backup_path = Path(action.data['backup_path'])

        if backup_path.exists():
            shutil.copy2(backup_path, config_path)
            logger.info(f'Restored config from backup: {config_path}')
        else:
            logger.warning(f'Backup not found for config: {backup_path}')
