# Native Letta Agent-to-Agent Communication

**Status**: ✅ Enabled and Operational
**Date**: 2025-12-24

## Overview

All 4 research agents now have native Letta agent-to-agent communication enabled using the built-in `send_message_to_agent_async` tool.

## Implementation

### Tools Enabled

- **send_message_to_agent_async** (tool-640603e9-1be0-4ddb-abbf-ff58bd08b047)
  - Fire-and-forget messaging
  - Sender identity automatically included
  - No response expected

Also available but not attached (per Letta recommendation):
- **send_message_to_agent_and_wait_for_reply** - Synchronous messaging
- **send_message_to_agents_matching_tags** - Broadcast to multiple agents

## Agents with Communication

✅ thoth_main_orchestrator (25 tools)
✅ system_citation_analyzer (18 tools)
✅ system_discovery_scout (24 tools)
✅ system_analysis_expert (24 tools)

## Usage

### From Within Agent

```python
# Agent can call this tool directly
send_message_to_agent_async(
    message="Find papers on quantum computing",
    other_agent_id="agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64"  # scout
)
```

### Message Format

Messages automatically include sender information:
```
[Incoming message from agent with ID 'agent-10418b8d...' - to reply to this message,
make sure to use the 'send_message_to_agent_async' tool, or the agent will not
receive your message]

Find papers on quantum computing
```

## Setup Process (For Reference)

The setup process that was completed:

1. **Create test agent** with `include_multi_agent_tools=True`
   - This triggers Letta to create the multi-agent tools in the database
   - Tools are created but attached only to that specific agent

2. **Extract tool IDs** from test agent
   - `send_message_to_agent_async`: tool-640603e9-1be0-4ddb-abbf-ff58bd08b047
   - `send_message_to_agent_and_wait_for_reply`: tool-85848c67-6187-456b-b5e5-71a8f0cbcb41
   - `send_message_to_agents_matching_tags`: tool-526ffa7b-5938-4eb2-a705-472d09eb390f

3. **Attach to existing agents** via PATCH /v1/agents/{id}
   - Added `send_message_to_agent_async` to all 4 research agents
   - Used async version only per Letta's recommendation

4. **Cleanup** - Delete test agent

## Tool IDs Reference

Stored in: `scripts/multi_agent_tool_ids.json`

```json
{
  "send_message_to_agent_and_wait_for_reply": "tool-85848c67-6187-456b-b5e5-71a8f0cbcb41",
  "send_message_to_agent_async": "tool-640603e9-1be0-4ddb-abbf-ff58bd08b047",
  "send_message_to_agents_matching_tags": "tool-526ffa7b-5938-4eb2-a705-472d09eb390f"
}
```

## Workflow Examples

### Example 1: Orchestrator Delegates to Scout

```python
# Orchestrator (agent-10418b8d...) sends task to Scout
send_message_to_agent_async(
    message="Search arXiv for papers on 'large language models reasoning' from 2024",
    other_agent_id="agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64"
)

# Scout receives message with sender info, processes, and can reply
send_message_to_agent_async(
    message="Found 15 relevant papers. Results stored in active_papers memory block.",
    other_agent_id="agent-10418b8d-37a5-4923-8f70-69ccc58d66ff"
)
```

### Example 2: Parallel Task Distribution

```python
# Orchestrator sends to multiple agents simultaneously
send_message_to_agent_async(
    message="Analyze citation network for papers in active_papers",
    other_agent_id="agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5"  # analyzer
)

send_message_to_agent_async(
    message="Synthesize key findings from analyzed papers",
    other_agent_id="agent-8a4183a6-fffc-4082-b40b-aab29727a3ab"  # expert
)
```

## Advantages Over Message Queue

✅ **Native integration** - Built into Letta, no custom code
✅ **Event-driven** - No polling required
✅ **Automatic sender identification** - Sender info included
✅ **Production-tested** - Used in official Letta tests
✅ **Simpler** - No manual message parsing

## When to Use Message Queue Instead

The shared memory message queue is still useful for:
- Task tracking and history
- Dependency management
- Status monitoring
- Batch processing
- Complex workflows with multiple steps

## Best Practice: Hybrid Approach

Use **both** systems together:
- **Native tools** for real-time agent-to-agent messaging
- **Shared memory** for state coordination and workflow tracking

Example:
```python
# 1. Post task to message queue (for tracking)
post_message(
    sender="orchestrator",
    receiver="scout",
    task="Find papers on quantum computing",
    metadata={"task_id": "task-123"}
)

# 2. Send via native tool (for execution)
send_message_to_agent_async(
    message="Task ID: task-123\nFind papers on quantum computing. Update message queue when complete.",
    other_agent_id="scout-agent-id"
)

# 3. Scout completes and updates queue
mark_message_complete("orchestrator", "scout", timestamp)
```

## Troubleshooting

### Tools not appearing

If multi-agent tools don't exist in your Letta instance:

1. Create a test agent with `include_multi_agent_tools=True`
2. Extract tool IDs from that agent
3. Attach to your production agents
4. Delete test agent

### Agent can't find other agents

Make sure you're using the correct agent ID (agent-xxxxxxxx format).

List all agents:
```bash
curl http://localhost:8283/v1/agents | jq -r '.[] | "\(.name): \(.id)"'
```

## References

- [Letta Multi-Agent Documentation](https://docs.letta.com/guides/agents/multi-agent/)
- [Letta Multi-Agent Tutorial](https://docs.letta.com/tutorials/multi-agent-async/)
- Implementation: `/app/letta/functions/function_sets/multi_agent.py`
- Tests: `/app/tests/integration_test_multi_agent.py`
