---
name: RAG System Administration
description: Manage and optimize the RAG (Retrieval-Augmented Generation) system including reindexing, search optimization, and custom index creation. Use when user wants to improve search quality, reindex their collection, or create specialized indexes.
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
1. **Vector Store** - Stores embeddings for semantic search
2. **Indexes** - Organized collections of embeddings
3. **Settings** - Configuration for chunking, embedding models, and search parameters

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
    "embedding_model": "text-embedding-3-small",
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "max_chunks_per_doc": 50,
    "min_chunk_size": 100,
    "collection_name": "thoth_articles"
  },
  "search": {
    "default_limit": 10,
    "min_relevance": 0.7,
    "hybrid_search": true,
    "rerank": false
  }
}
```

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
