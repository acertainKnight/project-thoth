# External MCP Integration Quick Start Guide

## Overview

This guide provides a quick reference for implementing external MCP tool integration in the Thoth agent.

## Key Implementation Files to Create

### 1. External Configuration (`src/thoth/mcp/external_config.py`)

```python
"""
External MCP server configuration models.
"""
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class TransportType(str, Enum):
    """Supported MCP transport types."""
    STDIO = "stdio"
    HTTP = "http"
    SSE = "sse"


class AuthType(str, Enum):
    """Authentication types for external servers."""
    NONE = "none"
    BEARER = "bearer"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    ENV = "env"


class AuthConfig(BaseModel):
    """Authentication configuration."""
    type: AuthType = AuthType.NONE
    token: Optional[str] = None
    api_key: Optional[str] = None
    env_var: Optional[str] = None
    oauth_config: Optional[Dict[str, str]] = None


class RetryConfig(BaseModel):
    """Retry configuration for failed connections."""
    max_attempts: int = Field(3, description="Maximum retry attempts")
    initial_delay: float = Field(1.0, description="Initial retry delay in seconds")
    max_delay: float = Field(60.0, description="Maximum retry delay in seconds")
    exponential_base: float = Field(2.0, description="Exponential backoff base")


class ExternalMCPServerConfig(BaseModel):
    """Configuration for an external MCP server."""
    name: str = Field(..., description="Unique server identifier")
    url: str = Field(..., description="Server URL or command")
    transport: TransportType = Field(..., description="Transport type")
    auth: Optional[AuthConfig] = Field(None, description="Authentication config")
    max_connections: int = Field(5, description="Maximum concurrent connections")
    timeout: int = Field(30, description="Connection timeout in seconds")
    retry_policy: RetryConfig = Field(default_factory=RetryConfig)
    health_check_interval: int = Field(60, description="Health check interval")
    enabled: bool = Field(True, description="Whether server is enabled")
    
    class Config:
        """Pydantic config."""
        use_enum_values = True
```

### 2. External Manager (`src/thoth/mcp/external_manager.py`)

```python
"""
Manager for external MCP server connections.
"""
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .base_tools import MCPToolCallResult
from .client import MCPClient
from .external_config import ExternalMCPServerConfig
from .protocol import MCPToolSchema


class ExternalMCPManager:
    """Manages connections to external MCP servers."""
    
    def __init__(self):
        """Initialize the external MCP manager."""
        self.servers: Dict[str, ExternalMCPServerConfig] = {}
        self.clients: Dict[str, MCPClient] = {}
        self.tool_cache: Dict[str, List[MCPToolSchema]] = {}
        self._connection_locks: Dict[str, asyncio.Lock] = {}
        
    async def add_server(self, config: ExternalMCPServerConfig) -> None:
        """
        Add and connect to an external MCP server.
        
        Args:
            config: Server configuration
        """
        if not config.enabled:
            logger.info(f"Server {config.name} is disabled, skipping")
            return
            
        if config.name in self.servers:
            logger.warning(f"Server {config.name} already exists, updating config")
            
        self.servers[config.name] = config
        self._connection_locks[config.name] = asyncio.Lock()
        
        # Try to connect immediately if auto-discovery is enabled
        try:
            await self._ensure_connected(config.name)
            logger.info(f"Successfully added external MCP server: {config.name}")
        except Exception as e:
            logger.error(f"Failed to connect to {config.name}: {e}")
            
    async def remove_server(self, server_name: str) -> None:
        """Remove an external MCP server."""
        if server_name in self.clients:
            client = self.clients[server_name]
            await client.close()
            del self.clients[server_name]
            
        if server_name in self.servers:
            del self.servers[server_name]
            
        if server_name in self.tool_cache:
            del self.tool_cache[server_name]
            
        if server_name in self._connection_locks:
            del self._connection_locks[server_name]
            
        logger.info(f"Removed external MCP server: {server_name}")
        
    async def _ensure_connected(self, server_name: str) -> MCPClient:
        """Ensure connection to a server exists."""
        async with self._connection_locks[server_name]:
            if server_name in self.clients:
                return self.clients[server_name]
                
            config = self.servers[server_name]
            client = MCPClient(
                client_name=f"Thoth-{server_name}",
                client_version="1.0.0"
            )
            
            # Connect based on transport type
            if config.transport == "stdio":
                # Parse command from URL
                command = config.url.split()
                await client.connect_stdio(command)
            elif config.transport == "http":
                await client.connect_http(config.url)
            else:
                raise ValueError(f"Unsupported transport: {config.transport}")
                
            await client.initialize()
            self.clients[server_name] = client
            
            # Cache tools
            tools = await client.list_tools()
            self.tool_cache[server_name] = tools
            
            return client
            
    async def discover_tools(self, server_name: str) -> List[MCPToolSchema]:
        """
        Discover available tools from an external server.
        
        Args:
            server_name: Name of the server
            
        Returns:
            List of available tools
        """
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")
            
        client = await self._ensure_connected(server_name)
        tools = await client.list_tools()
        
        # Update cache
        self.tool_cache[server_name] = tools
        
        return tools
        
    async def execute_external_tool(
        self, 
        server_name: str, 
        tool_name: str, 
        arguments: Dict[str, Any]
    ) -> MCPToolCallResult:
        """
        Execute a tool on an external server.
        
        Args:
            server_name: Name of the server
            tool_name: Name of the tool
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        if server_name not in self.servers:
            raise ValueError(f"Unknown server: {server_name}")
            
        client = await self._ensure_connected(server_name)
        
        try:
            result = await client.call_tool(tool_name, arguments)
            
            # Convert to MCPToolCallResult
            return MCPToolCallResult(
                content=result.get("content", []),
                isError=result.get("isError", False)
            )
        except Exception as e:
            logger.error(f"Failed to execute {tool_name} on {server_name}: {e}")
            return MCPToolCallResult(
                content=[{
                    "type": "text",
                    "text": f"Error executing external tool: {str(e)}"
                }],
                isError=True
            )
            
    async def get_all_tools(self) -> Dict[str, List[MCPToolSchema]]:
        """Get all tools from all connected servers."""
        all_tools = {}
        
        for server_name in self.servers:
            try:
                tools = await self.discover_tools(server_name)
                all_tools[server_name] = tools
            except Exception as e:
                logger.error(f"Failed to get tools from {server_name}: {e}")
                
        return all_tools
        
    async def health_check(self, server_name: Optional[str] = None) -> Dict[str, bool]:
        """
        Check health of external servers.
        
        Args:
            server_name: Specific server to check (None for all)
            
        Returns:
            Health status by server
        """
        servers_to_check = [server_name] if server_name else list(self.servers.keys())
        health_status = {}
        
        for name in servers_to_check:
            try:
                client = await self._ensure_connected(name)
                # Try to list tools as a health check
                await client.list_tools()
                health_status[name] = True
            except Exception as e:
                logger.warning(f"Health check failed for {name}: {e}")
                health_status[name] = False
                
        return health_status
```

### 3. Unified Registry (`src/thoth/mcp/unified_registry.py`)

```python
"""
Unified tool registry for internal and external MCP tools.
"""
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from .base_tools import MCPTool, MCPToolCallResult, MCPToolRegistry
from .external_manager import ExternalMCPManager
from .protocol import MCPToolSchema


class UnifiedMCPToolRegistry(MCPToolRegistry):
    """Extended registry that manages both internal and external tools."""
    
    def __init__(self, service_manager):
        """Initialize unified registry."""
        super().__init__(service_manager)
        self.external_manager = ExternalMCPManager()
        self.external_tools: Dict[str, Tuple[str, MCPToolSchema]] = {}
        self.namespace_prefix = True
        
    def register_external_tool(self, server_name: str, tool: MCPToolSchema) -> None:
        """
        Register an external tool with server mapping.
        
        Args:
            server_name: Name of the external server
            tool: Tool schema from the server
        """
        # Create namespaced name
        if self.namespace_prefix:
            full_name = f"{server_name}.{tool.name}"
        else:
            full_name = tool.name
            
        self.external_tools[full_name] = (server_name, tool)
        logger.debug(f"Registered external tool: {full_name}")
        
    async def refresh_external_tools(self) -> None:
        """Refresh all external tools from connected servers."""
        self.external_tools.clear()
        
        all_tools = await self.external_manager.get_all_tools()
        
        for server_name, tools in all_tools.items():
            for tool in tools:
                self.register_external_tool(server_name, tool)
                
        logger.info(f"Refreshed {len(self.external_tools)} external tools")
        
    def get_tool_schemas(self) -> List[MCPToolSchema]:
        """Get schemas for all tools (internal and external)."""
        schemas = super().get_tool_schemas()
        
        # Add external tool schemas
        for full_name, (server_name, tool) in self.external_tools.items():
            # Create schema with namespaced name
            external_schema = MCPToolSchema(
                name=full_name,
                description=f"[{server_name}] {tool.description}",
                inputSchema=tool.inputSchema
            )
            schemas.append(external_schema)
            
        return schemas
        
    async def execute_tool(
        self, 
        name: str, 
        arguments: Dict[str, Any]
    ) -> MCPToolCallResult:
        """Execute either internal or external tool."""
        # Check if it's an external tool
        if name in self.external_tools:
            server_name, tool_schema = self.external_tools[name]
            return await self.external_manager.execute_external_tool(
                server_name, 
                tool_schema.name,  # Use original tool name
                arguments
            )
            
        # Otherwise, execute as internal tool
        return await super().execute_tool(name, arguments)
        
    def get_tool_names(self) -> List[str]:
        """Get names of all registered tools."""
        names = super().get_tool_names()
        names.extend(self.external_tools.keys())
        return names
```

### 4. Configuration Extension (`src/thoth/utilities/config/services.py`)

Add this to the existing file:

```python
class ExternalMCPConfig(BaseSettings):
    """Configuration for external MCP servers."""
    
    model_config = SettingsConfigDict(
        env_prefix='EXTERNAL_MCP_',
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
        extra='ignore',
    )
    
    servers: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of external MCP servers to connect to"
    )
    auto_discover: bool = Field(
        True, 
        description="Automatically discover tools on connection"
    )
    namespace_prefix: bool = Field(
        True, 
        description="Prefix external tools with server name"
    )
    config_file: Optional[str] = Field(
        None,
        description="Path to YAML config file for external servers"
    )
```

### 5. Agent Integration Update

Update `src/thoth/ingestion/agent_v2/core/agent.py`:

```python
async def _get_mcp_tools_via_adapter(self) -> list[Any]:
    """Get MCP tools using official LangChain MCP adapter patterns."""
    if not self.use_mcp_tools:
        return []

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient

        # Get internal MCP server details
        mcp_port = self.service_manager.config.mcp_port
        mcp_host = self.service_manager.config.mcp_host

        # Build server configuration
        servers = {
            'thoth': {
                'url': f'http://{mcp_host}:{mcp_port}/mcp',
                'transport': 'streamable_http',
            }
        }
        
        # Add external servers if configured
        external_config = getattr(self.service_manager.config, 'external_mcp', None)
        if external_config and external_config.servers:
            for server in external_config.servers:
                if server.get('enabled', True):
                    servers[server['name']] = {
                        'url': server['url'],
                        'transport': server.get('transport', 'stdio')
                    }

        logger.info(f'Initializing MCP tools from {len(servers)} servers...')

        # Use the official MultiServerMCPClient pattern
        self.mcp_client = MultiServerMCPClient(servers)

        # Load tools using the official pattern
        tools = await self.mcp_client.get_tools()

        if not tools:
            logger.warning('No MCP tools available - running in degraded mode')
            return []

        logger.info(f'Successfully loaded {len(tools)} MCP tools')
        return tools

    except ImportError as e:
        logger.error(f'Missing MCP dependencies: {e}')
        logger.error('Install with: pip install langchain-mcp-adapters')
        return []
    except Exception as e:
        logger.error(f'Failed to initialize MCP tools: {e}')
        logger.warning('Continuing in degraded mode without MCP tools')
        return []
```

## Usage Examples

### 1. Environment Variable Configuration

```bash
# .env file
EXTERNAL_MCP_SERVERS='[{"name": "github", "url": "npx @github/mcp-server", "transport": "stdio"}]'
EXTERNAL_MCP_AUTO_DISCOVER=true
EXTERNAL_MCP_NAMESPACE_PREFIX=true
```

### 2. YAML Configuration File

```yaml
# mcp_servers.yaml
external_mcp:
  servers:
    - name: github-copilot
      url: npx @github/copilot-mcp-server
      transport: stdio
      enabled: true
      auth:
        type: env
        env_var: GITHUB_TOKEN
        
    - name: web-browser
      url: http://localhost:8080/mcp
      transport: http
      auth:
        type: bearer
        token: ${MCP_BROWSER_TOKEN}
        
    - name: database-tools
      url: npx @modelcontextprotocol/server-postgres
      transport: stdio
      auth:
        type: env
        env_var: DATABASE_URL
```

### 3. Programmatic Usage

```python
# Example: Adding external MCP servers programmatically
from thoth.mcp.external_config import ExternalMCPServerConfig, AuthConfig
from thoth.mcp.unified_registry import UnifiedMCPToolRegistry

async def setup_external_tools(registry: UnifiedMCPToolRegistry):
    # Add GitHub Copilot server
    github_config = ExternalMCPServerConfig(
        name="github",
        url="npx @github/copilot-mcp-server",
        transport="stdio",
        auth=AuthConfig(type="env", env_var="GITHUB_TOKEN")
    )
    
    await registry.external_manager.add_server(github_config)
    
    # Add custom HTTP server
    custom_config = ExternalMCPServerConfig(
        name="my-tools",
        url="http://localhost:9000/mcp",
        transport="http",
        auth=AuthConfig(type="api_key", api_key="secret123")
    )
    
    await registry.external_manager.add_server(custom_config)
    
    # Refresh tools
    await registry.refresh_external_tools()
    
    # List all available tools
    tools = registry.get_tool_names()
    print(f"Available tools: {tools}")
```

### 4. Using External Tools in the Agent

```python
# Tools are automatically namespaced
user: "Use github.search_code to find Python MCP implementations"
agent: "I'll search for Python MCP implementations using the GitHub tool..."

# The agent automatically routes to the correct external server
user: "Query the database for user statistics"
agent: "I'll use database-tools.execute_query to get the user statistics..."
```

## Testing

### Mock External Server for Testing

```python
# tests/mcp/test_external_integration.py
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from thoth.mcp.external_config import ExternalMCPServerConfig
from thoth.mcp.external_manager import ExternalMCPManager


@pytest.fixture
async def mock_mcp_client():
    client = MagicMock()
    client.connect_stdio = AsyncMock()
    client.connect_http = AsyncMock()
    client.initialize = AsyncMock()
    client.list_tools = AsyncMock(return_value=[
        {
            "name": "test_tool",
            "description": "A test tool",
            "inputSchema": {"type": "object", "properties": {}}
        }
    ])
    client.call_tool = AsyncMock(return_value={
        "content": [{"type": "text", "text": "Test result"}],
        "isError": False
    })
    return client


@pytest.mark.asyncio
async def test_external_server_connection(mock_mcp_client):
    manager = ExternalMCPManager()
    
    config = ExternalMCPServerConfig(
        name="test-server",
        url="npx test-mcp-server",
        transport="stdio"
    )
    
    # Mock the client creation
    with patch('thoth.mcp.external_manager.MCPClient', return_value=mock_mcp_client):
        await manager.add_server(config)
        
        # Verify connection
        assert "test-server" in manager.servers
        
        # Test tool discovery
        tools = await manager.discover_tools("test-server")
        assert len(tools) == 1
        assert tools[0]["name"] == "test_tool"
```

## Deployment Checklist

1. **Configuration**
   - [ ] Update `.env` file with external server configs
   - [ ] Create `mcp_servers.yaml` if using file-based config
   - [ ] Set authentication credentials securely

2. **Dependencies**
   - [ ] Ensure `langchain-mcp-adapters` is installed
   - [ ] Install any required npm packages for stdio servers
   - [ ] Verify network access to HTTP servers

3. **Security**
   - [ ] Review authentication configurations
   - [ ] Validate server URLs and commands
   - [ ] Set up proper access controls

4. **Monitoring**
   - [ ] Enable health checks for external servers
   - [ ] Set up alerts for connection failures
   - [ ] Monitor tool execution performance

5. **Documentation**
   - [ ] Document available external servers
   - [ ] Create user guide for tool usage
   - [ ] Update API documentation