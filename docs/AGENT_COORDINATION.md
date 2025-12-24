# Agent Coordination System

**Status**: ✅ Production Ready
**Version**: 1.0.0
**Date**: 2025-12-24

## Overview

The Thoth agent coordination system enables asynchronous communication and task delegation between multiple Letta agents using shared memory blocks as a message queue.

## Architecture

### Shared Memory Blocks

The system uses 6 shared memory blocks:

1. **research_context** (1000 chars) - Current research topic and scope
2. **active_papers** (2000 chars) - Papers in the processing pipeline
3. **citation_network** (1500 chars) - Citation relationships
4. **research_findings** (2000 chars) - Synthesized insights
5. **workflow_state** (800 chars) - Current workflow status
6. **message_queue** (3000 chars) - Agent-to-agent messages

All blocks are attached to all 4 agents, enabling complete visibility and coordination.

### Agents

- **thoth_main_orchestrator** - Coordinates workflow, delegates tasks
- **system_discovery_scout** - Searches for and discovers papers
- **system_citation_analyzer** - Builds citation networks
- **system_analysis_expert** - Synthesizes findings and insights

## Message Queue Protocol

### Message Format

```
[timestamp] sender -> receiver
Task: description
Priority: high/medium/low/critical
Status: pending/in_progress/complete
Metadata: {"key": "value"}
---
```

### Example Message

```
[2025-12-24 10:30:00] thoth_main_orchestrator -> system_discovery_scout
Task: Find recent papers on large language models
Priority: high
Status: pending
Metadata: {"search_terms": ["LLM", "reasoning"], "max_results": 15}
---
```

## Usage

### Python API

```python
from thoth.coordination.message_queue import (
    post_message,
    read_messages_for_agent,
    mark_message_complete
)

# Post a task
post_message(
    sender="thoth_main_orchestrator",
    receiver="system_discovery_scout",
    task="Find papers on quantum computing",
    priority="high",
    metadata={"max_results": 10}
)

# Check for pending tasks
pending = read_messages_for_agent(
    "system_discovery_scout",
    status="pending"
)

# Mark task complete
mark_message_complete(
    sender="thoth_main_orchestrator",
    receiver="system_discovery_scout",
    timestamp="2025-12-24 10:30:00"
)
```

### Command Line

```bash
# Create message queue block
python3 scripts/create_message_queue.py

# Run example workflow
python3 examples/research_workflow_with_coordination.py
```

## Workflow Patterns

### Pattern 1: Simple Delegation

Orchestrator delegates a single task to a specialist agent.

```python
# Orchestrator
post_message(
    sender="thoth_main_orchestrator",
    receiver="system_discovery_scout",
    task="Search for papers",
    priority="high"
)

# Scout (checks queue periodically)
pending = read_messages_for_agent("system_discovery_scout", status="pending")
for task in pending:
    execute_task(task)
    mark_message_complete(task['sender'], task['receiver'], task['timestamp'])
```

### Pattern 2: Sequential Pipeline

Tasks with dependencies execute in order.

```python
# Task 1: Discovery
post_message(
    sender="orchestrator",
    receiver="scout",
    task="Find papers",
    metadata={"task_id": "discovery_1"}
)

# Task 2: Analysis (depends on Task 1)
post_message(
    sender="orchestrator",
    receiver="analyzer",
    task="Analyze citations",
    metadata={"depends_on": "discovery_1"}
)

# Agents check dependencies via shared memory blocks
```

### Pattern 3: Parallel Execution

Multiple agents work on independent tasks simultaneously.

```python
# Delegate to multiple agents
for agent in ["scout", "analyzer", "expert"]:
    post_message(
        sender="orchestrator",
        receiver=agent,
        task=f"Process batch {agent}",
        priority="medium"
    )

# All agents process tasks in parallel
```

## Best Practices

### For Orchestrator

1. **Delegate clearly** - Specify task, priority, and metadata
2. **Check dependencies** - Ensure prerequisites are met
3. **Monitor progress** - Read workflow_state block regularly
4. **Handle failures** - Retry failed tasks with backoff

### For Workers

1. **Poll regularly** - Check message queue every 30-60 seconds
2. **Update state** - Write progress to shared memory blocks
3. **Mark complete** - Always mark messages as complete when done
4. **Handle errors** - Report failures via workflow_state block

### General

1. **Use priorities** - High priority tasks first
2. **Clean old messages** - Call `clear_old_messages()` periodically
3. **Metadata for context** - Include relevant data in metadata field
4. **Check dependencies** - Read shared memory before starting tasks

## API Reference

### `post_message(sender, receiver, task, priority="medium", metadata=None)`

Post a message to the agent message queue.

**Parameters**:
- `sender` (str): Agent name posting the message
- `receiver` (str): Agent name receiving the message
- `task` (str): Task description
- `priority` (str): Priority level (low/medium/high/critical)
- `metadata` (dict): Optional additional data

**Returns**: `bool` - True if successful

### `read_messages()`

Read all messages from the queue.

**Returns**: `List[Dict]` - List of message dictionaries

### `read_messages_for_agent(agent_name, status=None)`

Read messages for a specific agent.

**Parameters**:
- `agent_name` (str): Name of receiving agent
- `status` (str): Optional status filter (pending/in_progress/complete)

**Returns**: `List[Dict]` - Filtered messages

### `mark_message_complete(sender, receiver, timestamp)`

Mark a message as complete.

**Parameters**:
- `sender` (str): Original sender
- `receiver` (str): Original receiver
- `timestamp` (str): Message timestamp for identification

**Returns**: `bool` - True if successful

### `clear_old_messages(keep_recent=10)`

Clear old completed messages.

**Parameters**:
- `keep_recent` (int): Number of recent messages to keep

**Returns**: `bool` - True if successful

## Implementation Notes

### Why Shared Memory vs Native Tools?

Letta v0.16.1 does not provide built-in agent-to-agent communication tools. The message queue via shared memory provides:

- ✅ Works with current Letta version
- ✅ No external dependencies
- ✅ Persistent message history
- ✅ All agents have access
- ⚠️ Requires polling (not event-driven)
- ⚠️ Manual message parsing needed

When Letta releases native communication tools, migration will be straightforward as the message format and workflow patterns remain the same.

### Database Schema

Message queue stored in Letta PostgreSQL database:

- Table: `blocks`
- Block Label: `message_queue`
- Limit: 3000 characters
- All 4 agents have read/write access

### Performance

- Message posting: ~50ms (HTTP + DB update)
- Message reading: ~30ms (HTTP + parsing)
- Recommended polling: 30-60 seconds
- Max queue size: ~20-30 messages (3000 char limit)

## Troubleshooting

### Messages Not Appearing

```bash
# Check if block exists
curl http://localhost:8283/v1/blocks/ | grep message_queue

# Verify agent has block attached
curl http://localhost:8283/v1/agents/AGENT_ID | grep message_queue
```

### Database Connection Issues

```bash
# Check Letta is running
docker ps | grep thoth-letta

# Check logs
docker logs thoth-letta --tail 50
```

### Clear Stuck Messages

```python
from thoth.coordination.message_queue import clear_old_messages

# Clear all completed messages
clear_old_messages(keep_recent=0)
```

## Examples

See `examples/research_workflow_with_coordination.py` for a complete workflow demonstration.

## Testing

```bash
# Run tests (requires pytest)
python3 -m pytest tests/test_message_queue.py -v

# Manual test
python3 -c "from thoth.coordination.message_queue import *; ..."
```

## Future Enhancements

When native Letta communication becomes available:

1. Replace message queue calls with native tools
2. Enable event-driven coordination (no polling)
3. Add delivery confirmation
4. Support broadcast messages
5. Implement priority queues

The current implementation provides a stable foundation for immediate use while maintaining compatibility with future native features.

## License

MIT License - See LICENSE file for details
