"""
LangChain MCP Integration

Provides seamless integration between our enterprise connection manager
and LangChain's MCP adapter tools for production deployments.
"""

import asyncio
from typing import Any

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.tools import load_mcp_tools
from loguru import logger

from .connection_manager import ConnectionConfig, mcp_connection_manager


class PooledMCPToolWrapper:
    """
    Wrapper that makes LangChain MCP tools use our connection pool.

    This ensures all tool calls reuse existing connections instead of
    creating new ones, preventing the "Already initialized" error.

    Note: This is a simple wrapper that delegates to BaseTool instead
    of inheriting from it to avoid Pydantic complexities.
    """

    def __init__(self, original_tool: BaseTool, server_name: str):
        # Store the original tool and server name
        self._original_tool = original_tool
        self._server_name = server_name

        # Expose necessary attributes for LangChain compatibility
        self.name = original_tool.name
        self.description = original_tool.description
        self.args_schema = getattr(original_tool, 'args_schema', None)

        # Copy other attributes that might be needed
        for attr in ['return_direct', 'verbose', 'callbacks', 'tags', 'metadata']:
            if hasattr(original_tool, attr):
                setattr(self, attr, getattr(original_tool, attr))

    def _run(self, *args, **kwargs) -> Any:
        """Synchronous execution (not recommended for async tools)."""
        return asyncio.run(self._arun(*args, **kwargs))

    async def _arun(self, *args, **kwargs) -> Any:
        """Asynchronous execution using pooled connection."""
        try:
            # Use our connection manager instead of creating new connections
            async with mcp_connection_manager.get_session(self._server_name) as session:
                # Get fresh tools from the session
                tools = await load_mcp_tools(session)

                # Find the matching tool
                matching_tool = None
                for tool in tools:
                    if tool.name == self._original_tool.name:
                        matching_tool = tool
                        break

                if not matching_tool:
                    raise RuntimeError(
                        f'Tool {self._original_tool.name} not found in session'
                    )

                # Execute the tool with the pooled session
                if hasattr(matching_tool, '_arun'):
                    return await matching_tool._arun(*args, **kwargs)
                else:
                    return matching_tool._run(*args, **kwargs)

        except Exception as e:
            logger.error(
                f'Pooled tool execution failed for {self._original_tool.name}: {e}'
            )
            raise

    def __getattr__(self, name):
        """Delegate any missing attributes to the original tool."""
        return getattr(self._original_tool, name)


class MCPToolsManager:
    """
    High-level manager for MCP tools integration with LangChain.

    Provides enterprise-grade tool loading with connection pooling,
    fallback mechanisms, and distributed deployment support.
    """

    def __init__(self):
        self.initialized = False
        self.tools_cache: dict[str, list[BaseTool]] = {}
        self.fallback_mode = False

    async def initialize(
        self,
        mcp_host: str = 'localhost',
        mcp_port: int = 8001,
        max_connections: int = 10,
        enable_health_monitoring: bool = True,
    ) -> None:
        """Initialize the MCP tools manager with connection pooling."""
        if self.initialized:
            logger.warning('MCP tools manager already initialized')
            return

        try:
            # Configure connection pool
            config = ConnectionConfig(
                server_name='thoth',
                url=f'http://{mcp_host}:{mcp_port}/mcp',
                transport='streamable_http',
                max_connections=max_connections,
                connection_timeout=30,
                retry_attempts=3,
                retry_delay=1.0,
                health_check_interval=60,
            )

            # Add server to connection manager
            await mcp_connection_manager.add_server(config)

            # Start health monitoring if requested
            if enable_health_monitoring:
                await mcp_connection_manager.start_health_monitoring()

            self.initialized = True
            logger.info('MCP tools manager initialized with connection pooling')

        except Exception as e:
            logger.error(f'Failed to initialize MCP tools manager: {e}')
            self.fallback_mode = True
            raise

    async def get_tools(self, use_cache: bool = True) -> list[BaseTool]:
        """
        Get MCP tools with connection pooling and caching.

        Args:
            use_cache: Whether to use cached tools (recommended for production)

        Returns:
            List of LangChain-compatible tools using pooled connections
        """
        if not self.initialized and not self.fallback_mode:
            raise RuntimeError('MCP tools manager not initialized')

        if self.fallback_mode:
            logger.warning('MCP tools manager in fallback mode - no tools available')
            return []

        cache_key = 'thoth'

        # Check cache first
        if use_cache and cache_key in self.tools_cache:
            logger.debug(f'Returning {len(self.tools_cache[cache_key])} cached tools')
            return self.tools_cache[cache_key]

        try:
            # Get tools from connection manager
            raw_tools = await mcp_connection_manager.get_tools('thoth')

            # The tools are already using connection pooling at the session level
            # No need to wrap them - the connection manager handles pooling
            self.tools_cache[cache_key] = raw_tools

            logger.info(f'Loaded {len(raw_tools)} MCP tools with connection pooling')
            return raw_tools

        except Exception as e:
            logger.error(f'Failed to load MCP tools: {e}')
            # Enable fallback mode on failure
            self.fallback_mode = True
            return []

    async def refresh_tools(self) -> list[BaseTool]:
        """Force refresh of tools cache."""
        self.tools_cache.clear()
        return await self.get_tools(use_cache=False)

    def get_connection_stats(self) -> dict[str, Any]:
        """Get connection pool statistics."""
        if not self.initialized:
            return {}

        stats = mcp_connection_manager.get_all_stats()
        return {
            server: {
                'active_connections': stat.active_connections,
                'total_requests': stat.total_requests,
                'failed_requests': stat.failed_requests,
                'success_rate': (
                    (stat.total_requests - stat.failed_requests) / stat.total_requests
                    if stat.total_requests > 0
                    else 0
                ),
                'avg_response_time': stat.avg_response_time,
                'last_health_check': stat.last_health_check,
            }
            for server, stat in stats.items()
        }

    def is_healthy(self) -> bool:
        """Check if MCP tools are healthy and operational."""
        if not self.initialized or self.fallback_mode:
            return False

        # Check if we have tools cached
        if 'thoth' not in self.tools_cache:
            return False

        # Check connection pool health
        stats = mcp_connection_manager.get_server_stats('thoth')
        if not stats:
            return False

        # Consider healthy if success rate > 90%
        if stats.total_requests > 0:
            success_rate = (
                stats.total_requests - stats.failed_requests
            ) / stats.total_requests
            return success_rate > 0.9

        return True

    async def shutdown(self):
        """Graceful shutdown of MCP tools manager."""
        logger.info('Shutting down MCP tools manager...')

        self.tools_cache.clear()
        self.initialized = False

        await mcp_connection_manager.shutdown()

        logger.info('MCP tools manager shutdown complete')


# Global instance for application use
mcp_tools_manager = MCPToolsManager()
