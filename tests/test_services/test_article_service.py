"""
Tests for ArticleService.

Tests the article evaluation and scoring functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from thoth.services.article_service import ArticleService
from thoth.utilities.models import (
    QueryEvaluationResponse,
    ResearchQuery,
    ScrapedArticleMetadata,
)


class TestArticleService:
    """Test suite for ArticleService."""

    @pytest.fixture
    def article_service(self):
        """Create an ArticleService instance for testing."""
        return ArticleService()

    @pytest.fixture
    def sample_article(self):
        """Create a sample article for testing."""
        return ScrapedArticleMetadata(
            title='Deep Learning for Natural Language Processing',
            authors=['John Doe', 'Jane Smith'],
            abstract='This paper presents a novel approach to NLP using deep learning techniques. We introduce a transformer-based architecture that achieves state-of-the-art results on multiple benchmarks.',
            journal='NeurIPS',
            source='test',
            keywords=['deep learning', 'NLP', 'transformers'],
            pdf_url='https://example.com/paper.pdf',
        )

    def test_evaluate_against_query_high_score(
        self, article_service, sample_article, sample_research_query
    ):
        """Test evaluating article with high relevance score."""
        # Mock LLM structured response
        mock_response = QueryEvaluationResponse(
            relevance_score=0.9,
            meets_criteria=True,
            keyword_matches=['machine learning', 'neural networks'],
            topic_analysis='Highly relevant to research query',
            methodology_match='Good match for methodology',
            reasoning='This article directly addresses the research question',
            recommendation='keep',
            confidence=0.95,
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = mock_response
        mock_llm.with_structured_output.return_value = mock_structured

        # Mock the private _llm attribute
        article_service._llm = mock_llm

        evaluation = article_service.evaluate_against_query(
            article=sample_article,
            query=sample_research_query,
        )

        assert evaluation.relevance_score == 0.9
        assert evaluation.meets_criteria is True
        assert evaluation.recommendation == 'keep'

    def test_evaluate_against_query_low_score(
        self, article_service, sample_article, sample_research_query
    ):
        """Test evaluating article with low relevance score."""
        mock_response = QueryEvaluationResponse(
            relevance_score=0.3,
            meets_criteria=False,
            keyword_matches=[],
            topic_analysis='Not relevant to research interests',
            methodology_match='Does not match methodology preferences',
            reasoning='This article is outside the scope of the research question',
            recommendation='reject',
            confidence=0.9,
        )

        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = mock_response
        mock_llm.with_structured_output.return_value = mock_structured

        # Mock the private _llm attribute
        article_service._llm = mock_llm

        evaluation = article_service.evaluate_against_query(
            article=sample_article,
            query=sample_research_query,
        )

        assert evaluation.relevance_score == 0.3
        assert evaluation.meets_criteria is False
        assert evaluation.recommendation == 'reject'

    def test_evaluate_for_download_with_queries(self, article_service, sample_article):
        """Test evaluating article for download with multiple queries."""
        queries = [
            ResearchQuery(
                name='nlp_query',
                description='NLP research',
                research_question='What are advances in NLP?',
                keywords=['NLP', 'natural language'],
                required_topics=['NLP'],
                preferred_topics=['deep learning'],
                excluded_topics=['hardware'],
                minimum_relevance_score=0.7,
            ),
            ResearchQuery(
                name='ml_query',
                description='ML research',
                research_question='What are advances in ML?',
                keywords=['machine learning'],
                required_topics=['machine learning'],
                preferred_topics=['neural networks'],
                excluded_topics=['robotics'],
                minimum_relevance_score=0.7,
            ),
        ]

        # Mock evaluate_against_query to return different scores
        with patch.object(article_service, 'evaluate_against_query') as mock_eval:
            mock_eval.side_effect = [
                QueryEvaluationResponse(
                    relevance_score=0.9,
                    meets_criteria=True,
                    keyword_matches=['NLP', 'deep learning'],
                    topic_analysis='Great match for NLP',
                    reasoning='Highly relevant',
                    recommendation='keep',
                    confidence=0.9,
                ),
                QueryEvaluationResponse(
                    relevance_score=0.4,
                    meets_criteria=False,
                    keyword_matches=['machine learning'],
                    topic_analysis='Weak match for ML',
                    reasoning='Somewhat relevant',
                    recommendation='reject',
                    confidence=0.8,
                ),
            ]

            result = article_service.evaluate_for_download(
                metadata=sample_article,
                queries=queries,
            )

            assert result.relevance_score == 0.9  # Best score
            assert result.should_download is True
            assert 'nlp_query' in result.matching_queries
            assert 'ml_query' not in result.matching_queries

    def test_evaluate_for_download_no_queries(self, article_service, sample_article):
        """Test evaluating article when no queries are configured."""
        result = article_service.evaluate_for_download(
            metadata=sample_article,
            queries=[],
        )

        assert result.relevance_score == 1.0
        assert result.should_download is True
        assert 'No queries configured' in result.topic_analysis

    def test_check_relevance(
        self, article_service, sample_article, sample_research_query
    ):
        """Test quick relevance check based on keywords."""
        score = article_service.check_relevance(
            title=sample_article.title,
            abstract=sample_article.abstract,
            query=sample_research_query,
        )

        # Should have some score since 'machine learning' and 'neural networks'
        # are in the query keywords
        assert score > 0.0
        assert score <= 1.0

    def test_check_relevance_with_excluded_topics(
        self, article_service, sample_research_query
    ):
        """Test relevance check with excluded topics."""
        # Add hardware to excluded topics
        sample_research_query.excluded_topics = ['hardware']

        score = article_service.check_relevance(
            title='Hardware Acceleration for ML',
            abstract='This paper discusses hardware solutions for machine learning.',
            query=sample_research_query,
        )

        # Score should be reduced due to excluded topic
        assert score < 0.5

    def test_evaluate_for_download_no_matches(self, article_service, sample_article):
        """Test evaluating article when no queries match."""
        queries = [
            ResearchQuery(
                name='unrelated_query',
                description='Unrelated research',
                research_question='What are advances in quantum computing?',
                keywords=['quantum', 'qubit'],
                required_topics=['quantum computing'],
                preferred_topics=[],
                excluded_topics=[],
                minimum_relevance_score=0.7,
            ),
        ]

        with patch.object(article_service, 'evaluate_against_query') as mock_eval:
            mock_eval.return_value = QueryEvaluationResponse(
                relevance_score=0.2,
                meets_criteria=False,
                keyword_matches=[],
                topic_analysis='Not relevant',
                reasoning='Article is unrelated to quantum computing',
                recommendation='reject',
                confidence=0.95,
            )

            result = article_service.evaluate_for_download(
                metadata=sample_article,
                queries=queries,
            )

            assert result.relevance_score == 0.2
            assert result.should_download is False
            assert len(result.matching_queries) == 0
