"""
Letta Filesystem Watcher Service

Monitors vault files for changes and automatically syncs them to Letta filesystem.
Uses watchdog for file system monitoring with debouncing to avoid excessive syncs.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from thoth.config import Config


class LettaFilesystemWatcher(FileSystemEventHandler):
    """
    Watches vault notes directory and syncs changes to Letta filesystem.
    
    Features:
    - Monitors markdown files in notes directory
    - Debounces rapid changes (avoids syncing on every keystroke)
    - Batches multiple changes into single sync
    - Configurable sync delay
    """

    def __init__(
        self,
        config: Config,
        letta_filesystem_service,  # Type: LettaFilesystemService (avoid circular import)
        debounce_seconds: int = 5,
    ):
        """
        Initialize the watcher.

        Args:
            config: Configuration object
            letta_filesystem_service: LettaFilesystemService instance for syncing
            debounce_seconds: Seconds to wait before syncing after last change
        """
        super().__init__()
        self.config = config
        self.letta_service = letta_filesystem_service
        self.debounce_seconds = debounce_seconds
        
        # Track pending changes
        self._pending_sync = False
        self._last_change_time: Optional[float] = None
        self._sync_task: Optional[asyncio.Task] = None
        
        # Observer for file system events
        self.observer: Optional[Observer] = None
        self._running = False
        
        self.logger = logger.bind(service='letta_filesystem_watcher')
        self.logger.info(
            f'LettaFilesystemWatcher initialized (debounce: {debounce_seconds}s)'
        )

    def start(self) -> None:
        """Start watching the notes directory."""
        if self._running:
            self.logger.warning('Watcher already running')
            return

        # Get notes directory from config
        notes_dir = self.config.notes_dir
        if not notes_dir.exists():
            self.logger.warning(f'Notes directory does not exist: {notes_dir}')
            notes_dir.mkdir(parents=True, exist_ok=True)

        # Start watchdog observer
        self.observer = Observer()
        self.observer.schedule(self, str(notes_dir), recursive=True)
        self.observer.start()
        self._running = True
        
        self.logger.info(f'Started watching: {notes_dir}')

    def stop(self) -> None:
        """Stop watching the notes directory."""
        if not self._running:
            return

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None

        # Cancel any pending sync
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()

        self._running = False
        self.logger.info('Stopped watching')

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if self._should_sync_file(path):
            self.logger.debug(f'File created: {path.name}')
            self._schedule_sync()

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if self._should_sync_file(path):
            self.logger.debug(f'File modified: {path.name}')
            self._schedule_sync()

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if self._should_sync_file(path):
            self.logger.debug(f'File deleted: {path.name}')
            self._schedule_sync()

    def _should_sync_file(self, path: Path) -> bool:
        """
        Check if a file should trigger a sync.

        Args:
            path: File path

        Returns:
            True if file should trigger sync
        """
        # Only sync markdown files
        if path.suffix != '.md':
            return False

        # Ignore hidden files and temp files
        if path.name.startswith('.') or path.name.startswith('~'):
            return False

        # Ignore swap files
        if path.suffix in {'.swp', '.tmp', '.bak'}:
            return False

        return True

    def _schedule_sync(self) -> None:
        """
        Schedule a sync after debounce period.
        
        Multiple rapid changes will be batched into a single sync.
        """
        self._pending_sync = True
        self._last_change_time = time.time()

        # If no sync task running, start one
        if not self._sync_task or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._debounced_sync())

    async def _debounced_sync(self) -> None:
        """
        Wait for debounce period, then sync if no new changes.
        
        This prevents syncing on every keystroke in a text editor.
        """
        while self._pending_sync:
            # Wait for debounce period
            await asyncio.sleep(self.debounce_seconds)

            # Check if enough time has passed since last change
            if self._last_change_time:
                time_since_change = time.time() - self._last_change_time
                if time_since_change >= self.debounce_seconds:
                    # No changes in debounce period - do sync
                    await self._do_sync()
                    self._pending_sync = False
                    self._last_change_time = None

    async def _do_sync(self) -> None:
        """
        Execute the actual sync to Letta filesystem.
        """
        try:
            self.logger.info('Auto-syncing vault files to Letta filesystem...')
            
            # Get folder configuration
            letta_config = self.config.memory_config.letta if hasattr(self.config.memory_config, 'letta') else None
            filesystem_config = letta_config.get('filesystem', {})
            folder_name = filesystem_config.get('folderName', 'thoth_processed_articles')
            embedding_model = filesystem_config.get('embeddingModel', 'openai/text-embedding-3-small')
            
            # Get or create the folder
            folder_id = await self.letta_service.get_or_create_folder(
                name=folder_name,
                embedding_config={'embedding_model': embedding_model}
            )
            
            if not folder_id:
                self.logger.error('Failed to get or create Letta folder')
                return
            
            # Sync files to the folder
            result = await self.letta_service.sync_vault_to_folder(
                folder_id=folder_id
            )
            
            if result:
                uploaded = result.get('uploaded', 0)
                skipped = result.get('skipped', 0)
                errors = result.get('errors', [])
                
                if errors:
                    self.logger.warning(
                        f'Auto-sync complete with errors: {uploaded} uploaded, '
                        f'{skipped} skipped, {len(errors)} errors'
                    )
                else:
                    self.logger.success(
                        f'Auto-sync complete: {uploaded} uploaded, {skipped} skipped'
                    )
            else:
                self.logger.warning('Auto-sync returned no result')
                
        except Exception as e:
            self.logger.error(f'Auto-sync failed: {e}')


class LettaFilesystemWatcherService:
    """
    Service wrapper for LettaFilesystemWatcher.
    
    Provides lifecycle management and integration with ServiceManager.
    """

    def __init__(self, config: Config, letta_filesystem_service):
        """
        Initialize the watcher service.

        Args:
            config: Configuration object
            letta_filesystem_service: LettaFilesystemService instance
        """
        self.config = config
        self.letta_service = letta_filesystem_service
        
        # Get debounce settings from config
        letta_config = config.memory_config.letta if hasattr(config.memory_config, 'letta') else None
        filesystem_config = letta_config.get('filesystem', {})
        debounce_seconds = filesystem_config.get('debounceSeconds', 5)
        
        # Create watcher
        self.watcher = LettaFilesystemWatcher(
            config=config,
            letta_filesystem_service=letta_filesystem_service,
            debounce_seconds=debounce_seconds,
        )
        
        self.logger = logger.bind(service='letta_filesystem_watcher_service')
        self.logger.info('LettaFilesystemWatcherService initialized')

    def start(self) -> None:
        """Start the watcher."""
        letta_config = self.config.memory_config.letta if hasattr(self.config.memory_config, 'letta') else None
        filesystem_config = getattr(letta_config, 'filesystem', None) if letta_config else None
        auto_sync = getattr(filesystem_config, 'autoSync', False) if filesystem_config else False
        
        if auto_sync:
            self.watcher.start()
            self.logger.info('Auto-sync enabled - watching for file changes')
        else:
            self.logger.info('Auto-sync disabled - use manual sync')

    def stop(self) -> None:
        """Stop the watcher."""
        self.watcher.stop()

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
