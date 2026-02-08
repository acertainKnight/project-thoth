---
name: Research Query Management
description: Set up and manage automated recurring research searches. Use when user wants to stay updated on a topic, create scheduled searches, or refine existing queries.
tools:
  - list_available_sources
  - create_research_question
  - list_research_questions
  - get_research_question
  - update_research_question
  - delete_research_question
  - run_discovery_for_question
---

# Research Query Management

Create and manage automated research queries that run on schedule to keep users updated on topics they care about.

## Tools to Use

For query management, use these tools:

| Tool | Purpose |
|------|---------|
| `list_available_sources` | Show source options |
| `create_research_question` | Create new query |
| `list_research_questions` | See existing queries |
| `get_research_question` | Get query details |
| `update_research_question` | Modify query settings |
| `delete_research_question` | Remove a query |
| `run_discovery_for_question` | Test a query |

## Setting Up a New Recurring Search

### Step 1: Understand User Needs

Ask these questions:
1. "What topic do you want to track?"
2. "How often do you want updates?" (daily/weekly)
3. "How many papers per update is manageable for you?"

### Step 2: Build the Query

```
list_available_sources()  # Show options

create_research_question(
  title="Descriptive title for this search",
  keywords=["primary_term", "secondary_term", "synonym"],
  sources=["source1", "source2"],
  max_papers=15,
  relevance_threshold=0.7,
  schedule="daily"  # or "weekly"
)
```

### Step 3: Test the Query

```
run_discovery_for_question(question_id="[new query ID]")
```

Review results with user:
- Are papers relevant?
- Too many/too few results?
- Missing important keywords?

### Step 4: Confirm Setup

```
"Your recurring search is set up:

📋 **Query**: [title]
🔑 **Keywords**: [list]
📚 **Sources**: [list]
⏰ **Schedule**: [daily/weekly]
📊 **Expected**: ~[X] papers per run

The system will automatically search for new papers and add them
to your collection. You'll find new papers in your daily/weekly digest."
```

## Refining Existing Queries

### Diagnosis Questions

When user reports issues, ask:

| Problem | Ask |
|---------|-----|
| Too many papers | "Are most papers relevant, or is there noise?" |
| Too few papers | "What kinds of papers are you missing?" |
| Wrong topic | "Can you show me papers you want vs. what you're getting?" |

### Common Refinements

**Too much noise**:
```
get_research_question(question_id="[query ID]")

update_research_question(
  question_id="[query ID]",
  relevance_threshold=0.8,  # Raise from 0.7
  keywords=["more", "specific", "terms"]  # Add specificity
)
```

**Missing papers**:
```
update_research_question(
  question_id="[query ID]",
  relevance_threshold=0.65,  # Lower threshold
  sources=["add", "more", "sources"],  # Add sources
  keywords=["existing", "plus", "synonyms"]  # Add synonyms
)
```

**Wrong domain**:
```
update_research_question(
  question_id="[query ID]",
  keywords=["topic", "-exclude_term"],  # Negative keywords
  sources=["domain_specific_source"]  # Change sources
)
```

## Schedule Recommendations

| User Availability | Schedule | Max Papers |
|-------------------|----------|------------|
| 10 min/day | daily | 10-15 |
| 30 min/week | weekly | 30-50 |
| 1+ hour/week | weekly | 50-100 |
| Comprehensive review | weekly | 100+ |

## Query Health Check

Periodically review query performance:

```
list_research_questions()

For each query:
  get_research_question(question_id="...")

  Check:
  - Last run date
  - Papers found per run
  - User engagement (if tracked)

  Recommend adjustments if needed
```

## Workflow Examples

### Example 1: New Topic Tracking

**User**: "Keep me updated on new papers about state space models"

```
1. "I'll set up a recurring search for you. A few questions:
    - How often should I check for new papers? (daily/weekly)
    - How many papers can you review? (~10-15 daily or ~30-50 weekly)"

2. [User: "Weekly, about 30 papers"]

3. create_research_question(
     title="State Space Models Research Updates",
     keywords=["state space model", "SSM", "Mamba", "S4", "linear attention"],
     sources=["arxiv", "semantic_scholar"],
     max_papers=35,
     relevance_threshold=0.7,
     schedule="weekly"
   )

4. run_discovery_for_question(question_id="...")

5. "Found 28 papers in the initial test. Here are the top 5:
    [list]

    Does this look like what you're looking for?"
```

### Example 2: Refining a Noisy Query

**User**: "My attention mechanisms search is giving me too many irrelevant papers"

```
1. list_research_questions()  # Find the query

2. get_research_question(question_id="attention-query-id")
   → Current settings: threshold=0.65, keywords=["attention"]

3. "I see your current search uses broad keywords. Let's refine:
    - What specific type of attention are you interested in?
    - Any domains you want to exclude?"

4. [User: "Just efficient attention for transformers, not general attention"]

5. update_research_question(
     question_id="attention-query-id",
     keywords=["efficient attention", "linear attention", "sparse attention", "flash attention"],
     relevance_threshold=0.75
   )

6. run_discovery_for_question(question_id="attention-query-id")

7. "Updated! Test run found 18 papers (down from 45).
    Here are the top 5 - are these more relevant?"
```

### Example 3: Multiple Related Queries

**User**: "I'm researching LLM efficiency - help me set up comprehensive tracking"

```
1. "For comprehensive coverage, I recommend multiple focused queries:

   Query 1: Model Architecture Efficiency
   Query 2: Training Efficiency
   Query 3: Inference Optimization

   Each will capture different aspects. Shall I set these up?"

2. [Create each query with specific keywords]

3. "You now have 3 queries running weekly:
    - Architecture: ~15 papers/week
    - Training: ~20 papers/week
    - Inference: ~25 papers/week

    Total: ~60 papers/week. Manageable for your schedule?"
```

## Response Template

For new query setup:
```
## Research Query Created ✓

**Title**: [query title]
**ID**: [query_id]

**Configuration**:
- Keywords: [list]
- Sources: [list]
- Schedule: [frequency]
- Max papers: [count]
- Relevance threshold: [value]

**Test Results**:
- Papers found: [count]
- Sample papers: [top 3]

**Next steps**:
- Query will run automatically on [schedule]
- Use `get_research_question(question_id="[ID]")` to check status
- Ask me to refine if results aren't quite right
```
