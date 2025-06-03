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
from thoth.utilities.models import DiscoverySource, ScheduleConfig


class TestQueryTools:
    """Test suite for query management tools."""

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter."""
        adapter = MagicMock()
        return adapter

    def test_create_query_tool(self, mock_adapter):
        """Test CreateQueryTool."""
        tool = CreateQueryTool(adapter=mock_adapter)

        # Mock adapter response to return success without creating ResearchQuery
        mock_adapter.create_query.return_value = True

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

    def test_list_queries_tool(self, mock_adapter):
        """Test ListQueriesTool."""
        tool = ListQueriesTool(adapter=mock_adapter)

        # Create a mock query without tags
        mock_query = MagicMock()
        mock_query.name = 'test_query'
        mock_query.description = 'Test description'
        mock_query.created_at = '2023-01-01'
        mock_query.keywords = ['ml', 'ai']
        mock_query.tags = None  # Avoid the attribute error

        # Mock adapter response
        mock_adapter.list_queries.return_value = [mock_query]

        # Test tool execution
        result = tool._run()

        assert 'test_query' in result
        assert 'Test description' in result

    def test_get_query_tool(self, mock_adapter):
        """Test GetQueryTool."""
        tool = GetQueryTool(adapter=mock_adapter)

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

        # Mock adapter response
        mock_adapter.get_query.return_value = mock_query

        # Test tool execution
        result = tool._run(query_name='test_query')

        assert 'test_query' in result
        assert 'Test research question' in result


class TestDiscoveryTools:
    """Test suite for discovery tools."""

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter."""
        adapter = MagicMock()
        return adapter

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

    def test_list_discovery_sources_tool(self, mock_adapter, sample_discovery_source):
        """Test ListDiscoverySourcesTool."""
        tool = ListDiscoverySourcesTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.list_discovery_sources.return_value = [sample_discovery_source]

        # Test tool execution
        result = tool._run()

        assert sample_discovery_source.name in result
        assert sample_discovery_source.description in result

    def test_create_discovery_source_tool(self, mock_adapter):
        """Test CreateArxivSourceTool."""
        tool = CreateArxivSourceTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.create_discovery_source.return_value = True

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

    def test_create_pubmed_source_tool(self, mock_adapter):
        """Test CreatePubmedSourceTool."""
        tool = CreatePubmedSourceTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.create_discovery_source.return_value = True

        # Test tool execution
        result = tool._run(
            name='pubmed_test',
            keywords=['cancer', 'treatment'],
            max_articles=20,
            schedule_hours=48,
        )

        assert 'Successfully' in result or 'Created' in result
        assert 'pubmed_test' in result

    def test_run_discovery_tool(self, mock_adapter):
        """Test RunDiscoveryTool."""
        tool = RunDiscoveryTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.run_discovery.return_value = {
            'success': True,
            'articles_found': 10,
            'articles_filtered': 8,
            'articles_downloaded': 5,
            'execution_time': 2.5,
            'errors': [],
        }

        # Test tool execution
        result = tool._run(source_name='test_source', max_articles=10)

        assert '10' in result
        assert '5' in result


class TestRAGTools:
    """Test suite for RAG tools."""

    @pytest.fixture
    def mock_adapter(self):
        """Create a mock adapter."""
        adapter = MagicMock()
        return adapter

    def test_search_knowledge_tool(self, mock_adapter):
        """Test SearchKnowledgeTool."""
        tool = SearchKnowledgeTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.search_knowledge.return_value = [
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

    def test_ask_question_tool(self, mock_adapter):
        """Test AskQuestionTool."""
        tool = AskQuestionTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.ask_knowledge_base.return_value = {
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

    def test_index_knowledge_base_tool(self, mock_adapter):
        """Test IndexKnowledgeBaseTool."""
        tool = IndexKnowledgeBaseTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.index_knowledge_base.return_value = {
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
    def mock_adapter(self):
        """Create a mock adapter."""
        adapter = MagicMock()
        return adapter

    def test_analyze_topic_tool(self, mock_adapter):
        """Test AnalyzeTopicTool."""
        tool = AnalyzeTopicTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.search_knowledge.return_value = [
            {
                'title': 'Machine Learning Paper 1',
                'content': 'Content about ML...',
                'score': 0.9,
            }
        ]
        mock_adapter.ask_knowledge.return_value = {
            'question': 'What are the key findings in Machine Learning research?',
            'answer': 'Overview of ML research...',
            'sources': [],
        }

        # Test tool execution
        result = tool._run(topic='Machine Learning', depth='medium')

        assert 'Machine Learning' in result
        assert 'Overview of ML research' in result

    def test_article_analysis_tool(self, mock_adapter):
        """Test ArticleAnalysisTool."""
        with patch('thoth.ingestion.agent_v2.tools.analysis_tools.OpenAI'):
            tool = ArticleAnalysisTool(adapter=mock_adapter)

            # Test tool execution (note: this tool has a simple implementation)
            result = tool._run(
                article_title='Test Paper',
                article_abstract='Test abstract about research findings',
            )

            # Basic validation since this is a placeholder implementation
            assert 'Test Paper' in result
            assert 'relevant' in result.lower() or 'research' in result.lower()

    def test_evaluate_article_tool(self, mock_adapter):
        """Test EvaluateArticleTool."""
        tool = EvaluateArticleTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.get_query.return_value = MagicMock(name='test_query')
        mock_adapter.search_knowledge.return_value = [
            {
                'title': 'Test Paper',
                'content': 'Test content',
                'score': 0.9,
            }
        ]
        mock_adapter.evaluate_article.return_value = MagicMock(
            relevance_score=8.5,
            recommendation=MagicMock(value='keep'),
            reasoning='Good article',
            matching_keywords=['test'],
            suggested_queries=[],
        )

        # Test tool execution
        result = tool._run(article_title='Test Paper', query_name='test_query')

        assert '8.5' in result
        assert 'KEEP' in result

    def test_find_related_tool(self, mock_adapter):
        """Test FindRelatedTool."""
        tool = FindRelatedTool(adapter=mock_adapter)

        # Mock adapter response
        mock_adapter.search_knowledge.side_effect = [
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
