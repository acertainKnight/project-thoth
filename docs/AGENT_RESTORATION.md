# Letta Agent Restoration - Complete Guide

## What Gets Restored ✅

### Core Agent Data (Fully Automated)

Our `scripts/restore-agents-complete.py` automatically restores:

#### 1. Memory Blocks
- **All custom memory blocks** with full content
- Lead Engineer: 24 blocks (11KB+ of project documentation per block)
  - Components: obsidian-plugin, citation-system, discovery-system, RAG, etc.
  - Project docs: current-work, architecture, conventions, code-deep-dive
  - Persona and human context
- Thoth agents: 6-7 blocks each
  - research_context, active_papers, citation_network, research_findings

#### 2. Server-Side Tools
- Tools registered on Letta server (web_search, fetch_webpage, send_message, etc.)
- Automatically filtered to match server availability
- Lead Engineer: 6 tools
- Thoth agents: 4-9 tools each

#### 3. Tool Rules
- Tool execution policies and restrictions
- Lead Engineer: 18 rules defining when tools can be used
- Preserves agent behavior and safety constraints

#### 4. Tags
- Agent categorization tags
- Example: "origin:letta-code"
- Used for filtering and organizing agents

#### 5. System Prompts
- Complete agent personality and instructions
- Lead Engineer: 14KB system prompt
- Thoth agents: 206-3092 characters
- Defines agent behavior and capabilities

#### 6. Configuration
- `llm_config`: Model endpoints, provider settings
- `embedding_config`: Embedding model configuration
- `model_settings`: Temperature, max tokens, reasoning mode

## What Doesn't Get Restored (By Design)

### Client-Side Tools (No Restoration Needed)

These tools are provided by Letta Code at runtime, not stored in the database:

**File Operations:**
- Edit, Write, Read, MultiEdit, Glob, Grep

**Shell Operations:**
- Bash, BashOutput, KillBash

**Agent Operations:**
- Task (spawn sub-agents)
- TodoWrite (task management)

**Interactive:**
- AskUserQuestion, EnterPlanMode, ExitPlanMode, Skill

**Why:** These tools exist only during Letta Code client sessions. When you connect with Letta Code, these tools are automatically injected into the agent's available toolset. They don't need to be stored on the server.

### Conversation History (Can Be Restored, But Requires Extra Work)

**What's Lost:**
- Message history (536 messages in Lead Engineer backup)
- Conversation state and context
- User/agent interaction logs

**Why Not Automatic:**
1. **Size**: Conversation history can be massive (500+ messages)
2. **API Limitation**: Backup contains only message IDs, not full message content
3. **Database Recreation**: Messages were deleted when database was recreated
4. **Separate Storage**: Messages live in different tables than agent config

**Impact:** Minimal - agents function perfectly without message history. They retain all their knowledge through memory blocks.

## How to Restore Conversation History (If Needed)

Conversation history **can** be restored, but requires additional steps:

### Option 1: Use Letta's Agent File Export (Recommended)

```bash
# BEFORE dropping database, export agents with Letta's native format
curl -o agent-backup.json "http://localhost:8283/v1/agents/{agent_id}/export"

# After migration, import using Letta's import API
curl -X POST "http://localhost:8283/v1/agents/import" \
  -F "file=@agent-backup.json"
```

**Pros:** Uses official Letta API, includes all agent data
**Cons:** Must be done BEFORE dropping database

### Option 2: Manual Message Recreation

If you need conversation history after database recreation:

1. **During backup**, export full message data:
```python
# Add to backup script
messages = []
for msg_id in agent['message_ids']:
    msg_resp = requests.get(f"{LETTA_URL}/v1/messages/{msg_id}")
    if msg_resp.status_code == 200:
        messages.append(msg_resp.json())

# Save messages separately
with open(f"{BACKUP_DIR}/{agent_id}-messages.json", 'w') as f:
    json.dump(messages, f)
```

2. **During restoration**, recreate messages via API:
```python
# Not currently implemented - would need message creation API
# This is why conversation history is marked as "not restored"
```

**Challenge:** Letta's message API is designed for real-time agent interaction, not bulk message recreation. Would need to:
- Preserve message ordering
- Maintain conversation threading
- Handle message types (user, assistant, system, function calls)
- Restore message metadata (timestamps, sender info)

### Option 3: PostgreSQL Database Dump (Most Complete)

For absolute full restoration including everything:

```bash
# BEFORE migration - backup entire PostgreSQL database
docker exec letta-postgres pg_dump -U letta -d letta > letta-full-backup.sql

# AFTER migration - restore full database
docker exec -i letta-postgres psql -U letta -d letta < letta-full-backup.sql
```

**Pros:** Preserves EVERYTHING including internal state
**Cons:**
- Can't upgrade Letta versions (keeps old schema)
- All-or-nothing approach
- Large backup files

## Automated Restoration Usage

### Restore All Agents

```bash
python3 scripts/restore-agents-complete.py ~/letta-backup-20260117 http://localhost:8283
```

### Restore Specific Agents

```bash
python3 scripts/restore-agents-complete.py ~/letta-backup-20260117 http://localhost:8283 \
  "Lead Engineer" \
  "thoth_main_orchestrator" \
  "system_discovery_scout"
```

### Output Example

```
✓ Lead Engineer
  ID: agent-d2f981c2-352c-4214-b48a-ed3051f0a8cf
  Memory blocks: 24/24
  Tools: 6/4
  Tool rules: 18/14
  Tags: 1/1
  System prompt: 14116 chars
```

## Verification Commands

### Check Agent Memory Blocks

```bash
curl -s http://localhost:8283/v1/agents/{agent_id} | jq '{
  name: .name,
  memory_blocks: (.memory.blocks | length),
  sample_blocks: [.memory.blocks[0:3][] | {label: .label, size: (.value | length)}]
}'
```

### Check Tools and Rules

```bash
curl -s http://localhost:8283/v1/agents/{agent_id} | jq '{
  tools: [.tools[].name],
  tool_rules: (.tool_rules | length),
  tags: .tags
}'
```

### Check Current Messages

```bash
curl -s "http://localhost:8283/v1/agents/{agent_id}/messages?limit=10" | jq length
```

## Migration Workflow

The automated migration script (`scripts/letta-migrate.sh`) includes complete restoration:

1. **Backup** - Export all agents to `~/letta-backup-YYYYMMDD-HHMMSS/`
2. **Version Update** - Update Docker image version
3. **Database Recreation** - Drop and recreate with fresh schema
4. **Extensions** - Install pgvector
5. **Start Server** - Launch Letta with new version
6. **Compatibility Fixes** - Apply schema patches
7. **Agent Restoration** - Restore with complete data using restore-agents-complete.py
8. **Verification** - Confirm restoration success

## Key Insights

1. **Memory blocks are the most critical** - They contain all knowledge and context
2. **Client-side tools are ephemeral** - No storage needed, injected at runtime
3. **Server-side tools are persistent** - Must be restored from backup
4. **Tool rules define behavior** - Important for maintaining agent policies
5. **Conversation history is optional** - Agents work fully without it
6. **Message restoration is possible** - But requires extra implementation work

## Future Enhancements

Could be implemented if conversation history becomes critical:

1. **Message export** during backup phase
2. **Message recreation API** wrapper for bulk import
3. **Conversation threading** preservation
4. **Timestamp and metadata** restoration
5. **Integration with Letta export API** for full agent files

For now, the current restoration preserves all essential agent functionality and knowledge while keeping the migration process simple and reliable.

## References

- [Letta Agent Export API](https://docs.letta.com/api-reference/agents/import-file)
- [Letta Message API](https://docs.letta.com/guides/agents/messages/)
- [Letta Agent Files (.af format)](https://github.com/letta-ai/agent-file)
