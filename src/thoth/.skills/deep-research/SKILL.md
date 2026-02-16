---
name: deep-research
description: Conduct deep analysis of research papers, synthesize literature, and
  generate comprehensive reviews. Use when user needs thorough paper analysis, literature
  reviews, or cross-paper synthesis.
tools:
- read_full_article
- unload_article
- answer_research_question
- explore_citation_network
- compare_articles
- find_related_papers
- evaluate_article
- get_citation_context
- search_articles
- get_article_details
- search_external_knowledge
- list_knowledge_collections
---

# Deep Research & Literature Synthesis

Conduct thorough analysis of research papers, synthesize findings across multiple sources, and generate comprehensive literature reviews. Leverage both research papers and external knowledge (textbooks, background material) for complete understanding.

## Tools to Use

For deep research, use these analysis tools:

| Tool | Purpose |
|------|---------|
| `read_full_article` | **Read complete article content for deep learning** |
| `unload_article` | **Free article memory slot (max 3 articles)** |
| `answer_research_question` | Multi-source synthesis with citations (supports scope filtering) |
| `explore_citation_network` | Citation graph analysis |
| `compare_articles` | Side-by-side comparison |
| `find_related_papers` | Semantic similarity |
| `evaluate_article` | Quality scoring |
| `get_citation_context` | Citation relationship context |
| `search_articles` | Find papers in knowledge base |
| `get_article_details` | Get article metadata and preview |
| `search_external_knowledge` | Search textbooks and background material |
| `list_knowledge_collections` | Show available external knowledge collections |

**Note**: These are analysis-heavy tools. For simpler queries, use the `knowledge-base-qa` skill instead.

## Article Memory Limit

**CRITICAL**: You can load a maximum of **3 articles** at a time into your working memory.

- Use `read_full_article(article_identifier="...", agent_id="your_agent_id")` to load articles
- Each load consumes one memory slot (status displayed after loading)
- When memory is full (3/3), use `unload_article` before loading new articles
- Use `unload_article(article_identifier="...", agent_id="your_agent_id")` to free slots

**Deep research workflow**: When analyzing many papers, strategically load and unload articles:
1. Load 3 key papers initially
2. Analyze and extract insights
3. Unload papers you're done with
4. Load new papers to fill knowledge gaps
5. Repeat until synthesis is complete

## Iterative Learning Pattern

**Key Principle**: You can read, learn from an article, and keep reading to build deep understanding. With the 3-article memory limit, manage your loaded articles strategically. Start with foundational knowledge from textbooks before diving into research papers.

### The Learning Loop

```
0. FOUNDATION (if needed): Get background understanding
   list_knowledge_collections()
   search_external_knowledge(
     query="foundational concept",
     collection_name="Relevant Textbook Collection"
   )
   → Build theoretical foundation first

1. DISCOVER: Search for relevant papers
   search_articles(query="topic")

2. READ DEEPLY: Load full article content (max 3 at a time)
   read_full_article(
     article_identifier="paper title or DOI",
     agent_id="your_agent_id"
   )
   → Read the entire article, not just previews
   → Status shows: "Article Memory: 2/3 slots used"

3. ANALYZE: Extract key insights
   - What are the main contributions?
   - What methods were used?
   - What are the limitations?

4. IDENTIFY GAPS: What questions remain?
   - What concepts need clarification? → search_external_knowledge
   - What related work should you read? → find_related_papers

5. MANAGE MEMORY: Free slots if needed
   If you've loaded 3 articles and need to read another:
   unload_article(
     article_identifier="title or DOI to unload",
     agent_id="your_agent_id"
   )

6. REPEAT: Read more articles to fill gaps
   find_related_papers(article_id="...")
   read_full_article(
     article_identifier="next paper",
     agent_id="your_agent_id"
   )

7. SYNTHESIZE: Combine insights across papers
   answer_research_question(
     question="synthesis query",
     scope="all"  # Include both papers and external knowledge
   )
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

**Memory tip**: Load articles you'll actively analyze. Use `unload_article` to swap out papers you're done with when you need to load new ones.

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
   read_full_article(
     article_identifier="[paper title or DOI]",
     agent_id="your_agent_id"
   )
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

   # If memory is full (3/3), unload one first
   unload_article(
     article_identifier="[article to remove]",
     agent_id="your_agent_id"
   )

   # Then load new article
   read_full_article(
     article_identifier="[related paper]",
     agent_id="your_agent_id"
   )
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
1. read_full_article(
     article_identifier="Attention Is All You Need",
     agent_id="your_agent_id"
   )
   → Read the complete paper content
   → Status: "Article Memory: 1/3 slots used"

2. [Read and understand the paper thoroughly]
   - Note key contributions, methodology, results

3. explore_citation_network(
     article_id="[paper ID]",
     direction="cited_by",
     depth=1
   )

4. If concepts are unclear, read related papers:
   # Load up to 2 more articles (3 total max)
   read_full_article(
     article_identifier="[related paper on attention]",
     agent_id="your_agent_id"
   )
   → Status: "Article Memory: 2/3 slots used"
   → Keep learning until you understand

   # If you need a 4th article, unload one first
   unload_article(
     article_identifier="[first paper]",
     agent_id="your_agent_id"
   )
   read_full_article(
     article_identifier="[4th paper]",
     agent_id="your_agent_id"
   )

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
