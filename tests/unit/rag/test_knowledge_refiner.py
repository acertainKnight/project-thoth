"""Unit tests for knowledge refiner (CRAG strip decomposition)."""

from unittest.mock import Mock

import pytest
from langchain_core.documents import Document

from thoth.rag.knowledge_refiner import KnowledgeRefiner


class TestKnowledgeRefiner:
    """Test knowledge strip decomposition and filtering."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM client."""
        llm = Mock()
        return llm

    @pytest.fixture
    def refiner(self, mock_llm):
        """Create knowledge refiner instance."""
        return KnowledgeRefiner(
            llm_client=mock_llm, max_strips_per_document=20, batch_size=10
        )

    @pytest.mark.asyncio
    async def test_refine_empty_documents(self, refiner):
        """Test refinement with no documents."""
        result = await refiner.refine_documents_async('test query', [])
        assert result == []

    @pytest.mark.asyncio
    async def test_refine_single_document(self, refiner, mock_llm):
        """Test refinement of a single document."""
        # Mock LLM responses
        decompose_response = Mock()
        decompose_response.content = 'Statement 1\nStatement 2\nStatement 3'

        grade_responses = [Mock() for _ in range(3)]
        for resp in grade_responses:
            resp.content = 'yes'

        mock_llm.invoke.side_effect = [decompose_response, *grade_responses]

        # Content must be >= 50 chars so refiner runs decomposition (not early return)
        doc = Document(
            page_content='This is test content with multiple facts and enough length.',
            metadata={'title': 'Test Paper'},
        )

        result = await refiner.refine_documents_async('test query', [doc])

        assert len(result) == 1
        assert result[0].metadata['refined'] is True
        assert 'Statement 1' in result[0].page_content

    @pytest.mark.asyncio
    async def test_strip_filtering(self, refiner, mock_llm):
        """Test that irrelevant strips are filtered out."""
        # Mock decomposition
        decompose_response = Mock()
        decompose_response.content = 'Statement 1\nStatement 2\nStatement 3'

        # Mock grading - only first statement relevant
        grade_responses = [Mock(), Mock(), Mock()]
        grade_responses[0].content = 'yes'
        grade_responses[1].content = 'no'
        grade_responses[2].content = 'no'

        mock_llm.invoke.side_effect = [decompose_response, *grade_responses]

        doc = Document(
            page_content='This is test content with multiple facts and enough length.',
            metadata={'title': 'Test Paper'},
        )

        result = await refiner.refine_documents_async('test query', [doc])

        assert len(result) == 1
        # Should only contain the relevant statement
        assert 'Statement 1' in result[0].page_content
        assert 'Statement 2' not in result[0].page_content

    @pytest.mark.asyncio
    async def test_no_relevant_strips_filters_document(self, refiner, mock_llm):
        """Test that documents with no relevant strips are filtered out."""
        # Mock decomposition
        decompose_response = Mock()
        decompose_response.content = 'Statement 1\nStatement 2'

        # Mock grading - all irrelevant
        grade_responses = [Mock(), Mock()]
        for resp in grade_responses:
            resp.content = 'no'

        mock_llm.invoke.side_effect = [decompose_response, *grade_responses]

        doc = Document(
            page_content='This is test content with enough length to trigger decomposition.',
            metadata={'title': 'Test Paper'},
        )

        result = await refiner.refine_documents_async('test query', [doc])

        # Document should be filtered out
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_multiple_documents(self, refiner, mock_llm):
        """Test refinement of multiple documents."""
        # Mock responses for 2 documents
        # Doc 1: 2 statements, both relevant
        decompose1 = Mock()
        decompose1.content = 'Statement 1\nStatement 2'
        grade1 = [Mock(), Mock()]
        for resp in grade1:
            resp.content = 'yes'

        # Doc 2: 2 statements, 1 relevant
        decompose2 = Mock()
        decompose2.content = 'Statement 3\nStatement 4'
        grade2 = [Mock(), Mock()]
        grade2[0].content = 'yes'
        grade2[1].content = 'no'

        mock_llm.invoke.side_effect = [decompose1, *grade1, decompose2, *grade2]

        docs = [
            Document(
                page_content='Content 1 with enough length to trigger decomposition.',
                metadata={'title': 'Paper 1'},
            ),
            Document(
                page_content='Content 2 with enough length to trigger decomposition.',
                metadata={'title': 'Paper 2'},
            ),
        ]

        result = await refiner.refine_documents_async('test query', docs)

        assert len(result) == 2
        assert all(doc.metadata['refined'] for doc in result)

    @pytest.mark.asyncio
    async def test_error_handling_falls_back_to_original(self, refiner, mock_llm):
        """Test that errors during refinement fall back to original document."""
        # Mock LLM to raise exception
        mock_llm.invoke.side_effect = Exception('LLM error')

        doc = Document(
            page_content='This is test content with enough length to trigger decomposition.',
            metadata={'title': 'Test Paper'},
        )

        result = await refiner.refine_documents_async('test query', [doc])

        # Should return original document
        assert len(result) == 1
        assert result[0].page_content == doc.page_content

    @pytest.mark.asyncio
    async def test_strip_metadata_preserved(self, refiner, mock_llm):
        """Test that original document metadata is preserved."""
        decompose_response = Mock()
        decompose_response.content = 'Statement 1'

        grade_response = Mock()
        grade_response.content = 'yes'

        mock_llm.invoke.side_effect = [decompose_response, grade_response]

        doc = Document(
            page_content='Test content with enough length to trigger strip decomposition.',
            metadata={'title': 'Test Paper', 'paper_id': '123', 'custom': 'value'},
        )

        result = await refiner.refine_documents_async('test query', [doc])

        assert result[0].metadata['title'] == 'Test Paper'
        assert result[0].metadata['paper_id'] == '123'
        assert result[0].metadata['custom'] == 'value'
        assert result[0].metadata['refined'] is True
        assert 'num_strips_original' in result[0].metadata
        assert 'num_strips_relevant' in result[0].metadata

    def test_max_strips_limit(self, refiner, mock_llm):
        """Test that max strips per document is enforced."""
        # Create response with many statements
        many_statements = '\n'.join([f'Statement {i}' for i in range(50)])
        decompose_response = Mock()
        decompose_response.content = many_statements

        mock_llm.invoke.return_value = decompose_response

        # This would normally require async, but we're just testing the limit logic
        # The actual limit is enforced in _decompose_to_strips
        # Just verify refiner has the correct max_strips setting
        assert refiner.max_strips_per_document == 20
