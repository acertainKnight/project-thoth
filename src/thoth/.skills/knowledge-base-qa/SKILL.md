---
name: knowledge-base-qa
description: Answer questions using your existing research collection. Use when user
  asks questions about papers they have, wants summaries, or seeks insights from their
  knowledge base.
tools:
- answer_research_question
- read_full_article
- search_articles
- get_article_details
- collection_stats
---

# Knowledge Base Q&A

Answer research questions using articles already in your collection. Synthesize information across papers with proper citations.

## Tools to Use

For knowledge base queries, use these tools:

| Tool | Purpose |
|------|---------|
| `answer_research_question` | Primary Q&A with synthesis |
| `read_full_article` | Read complete article content for deep understanding |
| `search_articles` | Find specific papers (supports topic filtering) |
| `get_article_details` | Get paper metadata and preview |
| `collection_stats` | Check what's in the collection |

### Reading Full Articles

When you need more than a quick answer, **read the full article**:

```
read_full_article(article_identifier="paper title or DOI")
```

This returns the complete markdown content, allowing you to:
- Understand methodology details
- Find specific information not in summaries
- Learn deeply about a topic
- Read multiple papers to build comprehensive knowledge

**Iterative Learning**: You can read one article, identify questions, then read more articles to fill knowledge gaps. Keep reading until you fully understand the topic.

## Quick Answer Workflow

```
Step 1: Search for relevant papers
answer_research_question(
  question="User's question",
  max_sources=10,
  min_relevance=0.7,
  include_citations=true
)

Step 2: If more context needed
get_article_details(article_id="[specific paper]")

Step 3: Synthesize and cite properly
```

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
