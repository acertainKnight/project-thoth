"""Tests for research router endpoints."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from thoth.auth.dependencies import get_user_context
from thoth.server.dependencies import get_research_agent
from thoth.server.routers import research


@pytest.fixture
def mock_research_agent():
    """Create mock research agent with async chat method."""
    agent = Mock()

    # Set up async mock that returns a proper response
    async def default_chat_response(*_args, **_kwargs):
        return {'response': 'Here is the answer', 'tool_calls': []}

    agent.chat = AsyncMock(side_effect=default_chat_response)
    return agent


@pytest.fixture
def mock_llm_router():
    """Create mock LLM router."""
    router = Mock()
    router.select_model = Mock(return_value='gpt-4')
    return router


@pytest.fixture
def test_client(mock_research_agent, mock_user_context):
    """Create FastAPI test client with research router and dependency overrides."""
    app = FastAPI()
    app.include_router(research.router)

    app.dependency_overrides[get_research_agent] = lambda: mock_research_agent
    app.dependency_overrides[get_user_context] = lambda: mock_user_context

    client = TestClient(app)
    yield client

    app.dependency_overrides.clear()


class TestResearchChatEndpoint:
    """Tests for POST /chat endpoint."""

    def test_research_chat_without_agent(self, mock_user_context):
        """Test chat fails when research agent not initialized."""
        app = FastAPI()
        app.include_router(research.router)
        app.dependency_overrides[get_research_agent] = lambda: None
        app.dependency_overrides[get_user_context] = lambda: mock_user_context

        with TestClient(app) as client:
            request_data = {'message': 'Hello'}
            response = client.post('/chat', json=request_data)

            assert response.status_code == 503
            assert 'Research agent not initialized' in response.json()['detail']

    def test_research_chat_success(
        self,
        test_client,
        mock_research_agent,  # noqa: ARG002
        mock_llm_router,
    ):
        """Test chat returns response from research agent."""
        # Mock already set up in fixture with default response
        with patch(
            'thoth.server.routers.research.LLMRouter', return_value=mock_llm_router
        ):
            request_data = {'message': 'What is machine learning?'}
            response = test_client.post('/chat', json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert 'response' in data
            assert data['response'] == 'Here is the answer'
            assert 'tool_calls' in data

    def test_research_chat_with_conversation_id(
        self,
        test_client,
        mock_research_agent,  # noqa: ARG002
        mock_llm_router,
    ):
        """Test chat accepts a conversation_id field."""
        with patch(
            'thoth.server.routers.research.LLMRouter', return_value=mock_llm_router
        ):
            request_data = {
                'message': 'What is machine learning?',
                'conversation_id': 'conv-123',
            }
            response = test_client.post('/chat', json=request_data)

            assert response.status_code == 200
            data = response.json()
            assert 'response' in data

    def test_research_chat_handles_errors_gracefully(
        self, test_client, mock_research_agent, mock_llm_router
    ):
        """Test chat handles errors and returns error response."""
        # Setup mock to raise exception
        mock_research_agent.chat.side_effect = Exception('Agent error')

        with patch(
            'thoth.server.routers.research.LLMRouter', return_value=mock_llm_router
        ):
            request_data = {'message': 'Test'}
            response = test_client.post('/chat', json=request_data)

            assert response.status_code == 200  # Returns 200 with error in body
            data = response.json()
            assert 'error' in data
            assert data['error'] is not None


class TestResearchQueryEndpoint:
    """Tests for POST /query endpoint."""

    def test_research_query_without_agent(self, mock_user_context):
        """Test query fails when research agent not initialized."""
        app = FastAPI()
        app.include_router(research.router)
        app.dependency_overrides[get_research_agent] = lambda: None
        app.dependency_overrides[get_user_context] = lambda: mock_user_context

        with TestClient(app) as client:
            request_data = {'query': 'machine learning papers'}
            response = client.post('/query', json=request_data)

            assert response.status_code == 503
            assert 'Research agent not initialized' in response.json()['detail']

    def test_research_query_success(self, test_client, mock_research_agent):
        """Test query returns research results."""
        # Setup mock
        mock_research_agent.chat.return_value = {
            'response': 'Found 5 relevant papers on machine learning',
            'tool_calls': [
                {
                    'tool': 'thoth_search_papers',
                    'args': {'query': 'machine learning'},
                    'result': 'Results here',
                }
            ],
        }

        request_data = {
            'query': 'machine learning papers',
            'max_results': 10,
            'sources': ['arxiv'],
        }
        response = test_client.post('/query', json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert 'results' in data
        assert 'summary' in data
        assert 'sources_used' in data
        assert 'query' in data
        assert data['query'] == 'machine learning papers'
        assert 'arxiv' in data['sources_used']

    def test_research_query_with_minimal_data(self, test_client, mock_research_agent):
        """Test query works with minimal request data."""
        # Setup mock
        mock_research_agent.chat.return_value = {
            'response': 'Research summary',
            'tool_calls': [],
        }

        request_data = {'query': 'test query'}
        response = test_client.post('/query', json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data['query'] == 'test query'
        assert isinstance(data['results'], list)
        assert isinstance(data['sources_used'], list)

    def test_research_query_error_handling(self, test_client, mock_research_agent):
        """Test query handles errors properly."""
        # Setup mock to raise exception
        mock_research_agent.chat.side_effect = Exception('Query error')

        request_data = {'query': 'test'}
        response = test_client.post('/query', json=request_data)

        assert response.status_code == 500
        assert 'Research query failed' in response.json()['detail']
