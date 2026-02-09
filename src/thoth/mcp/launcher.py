"""
MCP Server Launcher

This module provides launchers for the MCP server with different configurations
and transport options.
"""

import asyncio
import sys
from pathlib import Path

from loguru import logger

from thoth.pipeline import ThothPipeline

from .resources import FileResourceProvider, KnowledgeBaseResourceProvider
from .server import create_mcp_server
from .tools import register_all_mcp_tools


async def launch_mcp_server(
    stdio: bool = False,
    http: bool = True,
    http_host: str = 'localhost',
    http_port: int = 8000,
    sse: bool = False,
    sse_host: str = 'localhost',
    sse_port: int = 8001,
    knowledge_base_path: str | None = None,
    file_access_paths: list[str] | None = None,
) -> None:
    """
    Launch the MCP server with specified configuration.

    Args:
        stdio: Enable stdio transport for CLI integration
        http: Enable HTTP transport for web APIs
        http_host: HTTP server host
        http_port: HTTP server port
        sse: Enable Server-Sent Events transport
        sse_host: SSE server host
        sse_port: SSE server port
        knowledge_base_path: Path to knowledge base files
        file_access_paths: List of file system paths to expose as resources
    """
    try:
        # Run database migrations first
        logger.info('Checking for pending database migrations...')
        try:
            from thoth.config import config
            from thoth.migrations.migration_manager import MigrationManager

            # Get database URL from config
            database_url = None
            if hasattr(config, 'secrets') and hasattr(config.secrets, 'database_url'):
                database_url = config.secrets.database_url
            else:
                # Use docker-compose service name
                database_url = (
                    'postgresql://thoth:thoth_password@letta-postgres:5432/thoth'
                )

            migration_manager = MigrationManager(database_url)
            success = await migration_manager.initialize_database()

            if success:
                status = await migration_manager.get_migration_status()
                logger.success(
                    f'✅ Database migrations complete: {status["applied_count"]} applied, '
                    f'{status["pending_count"]} pending'
                )
                if status['last_migration']:
                    last = status['last_migration']
                    logger.info(
                        f'   Current version: {last["version"]} ({last["name"]})'
                    )
            else:
                logger.warning('⚠️  Database migrations failed (continuing anyway)')
        except Exception as e:
            logger.warning(f'Could not run database migrations: {e}')
            logger.warning(
                'Continuing without migrations - manual migration may be needed'
            )

        # Initialize Thoth pipeline and services
        logger.info('Initializing Thoth pipeline...')
        pipeline = ThothPipeline()
        service_manager = pipeline.services

        # Create MCP server
        logger.info('Creating MCP server...')
        server = create_mcp_server(
            service_manager=service_manager,
            enable_stdio=stdio,
            enable_http=http,
            http_host=http_host,
            http_port=http_port,
            enable_sse=sse,
            sse_host=sse_host,
            sse_port=sse_port,
        )

        # Register all MCP tools
        logger.info('Registering MCP tools...')
        register_all_mcp_tools(server.tool_registry)

        # Initialize MCP Servers Manager
        logger.info('Initializing MCP Servers Manager...')
        from thoth.services.mcp_servers_manager import MCPServersManager

        mcp_manager = MCPServersManager()
        mcp_manager.initialize()

        # Add to service manager's internal dict
        service_manager._services['mcp_servers_manager'] = mcp_manager

        # Set dependencies for MCP manager
        from thoth.services.letta_service import LettaService

        letta_service = LettaService()
        letta_service.initialize()
        mcp_manager.set_dependencies(server.tool_registry, letta_service)

        # Load initial config and connect to external MCP servers
        await mcp_manager.load_config()
        await mcp_manager._connect_all_enabled_servers()

        # Start file watcher for hot-reload
        await mcp_manager.start_watching()
        logger.info('MCP Servers Manager initialized and watching for config changes')

        # Setup resource providers
        logger.info('Setting up resource providers...')

        # Add knowledge base resource provider
        if knowledge_base_path and Path(knowledge_base_path).exists():
            kb_provider = KnowledgeBaseResourceProvider(service_manager)
            server.add_resource_provider(kb_provider)
            logger.info(
                f'Added knowledge base resource provider: {knowledge_base_path}'
            )

        # Add file resource providers
        if file_access_paths:
            valid_paths = [p for p in file_access_paths if Path(p).exists()]
            if valid_paths:
                file_provider = FileResourceProvider(
                    base_paths=valid_paths,
                    allowed_extensions=[
                        '.md',
                        '.txt',
                        '.pdf',
                        '.json',
                        '.yaml',
                        '.yml',
                    ],
                )
                server.add_resource_provider(file_provider)
                logger.info(f'Added file resource provider for paths: {valid_paths}')

        # Start the server
        logger.info('Starting MCP server...')
        logger.info(f'Available tools: {len(server.tool_registry.get_tool_names())}')

        if stdio:
            logger.info(' Stdio transport enabled (for CLI integration)')
        if http:
            logger.info(f' HTTP transport enabled at http://{http_host}:{http_port}')
        if sse:
            logger.info(f' SSE transport enabled at http://{sse_host}:{sse_port}')

        await server.start()

        # Keep the server running indefinitely
        logger.info('MCP server is running. Press Ctrl+C to stop.')
        try:
            # Wait forever - this keeps the event loop running for background tasks
            stop_event = asyncio.Event()
            await stop_event.wait()
        except asyncio.CancelledError:
            logger.info('Server cancelled, shutting down gracefully...')
            await server.stop()

    except KeyboardInterrupt:
        logger.info('Received interrupt signal, shutting down...')
        # Stop MCP manager watcher
        if 'mcp_manager' in locals():
            await mcp_manager.stop_watching()
        await server.stop()
    except Exception as e:
        logger.error(f'Error starting MCP server: {e}')
        sys.exit(1)


def run_stdio_server() -> None:
    """
    Run MCP server with stdio transport only (for CLI integration).

    This is the entry point for running the server as a subprocess
    with stdio communication.
    """

    async def main():
        await launch_mcp_server(stdio=True, http=False, sse=False)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('MCP stdio server stopped')


def run_http_server(host: str = 'localhost', port: int = 8000) -> None:
    """
    Run MCP server with HTTP transport only.

    Args:
        host: HTTP server host
        port: HTTP server port
    """

    async def main():
        await launch_mcp_server(
            stdio=False, http=True, http_host=host, http_port=port, sse=False
        )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('MCP HTTP server stopped')


def run_full_server(
    http_host: str = 'localhost',
    http_port: int = 8000,
    sse_port: int = 8001,
    enable_file_access: bool = True,
) -> None:
    """
    Run MCP server with all transports enabled.

    Args:
        http_host: HTTP server host
        http_port: HTTP server port
        sse_port: SSE server port
        enable_file_access: Enable file system resource access
    """
    import os

    async def main():
        # Setup file access paths if enabled
        file_paths = None
        if enable_file_access:
            # Default file access paths
            file_paths = [
                str(Path.cwd()),  # Current working directory
                str(Path.home() / 'Documents'),  # User documents (if exists)
            ]

        # Disable stdio in Docker to avoid permission errors
        enable_stdio = os.getenv('THOTH_DOCKER', '').lower() not in ('1', 'true', 'yes')

        await launch_mcp_server(
            stdio=enable_stdio,
            http=True,
            http_host=http_host,
            http_port=http_port,
            sse=True,
            sse_host=http_host,
            sse_port=sse_port,
            file_access_paths=file_paths,
        )

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('MCP full server stopped')


# CLI entry points that can be used with click or argparse
def main_stdio():
    """Entry point for stdio-only MCP server."""
    run_stdio_server()


def main_http():
    """Entry point for HTTP-only MCP server."""
    import os

    host = os.getenv('MCP_HOST', 'localhost')
    port = int(os.getenv('MCP_PORT', '8000'))
    run_http_server(host, port)


def main_full():
    """Entry point for full MCP server with all transports."""
    import os

    host = os.getenv('MCP_HOST', 'localhost')
    http_port = int(os.getenv('MCP_HTTP_PORT', '8000'))
    sse_port = int(os.getenv('MCP_SSE_PORT', '8001'))
    enable_files = os.getenv('MCP_ENABLE_FILES', 'true').lower() == 'true'

    run_full_server(host, http_port, sse_port, enable_files)


if __name__ == '__main__':
    # Default to full server when run directly
    main_full()
