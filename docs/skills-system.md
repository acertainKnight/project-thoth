# Thoth Skills System

Complete guide to the dynamic skill-loading system that enables on-demand tool attachment.

## Table of Contents

- [Overview](#overview)
- [How Skills Work](#how-skills-work)
- [Bundled Skills](#bundled-skills)
- [Creating Custom Skills](#creating-custom-skills)
- [Skill Format](#skill-format)
- [Tool Loading Workflow](#tool-loading-workflow)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

The skills system enables **dynamic tool loading** for Letta agents, solving the "too many tools" problem that degrades LLM performance.

### The Problem

- MCP server has 64 tools total
- Loading all tools into one agent causes:
  - Token bloat (worse performance)
  - Confusion (LLM struggles to choose)
  - Cost inefficiency (pay for unused context)

### The Solution

**Skill-Based Loading**:
1. Agent starts with minimal tools (3-4 core tools)
2. User makes request: "Find papers on transformers"
3. Agent loads relevant skill: `load_skill(skill_ids=["paper-discovery"])`
4. Skill attaches its ~6 tools dynamically
5. Agent uses tools, then unloads skill when done

**Benefits**:
- **60-80% fewer tools** in agent context at any time
- **Better LLM performance**: Clearer tool choices
- **Token efficiency**: Pay only for what's active
- **Modular capabilities**: Skills as logical units

---

## How Skills Work

### Components

1. **Skill Files**: `SKILL.md` with YAML frontmatter
2. **Skill Service** (`src/thoth/services/skill_service.py`): Discovery and loading
3. **MCP Tools**: `load_skill`, `unload_skill`, `list_skills`
4. **Letta API**: Attach/detach tools from agents

### Architecture

```
User Request
    ↓
Agent (Orchestrator)
    ↓
load_skill(skill_ids=["paper-discovery"])
    ↓
Skill Service
    ├─ Parse SKILL.md YAML frontmatter
    ├─ Extract required tools list
    └─ Call Letta API to attach tools
    ↓
Agent now has skill tools available
    ↓
Agent follows skill guidance
    ↓
unload_skill(skill_ids=["paper-discovery"])  # Optional cleanup
```

### Discovery Hierarchy

Skills are discovered from 2 locations (in order):

1. **Vault Skills** (`vault/thoth/_thoth/skills/`):
   - User-created custom skills
   - Override bundled skills with same name
   - Hot-reloadable (no restart needed)

2. **Bundled Skills** (`src/thoth/.skills/`):
   - Shipped with Thoth
   - Core functionality
   - Updated with Thoth releases

---

## Bundled Skills

### Active Skills (9)

| Skill | Purpose | Tools | When to Use |
|-------|---------|-------|-------------|
| **paper-discovery** | Find papers from academic sources | 6 | User wants to find/search papers |
| **knowledge-base-qa** | Answer questions from collection | 5 | User asks questions about existing papers |
| **deep-research** | Comprehensive literature analysis | 12 | User needs in-depth analysis, literature review |
| **research-project-coordination** | Multi-phase project management | 8 | User has long-term research project |
| **research-query-management** | Automated recurring searches | 7 | User wants scheduled discovery |
| **rag-administration** | Advanced RAG management | 5 | Admin tasks: reindex, optimize search |
| **settings-management** | Configure Thoth through chat | 4 | User wants to change settings |
| **custom-source-setup** | Create custom article sources | 3 | User wants papers from unlisted website |
| **onboarding** | Initialize new users | 4 | First-time user setup |

### Skill Details

#### 1. Paper Discovery

**File**: `src/thoth/.skills/paper-discovery/SKILL.md`

**Tools** (6):
- `list_available_sources` - See available sources
- `create_research_question` - Create search query
- `run_discovery_for_question` - Execute search
- `list_articles` - Browse results
- `search_articles` - Filter/search results
- `collection_stats` - Check collection size

**Quick Workflow**:
```
1. Create research question
   create_research_question(
     title="Topic description",
     keywords=["key1", "key2"],
     sources=["semantic_scholar", "openalex"],
     max_papers=25
   )

2. Run discovery
   run_discovery_for_question(question_id="xyz")

3. Review results
   list_articles(limit=20, sort_by="relevance")
```

#### 2. Knowledge Base Q&A

**File**: `src/thoth/.skills/knowledge-base-qa/SKILL.md`

**Tools** (5):
- `answer_research_question` - Deep Q&A with citations
- `search_articles` - Search collection
- `get_article_details` - Get paper details
- `find_related_papers` - Similarity search
- `collection_stats` - Collection overview

**Use Cases**:
- "What papers discuss attention mechanisms?"
- "Summarize the findings on topic X"
- "Compare approach A vs B in my collection"

#### 3. Deep Research

**File**: `src/thoth/.skills/deep-research/SKILL.md`

**Tools** (12):
- All knowledge-base-qa tools
- `explore_citation_network` - Citation analysis
- `compare_articles` - Systematic comparison
- `evaluate_article` - Quality assessment
- `get_citation_context` - Citation context
- `generate_research_summary` - Literature review

**Workflow**:
```
1. Define research scope
2. Search and curate papers (paper-discovery)
3. Load deep-research skill
4. Systematic analysis:
   - Read and evaluate papers
   - Extract key findings
   - Map citation networks
   - Identify research gaps
5. Generate synthesis
```

#### 4. Research Project Coordination

**File**: `src/thoth/.skills/research-project-coordination/SKILL.md`

**Tools** (8):
- `create_research_question` - Define project
- `run_discovery_for_question` - Find papers
- `search_articles` - Browse collection
- `answer_research_question` - Analysis
- `generate_reading_list` - Organize papers
- `sync_with_obsidian` - Export notes
- `get_task_status` - Track progress

**Phases**:
1. **Planning**: Define research questions, scope
2. **Discovery**: Find relevant papers
3. **Reading**: Generate reading list, prioritize
4. **Analysis**: Deep dive, synthesis
5. **Writing**: Export notes, sync with Obsidian

#### 5. Research Query Management

**File**: `src/thoth/.skills/research-query-management/SKILL.md`

**Tools** (7):
- `create_research_question` - Define query
- `list_research_questions` - View all queries
- `update_research_question` - Modify query
- `delete_research_question` - Remove query
- `run_discovery_for_question` - Manual run
- `collection_stats` - Check results

**Automated Discovery**:
```
1. Create query with schedule
   create_research_question(
     title="Weekly ML papers",
     keywords=["machine learning", "2024"],
     sources=["arxiv"],
     schedule="0 9 * * MON"  # Every Monday 9 AM
   )

2. Scheduler runs automatically
3. New papers added to collection
4. Agent notifies user of new findings
```

#### 6. RAG Administration

**File**: `src/thoth/.skills/rag-administration/SKILL.md`

**Tools** (5):
- `reindex_collection` - Rebuild vector index
- `optimize_search` - Tune search parameters
- `create_custom_index` - Domain-specific index
- `search_custom_index` - Query custom index
- `list_custom_indexes` - View all indexes

**Admin Tasks**:
- Rebuild index after adding many papers
- Optimize search for specific domains
- Create specialized indexes (e.g., methods-only)

#### 7. Settings Management

**File**: `src/thoth/.skills/settings-management/SKILL.md`

**Tools** (4):
- `view_settings` - Display current settings
- `update_settings` - Modify configuration
- `validate_settings` - Check validity
- `reset_settings` - Restore defaults

**Example**:
```
User: "Change the default model to Claude 3.5 Sonnet"

Agent:
1. Loads settings-management skill
2. Calls view_settings() to see current config
3. Calls update_settings({
     "llm_config.default.model": "openrouter/anthropic/claude-3.5-sonnet"
   })
4. Confirms change applied
```

#### 8. Custom Source Setup

**File**: `src/thoth/.skills/custom-source-setup/SKILL.md`

**Tools** (3):
- `analyze_source_url` - LLM-powered page analysis
- `refine_source_selectors` - Iterative improvement
- `confirm_source_workflow` - Save workflow

**Automated Scraper Builder**:
```
User: "Can you get papers from Nature.com?"

Agent:
1. Loads custom-source-setup skill
2. analyze_source_url("https://www.nature.com/articles")
   → LLM proposes CSS selectors
   → Tests selectors, extracts sample articles
3. Shows samples to user
4. User: "The dates are wrong"
   refine_source_selectors(feedback="dates are incorrect")
   → LLM refines selectors
5. User: "Looks good"
   confirm_source_workflow()
   → Saves workflow for future use
```

**How It Works**:
- Playwright loads page, extracts simplified DOM
- LLM analyzes structure, proposes selectors
- Selectors tested on live page
- Iterative refinement based on user feedback
- Confirmed workflow saved

#### 9. Onboarding

**File**: `src/thoth/.skills/onboarding/SKILL.md`

**Tools** (4):
- `list_available_sources` - Show sources
- `collection_stats` - Check collection
- `view_settings` - Show configuration
- `create_research_question` - First search

**First-Time Workflow**:
1. Introduce Thoth capabilities
2. Explain skill system
3. Guide first paper search
4. Set up research question

---

## Creating Custom Skills

### Quick Start

1. **Create directory**:
   ```bash
   mkdir -p "$OBSIDIAN_VAULT_PATH/thoth/_thoth/skills/my-skill"
   ```

2. **Create SKILL.md**:
   ```yaml
   ---
   name: My Custom Skill
   description: What this skill does
   tools:
     - tool_name_1
     - tool_name_2
   ---

   # My Custom Skill

   ## Purpose

   [Explain when to use this skill]

   ## Workflow

   1. Step 1: Use tool_name_1 to...
   2. Step 2: Use tool_name_2 to...
   3. Step 3: Return results
   ```

3. **Agent discovers automatically** (no restart needed)

4. **Load skill**:
   ```
   User: "Load my-skill"
   Agent: load_skill(skill_ids=["my-skill"])
   ```

### Example: Literature Review Skill

```yaml
---
name: Literature Review
description: Generate comprehensive literature reviews for academic papers
tools:
  - search_articles
  - answer_research_question
  - explore_citation_network
  - compare_articles
  - generate_research_summary
---

# Literature Review

Generate comprehensive literature reviews following academic standards.

## Workflow

### 1. Scope Definition
- Ask user for: topic, timeframe, key papers
- Use `search_articles` to verify papers exist in collection

### 2. Paper Collection
- Find papers matching topic: `search_articles(query="...", filters=...)`
- Identify seminal works: `explore_citation_network` (high citation count)
- Find recent advances: Filter by year >= 2023

### 3. Thematic Analysis
- Group papers by approach/method
- Use `compare_articles` to identify similarities/differences
- Note: trends, evolution, contradictions

### 4. Synthesis
- `generate_research_summary` with structured sections:
  - Introduction: Context and significance
  - Evolution: Historical development
  - Current State: Recent advances
  - Research Gaps: What's missing
  - Future Directions: Opportunities

### 5. Citation Network
- `explore_citation_network` to identify:
  - Seminal papers (high in-degree)
  - Influential authors (centrality)
  - Research clusters (communities)

## Output Format

Structure review as:
1. **Overview**: 2-3 paragraphs summarizing field
2. **Thematic Sections**: Group papers by theme
3. **Synthesis**: Integrate findings across papers
4. **Gaps**: What's missing in current research
5. **Conclusion**: Summary and future directions
```

---

## Skill Format

### YAML Frontmatter

```yaml
---
name: Skill Name                # Required: Display name
description: What this skill does  # Required: When to use it
tools:                          # Required: Tool names (list)
  - tool_1
  - tool_2
  - tool_3
---
```

### Body Content (Markdown)

**Sections** (recommended):
1. **Purpose**: What the skill does
2. **Tools**: List tools and their purposes
3. **Workflow**: Step-by-step guide
4. **Examples**: Concrete usage examples
5. **Tips**: Best practices

**Formatting**:
- Use headers (`##`, `###`) for structure
- Use tables for tool references
- Use code blocks for examples
- Use lists for workflows

---

## Tool Loading Workflow

### Load Skill

**Via Agent**:
```
User: "Load the paper-discovery skill"
Agent: load_skill(skill_ids=["paper-discovery"], agent_id="agent_xyz")
```

**What Happens**:
1. Skill service parses `SKILL.md` YAML frontmatter
2. Extracts `tools` list
3. Calls Letta API: `POST /v1/agents/{agent_id}/tools/attach`
4. Tools now available to agent
5. Agent reads skill body for guidance
6. Skill marked as "loaded" in agent memory

### Unload Skill

```
Agent: unload_skill(skill_ids=["paper-discovery"], agent_id="agent_xyz")
```

**What Happens**:
1. Skill service looks up skill's tools
2. Calls Letta API: `POST /v1/agents/{agent_id}/tools/detach`
3. Tools removed from agent
4. Skill unmarked in agent memory

### List Skills

```
Agent: list_skills()
```

**Returns**:
```json
{
  "bundled": [
    {"id": "paper-discovery", "name": "Paper Discovery", "description": "...", "loaded": true},
    {"id": "knowledge-base-qa", "name": "Knowledge Base Q&A", "description": "...", "loaded": false}
  ],
  "vault": [
    {"id": "my-skill", "name": "My Custom Skill", "description": "...", "loaded": false}
  ]
}
```

---

## Best Practices

### For Skill Authors

1. **Clear Purpose**: Description should state exactly when to use skill
2. **Minimal Tools**: Only include essential tools (5-10 max)
3. **Step-by-Step**: Provide clear workflow with numbered steps
4. **Examples**: Include concrete usage examples
5. **Tool Tables**: Reference tools with descriptions

### For Agent Usage

1. **Load-Execute-Unload**: Load skill → use tools → unload when done
2. **Check First**: Use `list_skills` if unsure which skill to load
3. **Update Memory**: Track loaded skills in `loaded_skills` memory block
4. **Single Skill**: Focus on one skill at a time (avoid overload)

### For Users

1. **Custom Skills**: Create skills for recurring workflows
2. **Override Bundled**: Place custom version in vault to override
3. **Hot-Reload**: Edit skills and they reload automatically
4. **Share Skills**: Share `SKILL.md` files with colleagues

---

## Troubleshooting

### Skill Not Found

**Problem**: `list_skills` doesn't show custom skill

**Solution**:
```bash
# Check skill exists
ls "$OBSIDIAN_VAULT_PATH/thoth/_thoth/skills/my-skill/SKILL.md"

# Check YAML syntax
cat "$OBSIDIAN_VAULT_PATH/thoth/_thoth/skills/my-skill/SKILL.md" | head -10

# Restart Thoth to force reload
make dev-thoth-restart
```

### Tools Not Attaching

**Problem**: `load_skill` succeeds but tools not available

**Solution**:
```bash
# Check tool names in YAML match MCP tools
curl http://localhost:8082/mcp \
  -X POST \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}'

# Check agent tools
curl http://localhost:8283/v1/agents/{agent_id}/tools

# Check Thoth logs
make dev-logs | grep "load_skill"
```

### YAML Parse Error

**Problem**: Skill YAML frontmatter invalid

**Solution**:
- Ensure `---` delimiters on their own lines
- Check for proper indentation (2 spaces)
- Validate YAML syntax online
- Check tool names are strings (quoted if needed)

Example:
```yaml
❌ BAD:
--- name: My Skill
tools: [tool1, tool2]
---

✅ GOOD:
---
name: My Skill
tools:
  - tool1
  - tool2
---
```

---

## Advanced

### Skill Bundles

**Location**: `src/thoth/.skills/bundles/`

Meta-skills that load multiple skills:
```yaml
---
name: Research Workflow Coordination
description: Complete research workflow from discovery to synthesis
includes:
  - paper-discovery
  - knowledge-base-qa
  - deep-research
---
```

### Conditional Tool Loading

Skills can specify optional tools:
```yaml
---
name: Advanced Analysis
tools:
  - search_articles  # Required
  - reindex_collection  # Optional (from rag-administration)
optional_tools:
  - optimize_search
---
```

### Skill Versioning

Version skills for backward compatibility:
```yaml
---
name: Paper Discovery v2
version: 2.0.0
replaces: paper-discovery
tools:
  - list_available_sources_v2
  - create_research_question_v2
---
```

---

## Summary

**Key Benefits**:
- ✅ **60-80% fewer tools** in agent context
- ✅ **Better LLM performance** (clearer choices)
- ✅ **Token efficiency** (pay for what's active)
- ✅ **Modular capabilities** (logical units)
- ✅ **User-extensible** (custom skills)
- ✅ **Hot-reloadable** (no restart needed)

**Skill System is Core**: Skills are the foundation of Thoth's agent capabilities, enabling efficient, modular, and user-extensible research assistance.

---

**Last Updated**: February 2026
