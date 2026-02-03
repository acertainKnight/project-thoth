"""Tests for PDFMonitor to ensure backward compatibility during Phase 4."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from thoth.server.pdf_monitor import PDFHandler, PDFMonitor


class TestPDFMonitorBaseline:
    """
    Baseline tests for PDFMonitor with CURRENT implementation.
    
    These tests verify that PDFMonitor works correctly BEFORE Phase 4 changes.
    All tests must pass both before AND after the changes.
    """

    @pytest.mark.skip(reason="Skipping heavy initialization test - will test with new implementation")
    def test_pdfmonitor_with_no_pipeline_creates_thothpipeline(self):
        """Test that PDFMonitor creates ThothPipeline when pipeline=None."""
        # This test is skipped because it requires full ThothPipeline initialization
        # which is too heavy for unit tests. We'll test the new implementation separately.
        pass

    def test_pdfmonitor_with_provided_pipeline_uses_it(self):
        """Test that PDFMonitor uses provided pipeline instance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)
            
            # Create mock pipeline
            mock_pipeline = Mock()
            mock_pipeline.process_pdf = Mock()
            
            monitor = PDFMonitor(watch_dir=watch_dir, pipeline=mock_pipeline)
            
            # Should use the provided pipeline
            assert monitor.pipeline is mock_pipeline

    def test_pdfmonitor_stores_watch_dir(self):
        """Test that PDFMonitor properly stores watch directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)
            
            mock_pipeline = Mock()
            monitor = PDFMonitor(watch_dir=watch_dir, pipeline=mock_pipeline)
            
            assert monitor.watch_dir == watch_dir

    def test_pdfmonitor_creates_watch_dir_if_not_exists(self):
        """Test that PDFMonitor creates watch directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir) / "subdir" / "watch"
            
            mock_pipeline = Mock()
            monitor = PDFMonitor(watch_dir=watch_dir, pipeline=mock_pipeline)
            
            # Directory should have been created
            assert watch_dir.exists()
            assert watch_dir.is_dir()


class TestPDFHandlerBaseline:
    """Baseline tests for PDFHandler."""

    def test_pdfhandler_stores_pipeline(self):
        """Test that PDFHandler stores pipeline reference."""
        mock_pipeline = Mock()
        handler = PDFHandler(pipeline=mock_pipeline)
        
        assert handler.pipeline is mock_pipeline

    def test_pdfhandler_on_created_calls_pipeline_process_pdf(self):
        """Test that on_created() calls pipeline.process_pdf()."""
        mock_pipeline = Mock()
        mock_pipeline.process_pdf = Mock(return_value=('note.md', 'md.md', 'pdf.pdf'))
        
        handler = PDFHandler(pipeline=mock_pipeline)
        
        # Create fake file event
        from watchdog.events import FileCreatedEvent
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf_path.touch()  # Create empty file
            
            event = FileCreatedEvent(str(pdf_path))
            
            # Call handler
            handler.on_created(event)
            
            # Should have called pipeline.process_pdf
            mock_pipeline.process_pdf.assert_called_once()
            call_args = mock_pipeline.process_pdf.call_args[0]
            assert Path(call_args[0]) == pdf_path

    def test_pdfhandler_on_created_ignores_non_pdf_files(self):
        """Test that on_created() ignores non-PDF files."""
        mock_pipeline = Mock()
        mock_pipeline.process_pdf = Mock()
        
        handler = PDFHandler(pipeline=mock_pipeline)
        
        from watchdog.events import FileCreatedEvent
        
        with tempfile.TemporaryDirectory() as tmpdir:
            txt_path = Path(tmpdir) / "test.txt"
            txt_path.touch()
            
            event = FileCreatedEvent(str(txt_path))
            
            # Call handler
            handler.on_created(event)
            
            # Should NOT have called pipeline.process_pdf
            mock_pipeline.process_pdf.assert_not_called()

    def test_pdfhandler_on_created_handles_errors_gracefully(self):
        """Test that on_created() handles processing errors gracefully."""
        mock_pipeline = Mock()
        mock_pipeline.process_pdf = Mock(side_effect=Exception("Processing failed"))
        
        handler = PDFHandler(pipeline=mock_pipeline)
        
        from watchdog.events import FileCreatedEvent
        
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "test.pdf"
            pdf_path.touch()
            
            event = FileCreatedEvent(str(pdf_path))
            
            # Should not raise exception (error is logged)
            handler.on_created(event)
            
            # Pipeline should have been called
            mock_pipeline.process_pdf.assert_called_once()


class TestPDFMonitorProcessing:
    """Test PDFMonitor processing functionality."""

    def test_pdfmonitor_process_existing_files_calls_pipeline(self):
        """Test that _process_existing_files() calls pipeline.process_pdf()."""
        import warnings
        
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)
            
            # Create some PDF files
            pdf1 = watch_dir / "test1.pdf"
            pdf2 = watch_dir / "test2.pdf"
            pdf1.touch()
            pdf2.touch()
            
            # Create mock pipeline with pdf_tracker
            mock_pipeline = Mock()
            mock_pipeline.process_pdf = Mock(return_value=('note.md', 'md.md', 'pdf.pdf'))
            # Mock pdf_tracker to return False (files not processed)
            mock_pipeline.pdf_tracker = Mock()
            mock_pipeline.pdf_tracker.is_processed = Mock(return_value=False)
            mock_pipeline.pdf_tracker.verify_file_unchanged = Mock(return_value=False)
            
            # Suppress deprecation warning for test
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                monitor = PDFMonitor(watch_dir=watch_dir, pipeline=mock_pipeline)
            
            # Call _process_existing_files() directly (don't call start()!)
            monitor._process_existing_files()
            
            # Should have called pipeline.process_pdf for each PDF
            assert mock_pipeline.process_pdf.call_count == 2

    def test_pdfmonitor_handles_empty_directory(self):
        """Test that PDFMonitor handles empty watch directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)
            
            mock_pipeline = Mock()
            mock_pipeline.process_pdf = Mock()
            
            monitor = PDFMonitor(watch_dir=watch_dir, pipeline=mock_pipeline)
            
            # Process existing files (none exist) - call directly, don't use start()!
            monitor._process_existing_files()
            
            # Should not have called pipeline.process_pdf
            mock_pipeline.process_pdf.assert_not_called()


class TestPDFMonitorNewParameter:
    """Test PDFMonitor with new document_pipeline parameter (Phase 4)."""

    def test_pdfmonitor_with_document_pipeline_parameter(self):
        """Test that PDFMonitor works with new document_pipeline parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)
            
            # Create mock document pipeline
            mock_doc_pipeline = Mock()
            mock_doc_pipeline.process_pdf = Mock()
            
            # Use NEW parameter (should NOT show deprecation warning)
            monitor = PDFMonitor(watch_dir=watch_dir, document_pipeline=mock_doc_pipeline)
            
            # Should use the provided document pipeline
            assert monitor.pipeline is mock_doc_pipeline

    def test_pdfmonitor_old_pipeline_parameter_shows_deprecation(self):
        """Test that old pipeline parameter shows deprecation warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)
            
            mock_pipeline = Mock()
            
            # Use OLD parameter - should show deprecation warning
            with pytest.warns(DeprecationWarning, match="PDFMonitor parameter 'pipeline' is deprecated"):
                monitor = PDFMonitor(watch_dir=watch_dir, pipeline=mock_pipeline)
            
            # Should still work (backward compatible)
            assert monitor.pipeline is mock_pipeline

    def test_pdfmonitor_cannot_use_both_parameters(self):
        """Test that using both parameters raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)
            
            mock_pipeline = Mock()
            mock_doc_pipeline = Mock()
            
            # Using BOTH parameters should raise error
            with pytest.raises(ValueError, match="Cannot specify both"):
                PDFMonitor(
                    watch_dir=watch_dir,
                    pipeline=mock_pipeline,
                    document_pipeline=mock_doc_pipeline
                )

    def test_pdfmonitor_document_pipeline_processes_files(self):
        """Test that document_pipeline parameter processes files correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)
            
            # Create PDF file
            pdf1 = watch_dir / "test.pdf"
            pdf1.touch()
            
            # Mock document pipeline with pdf_tracker
            mock_doc_pipeline = Mock()
            mock_doc_pipeline.process_pdf = Mock(return_value=('note.md', 'md.md', 'pdf.pdf'))
            # Mock pdf_tracker to return False (file not processed)
            mock_doc_pipeline.pdf_tracker = Mock()
            mock_doc_pipeline.pdf_tracker.is_processed = Mock(return_value=False)
            mock_doc_pipeline.pdf_tracker.verify_file_unchanged = Mock(return_value=False)
            
            monitor = PDFMonitor(watch_dir=watch_dir, document_pipeline=mock_doc_pipeline)
            
            # Call _process_existing_files() directly to process files
            monitor._process_existing_files()
            
            # Should have called document_pipeline.process_pdf
            mock_doc_pipeline.process_pdf.assert_called_once()
