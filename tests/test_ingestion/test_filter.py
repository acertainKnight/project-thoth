"""
Tests for Filter component.

Tests the article filtering and evaluation functionality.
"""

from unittest.mock import MagicMock, patch

import pytest

from thoth.ingestion.filter import Filter
from thoth.utilities.models import (
    PreDownloadEvaluationResponse,
    ScrapedArticleMetadata,
)


class TestFilter:
    """Test suite for Filter component."""

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service manager for testing."""
        service_manager = MagicMock()

        # Mock query service
        service_manager.query.list_queries.return_value = ['test_query']
        service_manager.query.get_query.return_value = MagicMock(
            name='test_query',
            minimum_relevance_score=0.7,
        )

        # Mock article service
        service_manager.article.evaluate_for_download.return_value = (
            PreDownloadEvaluationResponse(
                relevance_score=0.8,
                should_download=True,
                keyword_matches=['machine learning'],
                topic_analysis='Relevant to research interests',
                reasoning='Relevant to research interests',
                confidence=0.9,
                matching_queries=['test_query'],
            )
        )

        # Mock initialize method
        service_manager.initialize.return_value = None

        return service_manager

    @pytest.fixture
    def filter_instance(self, mock_service_manager, temp_workspace):
        """Create a Filter instance for testing."""
        return Filter(
            service_manager=mock_service_manager,
            storage_dir=temp_workspace / 'filter',
        )

    @pytest.fixture
    def sample_scraped_article(self):
        """Create a sample scraped article."""
        return ScrapedArticleMetadata(
            title='Test Article',
            authors=['Author One', 'Author Two'],
            abstract='This is a test abstract about machine learning.',
            journal='Test Journal',
            source='test_source',
            keywords=['machine-learning', 'deep-learning'],
            pdf_url='https://example.com/test.pdf',
            doi='10.1234/test',
        )

    def test_process_article_relevant(
        self, filter_instance, sample_scraped_article, sample_research_query
    ):
        """Test processing a relevant article."""
        # Setup mock responses
        filter_instance.service_manager.query.list_queries.return_value = ['test_query']
        filter_instance.service_manager.query.get_query.return_value = (
            sample_research_query
        )
        filter_instance.service_manager.article.evaluate_for_download.return_value = (
            PreDownloadEvaluationResponse(
                relevance_score=0.9,
                should_download=True,
                keyword_matches=['machine learning'],
                topic_analysis='Highly relevant',
                reasoning='Highly relevant',
                confidence=0.95,
                matching_queries=['test_query'],
            )
        )

        with patch('thoth.ingestion.filter.requests.get') as mock_get:
            # Mock successful PDF download
            mock_response = MagicMock()
            mock_response.raise_for_status.return_value = None
            mock_response.iter_content.return_value = [b'PDF content']
            mock_get.return_value = mock_response

            result = filter_instance.process_article(
                metadata=sample_scraped_article,
                download_pdf=True,
            )

            assert result['decision'] == 'download'
            assert result['evaluation'].relevance_score == 0.9
            assert result['evaluation'].should_download is True
            assert result['pdf_downloaded'] is True
            assert result['pdf_path'] is not None

    def test_process_article_not_relevant(
        self, filter_instance, sample_scraped_article, sample_research_query
    ):
        """Test processing a non-relevant article."""
        # Setup mock responses
        filter_instance.service_manager.query.list_queries.return_value = ['test_query']
        filter_instance.service_manager.query.get_query.return_value = (
            sample_research_query
        )
        filter_instance.service_manager.article.evaluate_for_download.return_value = (
            PreDownloadEvaluationResponse(
                relevance_score=0.2,
                should_download=False,
                keyword_matches=[],
                topic_analysis='Not relevant',
                reasoning='Not relevant',
                confidence=0.9,
                matching_queries=[],
            )
        )

        result = filter_instance.process_article(
            metadata=sample_scraped_article,
            download_pdf=False,
        )

        assert result['decision'] == 'skip'
        assert result['evaluation'].relevance_score == 0.2
        assert result['evaluation'].should_download is False
        assert result['pdf_path'] is None

    def test_process_article_excluded(
        self, filter_instance, sample_scraped_article, sample_research_query
    ):
        """Test processing an excluded article."""
        # Modify article to have excluded content
        sample_scraped_article.keywords = ['hardware', 'robotics']
        sample_scraped_article.abstract = 'This paper focuses on hardware and robotics.'

        # Setup mock responses
        filter_instance.service_manager.query.list_queries.return_value = ['test_query']
        filter_instance.service_manager.query.get_query.return_value = (
            sample_research_query
        )
        filter_instance.service_manager.article.evaluate_for_download.return_value = (
            PreDownloadEvaluationResponse(
                relevance_score=0.1,
                should_download=False,
                keyword_matches=[],
                topic_analysis='Contains excluded topics',
                reasoning='Contains excluded topic: hardware',
                confidence=0.95,
                matching_queries=[],
            )
        )

        result = filter_instance.process_article(
            metadata=sample_scraped_article,
            download_pdf=False,
        )

        assert result['decision'] == 'skip'
        assert 'hardware' in result['evaluation'].reasoning

    def test_process_article_no_queries(self, filter_instance, sample_scraped_article):
        """Test processing when no queries exist."""
        # No queries available
        filter_instance.service_manager.query.list_queries.return_value = []

        result = filter_instance.process_article(
            metadata=sample_scraped_article,
            download_pdf=False,
        )

        assert result['decision'] == 'skip'
        assert (
            result['evaluation'].reasoning
            == 'No research queries configured for filtering'
        )

    def test_get_statistics(self, filter_instance):
        """Test getting filter statistics."""
        # Initially no statistics
        stats = filter_instance.get_statistics()
        assert stats['total_articles'] == 0

        # Process some articles to generate statistics
        articles = [
            ScrapedArticleMetadata(
                title=f'Article {i}',
                authors=['Author'],
                abstract='Abstract',
                journal='Journal',
                source='test',
                keywords=['test'],
            )
            for i in range(3)
        ]

        # Mock different evaluations
        evaluations = [
            PreDownloadEvaluationResponse(
                relevance_score=0.9,
                should_download=True,
                keyword_matches=['ml'],
                topic_analysis='Good',
                reasoning='Good',
                confidence=0.9,
                matching_queries=['test_query'],
            ),
            PreDownloadEvaluationResponse(
                relevance_score=0.3,
                should_download=False,
                keyword_matches=[],
                topic_analysis='Bad',
                reasoning='Bad',
                confidence=0.9,
                matching_queries=[],
            ),
            PreDownloadEvaluationResponse(
                relevance_score=0.8,
                should_download=True,
                keyword_matches=['ml'],
                topic_analysis='Good',
                reasoning='Good',
                confidence=0.9,
                matching_queries=['test_query'],
            ),
        ]

        filter_instance.service_manager.query.list_queries.return_value = ['test_query']
        filter_instance.service_manager.query.get_query.return_value = MagicMock()
        filter_instance.service_manager.article.evaluate_for_download.side_effect = (
            evaluations
        )

        # Process articles
        for article in articles:
            filter_instance.process_article(article, download_pdf=False)

        stats = filter_instance.get_statistics()

        assert stats['total_articles'] == 3
        assert stats['downloaded'] == 2
        assert stats['skipped'] == 1

    def test_clear_statistics(self, filter_instance):
        """Test clearing statistics."""
        # This test is no longer relevant as Filter doesn't have clear_statistics
        # Statistics are now persisted in JSON files
        pass

    def test_error_handling(self, filter_instance, sample_scraped_article):
        """Test error handling during processing."""
        # Mock an error during evaluation
        filter_instance.service_manager.article.evaluate_for_download.side_effect = (
            Exception('Test error')
        )

        result = filter_instance.process_article(
            metadata=sample_scraped_article,
            download_pdf=False,
        )

        assert result['decision'] == 'error'
        assert 'Test error' in result['error_message']
        assert result['evaluation'].relevance_score == 0.0
