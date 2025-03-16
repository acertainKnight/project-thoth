"""
PDF Monitor module for Thoth.

This module provides functionality to monitor a directory for new PDF files
and process them as they are added.
"""

import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer


def download_pdf(url: str, output_dir: Path) -> Path:
    """
    Download a PDF from a URL.

    Args:
        url: The URL of the PDF to download.
        output_dir: The directory to save the PDF to.

    Returns:
        Path: The path to the downloaded PDF.
    """
    # This is a placeholder implementation
    # In a real implementation, this would download the PDF from the URL
    output_path = output_dir / url.split("/")[-1]
    output_path.touch()
    return output_path


class PDFMonitor(FileSystemEventHandler):
    """
    Monitor a directory for new PDF files and process them.

    This class uses the watchdog library to monitor a directory for new PDF files
    and calls a callback function when a new PDF is detected.
    """

    def __init__(self, pdf_dir: Path):
        """
        Initialize the PDF monitor.

        Args:
            pdf_dir: The directory to monitor for new PDF files.
        """
        self.pdf_dir = Path(pdf_dir)
        self._callbacks = []
        self._observer = Observer()
        self._observer.schedule(self, str(self.pdf_dir), recursive=False)

    def on_new_pdf(self, callback: Callable[[Path], None]) -> None:
        """
        Register a callback to be called when a new PDF is detected.

        Args:
            callback: A function that takes a Path to the new PDF file.
        """
        self._callbacks.append(callback)

    def on_created(self, event: FileCreatedEvent) -> None:
        """
        Handle file creation events.

        This method is called by the watchdog observer when a new file is created
        in the monitored directory.

        Args:
            event: The file creation event.
        """
        # Convert the path to a Path object
        path = Path(event.src_path)

        # Check if the file is a PDF
        if path.suffix.lower() == ".pdf" and path.exists():
            # Call all registered callbacks
            for callback in self._callbacks:
                callback(path)

    def start(self) -> None:
        """Start monitoring the directory."""
        self._observer.start()

    def stop(self) -> None:
        """Stop monitoring the directory."""
        self._observer.stop()
        self._observer.join()

    def process_existing_pdfs(self) -> None:
        """
        Process all existing PDFs in the monitored directory.

        This method can be called to process PDFs that already exist in the
        directory before monitoring started.
        """
        for pdf_path in self.pdf_dir.glob("*.pdf"):
            for callback in self._callbacks:
                callback(pdf_path)

    def process_url_list(self, url_file: Path, chunk_size: int = 10) -> list[Path]:
        """
        Process a list of URLs to download PDFs.

        Args:
            url_file: Path to a file containing URLs, one per line.
            chunk_size: Number of URLs to process in each chunk.

        Returns:
            List[Path]: Paths to the downloaded PDFs.
        """
        # Read the URLs from the file
        with open(url_file) as f:
            urls = [line.strip() for line in f if line.strip()]

        # Process the URLs in chunks
        results = []
        for i in range(0, len(urls), chunk_size):
            chunk = urls[i : i + chunk_size]
            for url in chunk:
                pdf_path = download_pdf(url, self.pdf_dir)
                results.append(pdf_path)
            # Sleep briefly between chunks to avoid overwhelming the system
            if i + chunk_size < len(urls):
                time.sleep(1)

        return results
