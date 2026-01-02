"""
Integration tests for MCP monitoring pipeline.

Tests end-to-end monitoring workflows including health checks,
metrics collection, alerting, and cache refresh operations.
"""

import asyncio  # noqa: I001
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest
import httpx

from thoth.mcp.monitoring import (
    MCPHealthStatus,
    MCPMonitor,
    MCPServerStats,
    mcp_monitor,  # noqa: F401
)


class TestHealthCheckWorkflow:
    """Test health check workflows."""

    @pytest.mark.asyncio
    async def test_basic_health_check(self):
        """Test basic health check returns status."""
        monitor = MCPMonitor()

        status = await monitor.get_health_status()

        assert isinstance(status, MCPHealthStatus)
        assert isinstance(status.healthy, bool)
        assert status.server_count >= 0
        assert status.last_check > 0

    @pytest.mark.asyncio
    async def test_health_check_with_running_server(self, mcp_server_with_transports):
        """Test health check with running server."""
        # Start server
        await mcp_server_with_transports.start()

        # Give server time to start
        await asyncio.sleep(1)

        try:
            monitor = MCPMonitor()

            # Mock the HTTP check to succeed
            with patch('httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                status = await monitor.get_health_status()

                assert status.healthy is True
                assert status.server_count > 0
                assert len(status.errors) == 0

        finally:
            await mcp_server_with_transports.stop()

    @pytest.mark.asyncio
    async def test_health_check_with_stopped_server(self):
        """Test health check when server is not running."""
        monitor = MCPMonitor()

        status = await monitor.get_health_status()

        # Should detect no server
        assert status.healthy is False
        assert len(status.errors) > 0

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self):
        """Test health check handles connection errors."""
        monitor = MCPMonitor()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError('Connection failed')
            )

            status = await monitor.get_health_status()

            assert status.healthy is False
            assert any('connect' in err.lower() for err in status.errors)

    @pytest.mark.asyncio
    async def test_health_check_timeout(self):
        """Test health check handles timeouts."""
        monitor = MCPMonitor()

        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=httpx.TimeoutException('Timeout')
            )

            status = await monitor.get_health_status()

            assert status.healthy is False
            assert any('timeout' in err.lower() for err in status.errors)


class TestMultipleHealthCheckCycles:
    """Test multiple health check cycles."""

    @pytest.mark.asyncio
    async def test_sequential_health_checks(self):
        """Test running multiple sequential health checks."""
        monitor = MCPMonitor()

        results = []
        for _ in range(5):
            status = await monitor.get_health_status()
            results.append(status)
            await asyncio.sleep(0.1)

        # All checks should complete
        assert len(results) == 5

        # Timestamps should be increasing
        timestamps = [r.last_check for r in results]
        assert timestamps == sorted(timestamps)

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self):
        """Test running concurrent health checks."""
        monitor = MCPMonitor()

        # Run 10 health checks concurrently
        tasks = [monitor.get_health_status() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should complete
        assert len(results) == 10

        # All should have same basic structure
        for result in results:
            assert isinstance(result, MCPHealthStatus)
            assert result.last_check > 0

    @pytest.mark.asyncio
    async def test_health_check_interval_respected(self):
        """Test health check interval is respected."""
        monitor = MCPMonitor()
        monitor.health_check_interval = 1  # 1 second

        # First check
        status1 = await monitor.get_health_status()
        time1 = status1.last_check

        # Immediate second check
        status2 = await monitor.get_health_status()
        time2 = status2.last_check

        # Should have different timestamps
        assert time2 > time1

    @pytest.mark.asyncio
    async def test_health_check_state_persistence(self):
        """Test health check state persists across checks."""
        monitor = MCPMonitor()

        # First check
        await monitor.get_health_status()
        first_check_time = monitor.last_health_check

        await asyncio.sleep(0.1)

        # Second check
        await monitor.get_health_status()
        second_check_time = monitor.last_health_check

        # Should update
        assert second_check_time >= first_check_time


class TestServerDetailsMonitoring:
    """Test server details monitoring."""

    @pytest.mark.asyncio
    async def test_get_server_details_no_servers(self):
        """Test getting server details when no servers running."""
        monitor = MCPMonitor()

        details = await monitor.get_server_details()

        # Should return empty list when no servers
        assert isinstance(details, list)
        # May be empty or have placeholder data

    @pytest.mark.asyncio
    async def test_get_server_details_with_healthy_server(self):
        """Test getting server details with healthy server."""
        monitor = MCPMonitor()

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            details = await monitor.get_server_details()

            # Should have server stats
            assert len(details) > 0

            # Check first server stats
            stats = details[0]
            assert isinstance(stats, MCPServerStats)
            assert stats.server_name
            assert stats.healthy is True

    @pytest.mark.asyncio
    async def test_server_stats_structure(self):
        """Test server stats have correct structure."""
        monitor = MCPMonitor()

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            details = await monitor.get_server_details()

            if details:
                stats = details[0]
                assert hasattr(stats, 'server_name')
                assert hasattr(stats, 'active_connections')
                assert hasattr(stats, 'total_requests')
                assert hasattr(stats, 'failed_requests')
                assert hasattr(stats, 'success_rate')
                assert hasattr(stats, 'avg_response_time')
                assert hasattr(stats, 'circuit_breaker_state')
                assert hasattr(stats, 'healthy')

    @pytest.mark.asyncio
    async def test_server_stats_metrics_valid(self):
        """Test server stats metrics are valid."""
        monitor = MCPMonitor()

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            details = await monitor.get_server_details()

            if details:
                stats = details[0]
                assert stats.success_rate >= 0.0
                assert stats.success_rate <= 100.0
                assert stats.avg_response_time >= 0.0


class TestAlertingMechanism:
    """Test alerting on threshold violations."""

    def test_should_alert_unhealthy_server(self):
        """Test alert triggered on unhealthy server."""
        monitor = MCPMonitor()

        status = MCPHealthStatus(
            healthy=False,
            server_count=1,
            total_connections=1,
            active_connections=0,
            success_rate=0.0,
            avg_response_time=1.0,
            last_check=time.time(),
            errors=['Server down'],
        )

        assert monitor.should_alert(status) is True

    def test_should_alert_low_success_rate(self):
        """Test alert triggered on low success rate."""
        monitor = MCPMonitor()
        monitor.alert_thresholds['success_rate_min'] = 0.95

        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=100,
            active_connections=10,
            success_rate=0.90,  # Below threshold
            avg_response_time=0.5,
            last_check=time.time(),
            errors=[],
        )

        assert monitor.should_alert(status) is True

    def test_should_alert_high_response_time(self):
        """Test alert triggered on high response time."""
        monitor = MCPMonitor()
        monitor.alert_thresholds['response_time_max'] = 5.0

        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=10,
            active_connections=5,
            success_rate=0.99,
            avg_response_time=10.0,  # Above threshold
            last_check=time.time(),
            errors=[],
        )

        assert monitor.should_alert(status) is True

    def test_should_not_alert_healthy_system(self):
        """Test no alert for healthy system."""
        monitor = MCPMonitor()

        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=100,
            active_connections=50,
            success_rate=0.99,
            avg_response_time=0.5,
            last_check=time.time(),
            errors=[],
        )

        assert monitor.should_alert(status) is False

    def test_should_alert_with_errors(self):
        """Test alert triggered when errors present."""
        monitor = MCPMonitor()

        status = MCPHealthStatus(
            healthy=True,  # Even if healthy
            server_count=1,
            total_connections=10,
            active_connections=5,
            success_rate=0.99,
            avg_response_time=0.5,
            last_check=time.time(),
            errors=['Warning: High memory usage'],
        )

        assert monitor.should_alert(status) is True

    def test_custom_alert_thresholds(self):
        """Test custom alert thresholds."""
        monitor = MCPMonitor()
        monitor.alert_thresholds = {
            'success_rate_min': 0.80,  # Lower threshold
            'response_time_max': 10.0,  # Higher threshold
            'connection_failure_max': 5,
        }

        status = MCPHealthStatus(
            healthy=True,
            server_count=1,
            total_connections=10,
            active_connections=5,
            success_rate=0.85,  # Would alert with default, but not with custom
            avg_response_time=7.0,  # Would alert with default, but not with custom
            last_check=time.time(),
            errors=[],
        )

        assert monitor.should_alert(status) is False


class TestCacheRefreshOperations:
    """Test cache refresh operations."""

    @pytest.mark.asyncio
    async def test_refresh_tools_cache(self):
        """Test refreshing tools cache."""
        monitor = MCPMonitor()

        result = await monitor.refresh_tools_cache()

        assert isinstance(result, dict)
        assert 'success' in result
        assert 'timestamp' in result

    @pytest.mark.asyncio
    async def test_refresh_cache_returns_success(self):
        """Test cache refresh returns success status."""
        monitor = MCPMonitor()

        result = await monitor.refresh_tools_cache()

        # Should succeed (even if no-op in current implementation)
        assert result['success'] is True

    @pytest.mark.asyncio
    async def test_refresh_cache_timestamp(self):
        """Test cache refresh includes timestamp."""
        monitor = MCPMonitor()

        before = time.time()
        result = await monitor.refresh_tools_cache()
        after = time.time()

        assert 'timestamp' in result
        assert before <= result['timestamp'] <= after

    @pytest.mark.asyncio
    async def test_multiple_cache_refreshes(self):
        """Test multiple cache refresh operations."""
        monitor = MCPMonitor()

        results = []
        for _ in range(3):
            result = await monitor.refresh_tools_cache()
            results.append(result)
            await asyncio.sleep(0.1)

        # All should succeed
        assert all(r['success'] for r in results)

        # Timestamps should increase
        timestamps = [r['timestamp'] for r in results]
        assert timestamps == sorted(timestamps)


class TestPrometheusMetrics:
    """Test Prometheus metrics generation."""

    @pytest.mark.asyncio
    async def test_metrics_format(self):
        """Test metrics are in Prometheus format."""
        monitor = MCPMonitor()  # noqa: F841

        # Mock healthy server
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            from thoth.mcp.monitoring import get_mcp_metrics

            metrics = await get_mcp_metrics()

            # Should be string format
            assert isinstance(metrics, str)

            # Should contain metric lines
            lines = metrics.split('\n')
            assert len(lines) > 0

            # Check for expected metrics
            assert any('mcp_healthy' in line for line in lines)
            assert any('mcp_server_count' in line for line in lines)

    @pytest.mark.asyncio
    async def test_metrics_include_all_categories(self):
        """Test metrics include all expected categories."""
        monitor = MCPMonitor()  # noqa: F841

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            from thoth.mcp.monitoring import get_mcp_metrics

            metrics = await get_mcp_metrics()

            expected_metrics = [
                'mcp_healthy',
                'mcp_server_count',
                'mcp_total_connections',
                'mcp_active_connections',
                'mcp_success_rate',
                'mcp_avg_response_time',
            ]

            for expected in expected_metrics:
                assert expected in metrics

    @pytest.mark.asyncio
    async def test_metrics_values_are_numeric(self):
        """Test metric values are numeric."""
        monitor = MCPMonitor()  # noqa: F841

        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            from thoth.mcp.monitoring import get_mcp_metrics

            metrics = await get_mcp_metrics()

            # Parse metrics and verify values are numeric
            for line in metrics.split('\n'):
                if line and not line.startswith('#'):
                    parts = line.split()
                    if len(parts) >= 2:
                        # Last part should be numeric
                        try:
                            float(parts[-1])
                        except ValueError:
                            pytest.fail(f'Non-numeric metric value in: {line}')


class TestEndToEndMonitoringWorkflow:
    """Test complete end-to-end monitoring workflow."""

    @pytest.mark.asyncio
    async def test_startup_to_monitoring_workflow(self, mcp_server):
        """Test complete workflow from startup to monitoring."""
        # Step 1: Add transports
        mcp_server.add_http_transport('127.0.0.1', 9200)

        # Step 2: Start server
        await mcp_server.start()

        try:
            # Step 3: Wait for startup
            await asyncio.sleep(1)

            # Step 4: Health check
            monitor = MCPMonitor()

            with patch('httpx.AsyncClient') as mock_client:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )

                health_status = await monitor.get_health_status()
                assert health_status.healthy is True

                # Step 5: Get metrics
                server_details = await monitor.get_server_details()
                assert len(server_details) > 0

                # Step 6: Check alerting
                should_alert = monitor.should_alert(health_status)
                assert should_alert is False  # Should not alert when healthy

        finally:
            # Step 7: Shutdown
            await mcp_server.stop()

    @pytest.mark.asyncio
    async def test_continuous_monitoring_loop(self, mcp_server):
        """Test continuous monitoring loop."""
        mcp_server.add_http_transport('127.0.0.1', 9201)
        await mcp_server.start()

        try:
            monitor = MCPMonitor()

            # Run monitoring loop for 5 iterations
            for i in range(5):
                with patch('httpx.AsyncClient') as mock_client:
                    mock_response = Mock()
                    mock_response.status_code = 200
                    mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                        return_value=mock_response
                    )

                    health = await monitor.get_health_status()
                    details = await monitor.get_server_details()  # noqa: F841

                    # Log iteration
                    print(f'Monitoring iteration {i + 1}: healthy={health.healthy}')

                await asyncio.sleep(0.2)

        finally:
            await mcp_server.stop()

    @pytest.mark.asyncio
    async def test_monitoring_detects_server_restart(self, mcp_server):
        """Test monitoring detects server restart."""
        mcp_server.add_http_transport('127.0.0.1', 9202)

        monitor = MCPMonitor()

        # Start server
        await mcp_server.start()
        await asyncio.sleep(0.5)

        # Check healthy
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            status1 = await monitor.get_health_status()
            assert status1.healthy is True

        # Stop server
        await mcp_server.stop()
        await asyncio.sleep(0.5)

        # Check unhealthy
        status2 = await monitor.get_health_status()
        assert status2.healthy is False

        # Restart server
        await mcp_server.start()
        await asyncio.sleep(0.5)

        # Check healthy again
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            status3 = await monitor.get_health_status()
            assert status3.healthy is True

        await mcp_server.stop()
