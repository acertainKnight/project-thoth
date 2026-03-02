---
name: research-planning
description: Create, manage, and iterate on research plan documents in the Obsidian
  vault. Use when the user asks for a research plan, literature review roadmap, or
  when you need to formalize your own working research strategy.
tools:
- create_plan
- list_plans
- get_plan
- update_plan
- delete_plan
tags:
- planning
- research
- workflow
---

# Research Planning

Create and manage structured markdown plan documents directly in the Obsidian vault. Plans are automatically indexed into the RAG system so you can reference and search them alongside your research papers.

## Two Types of Plans

### Internal Plans (`plan_type="internal"`)
Stored in `thoth/_thoth/plans/` — your own working research strategy. Use these to:
- Map out a multi-step research approach before starting
- Track which questions remain open
- Note decisions and why you made them
- Draft a plan the user can review and edit

### User Plans (`plan_type="user"`)
Stored in `thoth/plans/` — formalized deliverables for the user. Use these when:
- The user asks "can you make me a research plan for X"
- You want to present a structured roadmap the user can follow independently
- You're summarizing a completed research arc into a reusable plan

## Recommended Plan Structure

Always include these sections in the `content` argument:

```markdown
## Objective
One paragraph: what research question are we answering and why.

## Steps
1. Step one (specific, actionable)
2. Step two
3. ...

## Key Papers / Sources to Check
- Any known papers or sources worth starting from

## Open Questions
- Unknowns to resolve during the research

## Notes
Running notes as the plan evolves.
```

## Workflow

### Starting a new research session
1. Call `create_plan` with `plan_type="internal"` to write out your approach
2. Proceed with discovery and analysis
3. Call `update_plan` as your understanding evolves (update `status`, add notes)
4. When ready to present to the user, call `create_plan` with `plan_type="user"` with the polished version

### When the user explicitly asks for a plan
1. Clarify scope if needed
2. Call `create_plan` with `plan_type="user"` and a thorough `content`
3. Tell the user the plan is saved in their vault at `thoth/plans/{plan_id}.md`

### Checking existing plans
```
list_plans                          # all plans
list_plans(plan_type="internal")    # only your working plans
list_plans(status="active")         # only active plans
get_plan(plan_id="my-plan-slug")    # read full content
```

### Updating a plan
```
update_plan(
    plan_id="my-plan-slug",
    status="complete",              # or "draft", "active", "archived"
    content="## Objective\n..."     # replaces full body
)
```

## Plan IDs

Plan IDs are auto-generated slugs from the title. For example:
- `"Literature Review: Transformers 2026"` → `literature-review-transformers-2026`
- `"My Research Strategy"` → `my-research-strategy`

Use `list_plans` if you need to look up an ID.

## RAG Integration

Plans are indexed into the same vector store as your research papers. This means:
- `answer_research_question` will surface relevant plan content in its context
- Searching for a topic will return matching plans alongside papers
- You can refer to plans when answering questions about research strategy

## Status Values

| Status | Meaning |
|--------|---------|
| `draft` | Not ready yet, still being drafted |
| `active` | In progress or currently relevant |
| `complete` | Research arc finished |
| `archived` | No longer active but kept for reference |

## Example

```
User: "Can you create a research plan for understanding how attention mechanisms work in LLMs?"

→ create_plan(
    title="Research Plan: Attention Mechanisms in LLMs",
    plan_type="user",
    content="""
## Objective
Understand how attention mechanisms work in large language models,
from the original transformer paper through modern variants.

## Steps
1. Read Vaswani et al. 2017 (Attention Is All You Need)
2. Search for survey papers on attention variants
3. Compare: MHA, MQA, GQA, FlashAttention architectures
4. Identify efficiency vs. quality trade-offs
5. Summarise findings

## Key Papers / Sources to Check
- Vaswani et al. 2017
- Flash Attention (Dao et al.)
- GQA paper (Ainslie et al.)

## Open Questions
- How does RoPE interact with attention?
- What are the memory bottlenecks?

## Notes
Starting fresh — no prior papers in collection on this topic.
""",
    tags=["attention", "transformers", "llm-architecture"]
)
```
