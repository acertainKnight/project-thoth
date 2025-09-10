"""
Main FastAPI application for Thoth server.

This module creates the FastAPI application and includes all router modules.
It serves as the central entry point for the refactored API server.
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

from thoth.mcp.monitoring import mcp_health_router
from thoth.server.chat_models import ChatPersistenceManager
from thoth.server.routers import (
    agent,
    chat,
    config,
    health,
    operations,
    research,
    tools,
    websocket,
)
from thoth.services.llm_router import LLMRouter
from thoth.utilities.config import get_config

# Module-level variables to store configuration
pdf_dir: Path = None
notes_dir: Path = None
base_url: str = None
current_config: dict[str, Any] = {}

# Service manager initialized when the server starts
service_manager = None

# Global agent instance - will be initialized when server starts
research_agent = None
agent_adapter = None
llm_router = None

# Chat persistence manager - will be initialized when server starts
chat_manager: ChatPersistenceManager = None


async def shutdown_mcp_server(timeout: float = 10.0) -> None:
    """Gracefully shutdown the MCP server background task."""
    if not hasattr(_start_mcp_server_background, '_background_tasks'):
        logger.info('No MCP server tasks to shutdown')
        return

    mcp_tasks = _start_mcp_server_background._background_tasks.copy()
    if not mcp_tasks:
        logger.info('No MCP server tasks running')
        return

    logger.info(f'Shutting down {len(mcp_tasks)} MCP server tasks...')

    # Cancel all MCP tasks gracefully
    for task in mcp_tasks:
        if not task.done():
            task.cancel()

    # Wait for tasks to complete with timeout, handling cancellation properly
    try:
        results = await asyncio.wait_for(
            asyncio.gather(*mcp_tasks, return_exceptions=True), timeout=timeout
        )
        # Check results for any non-CancelledError exceptions
        for result in results:
            if isinstance(result, Exception) and not isinstance(
                result, asyncio.CancelledError
            ):
                logger.warning(f'MCP task shutdown with exception: {result}')
        logger.info('MCP server tasks shutdown gracefully')
    except TimeoutError:
        logger.warning(f'MCP server tasks did not shutdown within {timeout}s')
    except asyncio.CancelledError:
        logger.info('MCP server shutdown was cancelled')
    except Exception as e:
        logger.error(f'Error shutting down MCP server tasks: {e}')

    # Clear the set
    _start_mcp_server_background._background_tasks.clear()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Handle FastAPI application lifespan events."""
    # Startup
    logger.info('Starting Thoth server application...')
    try:
        yield
    except asyncio.CancelledError:
        # Handle graceful cancellation during shutdown
        logger.info('Application lifespan cancelled, proceeding with shutdown...')
    finally:
        # Shutdown
        logger.info('Shutting down Thoth server application...')
        try:
            await websocket.shutdown_background_tasks(timeout=5.0)
            await shutdown_mcp_server(timeout=5.0)
        except asyncio.CancelledError:
            logger.info('Shutdown tasks cancelled, forcing cleanup...')
        except Exception as e:
            logger.error(f'Error during application shutdown: {e}')


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title='Thoth Obsidian Integration',
        description='API for integrating Thoth with Obsidian',
        version='0.1.0',
        lifespan=lifespan,
    )

    # Add CORS middleware to allow requests from Obsidian
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],  # Allow requests from any origin (including Obsidian)
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
        allow_headers=['*'],
    )

    # Include routers with proper prefixes
    app.include_router(health.router, tags=['health'])
    app.include_router(
        mcp_health_router, tags=['mcp-health']
    )  # Enterprise MCP monitoring
    app.include_router(websocket.router, tags=['websocket'])
    app.include_router(chat.router, prefix='/chat', tags=['chat'])
    app.include_router(agent.router, prefix='/agents', tags=['agent'])
    app.include_router(research.router, prefix='/research', tags=['research'])
    app.include_router(config.router, prefix='/config', tags=['config'])
    app.include_router(operations.router, prefix='/operations', tags=['operations'])
    app.include_router(tools.router, prefix='/tools', tags=['tools'])

    return app


async def _start_mcp_server_background() -> None:
    """Start the MCP server in the background."""
    if not hasattr(_start_mcp_server_background, '_background_tasks'):
        _start_mcp_server_background._background_tasks = set()

    try:
        logger.info('Starting MCP server in background...')

        # Import here to avoid circular dependencies
        from thoth.mcp.server import start_mcp_server

        # Start MCP server
        task = asyncio.create_task(start_mcp_server())
        _start_mcp_server_background._background_tasks.add(task)

        # Clean up completed tasks
        task.add_done_callback(_start_mcp_server_background._background_tasks.discard)

        logger.info('MCP server background task started')

    except Exception as e:
        logger.error(f'Failed to start MCP server in background: {e}')


async def start_server(
    host: str = '127.0.0.1',
    port: int = 8000,
    auto_start_mcp: bool = True,
    **kwargs,  # noqa: ARG001
) -> None:
    """
    Start the Thoth server with all necessary components.

    Args:
        host: Server host address
        port: Server port number
        auto_start_mcp: Whether to start the MCP server automatically
        **kwargs: Additional configuration options
    """
    global \
        service_manager, \
        research_agent, \
        chat_manager, \
        pdf_dir, \
        notes_dir, \
        base_url, \
        current_config

    try:
        # Get configuration
        config = get_config()
        current_config = config.model_dump()

        # Set up directories
        pdf_dir = config.pdf_dir
        notes_dir = config.notes_dir
        base_url = f'http://{host}:{port}'

        logger.info(f'Starting Thoth server on {base_url}')
        logger.info(f'PDF directory: {pdf_dir}')
        logger.info(f'Notes directory: {notes_dir}')

        # Initialize service manager
        from thoth.services.service_manager import ServiceManager

        service_manager = ServiceManager()

        # Initialize LLM router
        llm_router = LLMRouter(config)  # noqa: F841

        # Initialize chat persistence manager
        try:
            chat_manager = ChatPersistenceManager(
                storage_path=config.agent_storage_dir / 'chat_sessions.db'
            )
            logger.info('Chat persistence manager initialized')
        except Exception as e:
            logger.warning(f'Failed to initialize chat manager: {e}')
            chat_manager = None

        # Start MCP server FIRST if requested
        if auto_start_mcp:
            await _start_mcp_server_background()
            # Give the MCP server a moment to start up
            import asyncio

            await asyncio.sleep(2)

        # Initialize research agent (after MCP server is running)
        try:
            from thoth.ingestion.agent_v2.core.agent import (
                create_research_assistant_async,
            )

            research_agent = await create_research_assistant_async(
                service_manager=service_manager
            )
            logger.info('Research agent initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize research agent: {e}')
            research_agent = None

        # Initialize Letta orchestrator for agent management
        thoth_orchestrator = None
        try:
            from thoth.agents.orchestrator import ThothOrchestrator

            thoth_orchestrator = ThothOrchestrator(
                service_manager=service_manager, workspace_dir=config.agent_storage_dir
            )
            await thoth_orchestrator.setup()
            logger.info('Thoth orchestrator initialized successfully')
        except Exception as e:
            logger.warning(f'Failed to initialize Thoth orchestrator: {e}')
            thoth_orchestrator = None

        # Set up router dependencies
        health.set_directories(pdf_dir, notes_dir, base_url)
        websocket.set_dependencies(service_manager, research_agent, chat_manager)
        chat.set_chat_manager(chat_manager)
        agent.set_dependencies(research_agent, current_config, thoth_orchestrator)
        research.set_dependencies(research_agent, chat_manager)
        operations.set_service_manager(service_manager)
        tools.set_dependencies(research_agent, service_manager)

        logger.info('Thoth server initialization completed successfully')

    except Exception as e:
        logger.error(f'Failed to initialize Thoth server: {e}')
        raise


def start_obsidian_server(
    host: str = '127.0.0.1',
    port: int = 8000,
    auto_start_mcp: bool = True,
    **kwargs,
) -> None:
    """
    Start the Thoth server for Obsidian integration (synchronous entry point).

    Args:
        host: Server host address
        port: Server port number
        auto_start_mcp: Whether to start the MCP server automatically
        **kwargs: Additional configuration options
    """

    async def async_main():
        """Async main function to initialize and start the server."""
        # Initialize the server components
        await start_server(
            host=host, port=port, auto_start_mcp=auto_start_mcp, **kwargs
        )

        # Create the FastAPI app
        app = create_app()

        # Configure uvicorn
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level='info',
            access_log=True,
        )

        server = uvicorn.Server(config)

        # Set up signal handlers for graceful shutdown
        def signal_handler(signum, frame):  # noqa: ARG001
            logger.info(f'Received signal {signum}, initiating shutdown...')
            server.should_exit = True

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        try:
            await server.serve()
        except KeyboardInterrupt:
            logger.info('Server stopped by user')
        except Exception as e:
            logger.error(f'Server error: {e}')
            raise

    # Run the async main function
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info('Server interrupted by user')
    except Exception as e:
        logger.error(f'Failed to start server: {e}')
        sys.exit(1)


# Create the app instance for direct use
app = create_app()

# Export the main functions
__all__ = ['app', 'create_app', 'start_obsidian_server', 'start_server']
