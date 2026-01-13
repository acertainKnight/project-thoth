---
name: research-messages-search
description: Search conversation history for research context - papers discussed, citations analyzed, discoveries made, or questions explored.
---

# Research Messages Search

Find past research conversations, paper discussions, and analysis from your conversation history.

## Quick Start: The Research Needle

**Most common use**: Finding when you discussed a specific paper, topic, or research question.

### Standard Opening

```
User: "When did we discuss transformer architectures?"

Agent: "Let me search our conversation history for transformer discussions.

I'll use hybrid search (semantic + keyword) to find the most relevant messages."
```

**Then execute the search:**

```bash
npx tsx [SKILL_DIR]/scripts/search-messages.ts --query "transformer architectures" --limit 10
```

**Present results:**

```
Agent: "Found 8 conversations about transformers:

Most relevant:
- Dec 15, 2025: Analyzed 'Attention Is All You Need' paper
- Dec 18, 2025: Discussed transformer memory mechanisms
- Jan 3, 2026: Compared transformer vs Mamba architectures

Want me to expand around any of these to see the full context?"
```

---

## Diagnosis: What Are They Looking For?

Ask 2 questions to understand the search:

**Question 1: What type?**
```
Agent: "Are you looking for:
A) A specific paper we discussed?
B) Analysis of a research topic?
C) Discovery results from a query?
D) Citation network we built?
E) Something else?"
```

**Question 2: Time range?**
```
Agent: "Time frame:
A) Recent (last week)
B) This month
C) Specific date/period
D) Any time (full history)"
```

**Route based on answers:**

```
Type A (paper) + Recent → Paper title search, last 7 days
Type B (topic) + Any time → Semantic search, all history
Type C (discovery) + Month → Keyword "discovery", current month
Type D (citation) + Specific → Date-bounded search
```

---

## Conversation Patterns

### Pattern 1: Finding Paper Discussion

**Trigger**: User asks about a specific paper

```
User: "What did we say about the BERT paper?"

Agent: "Let me search for BERT discussions."

[Run search with "BERT paper", focus on title/authors]

Agent: "Found 3 conversations:
- Nov 20: Initial BERT paper analysis
- Nov 22: Compared BERT vs RoBERTa  
- Dec 1: Used BERT for sentiment analysis

The Nov 20 conversation has the main analysis. Want to see it?"

[If yes, use needle+expand strategy]
```

### Pattern 2: Finding Topic Discussions

**Trigger**: User asks about research topic/concept

```
User: "When did we talk about citation networks?"

Agent: "Searching for citation network discussions..."

[Run semantic search, --mode vector for concept matching]

Agent: "Found 5 conversations about citation networks:

Most relevant:
- Jan 5: Built citation graph for ML papers
- Jan 8: Analyzed influential papers using PageRank
- Jan 10: Discussed loop closure in citations

These span multiple conversations. Want the full thread?"

[If yes, expand around first occurrence and follow chronologically]
```

### Pattern 3: Finding Discovery Results

**Trigger**: User asks about papers found from discovery

```
User: "What papers did we find about state space models?"

Agent: "Searching for state space model discoveries..."

[Search with "discovery state space models" + keyword mode]

Agent: "Found 2 discovery sessions:
- Dec 28: Discovered 15 SSM papers from ArXiv
- Jan 4: Found Mamba paper and variants

The Dec 28 session has the full paper list. Show that?"
```

### Pattern 4: Needle + Expand Strategy

**Trigger**: User wants full context around a specific finding

```
Agent: "Found the needle! Message from Dec 15 at 2:30 PM.

Getting context around that message..."

[Run get-messages with --before and --after]

Agent: "Here's the full conversation (10 messages before + 10 after):

[Show conversation thread]

That's the complete context. Need more?"
```

---

## Quick Reference Cards

### Card 1: Search Modes

**When to use each mode:**

| Mode | Use When | Example |
|------|----------|---------|
| `hybrid` (default) | General search | "transformer discussions" |
| `vector` | Concept/semantic | "papers about memory" |
| `fts` | Exact phrase | "Attention Is All You Need" |

**Default to hybrid** unless user needs exact matches or pure semantic.

### Card 2: Time Filters

**Common time patterns:**

```bash
# Last week
--start-date "2026-01-06" --end-date "2026-01-13"

# Specific month
--start-date "2025-12-01" --end-date "2025-12-31"

# After specific date
--start-date "2025-11-01"

# Before specific date  
--end-date "2025-10-31"
```

**Pro tip**: Use ISO format `YYYY-MM-DD` for dates.

### Card 3: Research-Specific Queries

**Effective search terms for research:**

- Paper titles: Use quotes for exact match
- Authors: Include "et al" or full names
- Topics: Use technical terms, not casual language
- Citations: Include "citation" or "references"
- Discovery: Include "discovered" or "found papers"
- Analysis: Include "analyzed" or "compared"

**Examples:**
```
"Attention Is All You Need"  → Exact paper
transformer memory mechanisms → Topic discussion
Vaswani et al                → Author search
citation network analysis    → Analysis type
discovered mamba papers      → Discovery results
```

### Card 4: The Needle + Expand Pattern

**Two-step strategy for full context:**

**Step 1: Find the needle**
```bash
npx tsx [SKILL_DIR]/scripts/search-messages.ts \
  --query "your search terms" \
  --limit 5
```

**Step 2: Expand around it**
```bash
# Get context before
npx tsx [SKILL_DIR]/scripts/get-messages.ts \
  --before "message-id-from-search" \
  --limit 10

# Get context after  
npx tsx [SKILL_DIR]/scripts/get-messages.ts \
  --after "message-id-from-search" \
  --order asc \
  --limit 10
```

---

## Refinement Patterns

### Refinement 1: Too Many Results

**Symptom**: Search returns 50+ messages, overwhelming

**Fix**: Narrow the search

```
Agent: "That search returned too many results. Let's narrow it:

Option A: Add time filter (when roughly was this?)
Option B: Add specific terms (any unique words?)
Option C: Use exact phrase (put in quotes)

Which helps?"
```

### Refinement 2: No Results Found

**Symptom**: Search returns 0 results

**Fix**: Broaden and diagnose

```
Agent: "No results for that search. Let's troubleshoot:

1. Try semantic search (concepts vs exact words):
   --mode vector

2. Try broader terms:
   'transformer' instead of 'transformer architecture'

3. Search all agents (if multi-agent setup):
   --all-agents

Which should we try?"
```

### Refinement 3: Wrong Context

**Symptom**: Found messages but not the right conversation

**Fix**: Expand correctly

```
Agent: "That's not the conversation you wanted. Let me:

1. Check the other search results (we have 4 more)
2. Expand more context (20 messages instead of 10)
3. Refine search terms (what's unique about that conversation?)

Which approach?"
```

### Refinement 4: Need Cross-Session Context

**Symptom**: Topic discussed across multiple sessions

**Fix**: Search with sort, present chronologically

```
Agent: "This topic spans multiple conversations. Here's the timeline:

Session 1 (Dec 5): Initial discussion
Session 2 (Dec 8): Follow-up analysis
Session 3 (Dec 12): Final conclusions

Want to see all three in order, or just the most relevant?"
```

---

## Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| Search too slow | Reduce --limit to 5 |
| No results found | Use --mode vector for semantic search |
| Too many results | Add date range with --start-date |
| Wrong messages | Use exact phrase in quotes |
| Need more context | Use get-messages.ts with --before/--after |
| Want full thread | Expand before+after the needle |
| Multi-agent search | Add --all-agents flag |
| Need specific date | Use --start-date and --end-date (same day) |
| Results not relevant | Switch to --mode fts for exact keyword |

---

## Advanced: Cross-Agent Research Search

**Use case**: Finding which agent discussed a topic

```
Agent: "Searching across all agents for transformer discussions..."

[Run with --all-agents flag]

Agent: "Found discussions in 3 agents:
- Agent A (Lead Engineer): Technical analysis
- Agent B (Literature Review): Paper summaries
- Agent C (Research Assistant): Discovery results

Which agent's context do you want to explore?"
```

**Results include agent_id** - use with finding-agents skill to get agent details.

---

## Summary: The Agent's Mental Model

**Core workflow:**
1. Understand what user is looking for (paper, topic, discovery, etc.)
2. Choose search mode (hybrid default, vector for concepts, fts for exact)
3. Run search with appropriate filters
4. Present top results with context
5. If needed, expand around the needle
6. Refine if results aren't quite right

**Key principles:**
- Default to hybrid search (best balance)
- Use semantic (vector) for concept searches
- Use exact (fts) for specific phrases/titles
- Always offer to expand for full context
- Present results with timestamps and message types
- Help user narrow down if too many results
- Help user broaden if no results

**Success**: User finds the research conversation they were looking for and gets the full context they need.
