# Thoth Quick Reference

Command cheat sheet and quick reference for Thoth Research Assistant.

## Table of Contents

- [Docker Commands](#docker-commands)
- [CLI Commands](#cli-commands)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

## Docker Commands

### Service Management

```bash
# Start services
make dev                    # Development mode (hot-reload, debug)
make prod                   # Production mode (optimized)

# Stop services
make dev-stop              # Stop development
make prod-stop             # Stop production

# Restart services
make dev-restart           # Restart development
make prod-restart          # Restart production (zero downtime)

# View logs
make dev-logs              # Follow all development logs
make prod-logs             # Follow production logs
make logs                  # View all logs

# Health check
make health                # Check all services status

# Clean up
make clean                 # Remove build artifacts
make dev-clean             # Stop and remove dev containers
make prod-clean            # Stop and remove prod containers
```

### Individual Service Logs

```bash
# View specific service logs
docker logs thoth-dev-api                 # API server
docker logs thoth-dev-mcp                 # MCP server
docker logs thoth-dev-pdf-monitor         # PDF monitor
docker logs thoth-dev-letta               # Letta memory
docker logs thoth-dev-postgres            # PostgreSQL
docker logs thoth-dev-chroma              # ChromaDB

# Follow logs
docker logs -f thoth-dev-api              # Real-time API logs
```

### Service Status

```bash
# List running containers
docker compose -f docker-compose.dev.yml ps

# Check container resource usage
docker stats

# Inspect specific service
docker inspect thoth-dev-api
```

## CLI Commands

### PDF Processing

```bash
# Process single PDF
python -m thoth pdf process paper.pdf
python -m thoth pdf process paper.pdf --generate-tags --enrich-citations

# Batch process directory
python -m thoth pdf process ./papers/ --parallel
python -m thoth pdf process ./papers/ --parallel --max-workers 4

# Monitor directory
python -m thoth pdf monitor --watch-dir ./papers/
python -m thoth pdf monitor --watch-dir ./papers/ --recursive
```

### Discovery

```bash
# Start discovery service
python -m thoth discovery start

# Search sources
python -m thoth discovery search "query" --source arxiv
python -m thoth discovery search "query" --source semantic_scholar
python -m thoth discovery search "query" --sources arxiv semantic_scholar

# Schedule discovery
python -m thoth discovery schedule \
    --query "machine learning" \
    --source arxiv \
    --cron "0 9 * * *"

# List sources
python -m thoth discovery sources

# Stop discovery
python -m thoth discovery stop
```

### MCP Server

```bash
# Start MCP server
python -m thoth mcp start --host 0.0.0.0 --http-port 8000

# List available tools
python -m thoth mcp tools

# Test specific tool
python -m thoth mcp test discover_papers

# Server information
python -m thoth mcp info
```

### RAG Operations

```bash
# Build vector index
python -m thoth rag build

# Semantic search
python -m thoth rag search "query text"
python -m thoth rag search "query" --top-k 10 --threshold 0.7

# Query with filters
python -m thoth rag query "transformers" --year 2023 --author "Smith"

# Rebuild index
python -m thoth rag rebuild --force
```

### Citation Management

```bash
# Extract citations
python -m thoth citations extract paper.pdf
python -m thoth citations extract paper.pdf --enrich

# Format citations
python -m thoth citations format paper.pdf --style apa
python -m thoth citations format paper.pdf --style bibtex

# Build citation graph
python -m thoth citations graph --build
python -m thoth citations graph --analyze --metrics pagerank
python -m thoth citations graph --top-papers 20
```

### Research Questions

```bash
# Create research question
python -m thoth research create "Research question text"

# List questions
python -m thoth research list

# Run discovery for question
python -m thoth research discover <question_id>

# Export results
python -m thoth research export <question_id> --format json
```

### System Commands

```bash
# Check configuration
python -m thoth system check

# Show vault information
python -m thoth system vault

# Clear cache
python -m thoth system clear-cache

# Run migrations
python -m thoth system migrate

# Export data
python -m thoth system export --output backup.json
```

## API Endpoints

### Health & Status

```bash
# Overall health
curl http://localhost:8000/health | jq

# Service-specific health
curl http://localhost:8000/health/services | jq

# Ready status (Kubernetes)
curl http://localhost:8000/readiness

# Liveness probe
curl http://localhost:8000/liveness
```

### Configuration

```bash
# Get configuration
curl http://localhost:8000/config | jq

# Update configuration
curl -X POST http://localhost:8000/config \
  -H "Content-Type: application/json" \
  -d @settings.json

# Reload configuration
curl -X POST http://localhost:8000/config/reload

# Get schema
curl http://localhost:8000/config/schema | jq
```

### Document Processing

```bash
# Process PDF
curl -X POST http://localhost:8000/process \
  -F "file=@paper.pdf"

# Batch process
curl -X POST http://localhost:8000/batch-process \
  -H "Content-Type: application/json" \
  -d '{"files": ["file1.pdf", "file2.pdf"]}'

# Get operation status
curl http://localhost:8000/operations/<id> | jq

# List operations
curl http://localhost:8000/operations | jq
```

### Chat & Research

```bash
# Send chat message
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Thoth"}'

# Get chat history
curl http://localhost:8000/chat/history | jq

# Run research query
curl -X POST http://localhost:8000/research/query \
  -H "Content-Type: application/json" \
  -d '{"query": "transformers"}'

# Get results
curl http://localhost:8000/research/results/<id> | jq
```

### MCP Tools

```bash
# List tools
curl http://localhost:8082/tools | jq

# Get tool schema
curl http://localhost:8082/tools/<tool_name>/schema | jq

# Execute tool
curl -X POST http://localhost:8082/tools/<tool_name> \
  -H "Content-Type: application/json" \
  -d '{"param1": "value1"}'
```

### Letta (Agent Memory)

```bash
# List agents
curl http://localhost:8283/v1/agents | jq

# Get agent details
curl http://localhost:8283/v1/agents/<agent_id> | jq

# Send message to agent
curl -X POST http://localhost:8283/v1/agents/<agent_id>/messages \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello agent"}'

# Get agent memory
curl http://localhost:8283/v1/agents/<agent_id>/memory | jq
```

## Configuration

### Environment Variables

```bash
# Required
export OBSIDIAN_VAULT_PATH="/path/to/vault"
export MISTRAL_API_KEY="your_key"
export OPENROUTER_API_KEY="your_key"

# Optional
export OPENAI_API_KEY="your_key"
export SEMANTIC_SCHOLAR_KEY="your_key"
export GOOGLE_API_KEY="your_key"
```

### Settings File Location

```bash
# Main settings file
$OBSIDIAN_VAULT_PATH/_thoth/settings.json

# Plugin settings
$OBSIDIAN_VAULT_PATH/.obsidian/plugins/thoth-obsidian/data.json

# Environment file
.env  # In project root
```

### Key Settings

```json
{
  "llm_config": {
    "default": {
      "model": "mistral/mistral-large-latest",
      "temperature": 0.7
    }
  },
  "discovery": {
    "auto_start_scheduler": false,
    "default_max_articles": 50
  },
  "processing": {
    "generate_tags": true,
    "enrich_citations": true,
    "build_index": true
  }
}
```

## Common Workflows

### Daily Research Session

```bash
# 1. Start services
make dev

# 2. Check health
make health

# 3. Open Obsidian and chat with agent
# (Click Thoth ribbon icon)

# 4. View logs if needed
make dev-logs
```

### Process New Papers

```bash
# 1. Drop PDFs into vault
cp paper1.pdf paper2.pdf $OBSIDIAN_VAULT_PATH/_thoth/data/pdfs/

# 2. Monitor automatically processes them
# (If dev mode is running)

# 3. Check generated notes
ls $OBSIDIAN_VAULT_PATH/_thoth/data/notes/

# 4. View in Obsidian
```

### Discovery Workflow

```bash
# 1. Search for papers
python -m thoth discovery search "machine learning" \
    --source arxiv \
    --max-results 50

# 2. Review results in terminal

# 3. Download selected papers
# (PDFs auto-downloaded to _thoth/data/pdfs/)

# 4. Processing happens automatically
```

### Update Configuration

```bash
# 1. Edit settings
nano $OBSIDIAN_VAULT_PATH/_thoth/settings.json

# 2. In dev mode, changes apply automatically (~2s)

# 3. Or manually reload
make reload-settings

# 4. Verify changes
curl http://localhost:8000/config | jq
```

## Troubleshooting

### Quick Diagnostics

```bash
# Check all services
make health

# Check specific service
docker ps | grep thoth

# View recent errors
docker logs thoth-dev-api --tail 100 | grep ERROR

# Check disk space
df -h

# Check memory usage
docker stats --no-stream
```

### Common Fixes

```bash
# Restart specific service
docker restart thoth-dev-api

# Rebuild specific service
docker compose -f docker-compose.dev.yml up -d --build api

# Clear cache
rm -rf $OBSIDIAN_VAULT_PATH/_thoth/cache/*

# Reset database (WARNING: Loses data)
docker compose -f docker-compose.dev.yml down -v
make dev
```

### Port Conflicts

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>

# Or change port in settings.json
```

### Permission Issues

```bash
# Fix vault permissions
chmod -R u+rw $OBSIDIAN_VAULT_PATH/_thoth

# Fix Docker permissions
sudo chown -R 1000:1000 $OBSIDIAN_VAULT_PATH/_thoth
```

### Service Won't Start

```bash
# Check logs
docker logs thoth-dev-api

# Verify environment
echo $OBSIDIAN_VAULT_PATH
cat .env

# Rebuild from scratch
make clean
make dev
```

## Testing

### Run Tests

```bash
# All tests (998 total)
pytest tests/

# Specific categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# With coverage
pytest --cov=src/thoth tests/

# Specific test file
pytest tests/unit/services/test_llm_service.py

# Verbose output
pytest -vv tests/
```

### Code Quality

```bash
# Lint code
uv run ruff check .

# Format code
uv run ruff format .

# Auto-fix issues
uv run ruff check --fix .

# Type checking
uv run mypy src/thoth
```

## Service Ports Reference

### Development Mode

| Service | Port | Purpose |
|---------|------|---------|
| API | 8080 | REST API (external) |
| MCP HTTP | 8082 | MCP tools (external, maps to internal 8000) |
| MCP HTTP | 8082 | MCP HTTP transport (includes /mcp POST and /sse streaming endpoints) |
| ChromaDB | 8003 | Vector DB |
| Discovery | 8004 | Discovery service |
| Letta | 8283 | Agent memory |
| PostgreSQL | 5433 | Database |

### Production Mode

| Service | Port | Purpose |
|---------|------|---------|
| API | 8080 | REST API |
| MCP SSE | 8081 | MCP streaming |
| MCP HTTP | 8082 | MCP tools |
| Letta | 8283 | Agent memory |
| Letta Nginx | 8284 | SSE proxy |

## Keyboard Shortcuts

Configure in **Obsidian Settings → Hotkeys**:

- **Open Thoth Chat**: (Set your own)
- **New Chat Session**: (Set your own)
- **Insert Research Query**: (Set your own)
- **Start Agent**: (Set your own)
- **Stop Agent**: (Set your own)

## Directory Quick Reference

```
Vault Structure:
_thoth/
├── settings.json          # Configuration
├── data/
│   ├── pdfs/             # Input PDFs
│   ├── notes/            # Generated notes
│   ├── knowledge/        # Citation graphs
│   └── prompts/          # Custom prompts
├── logs/                 # Application logs
└── cache/                # Temporary cache

Docker Volumes:
thoth-letta-data          # Letta memory
thoth-letta-postgres      # PostgreSQL data
thoth-chroma-data         # Vector embeddings
```

## Help Resources

- **Documentation**: `/docs` directory
- **Setup**: [docs/setup.md](setup.md)
- **Architecture**: [docs/architecture.md](architecture.md)
- **Usage**: [docs/usage.md](usage.md)
- **GitHub**: [github.com/acertainKnight/project-thoth](https://github.com/acertainKnight/project-thoth)
- **Issues**: [GitHub Issues](https://github.com/acertainKnight/project-thoth/issues)

## Service Access Patterns

### ServiceManager Usage

**ALWAYS use short names** when accessing services:

```python
from thoth.services.service_manager import ServiceManager

# Initialize
manager = ServiceManager()
manager.initialize()

# ✅ CORRECT - Use short names
llm = manager.llm                  # LLMService
discovery = manager.discovery      # DiscoveryService
rag = manager.rag                  # RAGService (may be None)
processing = manager.processing    # ProcessingService (may be None)
postgres = manager.postgres        # PostgresService
citation = manager.citation        # CitationService
article = manager.article          # ArticleService
note = manager.note                # NoteService
tag = manager.tag                  # TagService

# ❌ WRONG - Don't use _service suffix
llm = manager.llm_service          # AttributeError!
discovery = manager.discovery_service  # AttributeError!

# ❌ WRONG - Don't access private dict
llm = manager._services['llm']     # Bad practice!
```

**Optional Services** (may be `None` if extras not installed):
- `processing` - Requires `pdf` extras (`uv sync --extra pdf`)
- `rag` - Requires `embeddings` extras (`uv sync --extra embeddings`)
- `cache` - Requires optimization extras
- `async_processing` - Requires optimization extras

**Check before using optional services:**

```python
# Option 1: Check if None
if manager.processing is not None:
    result = manager.processing.process_pdf(path)

# Option 2: Use hasattr
if hasattr(manager, 'processing'):
    result = manager.processing.process_pdf(path)

# Option 3: Try-except
try:
    result = manager.processing.process_pdf(path)
except AttributeError:
    print("Processing service not available (install pdf extras)")
```

**IDE Autocomplete**: Type hints are provided for all services. Your IDE will show:
- Available service names
- Service types
- Whether services are optional (may be None)

---

**Pro Tip**: Bookmark this page for quick reference! Most commands support `--help` flag for detailed information.
