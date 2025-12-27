"""
Main FastAPI application for Thoth server.

This module creates the FastAPI application and includes all router modules.
It serves as the central entry point for the refactored API server.
"""

import asyncio
import os
import signal
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI
from loguru import logger
from starlette.middleware.cors import CORSMiddleware

# Optional: MCP monitoring (requires mcp extras)
try:
    from thoth.mcp.monitoring import mcp_health_router
    MCP_HEALTH_AVAILABLE = True
except ImportError:
    mcp_health_router = None  # type: ignore
    MCP_HEALTH_AVAILABLE = False

from thoth.server.chat_models import ChatPersistenceManager

# Optional hot reload for development (requires watchdog package)
try:
    from thoth.server.hot_reload import SettingsFileWatcher
except ImportError:
    SettingsFileWatcher = None  # Not available in all service configurations
from thoth.server.routers import (
    agent,
    browser_workflows,
    chat,
    config as config_router,
    health,
    operations,
    research,
    research_questions,
    tools,
    websocket,
)
from thoth.services.llm_router import LLMRouter
from thoth.config import config
from thoth.discovery.scheduler import DiscoveryScheduler

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

# Global watcher instance for settings hot-reload
_settings_watcher: Optional[SettingsFileWatcher] = None

# Global discovery scheduler instance - will be initialized when server starts
discovery_scheduler: Optional[DiscoveryScheduler] = None

# Global workflow execution service - will be initialized when server starts
workflow_execution_service = None


def _should_enable_hot_reload() -> bool:
    """Check if hot-reload should be enabled."""
    # Enable in Docker or if explicitly requested
    docker_env = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
    hot_reload_enabled = os.getenv('THOTH_HOT_RELOAD', '0') == '1'

    return docker_env or hot_reload_enabled


def _on_settings_reload():
    """Callback when settings are reloaded."""
    logger.info("Settings file changed, reloading configuration...")
    try:
        config.reload_settings()
        logger.success("Configuration reloaded successfully!")
    except Exception as e:
        logger.error(f"Failed to reload configuration: {e}")


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
    global _settings_watcher, discovery_scheduler, workflow_execution_service

    # Startup
    logger.info('Starting Thoth server application...')

    # Initialize settings watcher if enabled
    if _should_enable_hot_reload():
        try:
            settings_file = config.vault_root / '_thoth' / 'settings.json'

            if settings_file.exists():
                logger.info(f"Enabling hot-reload for {settings_file}")
                _settings_watcher = SettingsFileWatcher(
                    settings_file=settings_file,
                    debounce_seconds=2.0,
                    validate_before_reload=True
                )
                _settings_watcher.add_callback(_on_settings_reload)
                _settings_watcher.start()
                logger.success("Settings hot-reload enabled!")
            else:
                logger.warning(f"Settings file not found: {settings_file}")
        except Exception as e:
            logger.error(f"Failed to start settings watcher: {e}")
            logger.warning("Continuing without hot-reload")
    else:
        logger.info("Hot-reload disabled (not in Docker environment)")

    # Initialize PostgreSQL connection pool if postgres service exists
    if service_manager and 'postgres' in service_manager._services:
        try:
            postgres_svc = service_manager._services['postgres']
            await postgres_svc.initialize()
            logger.success("PostgreSQL connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL: {e}")
            logger.warning("Continuing without PostgreSQL (some features may not work)")

    # Initialize WorkflowExecutionService after PostgreSQL is ready
    if service_manager and 'postgres' in service_manager._services:
        try:
            from thoth.discovery.browser.workflow_execution_service import WorkflowExecutionService

            logger.info("Initializing workflow execution service...")
            postgres_svc = service_manager._services['postgres']
            workflow_execution_service = WorkflowExecutionService(
                postgres_service=postgres_svc,
                max_concurrent_browsers=5,
                default_timeout=30000,
                max_retries=3,
            )
            await workflow_execution_service.initialize()
            logger.success("Workflow execution service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize workflow execution service: {e}")
            logger.warning("Continuing without workflow execution service (browser workflows will not work)")
            workflow_execution_service = None

    # Initialize discovery scheduler after PostgreSQL is ready
    if service_manager:
        try:
            from thoth.discovery.discovery_manager import DiscoveryManager

            logger.info("Initializing discovery scheduler...")
            discovery_manager = DiscoveryManager()

            # Get required services for research question scheduling
            research_question_service = None
            discovery_orchestrator = None

            try:
                research_question_service = service_manager.get_service('research_question')
            except Exception as e:
                logger.warning(f"Research question service not available: {e}")

            try:
                discovery_orchestrator = service_manager.get_service('discovery_orchestrator')
            except Exception as e:
                logger.warning(f"Discovery orchestrator service not available: {e}")

            # Get the current running event loop
            event_loop = asyncio.get_running_loop()
            logger.info(f"Passing event loop to scheduler: {event_loop}")

            # Initialize scheduler with optional research question support and event loop
            discovery_scheduler = DiscoveryScheduler(
                discovery_manager=discovery_manager,
                research_question_service=research_question_service,
                discovery_orchestrator=discovery_orchestrator,
                event_loop=event_loop  # Pass event loop for async operations from sync thread
            )

            # Sync scheduler with existing discovery sources
            discovery_scheduler.sync_with_discovery_manager()

            # Start the scheduler
            discovery_scheduler.start()
            logger.success("Discovery scheduler started successfully")

            if research_question_service and discovery_orchestrator:
                logger.info("Research question scheduling enabled")
            else:
                logger.info("Research question scheduling disabled (services not available)")

        except Exception as e:
            logger.error(f"Failed to initialize discovery scheduler: {e}")
            logger.warning("Continuing without discovery scheduler (scheduled discovery will not work)")
            discovery_scheduler = None

    logger.success("API server startup complete")

    try:
        yield
    except asyncio.CancelledError:
        # Handle graceful cancellation during shutdown
        logger.info('Application lifespan cancelled, proceeding with shutdown...')
    finally:
        # Shutdown
        logger.info('Shutting down Thoth server application...')

        # Shutdown workflow execution service
        if workflow_execution_service is not None:
            try:
                logger.info("Shutting down workflow execution service...")
                await workflow_execution_service.shutdown()
                logger.success("Workflow execution service shutdown complete")
            except Exception as e:
                logger.error(f"Error shutting down workflow execution service: {e}")

        # Stop discovery scheduler
        if discovery_scheduler is not None:
            try:
                logger.info("Stopping discovery scheduler...")
                discovery_scheduler.stop()
                logger.success("Discovery scheduler stopped")
            except Exception as e:
                logger.error(f"Error stopping discovery scheduler: {e}")

        # Stop settings watcher
        if _settings_watcher is not None:
            try:
                logger.info("Stopping settings watcher...")
                _settings_watcher.stop()
                logger.success("Settings watcher stopped")
            except Exception as e:
                logger.error(f"Error stopping settings watcher: {e}")

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

    # Include MCP health router if available (requires mcp extras)
    if MCP_HEALTH_AVAILABLE:
        app.include_router(
            mcp_health_router, tags=['mcp-health']
        )  # Enterprise MCP monitoring
        logger.debug("MCP health monitoring enabled")
    else:
        logger.debug("MCP health monitoring not available (requires mcp extras)")

    app.include_router(websocket.router, tags=['websocket'])
    app.include_router(chat.router, prefix='/chat', tags=['chat'])
    app.include_router(agent.router, prefix='/agents', tags=['agent'])
    app.include_router(research.router, prefix='/research', tags=['research'])
    app.include_router(research_questions.router, tags=['research-questions'])  # Week 4: Research question management
    app.include_router(browser_workflows.router, prefix='/api/workflows', tags=['workflows'])  # Browser workflow management
    app.include_router(config_router.router, prefix='/config', tags=['config'])
    app.include_router(operations.router, prefix='/operations', tags=['operations'])
    app.include_router(tools.router, prefix='/tools', tags=['tools'])

    # Add hot-reload health check endpoint
    @app.get("/health/hot-reload")
    async def health_hot_reload():
        """Check hot-reload status."""
        settings_file = config.vault_root / '_thoth' / 'settings.json'
        reload_count = getattr(config, 'reload_callback_count', 0)

        return {
            "enabled": _settings_watcher is not None,
            "settings_file": str(settings_file),
            "callback_count": reload_count,
            "status": "active" if _settings_watcher is not None else "disabled",
            "docker_env": os.getenv('DOCKER_ENV', 'false').lower() == 'true',
            "hot_reload_env": os.getenv('THOTH_HOT_RELOAD', '0') == '1'
        }

    # Add manual reload endpoint for testing
    @app.post("/api/reload-config")
    async def reload_config():
        """Manually trigger config reload (for testing)."""
        try:
            logger.info("Manual config reload requested")
            config.reload_settings()

            # Trigger all registered callbacks if watcher is active
            if _settings_watcher is not None:
                _settings_watcher._trigger_reload()
                callback_count = len(_settings_watcher._callbacks)
                logger.success(f"Config reloaded successfully with {callback_count} callbacks")
                return {
                    "status": "success",
                    "message": f"Config reloaded successfully ({callback_count} callbacks executed)",
                    "timestamp": config._last_reload_time if hasattr(config, '_last_reload_time') else None
                }
            else:
                logger.warning("Manual reload: watcher not active, only config reloaded")
                return {
                    "status": "success",
                    "message": "Config reloaded (hot-reload not enabled, callbacks not executed)",
                    "timestamp": None
                }
        except Exception as e:
            logger.error(f"Manual reload failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": None
            }

    return app


async def _start_mcp_server_background() -> None:
    """Start the MCP server in the background."""
    if not hasattr(_start_mcp_server_background, '_background_tasks'):
        _start_mcp_server_background._background_tasks = set()

    try:
        logger.info('Starting MCP server in background...')

        # Import here to avoid circular dependencies
        import socket

        # Find available port for HTTP MCP server
        def find_free_port(start_port: int = 8001) -> int:
            """Find a free port starting from start_port"""
            for port in range(start_port, start_port + 100):
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('localhost', port))
                        return port
                except OSError:
                    continue
            raise RuntimeError('Could not find a free port')

        # Skip MCP server startup in API - we run it as a separate process
        # This avoids stdio permission errors in local mode
        logger.info('MCP server runs as separate process - skipping background startup')
        return

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
        # config imported globally from thoth.config
        current_config = config.settings.model_dump() if hasattr(config, 'settings') else {}

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
        service_manager.initialize()

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

        # Initialize browser workflow dependencies
        if workflow_execution_service is not None:
            postgres_svc = service_manager._services.get('postgres')
            if postgres_svc:
                browser_workflows.set_dependencies(postgres_svc, workflow_execution_service)
                logger.info('Browser workflow dependencies initialized')
            else:
                logger.warning('PostgreSQL service not available for browser workflows')
        else:
            logger.warning('Workflow execution service not available')

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
