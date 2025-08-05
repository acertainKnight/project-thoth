## Thoth Multi-Agent Framework Upgrade Plan

> **Goal:** Transform Thoth from a primarily monolithic service-oriented pipeline into an *optionally enabled* multi-agent research platform inspired by the **ASI-Arch** paradigm. The new architecture should allow specialised agents (workers) to collaborate autonomously on complex research tasks while remaining 100 % backward-compatible with the current single-process workflow.

---

### 1. Strategic Objectives

1. **Horizontal Scalability & Concurrency** – Run multiple research tasks (OCR, citation mining, RAG, etc.) in parallel to reduce wall-clock time.
2. **Fault Isolation** – Failures inside one specialised agent must not crash the entire pipeline; instead, orchestrator can retry or reroute.
3. **Composable Workflows** – Researchers should be able to plug in/remove agents (e.g., a new `GraphAnalyticsAgent`) without core changes.
4. **Observability & Self-Evaluation** – Each agent exposes metrics, logs, and a self-critique channel for continuous improvement.
5. **Full Backwards Compatibility** – `thoth pipeline …` continues to work unchanged when `multi_agent = false` (default).

---

### 2. ASI-Arch Cheat-Sheet (for Context)

| Layer | Purpose | Typical Components |
|-------|---------|--------------------|
| **Executive** | High-level goal decomposition, planning | *Planner*, *Supervisor* |
| **Specialist** | Domain-specific reasoning & tool usage | *Researcher*, *Coder*, *Reviewer* |
| **Worker** | Deterministic execution, data movement | *Crawler*, *Vectoriser*, *DatabaseWriter* |
| **Critic** | Quality control & feedback loops | *Evaluator*, *Red-teamer* |

Thoth already has rich *services* that map nicely onto **Worker** roles. The upgrade will introduce explicit **Planner / Critic** agents and wrap existing services in **Specialist** agents.

---

### 3. Proposed Agent Taxonomy for Thoth

| Agent Name | ASI-Arch Layer | Primary Duties | Underlying Service(s) | Parallelism |
|------------|----------------|----------------|-----------------------|-------------|
| `GoalPlannerAgent` | Executive | Break user goal (CLI/HTTP) into task graph | — (Reasoning only) | 1 (singleton) |
| `DocumentProcessorAgent` | Specialist | OCR → markdown → semantic chunking | `processing`, `llm` | N (CPU-bound) |
| `CitationMinerAgent` | Specialist | Extract citations & build edges | `citation`, `llm`, `pdf_locator` | N |
| `TagCuratorAgent` | Specialist | Consolidate & suggest tags | `tag`, `llm` | N |
| `KnowledgeGraphAgent` | Specialist | Persist graph, run analytics | `citation`, `article` | 1-N (depends) |
| `RAGRetrieverAgent` | Specialist | Embed + query vector store | `rag`, `web_search` | N |
| `DiscoveryAgent` | Worker | Periodic web/DB crawling for new PDFs | `discovery`, `api_gateway` | N (scheduled) |
| `MemoryManagerAgent` | Worker | Persist episodic/archival memory via Letta | `cache` (opt.), `database` | 1 |
| `EvaluationAgent` | Critic | Score outputs, detect hallucinations | `llm` | N |

> **Note:** Each *Specialist* is a thin wrapper that converts high-level `Task` objects into *service* calls, preserving existing Thoth code.

---

### 4. High-Level Architecture Diagram
```
┌────────────────────┐               ┌────────────────────────────┐
│  CLI / FastAPI     │──User Goal──▶│  GoalPlannerAgent          │
└────────────────────┘               └────────────────────────────┘
                                          │Task Graph
                                          ▼
                               ┌──────────────────────────┐
                               │   Agent Orchestrator     │ (LangGraph / Ray DAG)
                               └──────────┬───────────────┘
                     ┌────────────────────┼─────────────────────┐
                     ▼                    ▼                     ▼
          DocumentProcessorAgent  CitationMinerAgent   DiscoveryAgent …
                     │                    │                     │
                     ▼                    ▼                     ▼
           processing.service     citation.service      discovery.service
                     │                    │                     │
                     ▼                    ▼                     ▼
               Shared Memory / Event Bus (Redis Streams or pydantic-encoded Kafka)
                     │
                     ▼
             EvaluationAgent (Critic) → feedback → Orchestrator
```
*Agents run in separate asyncio tasks or Ray actors; communication via event bus ensures decoupling.*

---

### 5. Communication & Data Contracts

1. **Task Envelope** – Pydantic model
   ```python
   class Task(BaseModel):
       id: UUID
       goal: str
       type: Literal[
           "PROCESS_PDF", "EXTRACT_CITATIONS", "SUGGEST_TAGS", …
       ]
       payload: dict
       parent_id: UUID | None
       created_at: datetime
   ```
2. **Result Envelope** – Contains `task_id`, `status`, `output`, `metrics`.
3. **Pub/Sub Layer** – Initial prototype uses `asyncio.Queue`; prod mode toggles to Redis Stream.
4. **Back-pressure & Retries** – Orchestrator monitors queue depth; idempotent tasks implement exponential backoff.

---

### 6. Detailed Module Design

#### 6.1 `thoth/agents/base.py`
*   `class BaseAgent(ABC)` – defines `subscribe()`, `process(task)`, `publish(result)`.
*   Handles structured logging, tracing ID propagation, and graceful shutdown.

#### 6.2 `thoth/agents/registry.py`
*   Auto-discovers subclasses via entry points (`thoth_agents` group) so third-party plugins can inject agents.

#### 6.3 `thoth/agents/orchestrator.py`
*   Builds a directed acyclic graph (DAG) of tasks returned by `GoalPlannerAgent`.
*   Uses **LangGraph** or **Ray DAG** for execution: each node is an *agent*, edges encode dependencies.
*   Offers two modes:
    1. **in_process** – pure asyncio (no external infra); suitable for local runs & unit tests.
    2. **distributed** – Ray cluster; tasks become *remote actors* enabling horizontal scaling.

#### 6.4 `thoth/agents/executive/planner.py`
*   LLM-powered chain: prompt = *“Break the following goal into atomic Thoth tasks …”*.
*   Emits TaskGraph → orchestrator.

#### 6.5 `thoth/agents/critic/evaluator.py`
*   Wraps `llm_service` to compute *faithfulness*, *relevance*, *toxicity* scores.
*   Stores metrics to Prometheus via `thoth.monitoring`.

#### 6.6 `thoth/agents/worker/*`
*   Each maps 1-to-1 with existing service modules; minimal glue code.

---

### 7. Config Flag & CLI Exposure

*   Add `multi_agent = false` in `[thoth]` section of `~/.thoth.toml` (default).
*   `thoth pipeline --multi-agent` or `thoth agent orchestrate goal.md` commands.
*   FastAPI route `POST /v2/agents/run` accepts JSON goal spec.

---

### 8. Backwards Compatibility Layer

1. **Facade Pattern** – Keep `ThothPipeline.process_pdf()` unchanged; internally it *delegates* to orchestrator when flag set.
2. **ServiceManager Re-use** – Agents import *existing* services; no duplication.
3. **Graceful Fallback** – If orchestrator detects only one agent registered it auto-switches to legacy sequential mode.

---

### 9. Observability & Monitoring

*   **Structured Logs** – `structlog + opentelemetry` headers per task.
*   **Metrics** – Per-agent latency, success_rate, tokens_consumed; export via Prometheus.
*   **Tracing** – Jaeger spans from Planner → Worker → Critic.

---

### 10. Implementation Roadmap (14 Commits)

| # | Commit Title | Key Changes |
|---|--------------|-------------|
| 1 | **chore: create thoth/agents package & BaseAgent** | Scaffold, update `pyproject.toml` |
| 2 | **feat(core): Task & Result pydantic models** | `thoth/agents/schemas.py` |
| 3 | **feat(core): in-process Orchestrator (asyncio)** | Can execute trivial DAG with echo agent |
| 4 | **feat(exec): GoalPlannerAgent with LLM prompts** | Returns TaskGraph JSON |
| 5 | **feat(worker): wrap ProcessingService as DocumentProcessorAgent** | Utilises existing OCR logic |
| 6 | **feat(worker): wrap CitationService as CitationMinerAgent** | |
| 7 | **feat(worker): wrap TagService as TagCuratorAgent** | |
| 8 | **feat(worker): DiscoveryAgent & scheduler hook** | Re-uses monitoring scheduler |
| 9 | **feat(critic): EvaluationAgent** | Uses `llm_service` for QA |
|10 | **feat(core): Event Bus abstraction + Redis driver** | Toggle via config |
|11 | **refactor(pipeline): delegate to Orchestrator when `multi_agent=true`** | No API break |
|12 | **docs: update README & architecture diagrams** | New section “Running in Multi-Agent mode” |
|13 | **test: integration tests with in-process orchestrator** | Achieve ≥90 % coverage for agents |
|14 | **ci: spin up Redis in GitHub Actions for agent tests** | |

*CI stays green; each commit includes migrations & documentation.*

---

### 11. Risk Assessment & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Increased code complexity | Medium | Medium | Strict module boundaries, BaseAgent ABC |
| Token overhead from planner/critic LLM calls | High | Cost | Cache prompts; allow opt-out flags |
| Distributed mode deployment difficulty | Low | High | Provide Docker Compose & Helm charts |
| Orchestrator deadlocks | Low | Medium | Unit tests + watchdog timeouts |

---

### 12. Success Criteria

1. Processing 10 PDFs in parallel is ≥40 % faster on 8-core machine.
2. Single-flag opt-in without environment variable gymnastics.
3. All existing CLI commands pass unchanged test suite.
4. Prometheus shows per-agent metrics; Jaeger trace includes at least 3 layers.
5. Planner-Critic feedback loop improves citation extraction F1 by ≥5 % on benchmark dataset.

---

### 13. Appendix: Minimal Code Skeleton (Illustrative Only)
```python
# thoth/agents/base.py
class BaseAgent(ABC):
    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
    async def subscribe(self): ...
    async def process(self, task): ...
    async def publish(self, result): ...
```
```python
# thoth/agents/orchestrator.py
class Orchestrator:
    def __init__(self, mode: Literal["in_process", "distributed"] = "in_process"):
        self.event_bus = InMemoryBus() if mode == "in_process" else RedisBus()
    async def run(self, goal: str):
        graph = await GoalPlannerAgent().plan(goal)
        await self.execute(graph)
```
*Full code to be implemented in phased commits.*

---

### 14. Integration with the Rest of the Thoth Ecosystem

1. **CLI (`thoth/cli`)** – New sub-command `thoth agents run "<goal.md>"` maps to orchestrator.
2. **FastAPI Server (`thoth/server`)** – Add `/v2/agents` endpoints returning SSE task updates.
3. **Monitoring** – Extend `thoth/monitoring/dashboard.py` to group metrics by `agent_id`.
4. **Pipelines** – `DocumentPipeline` and `KnowledgePipeline` are decomposed but remain callable as utilities.
5. **Services** – No changes required; agents import them, leveraging existing configuration & dependency injection via `ServiceManager`.

> This detailed roadmap provides a clear, incremental path toward a powerful multi-agent Thoth while safeguarding stability and developer experience.

### 15. Existing Parallelism & MCP Tool Integration

#### 15.1 What Already Runs in Parallel
* **ProcessingService** – Uses a multiprocessing pool to OCR pages concurrently.
* **Citation extraction** – `CitationService` schedules asynchronous extraction tasks per reference.
* **Optimized AsyncProcessingService** – When installed, network-bound calls (LLM, OCR API) run concurrently via `asyncio.gather()`.
* **Monitoring Scheduler** – Background threads trigger discovery crawls, note regeneration, and PDF health checks on independent schedules.

> **Take-away:** The multi-agent layer _does not_ replace these optimisations; it _organises_ them under a common orchestration and observability umbrella.

#### 15.2 Leveraging MCP Tools inside Agents
Thoth’s **MCP (Modular Command Protocol)** already exposes almost every service as a tool—complete with transport abstraction, schema metadata, and centralised auth. Worker/Specialist agents therefore _wrap_ MCP calls rather than duplicating logic.

```python
class DocumentProcessorAgent(BaseAgent):
    async def process(self, task: Task):
        from thoth.mcp.client import MCPClient
        client = MCPClient()  # re-uses global connection pool
        return await client.processing.ocr_to_markdown(
            pdf_path=task.payload["pdf_path"],
            output_dir=self.config.output_dir,
        )
```

Advantages:
1. **Retry semantics & idempotency** are baked into MCP transports.
2. **Remote vs. local execution** becomes a config flag (`agent_backend = "mcp" | "service"`).
3. **Auto-generated docs & schemas** let the Planner introspect tool signatures when building task graphs.

#### 15.3 Best-Practice Guidelines
| Scenario | Recommended Backend | Rationale |
|----------|--------------------|-----------|
| I/O-bound, API-heavy, or retry-prone work | **MCP tool** | Unified transport, error handling, easy distribution |
| Ultra-low latency, tight Python object coupling | **Direct service call** | Avoids serialisation overhead |
| Unit tests / CI | **Service** (in-process) | Fast, no external deps |
| Distributed cluster | **MCP** | Enables Ray / container scaling |

*Worker agents should accept a constructor arg `backend_mode` and instantiate either a `ServiceManager` reference or an `MCPClient` accordingly.*

#### 15.4 PDF Monitoring Pathway Mapping
| Legacy Flow (single-agent) | Multi-Agent Flow |
|----------------------------|------------------|
| `PDFTracker` → `DocumentPipeline.process_pdf()` | `PDFTracker` → enqueue **PROCESS_PDF** task on orchestrator |
| Inline OCR, citation, tag steps | Orchestrator fans out to `DocumentProcessorAgent`, `CitationMinerAgent`, etc. |
| Sequential result handling | Agents publish results to event bus; Planner merges outcomes |

All file-system debouncing, heuristics, and safety checks stay in `PDFTracker`; only the callback changes.

---

This section clarifies how the **new orchestration layer coexists with—and capitalises on—the concurrency and tool ecosystem Thoth already possesses.**

#### 15.5 Procedural Methods & Back-Compatibility Snapshot
1. **First-class Task Objects** – The orchestrator wraps today’s implicit method calls (e.g., `process_pdf`) into explicit `Task` envelopes, adding IDs, metadata, retries, and tracing.
2. **Planner & Critic Roles** – New Executive/Critic agents reason *about* tasks (ordering, quality gates) rather than doing the work themselves, complementing but not altering existing service logic.
3. **Toggleable Distributed Execution** – All services still default to in-process calls, but the orchestrator can promote any agent to a Ray actor or container **without touching service code**.
4. **Hot-pluggable Agents** – To add a `GraphAnalyticsAgent` you just register an entry-point; no edits to `pipeline.py` or `ServiceManager` required.
5. **Elevated Observability** – Because every unit of work is now a `Task`, it carries a correlation ID through logs, Prometheus metrics, and Jaeger traces, giving you per-agent insights the current pipeline can’t surface.

These points distil the conceptual difference between the existing *parallel functions inside one process* and the proposed *coordinated micro-agents* model, reaffirming that legacy workflows (PDF monitoring, discovery, etc.) remain fully operational.