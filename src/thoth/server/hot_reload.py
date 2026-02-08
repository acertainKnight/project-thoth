"""
Settings file watcher for hot-reload functionality.

Monitors vault/thoth/_thoth/settings.json and triggers config reloads
without requiring container restarts.
"""

from pathlib import Path  # noqa: I001
from typing import Callable, List  # noqa: UP035
import asyncio  # noqa: F401
import json
import threading
from loguru import logger

# Optional watchdog dependency for hot-reload functionality
# Not required for production MCP service
try:
    from watchdog.observers import Observer  # noqa: I001
    from watchdog.events import FileSystemEventHandler, FileSystemEvent

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    # Define stub classes for type hints
    class Observer:  # type: ignore
        pass

    class FileSystemEventHandler:  # type: ignore
        pass

    class FileSystemEvent:  # type: ignore
        pass


class SettingsFileWatcher:
    """Watches settings.json for changes and triggers reload callbacks."""

    def __init__(
        self,
        settings_file: Path,
        debounce_seconds: float = 2.0,
        validate_before_reload: bool = True,
    ):
        """
        Initialize settings file watcher.

        Args:
            settings_file: Path to settings.json to watch
            debounce_seconds: Delay before reload to prevent spam
            validate_before_reload: Validate JSON before reloading
        """
        self.settings_file = Path(settings_file).resolve()
        self.debounce_seconds = debounce_seconds
        self.validate_before_reload = validate_before_reload

        # Callback management
        self._callbacks: List[Callable[[], None]] = []  # noqa: UP006

        # Concurrency control
        self._reload_lock = threading.Lock()
        self._debounce_timer: threading.Timer | None = None
        self._debounce_lock = threading.Lock()

        # Watchdog components
        self._observer: Observer | None = None
        self._event_handler: SettingsChangeHandler | None = None

        # State tracking
        self._is_running = False
        self._last_reload_time: float | None = None

        # Validate settings file exists
        if not self.settings_file.exists():
            logger.warning(f'Settings file does not exist yet: {self.settings_file}')

        logger.debug(
            f'Initialized SettingsFileWatcher for {self.settings_file} '
            f'with {debounce_seconds}s debounce'
        )

    def add_callback(self, callback: Callable[[], None]) -> None:
        """
        Add a callback to be called when settings change.

        Args:
            callback: Callable with no arguments to execute on reload
        """
        if not callable(callback):
            raise TypeError(f'Callback must be callable, got {type(callback)}')

        self._callbacks.append(callback)
        logger.debug(f'Added reload callback: {callback.__name__}')

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """
        Remove a previously registered callback.

        Args:
            callback: Callback to remove
        """
        if callback in self._callbacks:
            self._callbacks.remove(callback)
            logger.debug(f'Removed reload callback: {callback.__name__}')

    def start(self) -> None:
        """Start watching the settings file."""
        if not WATCHDOG_AVAILABLE:
            logger.warning('Watchdog not available, hot-reload disabled')
            return

        if self._is_running:
            logger.warning('Settings watcher is already running')
            return

        # Ensure parent directory exists
        watch_dir = self.settings_file.parent
        if not watch_dir.exists():
            logger.error(f'Cannot watch non-existent directory: {watch_dir}')
            raise FileNotFoundError(f'Directory not found: {watch_dir}')

        # Create event handler and observer
        self._event_handler = SettingsChangeHandler(
            watcher=self, settings_file=self.settings_file
        )

        self._observer = Observer()
        self._observer.schedule(self._event_handler, str(watch_dir), recursive=False)

        # Start observer
        self._observer.start()
        self._is_running = True

        logger.info(
            f'Started watching settings file: {self.settings_file} '
            f'(watching directory: {watch_dir})'
        )

    def stop(self) -> None:
        """Stop watching the settings file."""
        if not self._is_running:
            logger.warning('Settings watcher is not running')
            return

        # Cancel any pending debounce timer
        with self._debounce_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

        # Stop observer
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        self._is_running = False
        logger.info('Stopped watching settings file')

    def _validate_settings(self, file_path: Path) -> bool:
        """
        Validate settings file before reload.

        Args:
            file_path: Path to settings file to validate

        Returns:
            True if valid, False otherwise
        """
        if not self.validate_before_reload:
            return True

        try:
            # Check file exists and is readable
            if not file_path.exists():
                logger.error(f'Settings file does not exist: {file_path}')
                return False

            if not file_path.is_file():
                logger.error(f'Settings path is not a file: {file_path}')
                return False

            # Load and validate JSON
            with open(file_path, 'r', encoding='utf-8') as f:  # noqa: UP015
                data = json.load(f)

            # Basic validation - must be a dictionary
            if not isinstance(data, dict):
                logger.error('Settings file is not a JSON object')
                return False

            # Check for minimum required fields (optional)
            # This could be enhanced with schema validation
            if len(data) == 0:
                logger.warning('Settings file is empty')

            logger.info('Settings file validation passed')
            return True

        except json.JSONDecodeError as e:
            logger.error(f'Invalid JSON in settings file: {e}')
            return False
        except PermissionError as e:
            logger.error(f'Permission denied reading settings file: {e}')
            return False
        except Exception as e:
            logger.error(f'Error validating settings: {e}')
            return False

    def _trigger_reload(self) -> None:
        """
        Trigger all registered callbacks after debounce.

        This method is called by the debounce timer and executes
        all registered callbacks in sequence, with error isolation.
        """
        import time

        with self._reload_lock:
            # Validate settings before triggering callbacks
            if not self._validate_settings(self.settings_file):
                logger.error('Settings validation failed, skipping reload')
                return

            logger.info(
                f'Triggering settings reload with {len(self._callbacks)} callbacks'
            )

            # Execute all callbacks
            success_count = 0
            error_count = 0

            for idx, callback in enumerate(self._callbacks):
                try:
                    callback_name = getattr(callback, '__name__', f'callback_{idx}')
                    logger.debug(f'Executing reload callback: {callback_name}')

                    callback()
                    success_count += 1

                except Exception as e:
                    error_count += 1
                    callback_name = getattr(callback, '__name__', f'callback_{idx}')
                    logger.error(
                        f"Error in reload callback '{callback_name}': {e}",
                        exc_info=True,
                    )

            # Update last reload time
            self._last_reload_time = time.time()

            # Log summary
            logger.info(
                f'Settings reload completed: {success_count} successful, '
                f'{error_count} failed'
            )

    def _schedule_reload(self) -> None:
        """
        Schedule a debounced reload.

        Cancels any pending reload and schedules a new one after
        the debounce period.
        """
        with self._debounce_lock:
            # Cancel existing timer if any
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            # Schedule new reload
            self._debounce_timer = threading.Timer(
                self.debounce_seconds, self._trigger_reload
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

            logger.debug(
                f'Scheduled settings reload in {self.debounce_seconds}s (debouncing)'
            )

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


class SettingsChangeHandler(FileSystemEventHandler):
    """Handler for file system events on settings file."""

    def __init__(self, watcher: SettingsFileWatcher, settings_file: Path):
        """
        Initialize handler.

        Args:
            watcher: Parent watcher instance
            settings_file: Path to settings file to monitor
        """
        super().__init__()
        self.watcher = watcher
        self.settings_file = settings_file.resolve()

    def on_modified(self, event: FileSystemEvent) -> None:
        """
        Called when a file in the watched directory is modified.

        Args:
            event: File system event
        """
        # Ignore directory modifications
        if event.is_directory:
            return

        # Only process our specific settings file
        event_path = Path(event.src_path).resolve()

        if event_path != self.settings_file:
            return

        logger.debug(f'Settings file modified: {event_path}')

        # Schedule debounced reload
        self.watcher._schedule_reload()

    def on_created(self, event: FileSystemEvent) -> None:
        """
        Called when a file is created in the watched directory.

        Handles the case where settings file is created after
        watcher starts.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        event_path = Path(event.src_path).resolve()

        if event_path != self.settings_file:
            return

        logger.info(f'Settings file created: {event_path}')

        # Schedule reload for newly created file
        self.watcher._schedule_reload()

    def on_moved(self, event: FileSystemEvent) -> None:
        """
        Called when a file is moved in the watched directory.

        Handles atomic write operations (write to temp, then move).

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        # Check if destination is our settings file
        dest_path = Path(event.dest_path).resolve()

        if dest_path != self.settings_file:
            return

        logger.debug(
            f'Settings file moved/renamed: {event.src_path} -> {event.dest_path}'
        )

        # Schedule reload for atomic write
        self.watcher._schedule_reload()


def create_settings_watcher(
    settings_file: Path,
    callbacks: List[Callable[[], None]] | None = None,  # noqa: UP006
    debounce_seconds: float = 2.0,
    validate_before_reload: bool = True,
    auto_start: bool = False,
) -> SettingsFileWatcher:
    """
    Factory function to create and optionally start a settings watcher.

    Args:
        settings_file: Path to settings.json to watch
        callbacks: Optional list of callbacks to register
        debounce_seconds: Delay before reload to prevent spam
        validate_before_reload: Validate JSON before reloading
        auto_start: Whether to automatically start the watcher

    Returns:
        Configured SettingsFileWatcher instance
    """
    watcher = SettingsFileWatcher(
        settings_file=settings_file,
        debounce_seconds=debounce_seconds,
        validate_before_reload=validate_before_reload,
    )

    # Register callbacks
    if callbacks:
        for callback in callbacks:
            watcher.add_callback(callback)

    # Auto-start if requested
    if auto_start:
        watcher.start()

    return watcher
