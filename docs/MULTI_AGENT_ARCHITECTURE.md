# Multi-Agent Research System Architecture

**Version**: 3.0.0 - Specialized Agent Architecture
**Date**: 2025-12-25

## Vision

A specialized multi-agent research system where each agent excels at one specific domain of the research workflow. Users interact with a single orchestrator that delegates tasks to domain experts.

## Design Principles

1. **Single Entry Point**: Users interact only with the orchestrator
2. **Clear Specialization**: Each agent handles one functional domain
3. **No Overlap**: Each tool assigned to exactly one agent
4. **Expert Agents**: Agents become highly specialized in their domain
5. **Minimal Orchestrator**: Orchestrator only delegates, doesn't perform specialized work

## Architecture Overview

```
                        USER (via mobile/ADE)
                              │
                              ▼
        ┌─────────────────────────────────────────────┐
        │     THOTH MAIN ORCHESTRATOR (Agent 1)       │
        │                                             │
        │  • 0 MCP tools (delegation only)            │
        │  • Determines which expert to delegate to   │
        │  • Coordinates multi-step workflows         │
        │  • Returns results to user                  │
        └──┬──────┬──────┬──────┬──────┬──────┬──────┘
           │      │      │      │      │      │
      ┌────┘      │      │      │      │      └────┐
      │           │      │      │      │           │
      ▼           ▼      ▼      ▼      ▼           ▼
┌──────────┐ ┌────────┐ ┌────┐ ┌────┐ ┌──────┐ ┌──────┐
│Discovery │ │Document│ │Cite│ │Rsrch│ │Organ│ │System│
│Scout     │ │Library │ │Spec│ │Anlst│ │Curator│ │Maint │
│          │ │        │ │    │ │    │ │      │ │      │
│9 tools   │ │13 tools│ │4   │ │3   │ │9     │ │8     │
└──────────┘ └────────┘ └────┘ └────┘ └──────┘ └──────┘
```

**Total**: 7 agents, 46 MCP tools, zero overlap

## Agent Specifications

### 1. Thoth Main Orchestrator (Entry Point)
**Role**: User-facing coordinator and task delegator
**Current ID**: `agent-10418b8d-37a5-4923-8f70-69ccc58d66ff`

**Responsibilities**:
- Accept user requests via mobile/ADE
- Determine which specialized agent to delegate to
- Coordinate multi-step workflows across agents
- Return synthesized results to user

**Tools** (Minimal - Delegation Only):
- `send_message` (built-in Letta tool for agent-to-agent communication)
- `archival_memory_search` (built-in Letta tool)
- `archival_memory_insert` (built-in Letta tool)
- `conversation_search` (built-in Letta tool)

**MCP Tools**: **NONE (0 tools)** - This agent ONLY delegates

**Delegation Path**: User → Orchestrator → Specialist → Orchestrator → User

---

### 2. Discovery Scout Agent
**Role**: Research paper discovery across academic sources
**Current ID**: `agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64`

**Responsibilities**:
- Configure and manage discovery sources (arXiv, bioRxiv, CrossRef, OpenAlex, PubMed)
- Run discovery queries across sources
- Find papers matching research criteria
- Report discovered papers to orchestrator

**MCP Tools** (9 tools):
- `create_arxiv_source`
- `create_biorxiv_source`
- `create_crossref_source`
- `create_openalex_source`
- `create_pubmed_source`
- `list_discovery_sources`
- `get_discovery_source`
- `delete_discovery_source`
- `run_discovery`

---

### 3. Document Librarian Agent ⭐ NEW
**Role**: PDF acquisition and article database management

**Responsibilities**:
- Download and locate PDFs for discovered papers
- Process PDFs and extract metadata
- Manage article database (CRUD operations)
- Validate PDF sources
- Evaluate article quality and relevance

**MCP Tools** (13 tools):

**PDF Management** (6 tools):
- `download_pdf`
- `locate_pdf`
- `process_pdf`
- `batch_process_pdfs`
- `extract_pdf_metadata`
- `validate_pdf_sources`

**Article Management** (7 tools):
- `list_articles`
- `search_articles`
- `get_article_details`
- `update_article_metadata`
- `delete_article`
- `evaluate_article`
- `export_article_data`

---

### 4. Citation Specialist Agent
**Role**: Citation extraction and bibliography management
**Current ID**: `agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5`

**Responsibilities**:
- Extract citations from papers
- Format citations in various styles
- Generate bibliographies
- Find related papers through citation networks

**MCP Tools** (4 tools):
- `extract_citations`
- `format_citations`
- `export_bibliography`
- `find_related_papers`

---

### 5. Research Analyst Agent
**Role**: Deep analysis and research synthesis
**Current ID**: `agent-8a4183a6-fffc-4082-b40b-aab29727a3ab` (was system_analysis_expert)

**Responsibilities**:
- Analyze research topics across papers
- Generate structured reading lists
- Create research summaries and literature reviews
- Identify trends and gaps in research

**MCP Tools** (3 tools):
- `analyze_topic`
- `generate_reading_list`
- `generate_research_summary`

---

### 6. Organization Curator Agent ⭐ NEW
**Role**: Query management and taxonomy organization

**Responsibilities**:
- Manage saved queries (CRUD operations)
- Organize research topics and tags
- Consolidate and manage tag vocabulary
- Suggest appropriate tags for papers

**MCP Tools** (9 tools):

**Query Management** (5 tools):
- `create_query`
- `get_query`
- `list_queries`
- `update_query`
- `delete_query`

**Organization & Tagging** (4 tools):
- `consolidate_tags`
- `consolidate_and_retag`
- `suggest_tags`
- `manage_tag_vocabulary`

---

### 7. System Maintenance Agent ⭐ NEW
**Role**: Collection health, backups, and system integration

**Responsibilities**:
- Monitor collection statistics
- Perform backups and restoration
- Reindex collection for search optimization
- Monitor memory health
- Sync with external tools (Obsidian)

**MCP Tools** (8 tools):

**Collection Management** (5 tools):
- `collection_stats`
- `backup_collection`
- `reindex_collection`
- `optimize_search`
- `create_custom_index`

**Memory & System** (2 tools):
- `memory_stats`
- `memory_health_check`

**Integration** (1 tool):
- `sync_with_obsidian`

---

## Tool Assignment Summary

| Agent | MCP Tools | Built-in Tools | Total |
|-------|-----------|----------------|-------|
| Thoth Main Orchestrator | 0 | 4 (delegation) | 4 |
| Discovery Scout | 9 | 4 (standard) | 13 |
| Document Librarian | 13 | 4 (standard) | 17 |
| Citation Specialist | 4 | 4 (standard) | 8 |
| Research Analyst | 3 | 4 (standard) | 7 |
| Organization Curator | 9 | 4 (standard) | 13 |
| System Maintenance | 8 | 4 (standard) | 12 |
| **Total** | **46** | **28** | **74** |

**Key**: All 46 MCP tools assigned with ZERO overlap.

---

## Example Workflows

### Workflow 1: Discover and Download Papers on Topic

**User Request**: "Find recent papers on quantum computing and download the PDFs"

**Delegation Flow**:
```
User → Orchestrator
  ├─→ Discovery Scout: "Run discovery for 'quantum computing' papers from 2024"
  │   └─→ Returns: [list of 50 papers with metadata]
  │
  └─→ Document Librarian: "Download PDFs for these 50 papers"
      └─→ Returns: {45 PDFs downloaded, 5 failed with URLs}

Orchestrator → User: "Found 50 papers, successfully downloaded 45 PDFs"
```

### Workflow 2: Analyze Research Topic

**User Request**: "Generate a literature review on CRISPR applications"

**Delegation Flow**:
```
User → Orchestrator
  ├─→ Organization Curator: "Get all queries tagged 'CRISPR'"
  │   └─→ Returns: [3 saved queries]
  │
  ├─→ Document Librarian: "Search articles matching these queries"
  │   └─→ Returns: [120 relevant articles]
  │
  ├─→ Research Analyst: "Generate research summary for these 120 articles"
  │   └─→ Returns: {summary with trends, gaps, key findings}
  │
  └─→ Citation Specialist: "Format bibliography for cited papers"
      └─→ Returns: [formatted bibliography]

Orchestrator → User: [Complete literature review with citations]
```

### Workflow 3: Organize Existing Collection

**User Request**: "Clean up my tags and optimize the collection"

**Delegation Flow**:
```
User → Orchestrator
  ├─→ Organization Curator: "Consolidate duplicate tags across collection"
  │   └─→ Returns: {merged 15 tag variations into 5 canonical tags}
  │
  ├─→ System Maintenance: "Reindex collection and optimize search"
  │   └─→ Returns: {reindexed 500 articles, created 3 new indexes}
  │
  └─→ System Maintenance: "Run collection stats"
      └─→ Returns: {500 articles, 45 queries, 20 tags, 450 PDFs}

Orchestrator → User: "Collection optimized: 500 articles, 20 tags, search 3x faster"
```

### Workflow 4: Citation Network Analysis

**User Request**: "Find papers related to this seminal paper through citations"

**Delegation Flow**:
```
User → Orchestrator
  ├─→ Citation Specialist: "Find papers citing and cited by this paper"
  │   └─→ Returns: [200 related papers via citation network]
  │
  ├─→ Document Librarian: "Get details for these 200 papers"
  │   └─→ Returns: [full metadata for all 200]
  │
  ├─→ Research Analyst: "Generate reading list prioritized by relevance"
  │   └─→ Returns: [ranked reading list with summaries]
  │
  └─→ Organization Curator: "Suggest tags for this citation network"
      └─→ Returns: {suggested tags: "citation-network", "computational-biology", "methods"}

Orchestrator → User: [Reading list with 200 papers, ranked and tagged]
```

---

## Implementation Plan

### Phase 1: Agent Creation (Current Status)
**Status**: 4 agents exist but need reconfiguration

**Existing Agents**:
- ✅ `thoth_main_orchestrator` (needs tool removal)
- ✅ `system_analysis_expert` (can become Research Analyst)
- ✅ `system_discovery_scout` (can become Discovery Scout)
- ✅ `system_citation_analyzer` (can become Citation Specialist)

**New Agents Needed**:
- ❌ Document Librarian (new)
- ❌ Organization Curator (new)
- ❌ System Maintenance (new)

### Phase 2: Tool Reassignment
1. Remove ALL MCP tools from orchestrator
2. Reassign tools from existing agents to match new architecture
3. Assign tools to new agents

### Phase 3: Testing
1. Test each specialized agent individually
2. Test orchestrator delegation to each agent
3. Test multi-agent workflows (examples above)
4. Verify mobile access continues working

### Phase 4: Documentation
1. Update agent descriptions with new roles
2. Document delegation patterns for orchestrator
3. Create user guide for common workflows

---

## Technical Notes

### Agent Communication
- Agents communicate via Letta's built-in `send_message` tool
- Message queue system already exists (RabbitMQ in docker-compose.yml)
- Orchestrator sends task + context, specialist returns results

### Tool Discovery
- All agents can see their assigned tools via Letta's tool system
- MCP tools registered in PostgreSQL `tools` table
- Agent-tool relationships in `tools_agents` junction table

### Memory Management
- Each agent has isolated memory (Letta's memory system)
- Agents can share context via archival memory or message passing
- System Maintenance agent monitors global memory health

### Mobile Access
- All interactions go through orchestrator via Letta ADE
- URL: https://app.letta.com connected to https://lambda-workstation.tail71634c.ts.net
- User sees single orchestrator, doesn't know about sub-agents
- Delegation happens transparently behind the scenes

---

## Comparison: Old vs New Architecture

### Old Architecture (v2.0.0)
```
thoth_main_orchestrator (14 tools including MCP)
  ├─ Query tools ❌ Should delegate
  ├─ Synthesis tools ❌ Should delegate
  └─ Collection stats ❌ Should delegate

system_analysis_expert (23 MCP tools)
  ├─ Too broad ❌ Multiple domains
  └─ Overlaps with other agents ❌

system_discovery_scout (22 MCP tools)
  ├─ Discovery tools ✅ Good
  └─ PDF tools ❌ Should be separate
  └─ Article tools ❌ Should be separate
  └─ Query tools ❌ Should be separate

system_citation_analyzer (16 MCP tools)
  ├─ Citation tools ✅ Good
  └─ PDF tools ⚠️ Some overlap
  └─ Article tools ❌ Overlaps
```

**Problems**:
- Orchestrator does specialized work (has MCP tools)
- Tool overlap (e.g., `generate_reading_list` on 3 agents)
- Agents have too many different responsibilities
- Unclear delegation paths

### New Architecture (v3.0.0)
```
Thoth Main Orchestrator (0 MCP tools)
  └─ ONLY delegates ✅

Discovery Scout (9 tools) ✅ Clear domain
Document Librarian (13 tools) ✅ Clear domain
Citation Specialist (4 tools) ✅ Clear domain
Research Analyst (3 tools) ✅ Clear domain
Organization Curator (9 tools) ✅ Clear domain
System Maintenance (8 tools) ✅ Clear domain
```

**Benefits**:
- ✅ Zero tool overlap
- ✅ Clear specialization per agent
- ✅ Orchestrator only delegates
- ✅ Each agent becomes expert in its domain
- ✅ Single user entry point maintained
- ✅ Scales to 7 agents (from 4)

---

## Next Steps

1. **Create 3 new agents** using Letta API:
   - Document Librarian
   - Organization Curator
   - System Maintenance

2. **Reconfigure 4 existing agents**:
   - Remove all MCP tools from orchestrator
   - Reassign tools from system_analysis_expert → Research Analyst
   - Reassign tools from system_discovery_scout → Discovery Scout
   - Reassign tools from system_citation_analyzer → Citation Specialist

3. **Test complete workflow** using mobile access at https://app.letta.com

4. **Document delegation patterns** for orchestrator
