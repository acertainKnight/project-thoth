# Design Philosophy

The decisions behind Thoth's architecture, and the trade-offs involved.

---

## Core Principles

### User control over convenience

When I had to choose between making something easier and making something more controllable, I picked control. All LLM prompts are Jinja2 templates you can read and edit. Extraction schemas are JSON files you define. Sources are plugins you can add. Skills are files you can create. Configuration is a single `settings.json`, not hidden state spread across a dozen places.

The trade-off is obvious: there's more to learn. But research workflows are deeply personal, and I'd rather give someone a tool they can bend to their needs than a polished box they can't open.

### The agent as the configuration interface

All that customizability creates a problem: there are a lot of knobs to turn. Prompt templates, extraction schemas, research question configs, LLM routing, discovery sources, analysis settings—it adds up. I didn't want users to need to understand the entire configuration surface before they could get value from the system.

The solution was making the agent itself the primary interface for configuration. Every setting, template, and schema that a user could edit by hand is also exposed to the Letta agent through MCP tools. The agent can read settings, update them, modify prompt templates, adjust research queries, change extraction schemas—all of it.

So instead of hunting through a settings file to figure out why your article notes don't include methodology sections, you just tell the agent: "I want methodology details in my paper notes going forward." The agent loads the settings-management skill, updates the analysis schema, and the next paper processed reflects the change.

Or if a research question is pulling in too many irrelevant results—"my RL search keeps returning robotics papers I don't care about"—the agent can tighten the query parameters, adjust the source filters, or refine the search terms. You describe the problem, the agent handles the configuration.

This was a deliberate architectural choice, not an afterthought. The MCP tools for settings management, schema editing, and query configuration were built specifically so that the agent could serve as a natural language layer over what would otherwise be a complex manual process. For initial setup, there's also a TUI wizard (`thoth setup`) that walks through the basics, so nobody has to start from a blank config file.

The key insight: the system can be as complex as it needs to be under the hood, as long as the user's primary interaction with that complexity is a conversation.

### Local-first

All processing happens on your machine. The only network calls are to LLM APIs (OpenRouter, OpenAI, Mistral) and academic APIs (Semantic Scholar, Crossref, etc.). No telemetry, no cloud processing. Your data lives in your Obsidian vault, and you can back it up however you want.

This matters because research often involves unpublished work. Privacy isn't a feature—it's table stakes.

### Standards over custom protocols

Thoth uses MCP for tools, PostgreSQL+pgvector for storage, Jinja2 for templates, JSON Schema for validation, and Docker for deployment. None of these are novel. That's the point.

Custom protocols feel simpler at first, but standards have longevity, community support, and tooling. MCP means any MCP-compatible client can use Thoth's tools. PostgreSQL means your data is in a format the whole industry knows how to work with.

### Small pieces, loosely joined

Letta runs as its own service. Skills load tools on demand rather than all at once. Sources are plugins, not hard-coded. Services communicate through a ServiceManager that handles dependency injection.

The cost is more moving parts. The benefit is that restarting Thoth never wipes your agent memory, you can swap components without rewriting the system, and failures stay contained.

### Start simple, go deep

The install is a single `curl` command. Agents start with 4 tools and expand when you load skills. Settings have sensible defaults. But if you want to customize every prompt template, define your own extraction schema, or write a custom source plugin, you can.

---

## Key Decisions

### Why Letta for agent memory?

I evaluated LangChain's memory (too basic, no real persistence), building a custom memory system (not worth reinventing), and Letta (formerly MemGPT).

Letta won because agents can update their own memory through tool calls. It's not just retrieval—the agent decides what to remember and what to forget. The PostgreSQL+pgvector backend means memory survives restarts, and there's no context window ceiling. It comes from real research (the MemGPT paper from UC Berkeley), not just framework marketing.

The downside is infrastructure: you need PostgreSQL and a Letta server running. But `make dev` handles that, and the memory quality is worth it.

### Why MCP for tools?

Custom REST endpoints would have been simpler to build. But MCP is becoming the standard protocol for LLM-tool integration. Building on it means Thoth's tools work with any MCP client (Claude Desktop, Letta, etc.), and users can bring in MCP tools from the broader ecosystem.

The trade-off is JSON-RPC overhead and a more complex server setup. For a research tool that lives on your machine, the performance hit doesn't matter, and the ecosystem compatibility does.

### Why skill-based tool loading?

Loading all 60 tools into an agent's context at once tanks LLM performance. The model gets confused with too many options, and you burn tokens on tool descriptions for capabilities the agent doesn't need right now.

Skills group related tools together. When you ask the agent to find papers, it loads the paper-discovery skill and gets the 5-6 tools it needs. When you're done, it unloads them. Token usage drops significantly, and the LLM makes better tool choices with a smaller set.

### Why plugins for sources?

Hard-coding academic sources (ArXiv, Semantic Scholar, etc.) would mean every new source requires a code change. The plugin architecture lets users add sources without touching the core.

The most interesting part is the auto-scraper: give it any URL, and it uses Playwright + an LLM to figure out the page structure and propose CSS selectors for extracting articles. You confirm or refine with natural language, and it saves a working scraper. No code needed.

### Why template-driven extraction?

Every prompt Thoth sends to an LLM is a Jinja2 template sitting in a directory you can browse. This means you can see exactly what's being asked, tweak the wording, or write provider-specific versions (the same analysis prompt can be optimized differently for GPT-4 vs. Gemini).

The analysis schema—what metadata gets extracted from papers—is a JSON file you edit. Want to extract "methodology type" from every paper? Add it to the schema. The LLM will follow your structure.

---

## Trade-offs I'm Aware Of

**Complexity vs. simplicity**: Thoth has more moving parts than a simple script that calls an API. The service-oriented architecture, plugin system, and skill-based loading all add complexity. I think it's justified for the extensibility, but there's a real learning curve.

**Local infrastructure**: Running Docker containers, PostgreSQL, and a Letta server is more setup than a SaaS tool. The install script and `make dev` abstract most of it, but if something breaks, you're debugging containers.

**Standards vs. speed**: Using MCP instead of a simple REST API, PostgreSQL instead of SQLite—these choices optimize for longevity and ecosystem compatibility over development speed. For a tool I plan to use for years, that felt right.

---

*Last updated: February 2026*
