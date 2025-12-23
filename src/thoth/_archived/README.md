# Archived Code

This directory contains code that has been archived during the Thoth MCP refactoring.

## Why was this code archived?

As part of the architectural refactoring to separate concerns between MCP tools and agent management, the following components have been moved to this archive:

### agent_v2/
**Archived Date**: 2025-12-22
**Reason**: Agent management has been migrated to Letta platform. The LangGraph-based agent implementation is no longer needed as Letta provides superior agent orchestration, memory management, and multi-agent coordination.

**Replacement**: Letta agents accessed via:
- Letta REST API (port 8283)
- Letta MCP server
- Optional proxy endpoints in Thoth API

### memory/
**Archived Date**: 2025-12-22
**Reason**: Memory management has been migrated to Letta's built-in memory system. The custom memory implementation (checkpointer, store, summarization) is no longer needed as Letta provides:
- Built-in checkpointing
- Message history
- Archival memory (RAG-backed long-term storage)
- Recall memory (entity extraction and tracking)

**Replacement**: Letta's integrated memory system

### agents/
**Archived Date**: 2025-12-22
**Reason**: Custom orchestrator and workflow agents have been replaced by Letta's multi-agent capabilities. The custom implementation is no longer needed as Letta provides:
- Built-in agent orchestration
- Dynamic agent creation
- Tool calling and coordination
- Smart workflow management

**Replacement**: Letta's orchestration system

## Current Architecture

After this refactoring, Thoth follows a clean separation of concerns:

1. **MCP Server** (`src/thoth/mcp/`)
   - 60+ research tools exposed via MCP protocol
   - RAG functionality
   - Document processing
   - Discovery and article management

2. **Backend Services** (`src/thoth/services/`)
   - ArticleService
   - DiscoveryService
   - PostgresService
   - RAG pipelines

3. **Agent Management** (External - Letta)
   - All agent logic handled by Letta
   - Accessed via Letta REST API or MCP
   - Optional convenience proxy endpoints in Thoth API

## Restoration

If you need to restore any of this code, use:

```bash
# Restore agent_v2
git checkout HEAD -- src/thoth/_archived/agent_v2
git mv src/thoth/_archived/agent_v2 src/thoth/ingestion/agent_v2

# Restore memory
git checkout HEAD -- src/thoth/_archived/memory
git mv src/thoth/_archived/memory src/thoth/memory

# Restore agents
git checkout HEAD -- src/thoth/_archived/agents
git mv src/thoth/_archived/agents src/thoth/agents
```

## References

- **Letta Documentation**: https://docs.letta.com/
- **Letta MCP Server**: https://github.com/cpacker/letta-mcp-server
- **MCP Specification**: https://modelcontextprotocol.io/
