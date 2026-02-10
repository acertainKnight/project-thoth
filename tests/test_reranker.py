"""
Tests for reranking layer (Phase 2).

Tests Cohere, LLM-based, and NoOp rerankers.
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from thoth.rag.reranker import (
    LLMReranker,
    NoOpReranker,
    create_reranker,
)


class TestNoOpReranker:
    """Test NoOp reranker (passthrough)."""

    @pytest.mark.asyncio
    async def test_noop_reranker(self):
        """Test NoOp reranker returns documents unchanged."""
        reranker = NoOpReranker()
        assert reranker.get_name() == 'noop'

        docs = [
            Document(page_content='doc1', metadata={'id': 1}),
            Document(page_content='doc2', metadata={'id': 2}),
            Document(page_content='doc3', metadata={'id': 3}),
        ]

        result = await reranker.rerank_async('test query', docs, top_n=2)

        # Should return top_n docs unchanged
        assert len(result) == 2
        assert result[0].metadata['id'] == 1
        assert result[1].metadata['id'] == 2


class TestLLMReranker:
    """Test LLM-based reranker."""

    @pytest.mark.asyncio
    async def test_llm_reranker_scoring(self):
        """Test LLM reranker scores and reorders documents."""
        # Mock LLM client
        mock_llm = MagicMock()

        # Mock responses with different scores
        mock_response_1 = MagicMock()
        mock_response_1.content = '0.9'

        mock_response_2 = MagicMock()
        mock_response_2.content = '0.3'

        mock_response_3 = MagicMock()
        mock_response_3.content = '0.7'

        mock_llm.invoke.side_effect = [
            mock_response_1,
            mock_response_2,
            mock_response_3,
        ]

        reranker = LLMReranker(llm_client=mock_llm, model='test-model')
        assert 'test-model' in reranker.get_name()

        docs = [
            Document(page_content='doc1', metadata={'id': 1}),
            Document(page_content='doc2', metadata={'id': 2}),
            Document(page_content='doc3', metadata={'id': 3}),
        ]

        result = await reranker.rerank_async('test query', docs)

        # Should reorder by score: doc1 (0.9), doc3 (0.7), doc2 (0.3)
        assert len(result) == 3
        assert result[0].metadata['id'] == 1
        assert result[0].metadata['rerank_score'] == 0.9
        assert result[1].metadata['id'] == 3
        assert result[1].metadata['rerank_score'] == 0.7
        assert result[2].metadata['id'] == 2
        assert result[2].metadata['rerank_score'] == 0.3


class TestRerankerFactory:
    """Test reranker factory."""

    def test_create_reranker_noop(self):
        """Test creating NoOp reranker."""
        reranker = create_reranker('none', api_keys={})
        assert isinstance(reranker, NoOpReranker)

    def test_create_reranker_llm(self):
        """Test creating LLM reranker."""
        mock_llm = MagicMock()
        reranker = create_reranker('llm', api_keys={}, llm_client=mock_llm)
        assert isinstance(reranker, LLMReranker)

    def test_create_reranker_auto_with_llm(self):
        """Test auto-detection selects LLM when no Cohere key."""
        mock_llm = MagicMock()
        reranker = create_reranker('auto', api_keys={}, llm_client=mock_llm)
        assert isinstance(reranker, LLMReranker)

    def test_create_reranker_auto_fallback(self):
        """Test auto-detection falls back to NoOp when nothing available."""
        reranker = create_reranker('auto', api_keys={}, llm_client=None)
        assert isinstance(reranker, NoOpReranker)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
