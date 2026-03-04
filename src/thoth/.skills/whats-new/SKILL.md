---
name: whats-new
description: Walk the user through new Thoth features since their last onboarding
  or update. Use when the user asks "what's new", "what changed", or "what can you
  do now". Also use after check_whats_new returns updates to walk through them.
tools:
- check_whats_new
- search_documentation
- load_documentation
---

# What's New Walkthrough

Walk the user through features that have shipped since they last used the system. The goal is a brief, conversational update — not a changelog dump.

## Step 1: Get the Changes

Call `check_whats_new` with the `last_seen_version` from the `human` memory block. If the field isn't set, pass `"0.0.0"`.

The tool returns the current server version and a list of changes grouped by version.

## Step 2: Decide How Much to Cover

- If there's one version worth of changes: just walk through them directly.
- If there are multiple versions: summarize the most impactful ones and offer to go deeper on any.
- If there's nothing new: tell them the system is up to date and ask if they want a refresher on any capabilities.

## Step 3: Present the Updates

Narrate the changes conversationally. Don't read the changelog line by line — group related things and explain what they mean for the user's workflow.

For each significant update, offer a brief demo or next step:

> "One thing that's new is [feature]. This means you can now [what it unlocks]. Want me to show you an example?"

If they're curious about something, use `search_documentation` to find the right doc and `load_documentation` to read it in full.

## Step 4: Update Their Version Record

Once they've been through the walkthrough (or if they say "skip it"), update `last_seen_version` in the `human` memory block to the current server version. Use `memory_replace` on the `human` block.

Don't wait for them to explicitly confirm — once you've presented the summary and they've responded (even just "thanks"), that counts.

## Tone

Keep it brief and practical. Users don't want a product announcement — they want to know if anything changes how they do their work. Lead with "here's what's relevant to you" rather than "here's everything that changed."
