"""
Comprehensive Unit Tests for MCP Monitoring System

Tests the MCPMonitor class including:
- Health status checks with various server states
- HTTP connection error handling (timeouts, connection errors, network errors)
- Server details retrieval with mock data
- Alert threshold logic validation
- Tools cache refresh operations
- Pydantic model validation
- Edge cases and error conditions
"""

import time  # noqa: I001
from unittest.mock import AsyncMock, Mock, patch  # noqa: F401

import httpx
import pytest
import respx

from thoth.mcp.monitoring import (
    MCPHealthStatus,
    MCPMonitor,
    MCPServerStats,
)


# ============================================================================
# MCPMonitor Initialization Tests
# ============================================================================


class TestMCPMonitorInit:
    """Test MCPMonitor initialization and configuration."""

    def test_monitor_init_default_values(self):
        """Test monitor initializes with correct default values."""
        monitor = MCPMonitor()

        assert monitor.last_health_check == 0
        assert monitor.health_check_interval == 30
        assert monitor.alert_thresholds == {
            'success_rate_min': 95.0,  # Percentage (0-100)
            'response_time_max': 5.0,
            'connection_failure_max': 10,
        }

    def test_monitor_init_alert_thresholds(self):
        """Test alert thresholds are properly initialized."""
        monitor = MCPMonitor()

        assert 'success_rate_min' in monitor.alert_thresholds
        assert 'response_time_max' in monitor.alert_thresholds
        assert 'connection_failure_max' in monitor.alert_thresholds

        # Verify threshold values are reasonable (success_rate is percentage 0-100)
        assert 0 < monitor.alert_thresholds['success_rate_min'] <= 100.0
        assert monitor.alert_thresholds['response_time_max'] > 0
        assert monitor.alert_thresholds['connection_failure_max'] > 0


# ============================================================================
# get_health_status() Tests - Healthy Server
# ============================================================================


class TestGetHealthStatusHealthy:
    """Test get_health_status() with healthy MCP server."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_healthy_server_response(self):
        """Test health status returns healthy when server responds 200."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200, json={'status': 'healthy'})
        )

        monitor = MCPMonitor()
        status = await monitor.get_health_status()

        assert status.healthy is True
        assert status.server_count == 1
        assert status.total_connections == 1
        assert status.active_connections == 1
        assert status.success_rate == 100.0
        assert status.avg_response_time == 0.1
        assert len(status.errors) == 0
        assert status.last_check > 0

    @pytest.mark.asyncio
    async def test_healthy_server_updates_last_check(self):
        """Test health check updates last_check timestamp."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            monitor = MCPMonitor()
            before_time = time.time()
            status = await monitor.get_health_status()
            after_time = time.time()

            assert before_time <= status.last_check <= after_time

    @pytest.mark.asyncio
    async def test_healthy_server_no_errors(self):
        """Test healthy server returns empty error list."""
        with respx.mock:
            respx.get('http://localhost:8000/health').mock(
                return_value=httpx.Response(200)
            )

            monitor = MCPMonitor()
            status = await monitor.get_health_status()

            assert isinstance(status.errors, list)
            assert len(status.errors) == 0


# ============================================================================
# get_health_status() Tests - Unhealthy Server
# ============================================================================


class TestGetHealthStatusUnhealthy:
    """Test get_health_status() with unhealthy MCP server."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_returns_503(self):
        """Test health status when server returns 503 Service Unavailable."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(503, json={'error': 'service unavailable'})
        )

        monitor = MCPMonitor()
        status = await monitor.get_health_status()

        assert status.healthy is False
        assert status.server_count == 0
        assert status.total_connections == 0
        assert status.active_connections == 0
        assert status.success_rate == 0.0
        assert len(status.errors) > 0
        assert 'MCP server returned status 503' in status.errors[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_returns_500(self):
        """Test health status when server returns 500 Internal Server Error."""
        respx.get('http://localhost:8000/health').mock(return_value=httpx.Response(500))

        monitor = MCPMonitor()
        status = await monitor.get_health_status()

        assert status.healthy is False
        assert 'MCP server returned status 500' in status.errors[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_returns_404(self):
        """Test health status when server returns 404 Not Found."""
        respx.get('http://localhost:8000/health').mock(return_value=httpx.Response(404))

        monitor = MCPMonitor()
        status = await monitor.get_health_status()

        assert status.healthy is False
        assert 'MCP server returned status 404' in status.errors[0]


# ============================================================================
# get_health_status() Tests - Connection Errors
# ============================================================================


class TestGetHealthStatusConnectionErrors:
    """Test get_health_status() with various connection errors."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_connection_refused(self):
        """Test health status when connection is refused."""
        respx.get('http://localhost:8000/health').mock(
            side_effect=httpx.ConnectError('Connection refused')
        )

        monitor = MCPMonitor()
        status = await monitor.get_health_status()

        assert status.healthy is False
        assert status.server_count == 0
        assert len(status.errors) > 0
        assert 'Cannot connect to MCP server at localhost:8000' in status.errors[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_timeout_error(self):
        """Test health status when request times out."""
        respx.get('http://localhost:8000/health').mock(
            side_effect=httpx.TimeoutException('Request timeout')
        )

        monitor = MCPMonitor()
        status = await monitor.get_health_status()

        assert status.healthy is False
        assert len(status.errors) > 0
        assert 'MCP server health check timed out' in status.errors[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_network_error(self):
        """Test health status when network is unreachable."""
        respx.get('http://localhost:8000/health').mock(
            side_effect=httpx.NetworkError('Network unreachable')
        )

        monitor = MCPMonitor()
        status = await monitor.get_health_status()

        assert status.healthy is False
        assert len(status.errors) > 0
        assert 'MCP health check error:' in status.errors[0]

    @pytest.mark.asyncio
    @respx.mock
    async def test_generic_http_error(self):
        """Test health status with generic HTTP exception."""
        respx.get('http://localhost:8000/health').mock(
            side_effect=httpx.HTTPError('Generic HTTP error')
        )

        monitor = MCPMonitor()
        status = await monitor.get_health_status()

        assert status.healthy is False
        assert len(status.errors) > 0


# ============================================================================
# get_health_status() Tests - Edge Cases
# ============================================================================


class TestGetHealthStatusEdgeCases:
    """Test get_health_status() edge cases and error conditions."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_malformed_response_json(self):
        """Test health status when server returns malformed JSON."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200, content=b'not json')
        )

        monitor = MCPMonitor()
        # Should still return healthy if status code is 200
        status = await monitor.get_health_status()
        assert status.healthy is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_empty_response(self):
        """Test health status when server returns empty response."""
        respx.get('http://localhost:8000/health').mock(
            return_value=httpx.Response(200, content=b'')
        )

        monitor = MCPMonitor()
        status = await monitor.get_health_status()
        assert status.healthy is True

    @pytest.mark.asyncio
    async def test_exception_during_health_check(self):
        """Test health status when unexpected exception occurs."""
        monitor = MCPMonitor()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.side_effect = RuntimeError('Unexpected error')

            status = await monitor.get_health_status()

            assert status.healthy is False
            assert len(status.errors) > 0
            assert 'MCP health check error:' in status.errors[0]


# ============================================================================
# get_server_details() Tests
# ============================================================================


class TestGetServerDetails:
    """Test get_server_details() with various scenarios."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_details_healthy_server(self):
        """Test server details returns correct stats for healthy server."""
        respx.get('http://localhost:8000/health').mock(return_value=httpx.Response(200))

        monitor = MCPMonitor()
        servers = await monitor.get_server_details()

        assert len(servers) == 1
        server = servers[0]
        assert server.server_name == 'thoth-mcp'
        assert server.healthy is True
        assert server.circuit_breaker_state == 'closed'
        assert server.active_connections > 0
        assert server.success_rate == 100.0

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_details_unhealthy_server(self):
        """Test server details returns empty list for unhealthy server."""
        respx.get('http://localhost:8000/health').mock(
            side_effect=httpx.ConnectError('Connection refused')
        )

        monitor = MCPMonitor()
        servers = await monitor.get_server_details()

        assert isinstance(servers, list)
        assert len(servers) == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_details_includes_timestamps(self):
        """Test server details includes valid timestamp."""
        respx.get('http://localhost:8000/health').mock(return_value=httpx.Response(200))

        monitor = MCPMonitor()
        servers = await monitor.get_server_details()

        assert len(servers) == 1
        assert servers[0].last_health_check > 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_server_details_uses_cached_health_status(self):
        """Test server details uses health status from get_health_status()."""
        respx.get('http://localhost:8000/health').mock(return_value=httpx.Response(200))

        monitor = MCPMonitor()

        # Get health status first
        health_status = await monitor.get_health_status()

        # Get server details
        servers = await monitor.get_server_details()

        assert len(servers) == 1
        assert servers[0].success_rate == health_status.success_rate
        assert servers[0].active_connections == health_status.active_connections


# ============================================================================
# should_alert() Tests
# ============================================================================


class TestShouldAlert:
    """Test should_alert() threshold logic."""

    def test_should_alert_healthy_status(self, healthy_status):
        """Test should_alert returns False for healthy status."""
        monitor = MCPMonitor()
        assert monitor.should_alert(healthy_status) is False

    def test_should_alert_unhealthy_status(self, unhealthy_status):
        """Test should_alert returns True for unhealthy status."""
        monitor = MCPMonitor()
        assert monitor.should_alert(unhealthy_status) is True

    def test_should_alert_low_success_rate(self):
        """Test should_alert returns True when success rate below threshold."""
        monitor = MCPMonitor()
        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=10,
            active_connections=5,
            success_rate=90.0,  # Below 95% threshold
            avg_response_time=0.5,
            last_check=time.time(),
            errors=[],
        )

        assert monitor.should_alert(status) is True

    def test_should_alert_high_response_time(self):
        """Test should_alert returns True when response time exceeds threshold."""
        monitor = MCPMonitor()
        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=10,
            active_connections=5,
            success_rate=99.0,
            avg_response_time=6.0,  # Above 5.0s threshold
            last_check=time.time(),
            errors=[],
        )

        assert monitor.should_alert(status) is True

    def test_should_alert_with_errors(self):
        """Test should_alert returns True when errors present."""
        monitor = MCPMonitor()
        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=10,
            active_connections=5,
            success_rate=99.0,
            avg_response_time=0.5,
            last_check=time.time(),
            errors=['Some error occurred'],
        )

        assert monitor.should_alert(status) is True

    def test_should_alert_edge_case_exact_threshold(self):
        """Test should_alert at exact threshold boundary."""
        monitor = MCPMonitor()
        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=10,
            active_connections=5,
            success_rate=95.0,  # Exactly at threshold
            avg_response_time=5.0,  # Exactly at threshold
            last_check=time.time(),
            errors=[],
        )

        # At exact threshold should not alert
        assert monitor.should_alert(status) is False

    def test_should_alert_multiple_threshold_violations(self):
        """Test should_alert with multiple threshold violations."""
        monitor = MCPMonitor()
        status = MCPHealthStatus(
            healthy=False,
            server_count=0,
            total_connections=0,
            active_connections=0,
            success_rate=50.0,  # Below threshold
            avg_response_time=10.0,  # Above threshold
            last_check=time.time(),
            errors=['Error 1', 'Error 2'],
        )

        assert monitor.should_alert(status) is True


# ============================================================================
# refresh_tools_cache() Tests
# ============================================================================


class TestRefreshToolsCache:
    """Test refresh_tools_cache() functionality."""

    @pytest.mark.asyncio
    async def test_refresh_cache_success(self):
        """Test successful cache refresh."""
        monitor = MCPMonitor()
        result = await monitor.refresh_tools_cache()

        assert result['success'] is True
        assert 'message' in result
        assert 'timestamp' in result
        assert result['timestamp'] > 0
        assert 'no cache to refresh' in result['message'].lower()

    @pytest.mark.asyncio
    async def test_refresh_cache_includes_timestamp(self):
        """Test cache refresh includes valid timestamp."""
        monitor = MCPMonitor()
        before_time = time.time()
        result = await monitor.refresh_tools_cache()
        after_time = time.time()

        assert before_time <= result['timestamp'] <= after_time

    @pytest.mark.asyncio
    async def test_refresh_cache_error_handling(self):
        """Test cache refresh error handling."""
        monitor = MCPMonitor()

        # Patch to simulate error during refresh
        with patch.object(
            monitor, 'refresh_tools_cache', side_effect=Exception('Cache error')
        ):
            try:
                await monitor.refresh_tools_cache()
                pytest.fail('Expected exception to be raised')
            except Exception as e:
                assert 'Cache error' in str(e)


# ============================================================================
# Model Validation Tests - MCPHealthStatus
# ============================================================================


class TestMCPHealthStatusModel:
    """Test MCPHealthStatus Pydantic model validation."""

    def test_health_status_valid_creation(self):
        """Test creating valid MCPHealthStatus instance."""
        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=10,
            active_connections=5,
            success_rate=95.5,
            avg_response_time=0.25,
            last_check=time.time(),
            errors=[],
        )

        assert status.healthy is True
        assert status.server_count == 1
        assert status.total_connections == 10
        assert status.active_connections == 5
        assert status.success_rate == 95.5
        assert status.avg_response_time == 0.25
        assert isinstance(status.errors, list)

    def test_health_status_with_errors(self):
        """Test MCPHealthStatus with error list."""
        errors = ['Error 1', 'Error 2', 'Error 3']
        status = MCPHealthStatus(
            healthy=False,
            server_count=0,
            total_connections=0,
            active_connections=0,
            success_rate=0.0,
            avg_response_time=0.0,
            last_check=time.time(),
            errors=errors,
        )

        assert len(status.errors) == 3
        assert status.errors == errors

    def test_health_status_default_values(self):
        """Test MCPHealthStatus without optional fields."""
        # All fields are required, test with minimal valid values
        status = MCPHealthStatus(
            healthy=False,
            server_count=0,
            total_connections=0,
            active_connections=0,
            success_rate=0.0,
            avg_response_time=0.0,
            last_check=0.0,
            errors=[],
        )

        assert status.healthy is False
        assert status.errors == []

    def test_health_status_type_validation(self):
        """Test MCPHealthStatus validates field types."""
        with pytest.raises((ValueError, TypeError)):
            MCPHealthStatus(
                healthy='not a bool',  # Should be bool
                server_count=1,
                total_connections=10,
                active_connections=5,
                success_rate=95.0,
                avg_response_time=0.25,
                last_check=time.time(),
                errors=[],
            )


# ============================================================================
# Model Validation Tests - MCPServerStats
# ============================================================================


class TestMCPServerStatsModel:
    """Test MCPServerStats Pydantic model validation."""

    def test_server_stats_valid_creation(self):
        """Test creating valid MCPServerStats instance."""
        stats = MCPServerStats(
            server_name='test-server',
            active_connections=5,
            total_requests=100,
            failed_requests=2,
            success_rate=98.0,
            avg_response_time=0.15,
            last_health_check=time.time(),
            circuit_breaker_state='closed',
            healthy=True,
        )

        assert stats.server_name == 'test-server'
        assert stats.active_connections == 5
        assert stats.total_requests == 100
        assert stats.failed_requests == 2
        assert stats.success_rate == 98.0
        assert stats.circuit_breaker_state == 'closed'
        assert stats.healthy is True

    def test_server_stats_unhealthy_server(self):
        """Test MCPServerStats for unhealthy server."""
        stats = MCPServerStats(
            server_name='failing-server',
            active_connections=0,
            total_requests=50,
            failed_requests=25,
            success_rate=50.0,
            avg_response_time=0.0,
            last_health_check=time.time(),
            circuit_breaker_state='open',
            healthy=False,
        )

        assert stats.healthy is False
        assert stats.circuit_breaker_state == 'open'
        assert stats.failed_requests > 0

    def test_server_stats_circuit_breaker_states(self):
        """Test MCPServerStats with different circuit breaker states."""
        for state in ['closed', 'open', 'half-open']:
            stats = MCPServerStats(
                server_name='test-server',
                active_connections=1,
                total_requests=10,
                failed_requests=0,
                success_rate=100.0,
                avg_response_time=0.1,
                last_health_check=time.time(),
                circuit_breaker_state=state,
                healthy=state == 'closed',
            )

            assert stats.circuit_breaker_state == state

    def test_server_stats_type_validation(self):
        """Test MCPServerStats validates field types."""
        with pytest.raises((ValueError, TypeError)):
            MCPServerStats(
                server_name='test',
                active_connections='not an int',  # Should be int
                total_requests=100,
                failed_requests=2,
                success_rate=98.0,
                avg_response_time=0.15,
                last_health_check=time.time(),
                circuit_breaker_state='closed',
                healthy=True,
            )
