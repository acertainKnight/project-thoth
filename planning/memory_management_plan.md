## Thoth Memory Management Enhancement Plan

### 1. Objectives
- Integrate **Letta** (open-source agentic memory framework) to empower Thoth with dynamic, context-aware, and self-evolving memory capabilities.
- Enable Thoth to:
  1. Create and prioritise new discovery sources autonomously.
  2. Select and chain tools more intelligently based on memory and context.
  3. Persist, update, and prune memories about users, projects, topics, and research interests with minimal developer intervention.

### 2. Architectural Overview
```
+------------------+            +-------------------+
|    Thoth Core    |<----RPC--->|   Letta Adapter   |
+------------------+            +-------------------+
        |                                  |
        v                                  v
+------------------+            +-------------------+
| Skill/Tool Layer |            |  Memory Storage   |
+------------------+            +-------------------+
```
- **Letta Adapter**: A thin abstraction translating Thoth events (conversation turns, tool calls, file edits) into Letta’s memory APIs.
- **Memory Storage**: Pluggable (SQLite initially, later Postgres / vector DB) – exposes vector & relational queries.

### 2.5 Letta Memory Deep Dive
Letta’s architecture follows the *Memory Hierarchy* proposed in the MemGPT paper. Understanding these layers is critical for an efficient integration:

| Layer | Purpose | Volatility | Where it Lives |
|-------|---------|------------|----------------|
| **Context Window** | Tokens currently supplied to the LLM. Managed by Letta’s `ContextManager`. | Ephemeral (per prompt) | In-memory list of messages |
| **Short-Term/Core Memory** | Recent interactions maintained across prompts to preserve discourse coherence. | Session-scoped | `core_memory` table (JSONB) |
| **Episodic Memory** | Compact summaries of completed tasks/threads. | Weeks–Months | `episodic_memory` table + vector index |
| **Archival Memory** | Long-term facts, docs, and user preferences. | Months–Years | `archival_memory` table + vector index |

Key operations performed by Letta:
1. **Write**  → every new observation is *scored* (salience & novelty) before insertion.
2. **Retrieve**  → vector + metadata filters fetch top-K memories to hydrate the prompt.
3. **Summarise**  → scheduled job converts low-salience Core memories into Episodic summaries.
4. **Prune**  → TTL or size pressure removes oldest Archival entries after cascading summarisation.

> **Why it matters for Thoth**: By plugging into these lifecycle hooks we gain transparent, automatic memory management while retaining the ability to override any policy via custom scorer/retriever functions.

#### In-Process Integration Strategy (No Docker, Single Process)
- Use `pip install letta` and import `from letta.agent import Agent, Memory`.
- Instantiate one *shared* `Memory` object backed by SQLite/pgvector. Pass it to each `Agent` representing a Thoth sub-task.
- Avoid the Letta REST server until we migrate to a micro-service/cloud model; the code stays *inside* Thoth’s Python runtime.

```python
from letta.memory import MemoryStore
shared_store = MemoryStore("sqlite:///thoth_memory.db", vector_backend="chromadb")

def make_agent(name):
    return Agent(name=name, memory=shared_store)
```

#### Multi-Agent, Multi-User Namespacing
| Namespace | Description | Isolation Mechanism |
|-----------|-------------|---------------------|
| `tenant_id` | Top-level isolation (e.g., organisation) | Separate database file or schema |
| `user_id`   | End-user profile & preferences | Column in every memory row |
| `agent_id`  | Individual agent instance | Column + composite index |
| `scope`     | `core` / `episodic` / `archival` | Enum column |

*Queries* always filter by `tenant_id` and may join on `user_id`/`agent_id` depending on desired sharing semantics.

#### Letta Hooks We Will Extend
1. `before_write(memory_item)` – inject custom salience logic for Thoth-specific entities (e.g., code patches).
2. `after_retrieve(memory_items)` – log retrieval quality and feed metrics dashboard.
3. `on_task_complete(agent, task)` – auto-summarise and store to Episodic layer.

#### Minimal Storage Schema (SQLite)
```sql
CREATE TABLE memory (
  id INTEGER PRIMARY KEY,
  tenant_id TEXT,
  user_id TEXT,
  agent_id TEXT,
  scope TEXT,
  role TEXT,
  content TEXT,
  embedding BLOB,
  created_at DATETIME,
  metadata JSON
);
CREATE VIRTUAL TABLE memory_fts USING fts5(content, content="memory", tokenize="porter");
```
FTS5 provides full-text fallback when vector retrieval fails.

---

### 3. Memory Data Model
| Memory Type | Key Fields | TTL / Retention | Notes |
|-------------|-----------|-----------------|-------|
| `UserProfile` | user_id, persona_prefs, project_list | Infinity (manual prune) | Single row per user |
| `Project` | project_id, name, description, repo_url, tags | Active + 6 mo | Linked to UserProfile |
| `TopicInterest` | topic, relevance_score, last_interaction | Sliding window | Auto-decay |
| `DiscoverySource` | source_id, uri, type (rss, git, web), added_by, status | Active | Can be auto-created |
| `Observation` | text, embedding, timestamp, linked_entities | 90 days | Compressed to summary after TTL |

### 4. Discovery Source Creation
1. **Triggers**
   - User explicitly shares a link.
   - Repeated mention of an external resource (>3 times).
   - Missing data flagged during task execution (e.g., unknown API).
2. **Pipeline**
   - Validate URI → Classify type → Store in `DiscoverySource` → Queue crawler job → Summarise & embed results → Update memory.
3. **Governance**
   - Use relevance feedback (user corrections, success metrics) to disable noisy sources.

### 5. Tool Selection Strategy
- Maintain `ToolPerformance` memories (tool, context_signature, outcome_score).
- Feature inputs to Letta’s planner:
  - Current task embedding.
  - Historical success rates.
  - Resource availability (API quota, latency).
- Implement bandit algorithm (e.g., UCB) within memory to explore/exploit tools.

### 6. Memory CRUD Workflows
```
Event detected ─┬─► Retrieve relevant memories (vector & symbolic)
               ├─► Decide: create/update? (similarity & recency thresholds)
               ├─► If create: sanitize → embed → store
               └─► If update: merge fields, bump timestamps, decay scores
```
- **Pruning**: nightly job applies decay functions & compresses stale observations into summaries.
- **User Redaction**: user can issue "forget" command → hard delete chain of linked memories.

### 7. User-Centric Memories
- `UserProfile.persona_prefs` stores style (tone, verbosity), preferred file formats, etc.
- `SessionContext` ephemeral store keeps current conversation thread pointers.
- Surface a `/memory` command allowing users to inspect & correct stored info.

### 8. Security & Privacy
- Encrypt PII at rest.
- Sign memories with hash to detect tampering.
- Role-based access: only Thoth processes with proper token can query full memory; public endpoints expose redacted views.

### 9. Persistence Layer
- Phase 1: SQLite + Chroma for vector embeddings (local dev).
- Phase 2: PostgreSQL + pgvector in production.
- Abstraction via Letta’s storage driver interface.

### 10. Metrics & Evaluation
| Metric | Target |
|--------|--------|
| Recall of relevant memories | >85% |
| Tool selection success rate | +20% over baseline |
| Avg. user correction per 100 interactions | <2 |
| Memory store latency (p95) | <150 ms |

### 11. Implementation Roadmap
1. **Week 1-2 – Foundations**
   - Fork Letta ➞ integrate as sub-module.
   - Build Adapter with mock storage.
2. **Week 3-4 – Data Model & Storage**
   - Define schemas in ORM.
   - Implement vector store & embedding pipeline.
3. **Week 5 – Discovery Sources**
   - Create crawler micro-service.
   - Configure triggers.
4. **Week 6 – Tool Decision Layer**
   - Log tool outcomes.
   - Implement bandit selection.
5. **Week 7 – User Commands & UI**
   - `/memory` inspection & redaction.
   - Dashboard for metrics.
6. **Week 8 – Hardening & Deploy**
   - Load testing, security audit, CI pipeline.

### 12. Risks & Mitigations
- **Vector drift**: schedule re-embedding when model updates.
- **Memory bloat**: aggressive summarisation & TTL policies.
- **Privacy violations**: implement consent gating & redaction APIs.

### 13. Open Questions
- Preferred embedding model (OpenAI vs. open-source)?
- Need for on-device storage for air-gapped deployments?
- How to surface memories for human override efficiently?

---
_Revision: 2025-08-04_