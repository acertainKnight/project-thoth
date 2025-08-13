# Epic: DuckDuckGo Search-Engine Integration & Agent Operability

This document is the authoritative blueprint for the pull-request series that adds DuckDuckGo-based discovery, exposes it through the MCP agent tools, and avoids code duplication.

---

## Legend
| Emoji | Meaning |
|-------|---------|
| 🛠️ | Code change |
| 🧪 | Automated test |
| 📜 | Documentation |
| ✅ | Proof / acceptance criterion |

Each **commit** below is independent, small, and passes CI on its own.

---

## Commit 01 ▸ Add planning document (this file)
* 🛠️  Create `planning/duckduckgo_discovery_plan.md`
* 📜  Document scope, rationale, and phased commits.
* ✅  PR shows this file rendered in GitHub.

---

## Commit 02 ▸ Extend Schemas for Search-Engine Sources
* 🛠️  File: `src/thoth/utilities/schemas.py`
  * Add `'search_engine'` to `DiscoverySource.source_type` enum.
  * Introduce optional fields:
    ```python
    engine: Literal['duckduckgo'] | None = None
    time_filter: Literal['day', 'week', 'month'] | None = None
    safe_search: Literal['off', 'moderate'] | None = 'moderate'
    ```
* 🧪  New unit test `tests/discovery/test_schema_search_engine.py`
  * Assert that model validates when `source_type='search_engine'` and `engine='duckduckgo'`.
* ✅  `pytest -k search_engine` green.

---

## Commit 03 ▸ Introduce `BaseSearchEngineSource` & `DuckDuckGoSearchSource`
* 🛠️  File: `src/thoth/discovery/api_sources.py`
  * Add abstract `BaseSearchEngineSource(BaseAPISource)`.
  * Implement concrete `DuckDuckGoSearchSource` using official Instant-Answer JSON endpoint with retry/back-off.
* 🧪  `tests/discovery/test_duckduckgo_source.py`
  * Use `vcr.py` to record fixture for query "large language models".
  * Assert ≥1 `ScrapedArticleMetadata` returned, each has `source='duckduckgo'`.
* ✅  Test passes offline via cassette; coverage diff ≥90% for new code.

---

## Commit 04 ▸ Register DuckDuckGo in `DiscoveryManager`
* 🛠️  File: `src/thoth/discovery/discovery_manager.py`
  * In `__init__`, extend `self.api_sources` dict: `'duckduckgo': DuckDuckGoSearchSource()`
* 🧪  Extend `tests/discovery/test_discovery_manager.py`
  * Create temp `DiscoverySource(source_type='search_engine', engine='duckduckgo', api_config={"query":"gpt"})` and call `_discover_from_api`.
  * Assert list not empty.
* ✅  Manager test green.

---

## Commit 05 ▸ Enhance Deduplication & Scoring
* 🛠️  File: `src/thoth/discovery/discovery_manager.py`
  * In `_filter_and_process_articles`, add URL SHA-256 bloom filter to eliminate duplicates across runs.
  * Compute simple relevance score (freshness + keyword match) and sort.
* 🧪  `tests/discovery/test_dedup_score.py`
  * Feed duplicates, assert only unique remain and score key exists.
* ✅  Test passes; existing unit tests unaffected.

---

## Commit 06 ▸ Extend MCP Discovery Tools – Create & Preview DuckDuckGo Sources
* 🛠️  File: `src/thoth/mcp/tools/discovery_tools.py`
  * Add `CreateDuckduckgoSourceMCPTool` (pattern matching `CreateArxivSourceMCPTool`).
  * Add `PreviewDuckduckgoQueryMCPTool` for ad-hoc search without persistence.
  * Update `RunDiscoveryMCPTool` to allow in-memory source when `source_name` absent but `engine` provided.
* 🧪  `tests/mcp/test_duckduckgo_tools.py`
  * Simulate create call; assert success message.
  * Simulate preview call; assert content list contains at least 1 URL.
* ✅  Tools register in `mcp.tools.__init__`; agent can `import` without error.

---

## Commit 07 ▸ Update CLI Help & Docs
* 🛠️  File: `src/thoth/cli/discovery.py` (or equivalent)
  * Add `duckduckgo` sub-command examples.
* 📜  `docs/discovery/duckduckgo.md` with usage patterns.
* 🧪  CLI e2e test in `tests/cli/test_duckduckgo_cli.py` using `CliRunner`.
* ✅  `thoth discovery new --engine duckduckgo --query "transformers"` completes 0-exit in test env.

---

## Commit 08 ▸ Scheduler Regression – Ensure Search-Engine Sources Run
* 🛠️  File: `src/thoth/discovery/scheduler.py`
  * No code change expected (uses polymorphism) but add guard for `search_engine`.
* 🧪  `tests/discovery/test_scheduler_duckduckgo.py`
  * Mock time, create scheduled `duckduckgo` source, run one loop, assert `last_run` updated.
* ✅  Scheduler unit test green.

---

## Commit 09 ▸ Prometheus Metrics for Search-Engine Queries
* 🛠️  File: `src/thoth/monitoring/metrics.py`
  * Increment `discovery_queries_total{source="duckduckgo"}`.
* 🧪  `tests/monitoring/test_metrics.py`
  * Ensure counter increments after simulated search.
* ✅  `prometheus_client` exposition shows new metric via HTTP scrape.

---

## Commit 10 ▸ Finalize Changelog & Bump Version
* 📜  Update `CHANGELOG.md` with "Added DuckDuckGo search-engine discovery".
* 🛠️  Bump minor version in `pyproject.toml`.
* ✅  Tag `vX.Y+1`; all CI jobs green → merge PR.

---

## Final Proof of Completion
1. **Integration script** (`scripts/demo_duckduckgo_discovery.py`) runs end-to-end: creates source, scheduler executes, articles stored, results printed.
2. GitHub PR conversation shows ✅ from all checks (lint, mypy, unit tests, coverage > 85%).
3. Reviewer can execute `thoth discovery preview-duckduckgo --query "graph neural networks"` and see non-empty result set.

---

*Total added LOC (est.):* ~700 **(including tests)**

*Estimated calendar time:* 3–4 dev days + 1 day review/buffer.