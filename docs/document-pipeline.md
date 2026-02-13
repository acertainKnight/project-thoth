# Document Processing Pipeline

How Thoth turns PDFs into structured, searchable, AI-ready notes.

**Core**: Multi-stage PDF-to-note transformation with parallel processing
**Status**: Production

---

## Overview

The pipeline takes academic PDFs and produces Obsidian notes with extracted metadata, citations, AI-generated tags, and (optionally) vector embeddings for RAG search. The whole thing runs in 30-60 seconds per paper.

The design was shaped by local server constraints. Unlike cloud pipelines with unlimited workers, a laptop or NAS has fixed CPU and RAM. The pipeline auto-detects available cores, scales workers accordingly, and caps concurrent processing to avoid memory exhaustion.

---

## Pipeline Stages

```
1. PDF Input          → Validate file, check cache, hash for change detection
        ↓
2. OCR Conversion     → Mistral OCR API (fast, accurate), pypdf fallback if API fails
        ↓
   ┌────┴────┐
   ↓         ↓
3a. Content  3b. Citation      ← These run in parallel
   Analysis     Extraction
   ↓         ↓
   └────┬────┘
        ↓
4. Note Generation    → Jinja2 template, YAML frontmatter, Obsidian wikilinks
        ↓
5. Background Indexing → Vector embeddings + FTS vectors, citation network updates
                         (non-blocking — note appears immediately)
```

**Timing** (wall-clock with parallelization):
```
PDF Input (1s)
    └─► OCR (10-15s)
            ├─► Content Analysis (5-10s)     ← parallel
            └─► Citation Extraction (10-20s)  ← parallel
            └─► Note Generation (2-5s)
                    └─► Background RAG Indexing (10-30s, non-blocking)

Total: 30-60s   |   Sequential would be: 38-75s
```

---

## Worker Scaling

The pipeline uses different worker counts for different task types, based on their bottleneck:

| Task Type | Bottleneck | Max Workers | Why |
|-----------|------------|-------------|-----|
| Content Analysis | CPU + Memory | 4 | Parsing is CPU-intensive, analysis loads data into memory |
| Citation Extraction | Network I/O | 6 | Waiting on API responses, more concurrency helps |
| OCR Processing | API Rate Limit | 3 | Mistral API limits concurrent requests |
| Background Tasks | Low Priority | 2 | Don't starve foreground tasks |

On a 4-core machine, everything gets capped at 3 workers (4 cores minus 1 reserved for the system). On a 16-core machine, the caps above apply — no point throwing 15 workers at OCR when the API only allows 3 concurrent requests.

### Why Threads + Async (Not Process Pools)

I considered three approaches:

| Approach | Time (100 papers) | Memory | Notes |
|----------|-------------------|--------|-------|
| Sequential | ~150 min | 200MB | Baseline |
| Thread Pool (8) | ~45 min | 400MB | 3.3x speedup |
| Process Pool (8) | ~40 min | 1.2GB | 3.8x speedup, high memory |
| **Hybrid (Thread+Async)** | **~35 min** | **450MB** | **4.3x speedup, best balance** |

Process pools give true parallelism but cost 50-100MB per process and add IPC complexity. Since most pipeline time is I/O (OCR API calls, citation API lookups, file reads), threads + async gets comparable throughput with much lower memory. The GIL isn't a real bottleneck here because I/O operations release it.

Thread pools are persistent — created once at initialization, reused across documents. No per-document pool creation overhead.

---

## Async OCR

OCR is the slowest step (10-15 seconds). Doing it synchronously means every PDF blocks the entire pipeline. With async:

```
Synchronous:  PDF1 OCR (15s) → Analysis → PDF2 OCR (15s) → ...
              3 PDFs: 75s

Async:        PDF1 OCR (15s) → Analysis
              PDF2 OCR (15s) → Analysis   (starts immediately)
              PDF3 OCR (15s) → Analysis   (starts immediately)
              3 PDFs: 25s
```

The pipeline uses Mistral's OCR API as the primary method (fast, accurate on academic papers). If the API fails — network issue, rate limit, outage — it falls back to local pypdf extraction. Local is slower and less accurate, but it works offline.

---

## Parallel Analysis and Citation Extraction

After OCR, content analysis and citation extraction run simultaneously via `asyncio.gather`. Analysis is CPU-bound (runs in thread pool), citations are I/O-bound (runs in async). Both start at the same time, and the pipeline waits for whichever finishes last.

A global semaphore limits concurrent documents to 8. Without it, processing 100 PDFs at once would use 20GB of memory (100 x 200MB peak per doc) and fire 5000 concurrent API calls. With the semaphore: 1.6GB memory, 400 concurrent calls, stable and predictable.

---

## Caching

The `PDFTracker` avoids redundant processing. Each processed PDF gets a SHA-256 hash stored in a JSON file. On subsequent runs, if the hash matches, processing is skipped.

- First run: 0% cache hits
- After a config change: ~70% hits (only re-process changed files)
- Re-run with no changes: 100% hits

The hash computation takes ~100ms for a 10MB PDF — a worthwhile trade for saving 30-60 seconds of full processing.

---

## Background Indexing

RAG indexing (generating embeddings, building search vectors) takes 10-30 seconds and isn't something the user needs to wait for. The note is the deliverable — embeddings are a bonus.

So indexing runs in a background thread pool. The user gets their note immediately, and search indexing happens eventually. If indexing fails, the note still exists — the failure gets logged and marked for retry. The user has their paper; they just can't search it yet.

---

## Memory Management

### Streaming for Large PDFs

A 100MB PDF can balloon to 500MB+ with parsing overhead. The pipeline processes page-by-page instead of loading the entire file:

| Approach | Peak Memory | Time |
|----------|-------------|------|
| Load entire PDF | 500MB | 30s |
| Page-by-page streaming | 150MB | 32s (6% slower) |

The 6% slowdown is worth the 70% memory reduction.

### Manual GC

After heavy operations (OCR, analysis), the pipeline triggers explicit garbage collection. Without it, temporary objects accumulate faster than Python's GC reclaims them:

- Without manual GC: Peak 3.2GB, steady state 2.5GB
- With manual GC: Peak 2.1GB, steady state 800MB

50-100ms of GC overhead for 1.5GB of memory savings.

---

## Error Handling

The pipeline follows a partial-results philosophy. A note without citations is better than no note at all.

**OCR**: Try API first, fall back to local pypdf. If both fail, that's fatal — there's nothing to process.

**Citations**: If the whole extraction fails, return an empty list. If individual citations fail to parse, skip them and keep going. The note gets a `citations_extracted: false` flag in its frontmatter so you know something went wrong.

**Indexing**: Background failures are logged, not raised. The note exists regardless.

---

## Docker Deployment

```yaml
services:
  thoth-pdf-monitor:
    command: ["python", "-m", "thoth", "monitor", "--optimized", "--recursive"]
    environment:
      - THOTH_MAX_WORKERS=8
      - THOTH_ENABLE_CACHING=true
    deploy:
      resources:
        limits:
          memory: 2G   # 8 concurrent docs × 200MB + safety margin
          cpus: '1.5'
```

---

## Trade-offs

**Threads vs processes**: Chose threads for lower memory at the cost of GIL constraints. Works well because the pipeline is I/O-dominant.

**API OCR vs local**: API is faster and more accurate but requires network access and costs money. Local is a safety net, not the primary path.

**Background indexing**: User gets notes faster, but there's a window where a paper exists but isn't searchable. In practice this is 10-30 seconds and rarely matters.

**Caching granularity**: File-level hashing means any change to a PDF triggers full reprocessing. Finer-grained caching (per-section) would be more efficient but vastly more complex.

---

*Last Updated: February 2026*
