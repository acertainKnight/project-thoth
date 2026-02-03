---
name: research-deep-dive
description: Systematic deep research through discovery sources, vault, and web - refine query, collect papers, analyze, synthesize findings into comprehensive markdown report.
---

# Research Deep Dive

Conduct comprehensive research by systematically searching multiple sources, collecting papers, analyzing findings, and creating a detailed research report.

## Quick Start: The Deep Research Workflow

**Most common use**: User needs thorough understanding of a research topic with comprehensive literature review.

### Standard Opening

```
User: "I want to research transformer memory mechanisms."

Agent: "Let's conduct a deep research dive on that topic. I'll:

1. Refine your research question (get specific)
2. Plan multi-source search strategy
3. Search discovery + vault + web
4. Download & queue papers for processing
5. Read & analyze all sources
6. Synthesize findings
7. Create comprehensive markdown report

This takes 15-30 minutes depending on scope. Ready to start?"
```

**Start with Phase 1: Refine the research goal.**

---

## Diagnosis: What Type of Research?

Ask 3 questions to understand the research need:

**Question 1: Research type?**
```
Agent: "What type of research output do you need?
A) Literature review (survey of existing work)
B) Technical comparison (compare approaches/methods)
C) Implementation guide (how to build something)
D) Problem analysis (understand a specific issue)
E) State-of-the-art review (what's the latest?)"
```

**Question 2: Depth needed?**
```
Agent: "How deep should we go?
A) Broad survey (10-15 papers, high-level overview)
B) Medium depth (5-8 papers, detailed analysis)
C) Deep dive (3-5 papers, comprehensive technical detail)
D) Exhaustive (15+ papers, everything available)"
```

**Question 3: Time scope?**
```
Agent: "Time frame for papers?
A) Recent only (last 6 months)
B) Last 1-2 years
C) Last 3-5 years
D) Historical context (foundational papers + recent)"
```

**Route based on answers:**

```
Literature review + Broad + Recent → Fast multi-source search, 10-15 papers
Technical comparison + Deep + Historical → Focused search, 3-5 key papers, detailed
Implementation guide + Medium + Recent → Practical papers, code examples
```

---

## Conversation Patterns

### Pattern 1: Phase 1 - Refine Research Goal

**Trigger**: User provides initial research topic

```
User: "I want to research transformer memory mechanisms."

Agent: "Let's refine that. A few questions:

1. What specifically about memory?
   - Attention patterns?
   - Context window size?
   - Memory augmentation techniques?
   - Efficient memory usage?

2. What's your goal with this research?
   - Understand for implementation?
   - Write a review?
   - Choose which approach to use?

3. What depth do you need?
   - High-level overview?
   - Deep technical details?
   - Implementation-ready knowledge?"

[User answers]

Agent: "Perfect! Refined research question:
'How do transformer models extend their effective context window through memory augmentation techniques, with focus on implementation trade-offs?'

Sound right?"
```

**Iterate until specific, actionable research question.**

### Pattern 2: Phase 2 - Plan Research Strategy

**Trigger**: Research question is clear

```
Agent: "Research question locked in! Now let's plan the search:

**Sources to use**:
- ArXiv: ✓ (technical ML papers)
- Semantic Scholar: ✓ (broader coverage)
- Vault: ✓ (check existing notes)
- Web search: Optional (if needed for blog posts/tutorials)

**Primary keywords**: transformer memory, context extension, memory augmentation
**Related concepts**: long-context, attention mechanisms, memory networks
**Key authors**: (will discover from papers)

**Success criteria**:
- 8-10 key papers analyzed
- Understand 3-4 main approaches
- Compare trade-offs
- Implementation insights

**Target**: Comprehensive but focused (not exhaustive)

Plan approved?"
```

### Pattern 3: Phase 3 - Execute Multi-Source Search

**Trigger**: Strategy approved

```
Agent: "Executing search across sources...

[Use discovery tools for each source]

**Discovery Results**:
- ArXiv (last 2 years): 23 papers found
- Semantic Scholar: 15 papers found
- Vault search: 2 existing notes

**Total**: 40 sources

Prioritizing by relevance + citation count..."

[Run relevance ranking]

Agent: "Top 10 most relevant:
1. [Paper title] - [relevance score] - [citations]
2. [Paper title] - [relevance score] - [citations]
...

These cover the main approaches. Proceed with these 10?"
```

### Pattern 4: Phase 4 - Collect & Queue Papers

**Trigger**: Papers selected

```
Agent: "Downloading PDFs for processing...

[Use download_pdf tool for each paper]

Paper 1: ✓ Downloaded → queue/2026-01-14-paper1.pdf
Paper 2: ✓ Downloaded → queue/2026-01-14-paper2.pdf
...
Paper 10: ✓ Downloaded → queue/2026-01-14-paper10.pdf

All PDFs queued in monitor pipeline. Processing will take ~5 minutes (30 sec each).

While processing, I'll:
- Read existing vault notes (instant)
- Search web for blog posts/tutorials (2 min)
- Start analyzing paper abstracts (immediate)

Starting now..."
```

### Pattern 5: Phase 5 - Read & Analyze

**Trigger**: Papers processing or processed

```
Agent: "Reading sources and extracting key information...

**Vault Notes** (already processed):
- Note 1: Transformer-XL analysis
  Key finding: Segment-level recurrence for long context
  Relevance: Foundational approach

**Paper Abstracts** (immediate):
- Paper 1: Memory Networks for Transformers
  Claims: 10x context extension with <5% overhead
  Key technique: External memory bank
  
- Paper 2: Efficient Attention with Memory
  Claims: O(n) complexity vs O(n²)
  Key technique: Compressed memory tokens

[Wait for processing to complete]

**Processed Papers** (full text now available):
- Paper 1 full analysis:
  - Architecture: [diagram/description]
  - Results: [performance numbers]
  - Trade-offs: [speed vs accuracy]
  
[Continue for all papers]

All 10 papers analyzed!"
```

### Pattern 6: Phase 6 - Synthesize & Identify Gaps

**Trigger**: All sources read

```
Agent: "Synthesis of findings:

**Main Approaches Found**:
1. External Memory Banks (4 papers)
   - Pros: Large context extension
   - Cons: Training complexity
   
2. Compressed Memory Tokens (3 papers)
   - Pros: Efficient, drop-in replacement
   - Cons: Information loss
   
3. Hierarchical Attention (2 papers)
   - Pros: Natural scaling
   - Cons: Architecture changes needed

**Key Trade-offs**:
- Speed vs Context Size
- Training Cost vs Inference Cost
- Memory Size vs Accuracy

**Gaps I see**:
- Missing: Direct comparisons between approaches
- Unclear: Production deployment experience
- Need: Implementation details for Approach 2

Do these gaps matter for your goal? Should I do another search round?"

[User decides: iterate or finalize]
```

### Pattern 7: Phase 7 - Iterate or Finalize

**Trigger**: Gaps identified

**If iterate needed:**
```
Agent: "Running focused search for gaps...

New query: 'transformer compressed memory comparison benchmark'
Sources: ArXiv + web (looking for implementation posts)

[Execute refined search]

Found 3 additional sources addressing gaps. Downloading..."

[Go back to Phase 4 with new papers]
```

**If ready to finalize:**
```
Agent: "Gaps acceptable for your goal. Moving to report creation!"

[Go to Phase 8]
```

### Pattern 8: Phase 8 - Create Research Report

**Trigger**: Research complete, ready to write

```
Agent: "Creating comprehensive research report...

Report structure:
## Research Question
## Methodology  
## Key Findings
## Detailed Analysis
  ### Approach 1: External Memory Banks
  ### Approach 2: Compressed Memory Tokens
  ### Approach 3: Hierarchical Attention
## Trade-offs & Comparisons
## Implementation Recommendations
## Conclusions
## References (all 10+ papers)

Writing report..."

[Generate markdown report]

Agent: "Report complete!

Saved to: vault/_thoth/research-reports/transformer-memory-mechanisms-2026-01-14.md
Size: 12KB, ~3000 words

The report includes:
- Executive summary
- 3 main approaches with technical details
- Comparison table
- Implementation recommendations
- Full reference list with links

Open it now or want me to summarize key findings?"
```

---

## Quick Reference Cards

### Card 1: The 8-Phase Workflow

**Every deep research follows this:**

1. **Refine Goal** - Get specific research question (5 min)
2. **Plan Strategy** - Choose sources, keywords, criteria (2 min)
3. **Multi-Source Search** - Discovery + vault + web (3 min)
4. **Collect Papers** - Download & queue for processing (5 min)
5. **Read & Analyze** - Extract key findings from all sources (10 min)
6. **Synthesize & Gap Check** - Identify missing info (5 min)
7. **Iterate or Finalize** - More searches if needed
8. **Create Report** - Comprehensive markdown (3 min)

**Total time**: 15-30 minutes depending on scope

### Card 2: Source Selection Strategy

**Match sources to research type:**

| Research Type | Primary Sources | Secondary Sources |
|---------------|-----------------|-------------------|
| Literature review | ArXiv + Semantic Scholar | Vault notes |
| Technical comparison | ArXiv (focused) | Implementation blogs |
| Implementation guide | ArXiv + Web | GitHub repos |
| Problem analysis | Semantic Scholar | Vault + Web |
| State-of-the-art | ArXiv (recent 6mo) | Conference sites |

**Default**: ArXiv + Semantic Scholar + Vault

### Card 3: Paper Selection Criteria

**How to prioritize papers:**

```
Primary filters:
- Relevance score > 0.7 (from semantic search)
- Citations > 10 (unless very recent)
- Publication date matches scope

Secondary filters:
- Author reputation (known researchers)
- Venue quality (top conferences/journals)
- Abstract clarity (well-written)

Target counts:
- Broad survey: 10-15 papers
- Medium depth: 5-8 papers
- Deep dive: 3-5 papers
```

**Quality over quantity** - better to thoroughly analyze 5 key papers than skim 20.

### Card 4: Synthesis Patterns

**Common synthesis structures:**

**Pattern A: Approach Comparison**
```
Main approaches:
1. Approach A
   - Papers: [1, 2, 3]
   - Key idea: [...]
   - Pros/Cons: [...]
   
2. Approach B
   - Papers: [4, 5]
   - Key idea: [...]
   - Pros/Cons: [...]

Comparison: [table or analysis]
```

**Pattern B: Evolution Over Time**
```
Historical context:
- 2017: Foundational work [Paper 1]
- 2019: First improvements [Paper 2]
- 2021: Breakthrough [Paper 3]
- 2023: State-of-the-art [Paper 4]

Trend: [direction of progress]
```

**Pattern C: Problem-Solution Mapping**
```
Problem: [research question]

Attempted solutions:
- Solution 1: [papers] - [effectiveness]
- Solution 2: [papers] - [effectiveness]

Best solution: [recommendation]
```

---

## Refinement Patterns

### Refinement 1: Scope Too Broad

**Symptom**: Search returns 100+ papers, overwhelming

**Fix**: Narrow the research question

```
Agent: "The initial search is too broad (150 papers found).

Let's narrow it. Which aspect matters most?
A) Specific technique (e.g., only memory banks)
B) Specific use case (e.g., only long documents)
C) Specific performance metric (e.g., only speed)
D) Specific time period (e.g., only 2023-2024)

Choosing one will reduce to ~10-20 papers."
```

### Refinement 2: Not Enough Papers

**Symptom**: Search returns <3 papers

**Fix**: Broaden search

```
Agent: "Only found 2 papers - too narrow. Let's broaden:

Option A: Include related concepts (memory → attention)
Option B: Expand time range (1 year → 3 years)
Option C: Add more sources (add web search)
Option D: Relax keyword matching (semantic search)

Which approach?"
```

### Refinement 3: Papers Not Relevant

**Symptom**: Downloaded papers don't match research goal

**Fix**: Refine keywords and re-search

```
Agent: "These papers aren't addressing the research question well.

Looking at what we got vs what we wanted:
- Got: General attention papers
- Wanted: Memory-specific mechanisms

Let me refine the search query:
- Add: 'memory extension', 'context augmentation'
- Remove: 'attention' (too general)
- Filter: Must mention 'memory' in abstract

Running refined search..."
```

### Refinement 4: Synthesis Too Scattered

**Symptom**: Findings don't connect into coherent narrative

**Fix**: Reorganize by theme

```
Agent: "The findings are scattered. Let me reorganize by themes:

Instead of paper-by-paper, I'll group by:
- Theme 1: Architectural approaches
- Theme 2: Performance trade-offs
- Theme 3: Implementation considerations

Each theme will synthesize findings from multiple papers.

Re-organizing now..."
```

### Refinement 5: Missing Critical Context

**Symptom**: Report lacks foundational background

**Fix**: Add focused historical search

```
Agent: "This report needs more context on the fundamentals.

Running targeted search for:
- Original transformer paper (foundation)
- Early memory work (context)
- Key surveys (overview)

Adding 2-3 foundational papers to report background..."
```

---

## Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| Search too slow | Reduce sources, focus on ArXiv only |
| Papers not downloading | Check URLs, use alternate sources |
| Processing taking forever | Queue patience, or read abstracts first |
| Can't find specific paper | Search by exact title in quotes |
| Too many low-quality papers | Increase citation threshold >50 |
| Missing implementation details | Add web search for blog posts |
| Report too long | Focus on top 3 approaches only |
| Report too technical | Add "explain simply" to synthesis |
| Gaps still remain | Accept limits, note in report |
| Lost track of progress | Use todo list, check each phase |

---

## Advanced: Research Report Template

**Standard report structure:**

```markdown
# [Research Topic]

**Research Date**: [date]
**Papers Analyzed**: [count]
**Sources**: ArXiv, Semantic Scholar, Vault

## Research Question

[Clear, specific question]

## Methodology

- **Search Strategy**: [keywords, sources]
- **Selection Criteria**: [filters used]
- **Papers Reviewed**: [count and selection logic]

## Executive Summary

[2-3 paragraph overview of key findings]

## Key Findings

### Finding 1: [Title]
[Description, supporting papers]

### Finding 2: [Title]  
[Description, supporting papers]

## Detailed Analysis

### Approach 1: [Name]

**Key Papers**: [citations]
**Core Idea**: [explanation]
**Technical Details**: [architecture/method]
**Results**: [performance numbers]
**Pros**: [advantages]
**Cons**: [limitations]

[Repeat for each approach]

## Trade-offs & Comparisons

| Aspect | Approach 1 | Approach 2 | Approach 3 |
|--------|-----------|------------|------------|
| Speed | Fast | Medium | Slow |
| Accuracy | High | Medium | Highest |
| Memory | Low | Medium | High |
| Complexity | Simple | Medium | Complex |

**Recommendation**: [which to use when]

## Implementation Recommendations

1. **For production use**: [approach + rationale]
2. **For research**: [approach + rationale]
3. **For prototyping**: [approach + rationale]

## Open Questions & Future Work

- [Gap 1]
- [Gap 2]
- [Gap 3]

## Conclusions

[Summary of findings and recommendations]

## References

1. [Paper 1 - full citation with link]
2. [Paper 2 - full citation with link]
...

## Appendix: Search Details

- **Search queries used**: [list]
- **Papers excluded**: [count and reason]
- **Processing notes**: [any issues]
```

---

## Summary: The Agent's Mental Model

**Core workflow:**
1. Start broad, refine to specific research question
2. Plan multi-source strategy (discovery + vault + web)
3. Cast wide net, then filter by relevance
4. Download & queue papers (parallel processing)
5. Read everything systematically
6. Synthesize by themes/approaches (not by paper)
7. Check gaps, iterate if needed
8. Create comprehensive markdown report

**Key principles:**
- **Iterative refinement**: Start broad → narrow → focused
- **Multi-source**: Don't rely on single source
- **Quality over quantity**: 5 good papers > 20 mediocre
- **Systematic analysis**: Extract key info from each source
- **Theme-based synthesis**: Group by concepts, not papers
- **Gap awareness**: Know when to search more
- **Actionable output**: Report includes recommendations

**Success metric**: User has comprehensive understanding of research topic with detailed report they can reference/share.
