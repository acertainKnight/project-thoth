"""
Pydantic models for external MCP server configuration.

These models define the schema for the mcps.json file that serves as the
single source of truth for external MCP server connections.
"""

from pydantic import BaseModel, Field


class MCPServerEntry(BaseModel):
    """Configuration for a single external MCP server."""

    name: str = Field(..., description='Human-readable name for the MCP server')
    enabled: bool = Field(
        default=True,
        description='Whether this server is enabled and should be connected',
    )
    transport: str = Field(..., description="Transport type: 'stdio', 'http', or 'sse'")

    # stdio transport fields
    command: str | None = Field(
        None, description="Command to execute for stdio transport (e.g., 'npx')"
    )
    args: list[str] = Field(
        default_factory=list,
        description='Arguments for the command (stdio transport)',
    )
    env: dict[str, str] = Field(
        default_factory=dict, description='Environment variables for the process'
    )

    # HTTP/SSE transport fields
    url: str | None = Field(
        None, description='URL for HTTP or SSE transport connections'
    )

    # Common fields
    auto_attach: bool = Field(
        default=True,
        alias='autoAttach',
        description='Whether to automatically attach discovered tools to Letta agents',
    )
    timeout: int = Field(default=30, description='Connection timeout in seconds')

    class Config:
        """Pydantic configuration."""

        populate_by_name = True


class MCPServersConfig(BaseModel):
    """Top-level configuration for all external MCP servers."""

    version: str = Field(default='1.0.0', description='Configuration schema version')
    mcp_servers: dict[str, MCPServerEntry] = Field(
        default_factory=dict,
        alias='mcpServers',
        description='Dictionary of MCP servers keyed by server ID',
    )

    class Config:
        """Pydantic configuration."""

        populate_by_name = True

    def get_enabled_servers(self) -> dict[str, MCPServerEntry]:
        """
        Get all enabled MCP servers.

        Returns:
            dict[str, MCPServerEntry]: Dictionary of enabled servers keyed by ID
        """
        return {
            server_id: server
            for server_id, server in self.mcp_servers.items()
            if server.enabled
        }

    def get_auto_attach_servers(self) -> dict[str, MCPServerEntry]:
        """
        Get all servers that should auto-attach tools to agents.

        Returns:
            dict[str, MCPServerEntry]: Dictionary of auto-attach enabled servers
        """
        return {
            server_id: server
            for server_id, server in self.mcp_servers.items()
            if server.enabled and server.auto_attach
        }
