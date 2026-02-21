"""
Project sync service for Thoth.

Watches PDF, markdown, and notes directories for file moves between project
folders and automatically syncs the linked files (PDF + markdown + note).
"""

import asyncio
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from thoth.config import config
from thoth.mcp.auth import get_current_user_paths
from thoth.utilities.vault_path_resolver import VaultPathResolver

if TYPE_CHECKING:
    from thoth.services.postgres_service import PostgresService

# Optional watchdog dependency
try:
    from watchdog.events import (
        FileCreatedEvent,
        FileDeletedEvent,
        FileSystemEventHandler,
    )
    from watchdog.observers.polling import PollingObserver

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    # Stubs for type hints
    class FileSystemEventHandler:  # type: ignore
        pass

    class FileCreatedEvent:  # type: ignore
        pass

    class FileDeletedEvent:  # type: ignore
        pass

    class PollingObserver:  # type: ignore
        pass


@dataclass
class PendingDelete:
    """Tracks a recently deleted file that might be part of a move operation."""

    path: Path
    filename: str
    timestamp: float
    db_record: dict | None


class ProjectSyncHandler(FileSystemEventHandler):
    """
    Handler for project file sync events.

    Detects file moves across project folders and syncs linked files.
    """

    def __init__(
        self,
        pdf_dir: Path,
        markdown_dir: Path,
        notes_dir: Path,
        postgres_service: 'PostgresService',
        event_loop: asyncio.AbstractEventLoop,
        pending_deletes: dict,
        vault_resolver: VaultPathResolver,
    ):
        """
        Initialize the project sync handler.

        Args:
            pdf_dir: Root directory for PDFs
            markdown_dir: Root directory for markdown files
            notes_dir: Root directory for notes
            postgres_service: PostgresService instance
            event_loop: Asyncio event loop for running async operations
            pending_deletes: Shared dict for tracking pending deletes
            vault_resolver: VaultPathResolver for path conversions
        """
        self.pdf_dir = pdf_dir
        self.markdown_dir = markdown_dir
        self.notes_dir = notes_dir
        self.postgres_service = postgres_service
        self.loop = event_loop
        self.pending_deletes = pending_deletes
        self.vault_resolver = vault_resolver

    def on_deleted(self, event):
        """Handle file deletion events."""
        if not isinstance(event, FileDeletedEvent):
            return

        file_path = Path(event.src_path)

        # Only track supported file types
        if file_path.suffix.lower() not in {'.pdf', '.md'}:
            return

        # Ignore hidden/temp files
        if file_path.name.startswith('.') or file_path.name.startswith('~'):
            return

        logger.debug(f'File deleted: {file_path.name}')

        # Look up in database
        future = asyncio.run_coroutine_threadsafe(
            self._handle_delete(file_path), self.loop
        )

        try:
            future.result(timeout=10)
        except Exception as e:
            logger.error(f'Error handling delete for {file_path}: {e}')

    def on_created(self, event):
        """Handle file creation events."""
        if not isinstance(event, FileCreatedEvent):
            return

        file_path = Path(event.src_path)

        # Only track supported file types
        if file_path.suffix.lower() not in {'.pdf', '.md'}:
            return

        # Ignore hidden/temp files
        if file_path.name.startswith('.') or file_path.name.startswith('~'):
            return

        logger.debug(f'File created: {file_path.name}')

        # Check if this matches a recent delete (move detection)
        future = asyncio.run_coroutine_threadsafe(
            self._handle_create(file_path), self.loop
        )

        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error(f'Error handling create for {file_path}: {e}')

    async def _handle_delete(self, file_path: Path) -> None:
        """Handle deletion - look up file in DB and add to pending deletes."""
        try:
            vault_relative = self.vault_resolver.make_relative(file_path)
        except ValueError:
            logger.debug(f'File {file_path} not in vault, ignoring')
            return

        # Look up in processed_papers
        async with self.postgres_service.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT pp.*, pm.id as paper_metadata_id, pm.collection_id
                FROM processed_papers pp
                JOIN paper_metadata pm ON pp.paper_id = pm.id
                WHERE pp.pdf_path = $1 OR pp.markdown_path = $1 OR pp.note_path = $1
                """,
                vault_relative,
            )

            if row:
                # Add to pending deletes
                pending = PendingDelete(
                    path=file_path,
                    filename=file_path.name,
                    timestamp=time.time(),
                    db_record=dict(row),
                )
                self.pending_deletes[file_path.name] = pending
                logger.info(
                    f'Tracked pending delete: {file_path.name} (paper: {row["paper_metadata_id"]})'
                )

    async def _handle_create(self, file_path: Path) -> None:
        """Handle creation - check for matching pending delete (move detection)."""
        filename = file_path.name

        # Check pending deletes
        pending = self.pending_deletes.get(filename)
        if not pending or not pending.db_record:
            return

        # This is a move!
        logger.info(f'Detected move: {filename} (from {pending.path} to {file_path})')

        # Remove from pending
        del self.pending_deletes[filename]

        # Determine new project folder
        new_project = self._get_project_from_path(file_path)
        old_project = self._get_project_from_path(pending.path)

        if new_project == old_project:
            logger.debug(f'Move within same project {new_project}, ignoring')
            return

        logger.info(f'Cross-project move: {old_project} -> {new_project}')

        # Sync the other linked files
        await self._sync_linked_files(pending.db_record, file_path, new_project)

    def _get_project_from_path(self, file_path: Path) -> str | None:
        """Extract project name from file path."""
        # Determine which root directory this file is under
        try:
            if file_path.is_relative_to(self.pdf_dir):
                relative = file_path.relative_to(self.pdf_dir)
            elif file_path.is_relative_to(self.markdown_dir):
                relative = file_path.relative_to(self.markdown_dir)
            elif file_path.is_relative_to(self.notes_dir):
                relative = file_path.relative_to(self.notes_dir)
            else:
                return None

            if len(relative.parts) > 1:
                return relative.parts[0]
        except (ValueError, AttributeError):
            pass
        return None

    async def _sync_linked_files(
        self, db_record: dict, _moved_file: Path, new_project: str | None
    ) -> None:
        """
        Sync the other two linked files to match the moved file's project.

        Args:
            db_record: Database record with current paths
            _moved_file: The file that was moved (used for move detection only)
            new_project: The new project name (None for root)
        """
        paper_id = db_record['paper_id']
        paper_metadata_id = db_record['paper_metadata_id']

        # Get current paths from DB (vault-relative)
        pdf_path_rel = db_record.get('pdf_path')
        markdown_path_rel = db_record.get('markdown_path')
        note_path_rel = db_record.get('note_path')

        # Convert to absolute
        pdf_path = self.vault_resolver.resolve(pdf_path_rel) if pdf_path_rel else None
        markdown_path = (
            self.vault_resolver.resolve(markdown_path_rel)
            if markdown_path_rel
            else None
        )
        note_path = (
            self.vault_resolver.resolve(note_path_rel) if note_path_rel else None
        )

        # Compute new paths for all three files
        new_pdf_path = self._compute_new_path(pdf_path, self.pdf_dir, new_project)
        new_markdown_path = self._compute_new_path(
            markdown_path, self.markdown_dir, new_project
        )
        new_note_path = self._compute_new_path(note_path, self.notes_dir, new_project)

        # Move the files that weren't already moved
        try:
            if pdf_path and pdf_path.exists() and pdf_path != new_pdf_path:
                new_pdf_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(pdf_path), str(new_pdf_path))
                logger.info(f'Moved PDF: {pdf_path.name} to {new_pdf_path.parent}')

            if (
                markdown_path
                and markdown_path.exists()
                and markdown_path != new_markdown_path
            ):
                new_markdown_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(markdown_path), str(new_markdown_path))
                logger.info(
                    f'Moved markdown: {markdown_path.name} to {new_markdown_path.parent}'
                )

            if note_path and note_path.exists() and note_path != new_note_path:
                new_note_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(note_path), str(new_note_path))
                logger.info(f'Moved note: {note_path.name} to {new_note_path.parent}')

            # Update database with new paths
            new_pdf_rel = self.vault_resolver.make_relative(new_pdf_path)
            new_markdown_rel = self.vault_resolver.make_relative(new_markdown_path)
            new_note_rel = self.vault_resolver.make_relative(new_note_path)

            async with self.postgres_service.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE processed_papers
                    SET pdf_path = $1, markdown_path = $2, note_path = $3, updated_at = NOW()
                    WHERE paper_id = $4
                    """,
                    new_pdf_rel,
                    new_markdown_rel,
                    new_note_rel,
                    paper_id,
                )

                # Update collection_id
                collection_id = None
                if new_project:
                    collection_id = await self._ensure_collection(conn, new_project)

                await conn.execute(
                    """
                    UPDATE paper_metadata
                    SET collection_id = $1, updated_at = NOW()
                    WHERE id = $2
                    """,
                    collection_id,
                    paper_metadata_id,
                )

            logger.success(
                f'Synced files for paper {paper_metadata_id[:8]} to project: {new_project or "root"}'
            )

        except Exception as e:
            logger.error(f'Failed to sync files for paper {paper_id}: {e}')

    def _compute_new_path(
        self, old_path: Path | None, root_dir: Path, new_project: str | None
    ) -> Path:
        """Compute new path for a file in the new project folder."""
        if not old_path:
            return None

        filename = old_path.name

        if new_project:
            return root_dir / new_project / filename
        else:
            return root_dir / filename

    async def _ensure_collection(self, _conn, project_name: str) -> str:
        """Ensure collection exists, creating if needed. Returns UUID."""
        from thoth.repositories.knowledge_collection_repository import (
            KnowledgeCollectionRepository,
        )

        repo = KnowledgeCollectionRepository(self.postgres_service)
        collection = await repo.get_by_name(project_name)
        if collection:
            return collection['id']

        # Create new
        new_collection = await repo.create(
            name=project_name, description=f'Auto-created project: {project_name}'
        )
        return new_collection['id']


class ProjectSyncService:
    """
    Service that watches for file moves between project folders and syncs linked files.
    """

    def __init__(
        self,
        pdf_dir: Path | None = None,
        markdown_dir: Path | None = None,
        notes_dir: Path | None = None,
        postgres_service: 'PostgresService | None' = None,
        polling_interval: float = 10.0,
    ):
        """
        Initialize the project sync service.

        Args:
            pdf_dir: PDF directory to watch
            markdown_dir: Markdown directory to watch
            notes_dir: Notes directory to watch
            postgres_service: PostgresService instance
            polling_interval: Polling interval in seconds
        """
        self.config = config
        user_paths = get_current_user_paths()
        default_pdf_dir = user_paths.pdf_dir if user_paths else self.config.pdf_dir
        default_markdown_dir = (
            user_paths.markdown_dir if user_paths else self.config.markdown_dir
        )
        default_notes_dir = (
            user_paths.notes_dir if user_paths else self.config.notes_dir
        )
        default_vault_root = (
            user_paths.vault_root if user_paths else self.config.vault_root
        )
        self.pdf_dir = pdf_dir or default_pdf_dir
        self.markdown_dir = markdown_dir or default_markdown_dir
        self.notes_dir = notes_dir or default_notes_dir
        self.postgres_service = postgres_service
        self.polling_interval = polling_interval

        # Ensure directories exist
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        # Vault path resolver
        self.vault_resolver = VaultPathResolver(default_vault_root)

        # Shared state for pending deletes
        self.pending_deletes: dict[str, PendingDelete] = {}

        # Create event loop for async operations
        self._loop_thread = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._start_event_loop()

        # Observer
        self.observer: PollingObserver | None = None
        self.is_running = False
        self.cleanup_thread = None

        logger.info(f'ProjectSyncService initialized (polling: {polling_interval}s)')

    def _start_event_loop(self) -> None:
        """Start a dedicated event loop in a background thread."""

        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._loop = asyncio.new_event_loop()
        self._loop_thread = threading.Thread(
            target=run_loop, args=(self._loop,), daemon=True
        )
        self._loop_thread.start()
        logger.debug('Started event loop thread for project sync')

    def start_watching(self) -> None:
        """Start watching directories for file moves."""
        if not WATCHDOG_AVAILABLE:
            logger.warning('Watchdog not available, project sync disabled')
            return

        if self.observer is not None and self.observer.is_alive():
            logger.warning('ProjectSyncService already running')
            return

        logger.info('Starting project sync watcher...')

        # Create handler
        handler = ProjectSyncHandler(
            pdf_dir=self.pdf_dir,
            markdown_dir=self.markdown_dir,
            notes_dir=self.notes_dir,
            postgres_service=self.postgres_service,
            event_loop=self._loop,
            pending_deletes=self.pending_deletes,
            vault_resolver=self.vault_resolver,
        )

        # Create observer
        self.observer = PollingObserver(timeout=self.polling_interval)
        self.observer.schedule(handler, str(self.pdf_dir), recursive=True)
        self.observer.schedule(handler, str(self.markdown_dir), recursive=True)
        self.observer.schedule(handler, str(self.notes_dir), recursive=True)
        self.observer.start()

        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_pending_deletes, daemon=True
        )
        self.cleanup_thread.start()

        self.is_running = True
        logger.success(
            f'ProjectSyncService watching (polling: {self.polling_interval}s)'
        )

    def _cleanup_pending_deletes(self) -> None:
        """Periodically clean up old pending deletes (genuine deletions)."""
        while self.is_running:
            time.sleep(30)  # Clean up every 30 seconds

            current_time = time.time()
            to_remove = []

            for filename, pending in self.pending_deletes.items():
                # Remove if older than 30 seconds
                if current_time - pending.timestamp > 30:
                    to_remove.append(filename)

            for filename in to_remove:
                del self.pending_deletes[filename]
                logger.debug(f'Removed stale pending delete: {filename}')

    def stop(self) -> None:
        """Stop the project sync service."""
        if self.observer and self.observer.is_alive():
            logger.info('Stopping project sync service...')
            self.is_running = False
            self.observer.stop()
            self.observer.join(timeout=5)
            logger.info('Project sync service stopped')

        # Stop event loop
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def health_check(self) -> dict[str, str]:
        """Return health status."""
        return {
            'status': 'healthy' if self.is_running else 'stopped',
            'service': self.__class__.__name__,
            'pending_deletes': str(len(self.pending_deletes)),
        }
