---
name: research-memory-cleanup
description: Defragment and clean research agent memory - consolidate paper info, organize research domains, remove redundancy from research tracking.
---

# Research Memory Cleanup

Clean up research agent memory by consolidating duplicate paper info, organizing research domains, and removing redundancy.

## Quick Start: The Cleanup Cycle

**Most common use**: Memory has grown messy with duplicate paper entries, scattered research notes, or conflicting discovery configs.

### Standard Opening

```
User: "My research memory is getting messy."

Agent: "Let's clean it up! I'll:

1. Backup your current memory (safety first)
2. Review what needs consolidating
3. Clean up duplicate/scattered info
4. Restore the cleaned version

This takes ~5 minutes. Ready to start?"
```

**Then execute the 3-step workflow.**

---

## Diagnosis: What Needs Cleaning?

Ask 3 questions to understand the mess:

**Question 1: What's messy?**
```
Agent: "What feels messy in your research memory?
A) Duplicate paper entries
B) Scattered research domain notes
C) Conflicting discovery configs
D) Old/outdated research areas
E) General disorganization"
```

**Question 2: How bad is it?**
```
Agent: "Scale of messiness:
A) Mildly cluttered (50-100 papers tracked)
B) Pretty messy (100-300 papers)
C) Very messy (300+ papers or 50K+ chars)
D) Complete chaos (multiple research agents merged)"
```

**Question 3: What to preserve?**
```
Agent: "What must NOT be lost?
- Active research questions?
- Discovery configurations?
- Paper reading lists?
- Citation networks?
- Analysis notes?

Tell me what's sacred, I'll protect it."
```

---

## Conversation Patterns

### Pattern 1: Standard Memory Cleanup

**Trigger**: General memory mess, not critical

```
Agent: "Starting standard cleanup. This will:

Step 1: Backup everything
Step 2: Consolidate duplicate paper entries
Step 3: Organize research domains
Step 4: Clean discovery configs
Step 5: Restore cleaned version

Backing up now..."

[Run backup script]

Agent: "Backup saved to .letta/backups/[agent-id]/[timestamp]/

Now spawning memory subagent to clean up the files..."

[Spawn memory subagent with cleanup task]

Agent: "Memory subagent working... (this takes 2-3 min)

[Wait for subagent to finish]

Agent: "Cleanup complete! Changes:
- Merged 15 duplicate paper entries → 5 unique papers
- Organized 3 research domains (ML, NLP, RL)
- Removed 2 outdated discovery configs
- Total reduction: 12,450 chars → 8,200 chars (34% smaller)

Restoring cleaned memory now..."

[Run restore script]

Agent: "Done! Your research memory is now organized and deduplicated."
```

### Pattern 2: Paper Entry Consolidation

**Trigger**: Many duplicate paper entries

```
Agent: "I see lots of duplicate paper entries. Cleaning up papers...

[Memory subagent task: consolidate papers]

Consolidation strategy:
1. Group by paper title/DOI
2. Merge all mentions into single entry
3. Keep: title, authors, citations, your notes
4. Remove: duplicate tracking, scattered mentions

Subagent will merge papers and DELETE source duplicates."
```

**Memory subagent prompt:**
```
Edit memory files in .letta/backups/working/ to consolidate paper entries.

Find duplicate papers (same title/DOI):
1. Create single comprehensive entry per paper
2. Merge all notes, citations, analysis
3. DELETE the duplicate source files (use rm command)

Example:
- paper-transformers-1.md
- paper-transformers-duplicate.md
→ Merge into single paper-transformers.md
→ rm paper-transformers-duplicate.md

After consolidation, report what was merged.
```

### Pattern 3: Research Domain Organization

**Trigger**: Research areas scattered, no clear structure

```
Agent: "Your research domains are scattered. Let me organize them...

[Memory subagent task: organize domains]

Organization strategy:
1. Identify main research areas (ML, NLP, CV, etc.)
2. Group papers/notes by domain
3. Create domain-specific memory blocks
4. Link related domains

Subagent will create organized structure."
```

**Memory subagent prompt:**
```
Organize research memory by domain.

Create domain blocks:
- research-domain-ml.md (ML papers and notes)
- research-domain-nlp.md (NLP papers and notes)
- research-domain-rl.md (RL papers and notes)

Move relevant content into each domain block.
DELETE scattered source files after merging.

Use clear structure:
## Papers
- Paper 1: [title] - [notes]
- Paper 2: [title] - [notes]

## Key Concepts
- Concept 1: [description]

## Active Questions
- Question 1: [question]
```

### Pattern 4: Discovery Config Cleanup

**Trigger**: Old/conflicting discovery configurations

```
Agent: "I see multiple discovery configs, some outdated. Cleaning...

[Memory subagent task: clean discovery configs]

Cleanup strategy:
1. Keep: Current active discovery configs
2. Archive: Old configs (if might need later)
3. Remove: Clearly outdated/conflicting configs

Subagent will preserve active, remove dead configs."
```

---

## Quick Reference Cards

### Card 1: The 3-Step Workflow

**Every cleanup follows this:**

```bash
# Step 1: Backup
npx tsx [SKILL_DIR]/scripts/backup-memory.ts $LETTA_AGENT_ID .letta/backups/working

# Step 2: Clean (spawn memory subagent with task)
Task({
  subagent_type: "memory",
  description: "Clean research memory",
  prompt: "[specific cleanup task]"
})

# Step 3: Restore
npx tsx [SKILL_DIR]/scripts/restore-memory.ts $LETTA_AGENT_ID .letta/backups/working
```

**Never skip backup!**

### Card 2: What to Consolidate

**Common research memory issues:**

| Issue | Consolidation Strategy |
|-------|------------------------|
| Duplicate papers | Merge by DOI/title → single entry |
| Scattered domains | Group by topic → domain blocks |
| Old discovery configs | Keep active, archive old, delete dead |
| Redundant notes | Merge similar notes → single coherent note |
| Conflicting info | Resolve conflicts → choose correct version |
| Walls of text | Add structure → headers + bullets |

### Card 3: Memory Subagent Prompts

**Template for cleanup tasks:**

```
Edit memory files in .letta/backups/working/ to [specific goal].

Focus on:
- [Primary consolidation task]
- [Secondary organization task]
- [Tertiary cleanup task]

IMPORTANT: After merging content, DELETE source files (rm command).
You have full bash access in .letta/backups/working/.

Delete files when:
1. Content merged into another block
2. File is duplicate/junk data
3. File is outdated and irrelevant

Report what was merged and what was deleted.
```

**Key principles:**
- Specific goal (consolidate papers, organize domains, etc.)
- Give full bash access permission
- Explicitly say to DELETE merged files
- Ask for report of changes

### Card 4: Rollback Safety

**If cleanup goes wrong:**

```bash
# Find the backup
ls -la .letta/backups/[agent-id]/

# Restore from timestamp
npx tsx [SKILL_DIR]/scripts/restore-memory.ts $LETTA_AGENT_ID .letta/backups/[agent-id]/[timestamp]
```

**Pro tip**: Each backup is timestamped, so you can roll back to any previous state.

---

## Refinement Patterns

### Refinement 1: Cleanup Too Aggressive

**Symptom**: Important research notes were removed

**Fix**: Roll back and be more specific

```
Agent: "The cleanup removed too much. Let me roll back:

[Restore from backup]

Agent: "Rolled back to pre-cleanup state.

Let's try again with more specific instructions:
- What exactly should be consolidated?
- What must be preserved no matter what?

Tell me the specifics and I'll give clearer instructions to the memory subagent."
```

### Refinement 2: Papers Still Duplicated

**Symptom**: Cleanup didn't merge all duplicates

**Fix**: More specific merge instructions

```
Agent: "Some papers are still duplicated. Let me:

1. Identify the duplicates (same DOI/title)
2. Show you which ones
3. Give memory subagent explicit merge list

This will be more precise."
```

**Enhanced prompt:**
```
Merge these specific paper duplicates:
- paper-bert.md + paper-bert-2.md → paper-bert.md
- paper-gpt3.md + gpt3-analysis.md → paper-gpt3.md

For each merge:
1. Combine all unique info
2. DELETE the duplicate file
3. Report: "Merged [file1] + [file2] → [result]"
```

### Refinement 3: Lost Structure

**Symptom**: Cleanup created walls of text, no organization

**Fix**: Add structure requirements

```
Agent: "The cleanup lost structure. Let me fix that:

[Re-run with structure requirements]

Memory subagent will now:
- Use markdown headers (##, ###)
- Organize with bullet points
- Keep related info together
- Add scannable formatting

Running again..."
```

### Refinement 4: Need Iterative Cleanup

**Symptom**: One cleanup pass isn't enough

**Fix**: Multiple passes with different focuses

```
Agent: "This needs multiple cleanup passes. Let's do:

Pass 1: Consolidate papers (done)
Pass 2: Organize domains (next)
Pass 3: Clean configs (after)

Each pass builds on the previous. Ready for Pass 2?"
```

---

## Troubleshooting

| Problem | Quick Fix |
|---------|-----------|
| Backup failed | Check disk space, .letta/backups/ permissions |
| Subagent deleted too much | Rollback, be more specific about what to preserve |
| Restore failed | Check working directory has cleaned files |
| Memory still messy | Run multiple passes, each with specific focus |
| Lost important notes | Rollback immediately, check backup timestamp |
| Cleanup took forever | Reduce scope, clean one section at a time |
| Files not deleted | Add "use rm command" explicitly to prompt |
| No consolidation | Memory subagent needs clearer merge instructions |
| Structure lost | Add formatting requirements to prompt |

---

## Advanced: Research-Specific Cleanup Patterns

### Pattern A: Paper Reading List Cleanup

**Use case**: Reading list has 50+ papers, many duplicates

```
Agent: "Cleaning up paper reading list...

Strategy:
1. Group by topic/domain
2. Mark status (read, reading, to-read)
3. Remove duplicates
4. Sort by priority

Memory subagent will create organized reading-list.md."
```

### Pattern B: Citation Network Cleanup

**Use case**: Citation graphs scattered across files

```
Agent: "Consolidating citation networks...

Strategy:
1. Merge all citation data
2. Remove duplicate edges
3. Update paper metadata
4. Create single citation-graph.md

Memory subagent will consolidate graphs."
```

### Pattern C: Discovery History Cleanup

**Use case**: Discovery results from 6 months, many outdated

```
Agent: "Cleaning discovery history...

Strategy:
1. Keep: Last 30 days of discoveries
2. Archive: 30-90 days (compress to summaries)
3. Delete: 90+ days (unless marked important)

Memory subagent will prune old discoveries."
```

---

## Summary: The Agent's Mental Model

**Core workflow:**
1. **Backup** first (ALWAYS) - safety net
2. **Review** what needs consolidating
3. **Clean** with memory subagent (specific instructions)
4. **Restore** cleaned version
5. **Validate** changes are good
6. **Rollback** if needed (backup saved)

**Key principles:**
- Never skip backup (rollback safety)
- Be specific with memory subagent instructions
- Explicitly tell subagent to DELETE merged files
- Run multiple passes for complex cleanups
- Validate before finalizing
- Research data is sacred - preserve when in doubt

**What to consolidate:**
- Duplicate paper entries (same DOI/title)
- Scattered research domain notes
- Redundant discovery configs
- Old/outdated research areas
- Walls of text (add structure)

**What to preserve:**
- Active research questions (sacred)
- Current discovery configs (active)
- Paper reading lists (user's workflow)
- Citation networks (research connections)
- Analysis notes (insights)

**Success**: Research memory is organized, deduplicated, and structured - agent can quickly access papers, domains, and configs without wading through duplicates.
