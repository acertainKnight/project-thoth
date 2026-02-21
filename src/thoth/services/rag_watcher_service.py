"""
RAG Watcher Service for automatic document processing and indexing.

This service watches directories for new PDFs and markdown files,
automatically processing them through the full RAG pipeline:
1. PDF → Markdown conversion (via OCR)
2. Markdown → Chunking → Embedding → Vector storage
"""

import asyncio
import time
from pathlib import Path
from typing import Any

from loguru import logger
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from thoth.services.base import BaseService, ServiceError
from thoth.services.processing_service import ProcessingService
from thoth.services.rag_service import RAGService


class RAGFileHandler(FileSystemEventHandler):
    """File system event handler for RAG pipeline automation."""

    def __init__(
        self,
        processing_service: ProcessingService,
        rag_service: RAGService,
        config: Any,
    ):
        """
        Initialize the handler.

        Args:
            processing_service: Service for PDF processing
            rag_service: Service for RAG indexing
            config: Configuration object
        """
        super().__init__()
        self.processing_service = processing_service
        self.rag_service = rag_service
        self.config = config
        self.processing_queue: dict[str, float] = {}  # path -> timestamp
        self.debounce_seconds = 2.0  # Wait 2s before processing
        self._user_id_cache: dict[str, str] = {}  # username -> user_id

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process PDFs and markdown files
        if file_path.suffix.lower() in ['.pdf', '.md']:
            self._queue_for_processing(file_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # Only process markdown files on modification
        # (PDFs shouldn't change after creation)
        if file_path.suffix.lower() == '.md':
            self._queue_for_processing(file_path)

    def _queue_for_processing(self, file_path: Path) -> None:
        """
        Queue a file for processing with debounce.

        Args:
            file_path: Path to the file
        """
        self.processing_queue[str(file_path)] = time.time()

    async def process_queue(self) -> None:
        """Process queued files after debounce period."""
        current_time = time.time()
        to_process = []

        # Find files ready for processing
        for path_str, queued_time in list(self.processing_queue.items()):
            if current_time - queued_time >= self.debounce_seconds:
                to_process.append(path_str)
                del self.processing_queue[path_str]

        # Process each file
        for path_str in to_process:
            file_path = Path(path_str)
            try:
                await self._process_file(file_path)
            except Exception as e:
                print(f'Error processing {file_path}: {e}')

    async def _process_file(self, file_path: Path) -> None:
        """
        Process a single file through the RAG pipeline.

        Args:
            file_path: Path to the file
        """
        if not file_path.exists():
            return

        if file_path.suffix.lower() == '.pdf':
            # PDF → Markdown conversion
            try:
                print(f'Processing PDF: {file_path.name}')
                markdown_path, _ = self.processing_service.ocr_convert(
                    pdf_path=file_path,
                )
                print(f'Converted to markdown: {markdown_path}')

                # Index the markdown immediately
                await self._index_markdown(markdown_path)

            except Exception as e:
                print(f'Error converting PDF {file_path}: {e}')

        elif file_path.suffix.lower() == '.md':
            # Markdown → Chunking → Embedding
            await self._index_markdown(file_path)

    async def _index_markdown(self, markdown_path: Path) -> None:
        """
        Index a markdown file into the RAG system.

        Args:
            markdown_path: Path to the markdown file
        """
        try:
            print(f'Indexing markdown: {markdown_path.name}')
            user_id = await self._resolve_user_id_from_path(markdown_path)

            # Use async version to avoid event loop conflicts
            doc_ids = self.rag_service.index_file(markdown_path, user_id=user_id)

            print(
                f'Indexed {len(doc_ids)} chunks from {markdown_path.name} into vector store'
            )

        except Exception as e:
            print(f'Error indexing markdown {markdown_path}: {e}')

    async def _resolve_user_id_from_path(self, file_path: Path) -> str | None:
        """Resolve user_id from a vault file path in multi-user mode."""
        if not getattr(self.config, 'multi_user', False):
            return None

        vaults_root = getattr(self.config, 'vaults_root', None)
        if vaults_root is None:
            return None

        try:
            relative = file_path.resolve().relative_to(vaults_root.resolve())
        except ValueError:
            return None

        if not relative.parts:
            return None

        username = relative.parts[0]
        if username in self._user_id_cache:
            return self._user_id_cache[username]

        db_url = getattr(self.config.secrets, 'database_url', None)
        if not db_url:
            logger.warning('Cannot resolve user_id from path: DATABASE_URL missing')
            return None

        import asyncpg

        conn = await asyncpg.connect(db_url)
        try:
            row = await conn.fetchrow(
                'SELECT id FROM users WHERE username = $1 AND is_active = TRUE',
                username,
            )
        finally:
            await conn.close()

        if row is None:
            logger.warning(f'No active user found for vault path username={username}')
            return None

        user_id = str(row['id'])
        self._user_id_cache[username] = user_id
        return user_id


class RAGWatcherService(BaseService):
    """
    Service for watching directories and automatically processing documents.

    This service monitors configured directories for:
    - New PDF files → converts to markdown → indexes
    - New/modified markdown files → indexes into vector store
    """

    def __init__(
        self,
        config=None,
        processing_service: ProcessingService | None = None,
        rag_service: RAGService | None = None,
    ):
        """
        Initialize the RAG watcher service.

        Args:
            config: Optional configuration object
            processing_service: Optional processing service
            rag_service: Optional RAG service
        """
        super().__init__(config)
        self._processing_service = processing_service
        self._rag_service = rag_service
        self._observer: Observer | None = None
        self._is_running = False
        self._watch_task: asyncio.Task | None = None

    @property
    def processing_service(self) -> ProcessingService:
        """Get or create the processing service."""
        if self._processing_service is None:
            self._processing_service = ProcessingService(self.config)
            self._processing_service.initialize()
        return self._processing_service

    @property
    def rag_service(self) -> RAGService:
        """Get or create the RAG service."""
        if self._rag_service is None:
            self._rag_service = RAGService(self.config)
            self._rag_service.initialize()
        return self._rag_service

    def initialize(self) -> None:
        """Initialize the watcher service."""
        self.logger.info('RAG watcher service initialized')

    def start_multi_user(self, vaults_root: Path, users: list[str]) -> None:
        """
        Start watching vault directories for all registered users.

        In multi-user mode, each user has their own vault under vaults_root.
        This method collects all per-user pdf/markdown/notes directories and
        starts a single shared watcher that monitors all of them.

        Args:
            vaults_root: Root directory containing all user vaults (THOTH_VAULTS_ROOT)
            users: List of usernames to watch (from the users table)

        Example:
            >>> watcher.start_multi_user(Path('/vaults'), ['alice', 'bob'])
        """
        watch_dirs = []
        for username in users:
            user_vault = vaults_root / username / 'thoth'
            for sub in ('papers/pdfs', 'papers/markdown', 'notes'):
                candidate = user_vault / sub
                if candidate.exists():
                    watch_dirs.append(candidate)

        if not watch_dirs:
            self.logger.warning(
                f'No vault directories found under {vaults_root} for users {users}'
            )
            return

        self.logger.info(
            f'Multi-user RAG watcher: watching {len(watch_dirs)} directories '
            f'across {len(users)} users'
        )
        self.start(watch_dirs=watch_dirs)

    def start(self, watch_dirs: list[Path] | None = None) -> None:
        """
        Start watching directories for new files.

        Args:
            watch_dirs: List of directories to watch (defaults to config)

        Raises:
            ServiceError: If starting fails
        """
        if self._is_running:
            self.logger.warning('RAG watcher is already running')
            return

        try:
            # Determine which directories to watch
            if watch_dirs is None:
                watch_dirs = [
                    self.config.pdf_dir,
                    self.config.markdown_dir,
                    self.config.notes_dir,
                ]

            # Create event handler
            handler = RAGFileHandler(
                processing_service=self.processing_service,
                rag_service=self.rag_service,
                config=self.config,
            )

            # Create observer
            self._observer = Observer()

            # Schedule watches for each directory
            for watch_dir in watch_dirs:
                if watch_dir.exists():
                    self._observer.schedule(handler, str(watch_dir), recursive=True)
                    self.logger.info(f'Watching directory: {watch_dir}')
                else:
                    self.logger.warning(f'Directory does not exist: {watch_dir}')

            # Start observer
            self._observer.start()
            self._is_running = True

            # Start queue processing task
            self._watch_task = asyncio.create_task(self._process_queue_loop(handler))

            self.logger.success('RAG watcher started successfully')
            self.log_operation(
                'watcher_started', directories=[str(d) for d in watch_dirs]
            )

        except Exception as e:
            self.logger.error(f'Error starting RAG watcher: {e}')
            raise ServiceError(self.handle_error(e, 'starting RAG watcher')) from e

    async def _process_queue_loop(self, handler: RAGFileHandler) -> None:
        """
        Background task to process queued files.

        Args:
            handler: The file handler with the processing queue
        """
        while self._is_running:
            try:
                await handler.process_queue()
                await asyncio.sleep(1)  # Check queue every second
            except Exception as e:
                self.logger.error(f'Error in queue processing: {e}')
                await asyncio.sleep(5)  # Back off on error

    def stop(self) -> None:
        """
        Stop watching directories.

        Raises:
            ServiceError: If stopping fails
        """
        if not self._is_running:
            self.logger.warning('RAG watcher is not running')
            return

        try:
            self._is_running = False

            # Cancel watch task
            if self._watch_task:
                self._watch_task.cancel()
                self._watch_task = None

            # Stop observer
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None

            self.logger.info('RAG watcher stopped')
            self.log_operation('watcher_stopped')

        except Exception as e:
            self.logger.error(f'Error stopping RAG watcher: {e}')
            raise ServiceError(self.handle_error(e, 'stopping RAG watcher')) from e

    def is_running(self) -> bool:
        """Check if the watcher is running."""
        return self._is_running

    def get_status(self) -> dict[str, Any]:
        """
        Get current watcher status.

        Returns:
            dict[str, Any]: Status information
        """
        return {
            'is_running': self._is_running,
            'watched_directories': (
                [
                    str(self.config.pdf_dir),
                    str(self.config.markdown_dir),
                    str(self.config.notes_dir),
                ]
                if self._is_running
                else []
            ),
        }

    def health_check(self) -> dict[str, str]:
        """Health check for the watcher service."""
        status = super().health_check()
        status['is_running'] = 'yes' if self._is_running else 'no'
        return status
