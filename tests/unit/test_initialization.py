"""Tests for the initialization module."""

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
        
        # Tag service should have citation tracker set
        assert hasattr(services.tag, '_citation_tracker')
        assert services.tag._citation_tracker is graph

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
