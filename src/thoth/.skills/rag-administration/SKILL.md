---
name: rag-administration
description: Manage and optimize the RAG (Retrieval-Augmented Generation) system including
  reindexing, search optimization, and custom index creation. Use when user wants
  to improve search quality, reindex their collection, or create specialized indexes.
tools:
- reindex_collection
- optimize_search
- create_custom_index
- search_custom_index
- list_custom_indexes
- view_settings
- update_settings
---

# RAG System Administration

Manage the Retrieval-Augmented Generation (RAG) system that powers knowledge base search and question answering. This is an advanced skill for optimizing search quality and managing the vector database.

## Overview

The RAG system consists of:
1. **Hybrid Search** - Semantic (pgvector) + BM25 (tsvector) with Reciprocal Rank Fusion
2. **Reranking** - LLM-based (zero-cost) or Cohere API for precision re-scoring
3. **Agentic Retrieval** - Self-correcting multi-step pipeline with query expansion, document grading, and hallucination checking (optional, runs on top of hybrid search)
4. **Vector Store** - Stores embeddings for semantic search (PostgreSQL + pgvector)
5. **Indexes** - Organized collections of embeddings
6. **Settings** - Configuration for chunking, embedding models, search, reranking, and agentic retrieval

## Core Capabilities

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `reindex_collection` | Rebuild the entire RAG index | After major changes, new embedding model, or data issues |
| `optimize_search` | Tune search parameters | When search results aren't relevant enough |
| `create_custom_index` | Create specialized topic indexes | For focused research areas needing fast retrieval |
| `search_custom_index` | Search within custom indexes | Query specialized indexes |
| `list_custom_indexes` | View available custom indexes | Check what indexes exist |

## When to Use This Skill

Use RAG administration when user:
- Reports poor search results or irrelevant answers
- Wants to improve search quality
- Has a large collection that needs optimization
- Wants to create focused indexes for specific topics
- Is changing RAG settings and needs to reindex

## Reindexing the Collection

### When to Reindex

Reindex is necessary when:
- Embedding model has changed in settings
- Chunking parameters have changed
- Index appears corrupted
- Significant portion of articles were added/removed
- Search quality has degraded significantly

### Reindex Workflow

```
Step 1: Check current settings
view_settings(section="rag")
→ Shows current embedding model, chunk size, overlap

Step 2: (Optional) Adjust settings if needed
update_settings(
  section="rag",
  updates={
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "embedding_model": "text-embedding-3-small"
  }
)

Step 3: Run reindex
reindex_collection(
  force=true,  # Force even if index exists
  batch_size=100  # Process in batches
)

Step 4: Monitor progress
get_task_status(task_type="reindex")
```

### Reindex Considerations

- **Time**: Full reindex can take 10-60 minutes depending on collection size
- **Cost**: Generates embeddings for all content (API costs if using OpenAI)
- **Availability**: Search works during reindex with old index

## Search Optimization

### Tuning Search Parameters

```
optimize_search(
  min_relevance_score=0.7,  # Filter threshold
  max_results=20,           # Maximum results per query
  hybrid_search=true,       # Combine semantic + keyword
  rerank=true               # Use reranking model
)
```

### Understanding Search Parameters

| Parameter | Effect | Recommended |
|-----------|--------|-------------|
| `min_relevance_score` | Higher = stricter matching | 0.7 for precision, 0.5 for recall |
| `max_results` | Limit retrieved chunks | 10-20 for Q&A, 50+ for synthesis |
| `hybrid_search` | Adds keyword matching | True for technical terms |
| `rerank` | Re-score top results | True for higher quality |

### Diagnosing Search Issues

```
1. Check index status
   list_custom_indexes()
   → See what indexes exist and their status

2. Test search
   search_articles(query="test query")
   → Check if results are relevant

3. Adjust thresholds
   optimize_search(min_relevance_score=0.6)
   → Lower threshold for more results

4. Verify settings
   view_settings(section="rag")
   → Confirm configuration is correct
```

## Custom Indexes

### Use Cases for Custom Indexes

- **Topic Focus**: Index only papers on "machine learning" for faster search
- **Time Range**: Index only recent papers (2023-2024)
- **Author Collection**: Index papers by specific research groups
- **Project Specific**: Index papers for a particular research project

### Creating a Custom Index

```
create_custom_index(
  name="ml_transformers_2024",
  description="Transformer papers from 2024",
  filter_criteria={
    "tags": ["transformers", "attention"],
    "year_min": 2024
  },
  include_full_text=true
)
```

### Managing Custom Indexes

```
# List all indexes
list_custom_indexes()
→ Shows: main, ml_transformers_2024, protein_research

# Search specific index
search_custom_index(
  index_name="ml_transformers_2024",
  query="efficient attention mechanisms"
)
```

## RAG Settings Reference

### Key Settings (via view_settings/update_settings)

```json
{
  "rag": {
    "embeddingModel": "text-embedding-3-small",
    "collectionName": "thoth_papers",
    "chunkSize": 500,
    "chunkOverlap": 50,
    "topK": 5,
    "hybridSearchEnabled": true,
    "hybridSearchWeight": 0.7,
    "rerankingEnabled": true,
    "rerankerProvider": "auto",
    "rerankerModel": "google/gemini-2.5-flash",
    "contextualEnrichmentEnabled": false,
    "adaptiveRoutingEnabled": false,
    "qa": {
      "model": "anthropic/claude-3-5-sonnet",
      "temperature": 0.1
    },
    "agenticRetrieval": {
      "enabled": false,
      "maxRetries": 2,
      "documentGradingEnabled": true,
      "queryExpansionEnabled": true,
      "queryDecompositionEnabled": true,
      "hallucinationCheckEnabled": true,
      "strictHallucinationCheck": false,
      "webSearchFallbackEnabled": false,
      "confidenceThreshold": 0.5
    }
  }
}
```

### Setting Details

| Setting | Purpose | Notes |
|---------|---------|-------|
| `hybridSearchEnabled` | Combine semantic + BM25 search | ~35% better accuracy, no extra cost |
| `hybridSearchWeight` | Balance (0.0=BM25 only, 1.0=semantic only) | 0.7 is recommended |
| `rerankingEnabled` | Re-score results with more powerful model | ~20-30% improvement |
| `rerankerProvider` | `auto` (Cohere if key, else LLM), `cohere`, or `llm` | Auto recommended |
| `contextualEnrichmentEnabled` | Add LLM context per chunk at index time | Expensive, disabled by default |
| `adaptiveRoutingEnabled` | Classify queries for routing | Experimental, disabled by default |

### Agentic Retrieval Settings

| Setting | Purpose | Notes |
|---------|---------|-------|
| `agenticRetrieval.enabled` | Master switch for agentic retrieval | Standard RAG still works when off |
| `agenticRetrieval.maxRetries` | Max retry loops on low confidence | 2 is a good default, higher costs more |
| `agenticRetrieval.documentGradingEnabled` | LLM grades each doc for relevance | Filters out noise from retrieval |
| `agenticRetrieval.queryExpansionEnabled` | Generate semantic query variations | Helps find papers with different terminology |
| `agenticRetrieval.queryDecompositionEnabled` | Break complex queries into sub-questions | Useful for multi-hop questions |
| `agenticRetrieval.hallucinationCheckEnabled` | Verify answer is grounded in sources | Catches unsupported claims |
| `agenticRetrieval.strictHallucinationCheck` | Strict = every claim directly stated in sources | Lenient mode allows reasonable inferences |
| `agenticRetrieval.confidenceThreshold` | Minimum relevance score for document grading | Lower = more documents pass, higher = stricter |

### Changing Embedding Models

**Warning**: Changing embedding model requires full reindex!

```
Step 1: Update setting
update_settings(
  section="rag",
  updates={"embedding_model": "text-embedding-3-large"}
)

Step 2: Force reindex
reindex_collection(force=true)
```

### Chunking Strategy

| Collection Type | chunk_size | chunk_overlap | Reasoning |
|-----------------|------------|---------------|-----------|
| Short papers | 500 | 100 | Smaller chunks for precision |
| Long papers | 1500 | 300 | Larger context per chunk |
| Mixed | 1000 | 200 | Balanced default |
| Dense technical | 800 | 200 | More overlap for context |

## Workflow Examples

### Example 1: Improve Search Quality

**User**: "My search results aren't very relevant"

```
1. Check current configuration
   view_settings(section="rag")
   → Current: min_relevance=0.8, hybrid=false

2. Optimize parameters
   optimize_search(
     min_relevance_score=0.6,
     hybrid_search=true,
     rerank=true
   )

3. Test search
   search_articles(query="user's topic")
   → Better results

4. Response:
   "I've adjusted your search settings:
   - Lowered relevance threshold (0.8 → 0.6) for more results
   - Enabled hybrid search for better keyword matching
   - Enabled reranking for higher quality top results

   Try your search again and let me know if it's improved."
```

### Example 2: Full Reindex After Settings Change

**User**: "I changed the embedding model, do I need to reindex?"

```
1. Check settings
   view_settings(section="rag")
   → embedding_model: text-embedding-3-large

2. Confirm reindex is needed
   "Yes, changing the embedding model requires a full reindex.
   This will regenerate embeddings for all articles.

   Current collection: ~500 papers
   Estimated time: 15-20 minutes

   Proceed with reindex?"

3. Execute reindex
   reindex_collection(
     force=true,
     batch_size=50
   )

4. Monitor
   get_task_status(task_type="reindex")
   → Progress: 250/500 articles processed

5. Complete
   "Reindex complete! All 500 articles now use text-embedding-3-large.
   Search should now work with the new embeddings."
```

### Example 3: Create Research Topic Index

**User**: "I want a focused index just for my reinforcement learning papers"

```
1. Create custom index
   create_custom_index(
     name="reinforcement_learning",
     description="Papers on RL, policy gradients, and decision making",
     filter_criteria={
       "tags": ["reinforcement-learning", "rl", "policy-gradient", "q-learning"]
     }
   )
   → Index created with 47 papers

2. Confirm
   "Created 'reinforcement_learning' index with 47 papers.

   To search this focused index:
   - Use search_custom_index with index_name='reinforcement_learning'

   This will give faster, more focused results for RL queries."
```

## Agentic Retrieval Management

### Enabling/Disabling

```
# Enable agentic retrieval
update_settings(
  section="rag",
  updates={
    "agenticRetrieval": {"enabled": true}
  }
)

# Disable just hallucination checking (if it's too aggressive)
update_settings(
  section="rag",
  updates={
    "agenticRetrieval": {"hallucinationCheckEnabled": false}
  }
)
```

### Tuning Agentic Retrieval

If agentic retrieval answers are slow but accurate, reduce retries:
```
update_settings(
  section="rag",
  updates={"agenticRetrieval": {"maxRetries": 1}}
)
```

If too many irrelevant documents are getting through grading, raise the threshold:
```
update_settings(
  section="rag",
  updates={"agenticRetrieval": {"confidenceThreshold": 0.7}}
)
```

If query expansion is pulling in off-topic papers, disable it:
```
update_settings(
  section="rag",
  updates={"agenticRetrieval": {"queryExpansionEnabled": false}}
)
```

### When to Recommend Agentic Retrieval

Suggest enabling it when users:
- Ask complex synthesis questions and get shallow answers
- Complain about missing relevant papers in results
- Need multi-hop reasoning across their collection

Suggest disabling or tweaking it when users:
- Report answers are too slow for their workflow
- Notice the hallucination checker is flagging reasonable inferences
- Have a small collection where standard RAG already works well

## Best Practices

### Performance
- Use batch_size of 50-100 for reindexing large collections
- Create custom indexes for frequently searched topics
- Enable reranking only if quality is more important than speed

### Quality
- Use hybrid search for technical domains with specific terminology
- Lower relevance threshold (0.5-0.6) if missing relevant results
- Increase chunk overlap if context is being lost

### Maintenance
- Reindex after adding 100+ new articles
- Review custom indexes periodically for relevance
- Monitor search quality with user feedback

## Troubleshooting

### No Results Found
```
1. Check index exists: list_custom_indexes()
2. Lower threshold: optimize_search(min_relevance_score=0.4)
3. Verify articles exist: collection_stats()
4. Force reindex if corrupted: reindex_collection(force=true)
```

### Slow Search
```
1. Check index size: list_custom_indexes()
2. Create focused index for common queries
3. Reduce max_results in optimize_search
4. Disable reranking for speed
```

### Inconsistent Results
```
1. Check for duplicate articles in collection
2. Verify embedding model hasn't changed without reindex
3. Force clean reindex: reindex_collection(force=true)
```
