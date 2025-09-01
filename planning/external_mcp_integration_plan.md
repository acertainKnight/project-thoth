# External MCP Tool Integration Plan for Thoth Agent

## Executive Summary

This plan outlines how to enable the Thoth agent to integrate and use external MCP (Model Context Protocol) tools and servers. The goal is to create a flexible, secure, and scalable system that allows users to extend the agent's capabilities by connecting to external MCP-compliant tools and services.

## Current Architecture Analysis

### Existing MCP Implementation
- **Server**: `MCPServer` in `src/thoth/mcp/server.py` - handles protocol messages and manages tools
- **Client**: `MCPClient` in `src/thoth/mcp/client.py` - connects to MCP servers via stdio/HTTP
- **Tools**: Internal tools inherit from `MCPTool` base class
- **Registry**: `MCPToolRegistry` manages tool registration and execution
- **Agent Integration**: Uses `langchain-mcp-adapters` with `MultiServerMCPClient`

### Key Components
1. **Protocol Handler**: Manages JSON-RPC 2.0 messages
2. **Transport Layer**: Supports stdio, HTTP, and SSE transports
3. **Tool Registry**: Handles tool discovery and execution
4. **Connection Manager**: Enterprise-grade connection pooling
5. **LangChain Integration**: Wraps MCP tools for LangChain compatibility

## Proposed Architecture for External MCP Integration

### 1. Multi-Server Connection Management

```python
class ExternalMCPServerConfig(BaseModel):
    """Configuration for an external MCP server."""
    name: str  # Unique identifier
    url: str  # Server URL or command
    transport: Literal["stdio", "http", "sse"]
    auth: Optional[AuthConfig] = None
    capabilities: Optional[MCPCapabilities] = None
    max_connections: int = 5
    timeout: int = 30
    retry_policy: RetryConfig = RetryConfig()
    health_check_interval: int = 60
    enabled: bool = True
```

### 2. Dynamic Tool Discovery and Registration

```python
class ExternalMCPManager:
    """Manages connections to external MCP servers."""
    
    def __init__(self, service_manager: ServiceManager):
        self.service_manager = service_manager
        self.external_servers: Dict[str, ExternalMCPServerConfig] = {}
        self.clients: Dict[str, MCPClient] = {}
        self.tool_cache: Dict[str, List[MCPToolSchema]] = {}
        
    async def add_server(self, config: ExternalMCPServerConfig) -> None:
        """Add and connect to an external MCP server."""
        
    async def discover_tools(self, server_name: str) -> List[MCPToolSchema]:
        """Discover available tools from an external server."""
        
    async def execute_external_tool(
        self, server_name: str, tool_name: str, arguments: Dict[str, Any]
    ) -> MCPToolCallResult:
        """Execute a tool on an external server."""
```

### 3. Unified Tool Registry

```python
class UnifiedMCPToolRegistry(MCPToolRegistry):
    """Extended registry that manages both internal and external tools."""
    
    def __init__(self, service_manager: ServiceManager):
        super().__init__(service_manager)
        self.external_manager = ExternalMCPManager(service_manager)
        self.external_tools: Dict[str, Tuple[str, MCPToolSchema]] = {}
        
    def register_external_tool(self, server_name: str, tool: MCPToolSchema) -> None:
        """Register an external tool with server mapping."""
        full_name = f"{server_name}.{tool.name}"
        self.external_tools[full_name] = (server_name, tool)
        
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> MCPToolCallResult:
        """Execute either internal or external tool."""
        if name in self.external_tools:
            server_name, tool_schema = self.external_tools[name]
            return await self.external_manager.execute_external_tool(
                server_name, tool_schema.name, arguments
            )
        return await super().execute_tool(name, arguments)
```

## Implementation Steps

### Phase 1: Configuration System (Week 1)

1. **Create Configuration Schema**
   - Define `ExternalMCPServerConfig` in `src/thoth/mcp/external_config.py`
   - Add validation for server URLs, transport types, and auth methods
   - Support environment variable configuration

2. **Extend Main Configuration**
   ```python
   # In src/thoth/utilities/config/services.py
   class ExternalMCPConfig(BaseSettings):
       """Configuration for external MCP servers."""
       servers: List[ExternalMCPServerConfig] = Field(
           default_factory=list,
           description="List of external MCP servers to connect to"
       )
       auto_discover: bool = Field(
           True, description="Automatically discover tools on connection"
       )
       namespace_prefix: bool = Field(
           True, description="Prefix external tools with server name"
       )
   ```

3. **Configuration File Support**
   ```yaml
   # Example: mcp_servers.yaml
   external_mcp:
     servers:
       - name: "github-copilot"
         url: "npx @github/copilot-mcp-server"
         transport: "stdio"
         enabled: true
       - name: "web-browser"
         url: "http://localhost:8080/mcp"
         transport: "http"
         auth:
           type: "bearer"
           token: "${MCP_BROWSER_TOKEN}"
       - name: "database-tools"
         url: "npx @db/mcp-postgres-server"
         transport: "stdio"
         auth:
           type: "env"
           env_var: "DATABASE_URL"
   ```

### Phase 2: Connection Management (Week 1-2)

1. **Implement ExternalMCPManager**
   - Create `src/thoth/mcp/external_manager.py`
   - Handle multiple transport types (stdio, HTTP, SSE)
   - Implement connection pooling per server
   - Add health checking and auto-reconnection

2. **Authentication Framework**
   ```python
   class MCPAuthHandler:
       """Handle authentication for external MCP servers."""
       
       async def authenticate(self, config: AuthConfig) -> Dict[str, Any]:
           if config.type == "bearer":
               return {"Authorization": f"Bearer {config.token}"}
           elif config.type == "oauth2":
               return await self._oauth2_flow(config)
           elif config.type == "api_key":
               return {"X-API-Key": config.api_key}
   ```

3. **Connection Lifecycle Management**
   - Lazy connection on first tool use
   - Graceful disconnection and cleanup
   - Connection state monitoring
   - Automatic retry with exponential backoff

### Phase 3: Tool Discovery and Registration (Week 2)

1. **Dynamic Tool Discovery**
   ```python
   async def discover_and_register_tools(self, server_config: ExternalMCPServerConfig):
       """Discover and register all tools from an external server."""
       client = await self._get_or_create_client(server_config)
       tools = await client.list_tools()
       
       for tool in tools:
           # Namespace external tools to avoid conflicts
           if self.config.namespace_prefix:
               tool.name = f"{server_config.name}.{tool.name}"
           
           # Register in unified registry
           self.registry.register_external_tool(server_config.name, tool)
   ```

2. **Tool Capability Negotiation**
   - Check server capabilities before registration
   - Handle version compatibility
   - Support feature detection
   - Graceful degradation for missing features

3. **Tool Metadata Enhancement**
   - Add server source information
   - Track tool availability status
   - Monitor performance metrics
   - Cache tool schemas

### Phase 4: Agent Integration (Week 2-3)

1. **Update ResearchAssistant**
   ```python
   async def _get_all_mcp_tools(self) -> List[Any]:
       """Get both internal and external MCP tools."""
       tools = []
       
       # Get internal tools
       internal_tools = await self._get_mcp_tools_via_adapter()
       tools.extend(internal_tools)
       
       # Get external tools if configured
       if self.service_manager.config.external_mcp.servers:
           external_tools = await self._get_external_mcp_tools()
           tools.extend(external_tools)
       
       return tools
   ```

2. **LangChain Adapter Extension**
   - Extend `MultiServerMCPClient` to support external servers
   - Handle tool namespacing in LangChain
   - Preserve tool metadata and descriptions

3. **Tool Execution Pipeline**
   - Route tool calls to correct server
   - Handle cross-server tool dependencies
   - Implement result transformation if needed

### Phase 5: Error Handling and Resilience (Week 3)

1. **Comprehensive Error Handling**
   ```python
   class ExternalMCPError(Exception):
       """Base exception for external MCP errors."""
       
   class ServerConnectionError(ExternalMCPError):
       """Failed to connect to external server."""
       
   class ToolExecutionError(ExternalMCPError):
       """Failed to execute tool on external server."""
   ```

2. **Fallback Mechanisms**
   - Cached tool results for offline mode
   - Alternative tool suggestions
   - Graceful degradation strategies
   - User notification system

3. **Circuit Breaker Pattern**
   - Prevent cascading failures
   - Automatic server isolation
   - Health check recovery
   - Rate limiting per server

### Phase 6: Monitoring and Observability (Week 3-4)

1. **Metrics Collection**
   ```python
   class ExternalMCPMetrics:
       """Collect metrics for external MCP operations."""
       server_connections: Counter
       tool_executions: Counter
       execution_duration: Histogram
       error_rate: Gauge
       active_connections: Gauge
   ```

2. **Logging Enhancement**
   - Structured logging for external calls
   - Request/response tracing
   - Performance profiling
   - Error analysis

3. **Dashboard Integration**
   - Real-time server status
   - Tool usage statistics
   - Performance metrics
   - Error tracking

### Phase 7: Security and Governance (Week 4)

1. **Security Framework**
   - Tool execution sandboxing
   - Input validation and sanitization
   - Output filtering
   - Rate limiting per tool/server

2. **Access Control**
   ```python
   class ToolAccessPolicy:
       """Define access policies for external tools."""
       allowed_users: List[str]
       allowed_roles: List[str]
       rate_limit: RateLimit
       data_access: DataAccessLevel
   ```

3. **Audit Trail**
   - Log all external tool executions
   - Track user actions
   - Monitor data flow
   - Compliance reporting

### Phase 8: Documentation and Examples (Week 4-5)

1. **User Documentation**
   - Configuration guide
   - Supported MCP servers list
   - Troubleshooting guide
   - Best practices

2. **Developer Documentation**
   - API reference
   - Extension guide
   - Custom server implementation
   - Testing strategies

3. **Example Configurations**
   - Popular MCP servers
   - Common use cases
   - Integration patterns
   - Performance optimization

## Example Usage

### 1. Adding a GitHub Copilot MCP Server
```python
# In configuration file
external_mcp:
  servers:
    - name: "github-copilot"
      url: "npx @github/copilot-mcp-server"
      transport: "stdio"
      auth:
        type: "env"
        env_var: "GITHUB_TOKEN"
```

### 2. Using External Tools in Agent
```python
# Tools appear with namespace prefix
agent: "Use the github-copilot.search_code tool to find Python implementations of MCP servers"
```

### 3. Programmatic Server Addition
```python
async def add_custom_mcp_server():
    config = ExternalMCPServerConfig(
        name="my-custom-tools",
        url="http://localhost:9000/mcp",
        transport="http",
        auth=AuthConfig(type="api_key", api_key="secret")
    )
    
    await external_manager.add_server(config)
    tools = await external_manager.discover_tools("my-custom-tools")
    print(f"Discovered {len(tools)} tools from my-custom-tools")
```

## Testing Strategy

### 1. Unit Tests
- Configuration validation
- Connection management
- Tool discovery
- Error handling

### 2. Integration Tests
- Mock MCP server for testing
- Multi-server scenarios
- Authentication flows
- Tool execution

### 3. End-to-End Tests
- Agent with external tools
- Performance benchmarks
- Failure scenarios
- Security testing

## Performance Considerations

1. **Connection Pooling**
   - Reuse connections per server
   - Configurable pool sizes
   - Connection timeout handling

2. **Caching Strategy**
   - Cache tool schemas
   - Cache authentication tokens
   - Cache health check results

3. **Async Optimization**
   - Parallel tool discovery
   - Concurrent execution where safe
   - Batch operations support

## Security Considerations

1. **Authentication Security**
   - Secure credential storage
   - Token rotation support
   - Certificate validation

2. **Network Security**
   - TLS/SSL enforcement
   - Proxy support
   - Network isolation options

3. **Execution Security**
   - Input sanitization
   - Output validation
   - Resource limits

## Migration Path

1. **Backward Compatibility**
   - Existing tools continue to work
   - No breaking changes to API
   - Gradual adoption possible

2. **Configuration Migration**
   - Auto-detect existing setups
   - Migration utilities
   - Validation tools

## Success Metrics

1. **Technical Metrics**
   - Number of external servers supported
   - Tool discovery success rate
   - Average connection latency
   - Error rates by server

2. **User Metrics**
   - External tools usage frequency
   - User satisfaction scores
   - Time saved by external tools
   - New use cases enabled

## Timeline

- **Week 1**: Configuration system and basic connection management
- **Week 2**: Tool discovery and registration
- **Week 3**: Agent integration and error handling
- **Week 4**: Security, monitoring, and documentation
- **Week 5**: Testing, optimization, and deployment

## Next Steps

1. Review and approve the plan
2. Set up development environment
3. Create initial configuration schema
4. Implement basic connection manager
5. Build prototype with simple external server

<function_calls>
<invoke name="todo_write">
<parameter name="merge">true