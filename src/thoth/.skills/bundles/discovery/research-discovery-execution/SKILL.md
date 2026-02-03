---
name: Research Discovery Execution
description: Execute and monitor discovery sessions for finding research papers across academic sources. Use when running discovery searches.
---

# Research Discovery Execution

Execute discovery searches systematically and monitor their progress to find relevant research papers.

## Quick Start: Running Discovery

**Most common use**: User needs to find papers on a specific topic from academic sources.

### Standard Execution

```
User request: "Find papers on quantum error correction from 2024"

Step 1: Verify research question exists
- Use list_research_questions
- If doesn't exist, tell orchestrator to create one first

Step 2: Run discovery
- Use run_discovery_for_question
- Specify question ID or name
- Set parameters (date range, sources)

Step 3: Monitor progress
- Update workflow_state with status
- Check for errors or timeouts
- Provide progress updates

Step 4: Return results
- Count of papers found per source
- Summary of top papers
- Quality metrics (relevance scores)
```

---

## Discovery Workflow

### Phase 1: Validation

**Before running discovery, validate:**

1. Research question exists
2. Sources are available
3. Parameters are valid
4. No duplicate recent searches

```
Check existing research questions:
questions = list_research_questions()

If question not found:
"The research question hasn't been created yet. The orchestrator 
should create it first using the research-question-creation skill."

If question exists but recently run:
"This discovery was run 2 hours ago. Found 45 papers. 
Do you want to run again or use existing results?"
```

### Phase 2: Execution

**Run discovery with proper parameters:**

```
run_discovery_for_question(
    question_id="...",
    force_refresh=False,  # Set to True to ignore cache
    max_results=100,      # Limit per source
    min_relevance=0.7     # Quality threshold
)
```

**Sources checked (in order):**
1. arXiv (fast, high quality)
2. Semantic Scholar (comprehensive)
3. PubMed (biomedical focus)
4. CrossRef (broad coverage)
5. bioRxiv (preprints)

### Phase 3: Monitoring

**Update workflow_state during execution:**

```
Initial:
"Discovery Status: Starting
Sources: arXiv, Semantic Scholar, PubMed
Expected time: 1-2 minutes"

During:
"Discovery Status: In Progress
arXiv: 23 papers found (complete)
Semantic Scholar: 15 papers found (in progress)
PubMed: pending
Time elapsed: 45 seconds"

Complete:
"Discovery Status: Complete
Total papers: 52
Sources: arXiv (23), Semantic Scholar (18), PubMed (11)
Duration: 118 seconds
Quality: 38 papers above relevance threshold"
```

### Phase 4: Results Processing

**Analyze and summarize results:**

```
For each source:
- Count of papers found
- Quality distribution (high/medium/low relevance)
- Date range covered
- Top papers by relevance score

Overall:
- Total unique papers (deduplicating across sources)
- Papers meeting quality threshold
- Recommended next steps
```

---

## Error Handling

### Common Errors and Solutions

**Error: "Source timeout"**
```
Problem: arXiv taking >60 seconds
Solution: Continue with other sources
Action: "arXiv timed out, but found 33 papers from Semantic Scholar 
         and PubMed. Do you want to retry arXiv or proceed with these?"
```

**Error: "No papers found"**
```
Problem: Search too narrow or no matching papers
Solution: Suggest broadening search
Action: "No papers found matching these criteria. Suggestions:
         - Broaden date range (try last 2 years instead of 6 months)
         - Add related keywords
         - Try different sources"
```

**Error: "Rate limit exceeded"**
```
Problem: Too many requests to source
Solution: Wait and retry, or skip source
Action: "Hit rate limit on Semantic Scholar. Waiting 30 seconds...
         Meanwhile, found 20 papers from arXiv."
```

**Error: "Invalid research question"**
```
Problem: Research question malformed or missing
Solution: Tell orchestrator to fix/create question
Action: "Research question needs to be created or fixed. Delegating 
         back to orchestrator..."
```

---

## Quality Thresholds

### Relevance Scoring

Papers are scored 0.0-1.0 based on:
- Title/abstract keyword matches (40%)
- Semantic similarity (30%)
- Citation count (20%)
- Publication venue (10%)

**Thresholds:**
- **High quality**: >0.8 - Highly relevant, well-cited
- **Medium quality**: 0.6-0.8 - Relevant, decent citations
- **Low quality**: <0.6 - Tangentially related

### Filtering Strategy

```
Default: Return all papers >0.6 relevance
Strict mode: Only >0.8 relevance
Exploratory mode: All papers >0.4 relevance

Example:
Found 80 papers total:
- 25 high quality (>0.8)
- 35 medium quality (0.6-0.8)
- 20 low quality (<0.6)

Recommended: Present high + medium (60 papers)
```

---

## Source-Specific Notes

### arXiv
- **Best for**: Computer Science, Physics, Math
- **Speed**: Fast (10-30 seconds)
- **Quality**: High (peer-reviewed preprints)
- **Limitation**: No biomedical papers

### Semantic Scholar
- **Best for**: Comprehensive coverage across fields
- **Speed**: Medium (30-60 seconds)
- **Quality**: Variable (includes preprints and journals)
- **Strength**: Great citation data

### PubMed
- **Best for**: Biomedical and life sciences
- **Speed**: Medium (20-40 seconds)
- **Quality**: High (peer-reviewed journals)
- **Limitation**: Only biomedical topics

### CrossRef
- **Best for**: DOI-based lookups, broad coverage
- **Speed**: Slow (60-120 seconds)
- **Quality**: Variable
- **Use case**: Fallback for other sources

### bioRxiv
- **Best for**: Latest biomedical preprints
- **Speed**: Fast (15-30 seconds)
- **Quality**: Medium (not peer-reviewed)
- **Strength**: Cutting-edge research

---

## Advanced Patterns

### Pattern A: Incremental Discovery

For large searches, run in batches:

```
Batch 1: Last 6 months (quick)
→ Review results
→ If insufficient, expand to 1 year
Batch 2: 6-12 months ago
→ Merge with Batch 1
→ If still insufficient, expand to 2 years
```

### Pattern B: Multi-Phase Discovery

For complex topics:

```
Phase 1: Core keywords (narrow)
→ Get foundational papers

Phase 2: Related keywords (broad)
→ Find connections and context

Phase 3: Citation expansion
→ Papers cited by Phase 1 papers
```

### Pattern C: Source Prioritization

Based on topic:

```
Computer Science topic:
Priority: arXiv > Semantic Scholar > CrossRef

Biomedical topic:
Priority: PubMed > bioRxiv > Semantic Scholar

Interdisciplinary:
Priority: Semantic Scholar > arXiv > PubMed
```

---

## Performance Optimization

### Parallel Source Queries

Sources can be queried in parallel:

```
Start all sources simultaneously:
- arXiv query (async)
- Semantic Scholar query (async)
- PubMed query (async)

Return results as they complete:
"arXiv: 23 papers found (15 seconds)"
"Semantic Scholar: still searching..."
"PubMed: 11 papers found (22 seconds)"
```

### Caching Strategy

```
Cache results for 24 hours:
- Same research question
- Same parameters
- Within 24 hours

Skip cache if:
- force_refresh=True
- User explicitly asks for fresh search
- Important new papers expected (conference just happened)
```

---

## Result Formatting

### Always provide structured results:

```
=== Discovery Results ===

**Summary:**
- Total papers: 52
- High quality: 25 papers
- Date range: Jan 2024 - Jan 2025
- Duration: 118 seconds

**By Source:**
1. arXiv: 23 papers (10-30s search time)
2. Semantic Scholar: 18 papers (45s search time)
3. PubMed: 11 papers (25s search time)

**Top 5 Papers:**
1. "Quantum Error Correction with..." (relevance: 0.95, 150 cites)
2. "Surface Codes for Fault-Tolerant..." (relevance: 0.92, 120 cites)
3. ...

**Quality Distribution:**
- High (>0.8): 25 papers
- Medium (0.6-0.8): 20 papers
- Below threshold (<0.6): 7 papers (filtered out)

**Next Steps:**
Would you like me to:
- Download PDFs for high-quality papers?
- Run citation analysis?
- Create a reading list?
```

---

## Integration with Workflow State

Always update workflow_state during discovery:

```
Start:
workflow_state: "Discovery started for quantum error correction"

Progress:
workflow_state: "Discovery 50% complete, 30 papers found so far"

Complete:
workflow_state: "Discovery complete: 52 papers found in 118 seconds"

Update active_papers memory:
"Papers pending download: [list of paper IDs]"

Update research_context:
"Current research: quantum error correction
Latest discovery: Jan 2025, 52 papers"
```

---

## Quick Reference

### Discovery Checklist

- [ ] Research question exists
- [ ] Sources are valid for topic
- [ ] Parameters set (date range, max results)
- [ ] workflow_state updated (starting)
- [ ] Run discovery
- [ ] Monitor progress
- [ ] Handle errors gracefully
- [ ] workflow_state updated (progress)
- [ ] Process and filter results
- [ ] Update memory blocks
- [ ] workflow_state updated (complete)
- [ ] Format and return results

### Common Parameters

```
Standard search:
- Date range: Last 2 years
- Max results: 100 per source
- Min relevance: 0.7

Quick search:
- Date range: Last 6 months
- Max results: 50 per source
- Min relevance: 0.8

Comprehensive search:
- Date range: Last 5 years
- Max results: 200 per source
- Min relevance: 0.6
```

---

## Summary

**Your job as Discovery Scout:**
1. Validate research question exists
2. Run discovery across relevant sources
3. Monitor progress and handle errors
4. Filter results by quality threshold
5. Update workflow_state and memory blocks
6. Format and return structured results
7. Suggest next steps

**Key principles:**
- Always check if question exists first
- Update workflow_state throughout
- Handle source failures gracefully
- Filter by quality thresholds
- Provide structured, actionable results

**Success metric**: User gets high-quality, relevant papers quickly with clear next-step options.
