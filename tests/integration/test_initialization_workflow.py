"""Integration tests for initialize_thoth() workflow (Phase 4)."""

import tempfile
import warnings
from pathlib import Path
from unittest.mock import Mock

import pytest

from thoth.initialization import initialize_thoth
from thoth.knowledge.graph import CitationGraph
from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
from thoth.server.pdf_monitor import PDFMonitor
from thoth.services.service_manager import ServiceManager


class TestInitializationWorkflow:
    """Test the complete initialization workflow."""

    def test_initialize_thoth_creates_all_components(self):
        """Test that initialize_thoth() creates all required components."""
        services, pipeline, graph = initialize_thoth()

        # Verify types
        assert isinstance(services, ServiceManager)
        assert isinstance(pipeline, OptimizedDocumentPipeline)
        assert isinstance(graph, CitationGraph)

        # Verify services are initialized
        assert services._initialized is True

        # Verify pipeline has services
        assert pipeline.services is services

        # Verify graph has service manager
        assert graph.service_manager is services

        # Verify citation tracker is set in services
        assert services.citation._citation_tracker is graph

    def test_initialize_thoth_can_be_called_multiple_times(self):
        """Test that initialize_thoth() can be called multiple times safely."""
        # First call
        services1, pipeline1, graph1 = initialize_thoth()

        # Second call - should create new instances
        services2, pipeline2, graph2 = initialize_thoth()

        # Should be different instances
        assert services1 is not services2
        assert pipeline1 is not pipeline2
        assert graph1 is not graph2


class TestPDFMonitorIntegration:
    """Test PDFMonitor integration with new initialization."""

    def test_pdfmonitor_with_new_initialization_pattern(self):
        """Test PDFMonitor works with initialize_thoth() pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)

            # Initialize using new pattern
            _, document_pipeline, _ = initialize_thoth()

            # Create PDFMonitor with new parameter (no deprecation warning)
            monitor = PDFMonitor(
                watch_dir=watch_dir, document_pipeline=document_pipeline
            )

            # Verify it has the pipeline
            assert monitor.pipeline is document_pipeline
            assert hasattr(monitor.pipeline, 'process_pdf')

    def test_pdfmonitor_backward_compatibility_with_thothpipeline(self):
        """Test that PDFMonitor still works with ThothPipeline (deprecated)."""
        from thoth.pipeline import ThothPipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)

            # Create ThothPipeline (old way)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                thoth_pipeline = ThothPipeline()

            # Create PDFMonitor with old parameter (should show deprecation warning)
            with pytest.warns(DeprecationWarning, match='pipeline.*deprecated'):
                monitor = PDFMonitor(watch_dir=watch_dir, pipeline=thoth_pipeline)

            # Should extract document_pipeline from ThothPipeline
            assert monitor.pipeline is thoth_pipeline.document_pipeline

    def test_pdfmonitor_processes_files_with_new_pipeline(self):
        """Test that PDFMonitor processes files correctly with new pipeline."""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)

            # Create PDF files
            pdf1 = watch_dir / 'test1.pdf'
            pdf2 = watch_dir / 'test2.pdf'
            pdf1.touch()
            pdf2.touch()

            # Mock document pipeline
            mock_pipeline = Mock()
            mock_pipeline.process_pdf = Mock(
                return_value=('note.md', 'md.md', 'pdf.pdf')
            )

            # Create monitor with new parameter
            monitor = PDFMonitor(watch_dir=watch_dir, document_pipeline=mock_pipeline)

            # Process existing files
            monitor._process_existing_files()

            # Should have processed both files
            assert mock_pipeline.process_pdf.call_count == 2


class TestBackwardCompatibility:
    """Test that old code patterns still work."""

    def test_thothpipeline_still_works_for_pdf_processing(self):
        """Test that ThothPipeline still works for PDF processing."""
        from thoth.pipeline import ThothPipeline

        # Suppress deprecation warnings for backward compatibility test
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            pipeline = ThothPipeline()

        # Should have all expected attributes
        assert hasattr(pipeline, 'services')
        assert hasattr(pipeline, 'document_pipeline')
        assert hasattr(pipeline, 'citation_tracker')
        assert hasattr(pipeline, 'process_pdf')

        # Services should be initialized
        assert isinstance(pipeline.services, ServiceManager)
        assert pipeline.services._initialized is True

    def test_old_pdfmonitor_initialization_still_works(self):
        """Test old PDFMonitor(pipeline=...) pattern still works."""
        from thoth.pipeline import ThothPipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)

            # OLD PATTERN - should still work
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                pipeline = ThothPipeline()
                monitor = PDFMonitor(watch_dir=watch_dir, pipeline=pipeline)

            # Should work correctly
            assert monitor.pipeline is not None
            assert hasattr(monitor.pipeline, 'process_pdf')


class TestNewVsOldPatternEquivalence:
    """Test that new and old patterns produce equivalent results."""

    def test_initialize_thoth_vs_thothpipeline_equivalence(self):
        """Test that initialize_thoth() produces same result as ThothPipeline."""
        from thoth.pipeline import ThothPipeline

        # New pattern
        services_new, pipeline_new, graph_new = initialize_thoth()

        # Old pattern
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            thoth_pipeline = ThothPipeline()

        # Should have same component types
        assert type(services_new) == type(thoth_pipeline.services)
        assert type(pipeline_new) == type(thoth_pipeline.document_pipeline)
        assert type(graph_new) == type(thoth_pipeline.citation_tracker)

        # Both should be functional
        assert services_new._initialized is True
        assert thoth_pipeline.services._initialized is True

    def test_pdfmonitor_works_same_with_both_patterns(self):
        """Test that PDFMonitor works identically with both patterns."""

        with tempfile.TemporaryDirectory() as tmpdir:
            watch_dir = Path(tmpdir)

            # Create test file
            pdf_file = watch_dir / 'test.pdf'
            pdf_file.touch()

            # Test NEW pattern
            _, document_pipeline_new, _ = initialize_thoth()
            mock_new = Mock()
            mock_new.process_pdf = Mock(return_value=('a', 'b', 'c'))
            mock_new.__class__.__name__ = 'Mock'  # Prevent extraction logic

            monitor_new = PDFMonitor(watch_dir=watch_dir, document_pipeline=mock_new)
            monitor_new._process_existing_files()

            # Test OLD pattern
            mock_old = Mock()
            mock_old.process_pdf = Mock(return_value=('a', 'b', 'c'))
            mock_old.__class__.__name__ = 'Mock'

            with warnings.catch_warnings():
                warnings.simplefilter('ignore', DeprecationWarning)
                monitor_old = PDFMonitor(watch_dir=watch_dir, pipeline=mock_old)
            monitor_old._process_existing_files()

            # Both should have processed the file
            assert mock_new.process_pdf.call_count == 1
            assert mock_old.process_pdf.call_count == 1
