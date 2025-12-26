# Project Thoth Multi-Agent System - Complete Architecture Explanation

## Overview

This is a **supervisor-worker multi-agent research assistant** built on Letta v0.16.1. The system uses:
- **1 Orchestrator Agent** (supervisor) that coordinates and delegates
- **3 Specialist Agents** (workers) with specialized capabilities
- **6 Shared Memory Blocks** for cross-agent coordination
- **Native Letta Communication** for agent-to-agent messaging

---

## 🧠 SHARED MEMORY BLOCKS (6 Total)

All 4 agents have access to these 6 shared memory blocks for coordination:

### 1. `research_context` (block-810bfa25-da22-46cd-acb0-9040a71dbfc0)

**Purpose**: Stores the high-level research topic, questions, and scope

**Why It Exists**:
- All agents need to understand WHAT they're researching
- Prevents agents from going off-topic
- Provides context for all decisions (paper selection, citation analysis, evaluation)

**Updated By**: Orchestrator (when user defines research topic)

**Read By**: All agents (to stay aligned with research goals)

**Example Content**:
```
Research Topic: Quantum error correction in topological qubits
Research Questions:
- What are the latest approaches to error correction?
- How do topological methods compare to traditional approaches?
Scope: Focus on papers from 2020-2024
```

---

### 2. `active_papers` (block-eda8a3d1-b3ec-4193-91e7-a2ced6c6a367)

**Purpose**: Tracks the queue and status of papers being processed

**Why It Exists**:
- Prevents duplicate work (agents can see what's already being processed)
- Provides visibility into the pipeline (what's queued, in-progress, completed)
- Enables load balancing (agents can pick from queue)

**Updated By**:
- Discovery Scout (adds papers to queue)
- Citation Analyzer (moves papers to "In Analysis")
- Analysis Expert (moves papers to "Completed")

**Read By**: All agents (to check status and avoid duplicates)

**Structure**:
```
Papers Queue: [arxiv:2024.12345, pubmed:98765]
In Analysis: [arxiv:2024.11111]
Completed: [arxiv:2024.00001, arxiv:2024.00002]
```

---

### 3. `citation_network` (block-db4391c0-29e7-4a31-9cc9-23e42ee67dd1)

**Purpose**: Stores citation relationships and key papers

**Why It Exists**:
- Citation analysis is CENTRAL to research (finding influential papers)
- Network structure reveals research communities and key contributions
- Helps discover related work (backward/forward citations)
- Identifies highly-cited seminal papers

**Updated By**: Citation Analyzer (builds citation graph)

**Read By**:
- Discovery Scout (to find related papers via citations)
- Analysis Expert (to understand paper importance)
- Orchestrator (to generate reading lists by citation count)

**Structure**:
```
Citation Relationships:
- arxiv:2024.12345 cites [arxiv:2024.11111, arxiv:2024.22222]
- arxiv:2024.11111 cited_by [arxiv:2024.12345, arxiv:2024.33333]

Key Papers: [arxiv:2024.11111 (cited 50 times)]
```

---

### 4. `research_findings` (block-2f8227c6-5c05-4226-b3e0-378b3ace5ceb)

**Purpose**: Accumulates insights, themes, and conclusions from papers

**Why It Exists**:
- Research is about SYNTHESIS, not just collection
- Prevents re-reading papers (findings are documented)
- Enables cross-paper analysis (identifying themes across papers)
- Builds toward final research summary

**Updated By**: Analysis Expert (after evaluating papers)

**Read By**:
- Orchestrator (for generating summaries)
- Analysis Expert (to build on previous findings)

**Structure**:
```
Key Insights:
- Topological qubits show 10x lower error rates
- Most approaches use Majorana zero modes

Themes:
- Error correction strategies
- Hardware implementations

Conclusions:
- Topological approaches are promising for scalability
```

---

### 5. `workflow_state` (block-84d49cea-25da-4280-b2aa-a5f9f32e4367)

**Purpose**: Tracks the current stage, task, and progress of the research workflow

**Why It Exists**:
- Prevents confusion about what phase we're in (discovery vs analysis vs synthesis)
- Shows who's working on what (avoiding conflicts)
- Tracks progress (for user visibility)
- Enables resumption after interruptions

**Updated By**:
- Orchestrator (changes stages, assigns tasks)
- All agents (update progress on their tasks)

**Read By**: All agents (to understand current phase and coordinate)

**Structure**:
```
Stage: discovery
Current Task: Find papers on quantum error correction
Assigned To: system_discovery_scout
Progress: 45%
Next Steps: [analyze citations, evaluate papers, generate summary]
```

---

### 6. `message_queue` (block-d093079e-5ce1-4270-9588-347f5b80f41b)

**Purpose**: Backup/alternative coordination mechanism using shared memory

**Why It Exists**:
- **Redundancy**: If native communication fails, agents can still coordinate
- **Audit Trail**: Logs all inter-agent messages
- **Debugging**: Can inspect message history
- **Asynchronous Tasks**: Post tasks that agents check periodically

**Updated By**: All agents (when sending messages without native communication)

**Read By**: All agents (polling for pending tasks)

**Structure**:
```
[2025-12-24 12:15:15] orchestrator -> scout
Task: Find papers on quantum computing
Status: pending

[2025-12-24 12:16:30] orchestrator -> scout
Task: Find papers on quantum computing
Status: completed
```

**Note**: With native Letta communication now enabled, this is primarily used as a backup and audit log.

---

## 🤖 AGENT TOOL ALLOCATION

### 1. THOTH_MAIN_ORCHESTRATOR (14 tools)

**Role**: Supervisor/Coordinator - Delegates work, manages workflow, generates high-level outputs

**Tools Explained**:

#### Communication (1 tool)
- `send_message_to_agent_async`: Delegate tasks to specialist agents

#### Memory Management (4 tools)
- `memory_insert`: Add new information to memory blocks
- `memory_replace`: Update existing memory content
- `core_memory_append`: Update agent's own persistent context
- `core_memory_replace`: Replace agent's persistent context

**Why**: Orchestrator needs to coordinate by reading/writing shared state

#### Query Management (4 tools)
- `create_query`: Start new research queries
- `get_query`: Check query details
- `list_queries`: See all active queries
- `update_query`: Refine research questions

**Why**: Orchestrator manages the research lifecycle from start to finish

#### Collection Overview (3 tools)
- `collection_stats`: Get high-level statistics (how many papers, etc.)
- `list_articles`: See what papers exist in collection
- `memory_stats`: Check memory usage

**Why**: Orchestrator needs overview to make delegation decisions

#### Synthesis (2 tools)
- `generate_reading_list`: Create prioritized reading recommendations
- `generate_research_summary`: Generate final research summaries

**Why**: Orchestrator synthesizes outputs from specialists into user-facing deliverables

**Does NOT Have**:
- ❌ Search tools (delegates to scout)
- ❌ Citation tools (delegates to analyzer)
- ❌ PDF processing (delegates to analyzer/expert)
- ❌ Evaluation tools (delegates to expert)

---

### 2. SYSTEM_DISCOVERY_SCOUT (22 tools)

**Role**: Paper Discovery Specialist - Finds papers from multiple sources

**Tools Explained**:

#### Communication (1 tool)
- `send_message_to_agent_async`: Report findings to orchestrator

#### Memory Management (4 tools)
- `memory_insert`, `memory_replace`, `core_memory_append`, `core_memory_replace`

**Why**: Needs to update `active_papers` with discovered papers

#### Discovery Sources (5 tools)
- `create_arxiv_source`: Configure arXiv searches
- `create_pubmed_source`: Configure PubMed searches
- `create_crossref_source`: Configure Crossref searches
- `create_openalex_source`: Configure OpenAlex searches
- `create_biorxiv_source`: Configure bioRxiv searches

**Why**: Multi-source discovery improves coverage (different databases for different fields)

#### Discovery Management (3 tools)
- `run_discovery`: Execute searches across configured sources
- `get_discovery_source`: Check source configuration
- `delete_discovery_source`: Remove unused sources

**Why**: Manage discovery pipeline lifecycle

#### Query Tools (2 tools)
- `create_query`: Can create sub-queries for different search strategies
- `update_query`: Refine queries based on results

**Why**: Scout iteratively refines searches based on what it finds

#### Search & Acquisition (4 tools)
- `search_articles`: Search existing collection (avoid re-downloading)
- `locate_pdf`: Find PDF sources for papers
- `download_pdf`: Acquire PDFs
- `conversation_search`: Natural language search

**Why**: Complete the acquisition pipeline from discovery to PDF download

#### Utility (3 tools)
- `list_discovery_sources`: See all configured sources
- `generate_reading_list`: Can suggest newly-found papers
- `memory_stats`: Monitor memory usage

**Does NOT Have**:
- ❌ Citation tools (analyzer's job)
- ❌ Evaluation tools (expert's job)

---

### 3. SYSTEM_CITATION_ANALYZER (16 tools)

**Role**: Citation Network Builder - Extracts and analyzes citations

**Tools Explained**:

#### Communication (1 tool)
- `send_message_to_agent_async`: Report citation networks to orchestrator

#### Memory Management (2 tools)
- `memory_insert`, `memory_replace`, `core_memory_append`, `core_memory_replace`

**Why**: Updates `citation_network` block with relationships

#### Citation Extraction (3 tools)
- `extract_citations`: Pull citations from PDF content
- `format_citations`: Standardize citation formats
- `export_bibliography`: Generate bibliography files

**Why**: Core citation analysis pipeline

#### PDF Processing (3 tools)
- `process_pdf`: Extract text and metadata from PDFs
- `extract_pdf_metadata`: Get paper metadata (title, authors, year)
- `validate_pdf_sources`: Verify PDF quality and completeness

**Why**: Citations must be extracted from PDFs

#### Network Building (2 tools)
- `find_related_papers`: Discover papers via citations (backward/forward)
- `search_articles`: Find papers in collection by metadata

**Why**: Build citation graph by following references

#### Article Management (4 tools)
- `get_article_details`: Get full paper information
- `list_articles`: See collection contents
- `locate_pdf`: Find PDFs for cited papers

**Why**: Need to look up cited papers and add them to collection

**Does NOT Have**:
- ❌ Search/discovery tools (scout's job)
- ❌ Evaluation tools (expert's job)
- ❌ Tag management (expert's job)

---

### 4. SYSTEM_ANALYSIS_EXPERT (23 tools)

**Role**: Synthesis & Evaluation Specialist - Analyzes quality, extracts insights

**Tools Explained**:

#### Communication (1 tool)
- `send_message_to_agent_async`: Report findings to orchestrator

#### Memory Management (2 tools)
- `memory_insert`, `memory_replace`, `core_memory_append`, `core_memory_replace`

**Why**: Updates `research_findings` with insights

#### Topic Analysis (1 tool)
- `analyze_topic`: Extract key topics and themes from papers

**Why**: Identify research themes across the collection

#### Quality Evaluation (1 tool)
- `evaluate_article`: Assess paper quality, relevance, methodology

**Why**: Prioritize high-quality papers for reading

#### Tag Management (4 tools)
- `suggest_tags`: Auto-tag papers with topics
- `consolidate_tags`: Merge similar tags (e.g., "ML" + "machine learning")
- `consolidate_and_retag`: Consolidate and re-apply tags
- `manage_tag_vocabulary`: Maintain controlled vocabulary

**Why**: Organize collection by topics for easy navigation

#### PDF Processing (2 tools)
- `batch_process_pdfs`: Process multiple PDFs efficiently
- `extract_pdf_metadata`: Get paper metadata

**Why**: Extract information from papers for analysis

#### Collection Management (3 tools)
- `collection_stats`: Monitor collection size and composition
- `reindex_collection`: Rebuild search index after updates
- `update_article_metadata`: Fix or enhance paper metadata

**Why**: Maintain collection quality and searchability

#### Article Lookup (4 tools)
- `get_article_details`: Get full paper information
- `list_articles`: Browse collection
- `search_articles`: Find papers by criteria
- `find_related_papers`: Discover related work

**Why**: Context needed for evaluation and synthesis

#### Synthesis (2 tools)
- `generate_reading_list`: Create prioritized reading lists
- `generate_research_summary`: Generate research summaries

**Why**: Synthesize findings into actionable outputs

#### PDF Processing (1 tool)
- `process_pdf`: Full PDF text extraction

**Why**: Deep analysis requires full text, not just metadata

**Does NOT Have**:
- ❌ Discovery tools (scout's job)
- ❌ Citation extraction (analyzer's job)

---

## 🔄 COMMUNICATION PATTERNS

### How Agents Coordinate

1. **Orchestrator → Scout**: "Find papers on topic X"
2. **Scout** updates `active_papers` with discovered papers
3. **Scout → Orchestrator**: "Found 15 papers"
4. **Orchestrator → Analyzer**: "Build citation network for these papers"
5. **Analyzer** updates `citation_network` with relationships
6. **Analyzer → Orchestrator**: "Citation network complete, 5 key papers identified"
7. **Orchestrator → Expert**: "Evaluate and synthesize these papers"
8. **Expert** updates `research_findings` with insights
9. **Expert → Orchestrator**: "Analysis complete, key themes identified"
10. **Orchestrator**: Generates final reading list and summary for user

### Why This Architecture Works

✅ **Clear Separation of Concerns**: Each agent has a specific job
✅ **No Redundancy**: Orchestrator doesn't duplicate specialist work
✅ **Efficient Tool Usage**: 18% fewer tools than before optimization
✅ **Supervisor-Worker Pattern**: Proven pattern from distributed systems
✅ **Shared Memory Coordination**: All agents can see progress and state
✅ **Native Communication**: Fast agent-to-agent messaging via Letta

---

## 📊 Optimization Results

**Before**: 91 tools total
- Orchestrator: 25 tools (doing search, analysis, everything)
- Citation Analyzer: 18 tools
- Discovery Scout: 24 tools
- Analysis Expert: 24 tools

**After**: 75 tools total
- Orchestrator: 14 tools (44% reduction - now purely coordinates)
- Citation Analyzer: 16 tools (11% reduction)
- Discovery Scout: 22 tools (8% reduction)
- Analysis Expert: 23 tools (4% reduction)

**Key Insight**: The orchestrator had the most bloat (25→14 tools) because it was trying to do everything instead of delegating.

---

## 🎯 System Goals Achieved

1. ✅ **Excellent Research Assistant**: Multi-source discovery, citation analysis, quality evaluation
2. ✅ **Streamlined Architecture**: Specialized agents with minimal tool overlap
3. ✅ **Top-of-the-Line Design**: Supervisor-worker pattern, native communication, shared memory
4. ✅ **Judicious Tool Allocation**: Each agent has only what it needs for its role
5. ✅ **Self-Hosted**: Full Letta capabilities running in Docker
6. ✅ **Production-Ready**: Documented, optimized, and operational
