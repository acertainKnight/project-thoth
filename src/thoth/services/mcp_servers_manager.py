"""
MCP Servers Manager Service

This service manages external MCP server connections with hot-reload capability.
It serves as the central coordinator for:
- Loading/saving mcps.json configuration
- Connecting/disconnecting external MCP servers
- Proxying discovered tools through Thoth's MCP registry
- Auto-attaching tools to Letta agents
- File watching for hot-reload
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from thoth.models.mcp_server_config import MCPServerEntry, MCPServersConfig
from thoth.services.base import BaseService


class MCPServersManager(BaseService):
    """
    Manages external MCP server connections and tool proxying.

    This service monitors the mcps.json file and automatically connects/disconnects
    servers, registers their tools with Thoth's MCP registry, and syncs tools to
    Letta agents.
    """

    def __init__(self, config=None):
        """
        Initialize the MCP Servers Manager.

        Args:
            config: Thoth configuration object
        """
        super().__init__(thoth_config=config)
        self.config_path: Path | None = None
        self.current_config: MCPServersConfig | None = None
        self.connected_servers: dict[str, Any] = {}
        self.server_tools: dict[
            str, list[dict[str, str]]
        ] = {}  # server_id -> list of tool dicts
        self.watch_task: asyncio.Task | None = None
        self._last_mtime: float | None = None
        self._mcp_registry: Any | None = None
        self._letta_service: Any | None = None

    def initialize(self) -> None:
        """Initialize the MCP servers manager."""
        # Get config path from settings
        mcp_config = self.config.settings.servers.mcp
        self.config_path = Path(mcp_config.external_servers_file)

        self.logger.info(
            f'MCPServersManager initialized with config: {self.config_path}'
        )

        # Create default config if it doesn't exist
        if not self.config_path.exists():
            self._create_default_config()

    def set_dependencies(self, mcp_registry: Any, letta_service: Any) -> None:
        """
        Set dependencies for tool registration and agent attachment.

        Args:
            mcp_registry: MCPToolRegistry for registering proxied tools
            letta_service: LettaService for registering MCP servers and attaching
                tools to agents
        """
        self._mcp_registry = mcp_registry
        self._letta_service = letta_service
        self.logger.info('MCPServersManager dependencies set')

    def _create_default_config(self) -> None:
        """Create a default mcps.json file with an empty servers list."""
        default_config = MCPServersConfig(
            version='1.0.0',
            mcp_servers={},  # Start with no servers - user adds them as needed
        )

        # Ensure parent directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Write config
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config.model_dump(by_alias=True), f, indent=2)

            self.logger.info(
                f'Created default MCP servers config at {self.config_path}'
            )
        except Exception as e:
            self.logger.error(f'Failed to create default config file: {e}')
            # Don't raise - allow system to continue

    async def load_config(self) -> MCPServersConfig:
        """
        Load the MCP servers configuration from mcps.json.

        Returns:
            MCPServersConfig: Loaded configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        if not self.config_path.exists():
            self.logger.warning(f'Config file not found: {self.config_path}')
            self._create_default_config()

        try:
            with open(self.config_path, encoding='utf-8') as f:
                content = f.read().strip()

            # Handle empty file
            if not content:
                self.logger.warning('Config file is empty, creating default config')
                self._create_default_config()
                # Reload after creating default
                with open(self.config_path, encoding='utf-8') as f:
                    content = f.read()

            data = json.loads(content)

            # Handle missing or null mcpServers field
            if 'mcpServers' not in data or data['mcpServers'] is None:
                data['mcpServers'] = {}

            config_obj = MCPServersConfig(**data)
            self._last_mtime = self.config_path.stat().st_mtime
            self.logger.info(
                f'Loaded MCP servers config: {len(config_obj.mcp_servers)} servers'
            )
            return config_obj

        except json.JSONDecodeError as e:
            self.logger.error(f'Invalid JSON in config file: {e}')
            self.logger.warning('Recreating config file with defaults')
            self._create_default_config()
            # Try loading again after recreating
            return await self.load_config()
        except Exception as e:
            self.logger.error(f'Failed to load config: {e}')
            raise

    async def save_config(self, config_obj: MCPServersConfig) -> None:
        """
        Save the MCP servers configuration to mcps.json.

        Args:
            config_obj: Configuration to save
        """
        try:
            # Ensure parent directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            # Write config
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_obj.model_dump(by_alias=True), f, indent=2)

            # Update mtime cache
            self._last_mtime = self.config_path.stat().st_mtime
            self.logger.info(
                f'Saved MCP servers config: {len(config_obj.mcp_servers)} servers'
            )

        except Exception as e:
            self.logger.error(f'Failed to save config: {e}')
            raise

    async def start_watching(self) -> None:
        """Start the file watcher for hot-reload."""
        if self.watch_task is not None:
            self.logger.warning('File watcher already running')
            return

        self.watch_task = asyncio.create_task(self._watch_loop())
        self.logger.info('Started file watcher for mcps.json')

    async def stop_watching(self) -> None:
        """Stop the file watcher."""
        if self.watch_task is not None:
            self.watch_task.cancel()
            try:
                await self.watch_task
            except asyncio.CancelledError:
                pass
            self.watch_task = None
            self.logger.info('Stopped file watcher')

    async def _watch_loop(self) -> None:
        """File watcher loop that checks for config changes every 2 seconds."""
        while True:
            try:
                await asyncio.sleep(2)

                if not self.config_path.exists():
                    continue

                current_mtime = self.config_path.stat().st_mtime
                if self._last_mtime is None or current_mtime > self._last_mtime:
                    self.logger.info('Config file changed, reloading...')
                    await self._on_config_changed()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f'Error in file watcher: {e}')

    async def _on_config_changed(self) -> None:
        """Handle config file changes by diffing and reconnecting servers."""
        try:
            new_config = await self.load_config()

            # If this is the first load, just connect all enabled servers
            if self.current_config is None:
                self.current_config = new_config
                await self._connect_all_enabled_servers()
                return

            # Diff the configs
            old_servers = set(self.current_config.mcp_servers.keys())
            new_servers = set(new_config.mcp_servers.keys())

            # Removed servers
            removed = old_servers - new_servers
            for server_id in removed:
                await self._disconnect_server(server_id)

            # Added or changed servers
            for server_id in new_servers:
                old_entry = self.current_config.mcp_servers.get(server_id)
                new_entry = new_config.mcp_servers[server_id]

                # If server exists and config changed, reconnect
                if old_entry and old_entry != new_entry:
                    self.logger.info(f'Server {server_id} config changed, reconnecting')
                    await self._disconnect_server(server_id)
                    if new_entry.enabled:
                        await self._connect_server(server_id, new_entry)

                # If server is new and enabled, connect
                elif not old_entry and new_entry.enabled:
                    await self._connect_server(server_id, new_entry)

                # If server was disabled, disconnect
                elif old_entry and old_entry.enabled and not new_entry.enabled:
                    await self._disconnect_server(server_id)

                # If server was enabled, connect
                elif old_entry and not old_entry.enabled and new_entry.enabled:
                    await self._connect_server(server_id, new_entry)

            self.current_config = new_config

            # Sync tools to agents
            await self.sync_tools_to_agents()

        except Exception as e:
            self.logger.error(f'Failed to handle config change: {e}')

    async def _connect_all_enabled_servers(self) -> None:
        """Connect to all enabled servers in the config."""
        if not self.current_config:
            return

        enabled_servers = self.current_config.get_enabled_servers()
        self.logger.info(f'Connecting to {len(enabled_servers)} enabled servers')

        for server_id, server_entry in enabled_servers.items():
            await self._connect_server(server_id, server_entry)

    async def _connect_server(
        self, server_id: str, server_entry: MCPServerEntry
    ) -> None:
        """
        Connect to an external MCP server and discover its tools.

        Args:
            server_id: Unique server identifier
            server_entry: Server configuration
        """
        try:
            self.logger.info(
                f'Connecting to MCP server: {server_id} ({server_entry.name})'
            )

            # Import here to avoid circular dependency
            from langchain_mcp_adapters.client import load_mcp_tools
            from langchain_mcp_adapters.sessions import create_session

            # Build connection config
            if server_entry.transport == 'stdio':
                if not server_entry.command:
                    raise ValueError(
                        f'Server {server_id}: command required for stdio transport'
                    )

                connection_config = {
                    'transport': 'stdio',
                    'command': server_entry.command,
                    'args': server_entry.args,
                }

                if server_entry.env:
                    connection_config['env'] = server_entry.env

            elif server_entry.transport in ['http', 'sse']:
                if not server_entry.url:
                    raise ValueError(
                        f'Server {server_id}: URL required for {server_entry.transport} transport'
                    )

                connection_config = {
                    'transport': server_entry.transport,
                    'url': server_entry.url,
                }

            else:
                raise ValueError(
                    f'Server {server_id}: unsupported transport {server_entry.transport}'
                )

            # Register server with Letta first (if available)
            # Letta will handle the connection and tool discovery
            if self._letta_service:
                letta_registered = await self._register_mcp_server_with_letta(
                    server_id, server_entry
                )
                if letta_registered:
                    # Get tools from Letta's discovery
                    tool_details = await self._sync_tools_from_letta(server_id)
                    if tool_details:
                        self.server_tools[server_id] = tool_details
                        self.logger.info(
                            f'Registered MCP server {server_id} with Letta: {len(tool_details)} tools available'
                        )
                        # Mark as connected (Letta manages the actual connection)
                        self.connected_servers[server_id] = 'letta_managed'
                    else:
                        self.logger.warning(
                            f'Server {server_id} registered with Letta but no tools discovered'
                        )
                else:
                    self.logger.error(
                        f'Failed to register server {server_id} with Letta'
                    )
            else:
                # Fallback: Direct connection via langchain_mcp_adapters
                # This is for development/testing when Letta is not available
                self.logger.warning(
                    f'Letta service not available - using direct MCP connection for {server_id}'
                )

                session = await create_session(connection_config).__aenter__()
                tools = await load_mcp_tools(session)

                if tools:
                    self.connected_servers[server_id] = session

                    # Store tool details (name, description, prefixed name)
                    tool_details = []
                    for tool in tools:
                        prefixed_name = f'{server_id}__{tool.name}'
                        tool_details.append(
                            {
                                'name': tool.name,
                                'description': getattr(tool, 'description', '') or '',
                                'prefixed_name': prefixed_name,
                            }
                        )
                    self.server_tools[server_id] = tool_details

                    self.logger.info(
                        f'Connected directly to {server_id}: discovered {len(tools)} tools'
                    )
                    self.logger.warning(
                        'Tools will not be available to Letta agents without Letta registration'
                    )
                else:
                    self.logger.warning(f'Server {server_id} provided no tools')

        except Exception as e:
            self.logger.error(f'Failed to connect to server {server_id}: {e}')

    async def _disconnect_server(self, server_id: str) -> None:
        """
        Disconnect from an external MCP server and unregister its tools.

        Args:
            server_id: Server identifier
        """
        if server_id not in self.connected_servers:
            return

        try:
            self.logger.info(f'Disconnecting from MCP server: {server_id}')

            # Close session
            session = self.connected_servers[server_id]
            if hasattr(session, '__aexit__'):
                await session.__aexit__(None, None, None)

            # Remove from tracking
            del self.connected_servers[server_id]

            # Detach tools from agents
            if server_id in self.server_tools:
                # TODO: Unregister prefixed tool names from MCP registry
                # TODO: Detach from Letta agents
                del self.server_tools[server_id]

            self.logger.info(f'Disconnected from {server_id}')

        except Exception as e:
            self.logger.error(f'Error disconnecting from {server_id}: {e}')

    async def sync_tools_to_agents(self) -> None:
        """Sync external MCP tools to Letta agents based on autoAttach setting."""
        if not self._letta_service or not self.current_config:
            return

        try:
            # Get all auto-attach servers
            auto_attach_servers = self.current_config.get_auto_attach_servers()

            # Collect all tools to attach
            tools_to_attach = []
            for server_id, server_entry in auto_attach_servers.items():
                if server_id in self.server_tools:
                    # Get prefixed names from tool details, excluding disabled tools
                    disabled = set(server_entry.disabled_tools)
                    prefixed_names = [
                        tool['prefixed_name']
                        for tool in self.server_tools[server_id]
                        if tool['name'] not in disabled
                    ]
                    tools_to_attach.extend(prefixed_names)

            if not tools_to_attach:
                self.logger.debug('No external MCP tools to attach')
                return

            self.logger.info(
                f'Syncing {len(tools_to_attach)} external MCP tools to agents'
            )

            # Get all agent IDs (would need to query Letta)
            # For now, just log
            self.logger.debug(f'Would attach tools: {tools_to_attach}')

        except Exception as e:
            self.logger.error(f'Failed to sync tools to agents: {e}')

    # CRUD operations

    async def add_server(self, server_id: str, server_entry: MCPServerEntry) -> None:
        """
        Add a new MCP server to the configuration.

        Args:
            server_id: Unique identifier for the server
            server_entry: Server configuration
        """
        config_obj = await self.load_config()

        if server_id in config_obj.mcp_servers:
            raise ValueError(f'Server {server_id} already exists')

        config_obj.mcp_servers[server_id] = server_entry
        await self.save_config(config_obj)

        # Update current config to reflect changes immediately
        self.current_config = config_obj

        self.logger.info(f'Added MCP server: {server_id}')

    async def update_server(self, server_id: str, server_entry: MCPServerEntry) -> None:
        """
        Update an existing MCP server configuration.

        Args:
            server_id: Server identifier
            server_entry: Updated configuration
        """
        config_obj = await self.load_config()

        if server_id not in config_obj.mcp_servers:
            raise ValueError(f'Server {server_id} not found')

        config_obj.mcp_servers[server_id] = server_entry
        await self.save_config(config_obj)

        # Update current config to reflect changes immediately
        self.current_config = config_obj

        self.logger.info(f'Updated MCP server: {server_id}')

    async def remove_server(self, server_id: str) -> None:
        """
        Remove an MCP server from the configuration.

        Args:
            server_id: Server identifier
        """
        config_obj = await self.load_config()

        if server_id not in config_obj.mcp_servers:
            raise ValueError(f'Server {server_id} not found')

        del config_obj.mcp_servers[server_id]
        await self.save_config(config_obj)

        # Update current config to reflect changes immediately
        self.current_config = config_obj

        self.logger.info(f'Removed MCP server: {server_id}')

    async def toggle_server(self, server_id: str, enabled: bool) -> None:
        """
        Enable or disable an MCP server.

        Args:
            server_id: Server identifier
            enabled: Whether to enable the server
        """
        config_obj = await self.load_config()

        if server_id not in config_obj.mcp_servers:
            raise ValueError(f'Server {server_id} not found')

        config_obj.mcp_servers[server_id].enabled = enabled
        await self.save_config(config_obj)

        # Update current config to reflect changes immediately
        self.current_config = config_obj

        self.logger.info(
            f'{"Enabled" if enabled else "Disabled"} MCP server: {server_id}'
        )

    async def test_connection(self, server_id: str) -> dict[str, Any]:
        """
        Test connectivity to an MCP server.

        Args:
            server_id: Server identifier

        Returns:
            dict: Test result with status and message
        """
        config_obj = await self.load_config()

        if server_id not in config_obj.mcp_servers:
            return {'success': False, 'message': f'Server {server_id} not found'}

        server_entry = config_obj.mcp_servers[server_id]

        try:
            # Try to connect temporarily
            from langchain_mcp_adapters.client import load_mcp_tools
            from langchain_mcp_adapters.sessions import create_session

            if server_entry.transport == 'stdio':
                connection_config = {
                    'transport': 'stdio',
                    'command': server_entry.command,
                    'args': server_entry.args,
                }
            else:
                connection_config = {
                    'transport': server_entry.transport,
                    'url': server_entry.url,
                }

            # Test connection with timeout
            async with create_session(connection_config) as session:
                tools = await asyncio.wait_for(
                    load_mcp_tools(session),
                    timeout=server_entry.timeout,
                )
                return {
                    'success': True,
                    'message': f'Connected successfully, found {len(tools)} tools',
                    'tool_count': len(tools),
                }

        except TimeoutError:
            return {'success': False, 'message': 'Connection timeout'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    async def get_server_status(self) -> dict[str, Any]:
        """
        Get status of all configured MCP servers.

        Returns:
            dict: Status information for all servers
        """
        if not self.current_config:
            self.current_config = await self.load_config()

        status = {}
        for server_id, server_entry in self.current_config.mcp_servers.items():
            status[server_id] = {
                'name': server_entry.name,
                'enabled': server_entry.enabled,
                'connected': server_id in self.connected_servers,
                'transport': server_entry.transport,
                'auto_attach': server_entry.auto_attach,
                'tool_count': len(self.server_tools.get(server_id, [])),
            }

        return status

    async def list_servers(self) -> dict[str, MCPServerEntry]:
        """
        List all configured MCP servers.

        Returns:
            dict: All server configurations keyed by server ID
        """
        config_obj = await self.load_config()
        return config_obj.mcp_servers

    def get_server_tool_details(self, server_id: str) -> list[dict[str, str]]:
        """
        Get detailed tool information for a specific server.

        Args:
            server_id: Server identifier

        Returns:
            list: List of tool dicts with 'name', 'description', 'prefixed_name' keys
        """
        return self.server_tools.get(server_id, [])

    def get_tools_for_server(self, server_id: str) -> list[str]:
        """
        Get tool names for a specific server (convenience method).

        Args:
            server_id: Server identifier

        Returns:
            list: List of tool names (unprefixed)
        """
        tool_details = self.server_tools.get(server_id, [])
        return [tool['name'] for tool in tool_details]

    async def _register_mcp_server_with_letta(
        self, server_id: str, server_entry: MCPServerEntry
    ) -> bool:
        """
        Register an MCP server with Letta's native MCP server support.

        Args:
            server_id: MCP server identifier
            server_entry: Server configuration

        Returns:
            bool: True if registration successful, False otherwise
        """
        if not self._letta_service:
            self.logger.warning(
                'Letta service not available - cannot register MCP server'
            )
            return False

        try:
            # Build server config for Letta
            server_config = {
                'transport': server_entry.transport,
            }

            if server_entry.transport == 'stdio':
                server_config['command'] = server_entry.command
                server_config['args'] = server_entry.args
                if server_entry.env:
                    server_config['env'] = server_entry.env
            elif server_entry.transport in ['http', 'sse']:
                server_config['url'] = server_entry.url

            # Register server with Letta
            result = self._letta_service.register_mcp_server(server_id, server_config)

            if result.get('success'):
                self.logger.info(
                    f"Registered MCP server '{server_id}' with Letta - Letta will discover tools automatically"
                )
                return True
            else:
                self.logger.error(
                    f"Failed to register MCP server '{server_id}' with Letta: {result.get('error')}"
                )
                return False

        except Exception as e:
            self.logger.error(
                f"Error registering MCP server '{server_id}' with Letta: {e}"
            )
            return False

    async def _sync_tools_from_letta(self, server_id: str) -> list[dict[str, str]]:
        """
        Get tool list from Letta's MCP server registration.

        Args:
            server_id: MCP server identifier

        Returns:
            list: Tool details from Letta (with unprefixed 'name' and prefixed
                'prefixed_name')
        """
        if not self._letta_service:
            return []

        try:
            # Get tools discovered by Letta
            letta_tools = self._letta_service.list_mcp_tools_by_server(server_id)

            tool_details = []
            for tool in letta_tools:
                tool_name = tool.get('name', '')

                # Letta may return prefixed names (server-id__tool-name)
                # Extract the unprefixed name for storage
                if '__' in tool_name and tool_name.startswith(f'{server_id}__'):
                    unprefixed_name = tool_name.split('__', 1)[1]
                else:
                    unprefixed_name = tool_name

                tool_details.append(
                    {
                        'name': unprefixed_name,  # Store unprefixed for API simplicity
                        'description': tool.get('description', ''),
                        'prefixed_name': tool_name,  # Store full name as Letta knows it
                    }
                )

            self.logger.info(
                f'Retrieved {len(tool_details)} tools from Letta for server {server_id}'
            )
            return tool_details

        except Exception as e:
            self.logger.error(
                f'Failed to sync tools from Letta for server {server_id}: {e}'
            )
            return []
