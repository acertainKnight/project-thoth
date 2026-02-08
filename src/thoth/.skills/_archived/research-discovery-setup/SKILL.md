---
name: Research Discovery Setup
description: Set up effective automated discovery - from vague idea to working system in one streamlined conversation.
---

# Research Discovery Setup

Help users configure automated discovery that delivers quality papers consistently.

## Quick Start: The 5-Minute Setup

**Most common scenario**: User has a vague research interest and needs help setting up discovery.

### Standard Opening
```
Agent: "Let's get your discovery set up! Three quick questions:

1. What research area interests you? (even if vague - we'll refine it)
2. How much time daily to review papers? (5 mins? 30 mins?)
3. Need cutting-edge research or learning fundamentals?

I'll configure everything based on your answers."
```

### After User Answers
```
Agent: "Perfect! Based on what you said, here's your starter configuration:

**Research Focus**: [refined 1-sentence version]
**Keywords**: [2-4 core search terms]
**Sources**: [1-2 most relevant APIs]
**Schedule**: [frequency based on time commitment]
**Quality Filter**: [threshold based on volume needs]

This should get you ~[X] papers [per day/week] to review.

Ready to test it now?"
```

### After Running Test Discovery
```
Agent: "Test results: [X] papers found

Quick scan of titles:
✓ [Y] papers look highly relevant
~ [Z] papers look somewhat relevant
✗ [W] papers look off-topic

Is this mix working for you? Too many? Too few? Wrong topic?"
```

**Then**: Refine based on feedback (see Refinement Patterns below)

---

## Diagnosis: Where Is The User?

### Ask These 3 Questions First

**Q1: Do they know what they want to research?**
- ✓ Clear idea → Skip to keyword building
- ✗ Vague idea → Question refinement needed

**Q2: Have they tried searching yet?**
- ✓ Yes, bad results → Diagnose what's wrong (see Troubleshooting)
- ✗ Not yet → Run initial test

**Q3: How much time for review?**
- 5-10 min/day → ~10-15 papers/day max
- 30 min/week → ~20-30 papers/week batch
- 1+ hour/week → ~50+ papers/week comprehensive

---

## Conversation Patterns

### Pattern 1: Vague Idea → Focused Question

**User**: "I'm interested in AI and finance"

**Agent**: "Let's narrow that down. Pick ONE direction to start:
- Using AI to predict stock prices?
- Using AI to analyze financial news sentiment?
- Using AI to detect fraud?
- Something else?

We can always expand later."

**User picks one**

**Agent**: "Great! Now let's scope it:
- What specific data? (news? social media? earnings calls?)
- What specific outcome? (daily predictions? risk scoring? trading signals?)
- What timeframe? (real-time? daily? weekly?)

Example refined question: 'Can Twitter sentiment predict daily stock returns?'

Does something like that capture your interest?"

### Pattern 2: Bad Results → Diagnosis

**Agent**: "Let's diagnose the problem. I need:
1. What keywords are you using?
2. Show me 2 papers you WANT
3. Show me 2 papers you're GETTING but don't want"

**[User provides]**

**Agent analyzes and identifies issue**:
- Keywords too broad → Add specific terms
- Keywords too narrow → Add synonyms, lower threshold
- Wrong domain → Add negative keywords
- Wrong timeframe → Add date filter

**Agent**: "The issue is [specific problem]. Here's the fix: [specific change].

Want me to test this now?"

### Pattern 3: Optimization (Already Working)

**Agent**: "You've been running for [X] days. Let's optimize:

**Current results**:
- [Y] papers/day on average
- You marked [Z]% as relevant

**Assessment**: [Good/Too many/Too few/Wrong mix]

**Recommendations**: [1-2 specific tweaks]

Want to try these adjustments?"

---

## Decision Trees

### Too Many Papers (>40/day)

```
Check relevance:
├─ >70% relevant → Just cap max_papers to 25
├─ 40-70% relevant → Increase threshold +0.1
└─ <40% relevant → Keywords too broad, add specific terms
```

### Too Few Papers (<5/day)

```
Check specificity:
├─ Keywords very specific → Broaden terms, add synonyms
├─ Keywords normal → Lower threshold -0.1
└─ Field is just slow → Adjust schedule to weekly
```

### Wrong Topic Papers

```
Check mismatch:
├─ Different domain (crypto vs stocks) → Add negative keywords
├─ Different time period (old papers) → Add date filter: last 2 years
├─ Different methodology → Add method-specific terms
└─ Different language → Add language filter
```

### Missing Key Papers

```
User shows example paper:
1. Look at that paper's title/abstract
2. Extract key terms it uses
3. Add those terms to search
4. Test again
```

---

## Quick Reference Cards

### Card 1: Question Refinement (30 seconds)
Ask 3 questions:
1. "What aspect interests you most?"
2. "Prediction? Analysis? Comparison?"
3. "Any constraints: domain/time/method?"

Result: "[Specific searchable question]"

### Card 2: Keyword Building
```
Question → Keywords (2-step):
1. Extract core nouns from question
2. Add 1 technical synonym if they used plain language

Example:
Q: "Can Twitter predict stocks?"
K: "twitter sentiment stock prediction"
```

### Card 3: Source Selection
**Default recommendations**:
- CS/ML/AI → arxiv + semantic_scholar
- Medical/Bio → pubmed + biorxiv
- General Science → openalex + crossref
- Economics/Social → openalex + ssrn

**Start with 2 sources max**, add more only if missing papers.

### Card 4: Threshold Settings
```
Default: 0.7 (works for 80% of cases)

Adjustments:
- User wants only best papers → 0.8
- User wants comprehensive coverage → 0.65
- Getting <5 papers/day → Lower by 0.05
- Getting >40 papers/day → Raise by 0.05
```

### Card 5: Schedule Guide
```
Based on user's available time:
- 10 min/day → Daily, 10-15 papers, threshold 0.75
- 30 min/3x week → Every other day, 20-30 papers, threshold 0.7
- 1 hour/week → Weekly, 50 papers, threshold 0.65
```

---

## Refinement Patterns

### Refinement 1: Too Much Noise

**Symptom**: <50% of papers are relevant

**Diagnosis**: Filter is too permissive OR keywords too broad

**Fix**:
```python
Option A: Increase threshold (0.7 → 0.75 or 0.8)
Option B: Add specific terms to keywords
Option C: Remove noisy source if one is producing junk

Recommendation: Try A first (fastest), then B if needed
```

### Refinement 2: Too Little Coverage

**Symptom**: <10 papers/day in active field

**Diagnosis**: Filter too strict OR keywords too narrow

**Fix**:
```python
Option A: Lower threshold (0.7 → 0.65)
Option B: Add synonym terms to keywords
Option C: Add another relevant source

Recommendation: Try B first (maintains quality), then A
```

### Refinement 3: Wrong Time Period

**Symptom**: Getting papers from 2015-2019, user wants recent

**Fix**:
```python
Add date filter: published_after="2022-01-01"

Or for cutting-edge: published_after="2024-01-01"
```

### Refinement 4: Domain Mismatch

**Symptom**: Getting crypto papers when researching stocks

**Fix**:
```python
Add negative keywords:
exclude_terms = ["cryptocurrency", "bitcoin", "crypto", "blockchain"]
```

---

## Troubleshooting Quick Reference

| Problem | Instant Fix |
|---------|-------------|
| Zero results | Lower threshold to 0.6, broader keywords |
| 100+ results/day | Raise threshold to 0.8, add specific terms |
| All old papers (>3 years) | Add date filter: last 2 years |
| Papers in wrong language | Add language filter: English |
| Wrong scientific domain | Add negative keywords for that domain |
| Too many duplicates | Normal - Thoth auto-deduplicates by DOI/title |
| Missing recent papers | Add arxiv source (most current) |
| Missing published papers | Add openalex or crossref |

---

## Advanced Scenarios

### Scenario: Comprehensive Literature Review

**User**: "I'm writing a survey paper, need EVERYTHING"

**Agent**: "Comprehensive strategy:
- Sources: ALL available (arxiv, semantic_scholar, openalex, crossref)
- Threshold: 0.65 (permissive)
- Schedule: Daily for 2 weeks
- Max: 50 papers/day

You'll get 400-700 papers total. This is the 'fire hose' approach.
After 2 weeks, we'll refine based on what you found.

Ready for high volume?"

### Scenario: Staying Current (Minimal Time)

**User**: "Just want to stay current, very busy"

**Agent**: "Time-efficient strategy:
- Sources: arxiv only (most current for your field)
- Threshold: 0.8 (very strict - only best)
- Schedule: Weekly on Monday
- Max: 10 papers/week

One 15-minute review session per week.
You'll catch major advances without daily commitment.

Sound good?"

### Scenario: Learning New Field

**User**: "I'm new to this field, need foundational papers"

**Agent**: "Learning strategy:
- Sources: openalex + semantic_scholar (broader coverage)
- Threshold: 0.7 (balanced)
- Date filter: 2019-present (recent but not bleeding edge)
- Max: 20 papers/week

Mix of recent reviews and important papers.
Good for building understanding.

Ready to start?"

---

## Source-Specific Notes

### ArXiv
- **Best for**: CS, Physics, Math, Stats preprints
- **Freshness**: Papers within days of submission
- **Peer review**: Minimal (pre-publication)
- **When to use**: Need cutting-edge, active research areas

### Semantic Scholar
- **Best for**: AI-powered semantic search
- **Freshness**: Mix of preprints and published
- **Coverage**: Broad, finds related papers well
- **When to use**: Want discovery of unexpected connections

### PubMed
- **Best for**: Medical, biomedical sciences
- **Freshness**: Published papers (peer-reviewed)
- **Coverage**: Comprehensive for medicine
- **When to use**: Medical/bio research only

### OpenAlex
- **Best for**: General academic research
- **Freshness**: Mix of everything
- **Coverage**: Most comprehensive (200M+ papers)
- **When to use**: Want broad coverage across fields

### Crossref
- **Best for**: DOI metadata
- **Freshness**: Published papers only
- **Coverage**: Journal articles, conferences
- **When to use**: Need published/citable papers

---

## Testing and Validation

### After Initial Setup
```
Agent: "I've configured your discovery. Before scheduling it, let's test:

[Run discovery once]

Got [X] papers. Let's review together:
1. Look at top 5 titles - relevant?
2. Any obvious misses or noise?
3. Is [X] papers manageable for you?

Based on your feedback, we'll adjust before going live."
```

### Weekly Check-In Pattern
```
Agent: "You've been running for a week. Quick review:

**Volume**: [X] papers/day average
**Your feedback**: [Y]% marked as relevant

[If >70% relevant]: "This is working well! Any tweaks needed?"
[If <50% relevant]: "We need to refine. The issue is likely [diagnosis]"
```

---

## Summary: The Agent's Mental Model

1. **Start simple**: 2 sources, 0.7 threshold, reasonable schedule
2. **Test immediately**: Run discovery once to validate
3. **Analyze results**: Look at actual papers with user
4. **Refine based on evidence**: Adjust what's broken
5. **Iterate**: Test again after changes
6. **Deploy when good**: Set schedule and let it run

**The goal**: Get user from "vague idea" to "working discovery" in one conversation, with working system at the end.

**Success metric**: User gets relevant papers they can actually review consistently.
