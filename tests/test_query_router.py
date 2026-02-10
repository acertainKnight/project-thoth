"""
Tests for query routing (Phase 5).

Tests adaptive query classification and routing.
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from thoth.rag.query_router import QueryRouter, QueryType


class TestQueryRouter:
    """Test query router classification."""

    def test_router_disabled(self):
        """Test router returns standard when disabled."""
        router = QueryRouter(enabled=False)

        result = router.classify_query('What is machine learning?')
        assert result == QueryType.STANDARD_RAG

    def test_classify_direct_answer(self):
        """Test classifying direct answer queries."""
        router = QueryRouter(enabled=True, use_semantic_router=False)

        # General knowledge questions
        result = router.classify_query('What is the capital of France?')
        assert result == QueryType.DIRECT_ANSWER

        result = router.classify_query('Define neural network')
        assert result == QueryType.DIRECT_ANSWER

    def test_classify_research_question(self):
        """Test research questions go to standard RAG."""
        router = QueryRouter(enabled=True, use_semantic_router=False)

        # Research-specific questions should use RAG
        result = router.classify_query('What is the methodology in this paper?')
        assert result == QueryType.STANDARD_RAG

        result = router.classify_query('What datasets were used in the study?')
        assert result == QueryType.STANDARD_RAG

    def test_classify_multi_hop(self):
        """Test classifying multi-hop queries."""
        router = QueryRouter(enabled=True, use_semantic_router=False)

        result = router.classify_query('Compare approach A versus approach B')
        assert result == QueryType.MULTI_HOP_RAG

        result = router.classify_query('Synthesize findings across papers')
        assert result == QueryType.MULTI_HOP_RAG

    def test_crag_fallback_low_confidence(self):
        """Test CRAG fallback triggers on low confidence."""
        router = QueryRouter(enabled=True, confidence_threshold=0.6)

        # Documents with low scores
        docs = [
            Document(page_content='doc1', metadata={'similarity': 0.4}),
            Document(page_content='doc2', metadata={'similarity': 0.5}),
        ]

        should_fallback = router.should_use_crag_fallback(docs, 'test query')
        assert should_fallback is True

    def test_crag_fallback_high_confidence(self):
        """Test CRAG fallback doesn't trigger on high confidence."""
        router = QueryRouter(enabled=True, confidence_threshold=0.6)

        # Documents with high scores
        docs = [
            Document(page_content='doc1', metadata={'similarity': 0.8}),
            Document(page_content='doc2', metadata={'similarity': 0.9}),
        ]

        should_fallback = router.should_use_crag_fallback(docs, 'test query')
        assert should_fallback is False

    @pytest.mark.asyncio
    async def test_query_decomposition(self):
        """Test multi-hop query decomposition."""
        router = QueryRouter(enabled=True)

        # Mock LLM client
        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = """1. What is method A?
2. What is method B?
3. How do they compare?"""
        mock_llm.invoke.return_value = mock_response

        sub_queries = await router.decompose_query_async(
            'Compare method A and method B', mock_llm
        )

        assert len(sub_queries) == 3
        assert 'method A' in sub_queries[0].lower()
        assert 'method B' in sub_queries[1].lower()
        assert 'compare' in sub_queries[2].lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
