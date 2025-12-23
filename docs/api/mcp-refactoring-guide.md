# Thoth MCP Refactoring Guide

## Overview

As of December 2025, Thoth has been refactored to cleanly separate concerns between MCP tools and agent management. This guide explains the new architecture and how to use the refactored system.

## Architecture Changes

### Before Refactoring

```
Thoth Monolith
├── MCP Server (tools)
├── Agent Management (LangGraph)
├── Memory Management (custom)
└── Orchestration (custom)
```

### After Refactoring

```
Thoth Ecosystem
├── Thoth MCP Server (port 8001/8002)
│   ├── 54+ Research Tools
│   ├── RAG Functionality
│   ├── Document Processing
│   └── Discovery Services
│
└── Letta Platform (port 8283)
    ├── Agent Management
    ├── Memory System
    ├── Tool Orchestration
    └── Multi-Agent Coordination
```

## What Changed

### Archived Components

The following components have been moved to `src/thoth/_archived/`:

1. **agent_v2/** - LangGraph-based agent implementation
   - Replaced by Letta's agent orchestration

2. **memory/** - Custom memory system (checkpointer, store, summarization)
   - Replaced by Letta's integrated memory (archival, recall, core)

3. **agents/** - Custom orchestrator and workflow agents
   - Replaced by Letta's multi-agent capabilities

### Active Components

The following components remain active and have been enhanced:

1. **MCP Server** (`src/thoth/mcp/`)
   - 54 research tools exposed via MCP protocol
   - SSE transport on port 8001 (primary)
   - HTTP transport on port 8002 (secondary)
   - Health check endpoint added

2. **Backend Services** (`src/thoth/services/`)
   - ArticleService
   - DiscoveryService
   - PostgresService
   - RAG pipelines

3. **API Endpoints** (`src/thoth/server/routers/`)
   - Tool management endpoints (unchanged)
   - Optional Letta proxy endpoints (new)
   - Research and discovery endpoints (unchanged)

## MCP Server Configuration

### Port Assignments

- **Port 8001**: SSE transport (primary, for streaming)
- **Port 8002**: HTTP transport (secondary, for simple requests)
- **Port 8283**: Letta REST API (external service)

### Starting MCP Server

```python
from thoth.mcp.server import start_mcp_server
from thoth.services.service_manager import ServiceManager

service_manager = ServiceManager()

await start_mcp_server(
    service_manager=service_manager,
    enable_stdio=True,    # For CLI integration
    enable_sse=True,      # Primary transport (port 8001)
    enable_http=True,     # Secondary transport (port 8002)
    sse_host='localhost',
    sse_port=8001,
    http_host='localhost',
    http_port=8002,
)
```

### Health Check

The MCP server now includes a health check endpoint:

```python
# Via MCP protocol
response = await mcp_client.call('health')

# Response:
{
    "status": "healthy",
    "server": {
        "name": "Thoth Research Assistant",
        "version": "1.0.0"
    },
    "tools": {
        "count": 54,
        "registered": true
    },
    "transports": {
        "active": ["stdio", "sse", "http"],
        "count": 3
    },
    "protocol": {
        "initialized": true
    }
}
```

## Available MCP Tools (54 Total)

### Query Management (5 tools)
- `list_queries` - List all research queries
- `create_query` - Create new research query
- `get_query` - Get query details
- `update_query` - Update query
- `delete_query` - Delete query

### Discovery Sources (9 tools)
- `list_discovery_sources` - List all discovery sources
- `create_arxiv_source` - Create arXiv source
- `create_pubmed_source` - Create PubMed source
- `create_crossref_source` - Create Crossref source
- `create_openalex_source` - Create OpenAlex source
- `create_biorxiv_source` - Create bioRxiv source
- `get_discovery_source` - Get source details
- `run_discovery` - Execute discovery for source
- `delete_discovery_source` - Delete source

### Processing Tools (5 tools)
- `process_pdf` - Process single PDF
- `batch_process_pdfs` - Batch process PDFs
- `get_article_details` - Get article details
- `list_articles` - List articles
- `collection_stats` - Get collection statistics

### Article Management (3 tools)
- `search_articles` - Search articles
- `update_article_metadata` - Update metadata
- `delete_article` - Delete article

### Tag Management (4 tools)
- `consolidate_tags` - Consolidate tags
- `suggest_tags` - Suggest tags for article
- `manage_tag_vocabulary` - Manage vocabulary
- `consolidate_and_retag` - Consolidate and retag

### Citation Tools (3 tools)
- `format_citations` - Format citations
- `export_bibliography` - Export bibliography
- `extract_citations` - Extract citations from text

### Analysis Tools (4 tools)
- `evaluate_article` - Evaluate article quality
- `analyze_topic` - Analyze research topic
- `find_related_papers` - Find related papers
- `generate_research_summary` - Generate summary

### Data Management (4 tools)
- `backup_collection` - Backup collection
- `export_article_data` - Export data
- `generate_reading_list` - Generate reading list
- `sync_with_obsidian` - Sync with Obsidian

### PDF & Content (4 tools)
- `locate_pdf` - Locate PDF file
- `validate_pdf_sources` - Validate sources
- `extract_pdf_metadata` - Extract metadata
- `download_pdf` - Download PDF

### Web Search (1 tool)
- `web_search` - Search web

### Advanced RAG (3 tools)
- `reindex_collection` - Reindex collection
- `optimize_search` - Optimize search
- `create_custom_index` - Create custom index

### Memory Tools (7 tools)
- `core_memory_append` - Append to core memory
- `core_memory_replace` - Replace core memory
- `archival_memory_insert` - Insert into archival
- `archival_memory_search` - Search archival
- `conversation_search` - Search conversations
- `memory_stats` - Get memory statistics
- `memory_health_check` - Check memory health

## Agent Management with Letta

All agent management is now handled by the Letta platform. Agents should interact with Letta directly, but Thoth provides optional convenience proxy endpoints.

### Letta Direct Access (Recommended)

```python
import httpx

# List agents
response = httpx.get('http://localhost:8283/api/agents')

# Send message to agent
response = httpx.post(
    'http://localhost:8283/api/agents/research_assistant/messages',
    json={
        'message': 'Find papers on quantum computing',
        'user_id': 'user123'
    }
)

# Create new agent
response = httpx.post(
    'http://localhost:8283/api/agents',
    json={
        'name': 'literature_reviewer',
        'description': 'Agent for reviewing literature',
        'tools': ['search_articles', 'analyze_topic']
    }
)
```

### Thoth Proxy Endpoints (Optional)

For backward compatibility and convenience, Thoth provides proxy endpoints:

```bash
# Check Letta status
GET /api/agent/status

# List agents
GET /api/agent/list

# Send chat message
POST /api/agent/chat
{
    "message": "Find papers on AI",
    "agent_name": "research_assistant",
    "user_id": "user123"
}

# Create agent
POST /api/agent/create
{
    "name": "my_agent",
    "description": "Custom agent",
    "tools": ["search_articles"]
}

# Get configuration
GET /api/agent/config

# Get info and documentation
GET /api/agent/info
```

## Migration Guide

### For MCP Tool Users

No changes needed! All 54 tools continue to work as before.

```python
# Before and After - Same API
from thoth.mcp.tools import MCPToolRegistry
from thoth.services.service_manager import ServiceManager

service_manager = ServiceManager()
registry = MCPToolRegistry(service_manager)

# Register all tools
from thoth.mcp.tools import register_all_mcp_tools
register_all_mcp_tools(registry)

# Use tools
result = await registry.execute_tool('search_articles', {
    'query': 'quantum computing',
    'limit': 10
})
```

### For Agent Users

**Before (deprecated):**
```python
from thoth.agents.orchestrator import ThothOrchestrator

orchestrator = ThothOrchestrator()
response = await orchestrator.handle_message('Find papers')
```

**After (recommended):**
```python
import httpx

# Use Letta REST API directly
async with httpx.AsyncClient() as client:
    response = await client.post(
        'http://localhost:8283/api/agents/research_assistant/messages',
        json={'message': 'Find papers', 'user_id': 'user123'}
    )
```

**After (convenience proxy):**
```python
import httpx

# Use Thoth proxy endpoint
async with httpx.AsyncClient() as client:
    response = await client.post(
        'http://localhost:8000/api/agent/chat',
        json={'message': 'Find papers'}
    )
```

### For Memory Users

**Before (deprecated):**
```python
from thoth.memory.store import MemoryStore

store = MemoryStore()
store.save('key', 'value')
```

**After:**
```python
# Use Letta's memory tools via MCP
result = await registry.execute_tool('archival_memory_insert', {
    'content': 'Important research finding...'
})

# Or use Letta API directly
response = httpx.post(
    'http://localhost:8283/api/agents/{agent_id}/memory',
    json={'content': 'Important finding'}
)
```

## Docker Configuration

### docker-compose.yml

```yaml
services:
  thoth-mcp:
    build: .
    ports:
      - "8001:8001"  # SSE transport
      - "8002:8002"  # HTTP transport
    environment:
      - MCP_SSE_PORT=8001
      - MCP_HTTP_PORT=8002
    depends_on:
      - postgres

  letta:
    image: letta/letta:latest
    ports:
      - "8283:8283"  # Letta REST API
    environment:
      - LETTA_SERVER_PORT=8283
    volumes:
      - letta-data:/root/.letta
```

## Environment Variables

### MCP Server
```bash
# Transport configuration
MCP_SSE_PORT=8001        # SSE transport port (primary)
MCP_HTTP_PORT=8002       # HTTP transport port (secondary)
MCP_ENABLE_STDIO=true    # Enable stdio transport

# Database
DATABASE_URL=postgresql://...

# API Keys
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
```

### Letta Integration
```bash
# Letta configuration
LETTA_BASE_URL=http://localhost:8283
LETTA_SERVER_PASS=...    # Letta API key
```

## Testing

### Test MCP Server

```bash
# Test health endpoint
curl http://localhost:8002/health

# Test tool via HTTP
curl -X POST http://localhost:8002/rpc \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "list_articles",
      "arguments": {"limit": 5}
    },
    "id": 1
  }'
```

### Test Letta Integration

```bash
# Check Letta status
curl http://localhost:8283/health

# List agents
curl http://localhost:8283/api/agents

# Send message via Thoth proxy
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find papers on quantum computing",
    "agent_name": "research_assistant"
  }'
```

## Benefits of Refactoring

1. **Separation of Concerns**
   - MCP server focuses on research tools
   - Letta handles all agent management

2. **Improved Scalability**
   - Services can scale independently
   - Letta's proven architecture for agents

3. **Better Maintenance**
   - Smaller, focused codebases
   - Easier to debug and test

4. **Enhanced Features**
   - Leverage Letta's advanced memory system
   - Built-in multi-agent coordination
   - Professional agent management UI

5. **Future-Proof**
   - Both systems evolve independently
   - Easy to upgrade components

## Troubleshooting

### MCP Server Not Starting

```bash
# Check port availability
lsof -i :8001
lsof -i :8002

# Check logs
docker logs thoth-mcp

# Verify tool registration
python -c "from thoth.mcp.tools import MCP_TOOL_CLASSES; print(len(MCP_TOOL_CLASSES))"
# Should output: 54
```

### Letta Connection Issues

```bash
# Check Letta is running
curl http://localhost:8283/health

# Check environment variable
echo $LETTA_BASE_URL

# Test from Thoth
curl http://localhost:8000/api/agent/status
```

### Tool Not Found

```bash
# List available tools
curl http://localhost:8002/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'
```

## Resources

- **Thoth Documentation**: [Link to main docs]
- **Letta Documentation**: https://docs.letta.com/
- **MCP Specification**: https://modelcontextprotocol.io/
- **Letta MCP Server**: https://github.com/cpacker/letta-mcp-server

## Support

For issues or questions:
1. Check archived code: `src/thoth/_archived/README.md`
2. Review this migration guide
3. Consult Letta documentation for agent issues
4. File issues on GitHub
