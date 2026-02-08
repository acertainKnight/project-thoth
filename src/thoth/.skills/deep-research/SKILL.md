---
name: Deep Research & Literature Synthesis
description: Conduct deep analysis of research papers, synthesize literature, and generate comprehensive reviews. Use when user needs thorough paper analysis, literature reviews, or cross-paper synthesis.
tools:
  - read_full_article
  - answer_research_question
  - explore_citation_network
  - compare_articles
  - find_related_papers
  - evaluate_article
  - get_citation_context
  - search_articles
  - get_article_details
---

# Deep Research & Literature Synthesis

Conduct thorough analysis of research papers, synthesize findings across multiple sources, and generate comprehensive literature reviews.

## Tools to Use

For deep research, use these analysis tools:

| Tool | Purpose |
|------|---------|
| `read_full_article` | **Read complete article content for deep learning** |
| `answer_research_question` | Multi-source synthesis with citations |
| `explore_citation_network` | Citation graph analysis |
| `compare_articles` | Side-by-side comparison |
| `find_related_papers` | Semantic similarity |
| `evaluate_article` | Quality scoring |
| `get_citation_context` | Citation relationship context |
| `search_articles` | Find papers in knowledge base |
| `get_article_details` | Get article metadata and preview |

**Note**: These are analysis-heavy tools. For simpler queries, use the `knowledge-base-qa` skill instead.

## Iterative Learning Pattern

**Key Principle**: You can read, learn from an article, and keep reading to build deep understanding.

### The Learning Loop

```
1. DISCOVER: Search for relevant papers
   search_articles(query="topic")

2. READ DEEPLY: Load full article content
   read_full_article(article_identifier="paper title or DOI")
   → Read the entire article, not just previews

3. ANALYZE: Extract key insights
   - What are the main contributions?
   - What methods were used?
   - What are the limitations?

4. IDENTIFY GAPS: What questions remain?
   - What concepts need clarification?
   - What related work should you read?

5. REPEAT: Read more articles to fill gaps
   find_related_papers(article_id="...")
   read_full_article(article_identifier="next paper")

6. SYNTHESIZE: Combine insights across papers
   answer_research_question(question="synthesis query")
```

### When to Read Full Articles

Use `read_full_article` when:
- You need to understand methodology details
- The preview (from `get_article_details`) isn't enough
- You're comparing specific techniques across papers
- You're writing a literature review
- You want to learn a topic deeply

Use `get_article_details` when:
- You just need metadata (authors, date, journal)
- You're doing initial screening of papers
- A quick preview is sufficient

### External Content

For web articles, blog posts, and documentation **outside** your knowledge base:
- Use Letta's built-in `fetch_webpage` tool to read external URLs
- This complements `read_full_article` which is for your indexed papers

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
1. Read the full article content
   read_full_article(article_identifier="[paper title or DOI]")
   → Returns complete markdown content for deep reading

2. Explore citation context
   explore_citation_network(
     article_id="[paper ID]",
     direction="both",  # cited_by and references
     depth=1
   )

3. Assess quality
   evaluate_article(
     article_id="[paper ID]",
     criteria=["novelty", "methodology", "impact"]
   )

4. If you have questions, read related papers
   find_related_papers(article_id="[paper ID]")
   read_full_article(article_identifier="[related paper]")
   → Keep reading until you understand the topic
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
1. Answer research question with synthesis
   answer_research_question(
     question="[topic question]",
     max_sources=20,
     min_relevance=0.7
   )
   → Returns comprehensive answer with citations from knowledge base

2. Explore citation relationships
   explore_citation_network(
     article_id="[key paper ID]",
     direction="both",
     depth=2
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
1. read_full_article(article_identifier="Attention Is All You Need")
   → Read the complete paper content

2. [Read and understand the paper thoroughly]
   - Note key contributions, methodology, results

3. explore_citation_network(
     article_id="[paper ID]",
     direction="cited_by",
     depth=1
   )

4. If concepts are unclear, read related papers:
   read_full_article(article_identifier="[related paper on attention]")
   → Keep learning until you understand

5. evaluate_article(
     article_id="[paper ID]",
     criteria=["novelty", "methodology", "impact"]
   )

6. Response:
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

   **Research lineage**:
   - Builds on: [references from citation network]
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
   → Returns comprehensive synthesis with citations

2. search_articles(query="efficient transformers", limit=20)
   → Find key papers in the knowledge base

3. For key papers, explore citations:
   explore_citation_network(article_id="[key paper]", direction="both")

4. Response:
   "## Literature Review: Efficient Transformers

   ### 1. Introduction
   [Context and importance from answer_research_question]

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

   ### 3. Citation Analysis
   [Key papers and their relationships from explore_citation_network]

   ### 4. Research Gaps
   [Identified from synthesis]

   ### References
   [Citations from answer_research_question]"
```

## Quality Standards

For deep research output:

1. **Accuracy**: Every claim backed by citation
2. **Comprehensiveness**: Cover major approaches/papers
3. **Structure**: Clear organization with sections
4. **Balance**: Present multiple viewpoints fairly
5. **Currency**: Include recent work (last 2 years)
6. **Gaps**: Identify what's missing in the literature
