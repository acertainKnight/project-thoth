---
name: knowledge-base-qa
description: Answer questions using your existing research collection and external knowledge. Use when user
  asks questions about papers they have, wants summaries, or seeks insights from their
  knowledge base.
tools:
- answer_research_question
- agentic_research_question
- read_full_article
- unload_article
- search_articles
- get_article_details
- collection_stats
- search_external_knowledge
- list_knowledge_collections
---

# Knowledge Base Q&A

Answer research questions using articles in your collection and external knowledge sources (textbooks, lecture notes, background material). Synthesize information across papers with proper citations.

## Knowledge Sources

Your knowledge base includes:
1. **Research papers** - Papers you've processed and analyzed
2. **External knowledge** - Textbooks, lecture notes, background material organized in collections

Use the `scope` parameter in Q&A tools to control which sources are searched.

## Tools to Use

For knowledge base queries, use these tools:

| Tool | Purpose |
|------|---------|
| `answer_research_question` | Quick Q&A — single-pass hybrid search (supports scope filtering) |
| `agentic_research_question` | Deep Q&A — multi-step pipeline with query expansion, document grading, hallucination checking (supports scope filtering) |
| `read_full_article` | Read complete article content for deep understanding |
| `unload_article` | Free article memory slot (max 3 articles) |
| `search_articles` | Find specific papers (supports topic filtering) |
| `get_article_details` | Get paper metadata and preview |
| `collection_stats` | Check what's in the collection |
| `search_external_knowledge` | Search textbooks and background material |
| `list_knowledge_collections` | Show available external knowledge collections |

## Scope Filtering

Both Q&A tools now support a `scope` parameter to control which knowledge sources are searched:

- `scope="all"` (default) - Search both research papers and external knowledge
- `scope="papers_only"` - Only search research papers
- `scope="external"` - Only search external knowledge (textbooks, notes)
- `scope="collection:Name"` - Search specific external knowledge collection

**Example**:
```
# Get foundational understanding from textbooks
answer_research_question(
  question="What are Markov Decision Processes?",
  scope="collection:RL Textbooks"
)

# Get latest research findings
answer_research_question(
  question="Recent advances in MDPs",
  scope="papers_only"
)

# Search everything for comprehensive answer
answer_research_question(
  question="How are MDPs used in modern RL?",
  scope="all"
)
```

### Choosing Between Standard and Agentic Q&A

Use `answer_research_question` for:
- Factual lookups ("What dataset did paper X use?")
- Simple questions with obvious keywords
- Quick answers where speed matters

Use `agentic_research_question` for:
- Comparison questions ("How does X compare to Y?")
- Synthesis across many papers ("What are the main approaches to Z?")
- Multi-hop reasoning ("How has the field's view on X changed over time?")
- Questions where a quick search might miss relevant papers

If agentic retrieval is disabled in settings, `agentic_research_question` falls back to standard RAG automatically—so it's safe to call either way.

The agentic tool takes longer (8-30 seconds vs <5 seconds) because it runs multiple retrieval rounds, grades documents, and verifies the answer. The user sees real-time progress updates in the UI ("Expanding search terms...", "Evaluating relevance...", etc.) so they know it's working.

### Understanding Retrieval Assessment (CRAG)

When you use `agentic_research_question`, the tool returns a **Retrieval Assessment** that tells you how well your knowledge base covered the topic:

- **CORRECT** (confidence >= 0.7): Strong coverage, use the answer as-is
- **AMBIGUOUS** (confidence 0.4-0.7): Partial coverage, supplement with web search
- **INCORRECT** (confidence < 0.4): Weak coverage, rely primarily on web search

**When you see AMBIGUOUS assessment:**
1. The tool will provide an "Action Required" section with a suggested web search query
2. Call `web_search` with that query (or refine it)
3. Synthesize the local answer with web results
4. Cite both local sources and web sources in your response
5. If you find relevant papers online, offer to download them with `download_pdf`

**When you see INCORRECT assessment:**
1. The tool will provide an "Action Required" section with a suggested web search query
2. Call `web_search` to find relevant sources
3. Base your answer primarily on web results
4. Mention that your knowledge base didn't have strong coverage
5. Offer to download any useful papers found online to expand the knowledge base

**When you see CORRECT assessment:**
- Use the answer directly - no action required
- The knowledge base had strong coverage

This Corrective Retrieval Augmented Generation (CRAG) workflow ensures you always provide the best answer, whether from local knowledge, web search, or both.

### Article Memory Limit

**IMPORTANT**: You can load a maximum of **3 articles** at a time into your working memory.

- Use `read_full_article` to load article content (requires your `agent_id`)
- Each load consumes one memory slot (displayed after loading)
- When memory is full (3/3), you must use `unload_article` before loading new articles
- Use `unload_article` to free slots when done with an article

**Why this limit?** Deep article reading loads substantial content. The 3-article limit ensures you can work with multiple papers while maintaining context window efficiency.

**Workflow tip**: If you need to reference more than 3 papers, use `unload_article` to swap articles in and out of memory as needed.

### Reading Full Articles

When you need more than a quick answer, **read the full article**:

```
read_full_article(
  article_identifier="paper title or DOI",
  agent_id="your_agent_id"
)
```

This returns the complete markdown content, allowing you to:
- Understand methodology details
- Find specific information not in summaries
- Learn deeply about a topic
- Read multiple papers to build comprehensive knowledge

**Iterative Learning**: You can read one article, identify questions, then read more articles to fill knowledge gaps. Keep reading until you fully understand the topic.

**Memory Management**: When you've loaded 3 articles and need to read another, use `unload_article` first:

```
unload_article(
  article_identifier="title or DOI of article to unload",
  agent_id="your_agent_id"
)
```

## Quick Answer Workflow

```
Step 1: Determine which knowledge source to use
- Foundational concepts → scope="external"
- Recent research → scope="papers_only"
- Comprehensive answer → scope="all"

Step 2: Search for relevant information
answer_research_question(
  question="User's question",
  max_sources=10,
  min_relevance=0.7,
  include_citations=true,
  scope="all"  # or papers_only/external/collection:Name
)

Step 3: If more context needed from external sources
search_external_knowledge(
  query="specific concept",
  collection_name="Relevant Collection"
)

Step 4: Synthesize and cite properly
```

## Deep Answer Workflow (Agentic)

```
Step 1: Ask the agentic pipeline
agentic_research_question(
  question="User's complex question",
  max_sources=10,
  max_retries=2
)
→ Pipeline automatically expands query, grades docs, checks hallucination
→ Returns answer with confidence score and source list

Step 2: If the user wants more depth on specific papers
read_full_article(article_identifier="paper from results")

Step 3: Synthesize additional context and cite
```

The agentic pipeline handles query expansion and document grading internally, so you don't need to manually search with multiple phrasings. It also returns a confidence score and flags if any claims couldn't be verified against sources.

## Question Types & Approaches

### Factual Questions
"What dataset did the GPT-4 paper use?"

```
search_articles(query="GPT-4", limit=5)
get_article_details(article_id="[matched paper]")
→ Direct answer with citation
```

### Synthesis Questions
"What are the main approaches to efficient attention?"

```
answer_research_question(
  question="Main approaches to efficient attention mechanisms",
  max_sources=15,
  min_relevance=0.75
)
→ Synthesized answer across multiple papers
```

### Comparison Questions
"How does FlashAttention compare to standard attention?"

```
search_articles(query="FlashAttention", limit=5)
search_articles(query="standard attention benchmark", limit=5)
→ Delegate to Research Analyst for deep comparison
```

## Citation Format

Always cite sources in responses:

```
According to [Author et al., Year], the main finding was...

Multiple studies have shown X [1, 2, 3]:
1. Smith et al. (2023) - "Paper Title"
2. Jones et al. (2024) - "Paper Title"
3. Brown et al. (2024) - "Paper Title"
```

## When to Delegate to Research Analyst

Delegate when user needs:
- Deep reading of specific papers
- Multi-paper comparison
- Quality assessment
- Citation network analysis
- Literature review generation

**Example**:
```
send_message_to_agent(
  agent_name="Research Analyst",
  message="Compare these 3 papers on attention efficiency: [IDs]. Focus on methodology and results."
)
```

## Response Quality Checklist

Before responding, ensure:
- [ ] Question is directly answered
- [ ] Sources are cited with author/year
- [ ] Confidence level is indicated if uncertain
- [ ] Offer to go deeper if synthesis was high-level

## Handling Insufficient Data

If collection doesn't have relevant papers:

```
"I searched your collection but didn't find papers specifically on [topic].

Current collection stats: [collection_stats output]

Options:
1. I can run a discovery search to find papers on this topic
2. You can add papers manually
3. I can answer based on general knowledge (without citations)

Would you like me to search for papers on [topic]?"
```

## Workflow Examples

### Example 1: Direct Question

**User**: "What's the computational complexity of the Mamba architecture?"

```
1. search_articles(query="Mamba architecture complexity", limit=5)
2. get_article_details(article_id="[best match]")
3. Extract complexity analysis from paper
4. Report: "According to [Gu & Dao, 2023], Mamba achieves
   O(N) complexity compared to O(N²) for standard attention..."
```

### Example 2: Synthesis Question

**User**: "Summarize the key challenges in RLHF"

```
1. answer_research_question(
     question="Key challenges and limitations of RLHF",
     max_sources=10
   )
2. If answer is comprehensive → return synthesis
3. If more depth needed → delegate to Research Analyst
```

### Example 3: "What do we have on X?"

**User**: "What papers do we have on vision-language models?"

```
1. search_articles(query="vision-language model", limit=20)
2. collection_stats()
3. Report: "You have X papers related to vision-language models:

   Recent (2024): [list]
   Key papers: [list by citation count]

   Topics covered: [clustering if available]

   Would you like me to summarize findings across these papers?"
```

## Response Template

```
## Answer: [Question Summary]

[Direct answer paragraph with inline citations]

**Key sources**:
- [Author et al., Year]: [Key finding from this paper]
- [Author et al., Year]: [Key finding from this paper]

**Confidence**: [High/Medium/Low] - based on [X] relevant papers

**Want more detail?**
- I can analyze specific papers in depth
- I can explore the citation network
- I can compare methodologies across papers
```
