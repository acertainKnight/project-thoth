"""Tests for health router endpoints."""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from thoth.server.routers import health


@pytest.fixture
def test_client():
    """Create FastAPI test client with health router."""
    from fastapi import FastAPI
    
    app = FastAPI()
    app.include_router(health.router)
    
    # Set up directories for the router
    with TemporaryDirectory() as tmpdir:
        pdf_dir = Path(tmpdir) / "pdfs"
        notes_dir = Path(tmpdir) / "notes"
        pdf_dir.mkdir()
        notes_dir.mkdir()
        
        health.set_directories(pdf_dir, notes_dir, "http://localhost:8000")
        
        yield TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @patch('thoth.server.app.service_manager')
    @patch('thoth.server.routers.health.HealthMonitor')
    def test_health_check_healthy(self, mock_monitor_class, mock_service_manager, test_client):
        """Test health check returns 200 when services are healthy."""
        # Setup mock
        mock_monitor = Mock()
        mock_monitor.overall_status.return_value = {
            'healthy': True,
            'services': {'llm': 'healthy', 'article': 'healthy'}
        }
        mock_monitor_class.return_value = mock_monitor
        
        # Make request
        response = test_client.get('/health')
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'
        assert data['healthy'] is True
        assert 'services' in data
        assert 'timestamp' in data

    @patch('thoth.server.app.service_manager')
    @patch('thoth.server.routers.health.HealthMonitor')
    def test_health_check_unhealthy(self, mock_monitor_class, mock_service_manager, test_client):
        """Test health check returns 503 when services are unhealthy."""
        # Setup mock
        mock_monitor = Mock()
        mock_monitor.overall_status.return_value = {
            'healthy': False,
            'services': {'llm': 'unhealthy', 'article': 'healthy'}
        }
        mock_monitor_class.return_value = mock_monitor
        
        # Make request
        response = test_client.get('/health')
        
        # Assertions
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'unhealthy'
        assert data['healthy'] is False

    @patch('thoth.server.app.service_manager', None)
    def test_health_check_service_manager_not_initialized(self, test_client):
        """Test health check handles service manager not initialized."""
        # Make request
        response = test_client.get('/health')
        
        # Assertions
        assert response.status_code == 503
        data = response.json()
        assert data['status'] == 'unhealthy'
        assert data['healthy'] is False
        assert 'Service manager not initialized' in data['error']

    @patch('thoth.server.app.service_manager')
    @patch('thoth.server.routers.health.HealthMonitor')
    def test_health_check_exception_handling(self, mock_monitor_class, mock_service_manager, test_client):
        """Test health check handles exceptions gracefully."""
        # Setup mock to raise exception
        mock_monitor_class.side_effect = Exception("Test exception")
        
        # Make request
        response = test_client.get('/health')
        
        # Assertions
        assert response.status_code == 500
        data = response.json()
        assert data['status'] == 'unhealthy'
        assert data['healthy'] is False
        assert 'Health check failed' in data['error']


class TestDownloadPdfEndpoint:
    """Tests for /download-pdf endpoint."""

    @patch('thoth.server.routers.health.download_pdf')
    def test_download_pdf_success(self, mock_download, test_client):
        """Test PDF download succeeds."""
        # Setup mock
        mock_pdf_path = Path("/tmp/test.pdf")
        mock_download.return_value = mock_pdf_path
        
        # Make request
        response = test_client.get('/download-pdf?url=http://example.com/paper.pdf')
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'file_path' in data
        assert 'filename' in data
        assert data['filename'] == 'test.pdf'

    @patch('thoth.server.routers.health.download_pdf')
    def test_download_pdf_error_handling(self, mock_download, test_client):
        """Test PDF download handles errors gracefully."""
        # Setup mock to raise exception
        mock_download.side_effect = Exception("Download failed")
        
        # Make request
        response = test_client.get('/download-pdf?url=http://example.com/paper.pdf')
        
        # Assertions
        assert response.status_code == 500
        data = response.json()
        assert data['status'] == 'error'
        assert 'Error downloading PDF' in data['message']


class TestViewMarkdownEndpoint:
    """Tests for /view-markdown endpoint."""

    def test_view_markdown_file_exists(self, test_client):
        """Test viewing markdown file that exists."""
        # Create a test markdown file
        with TemporaryDirectory() as tmpdir:
            notes_dir = Path(tmpdir)
            test_file = notes_dir / "test.md"
            test_content = "# Test Markdown\n\nThis is a test."
            test_file.write_text(test_content)
            
            # Update router directories
            health.set_directories(Path(tmpdir), notes_dir, "http://localhost:8000")
            
            # Make request with relative path
            response = test_client.get(f'/view-markdown?path=test.md')
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'success'
            assert data['content'] == test_content
            assert 'path' in data
            assert 'size' in data

    def test_view_markdown_file_not_found(self, test_client):
        """Test viewing markdown file that doesn't exist."""
        # Make request
        response = test_client.get('/view-markdown?path=nonexistent.md')
        
        # Assertions
        assert response.status_code == 404
        data = response.json()
        assert data['status'] == 'error'
        assert 'File not found' in data['message']

    def test_view_markdown_absolute_path(self, test_client):
        """Test viewing markdown file with absolute path."""
        # Create a test markdown file
        with TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "absolute.md"
            test_content = "# Absolute Path Test"
            test_file.write_text(test_content)
            
            # Make request with absolute path
            response = test_client.get(f'/view-markdown?path={test_file}')
            
            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert data['status'] == 'success'
            assert data['content'] == test_content
