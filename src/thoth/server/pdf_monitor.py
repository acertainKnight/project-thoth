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
    from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
    from thoth.pipeline import ThothPipeline

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

        # Create the file if it doesn't exist
        if not self.track_file.exists():
            self._save_tracked_files()

        logger.info(f'PDF tracker initialized with tracking file: {self.track_file}')

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
        """Load processed PDFs tracking from PostgreSQL."""
        import asyncpg  # noqa: I001
        import asyncio

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def load():
            conn = await asyncpg.connect(db_url)
            try:
                rows = await conn.fetch(
                    'SELECT pdf_path, new_pdf_path, note_path, file_size, file_mtime FROM processed_pdfs'
                )
                for row in rows:
                    # Stored paths are already relative (e.g., "thoth/papers/pdfs/file.pdf")  # noqa: W505
                    pdf_path_key = row['pdf_path']

                    # Build tracked file info with database values
                    tracked_info = {
                        'new_pdf_path': row['new_pdf_path'],
                        'note_path': row['note_path'],
                    }

                    # Add size and mtime from database if available
                    if row['file_size'] is not None:
                        tracked_info['size'] = row['file_size']
                    if row['file_mtime'] is not None:
                        tracked_info['mtime'] = row['file_mtime']

                    self.processed_files[str(pdf_path_key)] = tracked_info

                logger.info(f'Loaded {len(rows)} processed PDFs from PostgreSQL')
            finally:
                await conn.close()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(load())
            loop.close()
        else:
            # Already have a running loop
            asyncio.create_task(load())

    def _save_tracked_files(self):
        """
        Save the list of tracked files to PostgreSQL.
        """
        try:
            self._save_to_postgres()
        except Exception as e:
            logger.error(f'Error saving tracked files: {e}')

    def _save_to_postgres(self) -> None:
        """Save processed PDFs tracking to PostgreSQL."""
        import asyncpg  # noqa: I001
        import asyncio

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def save():
            conn = await asyncpg.connect(db_url)
            try:
                for pdf_path_key, metadata in self.processed_files.items():
                    # Ensure we're storing vault-relative paths
                    pdf_path = pdf_path_key
                    if self.vault_resolver and Path(pdf_path_key).is_absolute():
                        try:
                            pdf_path = self.vault_resolver.make_relative(
                                Path(pdf_path_key)
                            )
                        except (ValueError, Exception):
                            # If can't normalize, store as-is
                            pass
                    await conn.execute(
                        """
                        INSERT INTO processed_pdfs (pdf_path, new_pdf_path, note_path, file_size, file_mtime, processed_at)
                        VALUES ($1, $2, $3, $4, $5, NOW())
                        ON CONFLICT (pdf_path) DO UPDATE SET
                            new_pdf_path = EXCLUDED.new_pdf_path,
                            note_path = EXCLUDED.note_path,
                            file_size = EXCLUDED.file_size,
                            file_mtime = EXCLUDED.file_mtime
                    """,
                        str(pdf_path),
                        metadata.get('new_pdf_path'),
                        metadata.get('note_path'),
                        metadata.get('size'),
                        metadata.get('mtime'),
                    )
                logger.info(
                    f'Saved {len(self.processed_files)} processed PDFs to PostgreSQL'
                )
            finally:
                await conn.close()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(save())
            loop.close()
        else:
            # Already have a running loop
            asyncio.create_task(save())

    def is_processed(self, file_path: Path) -> bool:
        """
        Check if a file has been processed.

        Args:
            file_path: Path to the file to check.

        Returns:
            bool: True if the file has been processed, False otherwise.
        """
        # Normalize to vault-relative if resolver is available
        if self.vault_resolver:
            resolved = file_path.resolve()
            try:
                relative_path = self.vault_resolver.make_relative(resolved)
                is_in_cache = relative_path in self.processed_files
                logger.debug(
                    f'Checking processed: {file_path} -> {relative_path} -> {is_in_cache}'
                )
                if not is_in_cache:
                    # Log sample of keys for debugging
                    sample_keys = list(self.processed_files.keys())[:3]
                    logger.debug(f'Sample cache keys: {sample_keys}')
                return is_in_cache
            except ValueError as e:
                logger.debug(f'Could not normalize path {file_path}: {e}')
                pass

        # Fallback to absolute path
        abs_path = str(file_path.resolve())
        return abs_path in self.processed_files

    def get_note_path(self, file_path: Path) -> Path | None:
        """
        Get the note path for a processed file.
        Handles both absolute and relative paths in tracker.

        Args:
            file_path: Path to the file.
        Returns:
            Path | None: The path to the note, or None if not found.
        """
        # Try vault-relative lookup first
        if self.vault_resolver:
            resolved = file_path.resolve()
            if self.vault_resolver.is_vault_relative(resolved):
                try:
                    relative_path = self.vault_resolver.make_relative(resolved)
                    if relative_path in self.processed_files:
                        note_path_str = self.processed_files[relative_path].get(
                            'note_path'
                        )
                        if note_path_str:
                            # If note path is relative, resolve it to absolute
                            note_path = Path(note_path_str)
                            if not note_path.is_absolute():
                                return self.vault_resolver.resolve(note_path_str)
                            return note_path
                except ValueError:
                    pass

        # Fallback to absolute path lookup
        abs_path = str(file_path.resolve())
        if abs_path in self.processed_files:
            note_path_str = self.processed_files[abs_path].get('note_path')
            if note_path_str:
                note_path = Path(note_path_str)
                # If note path is relative, resolve it to absolute
                if not note_path.is_absolute() and self.vault_resolver:
                    return self.vault_resolver.resolve(note_path_str)
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
        # Determine the key to use - prefer vault-relative
        resolved_path = file_path.resolve()
        if self.vault_resolver:
            try:
                storage_key = self.vault_resolver.make_relative(resolved_path)
                logger.debug(f'Storing with vault-relative key: {storage_key}')
            except ValueError:
                storage_key = str(resolved_path)
                logger.debug(f'Storing with absolute key: {storage_key}')
        else:
            storage_key = str(resolved_path)
            logger.debug(f'Storing with absolute key: {storage_key}')

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

            # Convert new_pdf_path to vault-relative
            if 'new_pdf_path' in processed_data and self.vault_resolver:
                pdf_path = Path(processed_data['new_pdf_path']).resolve()
                try:
                    processed_data['new_pdf_path'] = self.vault_resolver.make_relative(
                        pdf_path
                    )
                except ValueError:
                    pass  # Keep absolute if conversion fails

            # Convert note_path to vault-relative
            if 'note_path' in processed_data:
                note_path = Path(processed_data['note_path']).resolve()
                if self.vault_resolver and self.vault_resolver.is_vault_relative(
                    note_path
                ):
                    try:
                        processed_data['note_path'] = self.vault_resolver.make_relative(
                            note_path
                        )
                    except ValueError:
                        pass  # Keep absolute if conversion fails

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
        # Try vault-relative lookup first
        lookup_key = None
        if self.vault_resolver:
            resolved = file_path.resolve()
            if self.vault_resolver.is_vault_relative(resolved):
                try:
                    lookup_key = self.vault_resolver.make_relative(resolved)
                except ValueError:
                    pass

        # Fallback to absolute path
        if lookup_key is None:
            lookup_key = str(file_path.resolve())

        # If file isn't tracked, it's considered changed
        if lookup_key not in self.processed_files:
            return False

        # Get current file stats
        try:
            stats = file_path.stat()
            tracked_info = self.processed_files[lookup_key]

            # Handle migration case: if size/mtime not in tracker, backfill from filesystem
            if 'size' not in tracked_info or 'mtime' not in tracked_info:
                logger.debug(
                    f'Backfilling size/mtime for {lookup_key} from filesystem'
                )
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
            pipeline: The Thoth pipeline instance to process PDFs.
                     Can be either ThothPipeline (deprecated) or OptimizedDocumentPipeline.
        """
        # Store the pipeline - could be ThothPipeline or OptimizedDocumentPipeline
        self.pipeline = pipeline

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
            self.pipeline.process_pdf(file_path)
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
            document_pipeline: OptimizedDocumentPipeline instance. If None, one is created.
            polling_interval: Interval in seconds for polling the directory.
            recursive: Whether to watch subdirectories recursively.
        """
        import warnings
        
        self.config = config
        self.watch_dir = watch_dir or self.config.pdf_dir

        # Ensure the watch directory exists
        self.watch_dir.mkdir(parents=True, exist_ok=True)

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
                "    from thoth.initialization import initialize_thoth\n"
                "    _, document_pipeline, _ = initialize_thoth()\n"
                "    monitor = PDFMonitor(document_pipeline=document_pipeline)\n",
                DeprecationWarning,
                stacklevel=2,
            )
            # Extract the document pipeline from ThothPipeline wrapper
            # Check if it's actually a ThothPipeline by checking for the class name
            if pipeline.__class__.__name__ == 'ThothPipeline' and hasattr(pipeline, 'document_pipeline'):
                self.pipeline = pipeline.document_pipeline
            else:
                # If passed an OptimizedDocumentPipeline directly, or a mock, use it as-is
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
        logger.info('🚀 PDFMonitor.start() method called')
        logger.info(f'🔍 WATCHDOG_AVAILABLE = {WATCHDOG_AVAILABLE}')

        if not WATCHDOG_AVAILABLE:
            logger.warning('Watchdog not available, PDF monitoring disabled')
            return

        # Process existing files first
        logger.info('📋 About to call _process_existing_files()...')
        self._process_existing_files()
        logger.info('✅ _process_existing_files() completed')

        # Set up and start the observer
        self._start_observer()

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
        logger.info(f'📂 Checking for existing PDF files in {self.watch_dir}')

        # Use recursive glob if recursive flag is set
        glob_pattern = '**/*.pdf' if self.recursive else '*.pdf'

        # Count files first
        pdf_files = list(self.watch_dir.glob(glob_pattern))
        if self.recursive:
            pdf_files = [f for f in pdf_files if f.is_file()]

        logger.info(f'📊 Found {len(pdf_files)} PDF files to process')

        for i, pdf_file in enumerate(pdf_files, 1):
            logger.info(f'📄 Processing PDF {i}/{len(pdf_files)}: {pdf_file.name}')

            try:
                # The pipeline now handles tracking and reprocessing checks
                logger.info(f'▶️  Calling pipeline.process_pdf() for {pdf_file.name}...')
                self.pipeline.process_pdf(pdf_file)
                self.files_processed += 1
                logger.info(f'✅ Successfully processed {pdf_file.name}')
            except Exception as e:
                logger.error(f'❌ Error processing existing file {pdf_file}: {e!s}')
                logger.exception('Full traceback:')

        # Update last check time
        from datetime import datetime

        self.last_check = datetime.now()

    def _start_observer(self):
        """
        Start or restart the observer with current watch directory.
        """
        event_handler = PDFHandler(self.pipeline)
        self.observer.schedule(
            event_handler, str(self.watch_dir), recursive=self.recursive
        )
        self.observer.start()
        logger.info(f'Observer started watching {self.watch_dir}')

    def _on_config_reload(self):
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

                logger.success(f'✅ PDF monitor now watching {new_pdf_dir}')
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

            logger.success('✅ PDF monitor config reloaded')

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
