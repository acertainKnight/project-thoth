# Thoth Usage Guide

Complete guide to using Thoth Research Assistant for daily research workflows.

## Table of Contents

- [Quick Reference](#quick-reference)
- [Using the Agent](#using-the-agent)
- [Document Processing](#document-processing)
- [Paper Discovery](#paper-discovery)
- [Research Questions](#research-questions)
- [Citation Management](#citation-management)
- [RAG & Semantic Search](#rag--semantic-search)
- [Skills System](#skills-system)
- [Settings Management](#settings-management)
- [Best Practices](#best-practices)

---

## Quick Reference

### Daily Commands

```bash
# Start services
thoth start              # or: make dev

# Check status
thoth status            # or: make health

# View logs
thoth logs              # or: make dev-logs

# Stop services
thoth stop              # or: make dev-stop
```

### CLI Subcommands

| Command | Purpose |
|---------|---------|
| `thoth setup` | Interactive setup wizard |
| `thoth server start` | Start API server |
| `thoth mcp start` | Start MCP server |
| `thoth letta auth` | Manage Letta authentication |
| `thoth discovery ...` | Paper discovery operations |
| `thoth pdf ...` | PDF processing |
| `thoth research ...` | Research operations |
| `thoth rag ...` | RAG operations |
| `thoth notes ...` | Note generation |
| `thoth schema ...` | Schema management |
| `thoth service ...` | Service management |
| `thoth system ...` | System utilities |
| `thoth database ...` | Database operations |
| `thoth performance ...` | Performance analysis |

---

## Using the Agent

### Via Obsidian Plugin (Primary Method)

1. **Open chat**:
   - Click Thoth icon in left sidebar
   - Or: Command Palette (`Ctrl/Cmd+P`) → "Open Thoth Chat"

2. **Start conversation**:
   ```
   You: "Find papers on transformer attention mechanisms"
   Agent: [Loads paper-discovery skill, searches sources, returns results]
   ```

3. **Multi-session support**:
   - Click "New Chat" for new session
   - Switch between sessions with tabs
   - All conversations persist across restarts

### Via Letta REST API

```bash
# List agents
curl http://localhost:8283/v1/agents

# Send message
curl -X POST http://localhost:8283/v1/agents/{agent_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "text": "Find papers on deep learning"}]}'
```

### Agent Capabilities

**Research Orchestrator** (`thoth_main_orchestrator`):
- User-facing coordinator
- Loads skills dynamically based on task
- Delegates complex analysis to Analyst
- Memory: persona, human, research_context, loaded_skills, planning, scratchpad

**Research Analyst** (`thoth_research_analyst`):
- Deep analysis specialist
- Literature reviews and synthesis
- Paper comparisons and evaluations
- Citation network exploration

### Common Agent Workflows

**Discovery**:
```
You: "Find recent papers on reinforcement learning"
Agent: Loads paper-discovery skill → searches ArXiv, Semantic Scholar →
       returns ranked results with relevance scores
```

**Q&A**:
```
You: "What are the main approaches to attention mechanisms in transformers?"
Agent: Loads knowledge-base-qa skill → searches processed papers →
       answers with citations from your collection
```

**Analysis**:
```
You: "Compare these two papers on attention mechanisms"
Agent: Delegates to research_analyst → loads both papers →
       compares methodology, results, conclusions → provides structured comparison
```

---

## Document Processing

### Automatic Processing (Recommended)

**Setup**:
```bash
# PDF Monitor runs automatically in dev mode
make dev
```

**Usage**:
1. Drop PDF into `vault/thoth/papers/pdfs/`
2. Monitor processes it automatically
3. Note appears in `vault/thoth/notes/`
4. Takes 30-60 seconds per paper

**What Gets Extracted**:
- Title, authors, abstract
- Full text with sections
- Citations (with 6-stage enrichment)
- Topic tags (AI-generated)
- Metadata (DOI, journal, year)

### Manual Processing

```bash
# Process single PDF
python -m thoth pdf process paper.pdf

# Process with options
python -m thoth pdf process paper.pdf \
    --output-dir ./notes \
    --generate-tags \
    --build-index

# Batch processing
python -m thoth pdf process ./papers/ --parallel --max-workers 4
```

### Custom Extraction

Edit `vault/thoth/_thoth/analysis_schema.json` to control what gets extracted:

```json
{
  "presets": {
    "custom": {
      "fields": {
        "title": true,
        "abstract": true,
        "methodology": true,
        "results": true,
        "limitations": true,
        "future_work": true,
        "custom_field": {
          "extract": true,
          "prompt": "Extract the computational complexity analysis"
        }
      }
    }
  }
}
```

Then use the preset:
```bash
# Via settings
python -m thoth schema set-preset custom

# Or in settings.json
{"processing": {"schema_preset": "custom"}}
```

---

## Paper Discovery

### Using Discovery Sources

**7 built-in sources**:
1. ArXiv (RSS + API)
2. Semantic Scholar
3. NeurIPS
4. ICML
5. OpenReview (ICLR, etc.)
6. ACL Anthology (NLP conferences)
7. Papers with Code

### Via Agent (Easiest)

```
You: "Find papers on deep learning published in 2024"
Agent: [Loads paper-discovery skill, queries sources, returns results]
```

### Via CLI

```bash
# List available sources
python -m thoth discovery list-sources

# Search specific source
python -m thoth discovery search "transformers" --source arxiv --max-results 50

# Search all sources
python -m thoth discovery search "neural networks" --max-results 100
```

### Creating Custom Sources

**Automated scraper builder** (LLM-powered):

```
You: "I want to add papers from https://example.com/papers"
Agent: [Loads custom-source-setup skill]
       [Analyzes page structure with LLM + Playwright]
       [Proposes CSS selectors]
       [Tests selectors and shows sample articles]
       [Iteratively refines based on your feedback]
       [Saves confirmed workflow]
```

**How it works**:
1. Playwright loads URL and extracts simplified DOM
2. LLM analyzes structure and proposes CSS selectors
3. Selectors tested on live page → sample articles extracted
4. You review samples and provide feedback
5. LLM refines selectors based on feedback
6. Repeat until accurate
7. Workflow saved for future use

---

## Research Questions

Research questions enable persistent, structured research with automated discovery.

### Creating Research Questions

**Via Agent**:
```
You: "Create a research question about attention mechanisms in transformers"
Agent: [Loads research-query-management skill]
       [Creates question with discovery settings]
       [Sets up automated discovery]
```

**Via CLI**:
```bash
# Create question
python -m thoth research create \
    --question "How do attention mechanisms work in transformers?" \
    --sources arxiv semantic_scholar \
    --schedule "0 9 * * *"  # Daily at 9 AM

# List questions
python -m thoth research list

# Run discovery for question
python -m thoth research discover <question_id>
```

### Research Question Features

- **Automated discovery**: Scheduled searches for new papers
- **Source configuration**: Which sources to query
- **Relevance filtering**: Automatic filtering based on your collection
- **Progress tracking**: Track papers found, processed, relevant
- **Synthesis**: Generate literature reviews from findings

---

## Citation Management

### Citation Extraction & Enrichment

**Automatic** (during PDF processing):
- Citations extracted from bibliography section
- 6-stage enrichment chain automatically runs
- DOIs, metadata, and citation counts added
- ~90% enrichment success rate

**Manual enrichment**:
```bash
# Via agent
You: "Enrich citations in paper_xyz"
Agent: [Runs citation enrichment service]

# Via CLI
python -m thoth citations enrich paper.pdf
```

### Citation Resolution Chain

1. **Crossref**: DOI lookup, metadata
2. **OpenAlex**: Citation counts, authors
3. **ArXiv**: ArXiv paper metadata
4. **Fuzzy Matcher**: Handle malformed citations
5. **Validator**: Confidence scoring
6. **Decision Engine**: Best match selection

### Citation Formats

**Via Agent**:
```
You: "Format citations from paper_xyz in APA style"
Agent: [Uses format_citations tool with APA formatter]
```

**Via MCP Tool** (from code/API):
```python
# Format citations
result = mcp_client.call_tool(
    "format_citations",
    {
        "article_id": "abc123",
        "style": "apa"  # or: bibtex, mla, chicago
    }
)

# Export bibliography
result = mcp_client.call_tool(
    "export_bibliography",
    {
        "article_ids": ["abc123", "def456"],
        "style": "bibtex",
        "output_file": "references.bib"
    }
)
```

---

## RAG & Semantic Search

### Building the Index

```bash
# Build index from all processed papers
python -m thoth rag build

# Rebuild index (if papers changed)
python -m thoth rag rebuild

# Add specific paper
python -m thoth rag add paper.pdf
```

### Searching

**Via Agent** (recommended):
```
You: "What papers discuss attention mechanisms?"
Agent: [Loads knowledge-base-qa skill]
       [Searches vector index]
       [Returns relevant papers with citations]
```

**Via CLI**:
```bash
# Semantic search
python -m thoth rag search "attention mechanisms in transformers"

# With filters
python -m thoth rag search "neural networks" \
    --top-k 10 \
    --min-score 0.7 \
    --year 2024
```

### Custom Indexes

Create domain-specific search indexes:

```
You: "Create a custom index for reinforcement learning papers"
Agent: [Loads rag-administration skill]
       [Uses create_custom_index tool]
       [Filters papers by topic]
       [Builds specialized index]
```

---

## Skills System

### Discovering Skills

**Via Agent**:
```
You: "What skills do you have?"
Agent: [Calls list_skills tool, shows available skills with descriptions]
```

**Via MCP**:
```bash
# List all skills
curl -X POST http://localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "list_skills"}, "id": 1}'
```

### Loading Skills

**Automatic** (agent loads as needed):
```
You: "Find papers on deep learning"
Agent: "Loading paper-discovery skill..."
       [Skill attaches required tools dynamically]
       [Agent uses tools to search]
```

**Manual**:
```
You: "Load the deep-research skill"
Agent: [Loads skill, attaches tools, shows capabilities]
```

### Creating Custom Skills

1. Create skill directory: `vault/thoth/_thoth/skills/my-skill/`
2. Create `SKILL.md`:
   ```yaml
   ---
   name: My Custom Skill
   description: What this skill does
   tools:
     - tool_name_1
     - tool_name_2
   ---

   # Skill guidance

   When this skill is loaded, follow these steps:
   1. First do X
   2. Then do Y
   3. Finally do Z
   ```
3. Agent auto-discovers skill on next restart
4. Load with: `load_skill(skill_ids=["my-skill"])`

**Hot-reload**: Edit skill files and they reload automatically (no restart needed)

---

## Settings Management

### Via Agent (Easiest)

```
You: "Change the default model to Claude 3.5 Sonnet"
Agent: [Loads settings-management skill]
       [Updates settings.json]
       [Confirms change applied]

You: "Show current LLM configuration"
Agent: [Displays current LLM settings]
```

### Via Settings File

Edit `vault/thoth/_thoth/settings.json`:

```json
{
  "llm_config": {
    "default": {
      "model": "openrouter/anthropic/claude-3.5-sonnet",
      "temperature": 0.7,
      "max_tokens": 4096
    }
  }
}
```

**Changes apply in ~2 seconds** (dev mode with hot-reload)

### Via MCP Tools

```python
# View settings
view_settings()

# Update settings
update_settings({"llm_config.default.temperature": 0.5})

# Validate settings
validate_settings()

# Reset to defaults
reset_settings()
```

---

## Best Practices

### Organizing Your Research

**Vault Structure**:
```
vault/
├── thoth/
│   ├── _thoth/                # Thoth config (user-editable)
│   │   ├── settings.json     # Edit configuration here
│   │   ├── mcps.json         # MCP server config
│   │   ├── analysis_schema.json
│   │   ├── prompts/          # Custom prompt templates
│   │   └── skills/           # User-created skills
│   ├── papers/
│   │   ├── pdfs/             # Drop PDFs here
│   │   └── markdown/         # Converted markdown
│   └── notes/                 # Generated notes appear here
├── Research/                  # Your research (manual)
│   ├── Projects/
│   │   ├── Project A/
│   │   └── Project B/
│   └── Literature Reviews/
└── Papers/                    # Link to generated notes
```

### Research Workflow Tips

1. **Start with discovery**: Use agent to find papers first
2. **Let auto-processing work**: Drop PDFs in folder, wait for notes
3. **Ask questions**: Use knowledge-base-qa skill for Q&A
4. **Track progress**: Use research questions for ongoing projects
5. **Build knowledge**: Citation networks auto-build as you process papers

### Agent Interaction

**Be specific**:
```
❌ "Find some papers"
✅ "Find papers on transformer attention mechanisms published in 2024"
```

**Use skills explicitly** when needed:
```
You: "Load the deep-research skill and analyze the paper on attention mechanisms"
```

**Leverage memory**:
```
You: "Remember that I'm interested in computational efficiency"
Agent: [Updates human memory block]

[Later]
You: "Find papers on transformers"
Agent: [Remembers your interest, prioritizes efficiency-focused papers]
```

### Performance Optimization

**Batch operations**:
```bash
# Process multiple PDFs at once
python -m thoth pdf process ./papers/ --parallel
```

**Scheduled discovery** (runs during off-hours):
```json
{
  "discovery": {
    "auto_start_scheduler": true,
    "schedules": [
      {
        "cron": "0 2 * * *",  // 2 AM daily
        "query": "machine learning",
        "max_articles": 50
      }
    ]
  }
}
```

**Cache management**:
```bash
# Clear cache if memory usage high
rm -rf vault/thoth/_thoth/cache/*

# Rebuild indexes
python -m thoth rag rebuild
```

---

## Advanced Usage

### Custom Prompts

Override default prompts by creating files in `vault/thoth/_thoth/prompts/`:

```
_thoth/prompts/
├── custom_analysis.j2        # Custom analysis prompt
├── custom_summary.j2          # Custom summary prompt
└── custom_citation.j2         # Custom citation extraction
```

Reference in settings.json:
```json
{
  "processing": {
    "custom_prompts": {
      "analysis": "_thoth/prompts/custom_analysis.j2"
    }
  }
}
```

### Direct MCP Tool Access

For programmatic access:

```python
import httpx

# Call MCP tool
response = httpx.post(
    "http://localhost:8082/mcp",
    json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "search_articles",
            "arguments": {
                "query": "transformer attention",
                "max_results": 10
            }
        },
        "id": 1
    }
)

result = response.json()["result"]
```

### Multi-User Setup

For teams:

1. **Shared Letta instance**: One Letta server, multiple Thoth instances
2. **Separate vaults**: Each user has their own Obsidian vault
3. **Shared database**: Optional shared PostgreSQL for team papers
4. **Access control**: Configure per-user API keys

---

## Troubleshooting

### Agent Not Responding

```bash
# Check Letta is running
curl http://localhost:8283/v1/health

# Check agents exist
curl http://localhost:8283/v1/agents

# View logs
docker logs letta-server
tail -f vault/thoth/_thoth/logs/thoth.log
```

### PDFs Not Processing

```bash
# Check PDF Monitor logs
docker logs thoth-dev-pdf-monitor  # dev mode
docker logs thoth-all-in-one       # prod mode

# Check file permissions
ls -la vault/thoth/papers/pdfs/

# Manual processing
python -m thoth pdf process paper.pdf --verbose
```

### Skills Not Loading

```bash
# List available skills
curl -X POST http://localhost:8082/mcp \
  -d '{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "list_skills"}, "id": 1}'

# Check skill directories exist
ls src/thoth/.skills/
ls vault/thoth/_thoth/skills/
```

### Discovery Not Finding Papers

1. **Check API keys**: Verify Semantic Scholar key is set
2. **Check sources**: List available sources
3. **Adjust query**: Be more specific
4. **Check logs**: Look for API errors

---

## Next Steps

- **[Quick Reference](quick-reference.md)**: Command cheat sheet
- **[Architecture](architecture.md)**: Understand system design
- **[MCP Architecture](mcp-architecture.md)**: Learn about tools
- **[Letta Architecture](letta-architecture.md)**: Learn about agents

---

**Last Updated**: February 2026
