# Multi-Agent Research Assistant Architecture

**Version**: 2.0.0 - Optimized & Streamlined
**Date**: 2025-12-24

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                  THOTH_MAIN_ORCHESTRATOR                    │
│                    (Supervisor/Coordinator)                  │
│                                                              │
│  Capabilities:                                               │
│  • Delegates tasks to specialist agents                      │
│  • Manages research queries and workflow                     │
│  • Synthesizes high-level summaries                          │
│  • Coordinates via agent communication                       │
└────────┬────────────────┬────────────────┬──────────────────┘
         │                │                │
         │ delegates      │ delegates      │ delegates
         ▼                ▼                ▼
┌────────────────┐ ┌───────────────┐ ┌──────────────────┐
│ DISCOVERY      │ │  CITATION     │ │   ANALYSIS       │
│ SCOUT          │ │  ANALYZER     │ │   EXPERT         │
├────────────────┤ ├───────────────┤ ├──────────────────┤
│ Finds papers   │ │ Builds        │ │ Synthesizes      │
│ via arXiv,     │ │ citation      │ │ findings and     │
│ PubMed,        │ │ networks and  │ │ generates        │
│ CrossRef, etc. │ │ relationships │ │ insights         │
└────────────────┘ └───────────────┘ └──────────────────┘
         │                │                │
         └────────────────┴────────────────┘
                          │
                  reports back via
              agent communication +
                 shared memory
```

## Agent Specifications

### 1. THOTH_MAIN_ORCHESTRATOR (Supervisor)

**Role**: Coordinator and task delegator

**Core Capabilities**:
- ✅ **Communication**: send_message_to_agent_async
- ✅ **Memory Management**: core_memory_*, memory_*
- ✅ **Query Management**: create_query, get_query, update_query, list_queries
- ✅ **High-Level Views**: collection_stats, list_articles
- ✅ **Synthesis**: generate_reading_list, generate_research_summary

**Responsibilities**:
- Define research queries and objectives
- Delegate discovery to scout
- Delegate citation analysis to analyzer
- Delegate synthesis to expert
- Generate reading lists and summaries from completed work
- Monitor workflow state

**Does NOT**:
- Search for papers directly (delegates to scout)
- Analyze citations (delegates to analyzer)
- Process PDFs (delegates to specialists)
- Perform deep analysis (delegates to expert)

**Actual Tool Count**: 14 tools ✅

---

### 2. SYSTEM_DISCOVERY_SCOUT (Discovery Specialist)

**Role**: Paper discovery and acquisition

**Core Capabilities**:
- ✅ **Communication**: send_message_to_agent_async
- ✅ **Memory Management**: core_memory_*, memory_*
- ✅ **Search Sources**: create_arxiv_source, create_pubmed_source, create_crossref_source, create_openalex_source, create_biorxiv_source
- ✅ **Discovery**: run_discovery, list_discovery_sources, delete_discovery_source, get_discovery_source
- ✅ **Search**: search_articles, conversation_search
- ✅ **Download**: download_pdf, locate_pdf
- ✅ **Query Support**: create_query, update_query (to refine searches)

**Responsibilities**:
- Configure and manage discovery sources (arXiv, PubMed, etc.)
- Execute discovery runs to find new papers
- Search existing collection for relevant papers
- Locate and download PDFs
- Report findings to orchestrator
- Update active_papers memory block

**Does NOT**:
- Analyze citations (analyzer's job)
- Extract metadata from PDFs (analyzer's job)
- Evaluate or tag papers (expert's job)
- Generate summaries (expert's job)

**Actual Tool Count**: 22 tools ✅

---

### 3. SYSTEM_CITATION_ANALYZER (Citation Specialist)

**Role**: Citation analysis and relationship mapping

**Core Capabilities**:
- ✅ **Communication**: send_message_to_agent_async
- ✅ **Memory Management**: core_memory_*, memory_*
- ✅ **Citation Tools**: extract_citations, format_citations
- ✅ **PDF Analysis**: extract_pdf_metadata, process_pdf, validate_pdf_sources
- ✅ **Relationship Mapping**: find_related_papers
- ✅ **Data Access**: get_article_details, list_articles, search_articles
- ✅ **Export**: export_bibliography

**Responsibilities**:
- Extract citations from papers
- Build citation networks
- Find related papers via citations
- Validate PDF sources
- Extract metadata from PDFs
- Format bibliographies
- Report to orchestrator
- Update citation_network memory block

**Does NOT**:
- Search for new papers (scout's job)
- Evaluate paper quality (expert's job)
- Generate research summaries (expert's job)
- Manage tags (expert's job)

**Actual Tool Count**: 16 tools ✅

---

### 4. SYSTEM_ANALYSIS_EXPERT (Synthesis & Analysis Specialist)

**Role**: Deep analysis and synthesis

**Core Capabilities**:
- ✅ **Communication**: send_message_to_agent_async
- ✅ **Memory Management**: core_memory_*, memory_*
- ✅ **Analysis**: analyze_topic, generate_research_summary
- ✅ **Tag Management**: consolidate_tags, manage_tag_vocabulary, suggest_tags, consolidate_and_retag
- ✅ **Evaluation**: evaluate_article, update_article_metadata
- ✅ **PDF Processing**: batch_process_pdfs, extract_pdf_metadata, process_pdf
- ✅ **Collection Management**: collection_stats, reindex_collection
- ✅ **Data Access**: get_article_details, list_articles, search_articles, find_related_papers
- ✅ **Synthesis**: generate_reading_list

**Responsibilities**:
- Analyze topics across paper collection
- Generate research summaries and insights
- Evaluate paper quality and relevance
- Manage tag taxonomy and vocabulary
- Process PDFs for content extraction
- Update article metadata
- Generate prioritized reading lists
- Report to orchestrator
- Update research_findings memory block

**Does NOT**:
- Search for new papers (scout's job)
- Build citation networks (analyzer's job)
- Format bibliographies (analyzer's job)

**Actual Tool Count**: 23 tools ✅

---

## Communication Patterns

### Pattern 1: Discovery Workflow

```
Orchestrator: "Search arXiv for papers on 'quantum error correction' from 2024"
    ↓ send_message_to_agent_async
Scout: Configures source, runs discovery, finds 15 papers
    ↓ send_message_to_agent_async
Orchestrator: "Found 15 papers. Stored in active_papers."
```

### Pattern 2: Citation Analysis Workflow

```
Orchestrator: "Analyze citations for papers in active_papers"
    ↓ send_message_to_agent_async
Analyzer: Extracts citations, builds network, finds 50 related papers
    ↓ send_message_to_agent_async
Orchestrator: "Citation network complete. 50 related papers identified."
```

### Pattern 3: Synthesis Workflow

```
Orchestrator: "Synthesize findings on quantum error correction"
    ↓ send_message_to_agent_async
Expert: Analyzes papers, identifies themes, generates insights
    ↓ send_message_to_agent_async
Orchestrator: "Key findings: 3 major approaches, 7 open challenges..."
```

### Pattern 4: Parallel Execution

```
Orchestrator sends simultaneously:
    ↓ send_message_to_agent_async → Scout: "Find more papers on topic X"
    ↓ send_message_to_agent_async → Analyzer: "Analyze citations for existing papers"
    ↓ send_message_to_agent_async → Expert: "Evaluate paper quality"

All three work in parallel, report back when complete
```

## Shared Memory Coordination

All agents share 6 memory blocks:

1. **research_context** - Current research topic and questions
2. **active_papers** - Papers currently being processed
3. **citation_network** - Citation relationships and clusters
4. **research_findings** - Synthesized insights and conclusions
5. **workflow_state** - Current workflow stage and progress
6. **message_queue** - Task queue for tracking (optional)

Each agent:
- **Reads** from relevant blocks for context
- **Writes** to their domain-specific block
- **Updates** workflow_state when completing tasks

## Benefits of This Architecture

✅ **Specialized & Focused**: Each agent has only the tools it needs
✅ **Clear Responsibilities**: No overlap or confusion about roles
✅ **Efficient**: Reduced token usage, faster responses
✅ **Scalable**: Easy to add new specialist agents
✅ **Maintainable**: Clear boundaries make debugging easier
✅ **Production-Ready**: Battle-tested patterns from distributed systems

## Token Efficiency

**Before Optimization**: 91 tools total across all agents
- Orchestrator: 25 tools
- Citation Analyzer: 18 tools
- Discovery Scout: 24 tools
- Analysis Expert: 24 tools

**After Optimization**: 75 tools total across all agents ✅
- Orchestrator: 14 tools (44% reduction)
- Citation Analyzer: 16 tools (11% reduction)
- Discovery Scout: 22 tools (8% reduction)
- Analysis Expert: 23 tools (4% reduction)

**Overall Savings**: 18% reduction in tool overhead (16 tools removed)

## Final Tool Allocation (Implemented)

### Orchestrator (14 tools)
✅ Communication: send_message_to_agent_async
✅ Memory: memory_insert, memory_replace, memory_stats, core_memory_append, core_memory_replace
✅ Query Management: create_query, get_query, update_query, list_queries
✅ High-Level Overview: collection_stats, list_articles
✅ Synthesis: generate_reading_list, generate_research_summary

### Discovery Scout (22 tools)
✅ Communication: send_message_to_agent_async
✅ Memory: memory_insert, memory_replace, memory_stats, core_memory_append, core_memory_replace
✅ Search Sources: create_arxiv_source, create_pubmed_source, create_crossref_source, create_openalex_source, create_biorxiv_source
✅ Discovery: run_discovery, list_discovery_sources, get_discovery_source, delete_discovery_source
✅ Search: search_articles, conversation_search
✅ Download: download_pdf, locate_pdf
✅ Query Support: create_query, update_query
✅ Synthesis: generate_reading_list

### Citation Analyzer (16 tools)
✅ Communication: send_message_to_agent_async
✅ Memory: memory_insert, memory_replace, core_memory_append, core_memory_replace
✅ Citation: extract_citations, format_citations
✅ PDF Analysis: process_pdf, extract_pdf_metadata, validate_pdf_sources, locate_pdf
✅ Relationship: find_related_papers
✅ Data Access: get_article_details, list_articles, search_articles
✅ Export: export_bibliography

### Analysis Expert (23 tools)
✅ Communication: send_message_to_agent_async
✅ Memory: memory_insert, memory_replace, core_memory_append, core_memory_replace
✅ Analysis: analyze_topic, generate_research_summary
✅ Tag Management: suggest_tags, consolidate_tags, manage_tag_vocabulary, consolidate_and_retag
✅ Evaluation: evaluate_article, update_article_metadata
✅ PDF Processing: process_pdf, extract_pdf_metadata, batch_process_pdfs
✅ Collection: collection_stats, reindex_collection
✅ Data Access: get_article_details, list_articles, search_articles, find_related_papers
✅ Synthesis: generate_reading_list

---

This architecture follows the **supervisor-worker pattern** with clear delegation, specialized capabilities, and efficient communication - the hallmark of excellent multi-agent systems.
