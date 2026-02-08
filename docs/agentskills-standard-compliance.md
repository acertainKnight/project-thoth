# AgentSkills.io Standard Compliance

## Overview

Thoth's skill system now fully complies with the **AgentSkills.io open standard** for AI skills. This ensures interoperability, portability, and compatibility with other AI systems that follow the same standard.

## What is AgentSkills.io?

AgentSkills.io is an **open standard** for defining AI skills using a lightweight, self-documenting format. It was created to enable:
- **Portability**: Skills work across different AI systems
- **Interoperability**: Skills can be shared and reused
- **Extensibility**: Easy to add new capabilities
- **Self-documentation**: Skills describe themselves

## Standard Requirements

### Required Fields

#### 1. `name` (YAML frontmatter)
- **Length**: 1-64 characters
- **Format**: Lowercase alphanumeric and hyphens only
- **Rules**:
  - Cannot start or end with hyphen
  - Cannot contain consecutive hyphens (`--`)
  - **MUST match parent directory name** ✓
- **Example**: `paper-analysis` (directory: `paper-analysis/`)

#### 2. `description` (YAML frontmatter)
- **Length**: 1-1024 characters
- **Purpose**: Describes what the skill does and when to use it
- **Example**: "Systematic paper analysis from reading to synthesis with gap identification"

### Optional Fields

#### 3. `tools` (YAML frontmatter)
- **Type**: List of strings
- **Purpose**: Tools required by this skill
- **Thoth Extension**: Automatically attached when skill is loaded
- **Example**: `["search_articles", "answer_research_question"]`

#### 4. `license` (YAML frontmatter)
- **Type**: String
- **Purpose**: License name or reference to bundled license file
- **Example**: `MIT` or `LICENSE.txt`

#### 5. `compatibility` (YAML frontmatter)
- **Length**: Max 500 characters
- **Purpose**: Environment requirements or compatibility notes
- **Example**: "Requires access to academic paper databases"

#### 6. `metadata` (YAML frontmatter)
- **Type**: Key-value mapping
- **Purpose**: Arbitrary additional metadata
- **Not yet implemented in Thoth**

## Thoth Implementation

### File Structure

```
vault/thoth/_thoth/skills/
└── [skill-id]/              # Directory name
    └── SKILL.md             # Required file
```

### SKILL.md Format

```yaml
---
name: skill-id              # MUST match directory name (AgentSkills.io)
description: Clear description of what this skill does (1-1024 chars)
tools:                      # Optional (Thoth extension)
  - tool_name_1
  - tool_name_2
license: MIT                # Optional (AgentSkills.io)
compatibility: Notes here   # Optional (AgentSkills.io, max 500 chars)
---

# Skill Content (Markdown)

## Purpose
[What this skill does...]

## Workflow
[Step-by-step guide...]
```

### Validation Rules

The `create_skill` tool enforces these AgentSkills.io rules:

**skill_id validation:**
```python
# Pattern: ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$
# ✓ Valid: "paper-analysis", "lit-review", "ml-fairness"
# ✗ Invalid: "-paper", "paper-", "paper--analysis", "Paper-Analysis"
```

**description validation:**
```python
# Length: 1-1024 characters
# ✓ Valid: Any description within this range
# ✗ Invalid: Empty string, >1024 chars
```

**compatibility validation:**
```python
# Length: max 500 characters (if provided)
# ✓ Valid: "Requires Python 3.8+, OpenAI API access"
# ✗ Invalid: String >500 characters
```

### Tool Output

When creating a skill, the tool confirms compliance:

```
✅ Successfully created skill: literature-review

**AgentSkills.io Standard Compliance:**
- name: literature-review (matches directory ✓)
- description: 243 chars (1-1024 ✓)

**Location**: /path/to/literature-review/SKILL.md
**Display Name**: Literature Review (auto-generated from name)
**Description**: Systematic literature reviews from scoping to synthesis...
**Tools**: answer_research_question, compare_articles
**License**: MIT
**Compatibility**: Requires academic database access

**AgentSkills.io**: Skill follows open standard for AI skills
```

**Note**: The `display_name` is automatically generated from the `name` field (e.g., `literature-review` → "Literature Review") for human-readable UI display. The `name` field itself must match the directory name per AgentSkills.io standard.

## Progressive Disclosure

AgentSkills.io uses a three-stage approach:

### 1. Discovery
- **Load**: Only name and description
- **Purpose**: Browse available skills quickly
- **Thoth**: `list_skills` returns metadata without full content

### 2. Activation
- **Load**: Full instructions when skill is matched
- **Purpose**: Agent reads guidance when needed
- **Thoth**: `load_skill` returns full SKILL.md content

### 3. Execution
- **Load**: Referenced files or bundled code as needed
- **Purpose**: Access resources on-demand
- **Thoth**: Tools are attached dynamically when skill loads

## Benefits of Standard Compliance

### 1. Portability
- Skills created in Thoth can work in other AgentSkills.io-compliant systems
- Skills from other systems can be imported into Thoth

### 2. Validation
- Strict naming rules prevent errors
- Clear length limits ensure consistency
- Automatic validation on creation

### 3. Interoperability
- Standard format enables skill sharing
- Common structure makes skills easier to understand
- Tooling can be built once and reused

### 4. Documentation
- Self-describing format
- No external docs needed
- Version control friendly (markdown)

## Comparison: Before vs After

### Before (Thoth-specific)
```yaml
---
name: Any Display Name Here
description: Short text (no length limit)
---
```
- ✗ Directory name could differ from `name` field
- ✗ No validation rules
- ✗ Not portable to other systems

### After (AgentSkills.io)
```yaml
---
name: skill-id                    # MUST match directory
description: Description text... # 1-1024 chars
tools:                           # Optional
  - tool_1
license: MIT                     # Optional
compatibility: Notes...          # Optional, max 500 chars
---
```
- ✓ Directory name matches `name` field (enforced)
- ✓ Strict validation rules
- ✓ Portable to other AgentSkills.io systems
- ✓ Optional standard fields supported

## Migration Path

### Existing Skills
Thoth's bundled skills already follow the naming convention where the directory name matches the `name` field, so they're automatically compliant with AgentSkills.io.

### Future Skills
All new skills created via `create_skill` tool automatically follow the AgentSkills.io standard with validation enforced.

### Updating Skills
The `update_skill` tool automatically maintains the `name` field to match the directory name (AgentSkills.io requirement).

## Example: Creating a Compliant Skill

```python
# Agent loads meta-skill
load_skill(skill_ids=["skill-creation-workshop"], agent_id="agent-123")

# Agent creates AgentSkills.io compliant skill
create_skill(
    skill_id="literature-review",           # Will be directory name AND YAML name
    display_name="Literature Review",        # Optional, for UI display
    description="Systematic literature reviews from scoping to synthesis with gap identification and methodology assessment",
    content="""
# Literature Review

## Purpose
Guide users through comprehensive literature reviews...

## Workflow
1. Scope definition
2. Search strategy
3. Paper selection
4. Analysis
5. Synthesis
""",
    tools=["answer_research_question", "compare_articles", "find_related_papers"],
    license="MIT",
    compatibility="Requires access to academic paper databases"
)

# Result:
# ✓ Directory created: literature-review/
# ✓ SKILL.md with name: literature-review (matches directory ✓)
# ✓ Description: 126 chars (within 1-1024 ✓)
# ✓ All optional fields included
# ✓ Fully AgentSkills.io compliant
```

## References

- **Specification**: https://agentskills.io/specification
- **GitHub**: https://github.com/anthropics/skills
- **What are skills**: https://agentskills.io/what-are-skills

## Display Name Handling

To maintain both AgentSkills.io compliance and good UX:

- **`name` field**: Lowercase with hyphens, matches directory (e.g., `paper-discovery`)
- **`display_name`**: Auto-generated Title Case for UI display (e.g., "Paper Discovery")
- **Formula**: `name.replace('-', ' ').title()`

This approach ensures:
- ✅ Full AgentSkills.io standard compliance
- ✅ Clean, readable names in UI and agent outputs
- ✅ No manual display name maintenance required

## Summary

Thoth now creates **fully compliant AgentSkills.io skills** with:

✅ **Required fields**: `name` (matching directory), `description` (1-1024 chars)
✅ **Optional fields**: `tools`, `license`, `compatibility`
✅ **Validation**: Automatic enforcement of naming and length rules
✅ **Portability**: Skills can work across AgentSkills.io systems
✅ **Progressive disclosure**: Three-stage loading (discovery, activation, execution)
✅ **Display names**: Auto-generated from `name` field for clean UI display

The meta-skill system now creates **portable, interoperable, standard-compliant** skills that can be shared across the AI ecosystem.
