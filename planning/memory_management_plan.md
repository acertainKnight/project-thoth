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