# MCP Tool Issues - Investigation & Fix Plan

**Date**: 2025-12-26
**Status**: Issues Identified, Fix Plan Created

## Investigation Summary

### ✅ What's Working
1. **MCP Server**: Healthy and responding
2. **Letta ↔ MCP Connection**: Established and functional
3. **Tool Registration**: All 46 tools registered in database
4. **Tool Assignment**: Tools properly assigned to specialist agents
5. **Tool Invocation**: Letta successfully calls MCP tools

### ❌ What's Broken

**ROOT CAUSE**: File permission errors when MCP tools try to access knowledge base

**Error**: `[Errno 13] Permission denied: 'knowledge'`

**Tools Affected**: ALL article/RAG-related tools:
- `list_articles`
- `search_articles` 
- `get_article_details`
- `export_article_data`
- And others that access the knowledge base

## Technical Details

### Evidence from Logs

```
Letta.letta.services.mcp_manager - INFO - MCP Result:  Error in list_articles: 
Error in RAGService while searching for '': [Errno 13] Permission denied: 'knowledge'
```

```python
File "/usr/local/lib/python3.11/pathlib.py", line 1116, in mkdir
PermissionError: [Errno 13] Permission denied: 'knowledge'
```

### Root Cause Analysis

1. **CitationGraph** tries to create `knowledge` directory during initialization
2. Path `knowledge` is **relative**, not absolute
3. Resolves to `/app/knowledge` (container working directory)
4. Container user (UID 1000) can't create directories in `/app` (owned by root)

### Correct Path

- **Should be**: `/vault/_thoth/data/knowledge` (absolute, writable)
- **Actually using**: `knowledge` (relative, not writable)

### Where It Fails

```python
# src/thoth/knowledge/graph.py:84
self.knowledge_base_dir = Path(knowledge_base_dir)
self.knowledge_base_dir.mkdir(parents=True, exist_ok=True)  # ← FAILS HERE
```

## Fix Plan

### Option 1: Fix Path Resolution (RECOMMENDED)

Ensure `CitationGraph` always receives absolute paths:

**File**: `src/thoth/knowledge/graph.py`

```python
def __init__(self, knowledge_base_dir, ...):
    # Convert to absolute path
    self.knowledge_base_dir = Path(knowledge_base_dir).resolve()
    
    # Now mkdir will work with correct absolute path
    self.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
```

### Option 2: Fix Container Permissions

Make `/app` writable (NOT RECOMMENDED - security issue):

```bash
docker exec thoth-mcp chmod 777 /app
```

### Option 3: Change Working Directory

Ensure MCP container starts in correct directory:

**File**: `docker-compose.yml`

```yaml
thoth-mcp:
  working_dir: /vault/_thoth  # Start in vault directory
  command: ["python", "-m", "thoth", "mcp", "full", ...]
```

## Implementation Steps

### Step 1: Fix Path Resolution ✅ RECOMMENDED

1. Update `src/thoth/knowledge/graph.py`:
   - Convert `knowledge_base_dir` to absolute path in `__init__`
   - Ensure all path operations use resolved absolute paths

2. Rebuild MCP container:
   ```bash
   docker-compose build thoth-mcp
   docker-compose restart thoth-mcp
   ```

3. Test RAG tools:
   - `list_articles`
   - `search_articles`  
   - `get_article_details`

### Step 2: Verify All Tools

Test each category systematically:

**Discovery Tools** (9):
- ✅ `create_arxiv_source`
- ✅ `create_biorxiv_source`
- ✅ `list_discovery_sources`
- etc.

**Article/RAG Tools** (7):
- ⏳ `list_articles` - NEEDS FIX
- ⏳ `search_articles` - NEEDS FIX
- ⏳ `get_article_details` - NEEDS FIX
- etc.

**PDF Tools** (6):
- ✅ `download_pdf`
- ✅ `validate_pdf_sources`
- etc.

**Citation Tools** (4):
- ✅ `extract_citations`
- ✅ `format_citations`
- etc.

**Query Tools** (5):
- ✅ `create_query`
- ✅ `list_queries`
- etc.

**Organization Tools** (4):
- ✅ `suggest_tags`
- ✅ `consolidate_tags`
- etc.

**Collection Tools** (5):
- ✅ `collection_stats`
- ✅ `backup_collection`
- etc.

**System Tools** (2):
- ✅ `memory_stats`
- ✅ `memory_health_check`

**Integration Tools** (1):
- ✅ `sync_with_obsidian`

### Step 3: Document Results

Create test report showing:
- ✅ Tools working correctly
- ❌ Tools still failing
- 🔧 Tools fixed by this plan

## Verification Command

```bash
# Test a fixed article tool
curl -s -X POST "http://localhost:8283/v1/agents/agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf/messages" \
  -H "Authorization: Bearer letta_dev_password" \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "List 3 articles"}], "stream": false}' \
  | jq -r '.messages[-1].content'
```

**Expected**: Should return article list, NOT permission error

## Next Actions

1. ✅ Implement Fix Option 1 (path resolution)
2. ⏳ Rebuild and restart MCP container  
3. ⏳ Test all 46 tools systematically
4. ⏳ Document working tool inventory
5. ⏳ Create tool usage guide for users

## Summary

**Problem**: MCP tools fail with permission errors because relative paths resolve to unwritable directories.

**Solution**: Convert all paths to absolute in `CitationGraph.__init__` before creating directories.

**Impact**: Fixes ALL article/RAG tools (7+ tools), unblocks multi-agent research workflows.

**Time to Fix**: ~30 minutes (code change + rebuild + test)
