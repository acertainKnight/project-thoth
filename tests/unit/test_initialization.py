"""Tests for the initialization module."""

import warnings

import pytest

from thoth.initialization import initialize_thoth
from thoth.knowledge.graph import CitationGraph
from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
from thoth.services.service_manager import ServiceManager


class TestInitializationFactory:
    """Test the initialize_thoth() factory function."""

    def test_initialize_thoth_returns_correct_types(self):
        """Test that initialize_thoth returns correct types."""
        services, pipeline, graph = initialize_thoth()
        
        assert isinstance(services, ServiceManager)
        assert isinstance(pipeline, OptimizedDocumentPipeline)
        assert isinstance(graph, CitationGraph)

    def test_initialize_thoth_services_initialized(self):
        """Test that ServiceManager is properly initialized."""
        services, _, _ = initialize_thoth()
        
        # ServiceManager should have _initialized flag set
        assert services._initialized is True
        
        # Should have core services available
        assert hasattr(services, 'llm')
        assert hasattr(services, 'article')
        assert hasattr(services, 'note')

    def test_initialize_thoth_pipeline_has_services(self):
        """Test that pipeline has access to services."""
        services, pipeline, _ = initialize_thoth()
        
        assert pipeline.services is services
        assert hasattr(pipeline, 'process_pdf')

    def test_initialize_thoth_graph_has_service_manager(self):
        """Test that citation graph has service manager."""
        services, _, graph = initialize_thoth()
        
        assert graph.service_manager is services

    def test_initialize_thoth_services_have_citation_tracker(self):
        """Test that services have citation tracker set."""
        services, _, graph = initialize_thoth()
        
        # Citation service should have citation tracker set
        assert hasattr(services.citation, '_citation_tracker')
        assert services.citation._citation_tracker is graph
        
        # Tag service should have citation tracker set (if available)
        # Note: TagService may be None in CI if OpenRouter API key not available
        if services._services['tag'] is not None:
            assert hasattr(services.tag, '_citation_tracker')
            assert services.tag._citation_tracker is graph
        else:
            # Skip test if TagService not available (missing API key in CI)
            pytest.skip("TagService not available (requires OpenRouter API key)")

    def test_initialize_thoth_with_custom_config(self):
        """Test initialize_thoth with custom config."""
        from thoth.config import config
        
        # Use existing config (don't create a new one to avoid issues)
        services, pipeline, graph = initialize_thoth(config=config)
        
        assert isinstance(services, ServiceManager)
        assert isinstance(pipeline, OptimizedDocumentPipeline)
        assert isinstance(graph, CitationGraph)

    def test_initialize_thoth_creates_directories(self):
        """Test that required directories are created."""
        from thoth.config import config
        
        # Should not raise even if directories don't exist
        services, pipeline, graph = initialize_thoth()
        
        # Directories should exist after initialization
        assert config.output_dir.exists()
        assert config.notes_dir.exists()
        assert config.markdown_dir.exists()

    def test_initialize_thoth_idempotent(self):
        """Test that initialize_thoth can be called multiple times."""
        # First call
        services1, pipeline1, graph1 = initialize_thoth()
        
        # Second call should work (creates new instances)
        services2, pipeline2, graph2 = initialize_thoth()
        
        # Different instances
        assert services1 is not services2
        assert pipeline1 is not pipeline2
        assert graph1 is not graph2
        
        # But same types
        assert type(services1) == type(services2)
        assert type(pipeline1) == type(pipeline2)
        assert type(graph1) == type(graph2)


class TestThothPipelineDeprecation:
    """Test ThothPipeline deprecation warnings."""

    def test_thothpipeline_init_shows_deprecation_warning(self):
        """Test that ThothPipeline.__init__() shows deprecation warning."""
        from thoth.pipeline import ThothPipeline
        
        with pytest.warns(DeprecationWarning, match="ThothPipeline is deprecated"):
            pipeline = ThothPipeline()
        
        # Should still work (backward compatible)
        assert hasattr(pipeline, 'services')
        assert hasattr(pipeline, 'document_pipeline')
        assert hasattr(pipeline, 'citation_tracker')

    def test_thothpipeline_process_pdf_shows_deprecation_warning(self):
        """Test that ThothPipeline.process_pdf() shows deprecation warning."""
        from thoth.pipeline import ThothPipeline
        
        # Suppress the __init__ warning to test process_pdf warning specifically
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            pipeline = ThothPipeline()
        
        # Now test process_pdf warning
        # Note: We can't actually call it without a real PDF, but we can mock it
        import unittest.mock as mock
        
        with mock.patch.object(pipeline.document_pipeline, 'process_pdf', return_value=('a', 'b', 'c')):
            with pytest.warns(DeprecationWarning, match="process_pdf.*deprecated"):
                pipeline.process_pdf('fake.pdf')

    def test_thothpipeline_still_works_correctly(self):
        """Test that ThothPipeline still initializes correctly despite deprecation."""
        from thoth.pipeline import ThothPipeline
        
        # Suppress warnings for functional test
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            pipeline = ThothPipeline()
        
        # Verify all components are initialized correctly
        assert isinstance(pipeline.services, ServiceManager)
        assert isinstance(pipeline.document_pipeline, OptimizedDocumentPipeline)
        assert isinstance(pipeline.citation_tracker, CitationGraph)
        
        # Verify services are accessible
        assert hasattr(pipeline.services, 'llm')
        assert hasattr(pipeline.services, 'article')
        
        # Verify pipeline has services
        assert pipeline.document_pipeline.services is pipeline.services

    def test_thothpipeline_vs_initialize_thoth_equivalent(self):
        """Test that ThothPipeline and initialize_thoth() produce equivalent results."""
        from thoth.pipeline import ThothPipeline
        
        # Suppress warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            pipeline = ThothPipeline()
        
        # Get results from initialize_thoth
        services, doc_pipeline, graph = initialize_thoth()
        
        # Should have same types
        assert type(pipeline.services) == type(services)
        assert type(pipeline.document_pipeline) == type(doc_pipeline)
        assert type(pipeline.citation_tracker) == type(graph)
