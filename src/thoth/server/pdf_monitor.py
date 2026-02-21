"""
PDF Monitor for Thoth.

This module provides functionality to monitor a directory for new PDF files
and process them through the Thoth pipeline automatically.
"""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from thoth.pipeline import ThothPipeline
    from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline

from loguru import logger

from thoth.config import config
from thoth.utilities.vault_path_resolver import VaultPathResolver

# Optional watchdog dependency for PDF monitoring
# Not required for MCP service
try:
    from watchdog.events import FileCreatedEvent, FileSystemEventHandler
    from watchdog.observers.polling import PollingObserver

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

    # Define stub classes for type hints
    class FileSystemEventHandler:  # type: ignore
        pass

    class FileCreatedEvent:  # type: ignore
        pass

    class PollingObserver:  # type: ignore
        pass


if TYPE_CHECKING:
    from thoth.pipeline import ThothPipeline


def _resolve_user_id_from_path(
    file_path: Path, cfg: object, cache: dict[str, str] | None = None
) -> str | None:
    """Resolve user_id from vault path when running in multi-user mode."""
    multi_user = bool(getattr(cfg, 'multi_user', False))
    vaults_root = getattr(cfg, 'vaults_root', None)
    if not multi_user or vaults_root is None:
        return None

    try:
        relative = file_path.resolve().relative_to(Path(vaults_root).resolve())
    except ValueError:
        return None

    if not relative.parts:
        return None

    username = relative.parts[0]
    if cache is not None and username in cache:
        return cache[username]

    db_url = (
        getattr(cfg.secrets, 'database_url', None) if hasattr(cfg, 'secrets') else None
    )
    if not db_url:
        return None

    from urllib.parse import urlparse

    import psycopg2

    parsed = urlparse(db_url)
    conn_params = {
        'host': parsed.hostname,
        'port': parsed.port or 5432,
        'user': parsed.username,
        'password': parsed.password,
        'database': parsed.path.lstrip('/'),
    }

    conn = psycopg2.connect(**conn_params)
    try:
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id FROM users WHERE username = %s AND is_active = TRUE',
            (username,),
        )
        row = cursor.fetchone()
        cursor.close()
    finally:
        conn.close()

    if not row:
        return None

    user_id = str(row[0])
    if cache is not None:
        cache[username] = user_id
    return user_id


class PDFTracker:
    """
    Persistent tracker for processed PDF files.

    This class maintains a record of processed files in a JSON file to ensure
    files aren't reprocessed after monitor restarts.
    """

    def __init__(self, track_file: Path | None = None):
        """
        Initialize the PDF tracker.

        Args:
            track_file: Path to the JSON file for tracking. If None, a default path is used.
        """  # noqa: W505
        self.config = config
        self.multi_user = bool(getattr(self.config, 'multi_user', False))
        self.vaults_root = getattr(self.config, 'vaults_root', None)
        self._user_id_cache: dict[str, str] = {}
        self.track_file = (
            track_file or Path(self.config.output_dir) / 'processed_pdfs.json'
        )

        # Initialize vault path resolver
        vault_root = getattr(self.config, 'vault_root', None)
        if vault_root:
            self.vault_resolver = VaultPathResolver(vault_root)
            logger.debug(f'VaultPathResolver initialized with vault root: {vault_root}')
        else:
            self.vault_resolver = None
            logger.warning('No vault_root in config - vault-relative paths disabled')

        # Ensure the parent directory exists
        self.track_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing tracked files
        self.processed_files: dict[str, dict] = {}
        self._load_tracked_files()

        # Legacy: JSON file is no longer used for tracking (migrated to PostgreSQL).
        # Docker healthcheck verifies the process is alive instead.

        logger.info(f'PDF tracker initialized with tracking file: {self.track_file}')

    def _storage_key(self, file_path: Path) -> str:
        """Build storage key for processed file tracking."""
        resolved = file_path.resolve()
        if self.multi_user and self.vaults_root:
            try:
                return str(
                    resolved.relative_to(Path(self.vaults_root).resolve())
                ).replace('\\', '/')
            except ValueError:
                pass

        if self.vault_resolver:
            try:
                return self.vault_resolver.make_relative(resolved)
            except ValueError:
                pass

        return str(resolved)

    def _load_tracked_files(self):
        """
        Load the list of tracked files from PostgreSQL.
        """
        try:
            self._load_from_postgres()
        except Exception as e:
            logger.error(f'Error loading tracked files from PostgreSQL: {e}')
            self.processed_files = {}

    def _load_from_postgres_legacy(self):
        """Legacy method - load from JSON file (deprecated)."""
        if self.track_file.exists():
            try:
                with open(self.track_file) as f:
                    loaded_data = json.load(f)

                # Migrate absolute paths to relative if vault resolver is available
                if self.vault_resolver and loaded_data:
                    migrated_count = 0
                    migrated_data = {}

                    for key, value in loaded_data.items():
                        key_path = Path(key)

                        # Check if key is absolute and within vault
                        if (
                            key_path.is_absolute()
                            and self.vault_resolver.is_vault_relative(key)
                        ):
                            try:
                                # Convert to vault-relative
                                relative_key = self.vault_resolver.make_relative(key)
                                migrated_data[relative_key] = value
                                migrated_count += 1
                                logger.debug(f'Migrated path: {key} → {relative_key}')

                                # Migrate paths in metadata too
                                if 'new_pdf_path' in value:
                                    pdf_path = Path(value['new_pdf_path'])
                                    if (
                                        pdf_path.is_absolute()
                                        and self.vault_resolver.is_vault_relative(
                                            pdf_path
                                        )
                                    ):
                                        value['new_pdf_path'] = (
                                            self.vault_resolver.make_relative(pdf_path)
                                        )

                                if 'note_path' in value:
                                    note_path = Path(value['note_path'])
                                    if (
                                        note_path.is_absolute()
                                        and self.vault_resolver.is_vault_relative(
                                            note_path
                                        )
                                    ):
                                        value['note_path'] = (
                                            self.vault_resolver.make_relative(note_path)
                                        )
                            except ValueError as e:
                                # Path not in vault, keep as-is
                                logger.warning(
                                    f'Cannot migrate path outside vault: {key} - {e}'
                                )
                                migrated_data[key] = value
                        else:
                            # Already relative or not absolute, keep as-is
                            migrated_data[key] = value

                    self.processed_files = migrated_data

                    if migrated_count > 0:
                        logger.info(
                            f'Migrated {migrated_count} absolute paths to vault-relative'
                        )
                        # Create backup before saving migrated data
                        backup_path = self.track_file.with_suffix(
                            '.json.pre-migration-bak'
                        )
                        try:
                            import shutil

                            shutil.copy2(self.track_file, backup_path)
                            logger.info(
                                f'Created pre-migration backup at {backup_path}'
                            )
                        except Exception as e:
                            logger.error(f'Failed to create backup: {e}')

                        # Save migrated data
                        self._save_tracked_files()
                else:
                    self.processed_files = loaded_data

                logger.info(
                    f'Loaded {len(self.processed_files)} tracked files from {self.track_file}'
                )
            except (OSError, json.JSONDecodeError) as e:
                logger.error(f'Error loading tracked files: {e}')
                # Create a backup of the corrupted file
                if self.track_file.exists():
                    backup_path = self.track_file.with_suffix('.json.bak')
                    try:
                        import shutil

                        shutil.copy2(self.track_file, backup_path)
                        logger.info(
                            f'Created backup of corrupted tracking file at {backup_path}'
                        )
                    except Exception as e:
                        logger.error(f'Failed to create backup: {e}')
                # Initialize with empty dict
                self.processed_files = {}
        else:
            logger.info(f'No existing tracking file found at {self.track_file}')
            self.processed_files = {}

    def _load_from_postgres(self) -> None:
        """Load processed PDFs tracking from PostgreSQL using synchronous psycopg2."""
        from urllib.parse import urlparse

        import psycopg2

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            print('PDFTracker: No DATABASE_URL found!', flush=True)
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        print('PDFTracker: _load_from_postgres() called', flush=True)
        print(f'PDFTracker: DATABASE_URL configured: {db_url[:30]}...', flush=True)

        # Parse PostgreSQL URL for psycopg2
        parsed = urlparse(db_url)
        conn_params = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path.lstrip('/'),
        }

        print('PDFTracker: Connecting to PostgreSQL...', flush=True)
        conn = psycopg2.connect(**conn_params)
        try:
            print('PDFTracker: Connected, fetching rows...', flush=True)
            cursor = conn.cursor()
            cursor.execute(
                'SELECT pdf_path, new_pdf_path, note_path, file_size, file_mtime, user_id FROM processed_pdfs'
            )
            rows = cursor.fetchall()
            print(f'PDFTracker: Fetched {len(rows)} rows from database', flush=True)

            for row in rows:
                # Stored paths are already relative (e.g., "thoth/papers/pdfs/file.pdf")
                pdf_path_key = row[0]  # pdf_path (original path)
                new_pdf_path = row[1]  # new_pdf_path (renamed path)

                # Build tracked file info with database values
                tracked_info = {
                    'new_pdf_path': new_pdf_path,
                    'note_path': row[2],  # note_path
                }

                # Add size and mtime from database if available
                if row[3] is not None:  # file_size
                    tracked_info['size'] = row[3]
                if row[4] is not None:  # file_mtime
                    tracked_info['mtime'] = row[4]
                if row[5] is not None:  # user_id
                    tracked_info['user_id'] = row[5]

                # Store under original path only
                # is_processed() will check both pdf_path and new_pdf_path columns
                self.processed_files[str(pdf_path_key)] = tracked_info

            cursor.close()
            print(
                f'PDFTracker: Loaded {len(rows)} files into processed_files dict',
                flush=True,
            )
            logger.info(f'Loaded {len(rows)} processed PDFs from PostgreSQL')
        finally:
            conn.close()
            print('PDFTracker: Database connection closed', flush=True)

    def _save_tracked_files(self):
        """
        Save the list of tracked files to PostgreSQL.
        """
        try:
            self._save_to_postgres()
        except Exception as e:
            logger.error(f'Error saving tracked files: {e}')

    def _save_to_postgres(self) -> None:
        """Save processed PDFs tracking to PostgreSQL using synchronous psycopg2."""
        from urllib.parse import urlparse

        import psycopg2

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        # Parse PostgreSQL URL for psycopg2
        parsed = urlparse(db_url)
        conn_params = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'user': parsed.username,
            'password': parsed.password,
            'database': parsed.path.lstrip('/'),
        }

        conn = psycopg2.connect(**conn_params)
        try:
            cursor = conn.cursor()
            for pdf_path_key, metadata in self.processed_files.items():
                # Ensure we're storing normalized tracking keys
                pdf_path = pdf_path_key
                if Path(pdf_path_key).is_absolute():
                    pdf_path = self._storage_key(Path(pdf_path_key))

                cursor.execute(
                    """
                    INSERT INTO processed_pdfs (pdf_path, new_pdf_path, note_path, file_size, file_mtime, user_id, processed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (pdf_path) DO UPDATE SET
                        new_pdf_path = EXCLUDED.new_pdf_path,
                        note_path = EXCLUDED.note_path,
                        file_size = EXCLUDED.file_size,
                        file_mtime = EXCLUDED.file_mtime,
                        user_id = EXCLUDED.user_id
                    """,
                    (
                        str(pdf_path),
                        metadata.get('new_pdf_path'),
                        metadata.get('note_path'),
                        metadata.get('size'),
                        metadata.get('mtime'),
                        metadata.get('user_id', 'default_user'),
                    ),
                )

            conn.commit()
            cursor.close()
            logger.info(
                f'Saved {len(self.processed_files)} processed PDFs to PostgreSQL'
            )
            print(
                f'PDFTracker: Saved {len(self.processed_files)} processed PDFs to PostgreSQL',
                flush=True,
            )
        finally:
            conn.close()

    def is_processed(self, file_path: Path) -> bool:
        """
        Check if a file has been processed by checking both original and renamed paths.

        Args:
            file_path: Path to the file to check.

        Returns:
            bool: True if the file has been processed, False otherwise.
        """
        lookup_key = self._storage_key(file_path)
        if lookup_key in self.processed_files:
            return True

        for metadata in self.processed_files.values():
            if metadata.get('new_pdf_path') == lookup_key:
                return True

        # Fallback to absolute path checks for older tracker entries
        abs_path = str(file_path.resolve())
        if abs_path in self.processed_files:
            return True

        for metadata in self.processed_files.values():
            if metadata.get('new_pdf_path') == abs_path:
                return True

        return False

    def get_note_path(self, file_path: Path) -> Path | None:
        """
        Get the note path for a processed file.
        Handles both absolute and relative paths in tracker.

        Args:
            file_path: Path to the file.
        Returns:
            Path | None: The path to the note, or None if not found.
        """
        lookup_key = self._storage_key(file_path)
        if lookup_key in self.processed_files:
            note_path_str = self.processed_files[lookup_key].get('note_path')
            if note_path_str:
                note_path = Path(note_path_str)
                if not note_path.is_absolute():
                    if self.multi_user and self.vaults_root:
                        return Path(self.vaults_root) / note_path
                    if self.vault_resolver:
                        return self.vault_resolver.resolve(note_path_str)
                return note_path

        # Fallback to absolute-path lookup for old records
        abs_path = str(file_path.resolve())
        if abs_path in self.processed_files:
            note_path_str = self.processed_files[abs_path].get('note_path')
            if note_path_str:
                note_path = Path(note_path_str)
                return note_path
        return None

    def mark_processed(self, file_path: Path, metadata: dict | None = None):
        """
        Mark a file as processed.
        Stores paths as vault-relative when possible.

        Args:
            file_path: Path to the original file to mark as processed.
            metadata: Optional metadata to store with the file. Should include
                'new_pdf_path' if renamed.
        """
        storage_key = self._storage_key(file_path)
        logger.debug(f'Storing with normalized key: {storage_key}')

        # Determine which path to use for getting file stats
        # If the file was renamed, the new path is in metadata
        new_path_str = metadata.get('new_pdf_path') if metadata else None
        path_for_stats = (
            Path(new_path_str)
            if new_path_str and Path(new_path_str).exists()
            else file_path
        )

        try:
            # Get file stats for verification from the path that currently exists
            stats = path_for_stats.stat()
        except FileNotFoundError:
            logger.error(
                f'Cannot get stats, file not found at {path_for_stats} or {file_path}. Cannot mark as processed.'
            )
            return

        # Prepare all data to be stored in the tracker
        processed_data = {
            'processed_time': time.time(),
            'size': stats.st_size,
            'mtime': stats.st_mtime,
        }
        if metadata:
            # Merge metadata, converting paths to vault-relative where possible
            processed_data.update(metadata)

            # Convert new_pdf_path to normalized storage key
            if 'new_pdf_path' in processed_data:
                pdf_path = Path(processed_data['new_pdf_path']).resolve()
                processed_data['new_pdf_path'] = self._storage_key(pdf_path)

            # Convert note_path to normalized storage key
            if 'note_path' in processed_data:
                note_path = Path(processed_data['note_path']).resolve()
                processed_data['note_path'] = self._storage_key(note_path)

        user_id = _resolve_user_id_from_path(
            path_for_stats, self.config, self._user_id_cache
        )
        if user_id:
            processed_data['user_id'] = user_id
        else:
            processed_data.setdefault('user_id', 'default_user')

        # Store file with metadata, using vault-relative key when possible
        self.processed_files[storage_key] = processed_data

        # Save the updated tracking information
        self._save_tracked_files()

        logger.debug(f'Marked file as processed: {storage_key}')

    def verify_file_unchanged(self, file_path: Path) -> bool:
        """
        Verify that a file hasn't changed since it was processed.

        Args:
            file_path: Path to the file to check.

        Returns:
            bool: True if the file is unchanged, False otherwise.
        """
        lookup_key = self._storage_key(file_path)

        # If file isn't tracked, it's considered changed
        if lookup_key not in self.processed_files:
            return False

        # Get current file stats
        try:
            stats = file_path.stat()
            tracked_info = self.processed_files[lookup_key]

            # Migration: if size/mtime not in tracker, backfill from filesystem
            if 'size' not in tracked_info or 'mtime' not in tracked_info:
                logger.debug(f'Backfilling size/mtime for {lookup_key} from filesystem')
                tracked_info['size'] = stats.st_size
                tracked_info['mtime'] = stats.st_mtime
                # Save the updated tracker immediately
                self._save_tracked_files()
                return True  # File is now tracked properly, consider it unchanged

            # Check if size or modification time changed
            if (
                stats.st_size != tracked_info['size']
                or stats.st_mtime != tracked_info['mtime']
            ):
                logger.info(f'File has changed since last processing: {file_path}')
                return False

            return True
        except (FileNotFoundError, KeyError):
            return False


class PDFHandler(FileSystemEventHandler):
    """
    Handler for PDF file events.

    This class handles file system events for PDF files, triggering
    the processing pipeline when new PDFs are detected.
    """

    def __init__(self, pipeline: 'ThothPipeline'):
        """
        Initialize the PDF handler.

        Args:
            pipeline: Thoth pipeline to process PDFs (ThothPipeline or
                OptimizedDocumentPipeline).
        """
        # Store the pipeline - could be ThothPipeline or OptimizedDocumentPipeline
        self.pipeline = pipeline
        self.config = config
        self._user_id_cache: dict[str, str] = {}

    def on_created(self, event):
        """
        Handle file creation events.

        Args:
            event: The file system event.
        """
        if not isinstance(event, FileCreatedEvent):
            return

        file_path = Path(event.src_path)

        # Only process PDF files
        if file_path.suffix.lower() != '.pdf':
            return

        logger.info(f'New PDF detected: {file_path}')

        try:
            # The pipeline handles tracking and reprocessing checks
            # Works with both ThothPipeline and OptimizedDocumentPipeline
            user_id = _resolve_user_id_from_path(
                file_path, self.config, self._user_id_cache
            )
            self.pipeline.process_pdf(file_path, user_id=user_id)
        except Exception as e:
            logger.error(f'Error processing {file_path}: {e!s}')


class PDFMonitor:
    """
    Monitor for PDF files.

    This class watches a directory for new PDF files and processes them
    through the Thoth pipeline.
    """

    def __init__(
        self,
        watch_dir: Path | None = None,
        pipeline: Optional['ThothPipeline'] = None,
        document_pipeline: Optional['OptimizedDocumentPipeline'] = None,
        polling_interval: float = 1.0,
        recursive: bool = False,
    ):
        """
        Initialize the PDF monitor.

        Args:
            watch_dir: Directory to watch for PDF files. If None, loaded from config.
            pipeline: DEPRECATED. ThothPipeline instance. Use document_pipeline instead.
            document_pipeline: OptimizedDocumentPipeline. If None, one is created.
            polling_interval: Interval in seconds for polling the directory.
            recursive: Whether to watch subdirectories recursively.
        """
        import warnings

        self.config = config
        self._user_id_cache: dict[str, str] = {}
        self.watch_dir = watch_dir or self.config.pdf_dir
        self.multi_user = bool(getattr(self.config, 'multi_user', False))
        self.watch_dirs: list[Path] = []

        if (
            self.multi_user
            and watch_dir is None
            and getattr(self.config, 'vaults_root', None)
        ):
            self.watch_dirs = [Path(self.config.vaults_root)]
            self.watch_dir = self.watch_dirs[0]
            recursive = True
        else:
            self.watch_dirs = [self.watch_dir]

        # Ensure watch directories exist
        for directory in self.watch_dirs:
            directory.mkdir(parents=True, exist_ok=True)

        # Handle both old and new parameters for backward compatibility
        if pipeline is not None and document_pipeline is not None:
            raise ValueError(
                "Cannot specify both 'pipeline' and 'document_pipeline' parameters. "
                "Use 'document_pipeline' only (pipeline is deprecated)."
            )

        if pipeline is not None:
            # OLD parameter - issue deprecation warning
            warnings.warn(
                "PDFMonitor parameter 'pipeline' is deprecated and will be removed in a future version. "
                "Use 'document_pipeline' instead:\n\n"
                '    from thoth.initialization import initialize_thoth\n'
                '    _, document_pipeline, _ = initialize_thoth()\n'
                '    monitor = PDFMonitor(document_pipeline=document_pipeline)\n',
                DeprecationWarning,
                stacklevel=2,
            )
            # Extract the document pipeline from ThothPipeline wrapper
            # Check if it's actually a ThothPipeline by checking for the class name
            if pipeline.__class__.__name__ == 'ThothPipeline' and hasattr(
                pipeline, 'document_pipeline'
            ):
                self.pipeline = pipeline.document_pipeline
            else:
                # OptimizedDocumentPipeline or mock: use as-is
                self.pipeline = pipeline
        elif document_pipeline is not None:
            # NEW parameter - use directly
            self.pipeline = document_pipeline
        else:
            # Neither provided - create new pipeline using initialize_thoth()
            from thoth.initialization import initialize_thoth

            _, self.pipeline, _ = initialize_thoth()

        # Set up the observer
        self.observer = PollingObserver(timeout=polling_interval)
        self.polling_interval = polling_interval
        self.recursive = recursive

        # Track current watch directory for reload detection
        self._current_watch_dir = self.watch_dir
        self.is_running = False
        self.files_processed = 0
        self.last_check = None

        # Register for config reload notifications
        if hasattr(self.config, 'register_reload_callback'):
            from thoth.config import Config

            Config.register_reload_callback('pdf_monitor', self._on_config_reload)
            logger.debug('PDFMonitor registered for config reload notifications')

        logger.info(
            f'PDF monitor initialized to watch: {self.watch_dir} (recursive: {self.recursive})'
        )

    def start(self):
        """
        Start monitoring the directory.

        This method initiates the file system monitor and begins watching
        for new PDF files.
        """
        print('MONITOR:  PDFMonitor.start() method entered', flush=True)
        logger.info('PDFMonitor.start() method called')
        print(f'MONITOR:  WATCHDOG_AVAILABLE = {WATCHDOG_AVAILABLE}', flush=True)
        logger.info(f'WATCHDOG_AVAILABLE = {WATCHDOG_AVAILABLE}')

        if not WATCHDOG_AVAILABLE:
            print('MONITOR:   Watchdog not available!', flush=True)
            logger.warning('Watchdog not available, PDF monitoring disabled')
            return

        # Process existing files first
        print('MONITOR:  About to call _process_existing_files()...', flush=True)
        logger.info('About to call _process_existing_files()...')
        self._process_existing_files()
        print('MONITOR:  _process_existing_files() completed', flush=True)
        logger.info('_process_existing_files() completed')

        # DEBUG: Explicit trace before observer start
        print('MONITOR:  Line 728: About to call _start_observer()...', flush=True)
        logger.info('Line 728: About to call _start_observer()...')

        # Set up and start the observer
        try:
            print('MONITOR:  Line 732: Calling _start_observer()...', flush=True)
            self._start_observer()
            print(
                'MONITOR:  Line 734: _start_observer() returned successfully',
                flush=True,
            )
            logger.info('_start_observer() returned successfully')
        except Exception as e:
            print(f'MONITOR:  EXCEPTION in _start_observer(): {e!s}', flush=True)
            logger.exception('EXCEPTION in _start_observer():')
            raise

        # Track current watch directory and mark as running
        self._current_watch_dir = self.watch_dir
        self.is_running = True

        logger.info(f'Started monitoring {self.watch_dir} for new PDF files')

        # Watch for settings file changes (hot reload)
        # Try to find settings file - check environment variable first
        import os

        settings_path = None

        # Check environment variable first
        env_settings = os.getenv('THOTH_SETTINGS_FILE')
        if env_settings and Path(env_settings).exists():
            settings_path = Path(env_settings)
            logger.info(
                f'Hot reload enabled - watching settings from env: {settings_path}'
            )
        else:
            # Fall back to common locations
            for path in [
                './thoth.settings.json',
                './workspace/settings.json',
                './thoth/_thoth/settings.json',
                './_thoth/settings.json',
                Path.home() / '.config/thoth/settings.json',
            ]:
                if Path(path).exists():
                    settings_path = Path(path)
                    logger.info(
                        f'Hot reload enabled - watching settings: {settings_path}'
                    )
                    break

        last_settings_mtime = (
            settings_path.stat().st_mtime
            if settings_path and settings_path.exists()
            else 0
        )

        try:
            while True:
                time.sleep(self.polling_interval)

                # Check if settings file changed (hot reload)
                if settings_path and settings_path.exists():
                    current_mtime = settings_path.stat().st_mtime
                    if current_mtime > last_settings_mtime:
                        logger.info('Settings file changed, reloading configuration...')
                        try:
                            # Reload config from file and notify all services
                            config.reload_settings()

                            # Check if watch directories changed in settings
                            if hasattr(self.config, 'monitor_config') and hasattr(
                                self.config.monitor_config, 'watch_directories'
                            ):
                                new_watch_dirs = (
                                    self.config.monitor_config.watch_directories
                                )
                                logger.info(
                                    f'Settings updated - watch directories: {new_watch_dirs}'
                                )

                            last_settings_mtime = current_mtime
                            logger.info('Configuration reloaded successfully')
                        except Exception as e:
                            logger.error(f'Failed to reload settings: {e}')

        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """
        Stop monitoring the directory.
        """
        logger.info('Attempting to stop PDF monitoring...')
        self.is_running = False

        if self.observer is not None:
            self.observer.stop()
            try:
                self.observer.join(timeout=2.0)  # Add a timeout to the join call
                if self.observer.is_alive():
                    logger.warning(
                        'Observer thread did not stop in time. Forcing shutdown.'
                    )
                    # If it's a PollingObserver, there isn't a direct force stop.
                    # The process will exit when the main thread finishes.
                    # For other observers like InotifyObserver, there might be OS-level cleanup.  # noqa: W505
                else:
                    logger.info('Observer thread stopped successfully.')
            except Exception as e:
                logger.error(f'Exception during observer shutdown: {e}')

        logger.info('PDF monitoring stopped')

    def _process_existing_files(self):
        """
        Process any existing PDF files in the watch directory.
        """
        print('MONITOR:  _process_existing_files() entered', flush=True)
        logger.info(
            f'Checking for existing PDF files in {len(self.watch_dirs)} watch directories'
        )

        # Use recursive glob if recursive flag is set
        glob_pattern = '**/*.pdf' if self.recursive else '*.pdf'
        print(f'MONITOR:  Using glob pattern: {glob_pattern}', flush=True)

        # Count files first
        print('MONITOR:  Globbing for PDF files...', flush=True)
        pdf_files: list[Path] = []
        for watch_dir in self.watch_dirs:
            pdf_files.extend(list(watch_dir.glob(glob_pattern)))
        print(
            f'MONITOR:  Found {len(pdf_files)} PDF files before filtering', flush=True
        )

        if self.recursive:
            pdf_files = [f for f in pdf_files if f.is_file()]
            print(f'MONITOR:  After filtering: {len(pdf_files)} files', flush=True)

        # CRITICAL FIX: Pre-filter to only unprocessed PDFs BEFORE iterating
        if self.pipeline.pdf_tracker:
            unprocessed_files = []
            for pdf_file in pdf_files:
                # Check if already processed and unchanged
                if not (
                    self.pipeline.pdf_tracker.is_processed(pdf_file)
                    and self.pipeline.pdf_tracker.verify_file_unchanged(pdf_file)
                ):
                    unprocessed_files.append(pdf_file)

            print(
                f'MONITOR:  Pre-filter results: {len(unprocessed_files)} unprocessed out of {len(pdf_files)} total PDFs',
                flush=True,
            )
            logger.info(
                f'Pre-filter: {len(unprocessed_files)} unprocessed out of {len(pdf_files)} total PDFs'
            )
            pdf_files = unprocessed_files

        logger.info(f'Found {len(pdf_files)} PDF files to process')
        print(f'MONITOR:  Starting to process {len(pdf_files)} PDFs', flush=True)

        for i, pdf_file in enumerate(pdf_files, 1):
            print(
                f'MONITOR:  Processing #{i}/{len(pdf_files)}: {pdf_file.name}',
                flush=True,
            )
            logger.info(f'Processing PDF {i}/{len(pdf_files)}: {pdf_file.name}')

            try:
                # The pipeline now handles tracking and reprocessing checks
                print(
                    f'MONITOR:   Calling pipeline.process_pdf() for {pdf_file.name}...',
                    flush=True,
                )
                logger.info(f'Calling pipeline.process_pdf() for {pdf_file.name}...')
                user_id = _resolve_user_id_from_path(
                    pdf_file, self.config, self._user_id_cache
                )
                self.pipeline.process_pdf(pdf_file, user_id=user_id)
                print(
                    f'MONITOR:  process_pdf() returned for {pdf_file.name}',
                    flush=True,
                )
                self.files_processed += 1
                logger.info(f'Successfully processed {pdf_file.name}')
            except Exception as e:
                print(
                    f'MONITOR:  Exception processing {pdf_file.name}: {e!s}',
                    flush=True,
                )
                logger.error(f'Error processing existing file {pdf_file}: {e!s}')
                logger.exception('Full traceback:')

        # Update last check time
        from datetime import datetime

        self.last_check = datetime.now()

    def _start_observer(self):
        """
        Start or restart the observer with current watch directory.
        """
        print('MONITOR:  _start_observer() ENTERED', flush=True)
        logger.info('_start_observer() ENTERED')

        print('MONITOR:  Creating PDFHandler...', flush=True)
        event_handler = PDFHandler(self.pipeline)
        print('MONITOR:  PDFHandler created', flush=True)

        for watch_dir in self.watch_dirs:
            print(f'MONITOR:  Scheduling observer for {watch_dir}...', flush=True)
            self.observer.schedule(
                event_handler, str(watch_dir), recursive=self.recursive
            )
        print('MONITOR:  Observer scheduled for all watch dirs', flush=True)

        print('MONITOR:  Starting observer thread...', flush=True)
        self.observer.start()
        print('MONITOR:  Observer thread started', flush=True)
        logger.info(f'Observer started watching directories: {self.watch_dirs}')

    def _on_config_reload(self, config: object = None) -> None:  # noqa: ARG002
        """
        Handle configuration reload for PDF monitor.

        Updates:
        - Watch directories if changed (requires restart)
        - Processing settings
        - Polling interval
        """
        try:
            logger.info('Reloading PDF monitor configuration...')

            # Get new watch directory from config
            new_pdf_dir = self.config.pdf_dir

            # Check if directory changed
            if self._current_watch_dir != new_pdf_dir:
                logger.info(
                    f'PDF directory changed: {self._current_watch_dir} → {new_pdf_dir}'
                )
                logger.warning('PDF directory change requires monitor restart')

                # Stop current observer if running
                if self.observer is not None and self.is_running:
                    logger.info('Stopping current observer...')
                    self.observer.stop()
                    self.observer.join(timeout=5)

                # Update directory
                self._current_watch_dir = new_pdf_dir
                self.watch_dir = new_pdf_dir

                # Ensure new directory exists
                self.watch_dir.mkdir(parents=True, exist_ok=True)

                # Restart observer with new directory if monitor was running
                if self.is_running:
                    logger.info('Restarting observer with new directory...')
                    # Create new observer instance
                    self.observer = PollingObserver(timeout=self.polling_interval)
                    self._start_observer()

                logger.success(f'PDF monitor now watching {new_pdf_dir}')
            else:
                logger.debug('Watch directory unchanged')

            # Update processing settings if available
            if hasattr(self.config, 'servers_config') and hasattr(
                self.config.servers_config, 'monitor'
            ):
                monitor_config = self.config.servers_config.monitor
                if hasattr(monitor_config, 'watch_interval'):
                    logger.info(f'Watch interval: {monitor_config.watch_interval}s')
                if hasattr(monitor_config, 'bulk_process_size'):
                    logger.info(
                        f'Bulk process size: {monitor_config.bulk_process_size}'
                    )

            logger.success('PDF monitor config reloaded')

        except Exception as e:
            logger.error(f'PDF monitor config reload failed: {e}')
            logger.warning('Continuing with current watch directory')

    def get_status(self) -> dict:
        """Get monitor status including watch directory."""
        return {
            'is_running': self.is_running,
            'watch_directory': str(self._current_watch_dir)
            if self._current_watch_dir
            else None,
            'files_processed': self.files_processed,
            'last_check': self.last_check.isoformat() if self.last_check else None,
        }


# Example usage
if __name__ == '__main__':
    # Set up and start the monitor
    monitor = PDFMonitor()

    try:
        monitor.start()
    except KeyboardInterrupt:
        logger.info('Monitoring stopped by user')
