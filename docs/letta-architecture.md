# Letta Agent Architecture

Complete guide to Letta's agent system in Thoth.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agent System](#agent-system)
- [Memory System](#memory-system)
- [Tool Integration](#tool-integration)
- [Service Management](#service-management)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)

---

## Overview

Letta provides Thoth's persistent agent system with:
- **Memory across sessions**: Agents remember past conversations
- **Tool execution**: Agents call MCP tools to perform actions
- **Multi-agent coordination**: Orchestrator delegates to specialist agents
- **PostgreSQL storage**: All data persists in database with pgvector

---

## Architecture

### Shared Service Design

Letta runs as **independent, shared infrastructure** that multiple projects can use:

#### Before (❌ Problem)
```
make dev → docker-compose.dev.yml
    ├── thoth-dev-letta (NEW, EMPTY database)
    ├── thoth-dev-letta-postgres (NEW, EMPTY database)
    └── Your agents were in the OLD standalone Letta

Result: Agents appeared to be gone!
```

#### After (✅ Solution)
```
Standalone Letta (docker-compose.letta.yml)
    ├── letta-server (persistent, shared)
    ├── letta-postgres (persistent, shared)
    ├── letta-redis (persistent, shared)
    └── letta-nginx (persistent, shared)

make dev → docker-compose.dev.yml
    ├── thoth-all-in-one
    │   └── Connects to standalone Letta via external network
    └── No Letta services (uses external)

Result: All agents preserved across restarts!
```

### Services

**Standalone Letta Stack** (`docker-compose.letta.yml`):

1. **letta-postgres** (port 5432)
   - PostgreSQL 15 with pgvector extension
   - Stores: agents, messages, memory blocks, conversations
   - Volume: `letta-postgres` (persistent)

2. **letta-server** (port 8283)
   - Main Letta API server
   - REST API + streaming SSE
   - Volumes: `letta-data`, `letta-home`

3. **letta-redis** (port 6379)
   - Job queuing and caching
   - Streaming message coordination

4. **letta-nginx** (port 8284)
   - SSE proxy with optimized timeouts
   - Connection pooling
   - Handles long-lived streams

**Thoth Services** (`docker-compose.dev.yml`):

- **thoth-all-in-one**: Connects to standalone Letta via `letta-network`
- **No Letta services**: Prevents duplicate instances

---

## Agent System

### Two-Agent Architecture

Thoth uses 2 specialized agents (optimized from initial 4-agent design):

#### 1. Research Orchestrator (`thoth_main_orchestrator`)

**Role**: User-facing coordinator

**Capabilities**:
- Skill loading (dynamic tool attachment)
- Quick search (`search_articles`)
- Task delegation to Analyst
- Multi-step workflow coordination

**Initial Tools** (4):
- `list_skills` - Discover available skills
- `load_skill` - Load skills dynamically
- `unload_skill` - Remove loaded skills
- `search_articles` - Quick collection search

**How It Works**:
```
User: "Find papers on transformers"

Orchestrator:
1. Calls list_skills to see "paper-discovery" skill
2. Loads skill: load_skill(skill_ids=["paper-discovery"])
3. Skill attaches ~10 discovery tools
4. Uses tools to search ArXiv, Semantic Scholar
5. Returns results to user
6. Can unload skill when done
```

**Memory Blocks** (6):
1. **persona**: Core identity and communication style
2. **human**: User preferences, research interests
3. **research_context**: Active projects, ongoing reviews
4. **loaded_skills**: Currently loaded skills tracker
5. **planning**: Multi-step task tracking
6. **scratchpad**: Temporary working memory

#### 2. Research Analyst (`thoth_research_analyst`)

**Role**: Deep analysis specialist

**Capabilities**:
- Literature reviews and synthesis
- Paper comparisons and evaluations
- Citation network exploration
- Research gap identification
- Comprehensive topic analysis

**Tools** (16):
- `answer_research_question` - Deep Q&A with citations
- `explore_citation_network` - Citation analysis
- `compare_articles` - Systematic paper comparison
- `extract_article_insights` - Key findings extraction
- `get_article_full_content` - Full paper access
- `find_related_papers` - Similarity search
- `analyze_topic` - Topic deep dive
- `generate_research_summary` - Literature review generation
- `evaluate_article` - Quality assessment
- `get_citation_context` - Citation context extraction
- `search_articles`, `search_by_topic`, `find_articles_by_authors` - Search
- `list_skills`, `load_skill` - Skill loading

**Memory Blocks** (4):
1. **persona**: Analysis specialist identity
2. **analysis_criteria**: Quality evaluation standards
3. **paper_summaries**: Recently analyzed papers
4. **planning**: Analysis task tracking
5. **scratchpad**: Analysis working memory

### Agent Initialization

**Automatic Startup**: Agents created/updated on Thoth start

**Process** (`AgentInitializationService`):
```python
1. Check if agent exists (by name lookup)
2. If missing:
   - Create new agent
   - Set system prompt
   - Attach tools
   - Create memory blocks
   - Attach filesystem folders
3. If exists:
   - Update tools (add/remove)
   - Update system prompt
   - Preserve memory blocks
   - Preserve conversation history
```

**Filesystem Attachment** (orchestrator only):
- Vault root: `{{OBSIDIAN_VAULT_PATH}}/thoth` → `/mnt/vault`
- Thoth data: `{{OBSIDIAN_VAULT_PATH}}/thoth/_thoth` → `/mnt/thoth`
- Skills: `src/thoth/.skills` → `/mnt/skills` (read-only)

---

## Memory System

### Memory Block Types

Letta uses **structured memory blocks** for context management:

| Block | Purpose | Limit | Writable |
|-------|---------|-------|----------|
| **persona** | Agent identity | 500 chars | Yes (self-update) |
| **human** | User info | 2000 chars | Yes (learn about user) |
| **research_context** | Active research | 3000 chars | Yes (track projects) |
| **loaded_skills** | Skill tracker | 1000 chars | Yes (skill loading) |
| **planning** | Task tracking | 2000 chars | Yes (clear when done) |
| **scratchpad** | Working memory | 2000 chars | Yes (temporary) |
| **analysis_criteria** | Standards | 1000 chars | Yes (update criteria) |
| **paper_summaries** | Recent papers | 3000 chars | Yes (analysis results) |

### Memory Operations

**Reading**:
- All memory blocks available in every message context
- Agent sees full block contents when responding

**Writing**:
- Agent calls `core_memory_append` to add text
- Agent calls `core_memory_replace` to update sections
- Changes persist across conversations

**Example**:
```
User: "I'm interested in computational efficiency"

Agent:
1. Reads "human" memory block
2. Calls core_memory_append(name="human", content="Primary interest: computational efficiency")
3. Memory updated for future conversations
```

### Conversation History

- **Stored**: All messages in PostgreSQL
- **Retrieved**: Last N messages loaded as context (configurable)
- **Searchable**: Letta's archival storage enables semantic search of past conversations

---

## Tool Integration

### MCP Connection

**How Agents Call Tools**:

1. **Tool Discovery**: Agent initialization attaches tools via Letta API
2. **Tool Call**: Agent decides to use tool and generates structured call
3. **MCP Routing**: Letta forwards call to Thoth MCP server (HTTP POST to `/mcp`)
4. **Execution**: MCP server routes to appropriate tool handler
5. **Result**: Tool result returned to Letta, injected into agent context
6. **Response**: Agent processes result and responds to user

**Connection**:
```
Agent → Letta Server (8283)
     → HTTP POST http://thoth-mcp:8000/mcp
     → MCP Server
     → Tool Execution
     → Result
```

### Skill-Based Tool Loading

**Dynamic Tool Attachment**:
```python
# Orchestrator starts with 4 tools
initial_tools = ["list_skills", "load_skill", "unload_skill", "search_articles"]

# User asks for paper discovery
User: "Find papers on transformers"

# Agent loads skill
Agent: load_skill(skill_ids=["paper-discovery"], agent_id="agent_xyz")

# Skill attaches its tools
skill_tools = [
    "list_available_sources",
    "create_research_question",
    "run_discovery_for_question",
    ...
]

# Agent now has 4 + 10 = 14 tools
```

**Benefits**:
- Reduces initial tool count (better performance)
- Tools loaded only when needed
- Skills provide guidance on tool usage
- Clean separation of capabilities

---

## Service Management

### Starting Letta

**Option 1: Automatic** (recommended):
```bash
make dev  # Checks and starts Letta automatically
```

**Option 2: Manual**:
```bash
# Start Letta standalone
make letta-start
# or
docker compose -f docker-compose.letta.yml up -d

# Then start Thoth
make dev
```

### Checking Status

```bash
# Letta containers
docker ps | grep letta

# Letta API health
curl http://localhost:8283/v1/health

# List agents
curl http://localhost:8283/v1/agents

# Check agent memory
curl http://localhost:8283/v1/agents/{agent_id}/memory

# Database query
docker exec letta-postgres psql -U letta -d letta \
  -c "SELECT id, name FROM agents;"
```

### Managing Letta

```bash
# Start
make letta-start

# Stop (WARNING: affects all projects)
make letta-stop

# Restart (WARNING: affects all projects)
make letta-restart

# Status
make letta-status

# Logs
make letta-logs
make letta-logs -f  # Follow mode
```

### Pre-flight Checks

**Script**: `scripts/check-letta.sh`

Runs before `make dev` and `make microservices`:
- ✅ Checks if Letta is running
- ✅ Offers to start if not running
- ✅ Verifies API accessibility
- ✅ Prevents duplicate instances

---

## Usage

### Via Obsidian Plugin

**Primary method**:
```
1. Open Obsidian
2. Click Thoth icon in sidebar
3. Chat with orchestrator
4. Orchestrator loads skills and delegates to analyst as needed
```

### Via Letta API

**Direct agent interaction**:
```bash
# List agents
curl http://localhost:8283/v1/agents

# Send message
curl -X POST http://localhost:8283/v1/agents/{agent_id}/messages \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "text": "Find papers on transformers"}
    ]
  }'

# Get memory
curl http://localhost:8283/v1/agents/{agent_id}/memory

# Update memory
curl -X POST http://localhost:8283/v1/agents/{agent_id}/memory \
  -H "Content-Type: application/json" \
  -d '{
    "block_label": "human",
    "operation": "append",
    "content": "User prefers Python examples"
  }'
```

### Common Workflows

**Discovery**:
```
User: "Find recent papers on deep learning"

Orchestrator:
1. Lists skills, identifies "paper-discovery"
2. Loads skill: load_skill(skill_ids=["paper-discovery"])
3. Uses discovery tools to search ArXiv, Semantic Scholar
4. Returns ranked results
5. Unloads skill when done
```

**Deep Analysis**:
```
User: "Analyze and compare these two papers"

Orchestrator:
1. Recognizes complex analysis task
2. Delegates to thoth_research_analyst
3. Analyst uses analysis tools systematically
4. Returns comprehensive comparison
5. Orchestrator summarizes for user
```

**Project Coordination**:
```
User: "I'm starting a literature review on transformers"

Orchestrator:
1. Updates research_context memory
2. Loads "deep-research" skill
3. Suggests workflow: discovery → analysis → synthesis
4. Tracks progress in planning memory
5. Coordinates multiple sessions
```

---

## Troubleshooting

### Agents Not Found

**Problem**: `GET /v1/agents` returns empty list

**Solution**:
```bash
# Check which Letta is running
docker ps | grep letta

# If thoth-dev-letta is running, stop it
docker stop thoth-dev-letta thoth-dev-letta-postgres
docker rm thoth-dev-letta thoth-dev-letta-postgres

# Start standalone Letta
make letta-start

# Restart Thoth to re-initialize agents
make dev-thoth-restart
```

### Connection Refused

**Problem**: `Connection refused to http://localhost:8283`

**Solution**:
```bash
# Check Letta is running
docker ps | grep letta-server

# Check health
docker inspect letta-server | jq '.[0].State.Health.Status'

# View logs
docker logs letta-server --tail 50

# Restart if unhealthy
make letta-restart
```

### Tools Not Working

**Problem**: Agent says "I don't have that tool"

**Solution**:
```bash
# Check agent tools
curl http://localhost:8283/v1/agents/{agent_id}/tools

# Check MCP server is running
curl http://localhost:8082/health

# Restart Thoth to re-attach tools
make dev-thoth-restart
```

### Memory Not Persisting

**Problem**: Agent forgets between sessions

**Solution**:
```bash
# Check database volume
docker volume inspect letta-postgres

# Check memory blocks exist
curl http://localhost:8283/v1/agents/{agent_id}/memory

# If volume is missing, data was lost
# Need to recreate agents (will lose conversation history)
docker compose -f docker-compose.letta.yml down -v
make letta-start
make dev-thoth-restart
```

### Port Conflicts

**Problem**: Port 5432 already in use

**Solution**:
```bash
# Check what's using port
sudo lsof -i :5432

# If system PostgreSQL, stop it
sudo systemctl stop postgresql

# Or edit docker-compose.letta.yml to use different port:
# ports:
#   - "5433:5432"  # Expose on 5433 instead
```

---

## Data Persistence

### Docker Volumes

All agent data persists in volumes:

- **letta-postgres**: PostgreSQL database (agents, messages, memory)
- **letta-data**: Letta persistent data
- **letta-home**: Letta home directory
- **letta-redis-data**: Redis cache

**These volumes survive container restarts/removals.**

### Backup

**Export agents**:
```bash
# Backup database
docker exec letta-postgres pg_dump -U letta -d letta > letta-backup.sql

# Restore database
cat letta-backup.sql | docker exec -i letta-postgres psql -U letta -d letta
```

**Export agent memory**:
```bash
# Save agent configuration
curl http://localhost:8283/v1/agents/{agent_id} > agent-backup.json

# Save memory blocks
curl http://localhost:8283/v1/agents/{agent_id}/memory > memory-backup.json
```

---

## Network Connectivity

### Docker Networks

- **letta-network** (172.22.0.0/16): Standalone Letta services
- **thoth-dev-network**: Thoth services
- **Bridge**: `thoth-all-in-one` joins `letta-network` via `external_links`

### DNS Resolution

Inside Thoth containers:
- `letta-server` → Letta API (port 8283)
- `letta-postgres` → PostgreSQL (port 5432)
- `letta-redis` → Redis (port 6379)

### Environment Variables

```bash
# Thoth → Letta connection
THOTH_LETTA_URL=http://letta-server:8283

# Letta → PostgreSQL
LETTA_PG_URI=postgresql://letta:password@letta-postgres:5432/letta

# Letta → Redis
LETTA_REDIS_URL=redis://letta-redis:6379/0
```

---

## Advanced

### Multi-Project Sharing

Letta can serve multiple projects:

```
letta-server (shared)
    ├── Project A agents
    ├── Project B agents
    └── Project C agents
```

**Isolation**: Agents are isolated by project (different names, no cross-talk)

**Benefit**: One Letta instance, multiple research projects

### Custom Agents

Create additional agents beyond the default 2:

```python
# Add to AgentInitializationService.AGENT_CONFIGS
'my_custom_agent': {
    'name': 'my_custom_agent',
    'description': 'Custom agent purpose...',
    'tools': ['tool1', 'tool2'],
    'memory_blocks': [...]
}
```

### Agent Communication

Agents can message each other:

```python
# Orchestrator → Analyst delegation (via Letta API)
response = await letta_client.send_agent_message(
    agent_id=analyst_agent_id,
    message="Analyze paper XYZ",
    from_agent=orchestrator_agent_id
)
```

---

## Summary

**Benefits**:
- ✅ Agents persist across restarts
- ✅ Memory survives code changes
- ✅ Multi-agent coordination
- ✅ Skill-based dynamic tool loading
- ✅ Letta shared across projects

**Trade-offs**:
- Letta must be started separately (but automated)
- Stopping Letta affects all projects
- Slightly more complex setup

**Architecture Decision**: Shared Letta was the right choice—it prevents data loss and enables multi-project workflows.

---

**Last Updated**: February 2026
