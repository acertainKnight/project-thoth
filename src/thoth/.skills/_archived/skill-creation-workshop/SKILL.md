---
name: Skill Creation Workshop
description: Collaboratively create and refine new skills through iterative design - validate needs, design structure, draft content, test, and refine.
---

# Skill Creation Workshop

Guide users (and yourself!) through creating new skills via iterative co-design.

## Quick Start: The Validation Question

**Before creating any skill, validate it's actually needed:**

```
Agent: "You want to create a skill for [X]. Let me check if this needs a skill.

**The 3 Tests**:

1. Is it ITERATIVE? (multiple back-and-forth cycles?)
   - ✓ Yes → Continue
   - ✗ No → Probably just a tool call

2. Is it CONVERSATIONAL? (requires guidance and feedback?)
   - ✓ Yes → Continue
   - ✗ No → Probably just documentation

3. Is it COMPLEX? (multi-step with decisions?)
   - ✓ Yes → Needs a skill!
   - ✗ No → Probably too simple

Based on [X], my assessment: [Pass/Fail + reasoning]

Should we proceed with creating a skill?"
```

### Examples of What DOESN'T Need a Skill

❌ "Summarize paper" → One tool call, no iteration
❌ "Search for papers" → Single operation
❌ "Show citation network" → Visualization, not workflow
❌ "Get paper metadata" → Data retrieval

### Examples of What DOES Need a Skill

✅ "Set up discovery" → Iterative refinement of config
✅ "Create research question" → Guided multi-phase process
✅ "Design new skill" → Collaborative design workflow
✅ "Optimize search strategy" → Test-refine-test cycle

---

## The Skill Creation Workflow

### Phase 1: Understand the Workflow

```
Agent: "Let's map out the workflow. Walk me through it:

1. What triggers this workflow? (user says/needs what?)
2. What's the starting state? (what does user have?)
3. What's the ending state? (what do they have after?)
4. What are the key decision points? (where do they need guidance?)
5. What are common problems? (where do users get stuck?)
6. How many iterations typically? (once? multiple refinements?)"
```

**Document the answers** - these become the skill structure.

### Phase 2: Design the Structure

**Core pattern for ALL skills:**

```markdown
## Quick Start
- The most common scenario (80% case)
- Standard opening conversation
- Get user from start → end quickly

## Diagnosis Section
- Decision trees for different starting points
- "If user has X → do Y"

## Conversation Patterns
- Pattern 1: [Most common case]
- Pattern 2: [Common variant]
- Pattern 3: [Edge case]

## Quick Reference Cards
- Card 1: [Key concept in 30 seconds]
- Card 2: [Another key concept]

## Refinement Patterns
- Problem 1 → Fix
- Problem 2 → Fix

## Troubleshooting
- Quick table: Problem | Solution
```

**Agent validates structure:**
```
Agent: "Based on your workflow, here's the proposed structure:

[Show structure outline]

Does this cover all the key phases? Missing anything?"
```

### Phase 3: Draft the Content

**Writing principles:**

1. **Action-first, not philosophy**
   - ❌ "Understanding the importance of keywords..."
   - ✅ "Ask user: 'What terms describe your topic?'"

2. **Conversation snippets, not instructions**
   - ❌ "The agent should help the user refine their keywords"
   - ✅ "Agent: 'Let's test those keywords. I'll run discovery now.'"

3. **Specific examples, not general advice**
   - ❌ "Consider various approaches"
   - ✅ "Option A: Raise threshold to 0.8"

4. **Scannable formatting**
   - Use tables, decision trees, bullet points
   - Short paragraphs (3-4 lines max)
   - Clear headers

**Agent drafts section by section:**
```
Agent: "Let's draft section by section. I'll write, you review.

**Section 1: Quick Start**
[Draft content]

How's this? Too verbose? Missing something?"
```

### Phase 4: Write the SKILL.md

**Template structure:**

```markdown
---
name: [Skill Name]
description: [One-line description of workflow - what it does, not what it is]
---

# [Skill Name]

[2-sentence overview of what this skill helps with]

## Quick Start: [The 80% Case]

### Standard Opening
```
Agent: "[Opening question/statement]"
```

[Most common conversation flow]

---

## Diagnosis: [Where Is The User?]

[Decision trees for different starting points]

---

## Conversation Patterns

### Pattern 1: [Name]
[Conversation flow with specific dialogue]

### Pattern 2: [Name]
[Another conversation flow]

---

## Quick Reference Cards

### Card 1: [Topic]
[Key information in scannable format]

---

## Refinement Patterns

### Refinement 1: [Problem]
**Symptom**: [What user reports]
**Fix**: [Specific solution]

---

## Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| [Issue] | [Solution] |

---

## Summary: The Agent's Mental Model

[Bullet points of key principles]
```

### Phase 5: Test the Skill

**Testing methodology:**

```
Agent: "Skill drafted! Let's test it. I'll:

1. Load the skill into my context
2. Pretend you're a user with [scenario]
3. Follow the skill's guidance
4. See if it actually works

Ready? Give me a test scenario."
```

**User provides scenario, agent role-plays using the skill**

**After test:**
```
Agent: "Test complete. What I noticed:

✓ [What worked well]
✗ [What was confusing/missing]
? [What was unclear]

Based on this, here are the fixes needed:
1. [Specific change]
2. [Specific change]

Want to refine and test again?"
```

### Phase 6: Refine Based on Feedback

**Common refinement needs:**

| Issue | Fix |
|-------|-----|
| Too verbose | Cut 50%, focus on actions |
| Unclear what to say | Add conversation snippets |
| Missing decision logic | Add decision tree |
| No troubleshooting | Add problem/solution table |
| Too abstract | Add specific examples |
| Can't scan quickly | Add formatting (tables, cards) |

**Iterative refinement:**
```
Agent: "Let me refine [section X]:

**Before** (too verbose):
[Show old version]

**After** (streamlined):
[Show new version]

Better?"
```

### Phase 7: Finalize and Deploy

**Pre-deployment checklist:**

```
Agent: "Before we finalize, let's check:

✓ Skill passes the 3 tests? (iterative, conversational, complex)
✓ Quick Start covers 80% case?
✓ Conversation patterns are copy-paste ready?
✓ Has decision trees for diagnosis?
✓ Has troubleshooting quick reference?
✓ Tested with real scenario?
✓ Agent can scan and understand in <2 minutes?

All checks passed? Let's save it!"
```

---

## Decision Tree: Does This Need a Skill?

```
User wants help with [X]
│
├─ Is it ONE tool call? → ❌ NO SKILL NEEDED
│  Example: "Summarize paper" → Just call summarize_paper()
│
├─ Is it just INFORMATION? → ❌ NO SKILL NEEDED
│  Example: "What sources exist?" → Just documentation
│
├─ Is it a SIMPLE sequence? → ❌ NO SKILL NEEDED
│  Example: "Download then process" → Two tool calls
│
└─ Is it ITERATIVE with DECISIONS? → ✅ SKILL NEEDED
   Example: "Set up discovery" → Test, analyze, refine, repeat
```

---

## Skill Anatomy Reference

### Section 1: Quick Start (REQUIRED)
**Purpose**: Get agent acting in 30 seconds
**Content**:
- Standard opening (what to say first)
- Most common conversation flow
- Expected outcome

**Length**: 50-100 lines

### Section 2: Diagnosis (REQUIRED)
**Purpose**: Handle different starting points
**Content**:
- 2-3 questions to understand user state
- Decision trees: "If X → do Y"

**Length**: 30-50 lines

### Section 3: Conversation Patterns (REQUIRED)
**Purpose**: Handle common scenarios
**Content**:
- 3-4 specific conversation flows
- Actual dialogue agent can copy-paste
- Each pattern: trigger → conversation → outcome

**Length**: 100-150 lines

### Section 4: Quick Reference Cards (REQUIRED)
**Purpose**: Fast lookup of key concepts
**Content**:
- 3-5 cards
- Each card: one concept in <10 lines
- Scannable format (bullets, tables)

**Length**: 50-75 lines

### Section 5: Refinement Patterns (REQUIRED)
**Purpose**: Handle when things go wrong
**Content**:
- 3-5 common problems
- Each: Symptom → Diagnosis → Fix
- Specific, actionable solutions

**Length**: 50-75 lines

### Section 6: Troubleshooting (REQUIRED)
**Purpose**: Quick fixes for known issues
**Content**:
- Table format: Problem | Solution
- 5-10 entries
- One-line fixes

**Length**: 20-30 lines

### Section 7: Advanced (OPTIONAL)
**Purpose**: Edge cases and deep dives
**Content**:
- Complex scenarios
- Detailed explanations
- Can use `<details>` to collapse

**Length**: Variable

---

## Good vs Bad Skill Content

### ❌ Bad: Philosophical/Instructional

```markdown
## Understanding Keywords

Keywords are fundamental to effective search. The agent should help
the user understand that keywords need to balance precision and recall.
There are many approaches to keyword optimization, and the agent should
guide the user through exploring these options.
```

**Why bad**: Tells agent TO help, not HOW to help

### ✅ Good: Action-Focused/Conversational

```markdown
## Quick Reference: Keywords

```
Agent: "Let's build your keywords in 2 steps:

1. What nouns describe your topic? [user answers]
2. What's the technical term for that? [user answers]

Keywords: [combine them]

Let's test these now."
```

**Why good**: Exact words to say, specific steps

---

### ❌ Bad: Abstract Principles

```markdown
## Source Selection

The agent should help users understand the trade-offs between different
discovery sources and guide them toward making informed decisions about
which sources best serve their research needs.
```

**Why bad**: No actionable guidance

### ✅ Good: Specific Recommendations

```markdown
## Card: Source Selection

**Default recommendations**:
- CS/ML/AI → arxiv + semantic_scholar
- Medical/Bio → pubmed + biorxiv
- Economics → openalex + ssrn

**Start with 2 sources**, add more only if missing papers.
```

**Why good**: Copy-paste decision logic

---

## Testing Checklist

### Test 1: Can Agent Understand Quickly?
- [ ] Read Quick Start in <1 minute
- [ ] Understand what skill does
- [ ] Know what to say to start conversation

### Test 2: Can Agent Execute?
- [ ] Conversation patterns are specific enough
- [ ] Decision trees have clear logic
- [ ] Quick reference cards are scannable

### Test 3: Does It Handle Failure?
- [ ] Refinement patterns cover common issues
- [ ] Troubleshooting table has real fixes
- [ ] Agent knows what to do when stuck

### Test 4: Is It Streamlined?
- [ ] No philosophical rambling
- [ ] Action-focused throughout
- [ ] Scannable formatting
- [ ] <400 lines total

### Test 5: Role-Play Test
- [ ] Agent loads skill
- [ ] User provides scenario
- [ ] Agent can execute workflow using skill
- [ ] Workflow reaches successful conclusion

---

## Refinement Patterns for Skills

### Refinement 1: Skill Too Abstract

**Symptom**: Agent reads skill but doesn't know what to say

**Fix**: Add conversation snippets
```markdown
Agent: "[Exact words to say]"
[User response]
Agent: "[Next exact words]"
```

### Refinement 2: Skill Too Long

**Symptom**: >500 lines, agent loses focus

**Fix**:
1. Cut philosophy/background - keep only actions
2. Move advanced content to separate file
3. Merge redundant sections

**Target**: <400 lines for main skill

### Refinement 3: No Clear Entry Point

**Symptom**: Agent doesn't know how to start

**Fix**: Add "Standard Opening" in Quick Start
```markdown
### Standard Opening
```
Agent: "[First thing to say every time]"
```
```

### Refinement 4: Missing Decision Logic

**Symptom**: Agent guesses what to do next

**Fix**: Add decision tree
```markdown
Check [X]:
├─ If A → Do this
├─ If B → Do that
└─ If C → Do other
```

### Refinement 5: No Troubleshooting

**Symptom**: Agent stuck when things go wrong

**Fix**: Add troubleshooting table with real fixes

---

## Common Skill Patterns

### Pattern 1: Setup Workflow
**Examples**: research-discovery-setup, research-question-creation

**Structure**:
1. Quick Start: Standard setup conversation
2. Diagnosis: Different starting points
3. Test: Try initial configuration
4. Refine: Iterate based on results
5. Deploy: Finalize and activate

### Pattern 2: Optimization Workflow
**Examples**: keyword optimization, threshold tuning

**Structure**:
1. Baseline: Current state assessment
2. Test: Try one change
3. Compare: Before vs after
4. Iterate: Repeat until optimal
5. Validate: Final check

### Pattern 3: Analysis Workflow
**Examples**: literature review, paper comparison

**Structure**:
1. Scope: What to analyze
2. Organize: Group by themes
3. Compare: Find patterns/gaps
4. Synthesize: Create output
5. Review: Validate completeness

### Pattern 4: Creation Workflow
**Examples**: skill creation, research question design

**Structure**:
1. Validate: Does this need to be created?
2. Design: Structure and components
3. Draft: Initial version
4. Test: Try it out
5. Refine: Improve based on test
6. Finalize: Lock it in

---

## Summary: Meta-Skill Principles

**What makes a good skill:**
1. Validates it's needed (passes 3 tests)
2. Action-focused (not philosophical)
3. Conversation patterns (copy-paste ready)
4. Scannable (tables, trees, cards)
5. Handles failure (refinement + troubleshooting)
6. Streamlined (<400 lines)

**The creation process:**
1. Validate → Design → Draft → Test → Refine → Deploy
2. Iterate until agent can execute workflow smoothly
3. Test with real scenario before finalizing

**Success metric**:
Agent can load skill, read Quick Start, and successfully guide user through workflow on first try.
