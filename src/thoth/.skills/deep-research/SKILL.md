---
name: Deep Research & Literature Synthesis
description: Conduct deep analysis of research papers, synthesize literature, and generate comprehensive reviews. Use when user needs thorough paper analysis, literature reviews, or cross-paper synthesis.
tools:
  - answer_research_question
  - explore_citation_network
  - compare_articles
  - extract_article_insights
  - get_article_full_content
  - find_related_papers
  - analyze_topic
  - generate_research_summary
  - evaluate_article
  - get_citation_context
  - search_articles
  - find_articles_by_authors
---

# Deep Research & Literature Synthesis

Conduct thorough analysis of research papers, synthesize findings across multiple sources, and generate comprehensive literature reviews.

## Tools to Use

For deep research, use these analysis tools:

| Tool | Purpose |
|------|---------|
| `answer_research_question` | Multi-source synthesis |
| `explore_citation_network` | Citation graph analysis |
| `compare_articles` | Side-by-side comparison |
| `extract_article_insights` | Deep paper analysis |
| `get_article_full_content` | Full text access |
| `find_related_papers` | Semantic similarity |
| `analyze_topic` | Topic-level analysis |
| `generate_research_summary` | Literature review |
| `evaluate_article` | Quality scoring |

**Note**: These are analysis-heavy tools. For simpler queries, use the `knowledge-base-qa` skill instead.

## When to Use This Skill

Use deep research when user asks for:
- "Analyze this paper in depth"
- "Compare these papers"
- "Write a literature review on X"
- "What are the research gaps in X?"
- "Synthesize findings across papers on X"
- "How has research on X evolved?"

## Deep Analysis Workflow

### Single Paper Deep Dive

```
1. Get full content
   get_article_full_content(article_id="[paper ID]")

2. Extract structured insights
   extract_article_insights(
     article_id="[paper ID]",
     aspects=["methodology", "findings", "limitations", "contributions"]
   )

3. Explore citation context
   explore_citation_network(
     article_id="[paper ID]",
     direction="both",  # cited_by and references
     depth=1
   )

4. Assess quality
   evaluate_article(
     article_id="[paper ID]",
     criteria=["novelty", "methodology", "impact"]
   )
```

### Multi-Paper Comparison

```
1. Identify papers to compare
   search_articles(query="[topic]", limit=10)

2. Run comparison
   compare_articles(
     article_ids=["paper1", "paper2", "paper3"],
     comparison_aspects=["methodology", "results", "datasets", "limitations"]
   )

3. Find additional related work
   find_related_papers(article_id="[seed paper]", limit=10)
```

### Literature Synthesis

```
1. Gather relevant papers
   answer_research_question(
     question="[topic question]",
     max_sources=20,
     min_relevance=0.7
   )

2. Analyze topic structure
   analyze_topic(
     topic="[research area]",
     include_trends=true,
     time_range="5 years"
   )

3. Generate comprehensive summary
   generate_research_summary(
     topic="[area]",
     paper_ids=["list of relevant IDs"],
     summary_type="literature_review"
   )
```

## Analysis Aspects

When analyzing papers, consider these dimensions:

### Methodology Assessment
- Research design (experimental, theoretical, empirical)
- Data sources and quality
- Evaluation metrics
- Reproducibility indicators

### Contribution Analysis
- Novel techniques/methods introduced
- Improvements over prior work
- Practical applications
- Theoretical insights

### Limitations & Gaps
- Acknowledged limitations
- Implicit assumptions
- Missing comparisons
- Future work directions

### Impact Assessment
- Citation count/trajectory
- Adoption in subsequent work
- Industry applications
- Community recognition

## Delegation Pattern

The Orchestrator should delegate to Research Analyst when:
- User explicitly requests deep analysis
- Question requires reading full papers
- Comparison across 3+ papers needed
- Literature review requested

**Delegation message format**:
```
send_message_to_agent(
  agent_name="Research Analyst",
  message="Deep analysis request: [specific task]
  
  Papers to analyze: [list of IDs or titles]
  
  Focus areas: [methodology/results/limitations/etc]
  
  Output needed: [comparison table/summary/review/etc]"
)
```

## Workflow Examples

### Example 1: Single Paper Deep Analysis

**User**: "Analyze the 'Attention Is All You Need' paper in depth"

```
1. search_articles(query="Attention Is All You Need Transformer")
   → Find paper ID

2. get_article_full_content(article_id="[paper ID]")

3. extract_article_insights(
     article_id="[paper ID]",
     aspects=["architecture", "methodology", "results", "impact"]
   )

4. explore_citation_network(
     article_id="[paper ID]",
     direction="cited_by",
     depth=1
   )

5. Response:
   "## Deep Analysis: Attention Is All You Need
   
   **Core Contribution**: [transformer architecture description]
   
   **Methodology**:
   - Self-attention mechanism
   - Positional encoding approach
   - Training procedure
   
   **Key Results**:
   - BLEU score improvements
   - Training efficiency gains
   
   **Impact Analysis**:
   - [X] citations
   - Spawned: BERT, GPT, T5, etc.
   
   **Limitations acknowledged**:
   - [list from paper]
   
   **Research lineage**:
   - Builds on: [references]
   - Influenced: [top citing papers]"
```

### Example 2: Comparative Analysis

**User**: "Compare GPT-4, Claude, and Llama 3 architectures"

```
1. search_articles(query="GPT-4 architecture", limit=3)
   search_articles(query="Claude architecture Anthropic", limit=3)
   search_articles(query="Llama 3 architecture", limit=3)

2. compare_articles(
     article_ids=[paper IDs for each],
     comparison_aspects=[
       "model_size",
       "training_data",
       "architecture_innovations",
       "benchmark_performance",
       "safety_measures"
     ]
   )

3. Response:
   "## Comparative Analysis: GPT-4 vs Claude vs Llama 3
   
   | Aspect | GPT-4 | Claude | Llama 3 |
   |--------|-------|--------|---------|
   | Size | ... | ... | ... |
   | Training | ... | ... | ... |
   | Key innovation | ... | ... | ... |
   
   **Key Differences**:
   1. [difference 1]
   2. [difference 2]
   
   **Shared Approaches**:
   - [commonality]
   
   **Notable gaps in literature**:
   - [what's not well documented]"
```

### Example 3: Literature Review

**User**: "Give me a literature review on efficient transformers"

```
1. answer_research_question(
     question="What are the main approaches to making transformers more efficient?",
     max_sources=25
   )

2. analyze_topic(
     topic="efficient transformers",
     include_trends=true,
     time_range="3 years"
   )

3. generate_research_summary(
     topic="efficient transformer architectures",
     summary_type="literature_review"
   )

4. Response:
   "## Literature Review: Efficient Transformers
   
   ### 1. Introduction
   [Context and importance]
   
   ### 2. Taxonomy of Approaches
   
   **2.1 Attention Approximation**
   - Linear attention [cite]
   - Sparse attention [cite]
   - Low-rank approximation [cite]
   
   **2.2 Architecture Modifications**
   - State space models [cite]
   - Mixture of experts [cite]
   
   **2.3 Implementation Optimizations**
   - FlashAttention [cite]
   - Memory-efficient attention [cite]
   
   ### 3. Comparative Analysis
   [Table comparing approaches]
   
   ### 4. Research Gaps
   - [Gap 1]
   - [Gap 2]
   
   ### 5. Future Directions
   [Emerging trends]
   
   ### References
   [Full citation list]"
```

## Quality Standards

For deep research output:

1. **Accuracy**: Every claim backed by citation
2. **Comprehensiveness**: Cover major approaches/papers
3. **Structure**: Clear organization with sections
4. **Balance**: Present multiple viewpoints fairly
5. **Currency**: Include recent work (last 2 years)
6. **Gaps**: Identify what's missing in the literature
