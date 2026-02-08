"""Test suite for RAGService."""

import pytest


class TestRAGServiceInitialization:
    """Test RAGService initialization (requires embeddings extras)."""

    def test_service_import_conditional(self):
        """Test RAGService import is conditional on embeddings extras."""
        try:
            from thoth.services.rag_service import RAGService

            # If import succeeds, test initialization
            service = RAGService()

            assert service.config is not None
        except ImportError:
            # Embeddings extras not installed - this is expected and OK
            pytest.skip('RAG service not available (embeddings extras not installed)')


class TestRAGServiceMethods:
    """Test RAGService key methods."""

    def test_service_has_required_methods(self):
        """Test RAGService has all required methods."""
        try:
            from thoth.services.rag_service import RAGService

            service = RAGService()

            # Check key methods exist (actual methods from implementation)
            assert hasattr(service, 'index_file')
            assert hasattr(service, 'index_directory')
            assert hasattr(service, 'search')
            assert hasattr(service, 'ask_question')
            assert hasattr(service, 'get_statistics')
        except ImportError:
            pytest.skip('RAG service not available (embeddings extras not installed)')

    def test_initialize_method(self):
        """Test initialize() method."""
        try:
            from thoth.services.rag_service import RAGService

            service = RAGService()

            # Should not raise
            service.initialize()
        except ImportError:
            pytest.skip('RAG service not available (embeddings extras not installed)')
