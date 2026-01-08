# Thoth Usage Guide

Day-to-day usage patterns, best practices, and workflows for Thoth Research Assistant.

## Table of Contents

- [Daily Workflow](#daily-workflow)
- [Document Processing](#document-processing)
- [Research Discovery](#research-discovery)
- [Using the Obsidian Plugin](#using-the-obsidian-plugin)
- [Working with Agents](#working-with-agents)
- [Citation Management](#citation-management)
- [Best Practices](#best-practices)
- [Tips & Tricks](#tips--tricks)

## Daily Workflow

### Starting Your Research Session

```bash
# 1. Start Thoth services (if not already running)
make dev  # or make prod for production

# 2. Verify services are healthy
make health

# 3. Open Obsidian and enable Thoth plugin
# Click the Thoth icon in the left ribbon
```

### Typical Research Workflow

1. **Discover Papers**: Find relevant research using multi-source discovery
2. **Download PDFs**: Save papers to `_thoth/data/pdfs/` directory
3. **Automatic Processing**: PDF Monitor processes them automatically
4. **Review Notes**: Generated notes appear in `_thoth/data/notes/`
5. **Chat with Agent**: Ask questions about processed papers
6. **Build Knowledge**: Citations and relationships tracked automatically

## Document Processing

### Processing Single PDF

**Via Obsidian Plugin** (Recommended):
1. Open Obsidian
2. Click Thoth ribbon icon
3. Drop PDF into `_thoth/data/pdfs/` folder
4. Wait for processing notification
5. Note appears in `_thoth/data/notes/`

**Via Command Line**:
```bash
# Process single paper
python -m thoth pdf process /path/to/paper.pdf

# With options
python -m thoth pdf process paper.pdf \
    --generate-tags \
    --enrich-citations \
    --build-index
```

### Batch Processing

```bash
# Process entire directory
python -m thoth pdf process ./papers/ --parallel

# Process with filtering
python -m thoth pdf process ./papers/ \
    --pattern "*.pdf" \
    --parallel \
    --max-workers 4
```

### Monitoring for Auto-Processing

**Automatic** (recommended):
```bash
# PDF Monitor runs automatically in development mode
make dev
# Now just drop PDFs into _thoth/data/pdfs/
```

**Manual monitoring**:
```bash
# Monitor specific directory
python -m thoth pdf monitor --watch-dir ./new-papers/

# With options
python -m thoth pdf monitor \
    --watch-dir ./papers/ \
    --recursive \
    --debounce 2  # Wait 2 seconds before processing
```

### Processing Options

Configure processing in `_thoth/settings.json`:

```json
{
  "processing": {
    "generate_tags": true,
    "enrich_citations": true,
    "build_index": true,
    "chunk_size": 500,
    "chunk_overlap": 50
  }
}
```

**Options Explained**:
- `generate_tags`: AI-generated topic tags
- `enrich_citations`: Lookup DOIs and metadata
- `build_index`: Add to RAG vector index
- `chunk_size`: Semantic chunk size (tokens)
- `chunk_overlap`: Overlap between chunks

## Research Discovery

### Multi-Source Search

**ArXiv Discovery**:
```bash
# Search ArXiv
python -m thoth discovery search "transformer architectures" \
    --source arxiv \
    --max-results 50

# Filter by category
python -m thoth discovery search "machine learning" \
    --source arxiv \
    --categories cs.LG cs.AI \
    --date-range "last_7_days"
```

**Semantic Scholar**:
```bash
# Search Semantic Scholar
python -m thoth discovery search "large language models" \
    --source semantic_scholar \
    --fields computer_science \
    --min-citations 10
```

**Combined Search**:
```bash
# Search all sources
python -m thoth discovery search "neural networks" \
    --sources arxiv semantic_scholar \
    --max-results 100 \
    --relevance-threshold 0.7
```

### Automated Discovery

**Schedule Regular Discovery**:
```bash
# Schedule daily discovery at 9 AM
python -m thoth discovery schedule \
    --query "reinforcement learning" \
    --source arxiv \
    --cron "0 9 * * *" \
    --max-articles 50
```

**Schedule Configuration** in `settings.json`:
```json
{
  "discovery": {
    "auto_start_scheduler": true,
    "schedules": [
      {
        "name": "Daily ML Papers",
        "query": "machine learning",
        "source": "arxiv",
        "cron": "0 9 * * *",
        "max_articles": 50
      }
    ]
  }
}
```

### Browser Workflows

For sites without APIs:

```bash
# Create custom workflow
python -m thoth discovery workflow create conference_papers.json

# Execute workflow
python -m thoth discovery workflow execute conference_papers
```

Example workflow (`conference_papers.json`):
```json
{
  "name": "Conference Paper Download",
  "steps": [
    {"action": "navigate", "url": "https://conference.org/papers"},
    {"action": "wait", "selector": ".paper-list"},
    {"action": "extract", "selector": ".paper-item"},
    {"action": "download", "selector": ".pdf-link"}
  ]
}
```

## Using the Obsidian Plugin

### Opening the Chat Interface

**Methods to open chat**:
1. Click **Thoth icon** in left ribbon (quickest)
2. Command Palette (`Ctrl/Cmd+P`) → "Open Thoth Chat"
3. Keyboard shortcut (configure in settings)

### Chat Window Features

**Desktop Mode**:
- Bottom-right popup (450x600px default)
- **Drag** title bar to reposition
- **Resize** by dragging edges
- **Transparent backdrop** - work in vault while chatting!

**Mobile Mode**:
- Fullscreen interface
- Touch-optimized controls
- Swipe to close

### Multi-Session Chats

**Create New Session**:
1. Click "New Chat" button
2. Or Command Palette → "Thoth: New Chat Session"

**Switch Sessions**:
- Click session tab at top of chat window
- Or use session dropdown

**Session Management**:
- **Rename**: Right-click session tab → Rename
- **Delete**: Right-click session tab → Delete
- **Archive**: Right-click → Archive (keeps history)

### Research Queries from Selection

1. Select text in any note
2. Right-click → "Insert Research Query"
3. Or use keyboard shortcut
4. Chat opens with selected text as query
5. Results appear in chat

### Settings Panel

Access via:
- Plugin settings: Settings → Thoth Research Assistant
- Or click gear icon in chat window

**Key Settings**:
- **Connection**: Local vs Remote mode
- **Auto-start**: Launch agent on Obsidian startup
- **API Keys**: Configure LLM providers
- **Directories**: Customize paths
- **Advanced**: JSON editor for power users

## Working with Agents

### Letta Agent System

Thoth uses **Letta** for persistent, intelligent agents with memory across sessions.

**Access Agent**:
1. Via Obsidian plugin chat (primary method)
2. Via REST API at `http://localhost:8283`
3. Via Letta web UI (if enabled)

### Agent Capabilities

**Available to All Agents**:
- 54 MCP research tools
- Persistent memory (PostgreSQL+pgvector)
- Cross-session continuity
- Real-time streaming responses

**Tool Categories**:
- **Query Management**: Save and retrieve research queries
- **Discovery**: Find papers from multiple sources
- **Citation Analysis**: Extract and enrich citations
- **Article Operations**: Manage paper metadata
- **Processing**: Trigger document pipeline
- **PDF Content**: Extract text and metadata
- **RAG Operations**: Semantic search
- **Analysis**: Deep document analysis
- **Tag Management**: Organize papers
- **Browser Workflows**: Custom scraping
- **Web Search**: Search academic sources
- **Settings**: Configuration management
- **Data Management**: Export/import operations

### Common Agent Interactions

**Research Assistance**:
```
You: "Find me recent papers on transformer attention mechanisms"
Agent: [Uses discovery tools to search ArXiv and Semantic Scholar]
       [Returns ranked list with relevance scores]

You: "Summarize the top 3 papers"
Agent: [Uses article tools to access papers]
       [Generates comprehensive summaries]
```

**Citation Analysis**:
```
You: "Extract citations from paper_xyz.pdf"
Agent: [Uses citation tools to parse references]
       [Returns structured citation data]

You: "Enrich these citations with DOIs"
Agent: [Uses enrichment service with 6-stage resolution]
       [Returns enhanced citations with metadata]
```

**Literature Review**:
```
You: "Help me review papers on reinforcement learning from 2023"
Agent: [Searches vault for matching papers]
       [Analyzes citation networks]
       [Identifies key papers and trends]
       [Generates structured review]
```

## Citation Management

### Extracting Citations

```bash
# Extract from PDF
python -m thoth citations extract paper.pdf

# Extract and enrich
python -m thoth citations extract paper.pdf --enrich

# Batch extraction
python -m thoth citations extract ./papers/ --batch --parallel
```

### Citation Enrichment

The **6-stage resolution chain** automatically enriches citations:

1. **Crossref**: DOI lookup
2. **OpenAlex**: Metadata and citation counts
3. **ArXiv**: ArXiv papers
4. **Fuzzy Matching**: Handle malformed citations
5. **Validation**: Confidence scoring
6. **Decision**: Best match selection

**Enrichment happens automatically** during document processing.

### Citation Network Analysis

```bash
# Build citation graph
python -m thoth citations graph --build

# Analyze network
python -m thoth citations graph --analyze \
    --metrics pagerank betweenness

# Find influential papers
python -m thoth citations graph --top-papers 20

# Export visualization
python -m thoth citations graph --export network.gexf
```

### Citation Formats

Generate bibliographies:

```bash
# Format citations in APA
python -m thoth citations format paper.pdf --style apa

# Format in BibTeX
python -m thoth citations format paper.pdf --style bibtex

# Other formats: MLA, Chicago, Harvard
python -m thoth citations format paper.pdf --style mla
```

## Best Practices

### Organizing Your Vault

**Recommended Structure**:
```
your-vault/
├── _thoth/              # Thoth data (automatic)
├── Research/            # Your research notes
│   ├── Projects/
│   ├── Literature/
│   └── Ideas/
├── Papers/              # Manual paper organization
│   ├── To-Read/
│   ├── In-Progress/
│   └── Completed/
└── Templates/           # Note templates
```

### Vault Management

**Keep _thoth/ Clean**:
- Don't manually edit files in `_thoth/data/`
- Generated notes can be moved out of `_thoth/data/notes/`
- Logs rotate automatically (check `_thoth/logs/`)
- Cache is safe to delete (will regenerate)

**Settings Management**:
- Edit `_thoth/settings.json` for configuration
- Changes apply immediately in dev mode (~2s)
- Back up settings.json before major changes
- Use version control for settings.json

### Performance Tips

1. **Batch Processing**: Process multiple PDFs at once
2. **Scheduled Discovery**: Run during off-hours
3. **Cache Warming**: Process common queries first
4. **Index Maintenance**: Rebuild RAG index periodically
5. **Log Rotation**: Clear old logs regularly

### API Key Management

**Security**:
- Never commit `.env` file to git
- Use environment variables for keys
- Rotate keys periodically
- Use separate keys for dev/prod

**Cost Optimization**:
- Start with free tiers
- Use caching to reduce API calls
- Batch operations when possible
- Monitor API usage regularly

## Tips & Tricks

### Keyboard Shortcuts

Configure in Obsidian Settings → Hotkeys:
- **Open Chat**: No default (set your own)
- **New Chat Session**: No default
- **Insert Research Query**: No default

### Quick Commands

**Via Command Palette** (`Ctrl/Cmd+P`):
- "Thoth: Open Chat"
- "Thoth: Start Agent"
- "Thoth: Stop Agent"
- "Thoth: Restart Agent"
- "Thoth: Check Health"

### Obsidian Integration

**Link to Generated Notes**:
```markdown
See [[paper_title]] for details on transformers.
```

**Embed Notes**:
```markdown
![[paper_title#Abstract]]
```

**Query Generated Tags**:
```markdown
#machine-learning #transformers #attention
```

### Advanced Features

**Custom Prompts**:
Place custom prompts in `_thoth/data/prompts/`:
```
_thoth/data/prompts/
├── summarize.txt
├── analyze.txt
└── review.txt
```

Reference in chat:
```
You: "Use my summarize prompt on this paper"
```

**Research Questions**:
Create structured research questions:
```bash
# Create research question
python -m thoth research create "How do transformers work?"

# Link papers to question
python -m thoth research link <question_id> <paper_id>

# Generate synthesis
python -m thoth research synthesize <question_id>
```

### Troubleshooting Common Issues

**Chat Not Responding**:
1. Check backend health: `make health`
2. Check WebSocket connection in DevTools
3. Restart plugin in Obsidian

**PDFs Not Processing**:
1. Check PDF Monitor logs: `docker logs thoth-dev-pdf-monitor`
2. Verify PDF is in correct directory
3. Check file permissions (UID 1000)
4. Try manual processing: `python -m thoth pdf process file.pdf`

**Discovery Not Finding Papers**:
1. Verify API keys are set
2. Check query relevance
3. Adjust relevance threshold in settings
4. Try different sources

**Memory Issues**:
1. Clear cache: `rm -rf _thoth/cache/*`
2. Rebuild indexes: `python -m thoth rag rebuild`
3. Check Docker container memory: `docker stats`

---

For more information:
- [Setup Guide](setup.md) - Installation and configuration
- [Architecture](architecture.md) - System design
- [Quick Reference](quick-reference.md) - Command cheat sheet
- [GitHub Issues](https://github.com/acertainKnight/project-thoth/issues) - Report problems

Happy researching! 🚀
