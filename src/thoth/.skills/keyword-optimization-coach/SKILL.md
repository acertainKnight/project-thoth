---
name: Keyword Optimization Coach
description: Iteratively improve search keywords through conversation, testing variations, and refining based on results to maximize relevant paper discovery.
---

# Keyword Optimization Coach

This skill guides you in helping users develop optimal keyword sets for paper discovery through collaborative brainstorming, testing, and iterative refinement.

## When to Use This Skill

- User provides only 1-2 generic keywords ("machine learning", "AI")
- Keywords are too broad or too narrow for effective discovery
- Initial discovery returns too many irrelevant papers
- Initial discovery returns too few papers
- User is unsure what keywords to use
- User asks "What keywords should I search for?"
- Need to expand keyword coverage for comprehensive discovery

## Overview

**The Problem**: The difference between "machine learning" and ["transformer architectures", "attention mechanisms", "self-supervised learning", "pre-training strategies"] is thousands of irrelevant papers vs. highly targeted results.

**Your Role**: Be a collaborative brainstorming partner who helps users discover the keywords that will find the papers they actually want.

**The Goal**: Transform weak keyword sets into comprehensive, targeted keywords that balance coverage and precision.

---

## The Keyword Optimization Process

### Phase 1: Assess Current Keywords

When user provides initial keywords, assess them:

**Questions to Ask Yourself**:
- How many keywords? (1-2 is too few, 10+ might be too many)
- How specific? (Generic like "AI" or specific like "sparse attention"?)
- What level? (High-level concepts or technical implementation terms?)
- Missing aspects? (Are there obvious related terms they haven't included?)

**Example Assessment**:
```
User: I want to search for "machine learning"

Agent: Let me work with you to develop stronger keywords. Right now "machine learning" 
is very broad - it would return papers on everything from decision trees to neural 
networks to reinforcement learning.

Let's collaborate to build a keyword set that targets exactly what you're after. 
From our earlier conversation, you're interested in [specific aspect]. 

Let's brainstorm keywords together - I'll suggest some, you tell me what resonates, 
and we'll refine from there. Sound good?
```

**Key Techniques**:
- ✅ Acknowledge their starting point positively
- ✅ Explain why refinement helps
- ✅ Frame it as collaboration, not correction
- ❌ Don't say "those keywords are bad"

### Phase 2: Collaborative Brainstorming

**Work together** to generate keyword candidates:

```
Agent: Let's brainstorm keywords for [their research question]. I'll start with 
some suggestions, and you tell me which ones feel right:

Core Terms (the main concepts):
- "transformer" ✓ definitely include this
- "attention mechanism" - describes the core technique
- "self-attention" - more specific variant

Technical Variations:
- "multi-head attention" - if architecture details matter
- "scaled dot-product attention" - very technical
- "attention weights" - if understanding mechanism

Related Concepts:
- "encoder-decoder" - if looking at translation/seq2seq
- "positional encoding" - if interested in position handling
- "feed-forward network" - the other main component

Which of these resonate with what you want to find? Any I'm missing that you'd add?
```

**Brainstorming Categories**:

1. **Core Concepts** - Main ideas (1-2 keywords)
2. **Technical Terms** - Implementation details (2-4 keywords)
3. **Synonyms & Variants** - Different ways to say the same thing (1-3 keywords)
4. **Acronyms & Full Forms** - Both "LLM" and "large language model"
5. **Related Methods** - Adjacent approaches
6. **Application Areas** - If domain-specific

**Key Techniques**:
- Organize suggestions into categories
- Mark some as "definitely include"
- Explain what each keyword would find
- Ask user to pick what resonates
- Always ask "what am I missing?"

### Phase 3: Test Core vs. Expanded

**Help users understand coverage vs. precision trade-off**:

```
Agent: Great! So we have two possible keyword sets. Let me show you the difference:

**Conservative Set** (High Precision):
- "transformer architecture"
- "attention mechanism" 
- "self-attention"

This will find: Papers specifically about transformer models and attention.
Might miss: Related approaches, surveys that mention transformers briefly.

**Expanded Set** (Better Coverage):
Core terms + these additions:
- "BERT" - famous transformer example
- "GPT" - another famous example  
- "encoder-decoder"
- "sequence modeling"

This will find: All the above PLUS papers on specific models, applications, 
and related approaches.
Might include: Some papers that mention these terms peripherally.

Which approach serves your goal better? Or should we find a middle ground?
```

**Key Techniques**:
- Show two options explicitly
- Explain what each finds
- Explain what each might miss
- Let user choose based on their goals
- Offer "middle ground" option

### Phase 4: Add Strategic Keywords

**Suggest strategic additions** based on common patterns:

#### Pattern 1: Acronyms + Full Forms
```
Agent: Let's make sure we catch papers that use different terminology. 
For example:

Some papers say "LLM", others say "large language model". 
Some say "NLP", others "natural language processing".

Should we include both forms? This ensures we don't miss papers based on 
author's terminology preference.
```

#### Pattern 2: Synonyms & Variants
```
Agent: In research, people use different terms for the same concept:
- "training" vs "learning" vs "optimization"
- "model" vs "network" vs "architecture"
- "performance" vs "accuracy" vs "effectiveness"

For your topic, I'd suggest including:
- Both "training" and "optimization"
- Both "model" and "architecture"

This catches papers regardless of author's word choice.
```

#### Pattern 3: Problem & Solution Keywords
```
Agent: Let's include keywords for both the problem and solution:

**Problem keywords** (what you're trying to solve):
- "long-range dependencies"
- "context window limitations"
- "memory constraints"

**Solution keywords** (approaches to solve it):
- "sparse attention"
- "memory-efficient"
- "context extension"

This finds papers discussing the problem AND papers proposing solutions.
```

#### Pattern 4: Temporal Keywords
```
Agent: If you want recent work, we can add temporal keywords:
- "recent advances"
- "state-of-the-art"
- "survey" (if you want overview papers)
- "benchmark" (if you want comparison papers)

These help prioritize certain types of papers. Interested?
```

### Phase 5: Review and Validate

**Present the final keyword set** for validation:

```
Agent: Excellent! Here's our optimized keyword set:

**Core Terms** (Must have - 3 keywords):
✓ transformer architecture
✓ attention mechanism
✓ self-attention

**Specific Variants** (Catch specific papers - 4 keywords):
✓ multi-head attention
✓ sparse attention
✓ cross-attention
✓ self-supervised

**Model Names** (Catch applied papers - 3 keywords):
✓ BERT
✓ GPT
✓ transformer models

**Total: 10 keywords**

This balance should give you:
- Strong coverage of transformer papers
- Specific technical approaches
- Both foundational and applied work
- Mix of general and specific terms

Does this feel comprehensive? Any you'd remove or add?
```

**Validation Questions**:
- "Does this cover everything you're interested in?"
- "Any keywords feel off-target?"
- "Are we missing any important aspects?"

### Phase 6: Iterative Refinement

**Be ready to iterate** based on feedback:

```
User: I don't really care about BERT and GPT specifically.

Agent: Got it! Let's remove the model names since you're interested in the 
general techniques, not specific implementations. 

Updated keyword set:

**Core Terms**:
✓ transformer architecture
✓ attention mechanism
✓ self-attention

**Technical Variants**:
✓ multi-head attention
✓ sparse attention
✓ cross-attention
✓ self-supervised

**Total: 7 keywords** - more focused!

This targets the underlying mechanisms and techniques rather than specific models.
Better?

---

User: Yes! But should we add something about efficiency?

Agent: Great instinct! If efficiency is important to you, let's add:

✓ efficient transformers
✓ memory-efficient attention
✓ computational complexity

Now we'll catch papers on both the techniques AND their optimization.
Does that complete the set?
```

---

## Keyword Strategy Patterns

### Strategy 1: Funnel Keywords (Broad to Specific)

Start broad, add specificity:

**Tier 1 - Field Level**:
- "natural language processing"
- "language models"

**Tier 2 - Approach Level**:
- "transformer"
- "attention mechanism"

**Tier 3 - Technical Level**:
- "multi-head attention"
- "scaled dot-product"

**Use Case**: When user wants comprehensive coverage from foundational to cutting-edge.

### Strategy 2: Cluster Keywords (Related Concepts)

Group related concepts:

**Cluster 1 - Architecture**:
- "transformer architecture"
- "encoder-decoder"
- "attention layers"

**Cluster 2 - Training**:
- "pre-training"
- "fine-tuning"
- "transfer learning"

**Cluster 3 - Applications**:
- "text generation"
- "machine translation"
- "question answering"

**Use Case**: When user interested in multiple aspects of a topic.

### Strategy 3: Boolean-Style Keywords

Think about AND/OR logic:

**Must Include (AND)**:
- "transformer" (core topic)
- "attention" (core mechanism)

**At Least One Of (OR)**:
- "efficiency" OR "optimization" OR "compression"

**Example Search Logic**:
Papers must mention transformers AND attention, and should discuss efficiency.

### Strategy 4: Exclusion Keywords

Sometimes knowing what to exclude helps:

```
Agent: I notice "transformer" also appears in electrical engineering papers. 
We can use negative keywords to exclude those:

Include:
- transformer architecture
- attention mechanism

Exclude (if source supports it):
- electrical transformer
- power systems
- voltage

This prevents electrical engineering papers from polluting results.
```

---

## Interactive Techniques

### Technique 1: The Synonym Game

```
Agent: Let's play the synonym game! I'll say a keyword, you tell me other ways 
researchers might say the same thing:

Me: "model"
Variations: "network", "architecture", "system"

Me: "training"  
Variations: "learning", "optimization", "fitting"

Me: "performance"
Variations: "accuracy", "effectiveness", "results", "metrics"

For your search, which of these variations should we include?
```

### Technique 2: The Paper Title Test

```
Agent: Let's test our keywords against imaginary paper titles. If you saw these 
titles, which should our keywords catch?

1. "Efficient Attention Mechanisms for Long-Context Transformers" - ✓ Should catch
2. "BERT for Domain-Specific Text Classification" - ✓ Should catch
3. "Convolutional Neural Networks for Image Recognition" - ✗ Shouldn't catch
4. "A Survey of Sequence-to-Sequence Models" - ? Maybe catch (is this relevant?)

Based on #4 - are sequence-to-sequence models relevant to you? If yes, we should 
add "seq2seq" and "sequence-to-sequence" to our keywords.
```

### Technique 3: The Coverage Check

```
Agent: Let's make sure we're not missing important aspects. For transformers, 
research typically covers:

✓ Architecture design - Covered by "transformer architecture", "attention mechanism"
✓ Training methods - Covered by "pre-training", "self-supervised"
✗ Applications - NOT covered yet!
✗ Interpretability - NOT covered yet!
✓ Efficiency - Covered by "efficient", "sparse attention"

The gaps are applications and interpretability. Are those important to you?
If yes, we should add:
- Applications: "text generation", "translation", "classification"
- Interpretability: "attention visualization", "interpretability", "explainability"
```

### Technique 4: The "Too Many Results" Refiner

```
Agent: Let me help you narrow down. You're getting too many results because 
keywords are too broad. Let's add specificity:

Instead of: "machine learning"
Try: "supervised learning" OR "deep learning" OR "neural networks"

Instead of: "optimization"
Try: "gradient descent" OR "Adam optimizer" OR "learning rate scheduling"

Which specific methods/approaches matter for your research?
```

### Technique 5: The "Too Few Results" Expander

```
Agent: You're only getting a handful of results because keywords are too specific. 
Let's broaden strategically:

Current: "sparse multi-head self-attention in BERT-style encoders"
This is VERY specific - maybe only 2-3 papers.

Let's expand in layers:
- Keep "sparse attention" (specific technique you care about)
- Expand "BERT-style encoders" to "transformer encoders" (broader)
- Add related terms: "efficient attention", "attention approximation"

This finds papers on sparse attention in ANY transformer, not just BERT.
Still interested?
```

---

## Handling Common Situations

### Situation 1: User Has No Keywords

**User says**: "I don't know what keywords to use"

**Response**:
```
Agent: No problem! Let's build them from your research question. You said you're 
interested in [X]. Let me suggest starting keywords based on that:

If your research question is about [problem/approach], typical keywords include:
- [main concept 1]
- [main concept 2]
- [technical term 1]

Do any of these feel like they're in the right direction? Or should I suggest 
different angles?
```

### Situation 2: User Provides Only Acronyms

**User says**: "Search for NLP, LLM, BERT"

**Response**:
```
Agent: Good start with the acronyms! Let's expand these to catch more papers:

NLP → Add: "natural language processing", "language understanding"
LLM → Add: "large language model", "language model"  
BERT → This is specific model, but add: "transformer", "pre-trained model"

Some papers spell out acronyms, others don't. Including both forms ensures 
we don't miss relevant work. Should we add the expanded forms?
```

### Situation 3: User Lists Many Generic Keywords

**User says**: "machine learning, AI, algorithms, data, models, optimization"

**Response**:
```
Agent: I see you've cast a wide net! These keywords are all relevant but very 
general - you'd get tens of thousands of papers on everything from medical AI 
to self-driving cars.

Let's narrow to what you specifically care about. From our conversation, you're 
interested in [specific aspect]. How about we replace these generic terms with 
more targeted ones:

Instead of "AI", "machine learning" →
Use: "deep learning", "neural networks", "[specific architecture]"

Instead of "optimization" →  
Use: "gradient descent", "Adam", "[specific optimization method]"

This targets your actual interest rather than the entire field. Thoughts?
```

### Situation 4: User Wants "Everything"

**User says**: "Just use all possible keywords related to X"

**Response**:
```
Agent: I appreciate wanting comprehensive coverage! However, too many keywords 
can actually hurt results - the search becomes unfocused.

Instead of "all keywords", let's use a strategic set that covers different aspects:

**Option A - Comprehensive Set** (12-15 keywords):
Cover major subtopics, techniques, and applications broadly

**Option B - Focused Set** (5-7 keywords):
Target exactly what you care about most, ignore periphery

**Option C - Layered Set**:
Start with focused set, then add more if needed based on initial results

Which approach serves your goal best? I'd recommend Option C - start focused, 
expand if we're missing important papers.
```

---

## Keyword Quality Checklist

Before finalizing keywords, verify:

- [ ] **Right Specificity**: Not too broad ("AI") or too narrow ("BERT-base fine-tuning on SST-2")
- [ ] **Coverage**: Covers main aspects user cares about
- [ ] **Balanced Count**: 5-12 keywords typically (not 2, not 30)
- [ ] **Multiple Levels**: Mix of general and specific terms
- [ ] **Synonyms Included**: Both "LLM" and "large language model"
- [ ] **Technical + Conceptual**: Both "transformer" (concept) and "attention mechanism" (technical)
- [ ] **Tested with User**: User confirmed these match their interest
- [ ] **Actionable**: Would actually appear in relevant papers

---

## Example Optimization Sessions

### Example 1: From Weak to Strong Keywords

```
User: I want papers on AI.

Agent: Let's develop strong keywords together! "AI" is very broad - it covers 
everything from chess-playing algorithms to medical diagnosis systems.

What aspect of AI interests you most? For example:
- Machine learning (learning from data)
- Computer vision (understanding images)
- Natural language processing (understanding text)
- Robotics (physical AI systems)

---

User: Machine learning, I guess.

Agent: Good! Machine learning is still quite broad though. Let me show you major 
areas within ML:

- Supervised learning (learning from labeled examples)
- Deep learning (neural networks with many layers)
- Reinforcement learning (learning through trial and error)
- Unsupervised learning (finding patterns without labels)

Which of these catches your interest?

---

User: Deep learning with neural networks.

Agent: Perfect! Now we're getting specific. Within deep learning, what aspects 
are you curious about?

- Architectures (how networks are designed - CNNs, transformers, etc.)
- Training techniques (how to train networks effectively)
- Applications (using deep learning for specific tasks)
- Theory (understanding why/how deep learning works)

---

User: Architectures, especially the transformer thing everyone talks about.

Agent: Excellent! Now we can build targeted keywords. Let's brainstorm:

**Core Terms**:
- "transformer" - the main architecture
- "neural architecture" - general term for network design
- "deep learning architecture" - broader context

**Technical Terms**:
- "attention mechanism" - the key innovation in transformers
- "self-attention" - specific attention type
- "multi-head attention" - technical detail

**Related**:
- "encoder-decoder" - common transformer structure
- "sequence modeling" - what transformers are often used for

From these, which 5-7 feel most relevant to what you want to learn about?

---

User: transformer, attention mechanism, self-attention, encoder-decoder, and maybe 
neural architecture?

Agent: Great selection! Let me refine these slightly:

✓ "transformer architecture" (better than just "transformer" - more specific)
✓ "attention mechanism"
✓ "self-attention"  
✓ "encoder-decoder architecture"
✓ "neural architecture" 

Should we also add:
- "multi-head attention" (specific technical detail)
- "positional encoding" (another key transformer component)

These would catch more technical papers. Or do you prefer keeping it more general?

---

User: Let's add multi-head attention but skip positional encoding.

Agent: Perfect! Final optimized keyword set:

**Keywords**:
1. transformer architecture
2. attention mechanism
3. self-attention
4. multi-head attention
5. encoder-decoder architecture
6. neural architecture

**What these will find**:
- Papers on transformer models and variants
- Technical deep-dives on attention mechanisms
- Architectural comparisons and innovations
- Papers using transformers for various tasks

**What these might miss**:
- Specific model implementations (BERT, GPT) unless they discuss architecture
- Non-transformer architectures (which you don't want anyway)

This is a solid set! Want to use these for your research question?

---

[Successfully transformed "AI" into 6 targeted transformer architecture keywords]
```

### Example 2: Refining Too-Technical Keywords

```
User: I want papers with these keywords: "sparse-blocked local-attention with 
global-token mechanisms in encoder-only transformers for long-document processing"

Agent: Wow, that's incredibly specific! You clearly know what you're looking for. 
However, this might be TOO specific - you might only find 1-2 papers with exactly 
this combination.

Let me show you a layered approach:

**Core (Must-Have)**:
- "sparse attention"
- "long-document"
- "transformer"

These are your essential requirements.

**Specific Variants** (Nice-to-Have):
- "local attention"
- "global tokens"
- "encoder-only"

These add specificity but aren't strict requirements.

**Related Approaches**:
- "efficient transformers"
- "attention approximation"

Catches related work you might want to know about.

This layered approach finds your exact interest PLUS related work you might find 
valuable. The original hyper-specific phrasing might exist in only 1-2 papers, 
while this finds 20-30 highly relevant papers.

Thoughts?

---

User: That makes sense. Should we keep all three layers?

Agent: I'd recommend starting with Core + Specific Variants (8 keywords total). 
This finds papers directly on your topic.

Then, if you want broader context, we can add the Related Approaches layer later.

Sound good?
```

---

## After Optimization: Integration

Once keywords are optimized, integrate with research question:

```
Agent: Excellent! We've developed a strong keyword set:

[List keywords]

These keywords will work with your research question:
"[User's refined question]"

Together, the question defines WHAT you're looking for, and keywords define 
the LANGUAGE papers use to describe it.

Next steps:
1. Use these keywords in your research question setup
2. We can also add topics/categories to further refine
3. Set up automated discovery with these keywords

Ready to continue with research question setup?
```

---

## Summary: Key Principles

1. **Collaborate, Don't Dictate**: Frame as brainstorming together
2. **Educate as You Go**: Explain why certain keywords work
3. **Show Trade-Offs**: Coverage vs precision, broad vs specific
4. **Test with User**: Have them validate keywords feel right
5. **Iterate Freely**: Expect multiple rounds of refinement
6. **Think in Layers**: Core terms + variants + related concepts
7. **Balance Quantity**: 5-12 keywords is the sweet spot
8. **Include Synonyms**: Both "LLM" and "large language model"

**Remember**: Perfect keywords are discovered through dialogue, not delivered as a list. Be curious about what they want, help them articulate it through keyword choices, and refine until they say "yes, that's exactly right!"
