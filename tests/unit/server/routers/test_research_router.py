"""Tests for research router endpoints."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from thoth.server.routers import research


@pytest.fixture
def test_client():
    """Create FastAPI test client with research router."""
    app = FastAPI()
    app.include_router(research.router)
    return TestClient(app)


@pytest.fixture
def mock_research_agent():
    """Create mock research agent."""
    agent = Mock()
    agent.chat = AsyncMock()
    return agent


@pytest.fixture
def mock_chat_manager():
    """Create mock chat manager."""
    manager = Mock()
    manager.get_session = Mock(return_value=None)
    manager.create_session = Mock()
    manager.add_message = Mock()
    return manager


class TestResearchChatEndpoint:
    """Tests for POST /chat endpoint."""

    def test_research_chat_without_agent(self, test_client):
        """Test chat fails when research agent not initialized."""
        research.set_dependencies(None, None)
        
        request_data = {'message': 'Hello'}
        response = test_client.post('/chat', json=request_data)
        
        assert response.status_code == 503
        assert 'Research agent not initialized' in response.json()['detail']

    def test_research_chat_success(self, test_client, mock_research_agent):
        """Test chat returns response from research agent."""
        # Setup mocks
        mock_research_agent.chat.return_value = {
            'response': 'Here is the answer',
            'tool_calls': []
        }
        research.set_dependencies(mock_research_agent, None)
        
        request_data = {'message': 'What is machine learning?'}
        response = test_client.post('/chat', json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert 'response' in data
        assert data['response'] == 'Here is the answer'
        assert 'tool_calls' in data

    def test_research_chat_with_chat_manager(self, test_client, mock_research_agent, mock_chat_manager):
        """Test chat stores messages when chat manager available."""
        # Setup mocks
        mock_research_agent.chat.return_value = {
            'response': 'Here is the answer',
            'tool_calls': []
        }
        research.set_dependencies(mock_research_agent, mock_chat_manager)
        
        request_data = {
            'message': 'What is machine learning?',
            'conversation_id': 'conv-123'
        }
        response = test_client.post('/chat', json=request_data)
        
        assert response.status_code == 200
        # Verify chat manager was called
        assert mock_chat_manager.get_session.called
        assert mock_chat_manager.add_message.called

    def test_research_chat_handles_errors_gracefully(self, test_client, mock_research_agent):
        """Test chat handles errors and returns error response."""
        # Setup mock to raise exception
        mock_research_agent.chat.side_effect = Exception("Agent error")
        research.set_dependencies(mock_research_agent, None)
        
        request_data = {'message': 'Test'}
        response = test_client.post('/chat', json=request_data)
        
        assert response.status_code == 200  # Returns 200 with error in body
        data = response.json()
        assert 'error' in data
        assert data['error'] is not None


class TestResearchQueryEndpoint:
    """Tests for POST /query endpoint."""

    def test_research_query_without_agent(self, test_client):
        """Test query fails when research agent not initialized."""
        research.set_dependencies(None, None)
        
        request_data = {'query': 'machine learning papers'}
        response = test_client.post('/query', json=request_data)
        
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
                    'result': 'Results here'
                }
            ]
        }
        research.set_dependencies(mock_research_agent, None)
        
        request_data = {
            'query': 'machine learning papers',
            'max_results': 10,
            'sources': ['arxiv']
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
            'tool_calls': []
        }
        research.set_dependencies(mock_research_agent, None)
        
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
        mock_research_agent.chat.side_effect = Exception("Query error")
        research.set_dependencies(mock_research_agent, None)
        
        request_data = {'query': 'test'}
        response = test_client.post('/query', json=request_data)
        
        assert response.status_code == 500
        assert 'Research query failed' in response.json()['detail']
