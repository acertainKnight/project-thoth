# Letta Memory Integration PR – Commit-by-Commit Plan

> Goal: Upgrade Thoth’s memory system to use Letta **in-process** (no external server) while keeping the architecture multi-agent ready.

---

## Overview
The implementation will be delivered as a single Pull Request consisting of **12 atomic commits**. Each commit is self-contained, passes existing tests, and introduces incremental functionality or refactorings. The order is designed to keep CI green at every step and simplify code review.

| # | Commit Title | Purpose / Key Changes | Touchpoints |
|---|--------------|-----------------------|-------------|
| 1 | **chore: add Letta dependency & scaffold** | • Add `letta>=0.9` to `pyproject.toml` / `requirements.txt`  <br>• Generate initial Alembic migration for `memory` table  <br>• Create `thoth/memory/` package | *build*, *deps*, *migrations* |
| 2 | **feat(core): introduce MemoryStore adapter** | • Implement `ThothMemoryStore` subclass wrapping `letta.memory.MemoryStore`  <br>• Expose simple CRUD interface used by agents | `thoth/memory/store.py`, `thoth/core/__init__.py` |
| 3 | **feat(core): share MemoryStore across agents** | • Instantiate `shared_store` in `thoth.bootstrap`  <br>• Inject into Agent factory (`make_agent`)  <br>• Update existing unit tests with fixture | `thoth/bootstrap.py`, tests |
| 4 | **feat(memory): write pipeline (before_write hook)** | • Override `before_write` to compute salience + metadata (tenant, user, agent)  <br>• Add `SalienceScorer` util  <br>• Unit tests for scoring thresholds | `thoth/memory/hooks.py`, tests |
| 5 | **feat(memory): retrieval pipeline (after_retrieve hook)** | • Override `after_retrieve` to log retrieval quality metrics  <br>• Add `RetrievalLogger` util (writes to `prometheus` counter) | `thoth/memory/hooks.py`, `thoth/metrics.py` |
| 6 | **feat(memory): episodic summariser job** | • Background async job triggered on `on_task_complete`  <br>• Uses Letta summarisation API to condense core→episodic memories  <br>• Schedule via existing `scheduler` | `thoth/memory/jobs.py` |
| 7 | **feat(memory): discovery source creation pipeline** | • Listener on conversation events to detect new URIs  <br>• Adds row to `DiscoverySource` + enqueues crawler task  <br>• Integrate with MemoryStore | `thoth/discovery/`, `thoth/memory/store.py` |
| 8 | **feat(cli): /memory command & user redaction** | • Extend CLI / chat UI with `/memory list`, `/memory forget <id>`  <br>• Implement hard-delete cascade in MemoryStore | `thoth/cli.py`, `thoth/memory/store.py` |
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

### Commit 2 – *feat(core): introduce MemoryStore adapter*
- File `thoth/memory/store.py`
  ```python
  from letta.memory import MemoryStore
  class ThothMemoryStore(MemoryStore):
      # custom helper methods here…
  ```
- Add typing stubs & docstrings.

### Commit 3 – *share MemoryStore across agents*
- Edit `thoth/bootstrap.py`:  
  ```python
  from thoth.memory.store import ThothMemoryStore
  shared_store = ThothMemoryStore("sqlite:///thoth.db", vector_backend="chromadb")
  ```
- Param-inject into all Agent constructors.

### Commit 4 – *write pipeline*
- New util `thoth/memory/salience.py` with heuristic & ML model fallback.
- Hook registration in `hooks.py`.

### Commit 5 – *retrieval logging*
- Add `metrics.py` exposing Prometheus counters: `memory_retrieval_hits`, `memory_retrieval_misses`.

### Commit 6 – *episodic summariser job*
- Cron job every hour converts stale core → episodic summarising via Letta’s summarise API.

### Commit 7 – *discovery source pipeline*
- New module `thoth/discovery/listener.py` capturing URI regexes.

### Commit 8 – *CLI memory commands*
- Update command parser; interactive output with colors.

### Commit 9 – *integration tests*
- New `pytest` fixtures for in-memory DB + monkeypatch embeddings.

### Commit 10 – *docs*
- Architecture diagram generated via Mermaid.

### Commit 11 – *CI updates*
- Ensure `alembic upgrade head` runs before tests.

### Commit 12 – *cleanup*
- Remove obsolete `.memory` references; run linters.

---

## Rollback Strategy
- Each commit is isolated; revert sequence from 12 → 1 if needed.
- Database migrations are reversible via Alembic downgrade.

## Acceptance Criteria
- All existing tests pass plus new memory tests.
- `/memory list` returns at least one stored memory after interaction in demo session.
- Retrieval hit-rate ≥60% on synthetic benchmark.

## Post-Merge Follow-Ups (Not in Scope of PR)
1. Switch vector backend to pgvector in staging.
2. Add voice mode memory integration.
3. Evaluate advanced salience ML model.

---

_Authored by: **@yourname**  •  Date: 2025-08-04_