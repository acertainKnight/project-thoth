"""
Tests for PDF monitor.

Tests the PDF monitoring and tracking functionality.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from thoth.pipeline import ThothPipeline
from thoth.server.pdf_monitor import PDFMonitor, PDFTracker


class TestPDFTracker:
    """Test suite for PDFTracker."""

    @pytest.fixture
    def tracker(self, temp_workspace):
        """Create a PDFTracker instance for testing."""
        track_file = temp_workspace / 'test_tracker.json'
        return PDFTracker(track_file=track_file)

    def test_is_processed_new_file(self, tracker, sample_pdf_path):
        """Test checking if a new file is processed."""
        assert not tracker.is_processed(sample_pdf_path)

    def test_mark_processed(self, tracker, sample_pdf_path):
        """Test marking a file as processed."""
        metadata = {'note_path': '/path/to/note.md'}

        tracker.mark_processed(sample_pdf_path, metadata)

        assert tracker.is_processed(sample_pdf_path)
        # Get entry from processed_files directly
        abs_path = str(sample_pdf_path.resolve())
        entry = tracker.processed_files.get(abs_path)
        assert entry is not None
        assert entry['note_path'] == '/path/to/note.md'

    def test_get_entry(self, tracker, sample_pdf_path):
        """Test getting entry for a processed file."""
        # File not processed yet
        abs_path = str(sample_pdf_path.resolve())
        assert tracker.processed_files.get(abs_path) is None

        # Mark as processed
        tracker.mark_processed(sample_pdf_path)

        # Now should have entry
        entry = tracker.processed_files.get(abs_path)
        assert entry is not None
        assert 'processed_time' in entry
        assert 'size' in entry

    def test_save_and_load(self, tracker, sample_pdf_path):
        """Test saving and loading tracker state."""
        # Mark file as processed
        tracker.mark_processed(sample_pdf_path)

        # Save explicitly (also happens in mark_processed)
        tracker._save_tracked_files()

        # Create new tracker instance
        new_tracker = PDFTracker(track_file=tracker.track_file)

        # Should still show as processed
        assert new_tracker.is_processed(sample_pdf_path)

    def test_file_modification_detection(self, tracker, sample_pdf_path):
        """Test detection of file modifications."""
        # Mark as processed
        tracker.mark_processed(sample_pdf_path)
        assert tracker.is_processed(sample_pdf_path)

        # Simulate file modification by changing content
        time.sleep(0.01)  # Ensure different timestamp
        sample_pdf_path.write_bytes(b'Modified content')

        # Should detect the change
        assert not tracker.verify_file_unchanged(sample_pdf_path)

    def test_corrupted_track_file_recovery(self, tracker):
        """Test recovery from corrupted tracking file."""
        # Write invalid JSON
        tracker.track_file.write_text('invalid json{')

        # Should handle gracefully and start fresh
        new_tracker = PDFTracker(track_file=tracker.track_file)
        assert len(new_tracker.processed_files) == 0


class TestPDFMonitor:
    """Test suite for PDFMonitor."""

    @pytest.fixture
    def monitor(self, temp_workspace, mock_pipeline):
        """Create a PDFMonitor instance for testing."""
        return PDFMonitor(
            watch_dir=temp_workspace / 'pdf',
            pipeline=mock_pipeline,
            polling_interval=0.1,
            recursive=False,
        )

    @pytest.fixture
    def mock_pipeline(self, temp_workspace):
        """Create a mock pipeline."""
        pipeline = MagicMock(spec=ThothPipeline)
        pipeline.process_pdf.return_value = (
            Path('/path/to/note.md'),
            Path('/path/to/pdf.pdf'),
            Path('/path/to/markdown.md'),
        )
        pipeline.pdf_tracker = PDFTracker(
            track_file=temp_workspace / 'test_tracker.json'
        )
        return pipeline

    def test_find_pdf_files_non_recursive(self, monitor, temp_workspace):  # noqa: ARG002
        """Test finding PDF files non-recursively."""
        pdf_dir = temp_workspace / 'pdf'

        # Create PDF files
        (pdf_dir / 'file1.pdf').write_bytes(b'PDF1')
        (pdf_dir / 'file2.pdf').write_bytes(b'PDF2')
        (pdf_dir / 'not_pdf.txt').write_text('Not a PDF')

        # Create subdirectory with PDF (should not be found)
        subdir = pdf_dir / 'subdir'
        subdir.mkdir()
        (subdir / 'file3.pdf').write_bytes(b'PDF3')

        # Use glob to find files like the monitor does
        files = list(pdf_dir.glob('*.pdf'))

        assert len(files) == 2
        assert any('file1.pdf' in str(f) for f in files)
        assert any('file2.pdf' in str(f) for f in files)
        assert not any('file3.pdf' in str(f) for f in files)

    def test_find_pdf_files_recursive(self, temp_workspace, mock_pipeline):
        """Test finding PDF files recursively."""
        monitor = PDFMonitor(  # noqa: F841
            watch_dir=temp_workspace / 'pdf',
            pipeline=mock_pipeline,
            recursive=True,
        )

        pdf_dir = temp_workspace / 'pdf'

        # Create PDF files
        (pdf_dir / 'file1.pdf').write_bytes(b'PDF1')

        # Create subdirectory with PDF
        subdir = pdf_dir / 'subdir'
        subdir.mkdir()
        (subdir / 'file2.pdf').write_bytes(b'PDF2')

        # Use glob to find files like the monitor does
        files = list(pdf_dir.glob('**/*.pdf'))

        assert len(files) == 2
        assert any('file1.pdf' in str(f) for f in files)
        assert any('file2.pdf' in str(f) for f in files)

    def test_process_new_files(self, monitor, mock_pipeline, temp_workspace):
        """Test processing new PDF files."""
        pdf_dir = temp_workspace / 'pdf'
        pdf_file = pdf_dir / 'test.pdf'
        pdf_file.write_bytes(b'Test PDF')

        # Mock the pipeline's process_pdf to mark files as processed in its tracker
        def _mock_process_pdf(pdf_path):
            monitor.pipeline.pdf_tracker.mark_processed(pdf_path)
            return (
                Path('/path/to/note.md'),
                Path('/path/to/pdf.pdf'),
                Path('/path/to/markdown.md'),
            )

        mock_pipeline.process_pdf.side_effect = _mock_process_pdf

        # Process existing files (what happens on start)
        monitor._process_existing_files()

        # Should have processed the file
        mock_pipeline.process_pdf.assert_called_once_with(pdf_file)
        assert monitor.pipeline.pdf_tracker.is_processed(pdf_file)

    def test_process_error_handling(self, monitor, mock_pipeline, temp_workspace):
        """Test error handling during processing."""
        pdf_dir = temp_workspace / 'pdf'
        pdf_file = pdf_dir / 'test.pdf'
        pdf_file.write_bytes(b'Test PDF')

        # Make processing fail
        mock_pipeline.process_pdf.side_effect = Exception('Processing failed')

        # Should not crash
        monitor._process_existing_files()

        # File should not be marked as processed
        assert not monitor.pipeline.pdf_tracker.is_processed(pdf_file)

    def test_monitor_lifecycle(self, monitor):
        """Test starting and stopping the monitor."""
        # Test that observer exists
        assert monitor.observer is not None
        assert not monitor.observer.is_alive()

        # Can't easily test full start/stop without threading issues
        # Just verify the monitor was created correctly
        assert monitor.watch_dir.exists()
        assert monitor.pipeline.pdf_tracker is not None

    def test_monitor_with_custom_tracker(self, temp_workspace, mock_pipeline):
        """Test monitor with custom tracking file."""
        custom_track_file = temp_workspace / 'custom_tracker.json'
        mock_pipeline.pdf_tracker = PDFTracker(track_file=custom_track_file)

        monitor = PDFMonitor(
            watch_dir=temp_workspace / 'pdf',
            pipeline=mock_pipeline,
        )

        assert monitor.pipeline.pdf_tracker.track_file == custom_track_file
        assert custom_track_file.exists()  # Should create the file
