# RAG System Architecture

## Executive Summary

Thoth's RAG (Retrieval-Augmented Generation) system provides **hybrid search** over research papers, combining semantic vector search (pgvector) with lexical full-text search (PostgreSQL tsvector/BM25) and an optional reranking layer for maximum retrieval quality. The system uses PostgreSQL as a unified backend, LangChain for orchestration, and OpenRouter for embeddings and LLM inference.

**Key Design Characteristics:**
- **Hybrid retrieval**: Semantic (vector) + lexical (BM25) search fused with Reciprocal Rank Fusion (RRF)
- **Reranking pipeline**: LLM-based (zero-cost) or Cohere API for precision re-scoring
- **Document-aware chunking**: Two-stage markdown header + recursive splitting
- **100% database-backed**: No file system dependencies, all data in PostgreSQL
- **Dual embedding options**: Local sentence-transformers OR OpenRouter cloud embeddings
- **Token-aware chunking**: Uses tiktoken for accurate token counting
- **Async-first**: Built for concurrent operations with connection pooling
- **Hot-reloadable**: Config changes without restart
- **Automatic migrations**: Schema upgrades applied seamlessly on startup

**Performance Profile:**
- Index build: ~500-1000 tokens/sec (local), ~200-500 tokens/sec (cloud)
- Query latency: <200ms for hybrid search + reranking, <100ms vector-only
- Memory: ~2GB with sentence-transformers, <100MB with cloud embeddings
- Scalability: Tested up to 100K document chunks

---

## Architecture Overview

### 1. System Layers

```
┌─────────────────────────────────────────────────────────────┐
│ API Layer: FastAPI Endpoints + MCP Tools                    │
│ - /search, /index, /query                                   │
│ - advanced_rag_tools.py (12 tools)                          │
└────────────┬────────────────────────────────────────────────┘
             │
┌────────────┴────────────────────────────────────────────────┐
│ RAG Manager (rag_manager.py)                                │
│ - Document processing pipeline                              │
│ - Hybrid query orchestration                                │
│ - RetrievalQA chain coordination                            │
│ - Reranking integration                                     │
└────────────┬─────────────────┬──────────────────────────────┘
             │                 │
     ┌───────┴──────┐   ┌─────┴───────────────────────┐
     │              │   │                             │
┌────▼────────┐  ┌──▼───▼──────────┐  ┌─────────────▼──────┐
│ Embedding   │  │ Vector Store   │  │ LLM (OpenRouter)   │
│ Manager     │  │ Manager        │  │ - QA generation    │
│ (embeddings)│  │ (vector_store) │  │ - LLM Reranking    │
│             │  │                │  │ - Summarization    │
│ - sentence- │  │ - PostgreSQL   │  └────────────────────┘
│   transformers│ │ - pgvector    │
│ - OpenRouter│  │ - asyncpg      │
│   embeddings│  │ - HNSW index   │
└─────────────┘  └───────┬────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ Hybrid Search Layer                                         │
│ ┌──────────────────┐  ┌───────────────┐  ┌───────────────┐ │
│ │ Semantic Search  │  │ BM25/FTS      │  │ Reranker      │ │
│ │ (pgvector <=>)   │  │ (tsvector)    │  │ (LLM/Cohere)  │ │
│ └────────┬─────────┘  └───────┬───────┘  └───────┬───────┘ │
│          └────────┬───────────┘                   │         │
│                   ▼                               │         │
│          ┌────────────────┐                       │         │
│          │ RRF Fusion     │───────────────────────┘         │
│          │ (score merge)  │                                 │
│          └────────────────┘                                 │
└─────────────────────────────────────────────────────────────┘
                         │
                  ┌──────▼──────┐
                  │ PostgreSQL  │
                  │ + pgvector  │
                  │ + tsvector  │
                  └─────────────┘
```

### 2. Data Flow

**Indexing Pipeline:**
```
Markdown Document (OCR'd PDF)
    ↓
[RAG Manager] → index_paper()
    ↓
[Document-Aware Chunking] → Two-stage splitter
    ├─ Stage 1: MarkdownHeaderTextSplitter (respect headers)
    ├─ Stage 2: RecursiveCharacterTextSplitter (size enforcement)
    ├─ chunk_size: 500-2000 tokens (configurable)
    ├─ chunk_overlap: 50-200 tokens
    └─ Preserves: headers, section breaks, paragraphs
    ↓
[Embedding Generation] → EmbeddingManager
    ├─ Local: sentence-transformers/all-MiniLM-L6-v2 (384 dims)
    └─ Cloud: OpenRouter API → text-embedding-3-small (1536 dims)
    ↓
[Vector + FTS Storage] → VectorStoreManager
    ├─ Store embeddings in document_chunks.embedding
    ├─ Auto-populate search_vector (tsvector, generated column)
    ├─ HNSW index for fast vector search
    ├─ GIN index for fast full-text search
    └─ Metadata: paper_id, chunk_index, source, created_at
```

**Query Pipeline (Hybrid Search + Reranking):**
```
User Query (natural language)
    ↓
[RAG Manager] → search_async()
    ↓
[Parallel Retrieval]
    ├─ [Semantic Search] → pgvector cosine similarity → top_k candidates
    └─ [BM25 Search] → tsvector full-text ranking → top_k candidates
    ↓
[Reciprocal Rank Fusion (RRF)]
    ├─ Merge semantic + lexical results
    ├─ Score: Σ 1/(k + rank_i) for each document across both lists
    └─ k=60 (standard RRF constant)
    ↓
[Reranking] (if enabled)
    ├─ LLM Reranker (default, zero-cost): Score via OpenRouter LLM
    └─ Cohere Reranker (optional): Dedicated reranking API
    ↓
[Context Assembly] → Merge chunks + metadata
    ├─ De-duplicate overlapping content
    ├─ Preserve document structure
    └─ Add paper metadata (title, authors, year)
    ↓
[RetrievalQA Chain] → LangChain orchestration
    ├─ Prompt: "Answer based on context..."
    ├─ LLM: OpenRouter (configurable)
    └─ Context window: 4K-8K tokens (configurable)
    ↓
Generated Answer + Source Citations
```

---

## Core Components

### 1. RAG Manager (rag_manager.py)

**Purpose:** Central orchestrator for all RAG operations including hybrid search, reranking, and document indexing.

**Key Methods:**
```python
async def search_async(
    query: str,
    top_k: int = 5,
    filter_metadata: dict | None = None,
) -> list[Document]:
    """
    Hybrid search: semantic + BM25 + reranking.

    Process:
    1. Run semantic search (pgvector cosine similarity)
    2. Run BM25 search (tsvector full-text ranking)
    3. Merge results with Reciprocal Rank Fusion
    4. Rerank with LLM or Cohere (if enabled)
    5. Return top_k results
    """

async def index_paper_by_id(paper_id: UUID) -> int:
    """
    Index a paper from the database.

    Process:
    1. Fetch markdown content from database
    2. Strip images for clean text
    3. Two-stage chunk (markdown headers → recursive)
    4. Generate embeddings
    5. Store chunks with metadata
    """

async def index_markdown_file(file_path: Path) -> int:
    """
    Index a markdown file directly.

    Process:
    1. Read markdown content
    2. Look up paper_id by title
    3. Two-stage chunk and embed
    4. Store in document_chunks table
    """
```

**Configuration (settings.json `rag` section):**
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
    "contextualEnrichmentModel": "google/gemini-2.5-flash",
    "adaptiveRoutingEnabled": false,
    "adaptiveRoutingModel": "google/gemini-2.5-flash",
    "qa": {
      "model": "anthropic/claude-3-5-sonnet",
      "temperature": 0.1
    }
  }
}
```

**Feature Defaults and Rationale:**

| Feature | Default | Why |
|---------|---------|-----|
| **Hybrid Search** | Enabled | ~35% better retrieval accuracy with no extra API costs |
| **Reranking** | Enabled | ~20-30% additional improvement; LLM reranker is zero-cost |
| **Contextual Enrichment** | Disabled | Requires LLM call per chunk during indexing (expensive) |
| **Adaptive Routing** | Disabled | Experimental; adds latency, requires tuning |

---

### 2. Hybrid Search Engine

**Why Hybrid Search?**

Semantic search alone misses exact keyword matches (e.g., "BERT-base" vs "transformer model"). BM25 alone misses semantic meaning (e.g., "attention mechanism" vs "self-attention"). Combining both catches what either would miss individually.

**Implementation:**

```python
# search_backends.py - BM25 Search via PostgreSQL tsvector
class BM25SearchBackend:
    """Full-text search using PostgreSQL tsvector with ts_rank_cd scoring."""

    async def search(self, query: str, k: int = 10) -> list[Document]:
        """
        Execute BM25 search using plainto_tsquery.

        Uses generated column: search_vector tsvector
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED

        Scoring: ts_rank_cd (cover density ranking)
        Index: GIN index on search_vector
        """
```

**Reciprocal Rank Fusion (RRF):**

```python
def reciprocal_rank_fusion(
    semantic_results: list[Document],
    bm25_results: list[Document],
    k: int = 60,
    semantic_weight: float = 0.7,
) -> list[Document]:
    """
    Merge results from multiple retrieval methods.

    Formula: score(d) = Σ weight_i / (k + rank_i(d))

    Args:
        k: Smoothing constant (60 is standard)
        semantic_weight: Weight for semantic results (0.7 = 70% semantic)
    """
```

**Why RRF over Linear Combination?**
- Rank-based: No need to normalize scores across different systems
- Fault-tolerant: Handles missing documents gracefully
- Tunable: `semantic_weight` controls the balance
- Industry-proven: Used by Elasticsearch, Pinecone, etc.

---

### 3. Reranking Layer

**Purpose:** Re-score retrieved documents with a more powerful model for higher precision.

**Architecture:**

```
Initial Retrieval (fast, broad)
    → 20-50 candidates from hybrid search
        ↓
Reranking (slow, precise)
    → Score each candidate against query
    → Return top_k (5-10) highest scoring
```

**Two Reranking Strategies:**

1. **LLM Reranker (default, zero-cost):**
   ```python
   class LLMReranker(BaseReranker):
       """Use any OpenRouter LLM to score document relevance."""

       async def rerank_async(self, query, documents, top_n):
           # Prompt LLM to score each document 0-10
           # Sort by score, return top_n
   ```
   - Uses existing OpenRouter quota (no extra cost)
   - Model configurable (default: `google/gemini-2.5-flash`)
   - ~200ms latency per batch

2. **Cohere Reranker (optional, highest quality):**
   ```python
   class CohereReranker(BaseReranker):
       """Cohere Rerank API for production-grade reranking."""

       async def rerank_async(self, query, documents, top_n):
           # Call Cohere rerank endpoint
           # Returns documents sorted by relevance score
   ```
   - Requires `cohereKey` in API keys
   - Dedicated reranking model (purpose-built)
   - ~100ms latency, higher accuracy

**Auto-Selection Logic:**
- If `rerankerProvider: "auto"`: Use Cohere if key available, else LLM
- If `rerankerProvider: "cohere"`: Use Cohere (requires key)
- If `rerankerProvider: "llm"`: Always use LLM reranker

---

### 4. Document-Aware Chunking

**Why Two-Stage Chunking?**

Academic papers have structure (sections, subsections, abstracts). Naive recursive splitting ignores this structure, producing chunks that mix content from different sections. Two-stage chunking respects document hierarchy.

**Stage 1: Markdown Header Splitting**
```python
from langchain.text_splitter import MarkdownHeaderTextSplitter

header_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=[
        ("#", "h1"),
        ("##", "h2"),
        ("###", "h3"),
    ]
)
# Result: chunks aligned to document sections
```

**Stage 2: Size-Enforced Recursive Splitting**
```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

recursive_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    encoding_name='cl100k_base',
    chunk_size=500,
    chunk_overlap=50,
    separators=['\n\n', '\n', '. ', ' ', ''],
)
# Result: section-aware chunks that fit embedding model limits
```

**Chunking Pipeline:**
```
Full Document
    ↓
[MarkdownHeaderTextSplitter]
    → Section: "# Introduction" (2000 tokens)
    → Section: "## Methods" (3000 tokens)
    → Section: "## Results" (1500 tokens)
    ↓
[RecursiveCharacterTextSplitter] (per section)
    → "# Introduction" → 4 chunks (500 tokens each)
    → "## Methods" → 6 chunks
    → "## Results" → 3 chunks
    ↓
Each chunk retains: section header metadata, paper_id, chunk_index
```

**Chunking Trade-offs:**

| Chunk Size | Pros | Cons |
|------------|------|------|
| Small (200-300) | Precise retrieval, less noise | May lose context, more chunks |
| Medium (500-800) | **Balanced** | - |
| Large (1000-2000) | Preserves context, fewer chunks | May include irrelevant content |

**Best Practice:** 500-800 tokens with 50-100 token overlap.

---

### 5. Embedding Manager (embeddings.py)

**Supported Providers:**
1. **OpenAI (cloud, default):**
   - Model: text-embedding-3-small (1536 dims)
   - Pros: High quality, fast API
   - Cons: API costs, requires key

2. **Local (sentence-transformers):**
   - Models: all-MiniLM-L6-v2 (384d), all-mpnet-base-v2 (768d)
   - Pros: Free, offline-capable
   - Cons: GPU recommended, 2GB+ memory

---

### 6. Vector Store Manager (vector_store.py)

**Database Schema (after migration 003):**
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    paper_id UUID REFERENCES papers(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector(1536),             -- pgvector type
    search_vector tsvector              -- Full-text search (generated)
        GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    parent_chunk_id UUID,               -- Parent-child relationships
    embedding_version VARCHAR(32)       -- Track embedding model version
        DEFAULT 'v1',
    chunk_type VARCHAR(50),
    metadata JSONB,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Performance indexes
CREATE INDEX idx_embedding_hnsw ON document_chunks
    USING hnsw (embedding vector_cosine_ops);     -- Vector similarity
CREATE INDEX idx_chunks_fts ON document_chunks
    USING gin(search_vector);                      -- Full-text search
CREATE INDEX idx_chunks_metadata ON document_chunks
    USING gin(metadata);                           -- Metadata filtering
CREATE INDEX idx_paper_id ON document_chunks(paper_id);
```

**Key Features:**
- **HNSW index**: O(log n) approximate nearest neighbor search
- **GIN index**: Fast full-text search with tsvector
- **Generated column**: `search_vector` auto-populates from `content`
- **Metadata filtering**: JSONB `@>` operator for flexible queries

---

## Integration Points

### 1. MCP Tools Integration

**Advanced RAG Tools (advanced_rag_tools.py):**

12 MCP tools expose RAG functionality to agents:

```python
@mcp_tool
def answer_research_question(question: str) -> dict:
    """
    Full hybrid RAG query with answer generation.

    Pipeline: hybrid search → reranking → LLM answer
    Returns: answer, source citations, confidence
    """

@mcp_tool
def optimize_search(queries: list[str]) -> dict:
    """
    Test and optimize search performance.

    Runs queries through full pipeline, reports:
    - Average relevance scores
    - Query latency
    - Reranking impact
    """

@mcp_tool
def reindex_collection(force: bool = False) -> dict:
    """
    Rebuild the entire RAG index.

    With hybrid search enabled:
    - Re-chunks with document-aware splitter
    - Regenerates embeddings
    - search_vector auto-populates (generated column)
    """
```

### 2. Document Pipeline Integration

**Indexing During Processing:**
```python
# Background RAG indexing (non-blocking)
async def _schedule_background_rag_indexing(self, paper_id, markdown_path):
    """
    Index paper after note generation completes.

    Uses document-aware chunking:
    1. MarkdownHeaderTextSplitter (respect sections)
    2. RecursiveCharacterTextSplitter (enforce size)
    3. Generate embeddings
    4. Store with search_vector auto-population
    """
```

### 3. Automatic Database Migrations

**Migration 003: Hybrid Search Support**

Applied automatically on every startup (API server, MCP server, all-in-one container):

```python
# In app.py lifespan() and launcher.py
migration_manager = MigrationManager(database_url)
await migration_manager.initialize_database()
```

**What migration 003 adds:**
- `search_vector` column (tsvector, generated from content)
- `parent_chunk_id` column (for parent-child chunks)
- `embedding_version` column (track model versions)
- GIN index on `search_vector`
- GIN index on `metadata`

**Safety:** Idempotent, non-destructive, existing data preserved. The `search_vector` column auto-populates from existing `content` via the generated column.

---

## Configuration & Deployment

### Development Configuration

```json
{
  "rag": {
    "embeddingModel": "text-embedding-3-small",
    "chunkSize": 500,
    "chunkOverlap": 50,
    "topK": 5,
    "hybridSearchEnabled": true,
    "hybridSearchWeight": 0.7,
    "rerankingEnabled": true,
    "rerankerProvider": "auto",
    "qa": {
      "model": "anthropic/claude-3-5-sonnet",
      "temperature": 0.1
    }
  }
}
```

### Production Configuration

For larger corpora, tune for higher recall:

```json
{
  "rag": {
    "embeddingModel": "text-embedding-3-small",
    "chunkSize": 800,
    "chunkOverlap": 100,
    "topK": 10,
    "hybridSearchEnabled": true,
    "hybridSearchWeight": 0.7,
    "rerankingEnabled": true,
    "rerankerProvider": "cohere",
    "qa": {
      "model": "anthropic/claude-3-5-sonnet",
      "temperature": 0.1
    }
  }
}
```

### Database Tuning (Production)

```sql
-- PostgreSQL performance tuning
ALTER SYSTEM SET shared_buffers = '4GB';
ALTER SYSTEM SET effective_cache_size = '12GB';
ALTER SYSTEM SET work_mem = '64MB';
ALTER SYSTEM SET maintenance_work_mem = '512MB';

-- pgvector-specific
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET hnsw.ef_search = 64;
```

---

## Performance Optimization

### Query Latency Breakdown

| Stage | Latency | Notes |
|-------|---------|-------|
| Embedding generation | 20-50ms (local), 100-200ms (cloud) | Cached for repeated queries |
| Semantic search (HNSW) | 10-50ms | O(log n) approximate |
| BM25 search (GIN) | 5-20ms | PostgreSQL native FTS |
| RRF fusion | <1ms | In-memory score merge |
| Reranking (LLM) | 100-300ms | Batched scoring |
| Reranking (Cohere) | 50-100ms | Dedicated API |
| Context assembly | 5-10ms | De-duplication + metadata |
| LLM generation | 1-5s | Depends on model |

**Total p95:** <200ms (search only), <500ms (search + reranking), <5s (with QA)

### HNSW Index Tuning

```sql
CREATE INDEX idx_embedding_hnsw ON document_chunks
USING hnsw (embedding vector_cosine_ops)
WITH (
    m = 16,              -- Max connections per node
    ef_construction = 64 -- Build quality
);

-- Query-time: higher = better accuracy, slower
SET hnsw.ef_search = 40;
```

---

## Known Issues & Limitations

### 1. Vector Incompatibility on Model Change

Changing embedding model requires full reindex. Different models produce incompatible vector spaces. The `embedding_version` column tracks which model generated each vector.

### 2. Large Document Handling

Very large documents (100+ pages) create 200+ chunks. Mitigated by document-aware chunking which produces fewer, more coherent chunks than naive splitting.

### 3. BM25 Language Dependency

The tsvector uses `'english'` language configuration by default. Non-English papers may have reduced BM25 effectiveness. Semantic search still works across languages.

### 4. Reranking Latency

LLM reranking adds 100-300ms per query. For latency-sensitive applications, disable reranking or use Cohere (faster, purpose-built).

---

## Future Enhancements

### 1. Contextual Enrichment (Schema Ready)

LLM-generated context prepended to each chunk during indexing. Improves retrieval by adding document-level context to individual chunks. Currently in schema but disabled by default due to indexing cost.

### 2. Adaptive Query Routing (Schema Ready)

Dynamic query classification to route different query types (factual, analytical, exploratory) through optimized retrieval strategies. Currently in schema but disabled by default.

### 3. Multi-Index Support

Separate indexes per research domain/project for faster, more focused searches.

### 4. Cross-Encoder Reranking

Local cross-encoder models (e.g., ms-marco-MiniLM) for offline reranking without API calls.

---

## Conclusion

Thoth's RAG system provides production-ready **hybrid search** over research papers with:

- **Hybrid retrieval**: Semantic + BM25 with Reciprocal Rank Fusion
- **Reranking pipeline**: LLM-based (zero-cost) or Cohere API
- **Document-aware chunking**: Two-stage markdown header + recursive splitting
- **PostgreSQL + pgvector + tsvector**: Unified vector and full-text storage
- **Automatic migrations**: Schema upgrades applied on startup, no manual steps
- **Flexible embeddings**: Local or cloud, easy switching
- **MCP integration**: 12 tools for agent access
- **Hot-reloadable**: Config changes without restart

**Performance targets achieved:**
- Hybrid search: <200ms (search), <500ms (with reranking)
- Full QA pipeline: <5s
- Scalability: 100K+ chunks

**Last Updated**: February 2026
