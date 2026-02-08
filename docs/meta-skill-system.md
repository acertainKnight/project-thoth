# Meta-Skill System: Creating Skills with Skills

## Overview

Thoth now has a **self-improving meta-skill system** that allows agents to create and update their own skills dynamically. When the `skill-creation-workshop` skill is loaded, agents gain access to `create_skill` and `update_skill` tools that let them expand their own capabilities.

## The Meta-Skill

**Skill**: `skill-creation-workshop`
**Location**: `src/thoth/.skills/skill-creation-workshop/SKILL.md`
**Tools**: `create_skill`, `update_skill`

### What It Does

This comprehensive 586-line skill guides agents through the complete skill creation process:

1. **Validation** - Determines if a new skill is actually needed (3 tests: iterative, conversational, complex)
2. **Design** - Structures the skill with proper sections and patterns
3. **Drafting** - Writes action-focused, conversation-ready content
4. **Testing** - Role-plays using the skill to find issues
5. **Refinement** - Iteratively improves based on testing
6. **Deployment** - Finalizes and saves the skill

### Key Features

- **Decision trees** for determining when skills are needed
- **Conversation patterns** with copy-paste ready dialogue
- **Quality checklists** to ensure skills are effective
- **Refinement patterns** for common issues
- **Testing methodology** with role-play scenarios

## The Tools

### `create_skill` Tool

Creates a new skill in the vault with proper YAML frontmatter and directory structure.

**Parameters:**
```python
{
    "skill_id": str,        # e.g., "paper-analysis"
    "name": str,            # e.g., "Paper Analysis"
    "description": str,     # One-line purpose
    "content": str,         # Full markdown content
    "tools": list[str],     # Optional: Required tools
    "bundle": str           # Optional: Bundle name
}
```

**Example:**
```python
create_skill(
    skill_id="literature-review",
    name="Comprehensive Literature Review",
    description="Guide users through systematic literature reviews with synthesis and gap identification",
    content="""
# Comprehensive Literature Review

## Quick Start: The Standard Review

[skill content here...]
""",
    tools=["answer_research_question", "compare_articles", "find_related_papers"]
)
```

**Output:**
- Creates `vault/thoth/_thoth/skills/literature-review/SKILL.md`
- Skill is immediately available via `list_skills`
- Can be loaded with `load_skill(skill_ids=["literature-review"])`

### `update_skill` Tool

Updates an existing vault skill (bundled skills are read-only).

**Parameters:**
```python
{
    "skill_id": str,        # Skill to update
    "name": str,            # Optional: New name
    "description": str,     # Optional: New description
    "content": str,         # Optional: New content
    "tools": list[str]      # Optional: New tools list
}
```

**Example:**
```python
update_skill(
    skill_id="literature-review",
    content="""
# Comprehensive Literature Review (Updated)

## Quick Start: Enhanced Process

[updated content...]
"""
)
```

## Workflow: Agent Creates a Skill

### Step 1: User Request
```
User: "I keep having to do systematic literature reviews.
       Can we create a skill for that?"
```

### Step 2: Agent Loads Meta-Skill
```
Agent: load_skill(skill_ids=["skill-creation-workshop"], agent_id="agent-xyz")

Result: ✅ Loaded 'skill-creation-workshop' successfully
        Tools added: create_skill, update_skill
        [586 lines of guidance loaded into context]
```

### Step 3: Validation
```
Agent: "Let me validate if this needs a skill using the 3 tests:

1. Is it ITERATIVE? (multiple back-and-forth cycles?)
   ✓ Yes - Reviews involve iterative refinement of scope and synthesis

2. Is it CONVERSATIONAL? (requires guidance and feedback?)
   ✓ Yes - Users need guidance on search strategies, analysis depth, etc.

3. Is it COMPLEX? (multi-step with decisions?)
   ✓ Yes - Multiple phases: scoping, searching, analyzing, synthesizing

Assessment: This PASSES all 3 tests. A skill is warranted!"
```

### Step 4: Design & Draft
```
Agent: "Based on the skill-creation-workshop guidance, I'll design the structure:

## Quick Start
- Standard literature review opening
- 80% case: topic + timeframe → comprehensive synthesis

## Diagnosis Section
- Has user done preliminary search?
- Do they have specific gaps to fill?
- What's the review scope?

## Conversation Patterns
- Pattern 1: New topic exploration
- Pattern 2: Gap identification in known area
- Pattern 3: Methodology-focused review

[Agent drafts full content following the meta-skill's guidance]"
```

### Step 5: Create the Skill
```python
Agent: create_skill(
    skill_id="literature-review",
    name="Comprehensive Literature Review",
    description="Guide systematic literature reviews from scoping to synthesis with gap identification",
    content="""[drafted content]""",
    tools=["answer_research_question", "compare_articles", "find_related_papers", "explore_citation_network"]
)

Result: ✅ Successfully created skill: literature-review
        Location: vault/thoth/_thoth/skills/literature-review/SKILL.md
        Tools: answer_research_question, compare_articles, find_related_papers, explore_citation_network

        Next steps:
        1. The skill is now available - use list_skills to see it
        2. Load it with: load_skill(skill_ids=["literature-review"], agent_id="<your-agent-id>")
        3. Test the skill workflow with a real scenario
        4. Refine using update_skill if needed
```

### Step 6: Test
```
Agent: "Let's test the new skill. I'll unload the creation workshop
        and load the literature review skill..."

unload_skill(skill_ids=["skill-creation-workshop"], agent_id="agent-xyz")
load_skill(skill_ids=["literature-review"], agent_id="agent-xyz")

[Agent role-plays using the skill with a test scenario]

Agent: "Test results:
✓ Quick Start works - clear entry point
✗ Missing decision logic for review depth
? Unclear when to use citation network exploration

Let me refine..."
```

### Step 7: Refine
```python
Agent: load_skill(skill_ids=["skill-creation-workshop"], agent_id="agent-xyz")

Agent: update_skill(
    skill_id="literature-review",
    content="""[updated with better decision logic and citation guidance]"""
)

Result: ✅ Successfully updated skill: literature-review
        Updated: content (2847 characters)

Agent: "Refined! Let me test again..."
```

## Self-Improvement Loop

This creates a **self-improvement loop**:

1. **Agent identifies pattern** - "I keep doing this task repeatedly"
2. **Agent creates skill** - Documents the workflow as a reusable skill
3. **Agent uses skill** - Follows its own guidance on future tasks
4. **Agent refines skill** - Updates based on what works/doesn't work
5. **Cycle continues** - Skills become more refined over time

## Integration with One-Skill-At-A-Time

The meta-skill respects the new skill loading constraints:

1. Agent loads `skill-creation-workshop` (gets `create_skill`, `update_skill`)
2. Agent creates new skill using the tools
3. Agent unloads `skill-creation-workshop`
4. Agent loads the newly created skill to test it
5. If refinement needed, swap back to `skill-creation-workshop`

## Skill Creation Best Practices

From the meta-skill's guidance:

### ✅ Good Skills Are:
- **Action-focused**: Tell agent what to say, not what to think about
- **Conversation-ready**: Include exact dialogue snippets
- **Scannable**: Use tables, decision trees, bullet points
- **Specific**: Concrete examples, not abstract principles
- **Streamlined**: <400 lines, no philosophical rambling

### ❌ Avoid:
- Philosophical discussions about why skills matter
- Abstract instructions like "help the user understand"
- Long paragraphs without structure
- Missing decision logic
- No troubleshooting section

### Required Sections:
1. **Quick Start** - Most common scenario (50-100 lines)
2. **Diagnosis** - Decision trees for different starting points (30-50 lines)
3. **Conversation Patterns** - 3-4 specific flows with dialogue (100-150 lines)
4. **Quick Reference Cards** - Key concepts in scannable format (50-75 lines)
5. **Refinement Patterns** - Common problems and fixes (50-75 lines)
6. **Troubleshooting** - Table of problem/solution pairs (20-30 lines)

## Technical Details

### File Structure
```
vault/thoth/_thoth/skills/
├── skill-creation-workshop/
│   └── SKILL.md                    # Meta-skill
└── [created-skill]/
    └── SKILL.md                    # Agent-created skill
```

### YAML Frontmatter
```yaml
---
name: Skill Name
description: One-line description
tools:                              # Optional
  - tool_1
  - tool_2
---

[Markdown content]
```

### Tool Registration

Tools are registered in `src/thoth/mcp/tools/__init__.py`:
```python
from .skill_management_tools import (
    CreateSkillMCPTool,
    UpdateSkillMCPTool,
)

MCP_TOOL_CLASSES = [
    # ...
    CreateSkillMCPTool,  # Loaded via skill-creation-workshop
    UpdateSkillMCPTool,  # Loaded via skill-creation-workshop
]
```

## Example: Agent Creating Skill

Full example conversation showing agent using the meta-skill:

```
User: "Can you help me create a skill for analyzing research gaps?"

Agent: [Loads skill-creation-workshop]
       "Let me use the skill creation process. First, validation:

       This needs a skill because:
       1. ✓ Iterative - requires back-and-forth on gap significance
       2. ✓ Conversational - needs guidance on different gap types
       3. ✓ Complex - multi-phase: identification → analysis → prioritization

       Proceeding with design..."

       [Designs structure following meta-skill guidance]
       [Drafts content with conversation patterns]

       create_skill(
           skill_id="research-gap-analysis",
           name="Research Gap Analysis",
           description="Systematically identify, analyze, and prioritize research gaps in literature",
           content="...",
           tools=["answer_research_question", "compare_articles"]
       )

       ✅ Skill created! Want to test it?

User: "Yes, test it with machine learning fairness as a topic"

Agent: [Unloads skill-creation-workshop]
       [Loads research-gap-analysis]
       [Executes workflow using new skill]

       "Test complete! The skill works well. Found one issue:
       - Missing guidance on distinguishing theoretical vs empirical gaps

       Shall I refine it?"

User: "Yes please"

Agent: [Swaps skills]
       [Updates with refinement]
       ✅ Updated! The skill is now production-ready.
```

## Benefits

1. **Self-Expanding System** - Agents can add capabilities without code changes
2. **Iterative Refinement** - Skills improve through use and testing
3. **User Customization** - Users can request skills for their specific workflows
4. **Knowledge Capture** - Successful workflows become reusable skills
5. **Reduced Maintenance** - Skills are markdown files, easy to version control

## Future Enhancements

Possible improvements:
- **Skill versioning** - Track iterations of skills
- **Skill sharing** - Export/import skills between installations
- **Skill analytics** - Track which skills are used most
- **Auto-skill-creation** - Agent proactively suggests skills after repeated patterns
- **Skill composition** - Combine multiple skills into workflows

## Summary

The meta-skill system closes the loop on self-improvement:
- Agents can now **create** skills (via `create_skill`)
- Agents can now **refine** skills (via `update_skill`)
- Agents use comprehensive **guidance** (via `skill-creation-workshop`)
- System becomes **more capable over time** through emergent skills

This transforms Thoth from a static tool system into a **living, learning, self-improving research assistant**.
