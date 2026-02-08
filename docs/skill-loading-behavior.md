# Skill Loading System - One Skill at a Time

## Overview

The skill loading system has been updated to ensure that agents can only have **ONE skill loaded at a time**. This prevents tool bloat and ensures agents have a focused set of capabilities at any given moment.

## Behavior

### Initial State
- Agents start with `load_skill` tool available
- Agents do NOT have `unload_skill` tool initially

### When Loading a Skill

1. Agent calls `load_skill(skill_ids=["skill-name"], agent_id="agent-123")`
2. System checks if agent already has a skill loaded
   - If YES: Returns error asking to unload first
   - If NO: Proceeds with loading
3. Skill content is loaded and returned
4. Required tools for the skill are attached to the agent
5. **Tool swap occurs:**
   - `load_skill` tool is REMOVED from agent
   - `unload_skill` tool is ADDED to agent
6. Agent's loaded skills are tracked in `_AGENT_LOADED_SKILLS` registry

### When Unloading a Skill

1. Agent calls `unload_skill(skill_ids=["skill-name"], agent_id="agent-123")`
2. System verifies:
   - Agent has skills loaded
   - Requested skill IDs match what's currently loaded
3. Skill-specific tools are detached from the agent
4. **Tool swap occurs:**
   - `unload_skill` tool is REMOVED from agent
   - `load_skill` tool is ADDED back to agent
5. Agent's loaded skills are cleared from `_AGENT_LOADED_SKILLS` registry

## Example Workflow

```python
# Agent starts with load_skill available
agent_tools = ['list_skills', 'load_skill', 'search_articles']

# Agent loads paper-discovery skill
load_skill(skill_ids=["paper-discovery"], agent_id="agent-123")
# Result:
# - paper-discovery skill content loaded
# - Tools added: arxiv_search, semantic_scholar_search, etc.
# - load_skill REMOVED
# - unload_skill ADDED

agent_tools = ['list_skills', 'unload_skill', 'search_articles',
               'arxiv_search', 'semantic_scholar_search', ...]

# Agent tries to load another skill (ERROR)
load_skill(skill_ids=["deep-research"], agent_id="agent-123")
# Result: Error - must unload paper-discovery first

# Agent unloads current skill
unload_skill(skill_ids=["paper-discovery"], agent_id="agent-123")
# Result:
# - paper-discovery tools REMOVED
# - unload_skill REMOVED
# - load_skill ADDED back

agent_tools = ['list_skills', 'load_skill', 'search_articles']

# Now agent can load a different skill
load_skill(skill_ids=["deep-research"], agent_id="agent-123")
# Success!
```

## Implementation Details

### Global State Tracking
```python
# Global registry to track which agents have skills loaded
# Key: agent_id, Value: list of loaded skill_ids
_AGENT_LOADED_SKILLS: dict[str, list[str]] = {}
```

### Required Parameters
Both `load_skill` and `unload_skill` now **require** `agent_id`:
- Needed for Letta API tool attachment/detachment
- Needed for tool swapping (load_skill ⇄ unload_skill)
- Needed for tracking loaded skills per agent

### Error Handling

**Load errors:**
- No agent_id provided → Error
- Agent already has skill loaded → Error (shows current skill)
- Skill not found → Error

**Unload errors:**
- No agent_id provided → Error
- No skills currently loaded → Warning (not an error)
- Requested skill doesn't match loaded → Error

## Benefits

1. **Prevents tool bloat**: Agent never has more than one skill's tools loaded
2. **Clear state management**: Agent always knows if it can load or unload
3. **Enforces workflow**: Agent must finish with current skill before loading new one
4. **Better UX**: Clear error messages guide agents through proper usage

## Migration Notes

### Breaking Changes
- `agent_id` is now **required** for both `load_skill` and `unload_skill`
- `detach_tools` parameter removed from `unload_skill` (always detaches now)
- Only one skill can be loaded at a time per agent

### Agent Initialization
- Orchestrator agent starts with `load_skill` only (not `unload_skill`)
- This ensures proper initial state

## Future Enhancements

Possible improvements:
1. Add `list_loaded_skills()` tool for agents to check current state
2. Support skill priority/categories for auto-swapping
3. Add `swap_skill(from_skill, to_skill)` for single-operation swapping
4. Persist loaded skills state across MCP server restarts
