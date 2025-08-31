"""
MCP Connection Monitoring and Health Checks

Provides comprehensive monitoring capabilities for production deployments
including health checks, metrics collection, and alerting integration.
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from .langchain_integration import mcp_tools_manager


class MCPHealthStatus(BaseModel):
    """Health status model for API responses."""

    healthy: bool
    server_count: int
    total_connections: int
    active_connections: int
    success_rate: float
    avg_response_time: float
    last_check: float
    errors: list[str]


class MCPServerStats(BaseModel):
    """Individual server statistics model."""

    server_name: str
    active_connections: int
    total_requests: int
    failed_requests: int
    success_rate: float
    avg_response_time: float
    last_health_check: float
    circuit_breaker_state: str
    healthy: bool


class MCPMonitor:
    """
    Comprehensive monitoring for MCP connections.

    Provides health checks, metrics, and alerting capabilities
    for production deployments.
    """

    def __init__(self):
        self.last_health_check = 0
        self.health_check_interval = 30
        self.alert_thresholds = {
            'success_rate_min': 0.95,
            'response_time_max': 5.0,
            'connection_failure_max': 10,
        }

    async def get_health_status(self) -> MCPHealthStatus:
        """Get comprehensive health status."""
        try:
            # Check if manager is initialized
            if not mcp_tools_manager.initialized:
                return MCPHealthStatus(
                    healthy=False,
                    server_count=0,
                    total_connections=0,
                    active_connections=0,
                    success_rate=0.0,
                    avg_response_time=0.0,
                    last_check=time.time(),
                    errors=['MCP tools manager not initialized'],
                )

            # Get connection statistics
            stats = mcp_tools_manager.get_connection_stats()

            if not stats:
                return MCPHealthStatus(
                    healthy=False,
                    server_count=0,
                    total_connections=0,
                    active_connections=0,
                    success_rate=0.0,
                    avg_response_time=0.0,
                    last_check=time.time(),
                    errors=['No MCP servers configured'],
                )

            # Aggregate statistics
            total_connections = sum(stat['total_requests'] for stat in stats.values())
            active_connections = sum(
                stat['active_connections'] for stat in stats.values()
            )

            # Calculate overall success rate
            total_failed = sum(stat['failed_requests'] for stat in stats.values())
            overall_success_rate = (
                (total_connections - total_failed) / total_connections
                if total_connections > 0
                else 1.0
            )

            # Calculate average response time
            avg_response_times = [
                stat['avg_response_time']
                for stat in stats.values()
                if stat['avg_response_time'] > 0
            ]
            overall_avg_response_time = (
                sum(avg_response_times) / len(avg_response_times)
                if avg_response_times
                else 0.0
            )

            # Check health criteria
            is_healthy = (
                mcp_tools_manager.is_healthy()
                and overall_success_rate >= self.alert_thresholds['success_rate_min']
                and overall_avg_response_time
                <= self.alert_thresholds['response_time_max']
            )

            # Collect any errors
            errors = []
            if overall_success_rate < self.alert_thresholds['success_rate_min']:
                errors.append(f'Low success rate: {overall_success_rate:.2%}')

            if overall_avg_response_time > self.alert_thresholds['response_time_max']:
                errors.append(f'High response time: {overall_avg_response_time:.2f}s')

            if mcp_tools_manager.fallback_mode:
                errors.append('Running in fallback mode')

            self.last_health_check = time.time()

            return MCPHealthStatus(
                healthy=is_healthy,
                server_count=len(stats),
                total_connections=total_connections,
                active_connections=active_connections,
                success_rate=overall_success_rate,
                avg_response_time=overall_avg_response_time,
                last_check=self.last_health_check,
                errors=errors,
            )

        except Exception as e:
            logger.error(f'Health check failed: {e}')
            return MCPHealthStatus(
                healthy=False,
                server_count=0,
                total_connections=0,
                active_connections=0,
                success_rate=0.0,
                avg_response_time=0.0,
                last_check=time.time(),
                errors=[f'Health check error: {e!s}'],
            )

    async def get_server_details(self) -> list[MCPServerStats]:
        """Get detailed statistics for each MCP server."""
        if not mcp_tools_manager.initialized:
            return []

        stats = mcp_tools_manager.get_connection_stats()
        server_details = []

        for server_name, stat in stats.items():
            # Determine circuit breaker state (simplified)
            circuit_state = 'closed'
            if stat['success_rate'] < 0.5:
                circuit_state = 'open'
            elif stat['success_rate'] < 0.8:
                circuit_state = 'half-open'

            server_details.append(
                MCPServerStats(
                    server_name=server_name,
                    active_connections=stat['active_connections'],
                    total_requests=stat['total_requests'],
                    failed_requests=stat['failed_requests'],
                    success_rate=stat['success_rate'],
                    avg_response_time=stat['avg_response_time'],
                    last_health_check=stat['last_health_check'],
                    circuit_breaker_state=circuit_state,
                    healthy=stat['success_rate'] > 0.9,
                )
            )

        return server_details

    def should_alert(self, status: MCPHealthStatus) -> bool:
        """Determine if an alert should be triggered."""
        return (
            not status.healthy
            or status.success_rate < self.alert_thresholds['success_rate_min']
            or status.avg_response_time > self.alert_thresholds['response_time_max']
            or len(status.errors) > 0
        )

    async def refresh_tools_cache(self) -> dict[str, Any]:
        """Force refresh of MCP tools cache."""
        try:
            tools = await mcp_tools_manager.refresh_tools()
            return {
                'success': True,
                'tools_loaded': len(tools),
                'timestamp': time.time(),
            }
        except Exception as e:
            logger.error(f'Failed to refresh tools cache: {e}')
            return {'success': False, 'error': str(e), 'timestamp': time.time()}


# Global monitor instance
mcp_monitor = MCPMonitor()


# FastAPI router for health endpoints
mcp_health_router = APIRouter(prefix='/mcp', tags=['MCP Health'])


@mcp_health_router.get('/health', response_model=MCPHealthStatus)
async def get_mcp_health():
    """Get MCP connection health status."""
    return await mcp_monitor.get_health_status()


@mcp_health_router.get('/servers', response_model=list[MCPServerStats])
async def get_mcp_servers():
    """Get detailed statistics for all MCP servers."""
    return await mcp_monitor.get_server_details()


@mcp_health_router.post('/refresh-cache')
async def refresh_mcp_cache():
    """Force refresh of MCP tools cache."""
    result = await mcp_monitor.refresh_tools_cache()

    if not result['success']:
        raise HTTPException(status_code=500, detail=result['error'])

    return result


@mcp_health_router.get('/metrics')
async def get_mcp_metrics():
    """Get MCP metrics in Prometheus format (for monitoring integration)."""
    status = await mcp_monitor.get_health_status()
    servers = await mcp_monitor.get_server_details()

    # Generate Prometheus-style metrics
    metrics = []

    # Overall metrics
    metrics.append(f'mcp_healthy {int(status.healthy)}')
    metrics.append(f'mcp_server_count {status.server_count}')
    metrics.append(f'mcp_total_connections {status.total_connections}')
    metrics.append(f'mcp_active_connections {status.active_connections}')
    metrics.append(f'mcp_success_rate {status.success_rate}')
    metrics.append(f'mcp_avg_response_time {status.avg_response_time}')

    # Per-server metrics
    for server in servers:
        labels = f'server="{server.server_name}"'
        metrics.append(
            f'mcp_server_active_connections{{{labels}}} {server.active_connections}'
        )
        metrics.append(f'mcp_server_total_requests{{{labels}}} {server.total_requests}')
        metrics.append(
            f'mcp_server_failed_requests{{{labels}}} {server.failed_requests}'
        )
        metrics.append(f'mcp_server_success_rate{{{labels}}} {server.success_rate}')
        metrics.append(
            f'mcp_server_response_time{{{labels}}} {server.avg_response_time}'
        )
        metrics.append(f'mcp_server_healthy{{{labels}}} {int(server.healthy)}')

    return '\n'.join(metrics)
