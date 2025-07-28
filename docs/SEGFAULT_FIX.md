# Segmentation Fault Fix for ChromaDB + sentence-transformers

## Problem

The application was experiencing segmentation faults when using ChromaDB with sentence-transformers for embeddings, particularly during the `vector_store.add_documents()` operation.

## Root Cause

The segmentation fault was caused by threading conflicts and memory management issues between:
- sentence-transformers library
- ChromaDB
- PyTorch and other ML libraries
- OpenMP and MKL threading libraries

## Solution Options

### Option 1: Fix Local Embeddings (Recommended for Offline Use)

#### 1. Environment Variable Configuration

Set these environment variables **before** importing any ML libraries:

```bash
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TORCH_NUM_THREADS=1
export CHROMA_MAX_BATCH_SIZE=100
export CHROMA_SUBMIT_BATCH_SIZE=100
export SQLITE_ENABLE_PREUPDATE_HOOK=0
export SQLITE_ENABLE_FTS5=0
```

#### 2. Safe Embeddings Configuration

Configure HuggingFaceEmbeddings with safer parameters:

```python
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name='all-MiniLM-L6-v2',
    model_kwargs={
        'device': 'cpu',
        'trust_remote_code': False,
    },
    encode_kwargs={
        'normalize_embeddings': True,
        'batch_size': 8,  # Smaller batch size
    },
    show_progress=False,  # Disable progress display
)
```

### Option 2: Use OpenAI Embeddings (Recommended for Production)

**Advantages:**
- ✅ No segmentation faults
- ✅ No local model downloads
- ✅ Better performance and quality
- ✅ No memory management issues

#### 1. Add to your `.env` file:

```bash
# API Key
API_OPENAI_KEY=your_openai_api_key_here

# RAG Configuration
RAG_EMBEDDING_MODEL=openai/text-embedding-3-small
RAG_EMBEDDING_BATCH_SIZE=100
RAG_VECTOR_DB_PATH=${WORKSPACE_DIR}/knowledge/vector_db
RAG_COLLECTION_NAME=thoth_knowledge
RAG_CHUNK_SIZE=500
RAG_CHUNK_OVERLAP=50
RAG_CHUNK_ENCODING=cl100k_base
RAG_QA_MODEL=openai/gpt-4o-mini
RAG_QA_TEMPERATURE=0.2
RAG_QA_MAX_TOKENS=2000
RAG_RETRIEVAL_K=4
```

#### 2. Available OpenAI embedding models:

- `openai/text-embedding-3-small` (1536 dimensions, cheaper)
- `openai/text-embedding-3-large` (3072 dimensions, better quality)
- `openai/text-embedding-ada-002` (1536 dimensions, legacy)

### Option 3: Alternative Local Models

If you want to avoid OpenAI costs but still have local embeddings, try these alternatives:

```bash
# Faster, smaller models that are less likely to cause segfaults
RAG_EMBEDDING_MODEL=all-MiniLM-L6-v2        # 384 dimensions, very fast
RAG_EMBEDDING_MODEL=all-MiniLM-L12-v2       # 384 dimensions, better quality
RAG_EMBEDDING_MODEL=paraphrase-MiniLM-L6-v2 # 384 dimensions, good for similarity
```

## Implementation

The fixes have been implemented in:

1. **`src/thoth/cli/main.py`** - Early environment variable configuration
2. **`src/thoth/rag/embeddings.py`** - Support for both local and OpenAI embeddings
3. **`src/thoth/rag/vector_store.py`** - Batch processing and safe ChromaDB configuration
4. **`scripts/fix_segfault.py`** - Troubleshooting script

## Testing

Run the troubleshooting script to verify the fixes:

```bash
uv run python scripts/fix_segfault.py
```

Test with OpenAI embeddings:

```bash
# Set your API key and model in .env, then test
uv run python -c "
from thoth.rag.embeddings import EmbeddingManager
manager = EmbeddingManager()
result = manager.embed_documents(['Test document'])
print(f'✅ Embedded successfully with {manager.model}')
"
```

## Cost Comparison

| Option | Setup | Cost | Quality | Reliability |
|--------|-------|------|---------|-------------|
| **Local (fixed)** | Complex | Free | Good | Medium |
| **OpenAI** | Simple | ~$0.02/1M tokens | Excellent | High |
| **Alternative Local** | Medium | Free | Good | High |

## Recommendation

- **For Development**: Use local embeddings with our fixes
- **For Production**: Use OpenAI embeddings for reliability
- **For Cost-Sensitive**: Use alternative local models (all-MiniLM-L6-v2)

## Prevention Tips

1. **Always set environment variables before importing ML libraries**
2. **Use smaller batch sizes when processing documents**
3. **Avoid concurrent ChromaDB operations**
4. **Keep ChromaDB and sentence-transformers updated**
5. **Monitor system memory usage during processing**
6. **Consider OpenAI embeddings for production workloads**

## Alternative Solutions

If issues persist, consider:

1. **Using API-based embeddings** (OpenAI, Cohere, etc.)
2. **Running ChromaDB as a separate service** with HTTP API
3. **Using different vector databases** (Pinecone, Weaviate, etc.)
4. **Containerizing the application** to isolate dependencies

## References

- [ChromaDB Issues](https://github.com/chroma-core/chroma/issues)
- [sentence-transformers Threading Issues](https://github.com/UKPLab/sentence-transformers/issues)
- [LangChain Vector Store Issues](https://github.com/langchain-ai/langchain/issues)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
