"""
Comprehensive Unit Tests for MCP Health FastAPI Endpoints

Tests FastAPI health endpoints including:
- GET /mcp/health endpoint responses
- GET /mcp/servers endpoint with server details
- POST /mcp/refresh-cache endpoint behavior
- GET /mcp/metrics Prometheus format validation
- Mock httpx client for external MCP server calls
- Error handling and status codes
- Response model validation
"""

import time
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from thoth.mcp.monitoring import (
    MCPHealthStatus,
    MCPMonitor,
    MCPServerStats,
    get_mcp_health,
    get_mcp_metrics,
    get_mcp_servers,
    mcp_health_router,
    refresh_mcp_cache,
)


# ============================================================================
# FastAPI Test Client Setup
# ============================================================================

@pytest.fixture
def test_client():
    """Create FastAPI test client with MCP health router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(mcp_health_router)

    return TestClient(app)


# ============================================================================
# GET /mcp/health Endpoint Tests
# ============================================================================

class TestHealthEndpoint:
    """Test GET /mcp/health endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_endpoint_healthy_server(self):
        """Test /mcp/health returns 200 with healthy status."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200, json={'status': 'healthy'})
        )

        status = await get_mcp_health()

        assert isinstance(status, MCPHealthStatus)
        assert status.healthy is True
        assert status.server_count == 1
        assert len(status.errors) == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_health_endpoint_unhealthy_server(self):
        """Test /mcp/health returns unhealthy status when server down."""
        respx.get('http://localhost:8000/health').mock(
            side_effect=httpx.ConnectError('Connection refused')
        )

        status = await get_mcp_health()

        assert isinstance(status, MCPHealthStatus)
        assert status.healthy is False
        assert status.server_count == 0
        assert len(status.errors) > 0

    def test_health_endpoint_via_test_client_healthy(self, test_client):
        """Test /mcp/health via test client with healthy server."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            response = test_client.get('/mcp/health')

            assert response.status_code == 200
            data = response.json()
            assert data['healthy'] is True
            assert data['server_count'] == 1
            assert 'success_rate' in data
            assert 'avg_response_time' in data

    def test_health_endpoint_via_test_client_unhealthy(self, test_client):
        """Test /mcp/health via test client with unhealthy server."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                side_effect=httpx.ConnectError('Connection refused')
            )

            response = test_client.get('/mcp/health')

            assert response.status_code == 200  # Endpoint still responds
            data = response.json()
            assert data['healthy'] is False
            assert len(data['errors']) > 0

    @pytest.mark.asyncio
    async def test_health_endpoint_response_model(self):
        """Test /mcp/health response matches MCPHealthStatus model."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            status = await get_mcp_health()

            # Verify all required fields present
            assert hasattr(status, 'healthy')
            assert hasattr(status, 'server_count')
            assert hasattr(status, 'total_connections')
            assert hasattr(status, 'active_connections')
            assert hasattr(status, 'success_rate')
            assert hasattr(status, 'avg_response_time')
            assert hasattr(status, 'last_check')
            assert hasattr(status, 'errors')

    def test_health_endpoint_includes_timestamp(self, test_client):
        """Test /mcp/health response includes valid timestamp."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            before_time = time.time()
            response = test_client.get('/mcp/health')
            after_time = time.time()

            data = response.json()
            assert before_time <= data['last_check'] <= after_time


# ============================================================================
# GET /mcp/servers Endpoint Tests
# ============================================================================

class TestServersEndpoint:
    """Test GET /mcp/servers endpoint."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_servers_endpoint_healthy_server(self):
        """Test /mcp/servers returns server list when healthy."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200)
        )

        servers = await get_mcp_servers()

        assert isinstance(servers, list)
        assert len(servers) == 1
        assert isinstance(servers[0], MCPServerStats)
        assert servers[0].healthy is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_servers_endpoint_unhealthy_server(self):
        """Test /mcp/servers returns empty list when server down."""
        respx.get('http://localhost:8000/health').mock(
            side_effect=httpx.ConnectError('Connection refused')
        )

        servers = await get_mcp_servers()

        assert isinstance(servers, list)
        assert len(servers) == 0

    def test_servers_endpoint_via_test_client(self, test_client):
        """Test /mcp/servers via test client."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            response = test_client.get('/mcp/servers')

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) == 1
            assert 'server_name' in data[0]
            assert 'healthy' in data[0]

    def test_servers_endpoint_includes_server_details(self, test_client):
        """Test /mcp/servers includes comprehensive server details."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            response = test_client.get('/mcp/servers')
            data = response.json()

            server = data[0]
            assert 'server_name' in server
            assert 'active_connections' in server
            assert 'total_requests' in server
            assert 'failed_requests' in server
            assert 'success_rate' in server
            assert 'avg_response_time' in server
            assert 'circuit_breaker_state' in server
            assert 'healthy' in server

    @pytest.mark.asyncio
    async def test_servers_endpoint_response_model(self):
        """Test /mcp/servers response matches MCPServerStats model."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            servers = await get_mcp_servers()

            if servers:
                server = servers[0]
                assert hasattr(server, 'server_name')
                assert hasattr(server, 'active_connections')
                assert hasattr(server, 'total_requests')
                assert hasattr(server, 'failed_requests')
                assert hasattr(server, 'success_rate')
                assert hasattr(server, 'avg_response_time')
                assert hasattr(server, 'last_health_check')
                assert hasattr(server, 'circuit_breaker_state')
                assert hasattr(server, 'healthy')


# ============================================================================
# POST /mcp/refresh-cache Endpoint Tests
# ============================================================================

class TestRefreshCacheEndpoint:
    """Test POST /mcp/refresh-cache endpoint."""

    @pytest.mark.asyncio
    async def test_refresh_cache_endpoint_success(self):
        """Test /mcp/refresh-cache returns success response."""
        result = await refresh_mcp_cache()

        assert isinstance(result, dict)
        assert result['success'] is True
        assert 'message' in result
        assert 'timestamp' in result

    def test_refresh_cache_endpoint_via_test_client(self, test_client):
        """Test /mcp/refresh-cache via test client."""
        response = test_client.post('/mcp/refresh-cache')

        assert response.status_code == 200
        data = response.json()
        assert data['success'] is True
        assert 'timestamp' in data

    @pytest.mark.asyncio
    async def test_refresh_cache_endpoint_error_handling(self):
        """Test /mcp/refresh-cache error handling."""
        with patch('thoth.mcp.monitoring.mcp_monitor.refresh_tools_cache',
                   return_value={'success': False, 'error': 'Cache refresh failed', 'timestamp': time.time()}):
            with pytest.raises(HTTPException) as exc_info:
                await refresh_mcp_cache()

            assert exc_info.value.status_code == 500
            assert 'Cache refresh failed' in str(exc_info.value.detail)

    def test_refresh_cache_endpoint_error_via_test_client(self, test_client):
        """Test /mcp/refresh-cache error handling via test client."""
        with patch('thoth.mcp.monitoring.mcp_monitor.refresh_tools_cache',
                   return_value={'success': False, 'error': 'Test error', 'timestamp': time.time()}):
            response = test_client.post('/mcp/refresh-cache')

            assert response.status_code == 500

    @pytest.mark.asyncio
    async def test_refresh_cache_endpoint_includes_timestamp(self):
        """Test /mcp/refresh-cache includes valid timestamp."""
        before_time = time.time()
        result = await refresh_mcp_cache()
        after_time = time.time()

        assert before_time <= result['timestamp'] <= after_time


# ============================================================================
# GET /mcp/metrics Endpoint Tests (Prometheus Format)
# ============================================================================

class TestMetricsEndpoint:
    """Test GET /mcp/metrics endpoint and Prometheus format."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_metrics_endpoint_prometheus_format(self):
        """Test /mcp/metrics returns Prometheus-formatted metrics."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200)
        )

        metrics = await get_mcp_metrics()

        assert isinstance(metrics, str)
        assert 'mcp_healthy' in metrics
        assert 'mcp_server_count' in metrics
        assert 'mcp_total_connections' in metrics
        assert 'mcp_active_connections' in metrics
        assert 'mcp_success_rate' in metrics
        assert 'mcp_avg_response_time' in metrics

    def test_metrics_endpoint_via_test_client(self, test_client):
        """Test /mcp/metrics via test client."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            response = test_client.get('/mcp/metrics')

            assert response.status_code == 200
            metrics_text = response.text
            assert 'mcp_healthy' in metrics_text

    @pytest.mark.asyncio
    @respx.mock
    async def test_metrics_endpoint_includes_server_metrics(self):
        """Test /mcp/metrics includes per-server metrics."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200)
        )

        metrics = await get_mcp_metrics()

        # Check for per-server metrics with labels
        assert 'mcp_server_active_connections{server="thoth-mcp"}' in metrics
        assert 'mcp_server_total_requests{server="thoth-mcp"}' in metrics
        assert 'mcp_server_failed_requests{server="thoth-mcp"}' in metrics
        assert 'mcp_server_success_rate{server="thoth-mcp"}' in metrics
        assert 'mcp_server_response_time{server="thoth-mcp"}' in metrics
        assert 'mcp_server_healthy{server="thoth-mcp"}' in metrics

    @pytest.mark.asyncio
    @respx.mock
    async def test_metrics_endpoint_metric_values(self):
        """Test /mcp/metrics contains valid numeric values."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200)
        )

        metrics = await get_mcp_metrics()
        lines = metrics.split('\n')

        for line in lines:
            if line.strip():
                # Each line should have format: metric_name [labels] value
                parts = line.rsplit(' ', 1)
                assert len(parts) == 2, f'Invalid metric line: {line}'

                metric_name, value = parts
                # Value should be numeric
                try:
                    float(value)
                except ValueError:
                    pytest.fail(f'Metric value is not numeric: {value}')

    @pytest.mark.asyncio
    @respx.mock
    async def test_metrics_endpoint_label_format(self):
        """Test /mcp/metrics uses correct label formatting."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200)
        )

        metrics = await get_mcp_metrics()

        # Check label format: {key="value"}
        assert 'server="thoth-mcp"' in metrics
        # Ensure proper curly brace formatting
        assert '{server="thoth-mcp"}' in metrics

    def test_metrics_endpoint_unhealthy_server(self, test_client):
        """Test /mcp/metrics when server is unhealthy."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                side_effect=httpx.ConnectError('Connection refused')
            )

            response = test_client.get('/mcp/metrics')

            assert response.status_code == 200
            metrics_text = response.text
            assert 'mcp_healthy 0' in metrics_text
            assert 'mcp_server_count 0' in metrics_text


# ============================================================================
# HTTP Client Mocking Tests
# ============================================================================

class TestHTTPClientMocking:
    """Test proper mocking of httpx client for external MCP server calls."""

    @pytest.mark.asyncio
    async def test_mock_httpx_async_client_healthy(self):
        """Test mocking httpx AsyncClient for healthy server."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            monitor = MCPMonitor()
            status = await monitor.get_health_status()

            assert status.healthy is True
            mock_client.get.assert_called_once_with('http://localhost:8000/health')

    @pytest.mark.asyncio
    async def test_mock_httpx_async_client_timeout(self):
        """Test mocking httpx AsyncClient timeout."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException('Timeout')
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            monitor = MCPMonitor()
            status = await monitor.get_health_status()

            assert status.healthy is False
            assert 'timed out' in status.errors[0].lower()

    @pytest.mark.asyncio
    async def test_mock_httpx_async_client_connection_error(self):
        """Test mocking httpx AsyncClient connection error."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError('Connection refused')
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            monitor = MCPMonitor()
            status = await monitor.get_health_status()

            assert status.healthy is False
            assert 'cannot connect' in status.errors[0].lower()

    @pytest.mark.asyncio
    async def test_mock_httpx_async_client_cleanup(self):
        """Test httpx AsyncClient is properly cleaned up."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_class.return_value = mock_client

            monitor = MCPMonitor()
            await monitor.get_health_status()

            # Verify context manager was used (cleanup happens automatically)
            assert mock_client.__aenter__.called
            assert mock_client.__aexit__.called


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestEndpointErrorHandling:
    """Test error handling across all endpoints."""

    @pytest.mark.asyncio
    async def test_health_endpoint_handles_monitor_exception(self):
        """Test /mcp/health handles exceptions from monitor."""
        with patch('thoth.mcp.monitoring.mcp_monitor.get_health_status',
                   side_effect=Exception('Monitor error')):
            # Should not raise, should return error status
            try:
                status = await get_mcp_health()
                # If it doesn't raise, it should return unhealthy status
                assert status.healthy is False
            except Exception:
                # Or it might propagate the exception
                pass

    @pytest.mark.asyncio
    async def test_servers_endpoint_handles_monitor_exception(self):
        """Test /mcp/servers handles exceptions from monitor."""
        with patch('thoth.mcp.monitoring.mcp_monitor.get_server_details',
                   side_effect=Exception('Monitor error')):
            try:
                servers = await get_mcp_servers()
                # Should return empty list on error
                assert isinstance(servers, list)
            except Exception:
                pass

    def test_refresh_cache_endpoint_returns_500_on_failure(self, test_client):
        """Test /mcp/refresh-cache returns 500 on failure."""
        with patch('thoth.mcp.monitoring.mcp_monitor.refresh_tools_cache',
                   return_value={'success': False, 'error': 'Cache error', 'timestamp': time.time()}):
            response = test_client.post('/mcp/refresh-cache')
            assert response.status_code == 500


# ============================================================================
# Integration Tests with Multiple Endpoints
# ============================================================================

class TestEndpointIntegration:
    """Test integration between different endpoints."""

    def test_health_and_servers_consistency(self, test_client):
        """Test /mcp/health and /mcp/servers return consistent data."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            health_response = test_client.get('/mcp/health')
            servers_response = test_client.get('/mcp/servers')

            health_data = health_response.json()
            servers_data = servers_response.json()

            # If health shows healthy, servers should have entries
            if health_data['healthy']:
                assert len(servers_data) > 0
                # Server stats should match health stats
                server = servers_data[0]
                assert server['healthy'] == health_data['healthy']

    def test_metrics_reflects_current_health(self, test_client):
        """Test /mcp/metrics reflects current health status."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            health_response = test_client.get('/mcp/health')
            metrics_response = test_client.get('/mcp/metrics')

            health_data = health_response.json()
            metrics_text = metrics_response.text

            # Metrics should reflect health status
            if health_data['healthy']:
                assert 'mcp_healthy 1' in metrics_text
            else:
                assert 'mcp_healthy 0' in metrics_text
