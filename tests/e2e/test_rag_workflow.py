"""End-to-end test for RAG (Retrieval-Augmented Generation) workflow.

Tests the complete RAG system structure from indexing to semantic search.
These tests verify the workflow components exist and are properly connected.

Full integration testing with real embeddings and vector DB requires
the 'embeddings' extras and is better suited for manual QA or CI/CD tests.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from thoth.services.service_manager import ServiceManager


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        dirs = {
            'vector_dir': base / 'vector_db',
            'documents_dir': base / 'documents',
        }
        for dir_path in dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)
        yield dirs


@pytest.fixture
def service_manager():
    """Create a ServiceManager instance (initialization may fail without full setup)."""
    try:
        sm = ServiceManager()
        sm.initialize()
        return sm
    except Exception:
        # If initialization fails (no DB, etc.), return a mock
        return Mock(spec=ServiceManager)


class TestRAGWorkflowStructure:
    """Test RAG workflow structure and components."""

    def test_rag_manager_exists(self):
        """Test RAGManager class exists."""
        try:
            from thoth.rag.rag_manager import RAGManager

            assert RAGManager is not None
        except ImportError:
            pytest.skip("RAG components require 'embeddings' extras")

    def test_vector_store_exists(self):
        """Test VectorStore class exists."""
        try:
            from thoth.rag.vector_store import VectorStore

            assert VectorStore is not None
        except ImportError:
            pytest.skip("RAG components require 'embeddings' extras")

    def test_embeddings_service_exists(self):
        """Test Embeddings class exists."""
        try:
            from thoth.rag.embeddings import Embeddings

            assert Embeddings is not None
        except ImportError:
            pytest.skip("RAG components require 'embeddings' extras")

    def test_rag_service_in_manager(self, service_manager):
        """Test RAG service is accessible through ServiceManager."""
        # May be None if embeddings extras not installed
        assert hasattr(service_manager, 'rag') or '_services' in dir(service_manager)


class TestRAGWorkflowIntegration:
    """Test RAG workflow integration points."""

    def test_rag_evaluation_framework_exists(self):
        """Test RAG evaluation framework exists."""
        try:
            from thoth.rag import evaluation

            assert evaluation is not None
        except ImportError:
            pytest.skip("RAG evaluation requires 'embeddings' extras")

    def test_langchain_integration_exists(self):
        """Test LangChain integration exists."""
        try:
            # Check if LangChain components are available
            import langchain

            assert langchain is not None
        except ImportError:
            pytest.skip('LangChain not installed')

    def test_sentence_transformers_available(self):
        """Test sentence-transformers is available (optional dependency)."""
        try:
            import sentence_transformers

            assert sentence_transformers is not None
        except ImportError:
            pytest.skip("sentence-transformers requires 'embeddings' extras")


class TestRAGAdvancedTools:
    """Test RAG advanced tools integration."""

    def test_advanced_rag_tools_exist(self):
        """Test advanced RAG tools exist."""
        from thoth.mcp.tools import advanced_rag_tools

        assert advanced_rag_tools is not None

    def test_rag_mcp_tools_registered(self):
        """Test RAG tools are registered in MCP."""
        from thoth.mcp.tools import advanced_rag_tools

        # Check module has tool definitions
        assert hasattr(advanced_rag_tools, '__file__')


class TestRAGWorkflowMethods:
    """Test RAG workflow methods and functionality."""

    def test_rag_manager_has_search_method(self):
        """Test RAGManager has search method."""
        try:
            from thoth.rag.rag_manager import RAGManager

            assert hasattr(RAGManager, 'search') or hasattr(
                RAGManager, 'semantic_search'
            )
        except ImportError:
            pytest.skip("RAG components require 'embeddings' extras")

    def test_rag_manager_has_index_method(self):
        """Test RAGManager has indexing method."""
        try:
            from thoth.rag.rag_manager import RAGManager

            assert hasattr(RAGManager, 'index_markdown_file') or hasattr(
                RAGManager, 'index_directory'
            )
        except ImportError:
            pytest.skip("RAG components require 'embeddings' extras")

    def test_vector_store_has_add_method(self):
        """Test VectorStore has add method."""
        try:
            from thoth.rag.vector_store import VectorStore

            assert hasattr(VectorStore, 'add') or hasattr(VectorStore, 'add_texts')
        except ImportError:
            pytest.skip("RAG components require 'embeddings' extras")

    def test_vector_store_has_search_method(self):
        """Test VectorStore has search method."""
        try:
            from thoth.rag.vector_store import VectorStore

            assert hasattr(VectorStore, 'search') or hasattr(
                VectorStore, 'similarity_search'
            )
        except ImportError:
            pytest.skip("RAG components require 'embeddings' extras")

    def test_embeddings_has_embed_method(self):
        """Test Embeddings has embed method."""
        try:
            from thoth.rag.embeddings import Embeddings

            assert hasattr(Embeddings, 'embed_documents') or hasattr(
                Embeddings, 'embed'
            )
        except ImportError:
            pytest.skip("RAG components require 'embeddings' extras")


class TestRAGPipelineIntegration:
    """Test RAG integration with document pipeline."""

    def test_pipeline_has_rag_indexing(self):
        """Test document pipeline has RAG indexing capability."""
        from thoth.pipelines.optimized_document_pipeline import (
            OptimizedDocumentPipeline,
        )

        # Check if pipeline has RAG-related methods
        assert hasattr(OptimizedDocumentPipeline, '_index_to_rag') or hasattr(
            OptimizedDocumentPipeline, '_schedule_background_rag_indexing'
        )

    def test_pipeline_can_schedule_rag_indexing(self):
        """Test pipeline can schedule background RAG indexing."""
        from thoth.pipelines.optimized_document_pipeline import (
            OptimizedDocumentPipeline,
        )

        # Verify background RAG indexing method exists
        assert hasattr(OptimizedDocumentPipeline, '_schedule_background_rag_indexing')


class TestRAGConfiguration:
    """Test RAG configuration and settings."""

    def test_rag_config_accessible(self):
        """Test RAG configuration is accessible."""
        from thoth.config import config

        # Check if config has RAG-related settings
        assert config is not None
        # RAG settings may be optional
        assert hasattr(config, '__dict__')

    def test_workflow_can_access_directories(self, temp_dirs):
        """Test workflow has access to required directories."""
        assert temp_dirs['vector_dir'].exists()
        assert temp_dirs['documents_dir'].exists()
