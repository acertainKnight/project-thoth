"""Tests for operations router endpoints."""

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from thoth.server.routers import operations


@pytest.fixture
def test_client():
    """Create FastAPI test client with operations router."""
    app = FastAPI()
    app.include_router(operations.router)
    return TestClient(app)


@pytest.fixture
def mock_service_manager():
    """Create mock service manager."""
    manager = Mock()
    manager.citation_service = None
    manager.discovery_service = None
    operations.set_service_manager(manager)
    yield manager
    # Clean up
    operations.set_service_manager(None)


class TestCollectionStatsEndpoint:
    """Tests for /collection/stats endpoint."""

    def test_collection_stats_without_service_manager(self, test_client):
        """Test collection stats fails when service manager not initialized."""
        # Ensure no service manager
        operations.set_service_manager(None)
        
        response = test_client.get('/collection/stats')
        
        assert response.status_code == 503
        assert 'Service manager not initialized' in response.json()['detail']

    def test_collection_stats_with_service_manager(self, test_client, mock_service_manager):
        """Test collection stats returns basic stats."""
        response = test_client.get('/collection/stats')
        
        assert response.status_code == 200
        data = response.json()
        assert 'total_documents' in data
        assert 'processed_documents' in data
        assert 'total_citations' in data
        assert 'status' in data
        assert data['status'] == 'operational'

    def test_collection_stats_with_citation_service(self, test_client, mock_service_manager):
        """Test collection stats handles citation service gracefully."""
        # Setup mock citation service (even if it fails, should return stats)
        mock_citation_service = Mock()
        mock_service_manager.citation_service = mock_citation_service
        
        response = test_client.get('/collection/stats')
        
        assert response.status_code == 200
        data = response.json()
        # Should still return stats structure even if citation service details fail
        assert 'processed_documents' in data
        assert 'total_citations' in data


class TestListArticlesEndpoint:
    """Tests for /articles endpoint."""

    def test_list_articles_without_service_manager(self, test_client):
        """Test list articles fails when service manager not initialized."""
        operations.set_service_manager(None)
        
        response = test_client.get('/articles')
        
        assert response.status_code == 503
        assert 'Service manager not initialized' in response.json()['detail']

    def test_list_articles_returns_paginated_results(self, test_client, mock_service_manager):
        """Test list articles returns paginated mock data."""
        response = test_client.get('/articles?limit=5&offset=0')
        
        assert response.status_code == 200
        data = response.json()
        assert 'articles' in data
        assert 'total' in data
        assert 'limit' in data
        assert 'offset' in data
        assert data['limit'] == 5
        assert data['offset'] == 0
        assert isinstance(data['articles'], list)

    def test_list_articles_with_custom_pagination(self, test_client, mock_service_manager):
        """Test list articles respects pagination parameters."""
        response = test_client.get('/articles?limit=2&offset=1')
        
        assert response.status_code == 200
        data = response.json()
        assert data['limit'] == 2
        assert data['offset'] == 1


class TestOperationStatusEndpoint:
    """Tests for /{operation_id}/status endpoint."""

    @patch('thoth.server.routers.operations.get_operation_status')
    def test_get_operation_status_found(self, mock_get_status, test_client):
        """Test getting status of existing operation."""
        # Setup mock
        mock_get_status.return_value = {
            'operation_id': 'test-123',
            'status': 'running',
            'progress': 50.0,
            'message': 'Processing...'
        }
        
        response = test_client.get('/test-123/status')
        
        assert response.status_code == 200
        data = response.json()
        assert data['operation_id'] == 'test-123'
        assert data['status'] == 'running'
        assert data['progress'] == 50.0

    @patch('thoth.server.routers.operations.get_operation_status')
    def test_get_operation_status_not_found(self, mock_get_status, test_client):
        """Test getting status of non-existent operation."""
        # Setup mock to return None
        mock_get_status.return_value = None
        
        response = test_client.get('/nonexistent-id/status')
        
        assert response.status_code == 404
        assert 'Operation not found' in response.json()['detail']


class TestStreamingOperationEndpoint:
    """Tests for /stream/operation endpoint."""

    @patch('thoth.server.routers.operations.create_background_task')
    def test_start_streaming_operation_creates_task(self, mock_create_task, test_client):
        """Test starting streaming operation creates background task."""
        request_data = {
            'operation_type': 'pdf_process',
            'parameters': {'pdf_paths': ['/test/file.pdf']}
        }
        
        response = test_client.post('/stream/operation', json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert 'operation_id' in data
        assert data['status'] == 'started'
        assert 'pdf_process' in data['message']
        
        # Verify background task was created
        mock_create_task.assert_called_once()

    @patch('thoth.server.routers.operations.create_background_task')
    def test_start_streaming_operation_with_custom_id(self, mock_create_task, test_client):
        """Test starting streaming operation with custom operation ID."""
        request_data = {
            'operation_type': 'discovery_run',
            'parameters': {'source_name': 'arxiv'},
            'operation_id': 'custom-op-123'
        }
        
        response = test_client.post('/stream/operation', json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data['operation_id'] == 'custom-op-123'
        assert data['status'] == 'started'
