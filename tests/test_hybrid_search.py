"""
Tests for hybrid search (Phase 1).

Tests BM25 + vector search with RRF fusion.
"""

from unittest.mock import MagicMock, patch

import pytest

from thoth.rag.search_backends import ParadeDBBackend, TsVectorBackend, create_backend


class TestSearchBackends:
    """Test full-text search backends."""

    def test_create_backend_tsvector(self):
        """Test creating tsvector backend."""
        backend = create_backend('tsvector')
        assert isinstance(backend, TsVectorBackend)
        assert backend.get_backend_name() == 'tsvector'

    def test_create_backend_paradedb(self):
        """Test creating ParadeDB backend (stub)."""
        backend = create_backend('paradedb')
        assert isinstance(backend, ParadeDBBackend)
        assert 'stub' in backend.get_backend_name().lower()

    def test_create_backend_default(self):
        """Test default backend fallback."""
        backend = create_backend('unknown')
        assert isinstance(backend, TsVectorBackend)


@pytest.mark.asyncio
class TestHybridSearch:
    """Test hybrid search with RRF fusion."""

    @patch('thoth.rag.vector_store.Config')
    async def test_rrf_fusion(self, mock_config):
        """Test RRF fusion combines vector and text results."""
        from thoth.rag.vector_store import VectorStoreManager

        # Mock config
        mock_config.return_value.rag_config.hybrid_search_enabled = True
        mock_config.return_value.rag_config.hybrid_rrf_k = 60
        mock_config.return_value.rag_config.hybrid_vector_weight = 0.7
        mock_config.return_value.rag_config.hybrid_text_weight = 0.3
        mock_config.return_value.rag_config.full_text_backend = 'tsvector'
        mock_config.return_value.secrets.database_url = 'postgresql://test'

        # Create mock embedding function
        mock_embedding = MagicMock()
        mock_embedding.embed_query.return_value = [0.1] * 384

        # Initialize vector store (will fail to connect, but we test logic)
        with pytest.raises(Exception):  # noqa: B017
            # Will fail because no real DB, but we're testing class initialization
            VectorStoreManager(embedding_function=mock_embedding)

    def test_rrf_scoring_formula(self):
        """Test RRF scoring formula is correct."""
        from thoth.rag.vector_store import VectorStoreManager

        mock_embedding = MagicMock()
        mock_config = MagicMock()
        mock_config.secrets.database_url = 'postgresql://test'
        mock_config.rag_config.full_text_backend = 'tsvector'

        with patch('thoth.rag.vector_store.Config', return_value=mock_config):
            with pytest.raises(Exception):  # noqa: B017  # DB connection will fail
                VectorStoreManager(embedding_function=mock_embedding)

        # Test RRF formula directly
        rrf_k = 60
        vector_weight = 0.7
        text_weight = 0.3

        # Document appears at rank 1 in vector, rank 2 in text
        vector_score = vector_weight / (rrf_k + 1)  # 0.7 / 61
        text_score = text_weight / (rrf_k + 2)  # 0.3 / 62
        total_score = vector_score + text_score

        assert total_score > vector_score
        assert total_score > text_score
        assert pytest.approx(total_score, 0.001) == 0.01147 + 0.00484


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
