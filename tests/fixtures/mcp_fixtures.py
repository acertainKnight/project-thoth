"""
MCP Monitoring Test Fixtures

Provides comprehensive fixtures for testing MCP monitoring capabilities including:
- Mock httpx clients with various response scenarios
- Sample health status and server stats models
- Error condition fixtures (timeouts, connection errors, server errors)
- Prometheus metrics validation fixtures
"""

import time
from typing import Any
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import respx

from thoth.mcp.monitoring import MCPHealthStatus, MCPServerStats


# ============================================================================
# Health Status Fixtures
# ============================================================================

@pytest.fixture
def healthy_status() -> MCPHealthStatus:
    """Create a healthy MCP health status."""
    return MCPHealthStatus(
        healthy=True,
        server_count=1,
        total_connections=5,
        active_connections=3,
        success_rate=98.5,
        avg_response_time=0.15,
        last_check=time.time(),
        errors=[],
    )


@pytest.fixture
def unhealthy_status() -> MCPHealthStatus:
    """Create an unhealthy MCP health status with errors."""
    return MCPHealthStatus(
        healthy=False,
        server_count=0,
        total_connections=0,
        active_connections=0,
        success_rate=0.0,
        avg_response_time=0.0,
        last_check=time.time(),
        errors=['Cannot connect to MCP server at localhost:8000'],
    )


@pytest.fixture
def degraded_status() -> MCPHealthStatus:
    """Create a degraded MCP health status (low success rate)."""
    return MCPHealthStatus(
        healthy=True,
        server_count=1,
        total_connections=10,
        active_connections=2,
        success_rate=85.0,  # Below threshold of 95%
        avg_response_time=3.2,
        last_check=time.time(),
        errors=['High error rate detected'],
    )


@pytest.fixture
def slow_response_status() -> MCPHealthStatus:
    """Create status with slow response times exceeding threshold."""
    return MCPHealthStatus(
        healthy=True,
        server_count=1,
        total_connections=3,
        active_connections=3,
        success_rate=99.0,
        avg_response_time=6.5,  # Above threshold of 5.0
        last_check=time.time(),
        errors=[],
    )


@pytest.fixture
def multiple_errors_status() -> MCPHealthStatus:
    """Create status with multiple error types."""
    return MCPHealthStatus(
        healthy=False,
        server_count=0,
        total_connections=0,
        active_connections=0,
        success_rate=0.0,
        avg_response_time=0.0,
        last_check=time.time(),
        errors=[
            'Cannot connect to MCP server at localhost:8000',
            'Connection timeout after 2.0s',
            'Circuit breaker opened after 5 consecutive failures',
        ],
    )


# ============================================================================
# Server Stats Fixtures
# ============================================================================

@pytest.fixture
def healthy_server_stats() -> MCPServerStats:
    """Create healthy server statistics."""
    return MCPServerStats(
        server_name='thoth-mcp',
        active_connections=3,
        total_requests=150,
        failed_requests=2,
        success_rate=98.7,
        avg_response_time=0.12,
        last_health_check=time.time(),
        circuit_breaker_state='closed',
        healthy=True,
    )


@pytest.fixture
def unhealthy_server_stats() -> MCPServerStats:
    """Create unhealthy server statistics."""
    return MCPServerStats(
        server_name='thoth-mcp',
        active_connections=0,
        total_requests=100,
        failed_requests=50,
        success_rate=50.0,
        avg_response_time=0.0,
        last_health_check=time.time(),
        circuit_breaker_state='open',
        healthy=False,
    )


@pytest.fixture
def multiple_servers_stats() -> list[MCPServerStats]:
    """Create statistics for multiple MCP servers."""
    return [
        MCPServerStats(
            server_name='thoth-mcp-primary',
            active_connections=5,
            total_requests=500,
            failed_requests=5,
            success_rate=99.0,
            avg_response_time=0.10,
            last_health_check=time.time(),
            circuit_breaker_state='closed',
            healthy=True,
        ),
        MCPServerStats(
            server_name='thoth-mcp-secondary',
            active_connections=2,
            total_requests=200,
            failed_requests=10,
            success_rate=95.0,
            avg_response_time=0.20,
            last_health_check=time.time(),
            circuit_breaker_state='closed',
            healthy=True,
        ),
        MCPServerStats(
            server_name='thoth-mcp-backup',
            active_connections=0,
            total_requests=50,
            failed_requests=25,
            success_rate=50.0,
            avg_response_time=0.0,
            last_health_check=time.time() - 300,  # 5 minutes ago
            circuit_breaker_state='open',
            healthy=False,
        ),
    ]


# ============================================================================
# HTTP Response Fixtures
# ============================================================================

@pytest.fixture
def mock_healthy_http_response():
    """Create mock HTTP response for healthy MCP server."""
    response = Mock(spec=httpx.Response)
    response.status_code = 200
    response.json.return_value = {'status': 'healthy', 'timestamp': time.time()}
    response.raise_for_status = Mock()
    return response


@pytest.fixture
def mock_unhealthy_http_response():
    """Create mock HTTP response for unhealthy MCP server."""
    response = Mock(spec=httpx.Response)
    response.status_code = 503
    response.json.return_value = {'status': 'unhealthy', 'error': 'Service unavailable'}
    response.raise_for_status = Mock(side_effect=httpx.HTTPStatusError(
        'Service unavailable',
        request=Mock(),
        response=response,
    ))
    return response


@pytest.fixture
def mock_timeout_error():
    """Create mock timeout error."""
    return httpx.TimeoutException('Request timed out after 2.0 seconds')


@pytest.fixture
def mock_connect_error():
    """Create mock connection error."""
    return httpx.ConnectError('Cannot connect to host localhost:8000')


@pytest.fixture
def mock_network_error():
    """Create mock network error."""
    return httpx.NetworkError('Network unreachable')


# ============================================================================
# Respx Mock Fixtures (HTTP Client Mocking)
# ============================================================================

@pytest.fixture
def respx_mock_healthy_server(respx_mock):
    """Mock httpx client to return healthy server response."""
    respx_mock.get('http://localhost:8000/health').mock(
        return_value=httpx.Response(200, json={'status': 'healthy'})
    )
    return respx_mock


@pytest.fixture
def respx_mock_unhealthy_server(respx_mock):
    """Mock httpx client to return unhealthy server response."""
    respx_mock.get('http://localhost:8000/health').mock(
        return_value=httpx.Response(503, json={'status': 'unhealthy'})
    )
    return respx_mock


@pytest.fixture
def respx_mock_timeout(respx_mock):
    """Mock httpx client to raise timeout exception."""
    respx_mock.get('http://localhost:8000/health').mock(
        side_effect=httpx.TimeoutException('Request timeout')
    )
    return respx_mock


@pytest.fixture
def respx_mock_connection_error(respx_mock):
    """Mock httpx client to raise connection error."""
    respx_mock.get('http://localhost:8000/health').mock(
        side_effect=httpx.ConnectError('Connection refused')
    )
    return respx_mock


@pytest.fixture
def respx_mock_network_error(respx_mock):
    """Mock httpx client to raise network error."""
    respx_mock.get('http://localhost:8000/health').mock(
        side_effect=httpx.NetworkError('Network unreachable')
    )
    return respx_mock


# ============================================================================
# Prometheus Metrics Fixtures
# ============================================================================

@pytest.fixture
def expected_prometheus_metrics_healthy() -> list[str]:
    """Expected Prometheus metrics for healthy system."""
    return [
        'mcp_healthy 1',
        'mcp_server_count 1',
        'mcp_total_connections 5',
        'mcp_active_connections 3',
        'mcp_success_rate 98.5',
        'mcp_avg_response_time 0.15',
        'mcp_server_active_connections{server="thoth-mcp"} 3',
        'mcp_server_total_requests{server="thoth-mcp"} 150',
        'mcp_server_failed_requests{server="thoth-mcp"} 2',
        'mcp_server_success_rate{server="thoth-mcp"} 98.7',
        'mcp_server_response_time{server="thoth-mcp"} 0.12',
        'mcp_server_healthy{server="thoth-mcp"} 1',
    ]


@pytest.fixture
def expected_prometheus_metrics_unhealthy() -> list[str]:
    """Expected Prometheus metrics for unhealthy system."""
    return [
        'mcp_healthy 0',
        'mcp_server_count 0',
        'mcp_total_connections 0',
        'mcp_active_connections 0',
        'mcp_success_rate 0.0',
        'mcp_avg_response_time 0.0',
    ]


@pytest.fixture
def sample_prometheus_metrics_text() -> str:
    """Sample Prometheus metrics in text format."""
    return """mcp_healthy 1
mcp_server_count 2
mcp_total_connections 10
mcp_active_connections 7
mcp_success_rate 97.5
mcp_avg_response_time 0.18
mcp_server_active_connections{server="thoth-mcp-1"} 5
mcp_server_total_requests{server="thoth-mcp-1"} 300
mcp_server_failed_requests{server="thoth-mcp-1"} 5
mcp_server_success_rate{server="thoth-mcp-1"} 98.3
mcp_server_response_time{server="thoth-mcp-1"} 0.15
mcp_server_healthy{server="thoth-mcp-1"} 1
mcp_server_active_connections{server="thoth-mcp-2"} 2
mcp_server_total_requests{server="thoth-mcp-2"} 150
mcp_server_failed_requests{server="thoth-mcp-2"} 10
mcp_server_success_rate{server="thoth-mcp-2"} 93.3
mcp_server_response_time{server="thoth-mcp-2"} 0.22
mcp_server_healthy{server="thoth-mcp-2"} 1"""


# ============================================================================
# Alert Threshold Fixtures
# ============================================================================

@pytest.fixture
def default_alert_thresholds() -> dict[str, float]:
    """Default alert thresholds matching MCPMonitor configuration."""
    return {
        'success_rate_min': 0.95,
        'response_time_max': 5.0,
        'connection_failure_max': 10,
    }


@pytest.fixture
def strict_alert_thresholds() -> dict[str, float]:
    """Stricter alert thresholds for testing edge cases."""
    return {
        'success_rate_min': 0.99,
        'response_time_max': 1.0,
        'connection_failure_max': 3,
    }


@pytest.fixture
def relaxed_alert_thresholds() -> dict[str, float]:
    """Relaxed alert thresholds for testing."""
    return {
        'success_rate_min': 0.80,
        'response_time_max': 10.0,
        'connection_failure_max': 50,
    }


# ============================================================================
# Cache Refresh Fixtures
# ============================================================================

@pytest.fixture
def successful_cache_refresh() -> dict[str, Any]:
    """Successful cache refresh result."""
    return {
        'success': True,
        'message': 'Tools are registered directly with Letta - no cache to refresh',
        'timestamp': time.time(),
    }


@pytest.fixture
def failed_cache_refresh() -> dict[str, Any]:
    """Failed cache refresh result."""
    return {
        'success': False,
        'error': 'Connection to Letta service failed',
        'timestamp': time.time(),
    }


# ============================================================================
# Time-based Fixtures
# ============================================================================

@pytest.fixture
def recent_timestamp() -> float:
    """Timestamp from 5 seconds ago."""
    return time.time() - 5.0


@pytest.fixture
def old_timestamp() -> float:
    """Timestamp from 1 hour ago."""
    return time.time() - 3600.0


@pytest.fixture
def future_timestamp() -> float:
    """Timestamp 1 hour in the future (for testing validation)."""
    return time.time() + 3600.0


# ============================================================================
# Mock AsyncClient Fixtures
# ============================================================================

@pytest.fixture
def mock_async_client_healthy():
    """Mock httpx AsyncClient that returns healthy responses."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {'status': 'healthy'}
    mock_client.get.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_async_client_unhealthy():
    """Mock httpx AsyncClient that returns unhealthy responses."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 503
    mock_response.json.return_value = {'status': 'unhealthy'}
    mock_client.get.return_value = mock_response
    return mock_client


@pytest.fixture
def mock_async_client_timeout():
    """Mock httpx AsyncClient that raises timeout errors."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.TimeoutException('Request timeout')
    return mock_client


@pytest.fixture
def mock_async_client_connection_error():
    """Mock httpx AsyncClient that raises connection errors."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ConnectError('Connection refused')
    return mock_client


@pytest.fixture
def mock_async_client_network_error():
    """Mock httpx AsyncClient that raises network errors."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.NetworkError('Network unreachable')
    return mock_client
