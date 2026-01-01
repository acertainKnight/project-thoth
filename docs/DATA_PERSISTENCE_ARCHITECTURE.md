# Data Persistence & Versioning Architecture

## Executive Summary

**Current Critical Issues**:
1. ❌ `markdown_content` NOT saved to papers table (0 of 183 papers)
2. ❌ Embeddings NOT generated (0 chunks in document_chunks)
3. ❌ No versioning - reprocessing overwrites previous analysis
4. ✅ Citation graph and tags ARE being saved correctly

**Root Causes**:
- Pipeline saves markdown to disk but not to `papers.markdown_content` field
- RAG config `skip_files_with_images=true` blocks all academic papers
- No versioning system for tracking multiple processing runs
- async/await conflict in VectorStoreManager

---

## Current Data Flow (What Exists)

### Pipeline Processing Stages

```
PDF → OCR → 2 Markdowns:
                ├─ {name}.md (WITH images) → Obsidian display
                └─ {name}_no_images.md (NO images) → LLM processing
                                            ↓
                                    Analyze Content
                                            ↓
                                    Extract Citations
                                            ↓
                                    Generate Note
                                            ↓
                                    Save to PostgreSQL ❓
```

### What's Being Saved

✅ **papers table** (183 processed papers):
- Metadata: title, authors, doi, arxiv_id, year, abstract
- File paths: pdf_path, markdown_path (images version)
- Analysis: analysis_data (JSONB with tags, methodology, results)
- ❌ markdown_content: NULL for all papers

✅ **citations table** (1,754 relationships):
- citing_paper_id → cited_paper_id
- citation_context

✅ **tags + paper_tags**:
- Normalized tag storage
- Many-to-many relationships

❌ **document_chunks** (0 chunks):
- Table exists with pgvector column
- HNSW index configured
- No data inserted

---

## Required Architecture: Versioned Processing

### New Table: `processing_versions`

```sql
CREATE TABLE processing_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,

    -- Processing metadata
    llm_model TEXT NOT NULL,
    processing_config JSONB NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Content snapshots
    markdown_content TEXT,  -- no_images version for embeddings
    analysis_data JSONB,    -- Full AnalysisResponse

    -- Status
    is_active BOOLEAN DEFAULT true,  -- Current version

    UNIQUE(paper_id, version)
);

CREATE INDEX idx_versions_paper_active 
    ON processing_versions(paper_id, is_active) WHERE is_active = true;
```

### Updated `document_chunks` (Add Versioning)

```sql
ALTER TABLE document_chunks
    ADD COLUMN processing_version INTEGER,
    ADD FOREIGN KEY (paper_id, processing_version) 
        REFERENCES processing_versions(paper_id, version);
```

### Updated `citations` (Add Versioning)

```sql
ALTER TABLE citations
    ADD COLUMN processing_version INTEGER,
    ADD FOREIGN KEY (citing_paper_id, processing_version) 
        REFERENCES processing_versions(paper_id, version);
```

---

## Implementation Plan

### Phase 1: Fix Data Loss (CRITICAL - Do First)

#### 1.1: Save markdown_content to papers table

**File**: `src/thoth/knowledge/graph.py`
**Method**: `CitationTracker.process_citations()`

Add parameter and save:
```python
def process_citations(
    self,
    pdf_path: str,
    markdown_path: str,
    no_images_markdown: str,  # ✅ ADD THIS
    analysis,
    citations,
    llm_model=None,
):
    # ... existing code ...

    # ✅ ADD: Save markdown_content to papers table
    await conn.execute("""
        UPDATE papers
        SET markdown_content = $1,
            markdown_path = $2
        WHERE id = $3
    """, no_images_markdown, markdown_path, paper_id)
```

#### 1.2: Fix RAG Configuration

**File**: `/vault/_thoth/settings.json`

Change:
```json
{
  "rag_config": {
    "skip_files_with_images": false  // ✅ WAS: true
  }
}
```

#### 1.3: Pass no_images_markdown to RAG

**File**: `src/thoth/pipelines/optimized_document_pipeline.py`

**Line 419-446**: Update `_generate_note()`:
```python
def _generate_note(
    self, 
    pdf_path: Path, 
    markdown_path: Path,
    no_images_markdown: str,  # ✅ ADD THIS PARAMETER
    analysis, 
    citations: list[Citation]
) -> tuple[str, str, str]:
    # ... existing note generation ...

    article_id = self.citation_tracker.process_citations(
        pdf_path=new_pdf_path,
        markdown_path=new_markdown_path,
        no_images_markdown=no_images_markdown,  # ✅ PASS IT
        analysis=analysis,
        citations=citations,
        llm_model=llm_model,
    )
```

**Line 181-189**: Update caller:
```python
note_future = self._background_tasks_executor.submit(
    self._generate_note,
    pdf_path=pdf_path,
    markdown_path=markdown_path,
    no_images_markdown=no_images_markdown,  # ✅ PASS IT
    analysis=analysis,
    citations=citations,
)
```

#### 1.4: Fix RAG to Index Correct File

**File**: `src/thoth/pipelines/optimized_document_pipeline.py`
**Lines 316-330**: Update `_schedule_background_rag_indexing()`:

```python
def _schedule_background_rag_indexing(
    self, 
    markdown_path: str, 
    no_images_markdown_path: str,  # ✅ ADD THIS
    note_path: str
) -> None:
    def _background_rag_indexing():
        try:
            # ✅ Index no_images version (no figures/tables)
            self._index_to_rag(Path(no_images_markdown_path))
            self._index_to_rag(Path(note_path))
            self.logger.debug('Background RAG indexing completed')
```

#### 1.5: Fix async/await in VectorStoreManager

**File**: `src/thoth/rag/vector_store.py`
**Line 97**: Change from `asyncio.run()` to awaitable:

```python
# ❌ OLD:
def add_documents(self, documents, paper_id=None, **kwargs):
    return asyncio.run(self._add_documents_async(documents, paper_id, **kwargs))

# ✅ NEW:
async def add_documents_async(self, documents, paper_id=None, **kwargs):
    """Async version - use this from async contexts."""
    return await self._add_documents_async(documents, paper_id, **kwargs)

def add_documents(self, documents, paper_id=None, **kwargs):
    """Sync wrapper - creates new event loop if needed."""
    try:
        loop = asyncio.get_running_loop()
        # Already in async context - return coroutine
        return self.add_documents_async(documents, paper_id, **kwargs)
    except RuntimeError:
        # No event loop - safe to use asyncio.run()
        return asyncio.run(self._add_documents_async(documents, paper_id, **kwargs))
```

#### 1.6: Backfill 183 Papers

**Script**: `src/thoth/migration/backfill_embeddings_fixed.py`

```python
# Query papers with markdown_content
papers = await conn.fetch("""
    SELECT id, title, markdown_content
    FROM papers
    WHERE markdown_content IS NOT NULL
    AND NOT embeddings_generated
""")

for paper in papers:
    # Create temp file with markdown_content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as tmp:
        tmp.write(paper['markdown_content'])
        tmp_path = Path(tmp.name)

    # Index with RAG service (skip_images_check=true since already no_images version)
    doc_ids = await services.rag.rag_manager.index_markdown_file(tmp_path)

    # Mark as indexed
    await conn.execute("""
        UPDATE papers SET embeddings_generated = true WHERE id = $1
    """, paper['id'])
```

---

### Phase 2: Add Versioning (After Phase 1 Works)

#### 2.1: Create Migration

**File**: `migrations/001_add_processing_versions.sql`

```sql
-- Create processing_versions table
CREATE TABLE processing_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    llm_model TEXT NOT NULL,
    processing_config JSONB NOT NULL,
    processed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    markdown_content TEXT,
    analysis_data JSONB,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(paper_id, version)
);

-- Add versioning to document_chunks
ALTER TABLE document_chunks
    ADD COLUMN processing_version INTEGER;

-- Add versioning to citations
ALTER TABLE citations
    ADD COLUMN processing_version INTEGER;

-- Migrate existing data to version=1
INSERT INTO processing_versions (paper_id, version, llm_model, processing_config, markdown_content, analysis_data, is_active)
SELECT 
    id,
    1,
    COALESCE(llm_model, 'unknown'),
    '{"migrated": true}'::jsonb,
    markdown_content,
    analysis_data,
    true
FROM papers
WHERE analysis_data IS NOT NULL;
```

#### 2.2: Update CitationTracker

**File**: `src/thoth/knowledge/graph.py` (or wherever CitationTracker is)

```python
class CitationTracker:
    async def create_processing_version(
        self,
        paper_id: uuid.UUID,
        markdown_content: str,
        analysis: AnalysisResponse,
        citations: list[Citation],
        llm_model: str,
        processing_config: dict,
    ) -> int:
        """
        Create new processing version with all data.
        
        Returns version number for this paper.
        """
        # Get next version number
        next_version = await self.conn.fetchval("""
            SELECT COALESCE(MAX(version), 0) + 1
            FROM processing_versions
            WHERE paper_id = $1
        """, paper_id)

        # Mark previous versions inactive
        await self.conn.execute("""
            UPDATE processing_versions
            SET is_active = false
            WHERE paper_id = $1
        """, paper_id)

        # Insert new version
        version_id = await self.conn.fetchval("""
            INSERT INTO processing_versions (
                paper_id, version, llm_model, processing_config,
                markdown_content, analysis_data, is_active
            ) VALUES ($1, $2, $3, $4, $5, $6, true)
            RETURNING id
        """, paper_id, next_version, llm_model, json.dumps(processing_config),
            markdown_content, json.dumps(analysis.dict()))

        return next_version
```

#### 2.3: Update Pipeline to Use Versioning

**File**: `src/thoth/pipelines/optimized_document_pipeline.py`

```python
# After generating note and citations:
version = await self.citation_tracker.create_processing_version(
    paper_id=article_id,
    markdown_content=no_images_markdown,
    analysis=analysis,
    citations=citations,
    llm_model=llm_model,
    processing_config=self.get_processing_config_snapshot(),
)

# Index embeddings with version reference
embedding_ids = await services.rag.index_content_versioned(
    content=no_images_markdown,
    paper_id=article_id,
    processing_version=version,
)
```

---

## Testing Plan

### Test 1: Verify markdown_content Saved
```sql
-- Should show 183 papers with markdown_content
SELECT COUNT(*) FROM papers WHERE markdown_content IS NOT NULL;

-- Should show no image references in content
SELECT title FROM papers 
WHERE markdown_content LIKE '%![%' 
LIMIT 5;  -- Should return 0 rows
```

### Test 2: Verify Embeddings Generated
```sql
-- Should show >0 chunks
SELECT COUNT(*) as total_chunks,
       COUNT(DISTINCT paper_id) as papers_with_embeddings
FROM document_chunks;

-- Should show 183 papers marked
SELECT COUNT(*) FROM papers WHERE embeddings_generated = true;
```

### Test 3: Test Semantic Search
```python
results = services.rag.search(
    query="memory systems in large language models",
    k=5
)
# Should return relevant papers with scores
```

### Test 4: Test Versioning (Phase 2)
```python
# Process paper first time
process_pdf("paper.pdf")  # Creates version=1

# Change config and reprocess
config.llm_config.model = "claude-3-opus"
process_pdf("paper.pdf")  # Creates version=2

# Verify both versions exist
SELECT version, llm_model, processing_config 
FROM processing_versions 
WHERE paper_id = {paper_id}
ORDER BY version;

# Should show:
# version=1, model=sonnet, active=false
# version=2, model=opus, active=true
```

---

## Files to Modify

| File | Changes | Priority |
|------|---------|----------|
| `src/thoth/knowledge/graph.py` | Add markdown_content save | CRITICAL |
| `src/thoth/pipelines/optimized_document_pipeline.py` | Pass no_images_markdown | CRITICAL |
| `/vault/_thoth/settings.json` | Change skip_files_with_images | CRITICAL |
| `src/thoth/rag/vector_store.py` | Fix async/await | CRITICAL |
| `src/thoth/migration/backfill_embeddings_fixed.py` | Create working backfill | CRITICAL |
| `migrations/001_add_processing_versions.sql` | Versioning schema | HIGH |
| `src/thoth/knowledge/graph.py` | Add versioning methods | HIGH |

---

## Success Criteria

### Phase 1 (Data Loss Fixed):
- [x] ✅ graph.py saves all paper metadata (DONE)
- [ ] 183 papers have markdown_content
- [ ] 183 papers have embeddings_generated=true
- [ ] document_chunks has >1000 chunks
- [ ] Semantic search returns relevant results
- [ ] No data lost on reprocessing

### Phase 2 (Versioning Added):
- [ ] Reprocessing creates version=2 (doesn't overwrite version=1)
- [ ] Both versions queryable
- [ ] Embeddings linked to versions
- [ ] Citations linked to versions
- [ ] Config changes tracked
- [ ] Rollback capability works

