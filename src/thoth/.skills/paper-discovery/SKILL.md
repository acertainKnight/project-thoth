---
name: Paper Discovery
description: Find and curate research papers from academic sources. Use when user asks to find papers, search for research, discover articles, or explore a new topic.
tools:
  - list_available_sources
  - create_research_question
  - run_discovery_for_question
  - list_articles
  - search_articles
  - collection_stats
---

# Paper Discovery

Find and curate research papers across academic sources (arXiv, PubMed, Semantic Scholar, OpenAlex, etc.).

## Tools to Use

For discovery tasks, use ONLY these tools:

| Tool | Purpose |
|------|---------|
| `list_available_sources` | See available search sources |
| `create_research_question` | Create a new search query |
| `run_discovery_for_question` | Execute the search |
| `list_articles` | Browse results |
| `search_articles` | Filter/search within results |
| `collection_stats` | Check collection size |

## Quick Discovery (5 min)

For a quick search on a topic:

```
Step 1: Create the query
create_research_question(
  title="User's topic in 1-2 sentences",
  keywords=["keyword1", "keyword2", "keyword3"],
  sources=["semantic_scholar", "openalex"],
  max_papers=25,
  relevance_threshold=0.7
)

Step 2: Run discovery
run_discovery_for_question(question_id="[from step 1]")

Step 3: Review results
list_articles(limit=20, sort_by="relevance")
```

## Source Selection Guide

| Research Area | Recommended Sources |
|---------------|---------------------|
| CS/ML/AI | `arxiv`, `semantic_scholar` |
| Medical/Bio | `pubmed`, `biorxiv` |
| General Science | `openalex`, `crossref` |
| Cross-disciplinary | `semantic_scholar`, `openalex` |

**Default**: Use `semantic_scholar` + `openalex` for broad coverage.

## Keyword Extraction

Extract keywords from user's request:

1. **Core nouns**: Main concepts (e.g., "transformers", "attention")
2. **Technical terms**: Field-specific language (e.g., "multi-head", "self-attention")
3. **Modifiers**: Scope limiters (e.g., "efficient", "sparse", "2024")

**Example**:
- User: "Find papers on efficient attention mechanisms in vision transformers"
- Keywords: `["vision transformer", "efficient attention", "ViT", "sparse attention"]`

## Relevance Threshold Guide

| Threshold | Use When |
|-----------|----------|
| 0.8+ | User wants only highly relevant papers |
| 0.7 | Default - good balance |
| 0.6 | Comprehensive search, broader coverage |
| 0.5 | Exploratory, casting a wide net |

## When to Delegate to Research Analyst

Delegate using `send_message_to_agent` when user needs:
- Deep analysis of discovered papers
- Quality assessment of results
- Literature synthesis across papers
- Citation network exploration

**Example delegation**:
```
send_message_to_agent(
  agent_name="Research Analyst",
  message="Analyze these 10 papers on sparse attention and summarize key approaches: [paper IDs]"
)
```

## Workflow Examples

### Example 1: Specific Topic Search

**User**: "Find recent papers on mixture of experts in LLMs"

```
1. create_research_question(
     title="Mixture of Experts in Large Language Models",
     keywords=["mixture of experts", "MoE", "sparse MoE", "LLM"],
     sources=["arxiv", "semantic_scholar"],
     max_papers=30,
     relevance_threshold=0.75
   )

2. run_discovery_for_question(question_id="...")

3. list_articles(limit=15, sort_by="date")

4. Report: "Found X papers on MoE in LLMs. Top 5: [list]. 
   Would you like me to analyze any of these in depth?"
```

### Example 2: Broad Exploration

**User**: "I want to explore what's happening in protein folding research"

```
1. list_available_sources()  # Show user options

2. create_research_question(
     title="Recent advances in protein structure prediction",
     keywords=["protein folding", "AlphaFold", "protein structure prediction"],
     sources=["biorxiv", "pubmed", "semantic_scholar"],
     max_papers=50,
     relevance_threshold=0.65
   )

3. run_discovery_for_question(question_id="...")

4. collection_stats()  # Show what was found

5. Report summary of results by sub-topic
```

## Error Handling

| Error | Solution |
|-------|----------|
| No results | Lower threshold, broaden keywords, add sources |
| Too many results | Raise threshold, add specific keywords |
| Wrong domain papers | Add negative keywords, change sources |
| Timeout | Reduce sources, lower max_papers |

## Response Template

After discovery, report:

```
## Discovery Results: [Topic]

**Sources searched**: [list]
**Papers found**: [count]
**Relevance threshold**: [value]

### Top Papers:
1. [Title] - [Authors] - [Year]
   Brief: [1 sentence description]

2. ...

### Next Steps:
- Would you like me to analyze any of these papers in depth?
- Should I set this up as a recurring search?
- Want me to adjust the search parameters?
```
