"""
Knowledge folder monitor for Thoth.

Watches a directory for new knowledge documents (textbooks, notes, etc.)
and automatically uploads them to collections based on folder structure.
"""

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from thoth.config import config

if TYPE_CHECKING:
    from thoth.services.knowledge_service import KnowledgeService
    from thoth.services.postgres_service import PostgresService

# Optional watchdog dependency
try:
    from watchdog.events import FileCreatedEvent, FileSystemEventHandler
    from watchdog.observers.polling import PollingObserver

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    # Stubs for type hints
    class FileSystemEventHandler:  # type: ignore
        pass

    class FileCreatedEvent:  # type: ignore
        pass

    class PollingObserver:  # type: ignore
        pass


class KnowledgeFileHandler(FileSystemEventHandler):
    """
    Handler for knowledge file events.

    Processes new files dropped into the knowledge directory,
    auto-creating collections from folder names.
    """

    def __init__(
        self,
        watch_dir: Path,
        knowledge_service: 'KnowledgeService',
        event_loop: asyncio.AbstractEventLoop,
    ):
        """
        Initialize the knowledge file handler.

        Args:
            watch_dir: Root directory being watched.
            knowledge_service: KnowledgeService instance for uploads.
            event_loop: Asyncio event loop for running async operations.
        """
        self.watch_dir = watch_dir
        self.knowledge_service = knowledge_service
        self.loop = event_loop
        self.supported_extensions = {
            '.pdf',
            '.md',
            '.txt',
            '.html',
            '.htm',
            '.epub',
            '.docx',
        }

    def on_created(self, event):
        """
        Handle file creation events.

        Args:
            event: File system event.
        """
        if not isinstance(event, FileCreatedEvent):
            return

        file_path = Path(event.src_path)

        # Only process supported file types
        if file_path.suffix.lower() not in self.supported_extensions:
            return

        # Ignore hidden files and temp files
        if file_path.name.startswith('.') or file_path.name.startswith('~'):
            return

        logger.info(f'New knowledge file detected: {file_path.name}')

        # Determine collection name from folder structure
        try:
            relative = file_path.relative_to(self.watch_dir)
            parts = relative.parts

            # Files at root are skipped (no collection)
            if len(parts) == 1:
                logger.warning(
                    f'Skipping file at root of knowledge directory: {file_path.name}. '
                    f'Files must be in a collection subfolder.'
                )
                return

            # Collection name is the first-level folder
            collection_name = parts[0]

            # Use run_coroutine_threadsafe to bridge sync handler to async service
            future = asyncio.run_coroutine_threadsafe(
                self._process_file(file_path, collection_name), self.loop
            )

            # Wait for completion (with timeout)
            try:
                future.result(timeout=300)  # 5 minutes max per file
            except Exception as e:
                logger.error(f'Failed to process {file_path.name}: {e}')

        except ValueError as e:
            logger.error(f'Error resolving collection for {file_path}: {e}')
        except Exception as e:
            logger.error(f'Error processing {file_path}: {e}')

    async def _process_file(self, file_path: Path, collection_name: str) -> None:
        """
        Process a single file (runs async in the event loop thread).

        Args:
            file_path: Path to the file.
            collection_name: Collection name from folder.
        """
        try:
            # Auto-create collection if it doesn't exist
            collection = await self.knowledge_service.get_collection(
                name=collection_name
            )
            if not collection:
                logger.info(f'Auto-creating collection: {collection_name}')
                await self.knowledge_service.create_collection(
                    name=collection_name,
                    description=f'Auto-generated from folder: {collection_name}',
                )

            # Check if already uploaded
            title = file_path.stem.replace('_', ' ').replace('-', ' ').title()
            is_uploaded = await self.knowledge_service.is_document_uploaded(
                title, collection_name
            )

            if is_uploaded:
                logger.debug(
                    f'Skipping already uploaded document: {file_path.name} (collection: {collection_name})'
                )
                return

            # Upload the document
            logger.info(f'Uploading {file_path.name} to collection: {collection_name}')
            result = await self.knowledge_service.upload_document(
                file_path=file_path,
                collection_name=collection_name,
                title=title,
            )

            logger.success(
                f'Successfully uploaded {file_path.name} '
                f'(paper_id: {result["paper_id"]}, chunks indexed)'
            )

        except Exception as e:
            logger.error(f'Failed to process {file_path.name}: {e}')
            raise


class KnowledgeMonitor:
    """
    Monitor for knowledge folder auto-uploads.

    Watches thoth/knowledge/ for new files and automatically uploads them
    to collections based on folder structure.
    """

    def __init__(
        self,
        watch_dir: Path | None = None,
        knowledge_service: 'KnowledgeService | None' = None,
        postgres_service: 'PostgresService | None' = None,
        polling_interval: float = 30.0,
    ):
        """
        Initialize the knowledge monitor.

        Args:
            watch_dir: Directory to watch. Defaults to config.knowledge_dir.
            knowledge_service: KnowledgeService instance.
            postgres_service: PostgresService instance.
            polling_interval: Polling interval in seconds.
        """
        self.config = config
        self.watch_dir = watch_dir or self.config.knowledge_base_dir
        self.knowledge_service = knowledge_service
        self.postgres_service = postgres_service
        self.polling_interval = polling_interval

        # Ensure watch directory exists
        self.watch_dir.mkdir(parents=True, exist_ok=True)

        # Create event loop for async operations (runs in dedicated thread)
        self._loop_thread = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._start_event_loop()

        # Observer will be created when start_watching is called
        self.observer: PollingObserver | None = None
        self.is_running = False
        self.files_processed = 0

        logger.info(
            f'Knowledge monitor initialized to watch: {self.watch_dir} '
            f'(polling interval: {polling_interval}s)'
        )

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
        logger.debug('Started event loop thread for knowledge monitor')

    def process_existing_files(self) -> None:
        """
        Process existing files in the knowledge directory on startup.

        Scans all subdirectories, auto-creates collections, and uploads files.
        """
        if not WATCHDOG_AVAILABLE:
            logger.warning('Watchdog not available, skipping existing files scan')
            return

        logger.info(f'Scanning for existing knowledge files in {self.watch_dir}')

        # Get all subdirectories (these become collections)
        collection_dirs = [
            d
            for d in self.watch_dir.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ]

        if not collection_dirs:
            logger.info('No collection folders found in knowledge directory')
            return

        logger.info(f'Found {len(collection_dirs)} collection folders')

        # Process each collection folder
        for collection_dir in collection_dirs:
            collection_name = collection_dir.name
            logger.info(f'Processing collection folder: {collection_name}')

            # Find all supported files in this collection
            supported_files = []
            for ext in ['.pdf', '.md', '.txt', '.html', '.htm', '.epub', '.docx']:
                supported_files.extend(collection_dir.rglob(f'*{ext}'))

            if not supported_files:
                logger.debug(f'No files found in {collection_name}')
                continue

            logger.info(f'Found {len(supported_files)} files in {collection_name}')

            # Process files async
            future = asyncio.run_coroutine_threadsafe(
                self._process_collection_files(collection_name, supported_files),
                self._loop,
            )

            try:
                # Wait for this collection to complete (5 min per collection)
                future.result(timeout=300)
                logger.success(f'Completed processing {collection_name}')
            except Exception as e:
                logger.error(f'Error processing {collection_name}: {e}')

        logger.success(
            f'Finished scanning existing files: {self.files_processed} processed'
        )

    async def _process_collection_files(
        self, collection_name: str, files: list[Path]
    ) -> None:
        """
        Process all files for a collection (async).

        Args:
            collection_name: Collection name.
            files: List of file paths to process.
        """
        # Auto-create collection if needed
        collection = await self.knowledge_service.get_collection(name=collection_name)
        if not collection:
            logger.info(f'Auto-creating collection: {collection_name}')
            try:
                await self.knowledge_service.create_collection(
                    name=collection_name,
                    description=f'Auto-generated from folder: {collection_name}',
                )
            except ValueError as e:
                # Might already exist from concurrent creation
                if 'already exists' in str(e).lower():
                    logger.debug(f'Collection {collection_name} already exists')
                else:
                    raise

        # Process each file
        for file_path in files:
            try:
                # Generate title from filename
                title = file_path.stem.replace('_', ' ').replace('-', ' ').title()

                # Check if already uploaded
                is_uploaded = await self.knowledge_service.is_document_uploaded(
                    title, collection_name
                )

                if is_uploaded:
                    logger.debug(f'Skipping already uploaded: {file_path.name}')
                    continue

                # Upload the document
                logger.info(f'Uploading {file_path.name}...')
                result = await self.knowledge_service.upload_document(
                    file_path=file_path,
                    collection_name=collection_name,
                    title=title,
                )

                self.files_processed += 1
                logger.success(
                    f'[{self.files_processed}] Uploaded {file_path.name} '
                    f'(paper_id: {result["paper_id"]})'
                )

            except Exception as e:
                logger.error(f'Failed to upload {file_path.name}: {e}')

    def start_watching(self) -> None:
        """
        Start watching the knowledge directory for new files.

        This method is non-blocking -- it starts the observer and returns.
        The observer runs in a background thread.
        """
        if not WATCHDOG_AVAILABLE:
            logger.warning('Watchdog not available, knowledge folder watching disabled')
            return

        if self.observer is not None and self.observer.is_alive():
            logger.warning('Knowledge monitor observer already running')
            return

        logger.info('Starting knowledge folder watcher...')

        # Create handler
        handler = KnowledgeFileHandler(
            watch_dir=self.watch_dir,
            knowledge_service=self.knowledge_service,
            event_loop=self._loop,
        )

        # Create and start observer
        self.observer = PollingObserver(timeout=self.polling_interval)
        self.observer.schedule(handler, str(self.watch_dir), recursive=True)
        self.observer.start()

        self.is_running = True
        logger.success(
            f'Knowledge monitor watching: {self.watch_dir} (polling: {self.polling_interval}s)'
        )

    def stop(self) -> None:
        """Stop the knowledge monitor."""
        if self.observer and self.observer.is_alive():
            logger.info('Stopping knowledge monitor...')
            self.observer.stop()
            self.observer.join(timeout=5)
            self.is_running = False
            logger.info('Knowledge monitor stopped')

        # Stop event loop
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

    def health_check(self) -> dict[str, str]:
        """Return health status."""
        return {
            'status': 'healthy' if self.is_running else 'stopped',
            'service': self.__class__.__name__,
            'watching': str(self.watch_dir),
            'files_processed': str(self.files_processed),
        }
