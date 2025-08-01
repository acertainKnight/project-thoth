# MCP Conversion Plan: True Protocol Compliance

## Overview

This document outlines the plan to convert Thoth's tool calling and agent system to follow true Model Context Protocol (MCP) standards, enabling easier tool creation and better integration with MCP-compliant clients and servers.

## Current System Analysis

### Strengths
- ✅ Existing MCP server foundation with FastAPI
- ✅ Tool registry system for management
- ✅ Service manager architecture
- ✅ LangGraph agent with tool binding

### Issues
- ❌ Tools use LangChain format, not MCP standard
- ❌ Missing proper MCP JSON-RPC 2.0 compliance
- ❌ No MCP initialization handshake
- ❌ Limited to HTTP transport (missing stdio, SSE)
- ❌ No support for MCP resources and prompts

## Target MCP Architecture

### 1. MCP Message Format Compliance

**Current**: Custom FastAPI endpoints
```python
@app.post("/chat")
async def chat(request: ChatRequest):
    return {"response": "...", "tool_calls": [...]}
```

**Target**: JSON-RPC 2.0 compliant
```python
# Initialize handshake
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2025-06-18",
    "capabilities": {
      "tools": {"listChanged": true}
    }
  }
}

# Tool call
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "create_arxiv_source",
    "arguments": {
      "name": "ml_papers",
      "keywords": ["machine learning"]
    }
  }
}
```

### 2. MCP Tool Definition Standard

**Current**: LangChain BaseTool
```python
class CreateArxivSourceTool(BaseThothTool):
    name = "create_arxiv_source"
    description = "Create an ArXiv discovery source"

    def _run(self, input_str: str) -> str:
        # Implementation
```

**Target**: MCP Tool Schema
```python
{
  "name": "create_arxiv_source",
  "description": "Create an ArXiv discovery source",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "keywords": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["name", "keywords"]
  }
}
```

### 3. Protocol Transport Support

**Current**: HTTP only
**Target**: Multiple transports
- Stdio (for CLI integration)
- HTTP with Server-Sent Events
- WebSocket support

### 4. MCP Resource Support

Add support for MCP resources (files, documents, data):
```python
{
  "uri": "file:///path/to/document.pdf",
  "name": "Research Paper",
  "description": "Academic paper on machine learning",
  "mimeType": "application/pdf"
}
```

## Implementation Plan

### Phase 1: Core MCP Protocol (Week 1)

1. **MCP Message Handler**
   - Implement JSON-RPC 2.0 message parsing
   - Add initialization handshake support
   - Create proper error handling

2. **Tool Schema Conversion**
   - Convert existing tools to MCP format
   - Add JSON Schema validation
   - Maintain backward compatibility

3. **Transport Layer**
   - Add stdio transport for CLI
   - Enhance HTTP with proper JSON-RPC
   - Prepare for SSE support

### Phase 2: Enhanced Features (Week 2)

1. **Resource Management**
   - Add file/document resource support
   - Implement resource discovery
   - Connect to knowledge base

2. **Prompt Templates**
   - Convert to MCP prompt format
   - Add dynamic prompt generation
   - Template parameter validation

3. **Client SDK**
   - Create Python MCP client
   - Add TypeScript client support
   - Documentation and examples

### Phase 3: Integration & Testing (Week 3)

1. **Agent Integration**
   - Update LangGraph agent for MCP
   - Test tool calling flows
   - Performance optimization

2. **External Integration**
   - Test with MCP-compliant clients
   - Integration with Claude Code
   - Third-party tool support

3. **Documentation**
   - API documentation
   - Developer guides
   - Migration documentation

## Technical Specifications

### MCP Server Structure
```
src/thoth/mcp/
├── server/
│   ├── __init__.py
│   ├── protocol.py      # JSON-RPC 2.0 handler
│   ├── transports.py    # Stdio, HTTP, SSE
│   └── handlers.py      # Tool/resource handlers
├── tools/
│   ├── __init__.py
│   ├── base.py          # MCP tool base class
│   ├── registry.py      # MCP tool registry
│   └── schemas.py       # JSON Schema definitions
├── resources/
│   ├── __init__.py
│   ├── manager.py       # Resource discovery
│   └── types.py         # Resource type definitions
└── client/
    ├── __init__.py
    ├── connection.py    # MCP client connection
    └── sdk.py           # Client SDK interface
```

### Key Classes

```python
class MCPServer:
    """MCP-compliant server implementation"""

class MCPTool:
    """MCP tool definition with JSON Schema"""

class MCPResource:
    """MCP resource for file/data access"""

class MCPTransport:
    """Base transport for stdio/HTTP/SSE"""
```

## Benefits of True MCP Compliance

### 1. Easier Tool Development
- Standard JSON Schema definitions
- Automatic validation
- Better error handling
- Clear documentation format

### 2. Better Integration
- Works with any MCP client
- Standard protocol handshake
- Compatible with Claude Code
- Future-proof architecture

### 3. Enhanced Capabilities
- Resource management
- Multiple transport options
- Streaming support
- Protocol versioning

### 4. Developer Experience
- Auto-generated client SDKs
- Standard tooling support
- Better debugging
- Community ecosystem

## Migration Strategy

### Backward Compatibility
- Keep existing FastAPI endpoints during transition
- Gradual tool migration
- Feature flags for new/old systems
- Deprecation warnings with timeline

### Testing Strategy
- Unit tests for each MCP component
- Integration tests with real clients
- Performance benchmarks
- Compatibility testing

### Rollout Plan
1. **Development Environment**: Test with internal tools
2. **Staging**: Limited user testing
3. **Production**: Gradual rollout with fallback
4. **Full Migration**: Remove legacy endpoints

## Success Metrics

1. **Compliance**: 100% MCP specification compliance
2. **Performance**: &lt;10ms tool call latency
3. **Compatibility**: Works with 5+ MCP clients
4. **Developer Experience**: 50% faster tool development
5. **Reliability**: 99.9% uptime with error handling

## Timeline

- **Week 1**: Core protocol implementation
- **Week 2**: Enhanced features and resources
- **Week 3**: Integration and testing
- **Week 4**: Documentation and rollout

This conversion will position Thoth as a leading MCP-compliant research assistant with state-of-the-art tool integration capabilities.
