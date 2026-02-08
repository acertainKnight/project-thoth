# Thoth Design Philosophy

Core architectural principles and design decisions that shape Thoth.

## Table of Contents

- [Core Principles](#core-principles)
- [Key Design Decisions](#key-design-decisions)
- [Architecture Patterns](#architecture-patterns)
- [Trade-offs](#trade-offs)

---

## Core Principles

### 1. User Control Over Convenience

**Principle**: When choosing between convenience and control, choose control.

**What this means**:
- All prompts are editable (Jinja2 templates)
- Extraction schemas are user-defined (JSON files)
- Sources are plugins (add any source)
- Skills are user-creatable (not locked in)
- Configuration is transparent (settings.json, not opaque)

**Why**:
- Research workflows are personal—no one-size-fits-all
- Users should be able to adapt the system to their needs
- Transparency builds trust

**Example**:
```
Instead of: Fixed extraction fields
We chose: User-editable analysis_schema.json

Trade-off: Users must understand schemas
Benefit: Users extract exactly what they need
```

### 2. Local-First, Privacy-Focused

**Principle**: Your data stays on your machine.

**What this means**:
- All processing happens locally
- Only LLM API calls leave your system
- No telemetry or tracking
- Full offline capability (after setup)
- Data in your vault, under your control

**Why**:
- Research often involves unpublished work
- Privacy is non-negotiable for many users
- Local processing is faster (no network latency)

**Example**:
```
Instead of: Cloud processing pipeline
We chose: Local Docker containers

Trade-off: Users need to run infrastructure
Benefit: Complete data privacy and control
```

### 3. Extensibility Through Standards

**Principle**: Use industry standards to enable ecosystem integration.

**What this means**:
- MCP protocol for tools (not custom REST API)
- PostgreSQL+pgvector for storage (not proprietary DB)
- Jinja2 for templates (not custom DSL)
- JSON Schema for validation (not custom formats)
- Docker for deployment (not custom packaging)

**Why**:
- Standards have longevity
- Standards have tooling and community support
- Standards enable interoperability

**Example**:
```
Instead of: Custom tool protocol
We chose: Model Context Protocol (MCP)

Trade-off: More complex than simple REST
Benefit: Works with any MCP-compatible system (Letta, Claude Desktop, etc.)
```

### 4. Composition Over Monoliths

**Principle**: Small, composable pieces beat large, integrated systems.

**What this means**:
- Letta runs independently (shared infrastructure)
- Skills load tools dynamically (not all-at-once)
- Sources are plugins (not built into core)
- Services are loosely coupled (ServiceManager coordinates)

**Why**:
- Easier to understand and debug
- Easier to extend and modify
- Better failure isolation

**Example**:
```
Instead of: All services in one container
We chose: Letta standalone + Thoth services separate

Trade-off: More infrastructure to manage
Benefit: Restarting Thoth never affects agents
```

### 5. Progressive Disclosure

**Principle**: Start simple, reveal complexity when needed.

**What this means**:
- Quick install: curl | bash
- Advanced install: Manual with full control
- Agents start minimal (4 tools)
- Skills load more tools on-demand
- Settings have defaults, advanced options available

**Why**:
- Lower barrier to entry
- Users aren't overwhelmed
- Power users can go deep

**Example**:
```
Instead of: Expose all 64 tools at once
We chose: Start with 4, load skills as needed

Trade-off: Extra step to load skills
Benefit: Better LLM performance, lower token usage
```

---

## Key Design Decisions

### Why Letta for Agent Memory?

**Decision**: Use Letta as agent memory system

**Alternatives Considered**:
1. **LangChain Memory**: Too simple, no persistence
2. **Custom Memory System**: Reinventing the wheel
3. **Letta (MemGPT)**: ✅ Chosen

**Why Letta**:
- **Research-backed**: Based on MemGPT paper from UC Berkeley
- **Self-editing memory**: Agents update their own context
- **Persistent**: PostgreSQL+pgvector backend
- **Cross-session continuity**: No context window limits
- **Tool integration**: Native MCP support

**Trade-offs**:
- ❌ Extra infrastructure (PostgreSQL, Letta server)
- ✅ Stateful agents that remember
- ✅ Production-ready memory system

### Why MCP for Tools?

**Decision**: Implement Model Context Protocol for tools

**Alternatives Considered**:
1. **Custom REST API**: Simple but proprietary
2. **LangChain Tools**: Python-only, no standard protocol
3. **MCP**: ✅ Chosen

**Why MCP**:
- **Industry standard**: Adopted by Anthropic, OpenAI ecosystem
- **Interoperability**: Works with any MCP client
- **Tool composability**: Dynamic attachment/detachment
- **Schema-first**: JSON Schema for validation

**Trade-offs**:
- ❌ More complex than simple REST
- ❌ JSON-RPC overhead
- ✅ Future-proof (works with ecosystem tools)
- ✅ Dynamic tool loading

### Why Skills System?

**Decision**: Skills load tools dynamically instead of loading all tools at once

**Alternatives Considered**:
1. **Load all tools**: Simple but inefficient
2. **Manual tool selection**: Too complex for users
3. **Skill-based loading**: ✅ Chosen

**Why Skills**:
- **Token efficiency**: 60-80% fewer tools in context
- **Better LLM performance**: Clearer tool choices
- **Logical grouping**: Skills = capabilities
- **User-extensible**: Create custom skills

**Trade-offs**:
- ❌ Extra step (load skill before using)
- ✅ Much better LLM performance
- ✅ Lower costs (fewer tokens)

### Why Plugin Architecture for Sources?

**Decision**: Sources are plugins, not hard-coded

**Alternatives Considered**:
1. **Hard-coded sources**: Simple but inflexible
2. **Plugin system**: ✅ Chosen

**Why Plugins**:
- **Open-ended**: Add any source without modifying core
- **LLM auto-scraper**: Create plugins from URLs
- **Source-specific optimizations**: Each plugin can optimize for its source
- **Community contributions**: Easy to share new sources

**Trade-offs**:
- ❌ More complex architecture
- ✅ Unlimited sources
- ✅ User-extensible

### Why Template-Driven Extraction?

**Decision**: Use Jinja2 templates for prompts and JSON schemas for extraction

**Alternatives Considered**:
1. **Hard-coded prompts**: Simple but inflexible
2. **DSL for schemas**: Custom but learning curve
3. **Jinja2 + JSON Schema**: ✅ Chosen

**Why Templates**:
- **Full transparency**: Users see exact prompts sent to LLMs
- **Provider-specific optimization**: Different templates for OpenAI/Google/Anthropic
- **No code changes**: Edit templates to change behavior
- **Industry standards**: Jinja2 and JSON Schema are widely used

**Trade-offs**:
- ❌ Users must learn Jinja2 (for advanced customization)
- ✅ Complete control over LLM prompts
- ✅ No code changes needed

### Why Hot-Reload Configuration?

**Decision**: Settings changes apply in ~2 seconds without restart (dev mode)

**Alternatives Considered**:
1. **Restart required**: Traditional approach
2. **Hot-reload**: ✅ Chosen

**Why Hot-Reload**:
- **Faster iteration**: Test changes immediately
- **Better UX**: No service interruptions
- **Development speed**: Rapid experimentation

**Trade-offs**:
- ❌ More complex implementation (file watching)
- ✅ Much better developer experience
- ✅ Faster configuration tuning

### Why Independent Letta Service?

**Decision**: Letta runs as standalone service, not part of Thoth stack

**Alternatives Considered**:
1. **Embedded Letta**: Letta starts with Thoth
2. **Standalone Letta**: ✅ Chosen

**Why Standalone**:
- **Data persistence**: Restarting Thoth never affects agents
- **Multi-project sharing**: One Letta, multiple projects
- **Independent updates**: Update Thoth without touching Letta
- **Clear separation**: Memory system is infrastructure

**Trade-offs**:
- ❌ Must start Letta separately (automated by make dev)
- ✅ Agents always persist
- ✅ Can serve multiple projects

---

## Architecture Patterns

### Service-Oriented Architecture

**Pattern**: Loosely coupled services coordinated by ServiceManager

**Components**:
- **ServiceManager**: Dependency injection coordinator
- **Independent Services**: LLMService, DiscoveryService, RAGService, etc.
- **Defined Interfaces**: Services depend on interfaces, not implementations

**Benefits**:
- Easy to test (mock interfaces)
- Easy to swap implementations
- Clear responsibilities

### Plugin Architecture

**Pattern**: Core + Plugins for extensibility

**Where Used**:
- **Discovery Sources**: 7 plugins + LLM auto-scraper
- **Skills**: 10 bundled + unlimited user skills
- **MCP Tools**: 64 built-in + ecosystem tools

**Benefits**:
- Core stays simple
- Users extend without forking
- Community can contribute plugins

### Factory Pattern

**Pattern**: `initialize_thoth()` factory creates entire system

**Why**:
- Single entry point for initialization
- Dependency ordering handled automatically
- Easy to test (mock factory output)

### Repository Pattern

**Pattern**: Services use repositories for data access

**Examples**:
- `ArticleRepository`: Database access for articles
- `CitationRepository`: Citation storage
- `QueryRepository`: Research questions

**Benefits**:
- Database abstraction
- Easy to swap storage backends
- Clear data access patterns

### Strategy Pattern

**Pattern**: Configurable algorithms

**Examples**:
- **LLM routing**: Different providers for different tasks
- **Citation resolution**: 6-stage chain with pluggable resolvers
- **Discovery**: Different strategies per source

**Benefits**:
- Runtime configuration
- Easy to add new strategies
- Clear algorithm interfaces

---

## Trade-offs

### Complexity vs Control

**Choice**: Accept higher complexity for user control

**What we gave up**:
- Simple "just works" experience (like ChatGPT)
- One-click deployment
- Hidden implementation details

**What we gained**:
- Users can customize everything
- Transparent operation
- Extensibility

**When this matters**:
- Advanced users who need control
- Research workflows that don't fit defaults
- Organizations with specific requirements

### Local vs Cloud

**Choice**: Local-first architecture

**What we gave up**:
- Easy scaling (can't just spin up cloud instances)
- Managed infrastructure
- Built-in backups

**What we gained**:
- Complete privacy
- No cloud costs (except LLM APIs)
- Offline capability

**When this matters**:
- Confidential research
- Cost-sensitive users
- Unreliable internet

### Standards vs Optimization

**Choice**: Use standards even when custom might be faster

**What we gave up**:
- Custom-optimized protocols
- Simpler implementations
- Less overhead

**What we gained**:
- Ecosystem compatibility
- Longevity (standards outlive custom systems)
- Tooling and community support

**When this matters**:
- Long-term maintainability
- Integration with other tools
- Future-proofing

### Modular vs Monolithic

**Choice**: Many small services vs one big service

**What we gave up**:
- Simple deployment (one container)
- Easy debugging (single log file)
- Lower resource usage

**What we gained**:
- Independent scaling
- Failure isolation
- Clear responsibilities
- Easier to understand

**When this matters**:
- Production deployments
- Multi-user setups
- Complex workflows

---

## Design Lessons

### What Worked Well

1. **MCP adoption**: Future-proofed tool system, works with ecosystem
2. **Skill-based loading**: Massive improvement in LLM performance
3. **Independent Letta**: Agents always persist, no data loss
4. **Template system**: Users love being able to customize prompts
5. **Plugin architecture**: Easy to add sources without core changes

### What We'd Do Differently

1. **Start with MCP from day one**: Retrofitting was painful
2. **Skill system earlier**: Should have been in v1
3. **Better documentation from start**: Docs lagged behind features
4. **Type hints everywhere**: Added incrementally, should be default

### Lessons for Future Projects

1. **Use standards early**: Custom protocols seem simple at first, but standards win long-term
2. **Extensibility points matter**: Plugin architecture takes effort but pays off
3. **User control beats convenience**: Advanced users will always want control
4. **Documentation is architecture**: If it's hard to document, the architecture needs work

---

## Summary

Thoth's design philosophy centers on **user control**, **local-first privacy**, **standards-based extensibility**, **modular composition**, and **progressive disclosure**.

These principles led to key decisions:
- **Letta** for agent memory (research-backed, persistent)
- **MCP** for tools (industry standard, ecosystem compatible)
- **Skills** for dynamic loading (token-efficient, user-extensible)
- **Plugins** for sources (open-ended, LLM auto-detection)
- **Templates** for prompts (transparent, customizable)
- **Independent services** (failure isolation, multi-project sharing)

Trade-offs were made consciously:
- Complexity for control
- Local infrastructure for privacy
- Standards for future-proofing
- Modularity for maintainability

**Result**: A research assistant that adapts to users, not the other way around.

---

**Last Updated**: February 2026
