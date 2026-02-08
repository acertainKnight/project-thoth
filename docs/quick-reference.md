# Thoth Quick Reference

Command cheat sheet for Thoth Research Assistant.

## Make Commands

### Development

```bash
make dev                      # Start development mode (hot-reload enabled)
make microservices            # Start dev in microservices mode (6 containers)
make dev-stop                 # Stop development services
make dev-logs                 # View development logs (follow)
make dev-status               # Check development status
make dev-thoth-restart        # Restart only Thoth (not Letta)
```

### Production

```bash
make prod                     # Start production (local mode, 1 container)
make prod-microservices       # Start production (microservices, 5 containers)
make prod-stop                # Stop production services
make prod-logs                # View production logs (follow)
make prod-status              # Check production status
make prod-restart             # Restart production server
```

### Letta Management

```bash
make letta-start              # Start Letta services (independent)
make letta-stop               # Stop Letta (WARNING: affects all projects)
make letta-restart            # Restart Letta (WARNING: affects all projects)
make letta-status             # Check Letta status
make letta-logs               # View Letta logs
```

### Thoth Management

```bash
make thoth-start              # Start Thoth (requires Letta running)
make thoth-stop               # Stop Thoth (Letta keeps running)
make thoth-restart            # Restart Thoth only
make thoth-status             # Check both Thoth and Letta status
make thoth-logs               # View Thoth logs
```

### Plugin

```bash
make deploy-plugin            # Deploy Obsidian plugin
make verify-plugin            # Verify plugin deployment
make plugin-dev               # Watch mode (auto-rebuild on changes)
```

### Utilities

```bash
make health                   # Check all services health
make reload-settings          # Manually trigger settings reload
make watch-settings           # Watch settings.json for changes
make test-hot-reload          # Test hot-reload functionality
make clean                    # Clean build artifacts
make clean-logs               # Clean old/large log files
make check-vault              # Check vault integration
make check-deps               # Check dependencies
```

---

## CLI Commands

### Setup

```bash
thoth setup                   # Interactive setup wizard
```

### Server

```bash
thoth server start            # Start API server
thoth server start --api-host 0.0.0.0 --api-port 8000
thoth server stop             # Stop API server
thoth server status           # Check server status
```

### MCP

```bash
thoth mcp start               # Start MCP server
thoth mcp start --http-port 8000
thoth mcp tools               # List all tools
thoth mcp info                # Server information
```

### Letta

```bash
thoth letta auth login        # OAuth login to Letta Cloud
thoth letta auth logout       # Logout from Letta Cloud
thoth letta auth status       # Check auth status
thoth letta setup             # Setup wizard for Letta
```

### PDF Processing

```bash
thoth pdf process <file>      # Process single PDF
thoth pdf process <dir> --parallel  # Batch process directory
thoth pdf monitor             # Monitor directory for new PDFs
thoth pdf monitor --watch-dir ./papers --recursive
```

### Discovery

```bash
thoth discovery start         # Start discovery service
thoth discovery stop          # Stop discovery service
thoth discovery search "query" --source arxiv
thoth discovery search "query" --sources arxiv semantic_scholar
thoth discovery schedule --query "ML" --cron "0 9 * * *"
thoth discovery list-sources  # List available sources
```

### Research

```bash
thoth research create "Question text"  # Create research question
thoth research list                    # List questions
thoth research get <id>                # Get question details
thoth research update <id>             # Update question
thoth research delete <id>             # Delete question
thoth research discover <id>           # Run discovery for question
```

### RAG

```bash
thoth rag build               # Build vector index
thoth rag rebuild             # Rebuild index
thoth rag search "query"      # Semantic search
thoth rag search "query" --top-k 10 --min-score 0.7
```

### Notes

```bash
thoth notes generate <pdf>    # Generate note from PDF
thoth notes list              # List generated notes
```

### Schema

```bash
thoth schema list-presets     # List analysis schema presets
thoth schema set-preset detailed  # Set active preset
thoth schema get-info         # Show current schema info
thoth schema validate         # Validate schema file
```

### Service

```bash
thoth service start <name>    # Start specific service
thoth service stop <name>     # Stop specific service
thoth service restart <name>  # Restart service
thoth service status          # Status of all services
```

### System

```bash
thoth system check            # Check system configuration
thoth system vault            # Show vault information
thoth system clear-cache      # Clear application cache
thoth system migrate          # Run migrations
```

### Database

```bash
thoth database init           # Initialize database
thoth database migrate        # Run migrations
thoth database reset          # Reset database (WARNING: deletes data)
```

### Performance

```bash
thoth performance analyze     # Analyze system performance
thoth performance benchmark   # Run benchmarks
```

---

## Agent Commands (via Chat)

### Discovery

```
"Find papers on [topic]"
"Search ArXiv for [query]"
"Discover papers published in 2024 about [topic]"
```

### Q&A

```
"What papers discuss [topic]?"
"Summarize the paper [title]"
"What are the key findings in [paper]?"
```

### Analysis

```
"Compare these two papers: [paper1] and [paper2]"
"Analyze the methodology in [paper]"
"Evaluate the quality of [paper]"
```

### Citation

```
"Extract citations from [paper]"
"Enrich citations with DOIs"
"Find papers that cite [paper]"
"Show citation network for [paper]"
```

### Skills

```
"What skills are available?"
"Load the deep-research skill"
"Unload the paper-discovery skill"
```

### Settings

```
"Change the default model to Claude 3.5 Sonnet"
"Show current LLM configuration"
"Update discovery max articles to 100"
```

---

## API Endpoints

### Health

```bash
curl http://localhost:8000/health
curl http://localhost:8082/health
curl http://localhost:8283/v1/health
```

### MCP Protocol

```bash
# List tools
curl -X POST http://localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}'

# Call tool
curl -X POST http://localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "search_articles",
      "arguments": {"query": "transformers", "max_results": 10}
    },
    "id": 1
  }'
```

### Letta API

```bash
# List agents
curl http://localhost:8283/v1/agents

# Get agent
curl http://localhost:8283/v1/agents/{agent_id}

# Send message
curl -X POST http://localhost:8283/v1/agents/{agent_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "text": "Hello"}]}'

# Get memory blocks
curl http://localhost:8283/v1/agents/{agent_id}/memory
```

---

## Configuration

### Environment Variables

```bash
# Required
export OBSIDIAN_VAULT_PATH="/path/to/vault"
export API_MISTRAL_KEY="your_key"
export API_OPENROUTER_KEY="your_key"

# Optional
export API_OPENAI_KEY="your_key"
export API_SEMANTIC_SCHOLAR_KEY="your_key"
```

### Settings File

**Location**: `$OBSIDIAN_VAULT_PATH/thoth/_thoth/settings.json`

**Hot-reload**: Changes apply in ~2 seconds (dev mode)

**Common settings**:
```json
{
  "llm_config": {
    "default": {"model": "mistral/mistral-large-latest", "temperature": 0.7}
  },
  "discovery": {"default_max_articles": 50},
  "processing": {"generate_tags": true, "enrich_citations": true},
  "memory": {"letta": {"mode": "self-hosted"}}
}
```

---

## Service Ports

### Development Mode

| Service | Port | Access |
|---------|------|--------|
| API | 8000 | http://localhost:8000 |
| MCP | 8082 | http://localhost:8082 (internal: 8000 with /mcp and /sse) |
| Letta | 8283 | http://localhost:8283 |
| PostgreSQL | 5433 | localhost:5433 |

### Production Mode

| Service | Port | Access |
|---------|------|--------|
| API | 8080 | http://localhost:8080 |
| MCP | 8082 | http://localhost:8082 |
| Letta | 8283 | http://localhost:8283 |
| Letta SSE | 8284 | http://localhost:8284 |

---

## Troubleshooting Quick Fixes

```bash
# Service not responding
docker restart thoth-dev-api

# Check logs for errors
docker logs thoth-dev-api --tail 100 | grep ERROR

# Clear cache
rm -rf $OBSIDIAN_VAULT_PATH/thoth/_thoth/cache/*

# Rebuild index
python -m thoth rag rebuild

# Reset to clean state (WARNING: loses data)
make dev-stop && make clean && make dev
```

---

## Getting Help

- **Full Documentation**: [docs/](.)
- **Setup Guide**: [setup.md](setup.md)
- **Usage Guide**: [usage.md](usage.md)
- **Architecture**: [architecture.md](architecture.md)
- **GitHub Issues**: [github.com/acertainKnight/project-thoth/issues](https://github.com/acertainKnight/project-thoth/issues)

---

**Pro Tip**: Use `--help` flag on any command for detailed options!

**Last Updated**: February 2026
