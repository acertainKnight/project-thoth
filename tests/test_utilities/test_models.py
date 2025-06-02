"""
Tests for utilities models.

Tests the data models and schemas used throughout the application.
"""

import pytest
from pydantic import ValidationError

from thoth.utilities.models import (
    AnalysisResponse,
    Citation,
    DiscoveryResult,
    DiscoverySource,
    PreDownloadEvaluationResponse,
    QueryEvaluationResponse,
    ResearchQuery,
    ScheduleConfig,
    ScrapedArticleMetadata,
)


class TestAnalysisResponse:
    """Test suite for AnalysisResponse model."""

    def test_valid_analysis_response(self):
        """Test creating a valid AnalysisResponse."""
        response = AnalysisResponse(
            abstract='Test abstract',
            key_points='- Finding 1\n- Finding 2',
            summary='Test summary',
            objectives='Test objectives',
            methodology='Test methodology',
            data='Test data',
            experimental_setup='Test setup',
            evaluation_metrics='Test metrics',
            results='Test results',
            discussion='Test discussion',
            strengths='Test strengths',
            limitations='Test limitations',
            future_work='Test future work',
            related_work='Test related work',
            tags=['tag1', 'tag2'],
        )

        assert response.abstract == 'Test abstract'
        assert '- Finding 1' in response.key_points
        assert response.methodology == 'Test methodology'
        assert len(response.tags) == 2

    def test_optional_fields(self):
        """Test optional fields in AnalysisResponse."""
        response = AnalysisResponse(
            abstract='Test abstract',
            key_points='- Finding 1',
        )

        assert response.abstract == 'Test abstract'
        assert response.summary is None
        assert response.methodology is None
        assert response.tags is None

    def test_tag_normalization(self):
        """Test that tags are normalized properly."""
        response = AnalysisResponse(
            abstract='Test abstract',
            tags=['Machine Learning', 'Deep Learning', 'NLP'],
        )

        # Tags should be normalized with # prefix and underscores
        assert response.tags == ['#machine_learning', '#deep_learning', '#nlp']


class TestResearchQuery:
    """Test suite for ResearchQuery model."""

    def test_valid_research_query(self):
        """Test creating a valid ResearchQuery."""
        query = ResearchQuery(
            name='ml_research',
            description='Machine learning research',
            research_question='What are the latest advances in ML?',
            keywords=['machine learning', 'deep learning'],
            required_topics=['machine learning'],
            preferred_topics=['neural networks'],
            excluded_topics=['hardware'],
        )

        assert query.name == 'ml_research'
        assert len(query.keywords) == 2
        assert 'machine learning' in query.required_topics

    def test_empty_lists_allowed_for_optional(self):
        """Test that empty lists are allowed for optional list fields."""
        query = ResearchQuery(
            name='basic_query',
            description='Basic query',
            research_question='Basic question?',
            keywords=['keyword'],
            required_topics=[],  # Empty allowed
            preferred_topics=[],  # Empty allowed
            excluded_topics=[],  # Empty allowed
        )

        assert len(query.required_topics) == 0
        assert len(query.preferred_topics) == 0
        assert len(query.excluded_topics) == 0


class TestCitation:
    """Test suite for Citation model."""

    def test_valid_citation(self):
        """Test creating a valid Citation."""
        citation = Citation(
            title='Referenced Paper',
            authors=['Author A', 'Author B'],
            year=2023,
            venue='Conference 2023',
            url='https://example.com/paper',
            doi='10.1234/example',
        )

        assert citation.title == 'Referenced Paper'
        assert citation.year == 2023
        assert citation.doi == '10.1234/example'

    def test_optional_fields_citation(self):
        """Test Citation with minimal required fields."""
        citation = Citation(
            title='Minimal Citation',
            authors=['Author'],
        )

        assert citation.title == 'Minimal Citation'
        assert citation.year is None
        assert citation.venue is None
        assert citation.url is None
        assert citation.doi is None


class TestScrapedArticleMetadata:
    """Test suite for ScrapedArticleMetadata model."""

    def test_valid_scraped_article(self):
        """Test creating a valid ScrapedArticleMetadata."""
        article = ScrapedArticleMetadata(
            title='Scraped Article',
            authors=['Author One', 'Author Two'],
            abstract='This is the abstract',
            journal='Test Journal',
            source='test_source',
            keywords=['keyword1', 'keyword2'],
            pdf_url='https://example.com/paper.pdf',
            doi='10.1234/example',
        )

        assert article.title == 'Scraped Article'
        assert len(article.authors) == 2
        assert article.pdf_url == 'https://example.com/paper.pdf'

    def test_minimal_scraped_article(self):
        """Test creating ScrapedArticleMetadata with minimal fields."""
        article = ScrapedArticleMetadata(
            title='Minimal Article',
            authors=['Author'],
            source='test_source',
        )

        assert article.title == 'Minimal Article'
        assert article.abstract is None
        assert article.journal is None
        assert article.keywords == []


class TestQueryEvaluationResponse:
    """Test suite for QueryEvaluationResponse model."""

    def test_valid_query_evaluation(self):
        """Test creating a valid QueryEvaluationResponse."""
        evaluation = QueryEvaluationResponse(
            relevance_score=0.85,
            meets_criteria=True,
            keyword_matches=['machine learning', 'deep learning'],
            topic_analysis='Strong match for ML topics',
            methodology_match='Uses experimental methodology as preferred',
            reasoning='Highly relevant to research interests',
            recommendation='keep',
            confidence=0.9,
        )

        assert evaluation.relevance_score == 0.85
        assert evaluation.meets_criteria is True
        assert len(evaluation.keyword_matches) == 2
        assert evaluation.recommendation == 'keep'

    def test_score_validation(self):
        """Test score validation (0-1 range)."""
        with pytest.raises(ValidationError):
            QueryEvaluationResponse(
                relevance_score=1.5,  # Invalid score > 1
                meets_criteria=True,
                topic_analysis='Test',
                reasoning='Test',
                recommendation='keep',
            )

    def test_recommendation_validation(self):
        """Test recommendation validation."""
        with pytest.raises(ValidationError):
            QueryEvaluationResponse(
                relevance_score=0.5,
                meets_criteria=True,
                topic_analysis='Test',
                reasoning='Test',
                recommendation='invalid',  # Should be 'keep', 'reject', or 'review'
            )


class TestPreDownloadEvaluationResponse:
    """Test suite for PreDownloadEvaluationResponse model."""

    def test_valid_pre_download_evaluation(self):
        """Test creating a valid PreDownloadEvaluationResponse."""
        evaluation = PreDownloadEvaluationResponse(
            relevance_score=0.85,
            should_download=True,
            keyword_matches=['machine learning', 'healthcare'],
            topic_analysis='Strong match for ML and healthcare topics',
            reasoning='Article clearly focuses on ML applications in healthcare',
            confidence=0.9,
            matching_queries=['ml_healthcare', 'clinical_ai'],
        )

        assert evaluation.relevance_score == 0.85
        assert evaluation.should_download is True
        assert len(evaluation.matching_queries) == 2

    def test_confidence_validation(self):
        """Test confidence validation (0-1 range)."""
        with pytest.raises(ValidationError):
            PreDownloadEvaluationResponse(
                relevance_score=0.5,
                should_download=True,
                topic_analysis='Test',
                reasoning='Test',
                confidence=1.5,  # Invalid confidence > 1
            )


class TestDiscoverySource:
    """Test suite for DiscoverySource model."""

    def test_valid_discovery_source(self):
        """Test creating a valid DiscoverySource."""
        schedule = ScheduleConfig(
            interval_minutes=60,
            max_articles_per_run=50,
        )

        source = DiscoverySource(
            name='arxiv_ml',
            source_type='api',
            description='ArXiv ML papers',
            is_active=True,
            schedule_config=schedule,
            api_config={'source': 'arxiv', 'categories': ['cs.LG']},
        )

        assert source.name == 'arxiv_ml'
        assert source.source_type == 'api'
        assert source.is_active is True

    def test_source_type_validation(self):
        """Test source_type validation."""
        schedule = ScheduleConfig()

        with pytest.raises(ValidationError):
            DiscoverySource(
                name='invalid',
                source_type='invalid_type',  # Should be 'api' or 'scraper'
                description='Invalid source',
                is_active=True,
                schedule_config=schedule,
            )

    def test_name_sanitization(self):
        """Test that names are sanitized to be valid filenames."""
        schedule = ScheduleConfig()

        source = DiscoverySource(
            name='Test Source!!!',
            source_type='api',
            description='Test',
            is_active=True,
            schedule_config=schedule,
        )

        # The validator should clean the name
        assert source.name == 'test_source___'


class TestDiscoveryResult:
    """Test suite for DiscoveryResult model."""

    def test_valid_discovery_result(self):
        """Test creating a valid DiscoveryResult."""
        result = DiscoveryResult(
            source_name='test_source',
            run_timestamp='2023-12-01T10:00:00',
            articles_found=100,
            articles_filtered=80,
            articles_downloaded=50,
            execution_time_seconds=10.5,
            errors=[],
        )

        assert result.source_name == 'test_source'
        assert result.articles_found == 100
        assert result.articles_downloaded == 50
        assert result.execution_time_seconds == 10.5

    def test_discovery_result_with_errors(self):
        """Test DiscoveryResult with errors."""
        result = DiscoveryResult(
            source_name='test_source',
            run_timestamp='2023-12-01T10:00:00',
            articles_found=10,
            articles_filtered=5,
            articles_downloaded=3,
            execution_time_seconds=5.0,
            errors=['Error 1', 'Error 2'],
        )

        assert len(result.errors) == 2
        assert 'Error 1' in result.errors
