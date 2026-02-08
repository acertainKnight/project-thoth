"""Tests for tools router endpoints."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from thoth.server.dependencies import get_research_agent, get_service_manager
from thoth.server.routers import tools


@pytest.fixture
def mock_research_agent():
    """Create mock research agent."""
    agent = Mock()
    agent.chat = AsyncMock()
    agent.get_available_tools = Mock(
        return_value=[
            {'name': 'thoth_search_papers', 'description': 'Search papers'},
            {'name': 'thoth_analyze_document', 'description': 'Analyze documents'},
        ]
    )
    return agent


@pytest.fixture
def mock_service_manager():
    """Create mock service manager."""
    manager = Mock()
    manager.discovery_service = Mock()
    manager.processing_service = Mock()
    manager.rag_service = Mock()
    manager.pdf_locator_service = Mock()
    manager.note_service = Mock()
    manager.discovery = Mock()
    return manager


@pytest.fixture
def test_client(mock_research_agent, mock_service_manager):
    """Create FastAPI test client with tools router and dependency overrides."""
    app = FastAPI()
    app.include_router(tools.router)

    # Override dependencies to return mocks
    app.dependency_overrides[get_research_agent] = lambda: mock_research_agent
    app.dependency_overrides[get_service_manager] = lambda: mock_service_manager

    client = TestClient(app)
    yield client

    # Clean up
    app.dependency_overrides.clear()


class TestExecuteToolEndpoint:
    """Tests for POST /execute endpoint."""

    def test_execute_tool_without_agent(self, mock_service_manager):
        """Test tool execution fails when research agent not initialized."""
        # Create app with None agent override
        app = FastAPI()
        app.include_router(tools.router)
        app.dependency_overrides[get_research_agent] = lambda: None
        app.dependency_overrides[get_service_manager] = lambda: mock_service_manager

        with TestClient(app) as client:
            request_data = {
                'tool_name': 'thoth_search_papers',
                'parameters': {'query': 'test'},
            }
            response = client.post('/execute', json=request_data)

            assert response.status_code == 503
            assert 'Research agent not initialized' in response.json()['detail']

    def test_execute_tool_through_agent(self, test_client, mock_research_agent):
        """Test tool execution through agent."""
        mock_research_agent.chat.return_value = {
            'response': 'Tool executed',
            'tool_calls': [{'tool': 'thoth_search_papers'}],
        }

        request_data = {
            'tool_name': 'thoth_search_papers',
            'parameters': {'query': 'machine learning'},
            'bypass_agent': False,
        }
        response = test_client.post('/execute', json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data['tool'] == 'thoth_search_papers'
        assert data['bypassed_agent'] is False
        assert 'response' in data

    def test_execute_tool_bypassing_agent_tool_not_found(
        self, test_client, mock_research_agent
    ):
        """Test bypassing agent with non-existent tool returns error."""

        request_data = {
            'tool_name': 'nonexistent_tool',
            'parameters': {},
            'bypass_agent': True,
        }
        response = test_client.post('/execute', json=request_data)

        # Returns 500 because HTTPException is caught by outer handler
        assert response.status_code == 500
        assert 'failed' in response.json()['detail'].lower()

    def test_execute_tool_bypassing_agent_success(
        self, test_client, mock_research_agent, mock_service_manager
    ):
        """Test bypassing agent with valid tool."""

        # Mock the tool to exist
        mock_research_agent.get_available_tools.return_value = [
            {'name': 'thoth_search_papers'}
        ]

        request_data = {
            'tool_name': 'thoth_search_papers',
            'parameters': {'query': 'test'},
            'bypass_agent': True,
        }
        response = test_client.post('/execute', json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data['tool'] == 'thoth_search_papers'
        assert data['bypassed_agent'] is True


class TestExecuteCommandEndpoint:
    """Tests for POST /execute/command endpoint."""

    def test_execute_command_without_service_manager(self, mock_research_agent):
        """Test command execution fails gracefully with missing services."""
        # When service_manager is None, command handlers fail
        app = FastAPI()
        app.include_router(tools.router)
        app.dependency_overrides[get_research_agent] = lambda: mock_research_agent
        app.dependency_overrides[get_service_manager] = lambda: None

        with TestClient(app) as client:
            request_data = {'command': 'discovery', 'args': ['list']}
            response = client.post('/execute/command', json=request_data)

            # Expects 500 because command handler fails with None service_manager
            assert response.status_code == 500
            assert 'Command execution failed' in response.json()['detail']

    def test_execute_discovery_list_command(self, test_client, mock_service_manager):
        """Test executing discovery list command."""
        mock_service_manager.discovery.list_sources = AsyncMock(
            return_value=['arxiv', 'semantic_scholar']
        )

        request_data = {'command': 'discovery', 'args': ['list']}
        response = test_client.post('/execute/command', json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data['command'] == 'discovery'
        assert 'result' in data

    def test_execute_command_with_streaming(self, test_client, mock_service_manager):
        """Test executing command with streaming enabled."""

        request_data = {'command': 'discovery', 'args': ['list'], 'streaming': True}
        response = test_client.post('/execute/command', json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data['streaming'] is True

    def test_execute_unknown_command(self, test_client, mock_service_manager):
        """Test executing unknown command returns error."""

        request_data = {'command': 'unknown_command', 'args': []}
        response = test_client.post('/execute/command', json=request_data)

        assert response.status_code == 500
        assert 'failed' in response.json()['detail'].lower()


class TestToolExecutionHelpers:
    """Tests for tool execution helper functions."""

    @pytest.mark.asyncio
    async def test_execute_search_papers_tool(self, mock_service_manager):
        """Test search papers tool execution."""
        mock_service_manager.discovery.search_papers = AsyncMock(
            return_value=[{'title': 'Paper 1'}]
        )

        result = await tools.execute_search_papers_tool(
            {'query': 'machine learning', 'max_results': 10}, mock_service_manager
        )

        assert result.tool == 'thoth_search_papers'
        assert result.query == 'machine learning'
        assert result.status == 'success'

    @pytest.mark.asyncio
    async def test_execute_download_pdf_tool(self, mock_service_manager):
        """Test download PDF tool execution."""
        with pytest.raises(ValueError, match='URL parameter is required'):
            await tools.execute_download_pdf_tool({}, mock_service_manager)

    @pytest.mark.asyncio
    async def test_execute_rag_search_tool(self, mock_service_manager):
        """Test RAG search tool execution."""
        mock_service_manager.rag.search = AsyncMock(
            return_value=[{'content': 'Result 1'}]
        )

        result = await tools.execute_rag_search_tool(
            {'query': 'test query', 'top_k': 5}, mock_service_manager
        )

        assert result.tool == 'thoth_rag_search'
        assert result.query == 'test query'
        assert result.status == 'success'

    @pytest.mark.asyncio
    async def test_execute_tool_directly_unknown_tool(self, mock_service_manager):
        """Test executing unknown tool directly returns placeholder."""
        result = await tools.execute_tool_directly(
            'unknown_tool', {}, mock_service_manager
        )

        assert result.status == 'not_implemented'
        assert 'not implemented' in result.result['message'].lower()


class TestCommandHandlers:
    """Tests for command handler functions."""

    @pytest.mark.asyncio
    async def test_execute_discovery_command_list(self, mock_service_manager):
        """Test discovery list command."""
        mock_service_manager.discovery.list_sources = AsyncMock(
            return_value=['source1', 'source2']
        )

        result = await tools.execute_discovery_command(
            ['list'], {}, mock_service_manager
        )

        assert result.action == 'list'
        assert result.sources is not None

    @pytest.mark.asyncio
    async def test_execute_pdf_locate_command(self, mock_service_manager):
        """Test PDF locate command."""
        mock_service_manager.pdf_locator.locate = AsyncMock(
            return_value=['url1', 'url2']
        )

        result = await tools.execute_pdf_locate_command(
            ['10.1234/test'], {}, mock_service_manager
        )

        assert result.identifier == '10.1234/test'
        assert result.found is True

    @pytest.mark.asyncio
    async def test_execute_rag_command_search(self, mock_service_manager):
        """Test RAG search command."""
        mock_service_manager.rag.search = AsyncMock(return_value=[{'result': 'data'}])

        result = await tools.execute_rag_command(
            ['search', 'test', 'query'], {}, mock_service_manager
        )

        assert result.action == 'search'
        assert result.query == 'test query'

    @pytest.mark.asyncio
    async def test_execute_notes_command_list(self, mock_service_manager):
        """Test notes list command."""
        mock_service_manager.note.list_notes = AsyncMock(
            return_value=['note1', 'note2']
        )

        result = await tools.execute_notes_command(['list'], {}, mock_service_manager)

        assert result.action == 'list'
        assert result.notes is not None
