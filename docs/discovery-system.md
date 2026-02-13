# Discovery System

How Thoth finds and aggregates research papers from multiple sources.

**Core**: Plugin-based paper aggregation with automated scheduling
**Status**: Production

---

## Overview

The discovery system keeps your vault updated with relevant papers from academic databases. It's built around a plugin architecture — each source (ArXiv, Semantic Scholar, CrossRef, OpenAlex, etc.) is a plugin that implements the same interface. A scheduler runs discoveries on configurable cadences, and a context analyzer makes the searches targeted rather than generic.

If one source is down, discovery continues with the rest. Partial results beat no results.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Discovery Scheduler                         │
│  - Cron-like scheduling, daemon mode, state persistence     │
└───────────────────────┬─────────────────────────────────────┘
                        ↓
┌───────────────────────────────────────────────────────────────┐
│                  Discovery Manager                             │
│  - Source orchestration, result aggregation                    │
│  - Deduplication (DOI/title matching), filter application     │
└──────┬─────────┬────────────┬──────────────┬──────────────────┘
       ↓         ↓            ↓              ↓
   ┌──────┐  ┌──────┐    ┌────────┐    ┌────────┐
   │ArXiv │  │PubMed│    │CrossRef│    │OpenAlex│  ... (plugins)
   └──────┘  └──────┘    └────────┘    └────────┘
       ↓         ↓            ↓              ↓
   Rate Limiters → Retry Logic → External APIs
```

There are two additional layers on top:

**Context Analyzer**: Looks at papers already in your vault — topics, authors, citation patterns — and generates targeted queries. Instead of searching "machine learning" and getting 10,000 results, it builds queries like "papers by Vaswani on transformer attention" based on what you already have.

**Browser Automation** (Playwright): For sites without APIs. Headless Chrome with session persistence, connection pooling (max 5 concurrent), and anti-detection strategies for sites that block bots.

---

## Source Plugins

Each plugin implements `BaseAPISource` with a `discover()` method and rate limit configuration. Here's what each source brings:

### ArXiv

- **Endpoint**: `https://export.arxiv.org/api/query` (Atom XML)
- **Rate limit**: 1 request per 3 seconds (we use 100ms with automatic backoff)
- **No API key required**: Open access
- **Category filtering**: `cs.LG`, `cs.AI`, `stat.ML`, etc.
- **Parsing**: BeautifulSoup with lxml-xml parser. Chose this over raw lxml for tolerance of malformed XML — real-world RSS feeds are messy.

### Semantic Scholar

- **Modern JSON API** with excellent metadata
- **Author disambiguation** already solved
- **Citation counts** included
- **Rate limit**: Higher with API key

### CrossRef

- **Authoritative DOI registry** from publishers
- **JSON REST API**: Modern, fast, well-documented
- **Generous rate limits**: 50 req/second
- **Polite pool**: Higher limits if you identify yourself with a contact email
- **Best for**: DOI lookups, citation metadata, publication details

### OpenAlex

- **Open access**: Free, 100K requests/day with email
- **250M+ works indexed**: Broadest coverage
- **Author disambiguation** and institution resolution built in
- **Citation counts**: Open citation data
- **AI-generated topic classifications**: Concepts with confidence scores

I lean on OpenAlex as a primary source because it has no API key friction, broader coverage than Google Scholar (which has no API), richer metadata than ArXiv, and citation counts that CrossRef doesn't provide.

### PubMed

- **Two-step process**: E-search (get IDs) then E-fetch (get details)
- **Rate limit**: 3 req/s without key, 10 req/s with NCBI API key
- **Batch fetching**: 100 PMIDs per request
- **Complex XML**: Nested authors, scattered journal info, sectioned abstracts

---

## Deduplication

Multiple sources often return the same paper (ArXiv and OpenAlex both index preprints, for example). Deduplication runs after aggregation:

1. **DOI exact match** (highest priority)
2. **Title fuzzy match** (>85% similarity)
3. **ArXiv ID match** (arxiv:2301.12345)

When duplicates are found, metadata is kept from the highest-quality source: CrossRef > OpenAlex > ArXiv > PubMed.

---

## Scheduler

The scheduler runs in a daemon thread with 60-second polling. Every minute it checks each source's `next_run` time and fires discovery if it's due.

**Why polling instead of dynamic sleep**: Simpler, predictable, tolerates clock changes (NTP sync). The alternative — sleeping until the next scheduled run — has edge cases (what if no sources are scheduled? what if a new source is added while sleeping?). For a scheduler that runs on intervals of hours or days, 60-second granularity is fine.

**State persistence**: Schedule state (last run, next run, enabled/disabled) is saved to a JSON file that survives container restarts.

**Scheduling modes**:
- **Interval-based**: `interval_minutes: 1440` (daily)
- **Time-of-day**: `time_of_day: "09:00"` with optional `days_of_week: [1, 3, 5]` (Mon/Wed/Fri at 9am)

**Threading vs async**: The scheduler uses a daemon thread, not asyncio. Discovery manager has sync code (file I/O), the scheduler needs to run for days or weeks, and a thread is simpler than managing an async event loop for this kind of long-running background process.

---

## Context Analyzer

This is what makes discovery useful rather than just noisy.

**Phase 1 — Topic Extraction**: Read all paper notes, extract keywords and tags from frontmatter, build a topic frequency map, identify clusters (NLP, CV, RL, etc.).

**Phase 2 — Author Network**: Extract author lists, build a collaboration graph, identify key researchers in your collection.

**Phase 3 — Citation Patterns**: Which papers are cited most? What's recent vs. foundational? Where are the research lineages?

**Phase 4 — Query Generation**: Combine topics + authors + trends into targeted search queries. "Papers by Author X on Topic Y" and "recent papers citing Paper Z" instead of generic keyword searches.

**Relevance scoring** for discovered papers uses a weighted combination:
- Topic match against vault (40%)
- Author overlap (30%)
- Citation overlap with existing papers (30%)
- Bonus for recency and citation count

Without the context analyzer, you're searching "machine learning" and drowning in noise. With it, you get targeted results that actually relate to your existing research.

---

## Browser Automation

For sites that don't have APIs (conference proceedings pages, institutional repositories), the system uses Playwright with headless Chromium.

**Why Playwright over Selenium**: Faster (native automation protocol), modern async API, simpler installation, built-in anti-detection. Selenium requires separate driver binaries and uses the slower WebDriver protocol.

**Browser pooling**: Max 5 concurrent browser contexts. Browser launch is expensive (~1-2 seconds), so browsers are kept alive and contexts are reused. Each workflow gets an isolated context (cookies, storage) so parallel workflows don't interfere.

**Workflows as data**: Scraping workflows are JSON configurations, not code:
```json
{
  "name": "ACM Digital Library Scraper",
  "steps": [
    {"action": "navigate", "url": "https://dl.acm.org/search"},
    {"action": "type", "selector": "input[name='query']", "text": "machine learning"},
    {"action": "click", "selector": "button[type='submit']"},
    {"action": "wait", "selector": ".search-result"},
    {"action": "extract", "selector": ".search-result", "fields": {...}}
  ]
}
```

This means workflows can be modified, templated, and shared without code changes. The auto-scraper builder (see [usage guide](usage.md#creating-custom-sources)) generates these workflows from any URL using an LLM to analyze the page structure.

**Anti-detection**: Disabled automation flags, realistic user agents, random delays between actions, mouse movements before clicks, viewport randomization. Enough to get past most basic bot detection.

**Session persistence**: Browser sessions (cookies, localStorage) are saved to disk and restored for authenticated access to paywalled sites.

---

## Rate Limiting

Each source has its own rate limiter using a token bucket algorithm:

| Source | Rate | Burst | Notes |
|--------|------|-------|-------|
| ArXiv | 1 req/3s | 1 | Conservative, backs off automatically |
| PubMed | 3-10 req/s | 10 | Higher with API key |
| CrossRef | 50 req/s | 100 | Very generous |
| OpenAlex | 10 req/s | 50 | With email identification |
| Browser | 1 req/s | 5 | Memory-constrained |

---

## Docker Deployment

```yaml
services:
  thoth-discovery:
    command: ["python", "-m", "thoth", "discovery", "start-scheduler"]
    environment:
      - THOTH_DISCOVERY_AUTO_START_SCHEDULER=true
      - THOTH_DISCOVERY_DEFAULT_MAX_ARTICLES=50
    restart: unless-stopped
```

Discovery runs in its own container so it can crash without affecting the API or MCP server. It's CPU and network-intensive, so isolation makes resource management cleaner.

---

## Trade-offs

**File + DB hybrid for source storage**: Sources live as JSON files (easy to hand-edit) and as database records (fast queries). The sync complexity is real — eventual consistency issues are possible — but the flexibility is worth it. Future plan: DB-first with a UI editor.

**60-second polling**: Wastes CPU checking when nothing is due. Dynamic sleep would be more efficient but harder to test and handle edge cases. For a scheduler with hour-or-day intervals, the overhead is negligible.

**Playwright vs Requests**: Both are used. Playwright for JavaScript-rendered sites and authenticated access, requests+BeautifulSoup for simple static HTML. Not every page needs a headless browser.

**Context analysis scope**: Currently analyzes titles, abstracts, and tags. Full-text analysis would be richer but much slower and more expensive.

---

## Future Work

- **Semantic deduplication**: Use embeddings for similarity instead of just DOI/title matching. Would catch cases where the same research appears under different titles.
- **Adaptive rate limiting**: Dynamically adjust rates based on API responses (429 headers, retry-after hints) instead of fixed limits.
- **Distributed discovery**: Multiple workers with Redis-based locking so only one worker runs a given source at a time.

---

*Last Updated: February 2026*
