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
from typing import Any

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
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer

    from thoth.server.hot_reload import SettingsFileWatcher
except ImportError:
    SettingsFileWatcher = None  # Not available in all service configurations
    Observer = None
    FileSystemEventHandler = None  # type: ignore[assignment,misc]

# Import routers - browser_workflows is optional (requires playwright)
from thoth.server.routers import (  # noqa: I001
    agent,
    chat,
    config as config_router,
    health,
    mcp_servers,
    models,
    operations,
    research,
    research_questions,
    schema,
    skills,
    tools,
    websocket,
)

# Browser workflows router is optional (requires playwright)
try:
    from thoth.server.routers import browser_workflows

    BROWSER_WORKFLOWS_AVAILABLE = True
except ImportError as e:
    import warnings

    warnings.warn(
        f'Browser workflows not available (missing playwright): {e}',
        ImportWarning,
        stacklevel=2,
    )
    browser_workflows = None
    BROWSER_WORKFLOWS_AVAILABLE = False
from thoth.config import config
from thoth.discovery.scheduler import DiscoveryScheduler
from thoth.services.llm_router import LLMRouter

# Module-level variables to store configuration
pdf_dir: Path = None
notes_dir: Path = None
base_url: str = None
current_config: dict[str, Any] = {}

# Service manager initialized when the server starts
# Global watcher instance for settings hot-reload (kept global for lifecycle management)
_settings_watcher: SettingsFileWatcher | None = None

# Global watcher instance for schema hot-reload (kept global for lifecycle management)
_schema_watcher: SettingsFileWatcher | None = None

# Global watcher for custom prompts hot-reload (kept global for lifecycle)
_prompts_watcher: SettingsFileWatcher | None = None

# Global discovery scheduler instance (kept global for lifecycle management)
discovery_scheduler: DiscoveryScheduler | None = None

# Global workflow execution service (kept global for lifecycle management)
workflow_execution_service = None

# NOTE: The following have been moved to app.state for better thread safety:
# - service_manager (accessed via dependencies.get_service_manager)
# - research_agent (accessed via dependencies.get_research_agent)
# - chat_manager (accessed via dependencies.get_chat_manager)
# - agent_adapter, llm_router (not needed in routers)


def _should_enable_hot_reload() -> bool:
    """Check if hot-reload should be enabled."""
    # Enable in Docker or if explicitly requested
    docker_env = os.getenv('DOCKER_ENV', 'false').lower() == 'true'
    hot_reload_enabled = os.getenv('THOTH_HOT_RELOAD', '0') == '1'

    return docker_env or hot_reload_enabled


def _on_settings_reload():
    """Callback when settings are reloaded."""
    logger.info('Settings file changed, reloading configuration...')
    try:
        config.reload_settings()
        logger.success('Configuration reloaded successfully!')
    except Exception as e:
        logger.error(f'Failed to reload configuration: {e}')


# Track previous model to detect changes
_previous_letta_model: str | None = None


def _on_letta_model_reload(reloaded_config) -> None:
    """Callback to sync Letta agent model when settings change.

    Compares the new model with the previous one and patches all
    Letta agents via the API if it changed.

    Args:
        reloaded_config: The reloaded Config instance.
    """
    global _previous_letta_model

    new_model = reloaded_config.settings.memory.letta.agent_model
    if not new_model or new_model == _previous_letta_model:
        return

    logger.info(
        f'Letta agent model changed: {_previous_letta_model!r} -> {new_model!r}'
    )
    _previous_letta_model = new_model

    # Patch agents in a background thread to avoid blocking the watcher
    import threading

    def _patch_agents():
        import requests as sync_requests

        letta_url = (
            os.environ.get('THOTH_LETTA_URL')
            or os.environ.get('LETTA_BASE_URL')
            or 'http://localhost:8283'
        )
        headers = {'Content-Type': 'application/json'}
        api_key = os.environ.get('LETTA_API_KEY', '')
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        try:
            resp = sync_requests.get(
                f'{letta_url}/v1/agents/', headers=headers, timeout=15
            )
            resp.raise_for_status()
            agents = resp.json()

            patched = 0
            for agent in agents:
                name = agent.get('name', '')
                if not name.startswith('thoth_'):
                    continue
                agent_id = agent['id']
                patch_resp = sync_requests.patch(
                    f'{letta_url}/v1/agents/{agent_id}',
                    headers=headers,
                    json={'llm_config': {'model': new_model}},
                    timeout=15,
                )
                if patch_resp.status_code in (200, 201):
                    patched += 1
                    logger.info(
                        f'Updated model for {name} ({agent_id[:16]}...) -> {new_model}'
                    )
                else:
                    logger.warning(
                        f'Failed to update model for {name}: {patch_resp.status_code}'
                    )

            logger.success(
                f'Letta agent model hot-reload complete: {patched} agent(s) updated'
            )
        except Exception as e:
            logger.error(f'Failed to hot-reload Letta agent model: {e}')

    threading.Thread(target=_patch_agents, daemon=True).start()


def _on_schema_reload():
    """Callback when analysis schema file is reloaded."""
    logger.info('Analysis schema file changed, reloading schema...')
    try:
        # Get schema service from processing service if available
        from thoth.services.service_manager import ServiceManager

        manager = ServiceManager()
        if hasattr(manager, 'processing') and manager.processing:
            schema_service = manager.processing.analysis_schema_service
            schema_service.load_schema(force_reload=True)
            logger.success(
                f'Analysis schema reloaded! Active preset: {schema_service.get_active_preset_name()}'
            )
        else:
            logger.debug('Processing service not available, skipping schema reload')
    except Exception as e:
        logger.error(f'Failed to reload analysis schema: {e}')


def _on_prompts_reload():
    """Callback when custom prompt files are reloaded."""
    logger.info('Custom prompt files changed, reloading prompts...')
    try:
        # Trigger config reload to reload prompt templates
        config.reload_settings()
        logger.success('Custom prompts reloaded!')
    except Exception as e:
        logger.error(f'Failed to reload custom prompts: {e}')


class _PromptsChangeHandler(
    FileSystemEventHandler if FileSystemEventHandler else object
):
    """Handler for file system events on custom prompt files.

    Inherits from watchdog.events.FileSystemEventHandler to provide the
    required dispatch() method that watchdog's Observer calls internally.
    """

    def __init__(self, watcher, prompts_dir: Path):
        super().__init__()
        self.watcher = watcher
        self.prompts_dir = prompts_dir.resolve()

    def on_modified(self, event):
        """Called when a file is modified."""
        if event.is_directory:
            return

        event_path = Path(event.src_path)

        # Only watch .j2 files (Jinja2 templates)
        if event_path.suffix == '.j2':
            logger.debug(f'Prompt file modified: {event_path}')
            self.watcher._schedule_reload()

    def on_created(self, event):
        """Called when a file is created."""
        if event.is_directory:
            return

        event_path = Path(event.src_path)

        if event_path.suffix == '.j2':
            logger.info(f'Prompt file created: {event_path}')
            self.watcher._schedule_reload()

    def on_deleted(self, event):
        """Called when a file is deleted."""
        if event.is_directory:
            return

        event_path = Path(event.src_path)

        if event_path.suffix == '.j2':
            logger.info(f'Prompt file deleted: {event_path}')
            self.watcher._schedule_reload()


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
async def lifespan(app: FastAPI):
    """Handle FastAPI application lifespan events."""
    global \
        _settings_watcher, \
        _schema_watcher, \
        _prompts_watcher, \
        discovery_scheduler, \
        workflow_execution_service

    # Startup
    logger.info('Starting Thoth server application...')

    # Run database migrations first
    try:
        from thoth.migrations.migration_manager import MigrationManager

        # Get database URL from config
        database_url = None
        if hasattr(config, 'secrets') and hasattr(config.secrets, 'database_url'):
            database_url = config.secrets.database_url
        else:
            # Use docker-compose service name
            database_url = 'postgresql://thoth:thoth_password@letta-postgres:5432/thoth'

        logger.info('Checking for pending database migrations...')
        migration_manager = MigrationManager(database_url)
        success = await migration_manager.initialize_database()

        if success:
            status = await migration_manager.get_migration_status()
            logger.success(
                f'Database migrations complete: {status["applied_count"]} applied, '
                f'{status["pending_count"]} pending'
            )
            if status['last_migration']:
                last = status['last_migration']
                logger.info(f'Current version: {last["version"]} ({last["name"]})')
        else:
            logger.warning('Database migrations failed (continuing anyway)')
    except Exception as e:
        logger.warning(f'Could not run database migrations: {e}')
        logger.warning('Continuing without migrations - manual migration may be needed')

    # Initialize settings watcher if enabled
    if _should_enable_hot_reload():
        # Settings file watcher
        try:
            settings_file = config.vault_root / 'thoth' / '_thoth' / 'settings.json'
            if not settings_file.exists():
                settings_file = config.vault_root / '_thoth' / 'settings.json'

            if settings_file.exists():
                logger.info(f'Enabling hot-reload for {settings_file}')
                _settings_watcher = SettingsFileWatcher(
                    settings_file=settings_file,
                    debounce_seconds=2.0,
                    validate_before_reload=True,
                )
                _settings_watcher.add_callback(_on_settings_reload)
                _settings_watcher.start()
                logger.success('Settings hot-reload enabled!')
            else:
                logger.warning(f'Settings file not found: {settings_file}')
        except Exception as e:
            logger.error(f'Failed to start settings watcher: {e}')
            logger.warning('Continuing without settings hot-reload')

        # Analysis schema file watcher
        try:
            schema_file = config.analysis_schema_path

            if schema_file.exists():
                logger.info(f'Enabling hot-reload for {schema_file}')
                _schema_watcher = SettingsFileWatcher(
                    settings_file=schema_file,
                    debounce_seconds=2.0,
                    validate_before_reload=True,
                )
                _schema_watcher.add_callback(_on_schema_reload)
                _schema_watcher.start()
                logger.success('Analysis schema hot-reload enabled!')
            else:
                logger.info(
                    f'Schema file not found yet: {schema_file} (will be created on first use)'
                )
        except Exception as e:
            logger.error(f'Failed to start schema watcher: {e}')
            logger.warning('Continuing without schema hot-reload')

        # Custom prompts directory watcher (only if not using default prompts)
        try:
            prompts_dir = config.prompts_dir
            # Check if prompts_dir is in vault (custom) vs repo (default)
            repo_prompts_dir = (
                Path(__file__).parent.parent.parent / 'templates' / 'prompts'
            )
            is_custom_prompts = prompts_dir.resolve() != repo_prompts_dir.resolve()

            if is_custom_prompts and prompts_dir.exists():
                logger.info(f'Enabling hot-reload for custom prompts: {prompts_dir}')
                # Watch the directory for any .j2 file changes
                _prompts_watcher = SettingsFileWatcher(
                    settings_file=prompts_dir
                    / '.watch_trigger',  # Dummy file for directory watching
                    debounce_seconds=2.0,
                    validate_before_reload=False,  # Don't validate since it's not JSON
                )
                _prompts_watcher.add_callback(_on_prompts_reload)
                # Start watching the directory
                _prompts_watcher._observer = Observer()
                _prompts_watcher._event_handler = _PromptsChangeHandler(
                    watcher=_prompts_watcher, prompts_dir=prompts_dir
                )
                _prompts_watcher._observer.schedule(
                    _prompts_watcher._event_handler, str(prompts_dir), recursive=True
                )
                _prompts_watcher._observer.start()
                _prompts_watcher._is_running = True
                logger.success(
                    f'Custom prompts hot-reload enabled! Watching: {prompts_dir}'
                )
            elif is_custom_prompts:
                logger.info(f'Custom prompts directory not found yet: {prompts_dir}')
            else:
                logger.debug('Using default prompts (no hot-reload needed)')
        except Exception as e:
            logger.error(f'Failed to start prompts watcher: {e}')
            logger.warning('Continuing without prompts hot-reload')
    else:
        logger.info('Hot-reload disabled (not in Docker environment)')

    # Register Letta model hot-reload callback (fires on any settings reload)
    try:
        global _previous_letta_model
        _previous_letta_model = config.settings.memory.letta.agent_model or None
        from thoth.config import Config

        Config.register_reload_callback('letta_model_sync', _on_letta_model_reload)
        logger.info(
            f'Letta model reload callback registered '
            f'(current model: {_previous_letta_model or "server default"})'
        )
    except Exception as e:
        logger.warning(f'Could not register Letta model reload callback: {e}')

    # Get service_manager from app.state (set by start_obsidian_server)
    # If running via direct uvicorn (e.g. Docker CMD), initialize it here
    service_manager = getattr(app.state, 'service_manager', None)

    if service_manager is None:
        logger.info(
            'ServiceManager not set on app.state (direct uvicorn mode), '
            'initializing now...'
        )
        try:
            from thoth.services.service_manager import ServiceManager

            service_manager = ServiceManager()
            service_manager.initialize()
            app.state.service_manager = service_manager
            logger.success('ServiceManager initialized in lifespan')
        except Exception as e:
            logger.error(f'Failed to initialize ServiceManager in lifespan: {e}')
            logger.warning(
                'Continuing without ServiceManager (most features will not work)'
            )

    # Initialize MCP Servers Manager BEFORE agent initialization
    # (so agents can sync external MCP tools during their init)
    if service_manager:
        try:
            from thoth.services.letta_service import LettaService
            from thoth.services.mcp_servers_manager import MCPServersManager

            logger.info('Initializing MCP Servers Manager for API server...')
            mcp_manager = MCPServersManager(config=config)
            mcp_manager.initialize()

            # Add to service manager's internal dict
            service_manager._services['mcp_servers_manager'] = mcp_manager

            # Initialize Letta service for MCP manager
            # LettaService handles MCP server registration with Letta
            letta_service = LettaService()
            letta_service.initialize()

            mcp_manager.set_dependencies(None, letta_service)

            # Load config and start watching
            await mcp_manager.load_config()
            await mcp_manager.start_watching()

            logger.success('MCP Servers Manager initialized in API server')
        except Exception as e:
            logger.error(
                f'Failed to initialize MCP Servers Manager: {e}', exc_info=True
            )
            logger.warning(
                'Continuing without MCP Servers Manager (MCP management will not work)'
            )

    # NOW initialize Letta agents (after MCP manager is ready)
    try:
        from thoth.services.agent_initialization_service import (
            AgentInitializationService,
        )

        agent_init = AgentInitializationService()
        agent_ids = await agent_init.initialize_all_agents(
            service_manager=service_manager
        )
        logger.info(f'Agents initialized: {", ".join(agent_ids.keys())}')
    except Exception as e:
        logger.warning(f'Could not initialize agents: {e}')
        logger.warning(
            'Continuing without agent initialization - agents may need manual setup'
        )

    # Initialize PostgreSQL connection pool if postgres service exists
    if service_manager and hasattr(service_manager, 'postgres'):
        try:
            postgres_svc = service_manager.postgres
            await postgres_svc.initialize()
            logger.success('PostgreSQL connection pool initialized')
        except Exception as e:
            logger.error(f'Failed to initialize PostgreSQL: {e}')
            logger.warning('Continuing without PostgreSQL (some features may not work)')

    # Initialize WorkflowExecutionService after PostgreSQL is ready
    if service_manager and hasattr(service_manager, 'postgres'):
        try:
            from thoth.discovery.browser.workflow_execution_service import (
                WorkflowExecutionService,
            )

            logger.info('Initializing workflow execution service...')
            postgres_svc = service_manager.postgres
            workflow_execution_service = WorkflowExecutionService(
                postgres_service=postgres_svc,
                max_concurrent_browsers=5,
                default_timeout=30000,
                max_retries=3,
            )
            await workflow_execution_service.initialize()
            logger.success('Workflow execution service initialized successfully')
        except Exception as e:
            logger.error(f'Failed to initialize workflow execution service: {e}')
            logger.warning(
                'Continuing without workflow execution service (browser workflows will not work)'
            )
            workflow_execution_service = None

    # Store workflow_execution_service in app.state for router access
    if workflow_execution_service is not None:
        app.state.workflow_execution_service = workflow_execution_service

    # Initialize discovery scheduler after PostgreSQL is ready
    if service_manager:
        try:
            from thoth.discovery.discovery_manager import DiscoveryManager

            logger.info('Initializing discovery scheduler...')
            discovery_manager = DiscoveryManager()

            # Get required services for research question scheduling
            research_question_service = None
            discovery_orchestrator = None

            try:
                research_question_service = service_manager.get_service(
                    'research_question'
                )
            except Exception as e:
                logger.warning(f'Research question service not available: {e}')

            try:
                discovery_orchestrator = service_manager.get_service(
                    'discovery_orchestrator'
                )
            except Exception as e:
                logger.warning(f'Discovery orchestrator service not available: {e}')

            # Get the current running event loop
            event_loop = asyncio.get_running_loop()
            logger.info(f'Passing event loop to scheduler: {event_loop}')

            # Initialize scheduler with optional research question support and event loop  # noqa: W505
            discovery_scheduler = DiscoveryScheduler(
                discovery_manager=discovery_manager,
                research_question_service=research_question_service,
                discovery_orchestrator=discovery_orchestrator,
                event_loop=event_loop,  # Pass event loop for async operations from sync thread
            )

            # Sync scheduler with existing discovery sources
            discovery_scheduler.sync_with_discovery_manager()

            # Start the scheduler
            discovery_scheduler.start()
            logger.success('Discovery scheduler started successfully')

            if research_question_service and discovery_orchestrator:
                logger.info('Research question scheduling enabled')
            else:
                logger.info(
                    'Research question scheduling disabled (services not available)'
                )

        except Exception as e:
            logger.error(f'Failed to initialize discovery scheduler: {e}')
            logger.warning(
                'Continuing without discovery scheduler (scheduled discovery will not work)'
            )
            discovery_scheduler = None

    logger.success('API server startup complete')

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
                logger.info('Shutting down workflow execution service...')
                await workflow_execution_service.shutdown()
                logger.success('Workflow execution service shutdown complete')
            except Exception as e:
                logger.error(f'Error shutting down workflow execution service: {e}')

        # Stop discovery scheduler
        if discovery_scheduler is not None:
            try:
                logger.info('Stopping discovery scheduler...')
                discovery_scheduler.stop()
                logger.success('Discovery scheduler stopped')
            except Exception as e:
                logger.error(f'Error stopping discovery scheduler: {e}')

        # Stop MCP Servers Manager file watcher
        if service_manager and 'mcp_servers_manager' in service_manager._services:
            try:
                logger.info('Stopping MCP Servers Manager...')
                mcp_manager = service_manager._services['mcp_servers_manager']
                await mcp_manager.stop_watching()
                logger.success('MCP Servers Manager stopped')
            except Exception as e:
                logger.error(f'Error stopping MCP Servers Manager: {e}')

        # Stop settings watcher
        if _settings_watcher is not None:
            try:
                logger.info('Stopping settings watcher...')
                _settings_watcher.stop()
                logger.success('Settings watcher stopped')
            except Exception as e:
                logger.error(f'Error stopping settings watcher: {e}')

        if _schema_watcher is not None:
            try:
                logger.info('Stopping schema watcher...')
                _schema_watcher.stop()
                logger.success('Schema watcher stopped')
            except Exception as e:
                logger.error(f'Error stopping schema watcher: {e}')

        if _prompts_watcher is not None:
            try:
                logger.info('Stopping prompts watcher...')
                _prompts_watcher.stop()
                logger.success('Prompts watcher stopped')
            except Exception as e:
                logger.error(f'Error stopping prompts watcher: {e}')

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
        allow_methods=[
            'GET',
            'POST',
            'PUT',
            'DELETE',
            'OPTIONS',
            'PATCH',
        ],  # Include OPTIONS and PATCH
        allow_headers=['*'],
    )

    # Include routers with proper prefixes
    app.include_router(health.router, tags=['health'])

    # Include MCP health router if available (requires mcp extras)
    if MCP_HEALTH_AVAILABLE:
        app.include_router(
            mcp_health_router, tags=['mcp-health']
        )  # Enterprise MCP monitoring
        logger.debug('MCP health monitoring enabled')
    else:
        logger.debug('MCP health monitoring not available (requires mcp extras)')

    app.include_router(websocket.router, tags=['websocket'])
    app.include_router(chat.router, prefix='/chat', tags=['chat'])
    app.include_router(agent.router, prefix='/agents', tags=['agent'])
    app.include_router(research.router, prefix='/research', tags=['research'])
    app.include_router(
        research_questions.router, tags=['research-questions']
    )  # Week 4: Research question management

    # Browser workflows router (optional - only if playwright is available)
    if BROWSER_WORKFLOWS_AVAILABLE and browser_workflows:
        app.include_router(
            browser_workflows.router, tags=['workflows']
        )  # Browser workflow management (router already has /api/workflows prefix)

    app.include_router(config_router.router, prefix='/config', tags=['config'])
    app.include_router(models.router, prefix='/models', tags=['models'])
    app.include_router(operations.router, prefix='/operations', tags=['operations'])
    app.include_router(schema.router, tags=['schema'])
    app.include_router(skills.router, tags=['skills'])
    app.include_router(mcp_servers.router, tags=['mcp-servers'])
    app.include_router(tools.router, prefix='/tools', tags=['tools'])

    # Add hot-reload health check endpoint
    @app.get('/health/hot-reload')
    async def health_hot_reload():
        """Check hot-reload status."""
        settings_file = config.vault_root / 'thoth' / '_thoth' / 'settings.json'
        if not settings_file.exists():
            settings_file = config.vault_root / '_thoth' / 'settings.json'
        reload_count = getattr(config, 'reload_callback_count', 0)

        return {
            'enabled': _settings_watcher is not None,
            'settings_file': str(settings_file),
            'callback_count': reload_count,
            'status': 'active' if _settings_watcher is not None else 'disabled',
            'docker_env': os.getenv('DOCKER_ENV', 'false').lower() == 'true',
            'hot_reload_env': os.getenv('THOTH_HOT_RELOAD', '0') == '1',
        }

    # Add manual reload endpoint for testing
    @app.post('/api/reload-config')
    async def reload_config():
        """Manually trigger config reload (for testing)."""
        try:
            logger.info('Manual config reload requested')
            config.reload_settings()

            # Trigger all registered callbacks if watcher is active
            if _settings_watcher is not None:
                _settings_watcher._trigger_reload()
                callback_count = len(_settings_watcher._callbacks)
                logger.success(
                    f'Config reloaded successfully with {callback_count} callbacks'
                )
                return {
                    'status': 'success',
                    'message': f'Config reloaded successfully ({callback_count} callbacks executed)',
                    'timestamp': config._last_reload_time
                    if hasattr(config, '_last_reload_time')
                    else None,
                }
            else:
                logger.warning(
                    'Manual reload: watcher not active, only config reloaded'
                )
                return {
                    'status': 'success',
                    'message': 'Config reloaded (hot-reload not enabled, callbacks not executed)',
                    'timestamp': None,
                }
        except Exception as e:
            logger.error(f'Manual reload failed: {e}')
            return {'status': 'error', 'message': str(e), 'timestamp': None}

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
        current_config = (
            config.settings.model_dump() if hasattr(config, 'settings') else {}
        )

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

        # research_agent has been deprecated and migrated to Letta native agents
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

        # All routers use FastAPI Depends() for DI
        # set_dependencies() calls removed - dependencies injected from app.state

        # Still need to set directories for health router (not migrated - not necessary)
        health.set_directories(pdf_dir, notes_dir, base_url)

        logger.info('All router dependencies injected via FastAPI Depends()')

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

        # Store dependencies in app.state for router access
        app.state.service_manager = service_manager
        app.state.research_agent = research_agent
        app.state.chat_manager = chat_manager
        app.state.workflow_execution_service = workflow_execution_service

        logger.info('Dependencies stored in app.state for router access')

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
# Note: When used this way (imported directly), dependencies must be set separately
# Typically used by: python -m uvicorn thoth.server.app:app
app = create_app()

# Initialize empty app.state for direct imports (populated by lifespan)
app.state.service_manager = None
app.state.research_agent = None
app.state.chat_manager = None
app.state.workflow_execution_service = None

# Export the main functions
__all__ = ['app', 'create_app', 'start_obsidian_server', 'start_server']
