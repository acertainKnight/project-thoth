---
name: Research Project Coordination
description: Manage large-scale research projects requiring multiple phases of discovery, analysis, and synthesis. Use when user is working on survey papers, thesis chapters, or comprehensive research projects.
tools:
  - create_research_question
  - run_discovery_for_question
  - list_research_questions
  - list_articles
  - search_articles
  - collection_stats
  - compare_articles
  - answer_research_question
  - explore_citation_network
---

# Research Project Coordination

Coordinate multi-phase research projects that require systematic discovery, collection building, and synthesis over time.

## Tools to Use

This skill uses tools from multiple categories:

**Discovery Phase**:
- `create_research_question` - Create search queries
- `run_discovery_for_question` - Execute searches
- `list_available_sources` - Source selection

**Collection Phase**:
- `list_articles` - Browse papers
- `search_articles` - Filter collection
- `collection_stats` - Track progress

**Analysis Phase** (delegate to Research Analyst):
- `compare_articles` - Cross-paper analysis
- `answer_research_question` - Comprehensive synthesis with citations
- `explore_citation_network` - Citation mapping

**Management**:
- `list_skills` - Load additional skills as needed
- `load_skill` - Get specialized guidance

## Project Types

### Survey Paper
Multi-topic comprehensive literature review covering an entire field.

### Thesis Chapter
Focused deep dive into a specific research question with background.

### Grant Proposal Background
Evidence gathering to support research direction claims.

### Competitive Analysis
Systematic comparison of approaches/methods in a space.

## Project Phases

### Phase 1: Scoping & Planning

```
1. Define project scope
   - Main research question
   - Sub-topics to cover
   - Expected output (survey, thesis, etc.)
   - Timeline constraints

2. Create project structure
   Project: [name]
   ├── Topic 1: [subtopic]
   │   └── Queries: [list]
   ├── Topic 2: [subtopic]
   │   └── Queries: [list]
   └── Topic N: [subtopic]
       └── Queries: [list]

3. Set collection targets
   - Papers per topic: [count]
   - Quality threshold: [value]
   - Time range: [years]
```

### Phase 2: Systematic Discovery

For each sub-topic:

```
1. Create targeted query
   create_research_question(
     title="[topic] for [project name]",
     keywords=["specific", "terms"],
     sources=["appropriate", "sources"],
     max_papers=50
   )

2. Execute discovery
   run_discovery_for_question(question_id="...")

3. Track progress
   collection_stats()

4. Adjust if needed
   - Too few results → broaden keywords
   - Wrong focus → refine terms
```

### Phase 3: Collection Curation

```
1. Review discovered papers
   list_articles(limit=100, sort_by="relevance")

2. Identify key papers per topic
   search_articles(query="[topic keyword]", limit=20)

3. Check coverage gaps
   - Missing seminal papers?
   - Recent work included?
   - All approaches represented?

4. Fill gaps with targeted searches
```

### Phase 4: Analysis & Synthesis

Delegate to Research Analyst:

```
send_message_to_agent(
  agent_name="Research Analyst",
  message="For the [project name] project, please:

  1. Analyze papers in [topic] category
  2. Generate synthesis for [section name]
  3. Identify key themes and research gaps

  Papers to analyze: [list of IDs]
  Output format: [structured summary / comparison table / narrative]"
)
```

### Phase 5: Integration

Combine analyses into final output:

```
1. Gather section summaries from Research Analyst
2. Identify cross-cutting themes
3. Highlight research gaps
4. Suggest future directions
```

## Progress Tracking

Maintain project status in conversation:

```
## Project: [Name]
Status: [Phase X of 5]
Started: [date]

### Topics Progress:
| Topic | Queries | Papers | Analyzed | Status |
|-------|---------|--------|----------|--------|
| Topic 1 | 2 | 45 | 20 | ✓ Complete |
| Topic 2 | 3 | 62 | 0 | In Progress |
| Topic 3 | 1 | 0 | 0 | Pending |

### Next Steps:
1. [immediate action]
2. [upcoming action]
```

## Workflow Examples

### Example 1: Survey Paper on LLM Efficiency

**User**: "I'm writing a survey paper on efficient large language models"

```
Phase 1: Scoping
"Let's plan your survey. I'll break this into sub-topics:

1. **Architectural Efficiency**
   - Sparse attention mechanisms
   - State space models
   - Mixture of experts

2. **Training Efficiency**
   - Parameter-efficient fine-tuning
   - Distillation methods
   - Curriculum learning

3. **Inference Optimization**
   - Quantization
   - Pruning
   - Speculative decoding

4. **Hardware-Aware Design**
   - Memory optimization
   - Hardware co-design

For each topic, I'll create discovery queries targeting ~30-50 papers.
Total target: ~150-200 papers across topics.

Shall I proceed with this structure?"

Phase 2: Discovery (for each topic)
create_research_question(
  title="Sparse Attention for LLM Efficiency Survey",
  keywords=["sparse attention", "efficient transformer", "linear attention"],
  sources=["arxiv", "semantic_scholar"],
  max_papers=50
)
run_discovery_for_question(...)

Phase 3: Track progress
"Discovery progress update:

| Topic | Papers Found | Status |
|-------|--------------|--------|
| Sparse Attention | 47 | ✓ |
| State Space Models | 38 | ✓ |
| MoE | 52 | ✓ |
| PEFT | 61 | In Progress |
| ... | ... | ... |

Total: 198 papers. Ready to begin analysis?"

Phase 4: Analysis (delegated)
send_message_to_agent(
  agent_name="Research Analyst",
  message="Survey analysis request for LLM Efficiency Survey:

  Section: Sparse Attention Mechanisms
  Papers: [list of 47 paper IDs]

  Please provide:
  1. Taxonomy of approaches
  2. Comparative analysis table
  3. Evolution timeline (2020-2024)
  4. Key research gaps
  5. Section summary (~500 words)"
)
```

### Example 2: Thesis Background Chapter

**User**: "Help me build the background chapter for my thesis on multimodal learning"

```
Phase 1: Scoping
"For a thesis background, we need:

1. **Foundational Work** (pre-2020)
   - Early multimodal approaches
   - Key theoretical frameworks

2. **Core Methods** (2020-2023)
   - Vision-language models
   - Audio-visual learning
   - Cross-modal attention

3. **Recent Advances** (2023-present)
   - Unified architectures
   - Scaling studies
   - Emergent capabilities

4. **Your Specific Focus Area**
   - [user's thesis topic]

I'll prioritize seminal papers and highly-cited work.
Target: ~80-100 papers total."

Phase 2-4: [Execute systematically]

Phase 5: Integration
"Background chapter structure ready:

## 2. Background and Related Work

### 2.1 Foundations of Multimodal Learning
[synthesis from foundational papers]

### 2.2 Vision-Language Models
[synthesis from VLM papers]

### 2.3 Cross-Modal Attention Mechanisms
[synthesis from attention papers]

### 2.4 Recent Advances and Open Challenges
[synthesis from recent papers]

### 2.5 Summary and Research Gap
[leading to your contribution]

Each section has been drafted with proper citations.
Would you like me to refine any section?"
```

## Project Templates

### Survey Paper Template
```
Sections: 6-8 topic areas
Papers per section: 20-40
Total papers: 150-300
Timeline: 4-8 weeks
Analysis depth: Comprehensive taxonomy + comparison
```

### Thesis Background Template
```
Sections: 4-5 areas
Papers per section: 15-25
Total papers: 60-100
Timeline: 2-4 weeks
Analysis depth: Historical context + state of art
```

### Grant Proposal Template
```
Sections: 2-3 key areas
Papers per section: 10-15
Total papers: 30-50
Timeline: 1-2 weeks
Analysis depth: Evidence for claims + gap identification
```

## Coordination Notes

- **Checkpoints**: Review with user after each phase
- **Iteration**: Expect 2-3 refinement cycles
- **Delegation**: Use Research Analyst for deep analysis
- **Documentation**: Keep project state updated
- **Flexibility**: Adapt structure based on findings
