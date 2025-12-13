"""
MCP Plugin Manager

This module provides comprehensive management for external MCP server plugins,
including discovery, loading, validation, and health monitoring.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from thoth.config import MCPConfig


class MCPPluginConfig(BaseModel):
    """Configuration for a single MCP plugin."""

    enabled: bool = Field(True, description='Whether the plugin is enabled')
    name: str = Field(..., description='Human-readable name for the plugin')
    description: str = Field('', description='Description of plugin functionality')

    # Transport configuration (union type for different transports)
    transport: str = Field(..., description='Transport type: stdio, http, or sse')

    # Command-based configuration (stdio)
    command: list[str] | None = Field(
        None, description='Command to start the MCP server'
    )
    args: list[str] = Field(default_factory=list, description='Additional arguments')
    env: dict[str, str] = Field(
        default_factory=dict, description='Environment variables'
    )
    cwd: str | None = Field(None, description='Working directory for the command')

    # URL-based configuration (http/sse)
    url: str | None = Field(None, description='URL for HTTP/SSE connections')

    # Authentication configuration
    auth: dict[str, Any] | None = Field(
        None, description='Authentication configuration'
    )

    # Plugin metadata
    priority: int = Field(
        1, description='Plugin loading priority (lower = higher priority)'
    )
    version: str | None = Field(None, description='Plugin version')
    capabilities: list[str] = Field(
        default_factory=lambda: ['tools'],
        description='Supported capabilities (tools, resources, prompts)',
    )

    # Performance and reliability
    timeout: int = Field(30, description='Connection timeout in seconds')
    retry_attempts: int = Field(3, description='Number of retry attempts')
    health_check_interval: int = Field(
        60, description='Health check interval in seconds'
    )

    # Security settings
    sandbox: bool = Field(True, description='Run in sandboxed environment')
    allowed_network_hosts: list[str] = Field(
        default_factory=list, description='Allowed network hosts'
    )
    allowed_file_paths: list[str] = Field(
        default_factory=list, description='Allowed file system paths'
    )


class MCPPluginRegistry(BaseModel):
    """Registry configuration for MCP plugins."""

    version: str = Field('1.0.0', description='Configuration schema version')
    plugins: dict[str, MCPPluginConfig] = Field(
        default_factory=dict, description='Plugin configurations by ID'
    )
    vault_variables: dict[str, str] = Field(
        default_factory=dict, description='Vault-specific variables for substitution'
    )


class MCPPluginManager:
    """
    Manages external MCP server plugins with discovery, loading, and health monitoring.

    This manager handles the complete lifecycle of MCP plugins including:
    - Auto-discovery of available MCP servers
    - Configuration loading and validation
    - Plugin connection management
    - Health monitoring and reconnection
    - Tool aggregation from multiple sources
    """

    def __init__(self, config: MCPConfig):
        """
        Initialize the MCP plugin manager.

        Args:
            config: MCPConfig containing plugin settings
        """
        self.config = config
        self.registry: MCPPluginRegistry | None = None
        self.active_sessions: dict[str, Any] = {}
        self.plugin_tools: dict[str, list[Any]] = {}
        self.health_tasks: dict[str, asyncio.Task] = {}

        # Delay import to avoid circular dependency
        from .validation import MCPPluginValidator

        self.validator = MCPPluginValidator()

        logger.info('MCP Plugin Manager initialized')

    async def load_plugin_config(
        self, config_path: Path | None = None
    ) -> MCPPluginRegistry:
        """
        Load plugin configuration from file or auto-detect location.

        Args:
            config_path: Optional explicit path to config file

        Returns:
            MCPPluginRegistry: Loaded plugin configuration

        Raises:
            FileNotFoundError: If config file not found
            ValidationError: If config validation fails
        """
        if config_path is None:
            config_path = await self._auto_detect_config_path()

        if not config_path.exists():
            logger.warning(
                f'Plugin config not found at {config_path}, creating default'
            )
            await self._create_default_config(config_path)

        try:
            with open(config_path, encoding='utf-8') as f:
                config_data = json.load(f)

            # Perform variable substitution
            config_data = self._substitute_variables(config_data)

            registry = MCPPluginRegistry(**config_data)
            logger.info(
                f'Loaded {len(registry.plugins)} plugin configurations from {config_path}'
            )

            # Validate configuration
            validation_result = await self.validator.validate_registry(registry)

            if validation_result.errors:
                logger.error(
                    f'Plugin configuration validation failed with {len(validation_result.errors)} errors:'
                )
                for error in validation_result.errors[:5]:  # Show first 5 errors
                    logger.error(f'  - {error}')
                if len(validation_result.errors) > 5:
                    logger.error(
                        f'  ... and {len(validation_result.errors) - 5} more errors'
                    )

            if validation_result.warnings:
                logger.warning(
                    f'Plugin configuration has {len(validation_result.warnings)} warnings:'
                )
                for warning in validation_result.warnings[:3]:  # Show first 3 warnings
                    logger.warning(f'  - {warning}')
                if len(validation_result.warnings) > 3:
                    logger.warning(
                        f'  ... and {len(validation_result.warnings) - 3} more warnings'
                    )

            if validation_result.errors:
                # Don't fail completely - just disable invalid plugins
                logger.warning('Disabling plugins with validation errors')
                for (
                    plugin_id,
                    plugin_result,
                ) in validation_result.plugin_results.items():
                    if not plugin_result.is_valid:
                        registry.plugins[plugin_id].enabled = False
                        logger.warning(
                            f'Disabled plugin {plugin_id} due to validation errors'
                        )

            return registry

        except json.JSONDecodeError as e:
            logger.error(f'Invalid JSON in plugin config: {e}')
            raise ValidationError(f'Invalid JSON in plugin config: {e}') from e
        except ValidationError as e:
            logger.error(f'Plugin config validation failed: {e}')
            raise

    async def _auto_detect_config_path(self) -> Path:
        """
        Auto-detect plugin configuration file location using settings
        and environment.
        """
        if self.config.plugin_config_path:
            return self.config.plugin_config_path

        # Environment variable override for MCP plugin config
        import os

        env_path = os.getenv('MCP_PLUGIN_CONFIG_PATH')
        if env_path:
            path = Path(env_path).expanduser().resolve()
            logger.info(f'Using MCP plugin config from environment: {path}')
            return path

        # Check for Obsidian vault via environment variable (highest priority for vault)
        obsidian_vault_path = os.getenv('OBSIDIAN_VAULT_PATH')
        if obsidian_vault_path:
            vault_config = (
                Path(obsidian_vault_path) / '.obsidian/plugins/thoth/mcp-plugins.json'
            )
            logger.info(
                f'Using Obsidian vault config from OBSIDIAN_VAULT_PATH: {vault_config}'
            )
            return vault_config

        # Search common locations (fallback)
        search_paths = [
            Path.home() / '.config/thoth/mcp-plugins.json',
            Path.cwd() / 'workspace/.mcp/plugins.json',
            Path.cwd() / 'mcp-plugins.json',
        ]

        for path in search_paths:
            if path.exists():
                logger.info(f'Auto-detected plugin config at {path}')
                return path

        # Default to user config directory
        default_path = Path.home() / '.config/thoth/mcp-plugins.json'
        logger.info(f'Using default plugin config location: {default_path}')
        return default_path

    def _get_obsidian_vault_path(self) -> Path | None:
        """Get Obsidian vault path from environment variable."""
        import os

        obsidian_vault_path = os.getenv('OBSIDIAN_VAULT_PATH')

        if obsidian_vault_path:
            vault_path = Path(obsidian_vault_path)
            if vault_path.exists():
                return vault_path
            else:
                logger.warning(
                    f'OBSIDIAN_VAULT_PATH points to non-existent directory: {vault_path}'
                )

        return None

    async def _create_default_config(self, config_path: Path) -> None:
        """Create default plugin configuration file."""
        config_path.parent.mkdir(parents=True, exist_ok=True)

        default_config = MCPPluginRegistry(
            plugins={
                'filesystem': MCPPluginConfig(
                    name='Filesystem',
                    description='File system operations',
                    transport='stdio',
                    command=['npx', '@modelcontextprotocol/server-filesystem', '.'],
                    enabled=False,  # Disabled by default for security
                ),
                'sqlite': MCPPluginConfig(
                    name='SQLite Database',
                    description='SQLite database operations',
                    transport='stdio',
                    command=[
                        'npx',
                        '@modelcontextprotocol/server-sqlite',
                        '--db-path',
                        './database.db',
                    ],
                    enabled=False,
                ),
            }
        )

        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config.model_dump(), f, indent=2)

        logger.info(f'Created default plugin config at {config_path}')

    def _substitute_variables(self, config_data: dict[str, Any]) -> dict[str, Any]:
        """Perform variable substitution in configuration."""
        vault_vars = config_data.get('vault_variables', {})

        # Add common variables with proper vault path from environment
        vault_path = self._get_obsidian_vault_path()
        if vault_path:
            vault_vars.update(
                {
                    'vault_path': str(vault_path),
                    'obsidian_vault': str(vault_path),
                    'home': str(Path.home()),
                    'workspace': str(Path.cwd() / 'workspace'),
                }
            )
        else:
            # Default fallback when no vault is configured
            vault_vars.update(
                {
                    'vault_path': str(Path.cwd()),
                    'home': str(Path.home()),
                    'workspace': str(Path.cwd() / 'workspace'),
                }
            )

        # Convert to JSON string and substitute
        config_str = json.dumps(config_data)
        for key, value in vault_vars.items():
            config_str = config_str.replace(f'{{{{{key}}}}}', value)

        return json.loads(config_str)

    async def load_plugins(self) -> list[Any]:
        """
        Load all enabled plugins and return combined tool list.

        Returns:
            list[Any]: Combined list of tools from all loaded plugins
        """
        if not self.config.plugins_enabled:
            logger.info('MCP plugins disabled in configuration')
            return []

        # Load plugin configuration
        try:
            self.registry = await self.load_plugin_config()
        except Exception as e:
            logger.error(f'Failed to load plugin configuration: {e}')
            return []

        # Load enabled plugins
        all_tools = []
        enabled_plugins = {
            pid: plugin
            for pid, plugin in self.registry.plugins.items()
            if plugin.enabled
        }

        if not enabled_plugins:
            logger.info('No enabled plugins found')
            return []

        logger.info(f'Loading {len(enabled_plugins)} enabled plugins')

        # Sort by priority
        sorted_plugins = sorted(enabled_plugins.items(), key=lambda x: x[1].priority)

        # Load plugins concurrently with connection limit
        semaphore = asyncio.Semaphore(self.config.max_concurrent_plugins)

        tasks = [
            self._load_single_plugin(plugin_id, plugin_config, semaphore)
            for plugin_id, plugin_config in sorted_plugins
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Aggregate successful results
        for plugin_id, result in zip(enabled_plugins.keys(), results, strict=False):
            if isinstance(result, Exception):
                logger.error(f'Failed to load plugin {plugin_id}: {result}')
            elif result:
                all_tools.extend(result)
                logger.info(f'Plugin {plugin_id} loaded {len(result)} tools')

        logger.info(f'Successfully loaded {len(all_tools)} total tools from plugins')
        return all_tools

    async def _load_single_plugin(
        self,
        plugin_id: str,
        plugin_config: MCPPluginConfig,
        semaphore: asyncio.Semaphore,
    ) -> list[Any]:
        """Load a single plugin with connection management."""
        async with semaphore:
            try:
                from langchain_mcp_adapters.client import load_mcp_tools
                from langchain_mcp_adapters.sessions import create_session

                # Build connection configuration
                connection_config = await self._build_connection_config(plugin_config)

                # Create session and load tools
                async with create_session(connection_config) as session:
                    tools = await load_mcp_tools(session)

                    if tools:
                        # Store tools and session reference
                        tool_list = list(tools)
                        self.plugin_tools[plugin_id] = tool_list

                        # Start health monitoring
                        if plugin_config.health_check_interval > 0:
                            self._start_health_monitoring(plugin_id, plugin_config)

                        logger.info(
                            f'Plugin {plugin_id} ({plugin_config.name}) loaded successfully'
                        )
                        return tool_list
                    else:
                        logger.warning(
                            f'Plugin {plugin_id} loaded but provided no tools'
                        )
                        return []

            except Exception as e:
                logger.error(f'Failed to load plugin {plugin_id}: {e}')
                # Try retry logic
                if plugin_config.retry_attempts > 1:
                    logger.info(
                        f'Retrying plugin {plugin_id} ({plugin_config.retry_attempts - 1} attempts left)'
                    )
                    await asyncio.sleep(2)  # Brief delay before retry
                    plugin_config.retry_attempts -= 1
                    return await self._load_single_plugin(
                        plugin_id, plugin_config, semaphore
                    )
                return []

    async def _build_connection_config(
        self, plugin_config: MCPPluginConfig
    ) -> dict[str, Any]:
        """Build connection configuration for MCP session."""
        if plugin_config.transport == 'stdio':
            if not plugin_config.command:
                raise ValueError('Command required for stdio transport')

            config = {
                'transport': 'stdio',
                'command': plugin_config.command[0],
                'args': plugin_config.command[1:] + plugin_config.args,
            }

            if plugin_config.env:
                config['env'] = plugin_config.env
            if plugin_config.cwd:
                config['cwd'] = plugin_config.cwd

            return config

        elif plugin_config.transport in ['http', 'sse']:
            if not plugin_config.url:
                raise ValueError(
                    f'URL required for {plugin_config.transport} transport'
                )

            config = {'transport': plugin_config.transport, 'url': plugin_config.url}

            # Add authentication if configured
            if plugin_config.auth:
                config['auth'] = plugin_config.auth

            return config
        else:
            raise ValueError(f'Unsupported transport: {plugin_config.transport}')

    def _start_health_monitoring(
        self, plugin_id: str, plugin_config: MCPPluginConfig
    ) -> None:
        """Start health monitoring task for plugin."""
        if plugin_id in self.health_tasks:
            self.health_tasks[plugin_id].cancel()

        task = asyncio.create_task(self._health_monitor_loop(plugin_id, plugin_config))
        self.health_tasks[plugin_id] = task

    async def _health_monitor_loop(
        self, plugin_id: str, plugin_config: MCPPluginConfig
    ) -> None:
        """Health monitoring loop for a plugin."""
        while True:
            try:
                await asyncio.sleep(plugin_config.health_check_interval)

                # Check if plugin is still responsive
                if plugin_id in self.plugin_tools:
                    logger.debug(f'Plugin {plugin_id} health check passed')
                else:
                    logger.warning(f'Plugin {plugin_id} appears unresponsive')

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f'Health check error for plugin {plugin_id}: {e}')

    async def shutdown(self) -> None:
        """Shutdown plugin manager and cleanup resources."""
        logger.info('Shutting down MCP Plugin Manager')

        # Cancel health monitoring tasks
        for task in self.health_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self.health_tasks:
            await asyncio.gather(*self.health_tasks.values(), return_exceptions=True)

        # Clear state
        self.active_sessions.clear()
        self.plugin_tools.clear()
        self.health_tasks.clear()

        logger.info('MCP Plugin Manager shutdown complete')
