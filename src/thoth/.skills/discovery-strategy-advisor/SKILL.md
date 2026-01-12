---
name: Discovery Strategy Advisor
description: Optimize entire discovery workflow through test-and-refine cycles - choosing sources, adjusting thresholds, tuning frequency, and iterating based on actual results.
---

# Discovery Strategy Advisor

This skill guides you in optimizing the complete discovery workflow through collaborative testing, result analysis, and iterative refinement.

## When to Use This Skill

- User is setting up new automated discovery
- Initial discovery returns poor quality results
- Need to choose which sources to query
- Need to set relevance thresholds and frequency
- User asks "What settings should I use?"
- Discovery working but could be optimized
- Need to adjust strategy based on early results

## Overview

**The Problem**: Default discovery settings (all sources, 0.7 relevance, daily schedule, 50 papers) might not be optimal for every research question. One size doesn't fit all.

**Your Role**: Be a strategy consultant who helps users optimize their discovery configuration through test-and-refine cycles.

**The Goal**: Transform generic discovery setup into a fine-tuned strategy that delivers high-quality, relevant papers consistently.

## The Strategy Optimization Process

### Phase 1: Understand Research Goals

**Before recommending strategy, understand user's goals:**

```
Agent: To help optimize your discovery strategy, let me understand what you're aiming for:

**Volume Goals**:
- Do you want comprehensive coverage (find everything relevant)?
- Or focused quality (only the most relevant)?

**Time Commitment**:
- How much time to review papers? (10 mins/day? 1 hour/week?)
- This affects how many papers we should return

**Timeliness**:
- Need bleeding-edge latest research?
- Or building foundational understanding (older papers OK)?

**Use Case**:
- Active research project (need all details)?
- Staying current in your field (highlights only)?
- Learning a new area (foundational + recent)?

Your answers shape the optimal strategy.
```

### Phase 2: Source Selection Strategy

**Help choose optimal sources:**

```
Agent: Thoth can query multiple sources. Let's choose the best ones for your topic.

[Call list_available_sources to show options]

For "[user's topic]", here's my recommendation:

**Definitely Include**:
✓ arxiv - Best for CS/ML preprints, very current
✓ semantic_scholar - AI-powered search, broad coverage

**Consider Adding**:
? openalex - Comprehensive, includes published papers (more than just preprints)
? crossref - DOI metadata, catches published versions

**Probably Skip**:
✗ pubmed - Medical/bio focus, not relevant for your CS topic
✗ biorxiv - Biology preprints, not relevant

We can start with the "Definitely Include" sources and add more if we're missing papers.

Sound good? Or would you like to adjust?
```

**Source Selection Principles**:

1. **Domain Matching**:
   - CS/AI → arxiv, semantic_scholar, openalex
   - Medical → pubmed, biorxiv
   - Interdisciplinary → use multiple sources

2. **Coverage vs Noise**:
   - Few sources = Less noise, might miss papers
   - Many sources = More coverage, more duplicates
   - Sweet spot: 2-4 sources for most topics

3. **Preprints vs Published**:
   - Preprint sources (arxiv, biorxiv) = Cutting edge, less peer review
   - Published sources (crossref, openalex) = More vetted, may lag

### Phase 3: Initial Configuration

**Set up initial test configuration:**

```
Agent: Let's start with sensible defaults, then refine based on results:

**Initial Settings**:
- Sources: arxiv, semantic_scholar
- Schedule: Daily at 3AM (for fast-moving field)
- Min Relevance: 0.7 (balanced filter)
- Max Papers: 25/day (manageable daily volume)
- Auto-download PDFs: Yes

**Rationale**:
- Daily schedule: "[Topic]" is active area, new papers frequently
- 0.7 relevance: Not too permissive (0.6) or too strict (0.8)
- 25/day: ~10-15 minutes to skim titles/abstracts

We'll run this for a few days, then adjust based on what we see.

Want to modify anything before the first run?
```

### Phase 4: Test and Evaluate

**Run initial discovery and analyze results:**

```
Agent: Great! I've set up your discovery with our initial settings. Let's run 
it once NOW to see what we get, then we can refine.

[Trigger run_discovery_for_question]

---

[After results come back]

Agent: Results are in! Let's analyze:

**What We Got**:
- 15 papers from arxiv
- 8 papers from semantic_scholar  
- Total: 23 papers

**Quick Assessment**:
Looking at the titles, I see:
- 12 papers seem highly relevant (52%)
- 8 papers seem somewhat relevant (35%)
- 3 papers seem off-topic (13%)

**Questions for you**:
1. Do the "highly relevant" papers match what you're looking for?
2. Are the "off-topic" papers completely wrong, or just tangential?
3. Is 23 papers/day manageable? Too many? Too few?

Let me know and we'll adjust!
```

### Phase 5: Iterative Refinement

**Adjust based on feedback:**

#### Refinement Pattern 1: Too Many Irrelevant Papers

```
User: About half these papers aren't really relevant.

Agent: Got it - we need to increase precision. Let's try:

**Option A - Stricter Relevance Threshold**:
Change 0.7 → 0.75 or 0.8
Effect: Filters out marginally relevant papers

**Option B - More Specific Keywords**:
Add more focused keywords to narrow search
Effect: Better targeting from the start

**Option C - Source Reduction**:
Drop one source if it's producing mostly noise
Effect: Less volume, better signal-to-noise

Looking at the off-topic papers, they mostly came from [source X]. 
I'd recommend Option A (increase threshold to 0.75) + Option C (drop source X).

Let's try that and run discovery again tomorrow. We'll see if quality improves!
```

#### Refinement Pattern 2: Too Few Papers

```
User: I'm only getting 3-5 papers per day. I want more coverage.

Agent: Let's increase volume while maintaining quality:

**Option A - Lower Relevance Threshold**:
Change 0.7 → 0.65
Effect: More papers, some may be less relevant

**Option B - Add More Sources**:
Add openalex or crossref
Effect: More coverage across different indexes

**Option C - Broader Keywords**:
Add related terms to cast wider net
Effect: Catches papers using different terminology

I'd suggest trying Option B first (add openalex), since we want MORE papers 
while keeping quality high. If that's not enough, we can lower threshold.

Sound good?
```

#### Refinement Pattern 3: Wrong Mix of Old/New

```
User: I'm getting mostly old papers from 2018-2020. I want more recent work.

Agent: Let's adjust temporal focus:

**Solution 1 - Date Filter**:
Add filter: Only papers from last 2 years (2024-2026)
Effect: Only recent work

**Solution 2 - Source Adjustment**:
Prioritize arxiv (very current) over crossref (includes older published papers)
Effect: Naturally biases toward recent

**Solution 3 - Keyword Addition**:
Add keywords like "recent", "2024", "state-of-the-art"
Effect: Keywords bias toward newer papers

For your use case (wanting cutting-edge research), I'd recommend Solution 1 
(date filter to last 2 years). This is cleanest approach.

Let's add that filter and rerun!
```

### Phase 6: Frequency Optimization

**Tune discovery frequency:**

```
Agent: You've been running daily discovery for a week. Let's evaluate the frequency:

**What we've seen**:
- Day 1: 23 papers
- Day 2: 18 papers
- Day 3: 22 papers
- Day 4: 6 papers (light day)
- Day 5: 19 papers
- Day 6: 15 papers
- Day 7: 20 papers

Average: ~17 papers/day

**Frequency Assessment**:
Your field has consistent daily activity. Options:

**Keep Daily** (Current):
- Pro: Never miss new papers, stay very current
- Con: Daily review commitment required

**Switch to Every Other Day**:
- Pro: ~34 papers every 2 days, less frequent review
- Con: Slightly less timely (24hr delay)

**Switch to Weekly**:
- Pro: One review session (~120 papers/week), batch processing
- Con: Week delay on latest papers

For your active research area, I'd stick with daily. But if review is 
becoming a burden, we could move to every-other-day.

What's your preference?
```

---

## Strategic Patterns

### Pattern 1: Conservative Start, Expand if Needed

```
Agent: My general strategy: Start conservative, expand if we're missing things.

**Week 1**: 
- 2 sources (arxiv + semantic_scholar)
- 0.75 relevance (strict)
- 20 papers/day max

**Evaluate**: Are we missing important papers?

**Week 2** (if needed):
- Add 1 more source (openalex)
- Lower to 0.7 relevance
- Increase to 30 papers/day

This ensures quality first, then expands coverage as needed.
```

### Pattern 2: A/B Testing

```
Agent: Let's A/B test two strategies:

**Strategy A**: Strict filtering
- Sources: arxiv only
- Threshold: 0.8
- Expected: 10-15 high-quality papers/day

**Strategy B**: Broad coverage
- Sources: arxiv + semantic_scholar + openalex
- Threshold: 0.65
- Expected: 30-40 papers/day with more noise

Let's run Strategy A for 3 days, then Strategy B for 3 days.
You tell me which mix of volume vs quality works better for you!
```

### Pattern 3: Adaptive Strategy

```
Agent: Let's set up an adaptive strategy that adjusts based on paper volume:

**High Activity Days** (lots of new papers):
- Threshold 0.75 (stricter to manage volume)

**Low Activity Days** (few new papers):
- Threshold 0.65 (more permissive to ensure coverage)

**Implementation**:
Set max_papers_per_run to 25, relevance to 0.7
- If hitting 25 papers (high activity), natural cutoff
- If getting <10 papers (low activity), you get them all

This self-adjusts to field's publication rhythm!
```

---

## Source-Specific Strategies

### ArXiv Strategy

**Best for**: CS, Physics, Math preprints

```
Agent: Since your topic is in CS/ML, arxiv is essential. Strategy:

**Category Filtering**:
- Definitely: cs.LG (Machine Learning)
- Consider: cs.AI, cs.CL (if NLP-related)
- Skip: Other cs.* unless directly relevant

**Temporal Focus**:
- Arxiv is VERY current (papers within days of submission)
- Don't need to go back far - last 6 months covers most active research

**Keywords**:
- Use technical terms that appear in arxiv paper titles
- Arxiv abstracts are detailed, so keywords match well
```

### Semantic Scholar Strategy

**Best for**: Cross-domain AI research

```
Agent: Semantic Scholar uses AI to find relevant papers. Strategy:

**Advantage**: 
- Understands semantic similarity (not just keyword matching)
- Good at finding related work you might not have keywords for

**Consideration**:
- Can be broader than arxiv (more fields covered)
- Use stricter relevance threshold (0.75+) if you get too much noise

**Best Practice**:
- Let semantic scholar be your "discovery" source (finds unexpected papers)
- Let arxiv be your "comprehensive" source (catches all CS papers)
```

### PubMed / BioRxiv Strategy

**Best for**: Medical, biological sciences

```
Agent: For medical/bio topics:

**PubMed**:
- Comprehensive medical literature
- Use MeSH terms if possible
- More published papers, less preprints

**BioRxiv**:
- Biology preprints (like arxiv for bio)
- Very current, less peer-reviewed

**Strategy**: Use both if you want complete coverage (published + preprints)
```

---

## Threshold Optimization Guide

### Understanding Relevance Scores

```
Agent: Let me explain how relevance thresholds work:

**0.5-0.6**: Very permissive
- Pro: Catches everything possibly related
- Con: Lots of tangentially related papers

**0.65-0.75**: Balanced (RECOMMENDED)
- Pro: Good mix of coverage and precision
- Con: Might miss some relevant papers

**0.8-0.9**: Very strict
- Pro: Only highly relevant papers
- Con: Might miss relevant papers with different terminology

**0.95+**: Extremely strict
- Pro: Basically perfect matches only
- Con: Will miss most papers, even relevant ones

**Default recommendation**: Start at 0.7, adjust based on results.
```

### Threshold Adjustment Flowchart

```
Agent: Here's how to adjust your threshold:

**Getting TOO MANY papers** (>40/day)?
→ Increase threshold by 0.05
→ Check if quality improves
→ Repeat if still too many

**Getting TOO FEW papers** (<5/day)?
→ Decrease threshold by 0.05
→ Check if you're missing good papers
→ Repeat if still too few

**Getting GOOD VOLUME but BAD QUALITY**?
→ Problem isn't threshold, it's keywords or sources
→ Refine keywords or remove noisy source

**Getting GOOD VOLUME and GOOD QUALITY**?
→ Don't change anything! It's working!
```

---

## Complete Strategy Review

After a few weeks, do comprehensive review:

```
Agent: You've been running discovery for 2 weeks. Let's do a complete strategy review:

**Volume Analysis**:
- Average: 18 papers/day
- Range: 6-28 papers/day
- Total: 252 papers collected

**Quality Analysis** (based on your feedback):
- You marked 45% as "highly relevant"
- You marked 35% as "somewhat relevant"
- You marked 20% as "not relevant"

**Source Breakdown**:
- ArXiv: 65% of papers, 50% highly relevant
- Semantic Scholar: 35% of papers, 35% highly relevant

**Recommendations**:
1. ✓ Volume is good (manageable daily amount)
2. ✓ Quality is acceptable (45% highly relevant is solid)
3. ? Consider slightly higher threshold (0.7 → 0.75) to reduce "not relevant" from 20% to ~10%
4. ✓ Source mix is good, keep both

**Proposed Adjustment**:
Change threshold to 0.75, keep everything else.
This should reduce volume to ~15 papers/day with better quality.

Thoughts?
```

---

## Example Strategy Sessions

### Example: Optimizing for Busy Researcher

```
User: I want to stay current but don't have much time.

Agent: Perfect - let's optimize for time efficiency:

**Goal**: ~5-10 highly relevant papers per week, not daily

**Strategy**:
- Sources: arxiv only (most relevant for CS)
- Schedule: Weekly on Monday
- Threshold: 0.8 (very strict - only best papers)
- Max papers: 15/week
- Keywords: Very specific to your exact interest

**Result**:
- One 15-minute review session per week
- Only the cream of the crop papers
- Won't miss major advances in your specific area

Want to try this "time-efficient" strategy?

---

[After 2 weeks]

Agent: How's the time-efficient strategy working?

User: I'm getting 8-12 papers per week, almost all are relevant, and the weekly 
review only takes 15 minutes. Much better!

Agent: Excellent! That's the sweet spot. Should we keep this, or any adjustments?
```

### Example: Comprehensive Coverage Strategy

```
User: I'm writing a survey paper. I need to find ALL relevant papers.

Agent: Got it - comprehensive coverage is the goal. Strategy:

**Week 1-2** (Cast Wide Net):
- Sources: ALL available (arxiv, semantic_scholar, openalex, crossref)
- Threshold: 0.65 (permissive)
- Schedule: Daily
- Max papers: 50/day

**Goal**: Find everything possibly relevant

**Week 3-4** (Refine):
- Based on what we found, narrow to most productive sources
- Increase threshold to reduce noise
- Focus on gaps we identified

**Process**:
You'll get a LOT of papers initially (30-50/day). Review them, mark 
relevant/irrelevant. After 2 weeks, we'll analyze patterns and optimize.

This is intensive but ensures you don't miss key papers for your survey.

Ready for the fire hose?

---

[After 2 weeks]

Agent: You've reviewed 500+ papers! Let's optimize for weeks 3-4:

Looking at your highly-relevant papers:
- 60% came from arxiv
- 25% came from semantic_scholar
- 15% from other sources

Also, papers before 2020 weren't very relevant (survey focuses on recent work).

**Refined Strategy**:
- Keep arxiv + semantic_scholar, drop others
- Add date filter: 2020-present only
- Increase threshold to 0.7
- Expected: 20-25 papers/day (more manageable)

You've already done the heavy lifting. Now we refine to catch remaining gaps!
```

---

## Summary: Key Principles

1. **Test Before Committing**: Run discovery once, evaluate, then refine
2. **Start Conservative**: Strict threshold + few sources, expand if needed
3. **Iterate Based on Results**: Use actual results to guide adjustments
4. **Match User's Time**: Strategy should fit their review capacity
5. **Source Selection Matters**: 2-4 relevant sources beats "all sources"
6. **Threshold is Key Knob**: Easiest way to adjust volume/quality
7. **Monitor and Adjust**: Review strategy every 1-2 weeks
8. **Quality > Quantity**: Better to get 10 perfect papers than 50 mixed

**The Best Strategy**: The one that gives you relevant papers you can actually review consistently. Everything else is optimization!
