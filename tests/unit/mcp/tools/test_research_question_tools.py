"""Unit tests for research question MCP tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from thoth.mcp.tools.research_question_tools import (
    CreateResearchQuestionMCPTool,
    DeleteResearchQuestionMCPTool,
    GetResearchQuestionMCPTool,
    ListAvailableSourcesMCPTool,
    ListResearchQuestionsMCPTool,
    RunDiscoveryForQuestionMCPTool,
    UpdateResearchQuestionMCPTool,
)


@pytest.fixture
def mock_service_manager():
    """Create a mock service manager."""
    manager = MagicMock()
    manager.research_question = MagicMock()
    manager.postgres = MagicMock()
    manager.discovery_orchestrator = MagicMock()
    return manager


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return MagicMock()


# ==================== ListAvailableSourcesMCPTool Tests ====================


class TestListAvailableSourcesMCPTool:
    """Tests for ListAvailableSourcesMCPTool."""

    @pytest.mark.asyncio
    async def test_list_sources_with_builtin_only(self, mock_service_manager, mock_logger):
        """Test listing sources when only built-in sources available."""
        tool = ListAvailableSourcesMCPTool(mock_service_manager)
        tool.logger = mock_logger

        # Mock repository to return empty workflows
        with patch('thoth.repositories.browser_workflow_repository.BrowserWorkflowRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.list_active.return_value = []
            mock_repo_class.return_value = mock_repo

            result = await tool.execute({})

        assert result.isError is False
        assert len(result.content) > 0
        # Check that built-in sources are listed
        content_text = ''.join([c['text'] for c in result.content])
        assert 'arxiv' in content_text
        assert 'pubmed' in content_text
        assert 'Built-in API Sources' in content_text

    @pytest.mark.asyncio
    async def test_list_sources_with_custom_workflows(self, mock_service_manager, mock_logger):
        """Test listing sources with custom browser workflows."""
        tool = ListAvailableSourcesMCPTool(mock_service_manager)
        tool.logger = mock_logger

        # Mock repository to return workflows
        with patch('thoth.repositories.browser_workflow_repository.BrowserWorkflowRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.list_active.return_value = [
                {'name': 'custom_scraper', 'description': 'Custom workflow'},
            ]
            mock_repo_class.return_value = mock_repo

            result = await tool.execute({})

        assert result.isError is False
        content_text = ''.join([c['text'] for c in result.content])
        assert 'Custom Sources' in content_text
        assert 'custom_scraper' in content_text


# ==================== CreateResearchQuestionMCPTool Tests ====================


class TestCreateResearchQuestionMCPTool:
    """Tests for CreateResearchQuestionMCPTool."""

    @pytest.mark.asyncio
    async def test_create_question_success(self, mock_service_manager, mock_logger):
        """Test successful research question creation."""
        tool = CreateResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        mock_service_manager.research_question.create_research_question = AsyncMock(
            return_value=question_id
        )

        arguments = {
            'name': 'Test Question',
            'keywords': ['ai', 'memory'],
            'selected_sources': ['arxiv', 'pubmed'],
        }

        result = await tool.execute(arguments)

        assert result.isError is False
        content_text = result.content[0]['text']
        assert 'successfully' in content_text.lower()
        assert str(question_id) in content_text
        assert 'Test Question' in content_text

    @pytest.mark.asyncio
    async def test_create_question_missing_required_field(self, mock_service_manager, mock_logger):
        """Test creation with missing required field."""
        tool = CreateResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        # Missing 'keywords'
        arguments = {
            'name': 'Test Question',
            'selected_sources': ['arxiv'],
        }

        # Should fail due to missing required field
        mock_service_manager.research_question.create_research_question = AsyncMock(
            side_effect=ValueError("Missing required field: keywords")
        )

        result = await tool.execute(arguments)

        assert result.isError is True
        # Check for error (KeyError in this case)
        assert 'Error' in result.content[0]['text'] or 'error' in result.content[0]['text'].lower()

    @pytest.mark.asyncio
    async def test_create_question_with_all_optional_fields(self, mock_service_manager, mock_logger):
        """Test creation with all optional fields."""
        tool = CreateResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        mock_service_manager.research_question.create_research_question = AsyncMock(
            return_value=question_id
        )

        arguments = {
            'name': 'Comprehensive Question',
            'keywords': ['ai', 'memory', 'agents'],
            'topics': ['cs.AI', 'cs.LG'],
            'authors': ['Smith', 'Jones'],
            'selected_sources': ['arxiv', 'semantic_scholar'],
            'schedule_frequency': 'weekly',
            'schedule_time': '09:00',
            'min_relevance_score': 0.8,
            'max_articles_per_run': 100,
            'auto_download_pdfs': False,
        }

        result = await tool.execute(arguments)

        assert result.isError is False
        # Verify all parameters were passed to service
        mock_service_manager.research_question.create_research_question.assert_called_once()


# ==================== ListResearchQuestionsMCPTool Tests ====================


class TestListResearchQuestionsMCPTool:
    """Tests for ListResearchQuestionsMCPTool."""

    @pytest.mark.asyncio
    async def test_list_questions_empty(self, mock_service_manager, mock_logger):
        """Test listing when no questions exist."""
        tool = ListResearchQuestionsMCPTool(mock_service_manager)
        tool.logger = mock_logger

        mock_service_manager.research_question.get_user_questions = AsyncMock(
            return_value=[]
        )

        result = await tool.execute({'user_id': 'test_user'})

        assert result.isError is False
        content_text = result.content[0]['text']
        assert 'No research questions found' in content_text

    @pytest.mark.asyncio
    async def test_list_questions_with_data(self, mock_service_manager, mock_logger):
        """Test listing with multiple questions."""
        tool = ListResearchQuestionsMCPTool(mock_service_manager)
        tool.logger = mock_logger

        questions = [
            {
                'id': uuid4(),
                'name': 'AI Memory',
                'keywords': ['ai', 'memory'],
                'topics': ['cs.AI'],
                'selected_sources': ['arxiv'],
                'schedule_frequency': 'daily',
                'created_at': '2026-01-10',
            },
            {
                'id': uuid4(),
                'name': 'Quantum Computing',
                'keywords': ['quantum'],
                'topics': [],
                'selected_sources': ['arxiv', 'pubmed'],
                'schedule_frequency': 'weekly',
                'created_at': '2026-01-09',
            },
        ]

        mock_service_manager.research_question.get_user_questions = AsyncMock(
            return_value=questions
        )

        result = await tool.execute({'user_id': 'test_user'})

        assert result.isError is False
        assert len(result.content) > 1  # Header + questions
        content_text = ''.join([c['text'] for c in result.content])
        assert 'AI Memory' in content_text
        assert 'Quantum Computing' in content_text


# ==================== GetResearchQuestionMCPTool Tests ====================


class TestGetResearchQuestionMCPTool:
    """Tests for GetResearchQuestionMCPTool."""

    @pytest.mark.asyncio
    async def test_get_question_success(self, mock_service_manager, mock_logger):
        """Test getting a specific question."""
        tool = GetResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        question = {
            'id': question_id,
            'user_id': 'test_user',
            'name': 'Test Question',
            'keywords': ['ai'],
            'topics': ['cs.AI'],
            'authors': [],
            'selected_sources': ['arxiv'],
            'schedule_frequency': 'daily',
            'min_relevance_score': 0.7,
            'created_at': '2026-01-10',
        }

        with patch('thoth.repositories.research_question_repository.ResearchQuestionRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_id.return_value = question
            mock_repo_class.return_value = mock_repo

            result = await tool.execute({
                'question_id': str(question_id),
                'user_id': 'test_user',
            })

        assert result.isError is False
        content_text = result.content[0]['text']
        assert 'Test Question' in content_text
        assert str(question_id) in content_text

    @pytest.mark.asyncio
    async def test_get_question_not_found(self, mock_service_manager, mock_logger):
        """Test getting non-existent question."""
        tool = GetResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()

        with patch('thoth.repositories.research_question_repository.ResearchQuestionRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_id.return_value = None
            mock_repo_class.return_value = mock_repo

            result = await tool.execute({
                'question_id': str(question_id),
                'user_id': 'test_user',
            })

        assert result.isError is True
        assert 'not found' in result.content[0]['text']

    @pytest.mark.asyncio
    async def test_get_question_wrong_user(self, mock_service_manager, mock_logger):
        """Test getting question with wrong user ID."""
        tool = GetResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        question = {
            'id': question_id,
            'user_id': 'other_user',
            'name': 'Test Question',
        }

        with patch('thoth.repositories.research_question_repository.ResearchQuestionRepository') as mock_repo_class:
            mock_repo = AsyncMock()
            mock_repo.get_by_id.return_value = question
            mock_repo_class.return_value = mock_repo

            result = await tool.execute({
                'question_id': str(question_id),
                'user_id': 'test_user',
            })

        assert result.isError is True
        assert 'does not have access' in result.content[0]['text']


# ==================== UpdateResearchQuestionMCPTool Tests ====================


class TestUpdateResearchQuestionMCPTool:
    """Tests for UpdateResearchQuestionMCPTool."""

    @pytest.mark.asyncio
    async def test_update_question_success(self, mock_service_manager, mock_logger):
        """Test successful update."""
        tool = UpdateResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        mock_service_manager.research_question.update_research_question = AsyncMock(
            return_value=True
        )

        result = await tool.execute({
            'question_id': str(question_id),
            'keywords': ['new', 'keywords'],
            'min_relevance_score': 0.8,
        })

        assert result.isError is False
        assert 'Successfully updated' in result.content[0]['text']

    @pytest.mark.asyncio
    async def test_update_question_no_fields(self, mock_service_manager, mock_logger):
        """Test update with no fields provided."""
        tool = UpdateResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()

        result = await tool.execute({
            'question_id': str(question_id),
        })

        assert result.isError is True
        assert 'No updates provided' in result.content[0]['text']


# ==================== DeleteResearchQuestionMCPTool Tests ====================


class TestDeleteResearchQuestionMCPTool:
    """Tests for DeleteResearchQuestionMCPTool."""

    @pytest.mark.asyncio
    async def test_delete_question_soft(self, mock_service_manager, mock_logger):
        """Test soft delete (default)."""
        tool = DeleteResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        mock_service_manager.research_question.delete_research_question = AsyncMock(
            return_value=True
        )

        result = await tool.execute({
            'question_id': str(question_id),
        })

        assert result.isError is False
        assert 'deactivated' in result.content[0]['text']

    @pytest.mark.asyncio
    async def test_delete_question_hard(self, mock_service_manager, mock_logger):
        """Test hard delete."""
        tool = DeleteResearchQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        mock_service_manager.research_question.delete_research_question = AsyncMock(
            return_value=True
        )

        result = await tool.execute({
            'question_id': str(question_id),
            'hard_delete': True,
        })

        assert result.isError is False
        assert 'deleted' in result.content[0]['text']


# ==================== RunDiscoveryForQuestionMCPTool Tests ====================


class TestRunDiscoveryForQuestionMCPTool:
    """Tests for RunDiscoveryForQuestionMCPTool."""

    @pytest.mark.asyncio
    async def test_run_discovery_success(self, mock_service_manager, mock_logger):
        """Test successful discovery execution."""
        tool = RunDiscoveryForQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        mock_service_manager.discovery_orchestrator.run_discovery_for_question = AsyncMock(
            return_value={
                'success': True,
                'articles_found': 25,
                'articles_downloaded': 20,
                'sources_used': ['arxiv', 'pubmed'],
            }
        )

        result = await tool.execute({
            'question_id': str(question_id),
        })

        assert result.isError is False
        content_text = result.content[0]['text']
        assert 'completed' in content_text.lower()
        assert '25' in content_text
        assert '20' in content_text

    @pytest.mark.asyncio
    async def test_run_discovery_orchestrator_unavailable(self, mock_service_manager, mock_logger):
        """Test when discovery orchestrator is not available."""
        tool = RunDiscoveryForQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        mock_service_manager.discovery_orchestrator = None
        question_id = uuid4()

        result = await tool.execute({
            'question_id': str(question_id),
        })

        assert result.isError is True
        assert 'not available' in result.content[0]['text']

    @pytest.mark.asyncio
    async def test_run_discovery_failure(self, mock_service_manager, mock_logger):
        """Test discovery execution failure."""
        tool = RunDiscoveryForQuestionMCPTool(mock_service_manager)
        tool.logger = mock_logger

        question_id = uuid4()
        mock_service_manager.discovery_orchestrator.run_discovery_for_question = AsyncMock(
            return_value={
                'success': False,
                'error': 'Database connection failed',
            }
        )

        result = await tool.execute({
            'question_id': str(question_id),
        })

        assert result.isError is True
        assert 'failed' in result.content[0]['text'].lower()
