# Multi-Agent Framework – Commit-by-Commit Upgrade Plan

> This roadmap converts the current Thoth codebase into an **optionally enabled multi-agent platform** _and_ wires that capability into the Obsidian UI.  Each commit is atomic, passes existing tests, and keeps `multi_agent = false` as the default until the final release toggle.

## TL;DR Commit Table

| # | Commit Title | Key Changes | Main Touchpoints |
|---|--------------|-------------|------------------|
| 1 | **chore(core): scaffold agents package & pydantic Task models** | Create `thoth/agents/` package, add `BaseAgent`, `Task`, `Result` schemas; update `pyproject.toml`. | `src/thoth/agents/` + `pyproject.toml` |
| 2 | **feat(core): in-process event bus & orchestrator skeleton** | `EventBus` (asyncio Queue), `Orchestrator` that executes a simple linear list of tasks. | `agents/orchestrator.py`, tests |
| 3 | **feat(executive): GoalPlannerAgent (LLM) v1** | Prompt templates + minimal task graph planner for PDF processing goal. | `agents/executive/planner.py`, `prompts/` |
| 4 | **feat(critic): EvaluationAgent (LLM) v1** | Computes faithfulness/relevance score; publishes `EVALUATION` result. | `agents/critic/evaluator.py` |
| 5 | **feat(worker): wrap ProcessingService -> DocumentProcessorAgent** | Thin adapter chooses backend (`service` vs `mcp`). | `agents/worker/document_processor.py` |
| 6 | **feat(worker): CitationMinerAgent** | Adapter for `citation` service/tools. | `agents/worker/citation_miner.py` |
| 7 | **feat(worker): TagCuratorAgent & KnowledgeGraphAgent** | Adapters for `tag` & `article` services. | `agents/worker/` |
| 8 | **refactor(pipeline): delegate to orchestrator when flag set** | Add `multi_agent` flag to config; modify `ThothPipeline` & `PDFTracker` to enqueue tasks. | `pipeline.py`, `server/`, `utilities/config.py` |
| 9 | **feat(core): MCP backend option for worker agents** | `backend_mode` arg; default `mcp`; adds `MCPClient` pooling util. | `agents/worker/base_backend.py` |
|10 | **feat(core): RedisStreamEventBus & Ray remote actors** | Toggle via `orchestrator_mode = distributed`. | `agents/event_bus/redis_bus.py`, `docker-compose.yml` |
|11 | **test(agents): integration tests for orchestrator DAG** | Spin up orchestrator w/ workers; process sample PDF; assert outputs. | `tests/agents/` |
|12 | **docs(core): developer guide & architecture diagrams** | `docs/multi_agent.md`, update README badges. | `docs/` |
|13 | **feat(cli): `thoth agents run` & FastAPI `/v2/agents/run`** | CLI subcommand + API route streaming progress events. | `cli/`, `server/` |
|14 | **feat(obsidian): plugin setting toggle + progress panel scaffold** | Add `Enable multi-agent` switch; create sidebar view for task progress. | `obsidian-plugin/*/src/ui/AgentPanel.tsx`, `manifest.json` |
|15 | **feat(obsidian): websocket/SSE client for `/v2/agents/run`** | Re-use existing fetch wrapper; show live task updates with status icons. | `obsidian-plugin/*/src/utils/api.ts` |
|16 | **refactor(obsidian): command palette actions** | `Run multi-agent analysis on current note/PDF`. | `obsidian-plugin/*/src/commands.ts` |
|17 | **test(obsidian): cypress e2e for multi-agent flow** | Start Thoth API in CI, run plugin tests. | `obsidian-plugin/*/tests/` |
|18 | **chore(release): flip default `multi_agent=true` + changelog** | Remove beta flag, bump version to `vX.Y.0`. | `utilities/config.py`, `CHANGELOG.md` |

## Detailed Breakdown

### Commit 1 – *chore(core): scaffold agents package & pydantic Task models*
1. `mkdir src/thoth/agents` with `__init__.py` exporting `Task`, `Result`, `BaseAgent`.
2. Add to `pyproject.toml`:
   ```toml
   [tool.poetry.dependencies]
   pydantic = "^2.7"
   ```
3. Ensure import redirection `from thoth.agents import Task` works project-wide.
4. CI: run `poetry install` to lock deps.

### Commit 2 – *feat(core): in-process event bus & orchestrator skeleton*
1. `EventBus` implemented with `asyncio.Queue` + `publish()`/`subscribe()`.
2. `Orchestrator.run(goal: str)` builds list `[Task(type="PROCESS_PDF", …)]` directly (hard-coded for now).
3. Add `tests/agents/test_orchestrator_basic.py` asserting task executed.

### Commit 3 – *GoalPlannerAgent v1*
1. Create `prompts/planner_v1.md` describing JSON schema.
2. Use `llm_service.chat(...)` to produce Task list from goal text; fallback to default list on LLM failure.

### Commit 4 – *EvaluationAgent v1*
1. Prompt includes expected citations, tags.
2. Publishes `EVALUATION_FAILED` when hallucination probability >0.5.
3. Metrics pushed to `thoth.monitoring` (`prometheus_client.Counter`).

### Commit 5 – *DocumentProcessorAgent*
1. Constructor: `backend_mode: Literal["service", "mcp"]="mcp"`.
2. For `service` mode, accept `ServiceManager`.

### Commit 6 – *CitationMinerAgent*
Similar pattern; uses `client.citation.extract(pdf_path=…)`.

### Commit 7 – *TagCuratorAgent & KnowledgeGraphAgent*
1. `TagCuratorAgent` calls `tag.consolidate_and_suggest(...)`.
2. `KnowledgeGraphAgent` writes edges via `citation_service.add_relationship(...)`.

### Commit 8 – *Pipeline delegation*
1. Load `multi_agent` value in `get_config()`.
2. `DocumentPipeline.process_pdf()` becomes:
   ```python
   if self.config.multi_agent:
       return self.orchestrator.enqueue_pdf(pdf_path)
   else:
       return self._legacy_process(pdf_path)
   ```
3. `PDFTracker` enqueues task instead of calling directly.

### Commit 9 – *MCP backend*
1. Add `agents/backends/mcp_backend.py` wrapping `MCPClient` with retry.
2. Update all worker agents to call `self.backend.do_xyz(...)`.

### Commit 10 – *Redis & Ray*
1. New `RedisStreamEventBus` (uses `aioredis`).
2. Create `ray_utils.py` to register each agent as a Ray remote actor.
3. `orchestrator_mode` config flag decides runtime.

### Commit 11 – *Integration tests*
1. Use `pytest-asyncio`; spin up orchestrator + agents in `asyncio`.
2. Process sample `tests/fixtures/sample.pdf`; assert note generated.

### Commit 12 – *Documentation*
1. Mermaid diagrams in `docs/multi_agent.md`.
2. Update README quick-start with `thoth pipeline --multi-agent`.

### Commit 13 – *CLI & API*
1. CLI: `thoth agents run "goal.md" --backend=mcp`.
2. FastAPI: `/v2/agents/run` returns Server-Sent Events with JSON `Result` messages.

### Commit 14 – *Obsidian plugin settings & panel*
1. Add checkbox **Enable Thoth Multi-Agent** in settings tab.
2. New React/Preact component `AgentProgressView` registering with workspace sidebar.

### Commit 15 – *Websocket/SSE client*
1. `api.ts` adds `connectMultiAgent(goal)` that opens SSE to server.
2. Incoming messages update `AgentProgressView` state.
3. Display status icons (⚙️ running, ✅ done, ❌ failed).

### Commit 16 – *Command palette actions*
1. Register commands:
   * *Run Multi-Agent Analysis on Active Note* – extracts file path, calls `connectMultiAgent`.
   * *Show Agent Progress Panel* – toggles sidebar.

### Commit 17 – *Plugin e2e tests*
1. Use Cypress + `obsidian-dataview` mock vault.
2. Run Thoth API via `docker-compose` with Redis; ensure UI shows tasks progressing.

### Commit 18 – *Release toggle & changelog*
1. Change default `multi_agent = true` in template config.
2. Add migration note: users can revert via `multi_agent=false`.
3. Tag release `vX.Y.0`.

---

## Obsidian Integration Notes
* **Transport** – Use the same FastAPI `/v2/agents/run` SSE endpoint. Plugin keeps no state; all progress updates originate server-side.
* **Vault Path Handling** – For PDFs stored inside vault, plugin sends absolute file path; server still writes notes into existing `notes_dir`, which the plugin already watches.
* **Backward Compatibility** – If multi-agent disabled server-side, endpoint falls back to legacy `ThothPipeline` and sends a single `COMPLETE` event—UI handles gracefully.

---

This commit plan ensures a *green-build* journey from the current monolithic pipeline to a fully orchestrated multi-agent platform, with a polished Obsidian UX that exposes task progress and maintains seamless compatibility with existing workflows.