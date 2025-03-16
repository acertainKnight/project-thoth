"""
Tests for the PDF Monitor.
"""

import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from watchdog.events import FileCreatedEvent

from thoth.core.pdf_monitor import PDFMonitor


class TestPDFMonitor(unittest.TestCase):
    """Tests for the PDF Monitor."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path("tests/fixtures/pdf_monitor")
        os.makedirs(self.test_dir, exist_ok=True)
        self.callback = MagicMock()
        self.pdf_monitor = PDFMonitor(self.test_dir)
        self.pdf_monitor.on_new_pdf(self.callback)

        # Reference to the standard test PDF
        self.test_pdf_path = Path("tests/fixtures/test.pdf")

        # Ensure the test PDF file exists
        if not self.test_pdf_path.exists():
            self.test_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.test_pdf_path, "wb") as f:
                f.write(b"%PDF-1.5\n%Test PDF file for OCR Manager tests")

    def tearDown(self):
        """Clean up after tests."""
        # Stop the monitor if it's running
        if hasattr(self, "pdf_monitor") and self.pdf_monitor._observer.is_alive():
            self.pdf_monitor.stop()

        # Remove test files
        for file in self.test_dir.glob("*.pdf"):
            file.unlink(missing_ok=True)

        for file in self.test_dir.glob("*.txt"):
            file.unlink(missing_ok=True)

    @patch("thoth.core.pdf_monitor.Observer")
    def test_start_and_stop(self, mock_observer):
        """Test starting and stopping the monitor."""
        # Mock the observer
        mock_observer_instance = MagicMock()
        mock_observer.return_value = mock_observer_instance

        # Create a new monitor with the mocked observer
        monitor = PDFMonitor(self.test_dir)

        # Start the monitor
        monitor.start()

        # Check that the observer was started
        mock_observer_instance.start.assert_called_once()

        # Stop the monitor
        monitor.stop()

        # Check that the observer was stopped
        mock_observer_instance.stop.assert_called_once()
        mock_observer_instance.join.assert_called_once()

    def test_on_created(self):
        """Test the on_created method."""
        # Create a PDF file event using the test.pdf name
        pdf_path = self.test_dir / "test.pdf"
        event = FileCreatedEvent(str(pdf_path))

        # Call the on_created method
        self.pdf_monitor.on_created(event)

        # Check that the callback was not called because file doesn't exist
        self.callback.assert_not_called()

        # Copy the test PDF file to the test directory
        shutil.copy(self.test_pdf_path, pdf_path)

        # Call the on_created method again
        self.pdf_monitor.on_created(event)

        # Now the callback should be called
        self.callback.assert_called_once_with(pdf_path)

    def test_on_created_non_pdf(self):
        """Test the on_created method with a non-PDF file."""
        # Create a non-PDF file event
        txt_path = self.test_dir / "test.txt"
        txt_path.touch()
        event = FileCreatedEvent(str(txt_path))

        # Call the on_created method
        self.pdf_monitor.on_created(event)

        # Check that the callback was not called
        self.callback.assert_not_called()

    @patch("thoth.core.pdf_monitor.Observer")
    def test_process_existing_pdfs(self, mock_observer):  # noqa: ARG002
        """Test processing existing PDFs."""
        # Copy the test PDF file to the test directory with different names
        pdf_path1 = self.test_dir / "test1.pdf"
        pdf_path2 = self.test_dir / "test2.pdf"
        shutil.copy(self.test_pdf_path, pdf_path1)
        shutil.copy(self.test_pdf_path, pdf_path2)

        # Create a new monitor with the mocked observer
        monitor = PDFMonitor(self.test_dir)
        monitor.on_new_pdf(self.callback)

        # Process existing PDFs
        monitor.process_existing_pdfs()

        # Check that the callback was called for each PDF
        self.assertEqual(self.callback.call_count, 2)
        self.callback.assert_any_call(pdf_path1)
        self.callback.assert_any_call(pdf_path2)

    def test_process_url_list(self):
        """Test processing a list of URLs."""
        # Create a URL list file
        url_file = self.test_dir / "urls.txt"
        with open(url_file, "w") as f:
            f.write("https://example.com/paper1.pdf\n")
            f.write("https://example.com/paper2.pdf\n")

        # Mock the download_pdf function
        with patch("thoth.core.pdf_monitor.download_pdf") as mock_download:
            mock_download.side_effect = [
                self.test_dir / "paper1.pdf",
                self.test_dir / "paper2.pdf",
            ]

            # Process the URL list
            result = self.pdf_monitor.process_url_list(url_file, chunk_size=1)

            # Check that download_pdf was called for each URL
            self.assertEqual(mock_download.call_count, 2)
            mock_download.assert_any_call(
                "https://example.com/paper1.pdf", self.test_dir
            )
            mock_download.assert_any_call(
                "https://example.com/paper2.pdf", self.test_dir
            )

            # Check the result
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0], self.test_dir / "paper1.pdf")
            self.assertEqual(result[1], self.test_dir / "paper2.pdf")
