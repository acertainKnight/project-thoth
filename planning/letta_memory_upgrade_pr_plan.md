# Letta Memory Integration PR – Commit-by-Commit Plan

> Goal: Upgrade Thoth’s memory system to use Letta **in-process** (no external server) while keeping the architecture multi-agent ready.

---

## Overview
The implementation will be delivered as a single Pull Request consisting of **12 atomic commits**. Each commit is self-contained, passes existing tests, and introduces incremental functionality or refactorings. The order is designed to keep CI green at every step and simplify code review.

| # | Commit Title | Purpose / Key Changes | Touchpoints |
|---|--------------|-----------------------|-------------|
| 1 | **chore: add Letta dependency & scaffold** | • Add `letta>=0.9` to `pyproject.toml` / `requirements.txt`  <br>• Generate initial Alembic migration for `memory` table  <br>• Create `thoth/memory/` package | *build*, *deps*, *migrations* |
| 2 | **feat(core): introduce MemoryStore & LangGraph adapter** | • Add `thoth/memory/store.py` wrapping `letta.memory.MemoryStore`  <br>• Add `thoth/memory/checkpointer.py` implementing LangGraph `BaseSaver` interface to bridge Letta ↔ LangGraph (replaces `MemorySaver`)  <br>• Ensure API parity (`get`, `put`, `exists`, `list`) | `src/thoth/memory/` |
| 3 | **refactor(agent_v2): wire LettaMemory into research agents** | • Inject `shared_store` via new optional param in `create_research_assistant*` factories  <br>• Replace `MemorySaver()` with `LettaCheckpointer(shared_store)` in `_build_graph`  <br>• Fallback to in-memory store when `enable_memory=False` | `ingestion/agent_v2/core/agent.py`, `ingestion/agent_v2/server.py`, `cli/agent.py` |
| 4 | **feat(memory): write pipeline (before_write hook)** | • Override `before_write` to compute salience + metadata (tenant, user, agent)  <br>• Add `SalienceScorer` util  <br>• Unit tests for scoring thresholds | `thoth/memory/hooks.py`, tests |
| 5 | **feat(memory): retrieval pipeline (after_retrieve hook)** | • Override `after_retrieve` to log retrieval quality metrics  <br>• Add `RetrievalLogger` util (writes to `prometheus` counter) | `thoth/memory/hooks.py`, `thoth/metrics.py` |
| 6 | **feat(memory): episodic summariser job** | • Schedule async job in existing `thoth.monitoring.scheduler` (no new scheduler duplicate)  <br>• Implement summariser in `thoth/memory/jobs.py` | `thoth/monitoring/scheduler.py`, `thoth/memory/jobs.py` |
| 7 | **feat(discovery): auto-create sources from chat context** | • Extend `thoth/discovery/discovery_manager.py` with `detect_new_sources()` called by chat hook  <br>• Use regex detection logic (previously non-existent)  <br>• Store to MemoryStore *and* existing DB model for sources | `thoth/discovery/discovery_manager.py`, `thoth/memory/store.py` |
| 8 | **feat(cli): /memory command & user redaction** | • Add new subparser in `thoth/cli/agent.py` (to avoid extra CLI module)  <br>• Command delegates to `ThothMemoryStore` for list/forget | `thoth/cli/agent.py` |
| 9 | **test(memory): add integration tests** | • Spin up in-memory SQLite + Chroma  <br>• End-to-end test: write → summarise → retrieve flow  <br>• Coverage >90% for new modules | `tests/memory/` |
|10 | **docs: developer guide for Letta memory** | • Add `docs/memory.md` with architecture diagrams  <br>• Update README quick-start with `pip install letta` step | `docs/` |
|11 | **chore(ci): ensure migrations & background jobs** | • Update GitHub Actions to run `alembic upgrade head`  <br>• Add `coverage run -m pytest`  <br>• Execute scheduler jobs during CI for smoke-test | `.github/workflows/ci.yml` |
|12 | **refactor: rename legacy memory modules & clean-up** | • Remove deprecated `old_memory.py`  <br>• Update imports  <br>• Apply `black` & `isort` | various |

---

## Detailed Commit Breakdown

### Commit 1 – *chore: add Letta dependency & scaffold*
1. Modify dependency files:  
   ```toml
   letta = ">=0.9,<1.0"
   ```
2. Create Alembic revision `20250804_add_memory_table.py` based on schema in plan.  
3. New package `thoth/memory/__init__.py` (empty placeholder).

### Commit 2 – *feat(core): introduce MemoryStore & LangGraph adapter*
- File `thoth/memory/store.py`
  ```python
  from letta.memory import MemoryStore as _LettaStore
  
  class ThothMemoryStore(_LettaStore):
      """Thin wrapper adding convenience helpers and enforcing Thoth namespaces."""
  ```
- File `thoth/memory/checkpointer.py`
  ```python
  from langgraph.checkpoint.base import BaseSaver
  from .store import ThothMemoryStore
  
  class LettaCheckpointer(BaseSaver):
      def __init__(self, store: ThothMemoryStore):
          self.store = store
      # implement put/get/exists as thin calls to store
  ```
- Add `shared_store` singleton in `thoth/memory/__init__.py` for easy import.

### Commit 3 – *refactor(agent_v2): wire LettaMemory into research agents*
1. Update `src/thoth/ingestion/agent_v2/core/agent.py`:
   - Inject new parameter `memory_store: ThothMemoryStore | None = None` in `__init__`.
   - Use `memory_store or shared_store`.
   - Replace `MemorySaver()` with `LettaCheckpointer(memory_store)`.
2. Propagate param through factory functions in `agent_v2/core/agent.py` and `server.py`.
3. Update CLI `thoth/cli/agent.py` to allow `--memory-off` flag to disable globally.

### Commit 4 – *feat(memory): write pipeline (before_write hook)*
1. Create `thoth/memory/hooks.py` with `def before_write(item): ...`.
2. Register hook inside `ThothMemoryStore.__init__` via `self.register_before_write(...)`.
3. `SalienceScorer` heuristics:
   - +5 if role == 'user' and length > 30 words
   - +3 if contains keywords from active tasks
   - degrade by recency.
4. Unit tests: confirm low-salience items are dropped.

### Commit 5 – *feat(memory): retrieval pipeline (after_retrieve hook)*
1. Extend `thoth/memory/hooks.py` with `after_retrieve` to push Prometheus counters.
2. Add `thoth/metrics.py` exposing `Counter` via `prometheus_client`.
3. Integration: hook registered in `ThothMemoryStore`.

### Commit 6 – *feat(memory): episodic summariser job*
1. Add `thoth/memory/jobs.py`:
   ```python
   async def summarise_core_to_episodic(store: ThothMemoryStore):
       items = store.query(scope='core', older_than=timedelta(hours=6))
       summary = await store.llm.summarise(items)
       store.write(scope='episodic', role='system', content=summary)
   ```
2. Modify `thoth/monitoring/scheduler.py` to schedule hourly.

### Commit 7 – *feat(discovery): auto-create sources from chat context*
1. In `discovery_manager.py`, add:
   ```python
   def detect_new_sources(self, messages: list[str]):
       for url in URL_REGEX.findall("\n".join(messages)):
           if not self.source_exists(url):
               self.create_source(url)
               memory_store.write(scope='core', role='system', content=f'Added source {url}')
   ```
2. Call `detect_new_sources` from `ResearchAssistant._agent_node` right after receiving user message.

### Commit 8 – *feat(cli): /memory command & user redaction*
1. Augment existing `agent` CLI subparser:
   - `thoth agent memory list`
   - `thoth agent memory forget <id>`
2. Implementation calls methods on `ThothMemoryStore`.

### Commit 9 – *test(memory): add integration tests*
- Create `tests/memory/test_memory_flow.py` covering:
  - write -> retrieve
  - summarisation job creates episodic entries
  - redaction deletes data

### Commit 10 – *docs*
- `docs/memory.md` includes:
  - Explanation of Letta layers (core, episodic, archival)
  - How to query memory via CLI/API

### Commit 11 – *CI updates*
- Update workflow to spin up `chromadb` in-memory server for tests (no Docker required).
- Ensure `prometheus_client` installed.

### Commit 12 – *cleanup*
- Delete `langgraph.checkpoint.memory` imports, update references.
- Run `pre-commit run --all-files`.

---

## Rollback Strategy
- Each commit is independent; if issue arises, revert last commit.
- Alembic generates down revision for schema.

## Acceptance Criteria
1. All unit & integration tests pass.
2. Memory enabled by default; disabling flag works.
3. Chat session persists across restarts (SQLite persistence).
4. `/memory list` shows memories; retrieval metrics accessible at `/metrics` endpoint.

## Compatibility Checks
- No existing module named `thoth.memory` → safe to create.
- We reuse `thoth/discovery/discovery_manager.py` instead of new listener → avoids duplication.
- We rely on existing `thoth.monitoring.scheduler` for jobs → no duplicate scheduler logic.

## Post-Merge Follow-Ups
- Evaluate using pgvector back-end in staging.
- Experiment with Letta ADE once multi-tenant cloud version is planned.

---
_Authorized by @yourname – 2025-08-04_
