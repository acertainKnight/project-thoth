---
name: Research Question Creation
description: Guide users through creating effective research questions for automated paper discovery. Use when user wants to set up automated paper discovery or create new search queries.
---

# Research Question Creation Workflow

This skill guides you through helping users create research questions for automated paper discovery in the Thoth system.

## When to Use This Skill

- User says "I want to search for papers about..."
- User asks about discovering new research
- User wants to set up automated alerts
- User needs help defining search criteria
- User mentions wanting to track a research topic

## Overview

Research questions in Thoth define:
- **WHAT to search for**: Keywords, topics, authors
- **WHICH sources to query**: ArXiv, PubMed, CrossRef, OpenAlex, BioRxiv, custom workflows
- **HOW OFTEN to search**: Daily, weekly, monthly schedules
- **QUALITY THRESHOLD**: Minimum relevance score for matches

## Workflow Steps

### 1. Discovery Phase

**Goal**: Understand what the user wants to research.

**Questions to Ask**:
- "What research area or topic are you interested in?"
- "Can you describe the main research question you're exploring?"
- "Are there specific aspects or subtopics you want to focus on?"

**Actions**:
- Listen actively to user's research interests
- Help clarify vague or broad topics
- Identify the core research question

**Example Conversation**:
```
User: I want to find papers about AI memory systems.

Agent: Great! Let's set up automated discovery for AI memory systems. 
To help create an effective research question, could you tell me more about what 
specific aspects of AI memory systems you're interested in? For example:
- Long-term memory in language models?
- Memory architectures for agents?
- Episodic vs semantic memory?
- Or all of the above?
```

### 2. Keyword Brainstorming

**Goal**: Identify effective search keywords.

**Process**:
1. Ask user for initial keywords they think are relevant
2. Suggest related terms and synonyms
3. Help refine keywords for better coverage
4. Aim for 3-7 high-quality keywords

**Guidance**:
- Use specific technical terms (e.g., "transformer attention" not just "AI")
- Include alternative phrasings (e.g., both "LLM" and "large language model")
- Consider acronyms and full terms
- Think about related concepts

**Example**:
```
Agent: Based on your interest in AI memory systems, here are some keyword suggestions:
- Core terms: "memory", "retrieval", "agent memory"
- Related: "context management", "long-term memory", "episodic memory"
- Technical: "memory architectures", "stateful agents", "memory augmentation"

Which of these resonate with your research focus? Any others you'd like to add?
```

### 3. Source Selection Phase

**Goal**: Choose appropriate discovery sources.

**Action**: Call `list_available_sources` to show options.

**Available Sources**:
- **arxiv**: Best for computer science, physics, math preprints
- **pubmed**: Medical and biological sciences
- **crossref**: DOI metadata, wide academic coverage
- **openalex**: Comprehensive open access database
- **biorxiv**: Biological sciences preprints
- **semantic_scholar**: AI-powered search across fields
- **Custom workflows**: User-created browser automation workflows

**Guidance for Selection**:
- Computer Science/AI → arxiv, semantic_scholar, openalex
- Medical/Biology → pubmed, biorxiv
- Interdisciplinary → use multiple sources or "*" for all
- Specific venues → consider custom workflows

**Example**:
```
Agent: Now let's choose which sources to query. I'll show you what's available.
[calls list_available_sources]

For AI memory systems research, I'd recommend:
- arxiv: For the latest CS preprints
- semantic_scholar: For AI-focused search
- openalex: For comprehensive coverage

Would you like to use these three, or would you prefer to query all sources?
```

### 4. Topics and Categories

**Goal**: Identify relevant academic categories/topics.

**For ArXiv**: Suggest specific categories
- cs.AI (Artificial Intelligence)
- cs.LG (Machine Learning)
- cs.CL (Computation and Language)
- cs.NE (Neural and Evolutionary Computing)

**For Other Sources**: General topic areas work

**Example**:
```
Agent: For ArXiv searches, I can filter by specific categories. For your research, 
I'd suggest:
- cs.AI (Artificial Intelligence)
- cs.LG (Machine Learning)

Should we include both of these?
```

### 5. Schedule and Frequency

**Goal**: Set up automated discovery schedule.

**Options**:
- **daily**: For rapidly evolving fields (AI, ML)
- **weekly**: For moderate-pace research areas
- **monthly**: For slower-moving or niche topics

**Default Time**: 3:00 AM (can be customized)

**Example**:
```
Agent: How often would you like to check for new papers?
- Daily: Best for fast-moving fields like AI/ML
- Weekly: Good for most research areas
- Monthly: For slower-paced or niche topics

I'd recommend daily checks for AI memory systems since it's an active area.
```

### 6. Quality Thresholds

**Goal**: Set relevance and filtering criteria.

**Parameters**:
- **min_relevance_score**: 0.0-1.0 (default: 0.7)
  - 0.6-0.7: Cast a wider net
  - 0.7-0.8: Balanced (recommended)
  - 0.8-0.9: Very focused, high precision

- **max_articles_per_run**: 1-500 (default: 50)
  - Adjust based on how broad the topic is

**Example**:
```
Agent: Let's set quality thresholds. I recommend:
- Minimum relevance: 0.7 (captures relevant papers without too much noise)
- Max articles per run: 50 (manageable daily volume)

Would you like to adjust these?
```

### 7. Review and Refinement

**Goal**: Confirm all parameters before creation.

**Actions**:
1. Summarize all collected parameters
2. Ask if user wants to modify anything
3. Suggest improvements if you see issues

**Example**:
```
Agent: Let me summarize your research question:

**Name**: AI Memory Systems Research
**Keywords**: memory, retrieval, agent memory, stateful agents
**Topics**: cs.AI, cs.LG
**Sources**: arxiv, semantic_scholar, openalex
**Schedule**: Daily at 3:00 AM
**Min Relevance**: 0.7
**Max Articles**: 50 per run

Does this look good, or would you like to refine anything?
```

### 8. Creation Phase

**Goal**: Execute the creation.

**Action**: Call `create_research_question` with finalized parameters.

**Parameters to Pass**:
```python
{
    'name': 'AI Memory Systems Research',
    'keywords': ['memory', 'retrieval', 'agent memory', 'stateful agents'],
    'topics': ['cs.AI', 'cs.LG'],
    'authors': [],  # Optional, if user mentioned specific researchers
    'selected_sources': ['arxiv', 'semantic_scholar', 'openalex'],
    'schedule_frequency': 'daily',
    'schedule_time': '03:00',
    'min_relevance_score': 0.7,
    'max_articles_per_run': 50,
    'auto_download_pdfs': True
}
```

**Success Response**:
```
Agent: ✓ Research question created successfully!

Your automated discovery is now active. The system will:
- Search arxiv, semantic_scholar, and openalex daily at 3:00 AM
- Look for papers matching your keywords and topics
- Download PDFs for articles scoring above 0.7 relevance
- Process up to 50 articles per run

You can manually trigger discovery anytime with the run_discovery_for_question tool.
Would you like to run it now to see initial results?
```

## Tips for Effective Facilitation

### Be Conversational, Not Robotic
- ❌ "Provide keywords for parameter 'keywords' array."
- ✅ "What are the main terms you'd use to describe your research area?"

### Explain Technical Terms
- When mentioning "relevance score", explain: "This filters out papers that don't closely match your criteria."
- When mentioning "ArXiv categories", explain: "These are like academic subject tags that help narrow the search."

### Suggest, Don't Prescribe
- ❌ "You must use cs.AI and cs.LG categories."
- ✅ "For AI research, cs.AI and cs.LG categories usually work well. Would you like to include both?"

### Handle Uncertainty Gracefully
```
User: I'm not sure which sources to use.

Agent: No worries! For computer science and AI research, I'd typically recommend 
starting with arxiv and semantic_scholar - they're the most comprehensive for 
this field. We can always adjust later if you're not getting what you need.

Or if you'd like, we can use "*" to search all available sources. What sounds better?
```

### Progressive Disclosure
- Don't overwhelm with all options at once
- Start with essential questions (what, which sources)
- Offer advanced options only if user seems interested
- Keep it focused on their needs

## Common Scenarios

### Scenario 1: User Knows Exactly What They Want
```
User: I want daily ArXiv alerts for "transformer architectures" in cs.AI and cs.LG.

Agent: Perfect! Let me set that up for you. 
[calls list_available_sources to show options]
I'll create a research question that searches ArXiv daily for transformer 
architectures in cs.AI and cs.LG. Should I include any related terms like 
"attention mechanism" or "self-attention" to catch more relevant papers?
```

### Scenario 2: User Needs Guidance
```
User: I want to learn about quantum computing.

Agent: Great topic! Let's set up automated discovery. To help narrow it down, 
what aspect of quantum computing interests you most? For example:
- Quantum algorithms?
- Quantum error correction?
- Quantum hardware/qubits?
- Applications to cryptography or optimization?
- General quantum computing research?
```

### Scenario 3: User Wants to Track Multiple Topics
```
User: I'm interested in both quantum computing and AI safety.

Agent: Those are both fascinating areas! I'd recommend creating separate research 
questions for each, since they'd use different keywords and potentially different 
sources. This gives you better-targeted results.

Would you like to start with quantum computing or AI safety?
```

## Troubleshooting

### User Provides Too Few Keywords
**Problem**: User says "just use AI"

**Solution**: 
```
Agent: "AI" is pretty broad - we'd get thousands of papers! Let's be more specific. 
What area of AI? For example:
- Machine learning?
- Natural language processing?
- Computer vision?
- Robotics?
```

### User Wants Everything
**Problem**: User says "I want papers about AI, ML, NLP, computer vision..."

**Solution**:
```
Agent: That covers a lot of ground! You might get overwhelmed with results. 
I'd suggest either:
1. Create focused research questions for each area (recommended)
2. Or pick your top 2-3 priorities to start with

Which approach sounds better?
```

### User Unsure About Scheduling
**Problem**: User doesn't know how often to check

**Solution**:
```
Agent: Here's a rule of thumb:
- Fast-moving fields (AI/ML, COVID research): Daily
- Steady fields (most science): Weekly  
- Niche or historical topics: Monthly

For your topic, I'd suggest [recommendation]. You can always adjust this later!
```

## After Creation

Once the research question is created, explain next steps:

1. **Automatic Discovery**: "The scheduler will automatically run at your specified time."
2. **Manual Trigger**: "You can manually run discovery anytime with run_discovery_for_question."
3. **View Results**: "Use list_research_questions to see all your active research questions."
4. **Modify Later**: "You can update or delete this research question anytime."

## Summary

Remember: Your role is to be a helpful guide, not just a data collector. Help users:
- Articulate their research interests clearly
- Choose effective search parameters
- Understand the system's capabilities
- Feel confident in their setup

Be friendly, patient, and focused on their research goals!
