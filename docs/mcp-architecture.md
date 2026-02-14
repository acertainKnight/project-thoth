# MCP Server Architecture

How Thoth exposes research tools via the Model Context Protocol.

**Transport**: HTTP with SSE Streaming (Port 8000)
**Status**: Production

---

## Overview

The MCP server is how everything outside of Thoth talks to it — Letta agents, Claude Desktop, custom scripts, whatever speaks MCP. It implements the MCP 2025-06-18 specification over three concurrent transport layers (SSE, HTTP, stdio) and exposes 60 research tools organized across 16 functional domains.

The server handles transport failures gracefully: if one port is busy, the others keep running. Tool execution is lazy — classes are registered at startup, but instances are only created when first called. Parameter validation happens at the boundary (JSON Schema), so invalid inputs never reach business logic.

---

## Why MCP Instead of a Custom REST API

During initial architecture (mid-2024), I had a choice: build custom REST endpoints or adopt MCP.

I went with MCP because:
- **Interoperability**: One implementation works with Letta, Claude Desktop, and any future MCP client.
- **Future-proofing**: MCP adoption is growing across the AI ecosystem.
- **Tool composability**: MCP's schema format lets LLMs understand tool capabilities natively.
- **Resource management**: Built-in abstractions for files, databases, and APIs.

The trade-offs: JSON-RPC overhead vs raw HTTP (negligible in practice), and SSE complexity for streaming vs polling (worth it for real-time responses). Standardization over custom optimizations was the right call for a tool I plan to use for years.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TransportManager                          │
│  - Coordinates all transports                               │
│  - Routes messages to _handle_message                       │
│  - Graceful failure handling                                │
└──────────────┬──────────────────────────────────────────────┘
               │
       ┌───────┴───────┬─────────────┬──────────────┐
       │               │             │              │
   ┌───▼───┐      ┌───▼───┐    ┌────▼────┐        │
   │ stdio │      │ HTTP  │    │   SSE   │        │
   │ Port  │      │ :8082 │    │ :8081   │        │
   │ stdin │      │       │    │(primary)│        │
   │ stdout│      │       │    │         │        │
   └───────┘      └───────┘    └─────────┘        │
   │              │             │                  │
   ▼              ▼             ▼                  ▼
CLI Tools    Web Clients   Letta/Claude    (Future transports)
```

### Transport Comparison

| Transport | Use Case | Clients | Streaming | Production Port |
|-----------|----------|---------|-----------|-----------------|
| **HTTP** | Real-time agents, Web APIs | Letta, LangChain, Any HTTP client | SSE Streaming | 8082 (primary) |
| **SSE** | Dedicated SSE transport | Legacy SSE clients | Full | 8081 |
| **stdio** | Local CLI tools | MCP CLI utilities | Bidirectional | N/A (stdin/out) |

### Why SSE Is the Primary Transport

Server-Sent Events over WebSocket was a deliberate choice:

1. **Unidirectional flow matches MCP**: Client sends requests via HTTP POST to `/mcp`, server streams responses via SSE on `/sse`. Simpler than full-duplex WebSocket.
2. **Built-in reconnection**: Browsers reconnect dropped SSE connections automatically. Last-Event-ID support for resumable streams.
3. **Proxy-friendly**: HTTP-based, no protocol upgrade. Easier to load balance and works through corporate proxies.

Each client gets an isolated message queue to prevent cross-client leakage. Queues are cleaned up on disconnect.

### Transport Failure Handling

If one transport fails to start (port conflict, permission error), the others keep running. The server only raises an error if *all* transports fail. This is important for developer experience — local dev often has port conflicts, and you don't want the whole server to die because SSE port 8081 is taken when HTTP on 8082 works fine.

---

## Protocol Layer

All messages are validated through Pydantic models at the protocol boundary. The protocol handler is a Facade over JSON-RPC 2.0 complexity.

Key invariants enforced:
- **Requests** (have `id`): Server must respond with matching `id`
- **Notifications** (no `id`): Server must not respond
- **Responses**: Exactly one of `result` or `error`, never both

A model validator catches violations at construction time rather than in production:

```python
@model_validator(mode='after')
def validate_response_structure(self):
    if self.result is not None and self.error is not None:
        raise ValueError('Response cannot have both result and error')
```

---

## Tool System

### Registry Design

Tools use lazy instantiation with class registration:

```python
class MCPToolRegistry:
    def register_class(self, tool_class: type[MCPTool]):
        """Store class reference. Instance created on first use."""
        temp = tool_class(self.service_manager)
        self._tool_classes[temp.name] = tool_class

    def get_tool(self, name: str) -> MCPTool | None:
        """Lazy instantiation on first access."""
        if name in self._tools:
            return self._tools[name]
        if name in self._tool_classes:
            tool = self._tool_classes[name](self.service_manager)
            self._tools[name] = tool
            return tool
```

**Why lazy?** 60 tools registered at startup, but most calls only hit a handful. Creating instances on demand keeps memory down and startup fast. ServiceManager is injected at instantiation, so tools can access any service without circular dependency issues.

### Validation

Tools validate inputs via JSON Schema. LLMs understand JSON Schema natively, clients can validate before sending, and invalid parameters never reach `execute()`. Clear error messages help LLMs retry with corrected inputs.

### Tool Categories

**Discovery Tools** (`discovery_tools.py`): Paper discovery source management across ArXiv, Semantic Scholar, etc. Each source has different required fields, so there's a separate tool per source type for type safety and LLM clarity.

**Processing Tools** (`processing_tools.py`): PDF processing and article management. Thin wrappers over the processing service — the tool validates inputs, the service handles business logic, the tool formats output for MCP.

**Advanced RAG Tools** (`advanced_rag_tools.py`, `research_qa_tools.py`): Vector search, indexing, and question answering. Includes both standard hybrid RAG (`answer_research_question`) and the agentic pipeline (`agentic_research_question`) with query expansion, document grading, and hallucination checking.

Standard hybrid search pipeline:
```
MCP tool call → RAG Manager → Parallel Retrieval
    ├─ Semantic search (pgvector cosine similarity)
    └─ BM25 search (PostgreSQL tsvector)
        ↓
    RRF Fusion → Reranking (LLM or Cohere) → Results
```

Agentic pipeline:
```
MCP tool call → AgenticRAGOrchestrator (LangGraph)
    ↓
[Classify] → [Expand Query] → [Decompose] → [Retrieve]
    ↓
[Grade Documents] → low relevance? → [Rewrite Query] → retry
    ↓
[Rerank] → [Generate Answer] → [Check Hallucination]
    ↓
grounded? → return answer
not grounded? → retry with tighter retrieval
```

The agentic tool pushes step-by-step progress updates via WebSocket (`/ws/progress`) so the Obsidian UI shows what the pipeline is doing in real time. Trade-off: 3-6x slower than standard RAG, but noticeably better answers for complex multi-hop questions.

**Browser Workflow Tools** (`browser_workflow_tools.py`): Automated web scraping using the Command pattern — workflows are stored as data (JSON step sequences), not code. This means workflows can be modified, templated, and version-controlled without touching Python.

### Error Handling

All tools use the same error pattern: include the exception type in the response (helps LLMs understand what went wrong), log the full traceback (for debugging), set `isError=True`. LLMs can often recover from errors if they get enough context about what failed.

---

## Resource Management

Resources abstract data sources (files, databases, APIs) for MCP clients.

**File Resource Provider**: Exposes vault files. Uses a whitelist approach for security — resolves symlinks before checking, rejects path traversal attempts. Binary files get base64-encoded since JSON-RPC can't transmit raw bytes.

**Knowledge Base Provider**: Interface defined, implementation stubbed. Will expose articles as `knowledge://` URIs when the need arises. Following YAGNI — the provider pattern makes adding it straightforward later.

---

## Deployment

### Docker

```yaml
services:
  thoth-mcp:
    command: ["python", "-m", "thoth", "mcp", "full",
              "--host", "0.0.0.0", "--http-port", "8000"]
    ports:
      - "8082:8000"
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.25'
```

The MCP server is lightweight — stateless, mostly JSON parsing and network I/O. Heavy work happens in the service layer. 512MB is generous.

### Integration with Letta

```
1. Letta agent created via API (port 8283)
2. Letta configures MCP server URL: http://thoth-mcp:8000
3. Letta opens SSE connection to /sse endpoint
4. Letta sends tool calls via POST /mcp
5. Thoth streams responses via SSE
6. Letta Nginx proxy (8284) handles SSE timeout management
```

The Nginx proxy in front of Letta SSE handles long-lived connections with `proxy_read_timeout 300s` for 5-minute tool executions, connection pooling with `keepalive 32`, and no buffering so events stream immediately.

### Health Checks

The `/health` endpoint reports tool count, active transports, and protocol initialization state. Docker healthcheck runs every 30 seconds with a 60-second startup grace period.

---

## Performance

| Metric | Value | Notes |
|--------|-------|-------|
| Startup Time | ~5s | Includes service initialization |
| Tool Registration | <100ms | 60 tools, lazy instantiation |
| Request Latency | 10-50ms | HTTP transport, excludes tool execution |
| SSE Throughput | 1000+ msg/s | Limited by Python asyncio |
| Memory Footprint | 128-256MB | Base server + tool classes |
| Concurrent Clients | 100+ | Per-client queue isolation |

**Scaling**: The server is stateless, so horizontal scaling means running multiple instances behind a load balancer. SSE connections need sticky sessions (Nginx `ip_hash`). Each instance gets its own PostgreSQL connection pool.

---

## Security

**Authentication**: None currently. The MCP server runs on Docker's internal network (`thoth-network`), so only the Letta container can reach it. Adding API key auth is planned for when external access is needed.

**File access**: Whitelist-based path validation prevents directory traversal. Only files under configured base paths are accessible.

---

## Known Issues

1. **Prompts not implemented**: Returns empty list. No clients currently use MCP prompts. Will implement when Letta adds prompt template support.
2. **stdio transport in Docker**: Disabled (`THOTH_DOCKER=1` check). Permission issues with stdin/stdout in containers. Use HTTP/SSE instead.
3. **No per-tool timeout**: Long-running tools (PDF processing) can block. Plan: add `timeout_seconds` to tool schema.

---

## Future Work

- **Tool result caching**: For idempotent tools like `list_skills` or `collection_stats`. Challenge is invalidation for tools with side effects.
- **Metrics**: Prometheus counters and histograms for tool execution duration and error rates.
- **Tool versioning**: Backward compatibility when tool schemas change (`discover_papers_v1`, `discover_papers_v2`).

---

*Last Updated: February 2026*
