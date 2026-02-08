---
name: Research Workflow Coordination
description: Coordinate multi-phase research workflows with parallel specialist execution. Use when orchestrating complex research tasks requiring multiple agents.
---

# Research Workflow Coordination

Master the art of coordinating multiple specialists to execute complex research workflows efficiently.

## Quick Start: The Coordination Workflow

**Most common use**: User needs comprehensive research involving discovery, analysis, and synthesis across multiple specialists.

### Standard Opening

```
User: "I need a comprehensive literature review on transformer attention mechanisms."

Orchestrator: "I'll coordinate a multi-phase research workflow for you:

Phase 1: Discovery (parallel)
  - Discovery Scout: Find papers from arXiv, Semantic Scholar
  - Document Librarian: Prepare for PDF downloads

Phase 2: Acquisition (sequential, after Phase 1)
  - Document Librarian: Download and process PDFs

Phase 3: Analysis (parallel)
  - Citation Specialist: Build citation network
  - Research Analyst: Deep analysis and synthesis

Expected time: 10-15 minutes. I'll update you as each phase completes."
```

---

## When to Use Async vs Sync Delegation

### Use ASYNC for long-running tasks (>10 seconds):
- **Discovery**: Finding papers across sources (1-3 minutes)
- **PDF processing**: Downloading and processing papers (30 sec - 5 min)
- **Deep analysis**: Topic analysis, synthesis (2-5 minutes)
- **Citation extraction**: Building citation networks (1-2 minutes)

### Use SYNC for quick queries (<10 seconds):
- **Collection stats**: Paper counts, statistics (instant)
- **Simple lookups**: Finding specific papers by ID (instant)
- **Tag queries**: Listing tags, checking taxonomy (instant)
- **Status checks**: Agent status, workflow progress (instant)

---

## Coordination Patterns

### Pattern 1: Parallel Discovery + Preparation

**When**: User needs papers found and system prepared for downloads

**Example**:
```
User: "Find quantum computing papers from 2024"

Step 1: Analyze request
- Primary task: Discovery (long-running)
- Secondary task: Prepare for downloads (quick)
- Can run in parallel: YES

Step 2: Delegate (async, parallel)
send_message_to_agent(
  agent_id="agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64",
  message="Run discovery for quantum computing papers from 2024. Use arXiv and Semantic Scholar."
)

send_message_to_agent(
  agent_id="agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf",
  message="Prepare collection for new papers on quantum computing"
)

Step 3: Update workflow_state
"Status: Active
Active Tasks: 2

Task 1: Discovery
Agent: Discovery Scout
Type: async
Status: in_progress
Started: [timestamp]

Task 2: Collection Prep
Agent: Document Librarian
Type: async
Status: in_progress
Started: [timestamp]"

Step 4: Inform user
"I've started parallel discovery across arXiv and Semantic Scholar. This will take 1-2 minutes..."

Step 5: Monitor and synthesize
Check workflow_state periodically. When both complete, synthesize results.
```

### Pattern 2: Sequential Pipeline

**When**: Tasks depend on previous results

**Example**:
```
User: "Find papers on deep learning, download them, and analyze"

Phase 1: Discovery
- Delegate to Discovery Scout (async)
- Wait for completion

Phase 2: Download
- Use Phase 1 results
- Delegate to Document Librarian (async)
- Wait for completion

Phase 3: Analysis
- Use Phase 2 results
- Delegate to Research Analyst (async)
- Wait for completion

Phase 4: Synthesize
- Gather all results
- Create comprehensive response
```

### Pattern 3: Mixed Parallel + Sequential

**When**: Some tasks can run in parallel, others depend on results

**Example**:
```
User: "Research transformer architectures with citation analysis"

Phase 1: Discovery + Citation Prep (parallel)
- Discovery Scout: Find papers (async)
- Citation Specialist: Prepare citation tools (async)
- Both can run simultaneously

Phase 2: Download (sequential, needs Phase 1)
- Document Librarian: Download PDFs (async)
- Depends on discovery results

Phase 3: Analysis (parallel)
- Citation Specialist: Extract and analyze citations (async)
- Research Analyst: Deep topic analysis (async)
- Both use downloaded papers

Phase 4: Synthesis (sequential)
- Synthesize citation network + analysis
- Create literature review
```

### Pattern 4: Quick Stats Query

**When**: User needs immediate information from collection

**Example**:
```
User: "How many papers do we have on quantum computing?"

Step 1: Quick query (sync)
response = send_message_to_agent_and_wait_for_reply(
  agent_id="agent-544c0035-e3eb-42bf-a146-3c9eaada4979",
  message="Get collection statistics filtered by 'quantum computing'"
)

Step 2: Return immediately
"We have [count] papers on quantum computing. [additional stats]"

No workflow_state update needed - instant response.
```

---

## Workflow State Management

### Format

Always maintain workflow_state in this format:

```
=== Workflow State ===

Status: [Idle | Active | Waiting | Complete | Error]
Active Tasks: [count]
Phase: [discovery | download | analysis | synthesis | complete]
Started: [timestamp]

Task 1: [description]
Agent: [specialist name]
Agent ID: [full UUID]
Type: [sync|async]
Status: [pending|in_progress|complete|error]
Started: [timestamp]
Duration: [seconds]
Result: [summary when complete]
Error: [error message if failed]

Task 2: ...

=== History ===
[Previous completed tasks]
```

### Updating Workflow State

**When starting tasks:**
```
Update workflow_state:
"Status: Active
Active Tasks: 2
Phase: discovery

Task 1: Discovery for quantum papers
Agent: Discovery Scout
Agent ID: agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64
Type: async
Status: in_progress
Started: 2026-02-02 14:30:00

Task 2: Collection preparation
Agent: Document Librarian
Agent ID: agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf
Type: async
Status: in_progress
Started: 2026-02-02 14:30:05"
```

**When tasks complete:**
```
Update workflow_state:
"Status: Active
Active Tasks: 1
Phase: discovery

Task 1: Discovery for quantum papers
Agent: Discovery Scout
Status: complete
Duration: 142 seconds
Result: Found 23 papers from arXiv, 15 from Semantic Scholar

Task 2: Collection preparation
Agent: Document Librarian
Status: in_progress
..."
```

**When all complete:**
```
Update workflow_state:
"Status: Complete
Active Tasks: 0
Phase: complete
Completed: 2026-02-02 14:32:30

=== History ===
Task 1: Discovery - 142s - 38 papers found
Task 2: Collection prep - 5s - Ready
"
```

---

## Result Synthesis

### Always synthesize results, never just forward

**Bad (don't do this):**
```
Discovery Scout found: "23 papers from arXiv..."
```

**Good (do this):**
```
I've completed a comprehensive discovery search for quantum computing papers from 2024:

**Results:**
- 38 total papers found
- 23 from arXiv
- 15 from Semantic Scholar

**Top Papers:**
1. "Quantum Error Correction..." (150 citations)
2. "Scalable Quantum Algorithms..." (120 citations)
3. ...

**Next Steps:**
Would you like me to:
- Download PDFs for these papers?
- Analyze the citation network?
- Create a literature review?
```

### Synthesis Structure

**1. Overview/Summary**
- What was done
- High-level results
- Key metrics

**2. Detailed Findings**
- Paper lists with metadata
- Statistics and counts
- Important insights

**3. Context and Connections**
- How findings relate to research goals
- Patterns or trends noticed
- Unexpected discoveries

**4. Next Steps**
- Suggested follow-up actions
- Questions to explore further
- Additional specialists that could help

---

## Error Handling

### If a specialist fails:

```
1. Check error message
2. Determine if retryable or fatal
3. Update workflow_state with error
4. Decide on action:
   - Retry with different parameters
   - Skip and continue with other tasks
   - Abort workflow and inform user
   - Delegate to alternate specialist

Example:
Task 1 failed: "Discovery timeout on PubMed"
→ Retry with only arXiv
→ Continue with partial results
→ Inform user of limitation
```

### If workflow takes too long:

```
1. Check workflow_state for stuck tasks
2. Send status update to user:
   "Discovery is taking longer than expected (3 min so far).
    I'll keep monitoring and update you when complete."
3. Consider parallel alternative approaches
4. Set reasonable timeout (10 min for discovery)
```

---

## Advanced Patterns

### Pattern A: Incremental Results

For very long workflows, provide incremental updates:

```
Phase 1 complete: "Found 38 papers. Now downloading PDFs..."
Phase 2 complete: "Downloaded 35/38 PDFs. Now analyzing..."
Phase 3 complete: "Analysis complete. Creating literature review..."
Final: [comprehensive response]
```

### Pattern B: User-Driven Phases

Let user control when to proceed:

```
Phase 1 complete: "Found 38 papers. Review the list and let me know
                   if you want me to proceed with downloads."
[User confirms]
Phase 2 starts: Download PDFs
```

### Pattern C: Adaptive Workflow

Adjust workflow based on intermediate results:

```
Phase 1: Discovery
→ If papers < 10: Broaden search
→ If papers > 100: Narrow search or filter
→ If papers 10-100: Proceed with downloads
```

---

## Quick Reference

### Delegation Decision Tree

```
Question: Is this a quick lookup (<10s)?
  YES → Use sync: send_message_to_agent_and_wait_for_reply
  NO  → Continue

Question: Does this task take >10 seconds?
  YES → Use async: send_message_to_agent
  NO  → Use sync

Question: Are there multiple independent tasks?
  YES → Parallel async delegation
  NO  → Sequential delegation

Question: Does next task need previous results?
  YES → Wait for completion, then delegate
  NO  → Start immediately
```

### Specialist Quick Reference

**Long-running (use async):**
- Discovery Scout: 1-3 min
- Document Librarian: 30s - 5 min
- Citation Specialist: 1-2 min
- Research Analyst: 2-5 min

**Quick queries (use sync):**
- Organization Curator: <5s
- System Maintenance: <5s

---

## Summary: The Orchestrator's Mental Model

**Your job:**
1. Analyze user request → identify specialists needed
2. Determine dependencies → parallel or sequential?
3. Choose sync/async → quick or long-running?
4. Delegate with clear instructions
5. Update workflow_state for async tasks
6. Monitor completion → check workflow_state
7. Synthesize results → comprehensive response
8. Update shared memory → research_context, research_findings

**Key principles:**
- Parallel over sequential when possible
- Async for long tasks, sync for quick queries
- Always update workflow_state for async
- Always synthesize, never just forward
- Keep user informed of progress
- Handle errors gracefully

**Success metric**: User gets comprehensive, timely responses with minimal waiting through intelligent coordination.
