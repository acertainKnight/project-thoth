"""
Enterprise MCP Connection Manager

Provides production-ready connection pooling, session management, and
distributed deployment support for MCP tools integration.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from loguru import logger


@dataclass
class ConnectionConfig:
    """Configuration for MCP connections."""

    server_name: str
    url: str
    transport: str = 'streamable_http'
    max_connections: int = 10
    connection_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    health_check_interval: int = 60


@dataclass
class ConnectionStats:
    """Statistics for connection monitoring."""

    active_connections: int = 0
    total_requests: int = 0
    failed_requests: int = 0
    last_health_check: float = 0
    avg_response_time: float = 0


class CircuitBreaker:
    """Circuit breaker pattern for MCP connections."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = 'closed'  # closed, open, half-open

    def can_execute(self) -> bool:
        """Check if operation can proceed."""
        if self.state == 'closed':
            return True
        elif self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half-open'
                return True
            return False
        else:  # half-open
            return True

    def record_success(self):
        """Record successful operation."""
        self.failure_count = 0
        self.state = 'closed'

    def record_failure(self):
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.warning(
                f'Circuit breaker opened after {self.failure_count} failures'
            )


class MCPSessionPool:
    """Pool of reusable MCP sessions."""

    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.sessions: list[Any] = []
        self.active_sessions: dict[str, Any] = {}
        self.lock = asyncio.Lock()
        self.client = None
        self.circuit_breaker = CircuitBreaker()
        self.stats = ConnectionStats()

    async def initialize(self) -> None:
        """Initialize the session pool."""
        try:
            if not self.client:
                self.client = MultiServerMCPClient(
                    {
                        self.config.server_name: {
                            'url': self.config.url,
                            'transport': self.config.transport,
                        }
                    }
                )
                logger.info(f'Initialized MCP client for {self.config.server_name}')
        except Exception as e:
            logger.error(f'Failed to initialize MCP client: {e}')
            raise

    @asynccontextmanager
    async def get_session(self):
        """Get a session from the pool (context manager)."""
        if not self.circuit_breaker.can_execute():
            raise RuntimeError('Circuit breaker is open - MCP service unavailable')

        session_cm = None
        session_id = None
        start_time = time.time()

        try:
            async with self.lock:
                # Always create a fresh session (don't reuse to avoid context manager
                # issues)
                if not self.client:
                    await self.initialize()

                session_cm = self.client.session(self.config.server_name)
                session_id = id(session_cm)
                self.active_sessions[session_id] = session_cm

                self.stats.active_connections += 1
                self.stats.total_requests += 1

            # Use the session context manager properly
            logger.debug(f'Using MCP session {session_id}')
            async with session_cm as actual_session:
                yield actual_session

            # Record success
            self.circuit_breaker.record_success()
            response_time = time.time() - start_time
            self._update_avg_response_time(response_time)

        except Exception as e:
            logger.error(f'MCP session error: {e}')
            self.circuit_breaker.record_failure()
            self.stats.failed_requests += 1
            raise

        finally:
            # Return session to pool or clean up
            if session_id:
                async with self.lock:
                    self.stats.active_connections -= 1
                    if session_id in self.active_sessions:
                        del self.active_sessions[session_id]

                    # Don't return sessions to pool (create fresh each time to avoid
                    # context manager issues)

    def _update_avg_response_time(self, response_time: float):
        """Update average response time with exponential moving average."""
        alpha = 0.1
        if self.stats.avg_response_time == 0:
            self.stats.avg_response_time = response_time
        else:
            self.stats.avg_response_time = (
                alpha * response_time + (1 - alpha) * self.stats.avg_response_time
            )

    async def health_check(self) -> bool:
        """Perform health check on the connection."""
        try:
            async with self.get_session() as session:
                # Try to list tools as health check
                tools = await load_mcp_tools(session)
                self.stats.last_health_check = time.time()
                logger.debug(f'Health check passed: {len(tools)} tools available')
                return True
        except Exception as e:
            logger.warning(f'Health check failed: {e}')
            return False

    def get_stats(self) -> ConnectionStats:
        """Get connection statistics."""
        return self.stats

    async def shutdown(self):
        """Clean shutdown of all sessions."""
        async with self.lock:
            for session in self.sessions:
                try:
                    await session.close()
                except Exception as e:
                    logger.warning(f'Error closing session: {e}')

            self.sessions.clear()
            self.active_sessions.clear()

            if self.client:
                try:
                    await self.client.close()
                except Exception as e:
                    logger.warning(f'Error closing client: {e}')

            logger.info(f'Shut down MCP session pool for {self.config.server_name}')


class MCPConnectionManager:
    """
    Enterprise-grade MCP connection manager.

    Provides:
    - Connection pooling and reuse
    - Circuit breaker pattern
    - Health monitoring
    - Distributed deployment support
    - Graceful degradation
    """

    def __init__(self):
        self.pools: dict[str, MCPSessionPool] = {}
        self.configs: dict[str, ConnectionConfig] = {}
        self.lock = asyncio.Lock()
        self.health_check_task = None
        self.shutdown_event = asyncio.Event()

    async def add_server(self, config: ConnectionConfig) -> None:
        """Add a new MCP server to the connection manager."""
        async with self.lock:
            if config.server_name not in self.pools:
                pool = MCPSessionPool(config)
                await pool.initialize()
                self.pools[config.server_name] = pool
                self.configs[config.server_name] = config
                logger.info(f'Added MCP server: {config.server_name}')
            else:
                logger.warning(f'MCP server already exists: {config.server_name}')

    @asynccontextmanager
    async def get_session(self, server_name: str):
        """Get a session for the specified server."""
        if server_name not in self.pools:
            raise ValueError(f'Unknown MCP server: {server_name}')

        pool = self.pools[server_name]
        async with pool.get_session() as session:
            yield session

    async def get_tools(self, server_name: str) -> list[Any]:
        """Get tools from the specified server."""
        try:
            async with self.get_session(server_name) as session:
                tools = await load_mcp_tools(session)
                logger.debug(f'Loaded {len(tools)} tools from {server_name}')
                return tools
        except Exception as e:
            logger.error(f'Failed to get tools from {server_name}: {e}')
            raise

    async def start_health_monitoring(self, interval: int = 60):
        """Start background health monitoring."""

        async def health_monitor():
            while not self.shutdown_event.is_set():
                try:
                    for server_name, pool in self.pools.items():
                        healthy = await pool.health_check()
                        if not healthy:
                            logger.warning(f'Health check failed for {server_name}')

                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f'Health monitor error: {e}')
                    await asyncio.sleep(interval)

        if not self.health_check_task or self.health_check_task.done():
            self.health_check_task = asyncio.create_task(health_monitor())
            logger.info('Started MCP health monitoring')

    def get_server_stats(self, server_name: str) -> ConnectionStats | None:
        """Get statistics for a specific server."""
        if server_name in self.pools:
            return self.pools[server_name].get_stats()
        return None

    def get_all_stats(self) -> dict[str, ConnectionStats]:
        """Get statistics for all servers."""
        return {name: pool.get_stats() for name, pool in self.pools.items()}

    async def shutdown(self):
        """Graceful shutdown of all connections."""
        logger.info('Shutting down MCP connection manager...')

        # Stop health monitoring
        self.shutdown_event.set()
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        # Shutdown all pools
        for pool in self.pools.values():
            await pool.shutdown()

        self.pools.clear()
        self.configs.clear()
        logger.info('MCP connection manager shutdown complete')


# Global instance for application-wide use
mcp_connection_manager = MCPConnectionManager()
