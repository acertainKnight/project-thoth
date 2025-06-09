"""
Tests for agent tools.

Tests the various agent tool implementations.
"""

from unittest.mock import MagicMock, patch

import pytest

from thoth.ingestion.agent_v2.tools.analysis_tools import (
    AnalyzeTopicTool,
    ArticleAnalysisTool,
    EvaluateArticleTool,
    FindRelatedTool,
)
from thoth.ingestion.agent_v2.tools.discovery_tools import (
    CreateArxivSourceTool,
    CreatePubmedSourceTool,
    ListDiscoverySourcesTool,
    RunDiscoveryTool,
)
from thoth.ingestion.agent_v2.tools.query_tools import (
    CreateQueryTool,
    GetQueryTool,
    ListQueriesTool,
)
from thoth.ingestion.agent_v2.tools.rag_tools import (
    AskQuestionTool,
    IndexKnowledgeBaseTool,
    SearchKnowledgeTool,
)
from thoth.services.service_manager import ServiceManager
from thoth.utilities.schemas import DiscoverySource, Recommendation, ScheduleConfig


class TestQueryTools:
    """Test suite for query management tools."""

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service_manager with a mocked query service."""
        service_manager = MagicMock(spec=ServiceManager)
        service_manager.query = MagicMock()
        return service_manager

    def test_create_query_tool(self, mock_service_manager):
        """Test CreateQueryTool."""
        tool = CreateQueryTool(service_manager=mock_service_manager)

        # Mock service_manager response to return success without creating ResearchQuery
        mock_service_manager.query.create_query.return_value = True

        # Mock ResearchQuery to avoid validation error
        with patch('thoth.ingestion.agent_v2.tools.query_tools.ResearchQuery'):
            # Test tool execution
            result = tool._run(
                name='test_query',
                description='Test query description',
                research_question='What are the latest developments in machine learning?',
                keywords=['machine learning', 'AI'],
            )

            assert 'Successfully created' in result
            assert 'test_query' in result

    def test_list_queries_tool(self, mock_service_manager):
        """Test ListQueriesTool."""
        tool = ListQueriesTool(service_manager=mock_service_manager)

        # Create a mock query without tags
        mock_query = MagicMock()
        mock_query.name = 'test_query'
        mock_query.description = 'Test description'
        mock_query.created_at = '2023-01-01'
        mock_query.keywords = ['ml', 'ai']
        mock_query.tags = None  # Avoid the attribute error

        # Mock service_manager response
        mock_service_manager.query.get_all_queries.return_value = [mock_query]

        # Test tool execution
        result = tool._run()

        assert 'test_query' in result
        assert 'Test description' in result

    def test_get_query_tool(self, mock_service_manager):
        """Test GetQueryTool."""
        tool = GetQueryTool(service_manager=mock_service_manager)

        # Create a mock query
        mock_query = MagicMock()
        mock_query.name = 'test_query'
        mock_query.description = 'Test description'
        mock_query.research_question = 'Test research question'
        mock_query.created_at = '2023-01-01'
        mock_query.keywords = ['ml', 'ai']
        mock_query.required_topics = ['machine learning']
        mock_query.preferred_topics = ['deep learning']
        mock_query.excluded_topics = ['hardware']

        # Mock service_manager response
        mock_service_manager.query.get_query.return_value = mock_query

        # Test tool execution
        result = tool._run(query_name='test_query')

        assert 'test_query' in result
        assert 'Test research question' in result


class TestDiscoveryTools:
    """Test suite for discovery tools."""

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service_manager with a mocked discovery service."""
        service_manager = MagicMock(spec=ServiceManager)
        service_manager.discovery = MagicMock()
        return service_manager

    @pytest.fixture
    def sample_discovery_source(self):
        """Create a sample discovery source."""
        return DiscoverySource(
            name='arxiv_ml',
            source_type='api',
            description='ArXiv ML papers',
            is_active=True,
            schedule_config=ScheduleConfig(
                interval_minutes=60,
                max_articles_per_run=50,
            ),
        )

    def test_list_discovery_sources_tool(
        self, mock_service_manager, sample_discovery_source
    ):
        """Test ListDiscoverySourcesTool."""
        tool = ListDiscoverySourcesTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.discovery.list_sources.return_value = [
            sample_discovery_source
        ]

        # Test tool execution
        result = tool._run()

        assert sample_discovery_source.name in result
        assert sample_discovery_source.description in result

    def test_create_discovery_source_tool(self, mock_service_manager):
        """Test CreateArxivSourceTool."""
        tool = CreateArxivSourceTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.discovery.create_source.return_value = True

        # Test tool execution
        result = tool._run(
            name='test_source',
            keywords=['machine learning', 'AI'],
            categories=['cs.LG', 'cs.AI'],
            max_articles=50,
            schedule_hours=24,
        )

        assert 'Successfully' in result or 'Created' in result
        assert 'test_source' in result

    def test_create_pubmed_source_tool(self, mock_service_manager):
        """Test CreatePubmedSourceTool."""
        tool = CreatePubmedSourceTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.discovery.create_source.return_value = True

        # Test tool execution
        result = tool._run(
            name='pubmed_test',
            keywords=['cancer', 'treatment'],
            max_articles=20,
            schedule_hours=48,
        )

        assert 'Successfully' in result or 'Created' in result
        assert 'pubmed_test' in result

    def test_run_discovery_tool(self, mock_service_manager):
        """Test RunDiscoveryTool."""
        tool = RunDiscoveryTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.discovery.run_discovery.return_value = MagicMock(
            articles_found=10,
            articles_filtered=8,
            articles_downloaded=5,
            execution_time_seconds=2.5,
            errors=[],
        )

        # Test tool execution
        result = tool._run(source_name='test_source', max_articles=10)

        assert '10' in result
        assert '5' in result


class TestRAGTools:
    """Test suite for RAG tools."""

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service_manager with a mocked RAG service."""
        service_manager = MagicMock(spec=ServiceManager)
        service_manager.rag = MagicMock()
        return service_manager

    def test_search_knowledge_tool(self, mock_service_manager):
        """Test SearchKnowledgeTool."""
        tool = SearchKnowledgeTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.rag.search.return_value = [
            {
                'title': 'Test Paper',
                'content': 'Test content',
                'score': 0.9,
            }
        ]

        # Test tool execution
        result = tool._run(query='test query', k=5)

        assert 'Test Paper' in result
        assert '0.9' in result

    def test_ask_question_tool(self, mock_service_manager):
        """Test AskQuestionTool."""
        tool = AskQuestionTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.rag.ask_question.return_value = {
            'question': 'What is ML?',
            'answer': 'Machine learning is...',
            'sources': [
                {'metadata': {'title': 'ML Paper', 'document_type': 'article'}}
            ],
        }

        # Test tool execution
        result = tool._run(query='What is ML?', k=4)

        assert 'Machine learning is' in result
        assert 'ML Paper' in result

    def test_index_knowledge_base_tool(self, mock_service_manager):
        """Test IndexKnowledgeBaseTool."""
        tool = IndexKnowledgeBaseTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.rag.index_knowledge_base.return_value = {
            'total_files': 100,
            'total_chunks': 500,
            'notes_indexed': 50,
            'articles_indexed': 50,
            'errors': [],
        }

        # Test tool execution
        result = tool._run()

        assert '100' in result
        assert '500' in result


class TestAnalysisTools:
    """Test suite for analysis tools."""

    @pytest.fixture
    def mock_service_manager(self):
        """Create a mock service_manager with mocked analysis-related services."""
        service_manager = MagicMock(spec=ServiceManager)
        service_manager.rag = MagicMock()
        service_manager.query = MagicMock()
        service_manager.article = MagicMock()
        return service_manager

    def test_analyze_topic_tool(self, mock_service_manager):
        """Test AnalyzeTopicTool."""
        tool = AnalyzeTopicTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.rag.search.return_value = [
            {
                'title': 'Machine Learning Paper 1',
                'content': 'Content about ML...',
                'score': 0.9,
            }
        ]
        mock_service_manager.rag.ask_question.return_value = {
            'question': 'What are the key findings in Machine Learning research?',
            'answer': 'Overview of ML research...',
            'sources': [],
        }

        # Test tool execution
        result = tool._run(topic='Machine Learning', depth='medium')

        assert 'Machine Learning' in result
        assert 'Overview of ML research' in result

    def test_article_analysis_tool(self, mock_service_manager):
        """Test ArticleAnalysisTool."""
        with patch('thoth.ingestion.agent_v2.tools.analysis_tools.OpenAI'):
            tool = ArticleAnalysisTool(service_manager=mock_service_manager)

            # Test tool execution (note: this tool has a simple implementation)
            result = tool._run(
                article_title='Test Paper',
                article_abstract='Test abstract about research findings',
            )

            # Basic validation since this is a placeholder implementation
            assert 'Test Paper' in result
            assert 'relevant' in result.lower() or 'research' in result.lower()

    def test_evaluate_article_tool(self, mock_service_manager):
        """Test EvaluateArticleTool."""
        tool = EvaluateArticleTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.article.evaluate_against_query.return_value = MagicMock(
            relevance_score=8.5,
            recommendation=Recommendation.KEEP,
            reasoning='Good article',
        )
        mock_service_manager.rag.search.return_value = [
            {
                'title': 'Test Paper',
                'abstract': 'Test abstract',
                'content': 'some content',
            }
        ]

        # Test tool execution
        result = tool._run(article_title='Test Paper', query_name='test_query')

        assert '8.5' in result
        assert 'KEEP' in result

    def test_find_related_tool(self, mock_service_manager):
        """Test FindRelatedTool."""
        tool = FindRelatedTool(service_manager=mock_service_manager)

        # Mock service_manager response
        mock_service_manager.rag.search.side_effect = [
            # First call for target paper
            [
                {
                    'title': 'Test Paper',
                    'content': 'Test content about deep learning',
                    'score': 0.95,
                }
            ],
            # Second call for related papers
            [
                {
                    'title': 'Test Paper',
                    'content': 'Test content about deep learning',
                    'score': 0.95,
                },
                {
                    'title': 'Related Paper 1',
                    'content': 'Related content 1',
                    'score': 0.85,
                },
                {
                    'title': 'Related Paper 2',
                    'content': 'Related content 2',
                    'score': 0.80,
                },
            ],
        ]

        # Test tool execution
        result = tool._run(paper_title='Test Paper', max_results=2)

        assert 'Related Paper 1' in result
        assert 'Related Paper 2' in result
