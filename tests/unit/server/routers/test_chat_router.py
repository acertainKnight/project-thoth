"""Tests for chat router endpoints."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from thoth.server.routers import chat


@pytest.fixture
def test_client():
    """Create FastAPI test client with chat router."""
    app = FastAPI()
    app.include_router(chat.router)
    return TestClient(app)


@pytest.fixture
def mock_chat_manager():
    """Create mock chat manager."""
    manager = Mock()
    chat.set_chat_manager(manager)
    yield manager
    # Cleanup
    chat.set_chat_manager(None)


@pytest.fixture
def mock_session():
    """Create mock chat session."""
    session = Mock()
    session.id = 'session-123'
    session.title = 'Test Chat'
    session.created_at = datetime(2024, 1, 1, 12, 0, 0)
    session.updated_at = datetime(2024, 1, 1, 12, 0, 0)
    session.is_active = True
    session.metadata = {}
    session.message_count = 5
    session.last_message_preview = 'Last message'
    return session


class TestCreateSessionEndpoint:
    """Tests for POST /sessions endpoint."""

    def test_create_session_without_chat_manager(self, test_client):
        """Test creating session fails when chat manager not initialized."""
        chat.set_chat_manager(None)
        
        request_data = {'title': 'New Chat'}
        response = test_client.post('/sessions', json=request_data)
        
        assert response.status_code == 503
        assert 'Chat manager not initialized' in response.json()['detail']

    def test_create_session_success(self, test_client, mock_chat_manager, mock_session):
        """Test creating session returns session data."""
        mock_chat_manager.create_session.return_value = mock_session
        
        request_data = {'title': 'New Chat', 'metadata': {'key': 'value'}}
        response = test_client.post('/sessions', json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'session' in data
        assert data['session']['id'] == 'session-123'
        assert data['session']['title'] == 'Test Chat'


class TestListSessionsEndpoint:
    """Tests for GET /sessions endpoint."""

    def test_list_sessions_without_chat_manager(self, test_client):
        """Test listing sessions fails when chat manager not initialized."""
        chat.set_chat_manager(None)
        
        response = test_client.get('/sessions')
        
        assert response.status_code == 503
        assert 'Chat manager not initialized' in response.json()['detail']

    def test_list_sessions_success(self, test_client, mock_chat_manager, mock_session):
        """Test listing sessions returns session list."""
        mock_chat_manager.list_sessions.return_value = [mock_session]
        
        response = test_client.get('/sessions?active_only=true&limit=50')
        
        assert response.status_code == 200
        data = response.json()
        assert 'sessions' in data
        assert 'total_count' in data
        assert len(data['sessions']) == 1
        assert data['sessions'][0]['id'] == 'session-123'


class TestGetSessionEndpoint:
    """Tests for GET /sessions/{session_id} endpoint."""

    def test_get_session_not_found(self, test_client, mock_chat_manager):
        """Test getting non-existent session returns 404."""
        mock_chat_manager.get_session.return_value = None
        
        response = test_client.get('/sessions/nonexistent')
        
        assert response.status_code == 404
        assert 'Session not found' in response.json()['detail']

    def test_get_session_success(self, test_client, mock_chat_manager, mock_session):
        """Test getting session returns session data."""
        mock_chat_manager.get_session.return_value = mock_session
        
        response = test_client.get('/sessions/session-123')
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert data['session']['id'] == 'session-123'


class TestUpdateSessionEndpoint:
    """Tests for PUT /sessions/{session_id} endpoint."""

    def test_update_session_not_found(self, test_client, mock_chat_manager):
        """Test updating non-existent session returns 404."""
        mock_chat_manager.update_session.return_value = False
        
        request_data = {'title': 'Updated Title'}
        response = test_client.put('/sessions/nonexistent', json=request_data)
        
        assert response.status_code == 404
        assert 'Session not found' in response.json()['detail']

    def test_update_session_success(self, test_client, mock_chat_manager, mock_session):
        """Test updating session returns updated data."""
        mock_chat_manager.update_session.return_value = True
        mock_chat_manager.get_session.return_value = mock_session
        
        request_data = {'title': 'Updated Title'}
        response = test_client.put('/sessions/session-123', json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'Session updated successfully' in data['message']


class TestDeleteSessionEndpoint:
    """Tests for DELETE /sessions/{session_id} endpoint."""

    def test_delete_session_not_found(self, test_client, mock_chat_manager):
        """Test deleting non-existent session returns 404."""
        mock_chat_manager.delete_session.return_value = False
        
        response = test_client.delete('/sessions/nonexistent')
        
        assert response.status_code == 404
        assert 'Session not found' in response.json()['detail']

    def test_delete_session_success(self, test_client, mock_chat_manager):
        """Test deleting session returns success."""
        mock_chat_manager.delete_session.return_value = True
        
        response = test_client.delete('/sessions/session-123')
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'Session deleted successfully' in data['message']


class TestArchiveSessionEndpoint:
    """Tests for POST /sessions/{session_id}/archive endpoint."""

    def test_archive_session_not_found(self, test_client, mock_chat_manager):
        """Test archiving non-existent session returns 404."""
        mock_chat_manager.archive_session.return_value = False
        
        response = test_client.post('/sessions/nonexistent/archive')
        
        assert response.status_code == 404
        assert 'Session not found' in response.json()['detail']

    def test_archive_session_success(self, test_client, mock_chat_manager):
        """Test archiving session returns success."""
        mock_chat_manager.archive_session.return_value = True
        
        response = test_client.post('/sessions/session-123/archive')
        
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'Session archived successfully' in data['message']


class TestGetChatHistoryEndpoint:
    """Tests for GET /sessions/{session_id}/messages endpoint."""

    def test_get_chat_history_session_not_found(self, test_client, mock_chat_manager):
        """Test getting history for non-existent session returns 404."""
        mock_chat_manager.get_session.return_value = None
        
        response = test_client.get('/sessions/nonexistent/messages')
        
        assert response.status_code == 404
        assert 'Session not found' in response.json()['detail']

    def test_get_chat_history_success(self, test_client, mock_chat_manager, mock_session):
        """Test getting chat history returns messages."""
        mock_message = Mock()
        mock_message.id = 'msg-1'
        mock_message.role = 'user'
        mock_message.content = 'Hello'
        mock_message.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_message.metadata = {}
        
        mock_chat_manager.get_session.return_value = mock_session
        mock_chat_manager.get_messages.return_value = [mock_message]
        
        response = test_client.get('/sessions/session-123/messages?limit=100&offset=0')
        
        assert response.status_code == 200
        data = response.json()
        assert 'messages' in data
        assert 'session_info' in data
        assert 'total_count' in data
        assert 'has_more' in data
        assert len(data['messages']) == 1


class TestSearchMessagesEndpoint:
    """Tests for GET /search endpoint."""

    def test_search_messages_without_chat_manager(self, test_client):
        """Test searching messages fails when chat manager not initialized."""
        chat.set_chat_manager(None)
        
        response = test_client.get('/search?query=test')
        
        assert response.status_code == 503
        assert 'Chat manager not initialized' in response.json()['detail']

    def test_search_messages_success(self, test_client, mock_chat_manager):
        """Test searching messages returns results."""
        mock_message = Mock()
        mock_message.id = 'msg-1'
        mock_message.session_id = 'session-123'
        mock_message.role = 'user'
        mock_message.content = 'Hello test'
        mock_message.timestamp = datetime(2024, 1, 1, 12, 0, 0)
        mock_message.metadata = {}
        mock_message.relevance_score = 0.9
        
        mock_chat_manager.search_messages.return_value = [mock_message]
        
        response = test_client.get('/search?query=test&limit=50')
        
        assert response.status_code == 200
        data = response.json()
        assert 'messages' in data
        assert 'total_count' in data
        assert 'query' in data
        assert data['query'] == 'test'
        assert len(data['messages']) == 1
