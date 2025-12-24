# Letta Multi-Agent Communication Tools - Research Findings

**Research Date**: 2025-12-24
**Letta Version**: v0.16.1 (self-hosted)
**Status**: ✅ CRITICAL FINDINGS - Tools exist but require explicit enablement

---

## Executive Summary

The multi-agent communication tools (`send_message_to_agent_async`, `send_message_to_agent_and_wait_for_reply`, `send_message_to_agents_matching_tags`) **ARE available** in self-hosted Letta v0.16.1, but they are **NOT automatically enabled** for agents. They must be explicitly attached during agent creation.

### Key Discovery

**The tools exist in the codebase** at `/app/letta/functions/function_sets/multi_agent.py` but are **not included in base tools**. They are a separate tool category (`LETTA_MULTI_AGENT_CORE`) that must be explicitly enabled via the `include_multi_agent_tools` parameter.

---

## Architecture Analysis

### Tool Categories in Letta

Letta organizes tools into distinct categories (from `/letta/constants.py`):

```python
# Tool Module Constants
LETTA_CORE_TOOL_MODULE_NAME = "letta.functions.function_sets.base"
LETTA_MULTI_AGENT_TOOL_MODULE_NAME = "letta.functions.function_sets.multi_agent"
LETTA_VOICE_TOOL_MODULE_NAME = "letta.functions.function_sets.voice"
LETTA_BUILTIN_TOOL_MODULE_NAME = "letta.functions.function_sets.builtin"
LETTA_FILES_TOOL_MODULE_NAME = "letta.functions.function_sets.files"

# Multi-Agent Tool Names
MULTI_AGENT_TOOLS = [
    "send_message_to_agent_and_wait_for_reply",
    "send_message_to_agents_matching_tags",
    "send_message_to_agent_async"
]

# Local-Only Tools (not available on Letta Cloud)
LOCAL_ONLY_MULTI_AGENT_TOOLS = ["send_message_to_agent_async"]
```

### Tool Type Execution Model

From `/letta/agent.py` analysis:

1. **LETTA_CORE Tools**: Base tools with agent state access (memory, search)
2. **LETTA_MULTI_AGENT_CORE Tools**: Inter-agent communication tools
3. **External Tools**: Composio, MCP servers
4. **Sandbox Tools**: Custom user tools in isolated environments

**Multi-agent tools are loaded via**: `get_function_from_module(LETTA_MULTI_AGENT_TOOL_MODULE_NAME, function_name)`

---

## Available Multi-Agent Tools

### 1. `send_message_to_agent_and_wait_for_reply`

**Type**: Synchronous
**Description**: Sends a message to a specific agent and waits for response
**Use Case**: Request-response pattern, when sender needs confirmation

```python
# Function signature (from multi_agent.py)
def send_message_to_agent_and_wait_for_reply(
    self: "Agent",
    agent_id: str,
    message: str
) -> str:
    """
    Sends a message to a specific agent and waits for a response.

    Args:
        agent_id: The ID of the target agent
        message: The message content to send

    Returns:
        The response from the target agent
    """
```

### 2. `send_message_to_agent_async`

**Type**: Asynchronous (fire-and-forget)
**Description**: Sends a message without waiting for response
**Use Case**: Notifications, broadcasts, non-blocking communication
**Limitation**: **Local/self-hosted only** (not available on Letta Cloud)

```python
def send_message_to_agent_async(
    self: "Agent",
    agent_id: str,
    message: str
) -> str:
    """
    Fire-and-forget message to another agent.
    Returns confirmation without waiting for response.
    """
```

### 3. `send_message_to_agents_matching_tags`

**Type**: Multi-target broadcast
**Description**: Sends message to all agents matching specified tags
**Use Case**: Supervisor-worker pattern, group coordination

```python
def send_message_to_agents_matching_tags(
    self: "Agent",
    message: str,
    match_all: List[str],
    match_some: Optional[List[str]] = None
) -> List[Dict]:
    """
    Broadcast message to agents matching tag criteria.

    Args:
        message: Message to send
        match_all: Tags that must all be present
        match_some: Tags where at least one must be present

    Returns:
        List of responses from all matching agents
    """
```

---

## How to Enable Multi-Agent Tools

### Method 1: Python SDK (Recommended)

```python
from letta import Letta

# Initialize client (self-hosted)
client = Letta(base_url="http://localhost:8283")

# Create agent with multi-agent tools enabled
agent = client.agents.create(
    name="supervisor-agent",
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-3-small",

    # Enable multi-agent communication tools
    include_multi_agent_tools=True,

    # Optional: Also include base tools (memory, search)
    include_base_tools=True,

    # Memory blocks
    memory_blocks=[
        {"label": "persona", "value": "I am a supervisor agent coordinating tasks."}
    ],

    # Optional: Add tags for discovery
    tags=["supervisor"]
)

# Create worker agent
worker = client.agents.create(
    name="worker-agent",
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-3-small",
    include_multi_agent_tools=True,
    memory_blocks=[
        {"label": "persona", "value": "I am a worker agent."}
    ],
    tags=["worker"]
)

# Send message from supervisor to worker
response = client.agents.send_message(
    agent_id=agent.id,
    role="user",
    message=f"Please send a task to worker agent {worker.id}"
)
```

### Method 2: REST API

```bash
# Create agent with multi-agent tools
curl -X POST http://localhost:8283/v1/agents \
  -H "Content-Type: application/json" \
  -d '{
    "name": "multi-agent-enabled",
    "model": "openai/gpt-4o-mini",
    "embedding": "openai/text-embedding-3-small",
    "include_multi_agent_tools": true,
    "include_base_tools": true,
    "memory_blocks": [
      {
        "label": "persona",
        "value": "I can communicate with other agents."
      }
    ]
  }'
```

### Method 3: Manually Attach Tool IDs

```python
# First, list available tools to find multi-agent tool IDs
tools = client.tools.list(
    name="send_message_to_agent_async"
)

# Get tool IDs
multi_agent_tool_ids = [tool.id for tool in tools]

# Create agent with specific tool IDs
agent = client.agents.create(
    name="agent-with-tools",
    tool_ids=multi_agent_tool_ids,  # Explicitly attach tools
    include_base_tools=True
)
```

---

## Why Tools Weren't Appearing

### Root Cause Analysis

1. **Separate Tool Category**: Multi-agent tools are in `LETTA_MULTI_AGENT_CORE`, not `LETTA_CORE`
2. **Not in Base Tools**: `include_base_tools=True` only adds memory/search tools
3. **Requires Explicit Flag**: Must use `include_multi_agent_tools=True`
4. **No Environment Variable**: No `.env` flag to auto-enable for all agents

### Design Rationale

From documentation analysis:
- Prevents tool pollution for single-agent use cases
- Allows fine-grained control over agent capabilities
- Security consideration: inter-agent communication is privileged
- Local-only constraint for `send_message_to_agent_async` on self-hosted

---

## Docker Configuration (No Changes Needed)

### Current Setup Analysis

From `/compose.yaml`:
- ✅ PostgreSQL with pgvector support
- ✅ Letta server with all necessary environment variables
- ✅ No special flags needed for multi-agent tools

**The multi-agent tools are compiled into the Letta server image** and available via the module system. No Docker configuration changes are required.

### Environment Variables

From `.env.example` analysis:
- **No multi-agent-specific variables** exist
- Tools are controlled at **agent creation time**, not server startup
- Only LLM API keys needed (OpenAI, Anthropic, Ollama, etc.)

---

## Complete Working Example

```python
#!/usr/bin/env python3
"""
Complete example: Multi-agent communication in Letta v0.16.1
"""

from letta import Letta
import time

# Connect to self-hosted Letta
client = Letta(base_url="http://localhost:8283")

# Step 1: Create supervisor agent with multi-agent tools
supervisor = client.agents.create(
    name="supervisor",
    model="openai/gpt-4o-mini",
    embedding="openai/text-embedding-3-small",
    include_multi_agent_tools=True,  # KEY: Enable multi-agent tools
    include_base_tools=True,
    memory_blocks=[
        {
            "label": "persona",
            "value": "I am a supervisor. I coordinate tasks between workers."
        }
    ],
    tags=["supervisor"]
)

print(f"✅ Created supervisor agent: {supervisor.id}")

# Step 2: Create worker agents
workers = []
for i in range(3):
    worker = client.agents.create(
        name=f"worker-{i}",
        model="openai/gpt-4o-mini",
        embedding="openai/text-embedding-3-small",
        include_multi_agent_tools=True,  # KEY: Enable for workers too
        include_base_tools=True,
        memory_blocks=[
            {
                "label": "persona",
                "value": f"I am worker {i}. I execute tasks assigned to me."
            }
        ],
        tags=["worker"]
    )
    workers.append(worker)
    print(f"✅ Created worker agent: {worker.id}")

# Step 3: Verify tools are attached
agent_info = client.agents.get(agent_id=supervisor.id)
tool_names = [tool.name for tool in agent_info.tools]
print(f"\n📋 Supervisor tools: {tool_names}")

# Check for multi-agent tools
has_async = "send_message_to_agent_async" in tool_names
has_sync = "send_message_to_agent_and_wait_for_reply" in tool_names
has_broadcast = "send_message_to_agents_matching_tags" in tool_names

print(f"\n✅ Multi-agent tools available:")
print(f"  - Async messaging: {has_async}")
print(f"  - Sync messaging: {has_sync}")
print(f"  - Broadcast messaging: {has_broadcast}")

# Step 4: Send task from supervisor to specific worker
print(f"\n📤 Sending task to worker-0...")
response = client.agents.send_message(
    agent_id=supervisor.id,
    role="user",
    message=f"Please use send_message_to_agent_and_wait_for_reply to send "
            f"a task to worker agent {workers[0].id}: 'Process dataset A'"
)

print(f"📥 Response: {response.messages[-1].text}")

# Step 5: Broadcast to all workers using tags
print(f"\n📡 Broadcasting to all workers...")
response = client.agents.send_message(
    agent_id=supervisor.id,
    role="user",
    message="Please use send_message_to_agents_matching_tags to broadcast "
            "to all agents with tag 'worker': 'Status check - report your current task'"
)

print(f"📥 Response: {response.messages[-1].text}")

# Step 6: Async notification (fire-and-forget)
print(f"\n🚀 Sending async notification...")
response = client.agents.send_message(
    agent_id=supervisor.id,
    role="user",
    message=f"Please use send_message_to_agent_async to notify worker "
            f"{workers[1].id}: 'Prepare for incoming task'"
)

print(f"📥 Response: {response.messages[-1].text}")

print("\n✅ Multi-agent communication test complete!")
```

---

## Troubleshooting

### Issue 1: Tools Not Showing in Agent

**Symptom**: `send_message_to_agent_*` tools not in agent.tools list

**Solution**:
```python
# Recreate agent with explicit flag
agent = client.agents.create(
    include_multi_agent_tools=True,  # Add this!
    # ... other parameters
)
```

### Issue 2: "Tool not found" Error During Execution

**Symptom**: Agent tries to use tool but gets error

**Diagnosis**:
```python
# Check what tools are actually attached
agent = client.agents.get(agent_id="agent-id")
print([tool.name for tool in agent.tools])
```

**Solution**: Delete and recreate agent with `include_multi_agent_tools=True`

### Issue 3: "Agent not found" When Sending Message

**Symptom**: Target agent ID is not valid

**Solution**:
```python
# List all agents to verify IDs
agents = client.agents.list()
for agent in agents:
    print(f"{agent.name}: {agent.id}")
```

### Issue 4: Async Tool Not Available

**Symptom**: `send_message_to_agent_async` returns error

**Cause**: This tool is **local-only**, not available on Letta Cloud

**Verification**: Check if using self-hosted instance (should work in Docker)

---

## Tool Comparison Matrix

| Feature | `send_message_to_agent_and_wait_for_reply` | `send_message_to_agent_async` | `send_message_to_agents_matching_tags` |
|---------|-------------------------------------------|------------------------------|---------------------------------------|
| **Pattern** | Synchronous request-response | Fire-and-forget | Broadcast |
| **Waits for reply** | ✅ Yes | ❌ No | ✅ Yes (collects all) |
| **Return value** | Single response string | Confirmation only | List of responses |
| **Use case** | Task delegation, Q&A | Notifications, triggers | Supervisor-worker pattern |
| **Performance** | Slower (waits) | Fastest | Slower (multiple agents) |
| **Cloud availability** | ✅ Yes | ❌ Local only | ✅ Yes |
| **Target count** | 1 agent | 1 agent | Multiple agents |

---

## Best Practices

### 1. Choose the Right Tool

```python
# ✅ Use sync for request-response
"Send task to agent X and wait for confirmation"

# ✅ Use async for notifications
"Notify agent X about event (no response needed)"

# ✅ Use broadcast for coordination
"Ask all workers to report their status"
```

### 2. Tag Agents for Discovery

```python
agent = client.agents.create(
    tags=["worker", "data-processor", "team-alpha"]
)

# Later: broadcast to team-alpha
"Use send_message_to_agents_matching_tags with match_all=['team-alpha']"
```

### 3. Include Context in Messages

```python
# ❌ Bad: No context
"Process the data"

# ✅ Good: Full context
"Process dataset 'sales_2024.csv' using ETL pipeline v2, store results in database 'analytics'"
```

### 4. Handle Multiple Responses

```python
# When using broadcast, agent receives list of responses
# Parse and validate each response
responses = agent_tool_result  # List of dicts
for resp in responses:
    agent_id = resp['agent_id']
    message = resp['message']
    # Process each response
```

---

## API Reference

### Python SDK

```python
from letta import Letta

# Client initialization
client = Letta(base_url="http://localhost:8283")

# Agent creation with multi-agent tools
agent = client.agents.create(
    name: str,
    model: str,
    embedding: str,
    include_multi_agent_tools: bool = False,  # Enable multi-agent tools
    include_base_tools: bool = True,          # Include memory/search tools
    tool_ids: List[str] = None,               # Or explicitly list tool IDs
    tags: List[str] = None,                   # Tags for discovery
    memory_blocks: List[Dict] = None
)

# List tools
tools = client.tools.list(
    name: str = None,              # Filter by name
    search: str = None,            # Search query
    returnOnlyLettaTools: bool = False
)

# Get agent info (including attached tools)
agent = client.agents.get(agent_id: str)
# Access tools: agent.tools (list of Tool objects)
```

### REST API Endpoints

```bash
# Create agent with multi-agent tools
POST /v1/agents
{
  "include_multi_agent_tools": true,
  "include_base_tools": true,
  ...
}

# List available tools
GET /v1/tools?search=send_message

# Get agent details (includes tools)
GET /v1/agents/{agent_id}

# Send message to agent
POST /v1/agents/{agent_id}/messages
{
  "role": "user",
  "message": "..."
}
```

---

## References

### Documentation
- [Multi-agent systems | Letta Docs](https://docs.letta.com/guides/agents/multi-agent/)
- [Connecting agents to each other | Letta Tutorial](https://docs.letta.com/tutorials/multi-agent-async/)
- [Building Custom Multi-Agent Tools | Letta](https://docs.letta.com/guides/agents/multi-agent-custom-tools)
- [Agent Creation API | Letta Docs](https://docs.letta.com/api/resources/agents/methods/create/)
- [Connecting Agents to Tools | Letta](https://docs.letta.com/guides/agents/tools)
- [Self-hosting Letta | Letta Docs](https://docs.letta.com/guides/selfhosting/)
- [Letta Python SDK | Letta Docs](https://docs.letta.com/api/python)

### GitHub Repository
- [letta-ai/letta](https://github.com/letta-ai/letta)
- [letta/agent.py](https://github.com/letta-ai/letta/blob/main/letta/agent.py)
- [letta/functions/function_sets/multi_agent.py](https://github.com/letta-ai/letta/blob/main/letta/functions/function_sets/multi_agent.py)
- [letta/constants.py](https://github.com/letta-ai/letta/blob/main/letta/constants.py)
- [letta-ai/letta-python SDK](https://github.com/letta-ai/letta-python)

### Issues & Discussions
- [Adding Tools to Agent Returns errors #1900](https://github.com/letta-ai/letta/issues/1900)
- [MemGPT Q2 2024 Developer Roadmap #1200](https://github.com/letta-ai/letta/issues/1200)

---

## Summary

### ✅ What We Learned

1. **Multi-agent tools exist** in self-hosted Letta v0.16.1
2. **They are NOT enabled by default** - must use `include_multi_agent_tools=True`
3. **Three tools available**: async, sync, and broadcast variants
4. **No Docker/environment changes needed** - configuration is per-agent
5. **Tools are categorized separately** from base tools (different module)

### 🔑 Critical Step

**Always create agents with**:
```python
include_multi_agent_tools=True
```

This is the **ONLY** way to enable inter-agent communication.

### 📊 Verification Command

```python
# After creating agent, verify tools are attached
agent = client.agents.get(agent_id="your-agent-id")
tool_names = [tool.name for tool in agent.tools]
assert "send_message_to_agent_async" in tool_names
```

---

**Research completed**: 2025-12-24
**Status**: Ready for implementation ✅
