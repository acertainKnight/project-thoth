"""
MCP tools for managing external MCP server connections.

These tools allow agents to dynamically add, remove, configure, and test
external MCP servers that provide additional capabilities.
"""

from typing import Any

from thoth.mcp.base_tools import MCPTool, MCPToolCallResult
from thoth.models.mcp_server_config import MCPServerEntry


class ListMCPServersMCPTool(MCPTool):
    """List all configured external MCP servers with their status."""

    @property
    def name(self) -> str:
        return 'list_mcp_servers'

    @property
    def description(self) -> str:
        return (
            'List all configured external MCP servers including their connection status, '
            'enabled state, transport type, and tool count. Use this to see what external '
            'servers are available and their current state.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {},
            'required': [],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:  # noqa: ARG002
        """Execute the tool."""
        try:
            mcp_manager = self.service_manager.get_service('mcp_servers_manager')

            if not mcp_manager:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: MCP Servers Manager not available',
                        }
                    ],
                    is_error=True,
                )

            # Get server status
            status = await mcp_manager.get_server_status()

            if not status:
                return MCPToolCallResult(
                    content=[{'type': 'text', 'text': 'No MCP servers configured.'}]
                )

            # Format output
            lines = ['# External MCP Servers\n']
            for server_id, info in status.items():
                lines.append(f'\n## {server_id}')
                lines.append(f'- **Name**: {info["name"]}')
                lines.append(f'- **Enabled**: {info["enabled"]}')
                lines.append(f'- **Connected**: {info["connected"]}')
                lines.append(f'- **Transport**: {info["transport"]}')
                lines.append(f'- **Auto-attach tools**: {info["auto_attach"]}')
                lines.append(f'- **Tool count**: {info["tool_count"]}')

            return MCPToolCallResult(
                content=[{'type': 'text', 'text': '\n'.join(lines)}]
            )

        except Exception as e:
            self.logger.error(f'Error listing MCP servers: {e}')
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error listing MCP servers: {e}'}],
                is_error=True,
            )


class AddMCPServerMCPTool(MCPTool):
    """Add a new external MCP server to the configuration."""

    @property
    def name(self) -> str:
        return 'add_mcp_server'

    @property
    def description(self) -> str:
        return (
            'Add a new external MCP server to the configuration. Specify the server ID, '
            'name, transport type (stdio/http/sse), and connection details. For stdio '
            'transport, provide command and args. For http/sse, provide the URL.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'server_id': {
                    'type': 'string',
                    'description': "Unique identifier for the server (e.g., 'my-filesystem')",
                },
                'name': {
                    'type': 'string',
                    'description': 'Human-readable name for the server',
                },
                'transport': {
                    'type': 'string',
                    'enum': ['stdio', 'http', 'sse'],
                    'description': 'Transport type',
                },
                'command': {
                    'type': 'string',
                    'description': 'Command to execute (required for stdio transport)',
                },
                'args': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Command arguments (for stdio transport)',
                    'default': [],
                },
                'url': {
                    'type': 'string',
                    'description': 'Server URL (required for http/sse transport)',
                },
                'env': {
                    'type': 'object',
                    'description': 'Environment variables (for stdio transport)',
                    'default': {},
                },
                'enabled': {
                    'type': 'boolean',
                    'description': 'Whether to enable the server immediately',
                    'default': True,
                },
                'auto_attach': {
                    'type': 'boolean',
                    'description': 'Whether to auto-attach tools to agents',
                    'default': True,
                },
                'timeout': {
                    'type': 'integer',
                    'description': 'Connection timeout in seconds',
                    'default': 30,
                },
            },
            'required': ['server_id', 'name', 'transport'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            mcp_manager = self.service_manager.get_service('mcp_servers_manager')

            if not mcp_manager:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: MCP Servers Manager not available',
                        }
                    ],
                    is_error=True,
                )

            server_id = arguments['server_id']

            # Create server entry
            server_entry = MCPServerEntry(
                name=arguments['name'],
                transport=arguments['transport'],
                command=arguments.get('command'),
                args=arguments.get('args', []),
                url=arguments.get('url'),
                env=arguments.get('env', {}),
                enabled=arguments.get('enabled', True),
                auto_attach=arguments.get('auto_attach', True),
                timeout=arguments.get('timeout', 30),
            )

            # Validate based on transport
            if server_entry.transport == 'stdio' and not server_entry.command:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': "Error: 'command' is required for stdio transport",
                        }
                    ],
                    is_error=True,
                )

            if server_entry.transport in ['http', 'sse'] and not server_entry.url:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Error: 'url' is required for {server_entry.transport} transport",
                        }
                    ],
                    is_error=True,
                )

            # Add the server
            await mcp_manager.add_server(server_id, server_entry)

            return MCPToolCallResult(
                content=[
                    {
                        'type': 'text',
                        'text': (
                            f"Successfully added MCP server '{server_id}' ({server_entry.name}). "
                            f'The server is {"enabled" if server_entry.enabled else "disabled"} '
                            f'and will {"auto-attach" if server_entry.auto_attach else "not auto-attach"} '
                            'tools to agents.'
                        ),
                    }
                ]
            )

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error: {e}'}],
                is_error=True,
            )
        except Exception as e:
            self.logger.error(f'Error adding MCP server: {e}')
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error adding MCP server: {e}'}],
                is_error=True,
            )


class UpdateMCPServerMCPTool(MCPTool):
    """Update an existing MCP server configuration."""

    @property
    def name(self) -> str:
        return 'update_mcp_server'

    @property
    def description(self) -> str:
        return (
            "Update an existing MCP server's configuration. You can change any settings "
            'including the name, transport details, enabled state, and auto-attach behavior.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'server_id': {
                    'type': 'string',
                    'description': 'Server identifier to update',
                },
                'name': {'type': 'string', 'description': 'New human-readable name'},
                'transport': {
                    'type': 'string',
                    'enum': ['stdio', 'http', 'sse'],
                    'description': 'Transport type',
                },
                'command': {
                    'type': 'string',
                    'description': 'Command to execute (for stdio transport)',
                },
                'args': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Command arguments',
                },
                'url': {
                    'type': 'string',
                    'description': 'Server URL (for http/sse transport)',
                },
                'env': {'type': 'object', 'description': 'Environment variables'},
                'enabled': {
                    'type': 'boolean',
                    'description': 'Whether server is enabled',
                },
                'auto_attach': {
                    'type': 'boolean',
                    'description': 'Whether to auto-attach tools',
                },
                'timeout': {
                    'type': 'integer',
                    'description': 'Connection timeout in seconds',
                },
            },
            'required': ['server_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            mcp_manager = self.service_manager.get_service('mcp_servers_manager')

            if not mcp_manager:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: MCP Servers Manager not available',
                        }
                    ],
                    is_error=True,
                )

            server_id = arguments['server_id']

            # Get existing server
            servers = await mcp_manager.list_servers()
            if server_id not in servers:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': f"Error: Server '{server_id}' not found",
                        }
                    ],
                    is_error=True,
                )

            existing = servers[server_id]

            # Create updated entry (merge with existing)
            server_entry = MCPServerEntry(
                name=arguments.get('name', existing.name),
                transport=arguments.get('transport', existing.transport),
                command=arguments.get('command', existing.command),
                args=arguments.get('args', existing.args),
                url=arguments.get('url', existing.url),
                env=arguments.get('env', existing.env),
                enabled=arguments.get('enabled', existing.enabled),
                auto_attach=arguments.get('auto_attach', existing.auto_attach),
                timeout=arguments.get('timeout', existing.timeout),
            )

            # Update the server
            await mcp_manager.update_server(server_id, server_entry)

            return MCPToolCallResult(
                content=[
                    {
                        'type': 'text',
                        'text': f"Successfully updated MCP server '{server_id}'",
                    }
                ]
            )

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error: {e}'}],
                is_error=True,
            )
        except Exception as e:
            self.logger.error(f'Error updating MCP server: {e}')
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error updating MCP server: {e}'}],
                is_error=True,
            )


class RemoveMCPServerMCPTool(MCPTool):
    """Remove an MCP server from the configuration."""

    @property
    def name(self) -> str:
        return 'remove_mcp_server'

    @property
    def description(self) -> str:
        return (
            'Remove an external MCP server from the configuration. This will disconnect '
            "the server if it's currently connected and detach all its tools from agents."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'server_id': {
                    'type': 'string',
                    'description': 'Server identifier to remove',
                }
            },
            'required': ['server_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            mcp_manager = self.service_manager.get_service('mcp_servers_manager')

            if not mcp_manager:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: MCP Servers Manager not available',
                        }
                    ],
                    is_error=True,
                )

            server_id = arguments['server_id']

            # Remove the server
            await mcp_manager.remove_server(server_id)

            return MCPToolCallResult(
                content=[
                    {
                        'type': 'text',
                        'text': f"Successfully removed MCP server '{server_id}'",
                    }
                ]
            )

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error: {e}'}],
                is_error=True,
            )
        except Exception as e:
            self.logger.error(f'Error removing MCP server: {e}')
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error removing MCP server: {e}'}],
                is_error=True,
            )


class ToggleMCPServerMCPTool(MCPTool):
    """Enable or disable an MCP server."""

    @property
    def name(self) -> str:
        return 'toggle_mcp_server'

    @property
    def description(self) -> str:
        return (
            'Enable or disable an external MCP server. Disabling a server will disconnect '
            'it and detach its tools. Enabling will reconnect and attach tools if auto-attach '
            'is enabled.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'server_id': {'type': 'string', 'description': 'Server identifier'},
                'enabled': {
                    'type': 'boolean',
                    'description': 'Whether to enable (true) or disable (false) the server',
                },
            },
            'required': ['server_id', 'enabled'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            mcp_manager = self.service_manager.get_service('mcp_servers_manager')

            if not mcp_manager:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: MCP Servers Manager not available',
                        }
                    ],
                    is_error=True,
                )

            server_id = arguments['server_id']
            enabled = arguments['enabled']

            # Toggle the server
            await mcp_manager.toggle_server(server_id, enabled)

            action = 'enabled' if enabled else 'disabled'
            return MCPToolCallResult(
                content=[
                    {
                        'type': 'text',
                        'text': f"Successfully {action} MCP server '{server_id}'",
                    }
                ]
            )

        except ValueError as e:
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error: {e}'}],
                is_error=True,
            )
        except Exception as e:
            self.logger.error(f'Error toggling MCP server: {e}')
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error toggling MCP server: {e}'}],
                is_error=True,
            )


class TestMCPConnectionMCPTool(MCPTool):
    """Test connectivity to an MCP server."""

    @property
    def name(self) -> str:
        return 'test_mcp_connection'

    @property
    def description(self) -> str:
        return (
            "Test the connection to an external MCP server to verify it's reachable and "
            'responding correctly. This will attempt to connect and discover tools without '
            'permanently connecting the server.'
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            'type': 'object',
            'properties': {
                'server_id': {
                    'type': 'string',
                    'description': 'Server identifier to test',
                }
            },
            'required': ['server_id'],
        }

    async def execute(self, arguments: dict[str, Any]) -> MCPToolCallResult:
        """Execute the tool."""
        try:
            mcp_manager = self.service_manager.get_service('mcp_servers_manager')

            if not mcp_manager:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': 'Error: MCP Servers Manager not available',
                        }
                    ],
                    is_error=True,
                )

            server_id = arguments['server_id']

            # Test the connection
            result = await mcp_manager.test_connection(server_id)

            if result['success']:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': (
                                f"✓ Connection test successful for '{server_id}'\n"
                                f'{result["message"]}'
                            ),
                        }
                    ]
                )
            else:
                return MCPToolCallResult(
                    content=[
                        {
                            'type': 'text',
                            'text': (
                                f"✗ Connection test failed for '{server_id}'\n"
                                f'{result["message"]}'
                            ),
                        }
                    ],
                    is_error=True,
                )

        except Exception as e:
            self.logger.error(f'Error testing MCP connection: {e}')
            return MCPToolCallResult(
                content=[{'type': 'text', 'text': f'Error testing connection: {e}'}],
                is_error=True,
            )
