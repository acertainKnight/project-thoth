"""
PDF Monitor for Thoth.

This module provides functionality to monitor a directory for new PDF files
and process them through the Thoth pipeline automatically.
"""

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from loguru import logger
from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from thoth.utilities.config import get_config

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
        self.config = get_config()
        self.track_file = (
            track_file or Path(self.config.output_dir) / 'processed_pdfs.json'
        )

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
        Load the list of tracked files from disk.
        """
        if self.track_file.exists():
            try:
                with open(self.track_file) as f:
                    self.processed_files = json.load(f)
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

    def _save_tracked_files(self):
        """
        Save the list of tracked files to disk.
        """
        try:
            # Use atomic write pattern to avoid corruption
            temp_file = self.track_file.with_suffix('.json.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.processed_files, f, indent=2)

            # Atomic replace
            import os

            if os.name == 'nt':  # Windows
                # Windows doesn't support atomic renames to existing files
                if self.track_file.exists():
                    self.track_file.unlink()
                os.rename(temp_file, self.track_file)
            else:  # POSIX
                os.rename(temp_file, self.track_file)

            logger.debug(
                f'Saved {len(self.processed_files)} tracked files to {self.track_file}'
            )
        except Exception as e:
            logger.error(f'Error saving tracked files: {e}')

    def is_processed(self, file_path: Path) -> bool:
        """
        Check if a file has been processed.

        Args:
            file_path: Path to the file to check.

        Returns:
            bool: True if the file has been processed, False otherwise.
        """
        # Use canonical absolute path for consistency
        abs_path = str(file_path.resolve())

        # Check if the file is in the tracked list
        return abs_path in self.processed_files

    def get_note_path(self, file_path: Path) -> Path | None:
        """
        Get the note path for a processed file.
        Args:
            file_path: Path to the file.
        Returns:
            Path | None: The path to the note, or None if not found.
        """
        abs_path = str(file_path.resolve())
        if abs_path in self.processed_files:
            note_path_str = self.processed_files[abs_path].get('note_path')
            if note_path_str:
                return Path(note_path_str)
        return None

    def mark_processed(self, file_path: Path, metadata: dict | None = None):
        """
        Mark a file as processed.

        Args:
            file_path: Path to the original file to mark as processed.
            metadata: Optional metadata to store with the file. Should include
                'new_pdf_path' if renamed.
        """
        # Use canonical absolute path of the original file for the key
        original_abs_path = str(file_path.resolve())

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
            # Merge all provided metadata
            processed_data.update(metadata)

        # Store file with metadata, using original path as the key
        self.processed_files[original_abs_path] = processed_data

        # Save the updated tracking information
        self._save_tracked_files()

        logger.debug(f'Marked original file path as processed: {file_path}')

    def verify_file_unchanged(self, file_path: Path) -> bool:
        """
        Verify that a file hasn't changed since it was processed.

        Args:
            file_path: Path to the file to check.

        Returns:
            bool: True if the file is unchanged, False otherwise.
        """
        # Use canonical absolute path for consistency
        abs_path = str(file_path.resolve())

        # If file isn't tracked, it's considered changed
        if abs_path not in self.processed_files:
            return False

        # Get current file stats
        try:
            stats = file_path.stat()
            tracked_info = self.processed_files[abs_path]

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
        """
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
            # The pipeline now handles tracking and reprocessing checks
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
        polling_interval: float = 1.0,
        recursive: bool = False,
    ):
        """
        Initialize the PDF monitor.

        Args:
            watch_dir: Directory to watch for PDF files. If None, loaded from config.
            pipeline: ThothPipeline instance. If None, a new instance is created.
            polling_interval: Interval in seconds for polling the directory.
            recursive: Whether to watch subdirectories recursively.
        """
        self.config = get_config()
        self.watch_dir = watch_dir or self.config.pdf_dir

        # Ensure the watch directory exists
        self.watch_dir.mkdir(parents=True, exist_ok=True)

        # Initialize pipeline if not provided
        if pipeline is None:
            from thoth.pipeline import ThothPipeline

            self.pipeline = ThothPipeline()
        else:
            self.pipeline = pipeline

        # Set up the observer
        self.observer = PollingObserver(timeout=polling_interval)
        self.polling_interval = polling_interval
        self.recursive = recursive

        logger.info(
            f'PDF monitor initialized to watch: {self.watch_dir} (recursive: {self.recursive})'
        )

    def start(self):
        """
        Start monitoring the directory.

        This method initiates the file system monitor and begins watching
        for new PDF files.
        """
        # Process existing files first
        self._process_existing_files()

        # Set up and start the observer
        event_handler = PDFHandler(self.pipeline)
        self.observer.schedule(
            event_handler, str(self.watch_dir), recursive=self.recursive
        )
        self.observer.start()

        logger.info(f'Started monitoring {self.watch_dir} for new PDF files')

        try:
            while True:
                time.sleep(self.polling_interval)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """
        Stop monitoring the directory.
        """
        logger.info('Attempting to stop PDF monitoring...')
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
        logger.info(f'Checking for existing PDF files in {self.watch_dir}')

        # Use recursive glob if recursive flag is set
        glob_pattern = '**/*.pdf' if self.recursive else '*.pdf'

        for pdf_file in self.watch_dir.glob(glob_pattern):
            if self.recursive:
                # Only process files when recursive is True
                if not pdf_file.is_file():
                    continue

            logger.info(f'Processing existing PDF: {pdf_file}')

            try:
                # The pipeline now handles tracking and reprocessing checks
                self.pipeline.process_pdf(pdf_file)
            except Exception as e:
                logger.error(f'Error processing existing file {pdf_file}: {e!s}')


# Example usage
if __name__ == '__main__':
    # Set up and start the monitor
    monitor = PDFMonitor()

    try:
        monitor.start()
    except KeyboardInterrupt:
        logger.info('Monitoring stopped by user')
