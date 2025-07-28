# Thoth Debugging Guide

This guide helps you troubleshoot common issues encountered when running Thoth, particularly around embeddings, citation graph data, and RAG indexing.

## Common Issues and Solutions

### 1. Type Error: 'str' object has no attribute 'exists'

**Issue:** RAG indexing fails with a type error when trying to index markdown files.

**Cause:** String paths being passed where Path objects are expected.

**Solution:** Fixed in `src/thoth/pipelines/document_pipeline.py` by ensuring Path objects are created:

```python
# Before (problematic):
self._index_to_rag(new_markdown_path)  # string

# After (fixed):
self._index_to_rag(Path(new_markdown_path))  # Path object
```

**Status:** ✅ Fixed

---

### 2. Missing Essential Data Warnings

**Issue:** Multiple warnings like:
```
Missing essential data (PDF path stub, Markdown path stub, or analysis) for article xxx. Cannot regenerate note.
```

**Cause:** Articles in the citation graph lack the required metadata for note regeneration. This happens when:
- Articles are added via citations but don't have associated PDF/markdown files
- The original processing didn't complete successfully
- Data corruption in the citation graph

**Solution:**
1. **Improved Logging:** Enhanced error messages to show exactly which data is missing
2. **Prevention:** Ensure complete processing pipeline execution
3. **Manual Fix:** Remove incomplete entries from citation graph or reprocess source documents

**How to fix existing graph:**
```bash
# Option 1: Clear and rebuild citation graph
rm knowledge/graph/citations.graphml

# Option 2: Use debug script to identify problematic articles
python scripts/debug_embeddings.py
```

**Status:** ✅ Improved diagnostics added

---

### 3. Process Killed During Embedding Loading

**Issue:** Process gets killed with "Killed" message during checkpoint loading at ~25%.

**Cause:** Segmentation fault due to threading conflicts between:
- sentence-transformers library
- ChromaDB
- PyTorch and ML libraries
- OpenMP/MKL threading

**Solutions:**

#### Option A: Enhanced Local Embeddings (Default)
Environment variables are now automatically configured:
```bash
TOKENIZERS_PARALLELISM=false
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
NUMEXPR_NUM_THREADS=1
TORCH_NUM_THREADS=1
CHROMA_MAX_BATCH_SIZE=100
CHROMA_SUBMIT_BATCH_SIZE=100
```

#### Option B: Switch to OpenAI Embeddings (Recommended)
Add to your `.env` file:
```bash
# OpenAI API key
API_OPENAI_KEY=your_openai_api_key_here

# Switch to OpenAI embeddings
RAG_EMBEDDING_MODEL=openai/text-embedding-3-small
```

**Status:** ✅ Enhanced safety measures implemented

---

## Debugging Tools

### 1. Embeddings Debug Script

Test your embedding configuration:
```bash
python scripts/debug_embeddings.py
```

This script will:
- Check environment safety
- Test embedding initialization
- Suggest fixes for common issues
- Recommend OpenAI fallback if local embeddings fail

### 2. Manual Environment Setup

If you continue having issues, manually set environment variables before starting Thoth:

```bash
# Set safe environment
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export TORCH_NUM_THREADS=1
export CHROMA_MAX_BATCH_SIZE=100
export CHROMA_SUBMIT_BATCH_SIZE=100

# Then run Thoth
python -m thoth.cli.main your-command
```

### 3. Configuration Check

Verify your configuration:
```bash
python -c "from thoth.utilities.config import get_config; config = get_config(); print(f'Model: {config.rag_config.embedding_model}'); print(f'OpenAI Key: {bool(config.api_keys.openai_key)}')"
```

---

## Prevention Best Practices

### 1. Use OpenAI Embeddings for Production
- More reliable
- No memory/threading issues
- Better performance
- No local model downloads

### 2. Monitor System Resources
- Watch memory usage during embedding operations
- Use `htop` or `ps` to monitor process health
- Set resource limits if needed

### 3. Regular Health Checks
```bash
# Check system health
python scripts/health_check.py

# Test embeddings specifically
python scripts/debug_embeddings.py
```

---

## Emergency Recovery

If your system is completely broken:

### 1. Reset RAG Database
```bash
rm -rf knowledge/vector_db/
```

### 2. Reset Citation Graph
```bash
rm knowledge/graph/citations.graphml
```

### 3. Clear Processed Files Cache
```bash
rm knowledge/processed_pdfs.json
```

### 4. Switch to OpenAI Embeddings
Add to `.env`:
```bash
RAG_EMBEDDING_MODEL=openai/text-embedding-3-small
API_OPENAI_KEY=your_key_here
```

### 5. Restart Fresh
```bash
python -m thoth.cli.main reprocess-notes
```

---

## Getting Help

1. **Run the debug script first:** `python scripts/debug_embeddings.py`
2. **Check logs:** Look for specific error messages
3. **Try OpenAI embeddings:** Often solves segfault issues
4. **Check system resources:** Memory, disk space, etc.
5. **Reset if needed:** Clean slate with emergency recovery steps

For persistent issues, please share:
- Output of debug script
- Full error logs
- System information (OS, memory, etc.)
- Configuration details
