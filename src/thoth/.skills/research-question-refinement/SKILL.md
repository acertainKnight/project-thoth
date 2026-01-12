---
name: Research Question Refinement
description: Help users clarify vague research interests into specific, actionable research questions through interactive dialogue and iterative refinement.
---

# Research Question Refinement

This skill guides you in helping users transform broad, vague research interests into specific, well-defined research questions that will yield better discovery results.

## When to Use This Skill

- User says "I want to learn about X" (very broad topic)
- User provides vague research interests like "AI", "quantum computing", "climate change"
- User asks for papers on a topic but their request is too general
- Discovery returns too many irrelevant results (likely too broad)
- User seems unsure what they really want to know
- User says "I'm interested in everything related to..."

## Overview

**The Problem**: Most users start with broad topics ("I want papers about AI") when what they really need are specific research questions ("How do attention mechanisms in transformers enable long-range dependencies?").

**Your Role**: Be a conversational guide who helps users discover what they *really* want to know through questions, examples, and iterative refinement.

**The Goal**: Transform "I want to learn about AI" into a specific, focused research question that will produce relevant, high-quality papers.

---

## The Refinement Process

### Phase 1: Acknowledge and Explore

**When user provides broad topic**, acknowledge it positively and begin exploration:

```
User: I want to learn about artificial intelligence.

Agent: Great! AI is a fascinating field with many exciting areas. To help you find 
the most relevant papers, let's narrow down what aspect of AI interests you most.

Here are some major areas in AI - which resonates with you?
- Machine learning and neural networks
- Natural language processing (chatbots, translation, text generation)
- Computer vision (image recognition, object detection)
- Reinforcement learning (game playing, robotics)
- AI safety and ethics
- Or something else entirely?
```

**Key Techniques**:
- ✅ Positive acknowledgment: "Great topic!"
- ✅ Explain why narrowing helps: "to find the most relevant papers"
- ✅ Offer concrete sub-areas with examples in parentheses
- ✅ Always include "or something else" option
- ❌ Don't say "that's too broad" or "you need to be more specific"

### Phase 2: Progressive Narrowing

**Use a funnel approach**: Start broad, then progressively narrow through dialogue.

**Example Flow**:
```
User: I'm interested in natural language processing.

Agent: Excellent! NLP is a rich area. Let's get more specific. Within NLP, 
there are several hot topics:

- Large language models (LLMs) and transformers
- Sentiment analysis and opinion mining
- Machine translation
- Question answering systems
- Text summarization
- Named entity recognition and information extraction

Which of these catches your eye? Or is there a specific problem you're trying to 
solve with NLP?
```

```
User: Large language models sound interesting.

Agent: Perfect! LLMs are definitely where a lot of exciting research is happening. 
Now, what aspects of LLMs are you most curious about?

For example:
- Architecture improvements (new model designs, attention mechanisms)
- Training methods (pre-training strategies, fine-tuning techniques)
- Applications (specific use cases, domain adaptation)
- Capabilities and limitations (what LLMs can/can't do)
- Memory and context handling
- Efficiency and optimization (making them smaller/faster)
- Safety and alignment (preventing harmful outputs)

Which direction interests you most? And is there a particular problem or question 
you're trying to answer?
```

**Key Techniques**:
- Offer 5-7 concrete options at each level
- Include brief explanations in parentheses
- Ask about specific problems they're trying to solve
- Each response narrows the funnel
- Always ask "what are you curious about?" or "what problem are you trying to solve?"

### Phase 3: Uncover the Real Question

**Goal**: Move from topic to actual research question.

**Questions to Ask**:
1. "What would you like to understand better about [topic]?"
2. "Is there a specific problem you're trying to solve?"
3. "What gap in your knowledge are you trying to fill?"
4. "Are you looking for how-to information, or understanding why things work?"
5. "Is this for a project, or general learning?"

**Example**:
```
User: I'm interested in memory and context handling in LLMs.

Agent: Great focus! Now let's turn this into a research question. What specifically 
would you like to understand about memory in LLMs?

For instance, are you wondering:
- How to extend context windows beyond current limits?
- How LLMs remember information across conversations?
- How memory architectures compare to human memory?
- Which memory mechanisms work best for specific tasks?
- How to make memory more efficient?

Or is there a different angle you're approaching this from?
```

**Key Techniques**:
- Use "What would you like to understand?" questions
- Offer specific question formulations as examples
- Look for user's underlying motivation
- Help them articulate what they don't know

### Phase 4: Formulate the Refined Question

**Once you understand their interest**, help formulate a clear research question.

**Good Research Question Characteristics**:
- ✅ Specific: Focuses on one clear aspect
- ✅ Actionable: Can guide concrete searches
- ✅ Answerable: Papers likely exist on this
- ✅ Scoped: Not too broad, not too narrow
- ❌ Avoid: "Everything about X"
- ❌ Avoid: So narrow only 1-2 papers exist

**Example**:
```
User: I want to know how to extend context windows.

Agent: Perfect! Let me help you formulate this as a clear research question. 

Based on our conversation, here's a specific research question:

"What techniques and architectures enable transformers to handle longer context 
windows, and what are the trade-offs between different approaches?"

This question:
- Focuses on a specific aspect (extending context)
- Asks about both methods AND trade-offs (gives you complete picture)
- Is actionable for search (clear keywords)
- Has active research (you'll find plenty of papers)

Does this capture what you want to learn? Would you like to adjust it?
```

**Key Techniques**:
- State the refined question clearly
- Explain why it's good (teach the user)
- Ask for feedback: "Does this capture it?"
- Be ready to iterate if they want adjustments

### Phase 5: Validate and Refine

**Test the question** with the user before proceeding:

```
Agent: Let's make sure this question will get you what you need:

Research Question: "What techniques enable transformers to handle longer contexts, 
and what are the trade-offs?"

Keywords this suggests:
- "transformer", "long context", "context window"
- "attention mechanism", "memory"
- "efficiency", "scalability"

This should find papers on:
- Novel architectures (Sparse Transformers, Longformer, etc.)
- Memory-augmented models
- Compression techniques
- Performance comparisons

Does this match what you're looking for? Would you like to:
- Make it more specific (focus on one technique type)?
- Broaden it slightly (include related approaches)?
- Adjust the focus?
```

**Key Techniques**:
- Show what keywords the question implies
- Preview what types of papers they'll find
- Offer specific refinement options
- Get explicit confirmation before proceeding

---

## Common Refinement Patterns

### Pattern 1: "Too Broad" → Narrow Down

**User starts with**: "I want papers about machine learning"

**Refinement Steps**:
1. Machine learning → Supervised learning, unsupervised, reinforcement learning?
2. Supervised learning → Classification, regression, or both?
3. Classification → What kind of data? Images, text, tabular?
4. Image classification → What aspect? Architectures, training methods, applications?
5. Architectures → Comparing architectures or understanding one specific type?

**Result**: "How do convolutional neural network architectures compare to vision transformers for image classification tasks?"

### Pattern 2: "Too Specific" → Broaden Slightly

**User starts with**: "I want papers about BERT-base fine-tuning for sentiment analysis on Twitter data about cryptocurrency"

**Refinement Steps**:
```
Agent: That's very specific - you might find only a few papers on exactly that. 
Let's think about what you're really after:

Are you interested in:
- BERT fine-tuning techniques (could apply to any domain)?
- Sentiment analysis of crypto discussions (any model)?
- Social media sentiment analysis (any topic)?

What's the core question you're trying to answer?
```

**Possible Broadened Questions**:
- "What fine-tuning strategies work best for BERT on domain-specific text?"
- "How do NLP models perform on cryptocurrency sentiment analysis?"
- "What are effective approaches for sentiment analysis on social media?"

### Pattern 3: "Multiple Interests" → Separate or Connect

**User starts with**: "I'm interested in quantum computing and machine learning"

**Two Approaches**:

**Option A - Separate**:
```
Agent: Those are both fascinating fields! Would you like to:
1. Create separate research questions for each, OR
2. Focus on where they intersect (quantum machine learning)?

If separate, we can refine each topic individually.
If intersection, we can explore quantum algorithms for ML or using ML for quantum.
```

**Option B - Find Connection**:
```
Agent: Interesting combination! These fields intersect in some exciting ways. 
Are you interested in:
- Using quantum computing to improve machine learning (quantum ML)?
- Using machine learning to solve quantum computing problems?
- Understanding both fields separately?

What draws you to this combination?
```

### Pattern 4: "Problem-Based" → Question-Based

**User starts with**: "I need to make my model faster"

**Refinement**:
```
Agent: Let's turn that practical problem into a research question. 

First, tell me more:
- What kind of model? (neural network, decision tree, etc.)
- What's slow? (training time, inference time, or both?)
- What's your target? (real-time inference, faster training, etc.)
- What resources do you have? (GPU, TPU, CPU only?)

Based on your answers, we can formulate a question like:
"What techniques enable efficient inference for large transformer models on 
resource-constrained devices?"
```

---

## Interactive Techniques

### Technique 1: The Option Menu

Present 5-7 specific options instead of asking open-ended questions:

❌ **Bad**: "What aspect of AI interests you?"

✅ **Good**: 
```
What aspect of AI interests you?
- Neural network architectures
- Natural language processing
- Computer vision
- Reinforcement learning
- AI safety and ethics
- Applied AI in specific domains
- Something else (please describe)
```

### Technique 2: The Example Probe

Use examples to clarify:

```
Agent: To help me understand, which of these example questions feels closer to 
what you're after?

A) "How do transformers work?" (understanding the basics)
B) "How can I improve transformer performance?" (applied/practical)
C) "What are the latest advances in transformers?" (staying current)
D) "How do different transformer variants compare?" (comparative analysis)
```

### Technique 3: The Why Dig

Ask "why" to uncover real motivation:

```
User: I want to learn about transformers.

Agent: Great! What's drawing you to transformers specifically? For example:
- Working on a project that uses them?
- Trying to understand how ChatGPT-style models work?
- Interested in the fundamental attention mechanism?
- Looking to implement one yourself?

Knowing your "why" helps me point you to the right papers.
```

### Technique 4: The Trade-Off Test

Help users realize they need focus:

```
Agent: I want to make sure you get what you need. Right now, your topic 
would return about 10,000 papers on transformers. 

Would you prefer:
- A broad survey of the whole field (10-20 survey/review papers)?
- Deep dive on one specific aspect (50-100 focused papers)?
- Staying current with latest research (recent papers only)?

Each approach requires different search strategies. What serves your goal best?
```

### Technique 5: The Keywords Preview

Show what their question implies:

```
Agent: Based on your interest in "extending context in transformers", 
here are the keywords we'd search for:

- "transformer", "context window", "long context"
- "attention mechanism", "sparse attention"
- "memory", "memory-augmented"

This would find papers on architectures like Longformer, Reformer, and 
memory-augmented transformers.

Does that sound like what you're after? Or should we adjust?
```

---

## Handling Different User Types

### The Beginner

**Characteristics**: New to the field, unclear terminology, very broad interests

**Approach**:
- Explain jargon in parentheses
- Offer more structure and guidance
- Use analogies and examples
- Be patient with very broad starting points
- Teach them what makes a good research question

**Example**:
```
User: I want to learn about AI.

Agent: Welcome to AI research! It's a huge field, so let's find your entry point. 
Think of AI like a big city with different neighborhoods:

- Machine Learning (teaching computers from examples)
- Computer Vision (helping computers "see" images)
- Natural Language Processing (working with human language)
- Robotics (physical AI systems)

Which "neighborhood" sounds most interesting to you? Don't worry if you're not sure - 
we can explore and find what clicks!
```

### The Expert

**Characteristics**: Knows terminology, has specific interests, may be too narrow

**Approach**:
- Match their technical level
- Help them broaden if too narrow
- Focus on recent advances or comparisons
- Understand their research goals
- Less hand-holding, more peer discussion

**Example**:
```
User: I'm looking for papers on sparse attention mechanisms in transformer architectures.

Agent: Great - you know exactly what you're after! That's a very active area. 
To help you find the most relevant papers, let me ask:

- Are you interested in specific sparse attention patterns (local, strided, 
  global tokens)?
- Comparing different sparse approaches (Longformer vs Reformer vs BigBird)?
- Implementation and efficiency trade-offs?
- Theoretical analysis of expressiveness?

Also, should I include related work on:
- Memory-augmented alternatives to sparse attention?
- Linear attention mechanisms?

This will help me optimize the search strategy.
```

### The Problem-Solver

**Characteristics**: Has a practical problem, may not know the research terminology

**Approach**:
- Start with their problem
- Translate problem to research concepts
- Find the research that addresses their need
- Bridge practical and theoretical

**Example**:
```
User: My chatbot keeps forgetting what users said earlier in the conversation.

Agent: Ah, you're dealing with a context management challenge! In research terms, 
this relates to memory and long-term dependencies in conversational AI.

Let me help you find papers that address this. Your problem breaks down into:

1. Short-term memory (within single conversation) - "context window" and "attention"
2. Long-term memory (across conversations) - "memory networks" and "episodic memory"
3. Efficient context management - "context compression" and "retrieval"

Which aspect is most critical for your use case?
- Making the bot remember more within one conversation?
- Having it recall previous conversations?
- Efficiently managing long dialogues?

This will guide us to the right papers.
```

---

## Validation Checklist

Before finalizing the refined question, ensure:

- [ ] **Specific enough**: Focuses on 1-2 clear aspects, not "everything"
- [ ] **Searchable**: Contains clear keywords that would appear in papers
- [ ] **Answerable**: Recent papers likely exist on this topic
- [ ] **Scoped appropriately**: Not so broad you get 10,000 papers, not so narrow you get 2
- [ ] **Aligned with user's goal**: Matches what they said they want to learn/solve
- [ ] **Iteratively refined**: You've asked questions and incorporated their feedback
- [ ] **Explicitly confirmed**: User agreed this captures their interest

## Red Flags & How to Address

### 🚩 Red Flag: User says "I want everything about X"

**Response**:
```
I hear you want comprehensive coverage! However, "everything" on a big topic 
like [X] could mean thousands of papers. 

Let's think about this strategically. Would you prefer:
1. A few high-quality survey papers that summarize the field?
2. Recent papers on the most active sub-topics?
3. Foundational papers plus recent advances?

Or we could create multiple focused research questions that together cover 
the field. What sounds most useful?
```

### 🚩 Red Flag: User is vague even after several questions

**Response**:
```
I want to make sure I understand what you're looking for. Let me try a different 
approach:

Can you tell me:
- What will you DO with these papers? (project, thesis, curiosity, work problem)
- What's a question you wish you knew the answer to?
- If you found the perfect paper, what would its title be?

Sometimes it helps to think about the end goal rather than the topic itself.
```

### 🚩 Red Flag: User keeps adding topics

"I'm interested in X, and also Y, and also Z..."

**Response**:
```
You have wide-ranging interests! That's great, but for effective paper discovery, 
we should focus on one research question at a time.

Let's do this: which of these topics is most urgent or interesting to you RIGHT NOW?
- [Topic X]
- [Topic Y]
- [Topic Z]

We can refine that one first, set up discovery for it, and then come back to 
refine the others. That way you get high-quality results for each instead of 
scattered results that try to cover everything.
```

---

## Example Refinement Sessions

### Example 1: Complete Beginner

```
User: I want to learn about deep learning.

Agent: Great choice - deep learning is behind a lot of exciting AI advances! 
To point you to the most relevant papers, let's figure out which aspect of 
deep learning interests you most.

Think about what sparked your interest in deep learning:
- Seeing cool applications like image generators or chatbots?
- Wanting to understand how neural networks actually work?
- Needing it for a specific project?
- Just general curiosity about the field?

What brought you here?

---

User: I saw some cool image generators like DALL-E and want to understand how they work.

Agent: Ah perfect! You're interested in generative models for images. That's a 
specific and exciting area. 

There are a few different approaches to image generation:
- GANs (Generative Adversarial Networks) - two networks competing
- Diffusion models (like DALL-E 2, Midjourney) - gradually refining noise
- VAEs (Variational Autoencoders) - learning compressed representations
- Transformer-based (like DALL-E 1) - adapted from language models

Since you mentioned DALL-E, sounds like diffusion models might be your focus?
Or are you interested in comparing these different approaches?

---

User: Yeah, diffusion models sound right.

Agent: Excellent! Now let's narrow it down just a bit more. With diffusion models 
for image generation, what would you most like to understand?

- How the math/algorithm works (understanding the core technique)?
- How to control what gets generated (text-to-image, conditioning)?
- How to train these models yourself (practical implementation)?
- Recent advances and improvements to the technique?
- Or just a general overview of the whole field?

---

User: I want to understand how they control what gets generated from text.

Agent: Perfect! Now we have a clear research question. Let me formulate it:

**Refined Research Question:**
"How do diffusion models condition image generation on text descriptions, and 
what techniques enable better text-to-image alignment?"

This question will find papers on:
- Text conditioning mechanisms (CLIP embeddings, cross-attention)
- Classifier-free guidance
- Text-to-image diffusion architectures
- Prompt engineering and control

Keywords: "diffusion models", "text-to-image", "conditional generation", 
"text conditioning", "CLIP"

Does this capture what you want to learn? Should we adjust anything?

---

User: That's perfect!

Agent: Excellent! I'll use this refined question for discovery. This should give 
you high-quality papers specifically about text conditioning in diffusion models, 
rather than getting lost in thousands of general deep learning papers.

Would you like me to set up automated discovery for this research question?
```

### Example 2: Expert Researcher

```
User: I need papers on efficient attention mechanisms.

Agent: Got it - you're looking at attention efficiency. That's a very active area 
right now. To optimize the search, let me understand your specific focus:

Are you interested in:
- Specific sparse attention patterns (Longformer, Reformer, BigBird)?
- Linear attention mechanisms (Performer, RWKV)?
- Approximate attention methods?
- Hardware-efficient implementations?
- Theoretical analysis of attention complexity?

And what's your target: reducing compute, memory, or both?

---

User: Specifically linear attention that maintains model quality.

Agent: Ah, so the quality-efficiency trade-off in linear attention is your focus. 
That's a great question because many linear attention methods sacrifice quality.

Let me refine this:

**Research Question:**
"What linear attention mechanisms maintain competitive model performance compared 
to standard softmax attention, and what are the trade-offs between efficiency 
gains and quality?"

This targets:
- Performer, Linformer, AFT variations
- Quality benchmarks and comparisons
- Analysis of where linear attention succeeds vs fails
- Hybrid approaches

Should I also include:
- Memory-efficient attention alternatives?
- Recent 2024-2025 innovations in this space?

---

User: Yes, include recent innovations, but focus on methods with theoretical guarantees.

Agent: Perfect addition. Updated question:

**Research Question:**
"What linear attention mechanisms with theoretical guarantees maintain competitive 
performance, and what recent advances (2024-2025) improve the quality-efficiency 
trade-off?"

Filters:
- Date: 2023-2025 (to catch very recent work)
- Must include: "linear attention", "theoretical", "complexity"
- Venues: Top ML conferences (NeurIPS, ICML, ICLR) and theory venues

This more selective search will find ~20-40 highly relevant papers rather than 
hundreds. Sound good?
```

---

## After Refinement: Next Steps

Once the research question is refined, guide the user to next steps:

```
Great! We've refined your research question to:

"[Refined question here]"

Now let's set this up for discovery. We'll:
1. Create a research question in Thoth
2. Choose the best sources (ArXiv, Semantic Scholar, etc.)
3. Set up keywords and topics
4. Schedule automatic discovery

Should we also set up:
- Related keyword variations to catch more papers?
- Email alerts when new papers match?
- A minimum quality threshold?

Let's continue with the research question creation process!

[Transition to research-question-creation skill]
```

---

## Summary: Key Principles

1. **Start Positive**: Never make users feel bad for being vague
2. **Progressive Narrowing**: Funnel from broad to specific through dialogue
3. **Offer Concrete Options**: Don't ask open-ended questions without examples
4. **Uncover Real Motivation**: Ask why they're interested
5. **Formulate Clearly**: State the refined question explicitly
6. **Validate Before Proceeding**: Get explicit confirmation
7. **Teach While Refining**: Help them understand what makes a good question
8. **Adapt to User Level**: Beginners need more guidance, experts need less

**Your Goal**: Transform "I want papers about AI" into "What techniques enable efficient inference for large language models on edge devices, and how do they compare in accuracy vs speed trade-offs?" through conversation, not interrogation.

Be curious, be patient, be collaborative!
