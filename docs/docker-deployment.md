# Thoth Docker Deployment Guide

Complete guide to deploying Thoth using Docker with both local and microservices architectures.

## Table of Contents

- [Overview](#overview)
- [Deployment Modes](#deployment-modes)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)
- [Migration Guide](#migration-guide)
- [Advanced Topics](#advanced-topics)

## Overview

Thoth offers two deployment architectures to suit different use cases:

### Local Mode (Default) ⭐
**Best for:** Personal use, laptops, small self-hosted deployments

> **📘 Letta Setup**: Letta runs as a standalone service. See [LETTA_SETUP.md](./LETTA_SETUP.md) for details.

- **Containers:** 5 (thoth-all-in-one, letta-server, letta-postgres, letta-redis, letta-nginx)
- **Resource Usage:** ~3.5GB RAM
- **Startup Time:** ~30 seconds (Letta auto-starts if needed)
- **Management:** Simple, one unified Thoth container + standalone Letta
- **Services:** API, MCP, Discovery, PDF Monitor (all in one container)

### Microservices Mode
**Best for:** Debugging, development, service isolation

- **Containers:** 6-7 (separate for each service)
- **Resource Usage:** ~4.5-5GB RAM
- **Startup Time:** ~60 seconds
- **Management:** Independent service control
- **Services:** Each service in its own container

## Deployment Modes

### Architecture Comparison

| Feature | Local Mode | Microservices Mode |
|---------|-----------|-------------------|
| **Total Containers** | 3 | 6-7 |
| **Thoth Services** | All-in-one | Separate containers |
| **Memory Usage** | ~3.5GB | ~4.5-5GB |
| **Startup Time** | ~30s | ~60s |
| **Service Restart** | Restart all | Restart individual |
| **Debugging** | View supervisor logs | View per-service logs |
| **Resource Efficiency** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Scalability** | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| **Simplicity** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |

### When to Use Each Mode

**Use Local Mode when:**
- Running on a personal laptop
- Limited resources (< 8GB RAM)
- Simple deployment preferred
- Don't need to debug individual services
- Small self-hosted setup

**Use Microservices Mode when:**
- Debugging specific service issues
- Need to scale individual services
- Want independent service control
- Have resources to spare (8GB+ RAM)
- Production deployment with multiple replicas

## Prerequisites

### System Requirements

- **Docker:** 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- **Docker Compose:** 2.0+ (included with Docker Desktop)
- **RAM:** Minimum 4GB available, 8GB recommended
- **Disk:** ~5GB for images and data
- **Ports:** 8000, 8082, 8283, 5432/5433 must be available

### Software

```bash
# Verify Docker installation
docker --version
docker compose version

# Check available resources
docker info | grep -E 'CPUs|Total Memory'
```

### Required Files

1. **Obsidian Vault:** Path to your Obsidian vault with Thoth integration
2. **API Keys:** OpenAI, Anthropic, Mistral, etc. (in `.env` file)
3. **Settings:** `vault/_thoth/settings.json` configured

## Quick Start

### Local Mode (Recommended)

```bash
# 1. Set your vault path
export OBSIDIAN_VAULT_PATH="/path/to/your/vault"
# OR create .env.vault file:
echo "OBSIDIAN_VAULT_PATH=/path/to/your/vault" > .env.vault

# 2. Start Thoth (local mode is default)
make dev

# 3. Check health
make health

# 4. View logs
docker logs -f thoth-dev-all-in-one

# 5. Stop when done
make dev-stop
```

**Services Available:**
- API Server: http://localhost:8080
- MCP Server (HTTP): http://localhost:8082
- MCP Server (SSE): http://localhost:8081
- Letta Memory: http://localhost:8283

### Microservices Mode

```bash
# 1. Set your vault path (same as above)
export OBSIDIAN_VAULT_PATH="/path/to/your/vault"

# 2. Start in microservices mode
make microservices

# 3. Check health
make health

# 4. View individual service logs
docker logs -f thoth-dev-api
docker logs -f thoth-dev-mcp
docker logs -f thoth-dev-discovery
docker logs -f thoth-dev-pdf-monitor

# 5. Stop when done
make dev-stop
```

### Production Deployment

```bash
# Local mode (recommended for small deployments)
make prod

# Microservices mode (for scaling)
make prod-microservices

# Check status
make prod-status

# Stop
make prod-stop
```

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# API Keys (Required)
OPENAI_API_KEY=sk-...           # Embeddings (Thoth RAG + Letta memory)
API_OPENROUTER_KEY=...          # Backend LLM (analysis, queries, routing)
API_MISTRAL_KEY=...             # PDF OCR extraction

# Vault Path (Required)
OBSIDIAN_VAULT_PATH=/path/to/vault

# API Keys (Optional)
ANTHROPIC_API_KEY=sk-ant-...    # Direct Anthropic access
API_SEMANTIC_SCHOLAR_KEY=...
API_WEB_SEARCH_KEY=...

# Optional: Development
THOTH_LOG_LEVEL=DEBUG
THOTH_HOT_RELOAD=1
```

### Settings.json

Configure Thoth in `vault/_thoth/settings.json`:

```json
{
  "version": "1.0.0",
  "paths": {
    "workspace": "/path/to/vault/_thoth",
    "vault": "/path/to/vault"
  },
  "apiKeys": {
    "openaiKey": "",
    "anthropicKey": "",
    "mistralKey": "",
    "openrouterKey": ""
  },
  "servers": {
    "api": {
      "host": "0.0.0.0",
      "port": 8000,
      "autoStart": true
    },
    "mcp": {
      "host": "0.0.0.0",
      "httpPort": 8000,
      "httpPort": 8000,
      "autoStart": true,
      "enabled": true
    }
  },
  "llm": {
    "primaryProvider": "openai",
    "models": {
      "default": "gpt-4-turbo-preview",
      "analysis": "gpt-4-turbo-preview"
    }
  }
}
```

### Port Mapping

#### Development (Local Mode)
- `8080` → API Server (internal 8000)
- `8082` → MCP Server (internal 8000 - includes /mcp POST and /sse streaming)
- `8082` → MCP HTTP transport (internal 8000 - includes /mcp and /sse endpoints)
- `8283` → Letta Memory
- `5432` → PostgreSQL (shared with Letta)

#### Production (Local Mode)
- `8080` → API Server (internal 8000)
- `8082` → MCP Server (internal 8000 - includes /mcp POST and /sse streaming)
- `8081` → MCP SSE-only transport (internal 8001 - not used by Letta)
- `8283` → Letta Memory

#### Microservices Mode (same ports as local)

### Customizing Services

#### Local Mode - Disable Services

To disable specific services in local mode, edit `docker/supervisor/supervisord.conf`:

```ini
# Disable discovery by setting autostart=false
[program:thoth-discovery]
autostart=false
...
```

Then rebuild:
```bash
make dev-stop
docker compose -f docker-compose.dev.yml build thoth-all-in-one
make dev
```

#### Microservices Mode - Select Services

```bash
# Start only specific services
docker compose -f docker-compose.dev.yml --profile microservices up thoth-api thoth-mcp letta letta-postgres
```

## Common Workflows

### Daily Development

```bash
# Start in local mode
make dev

# Work on code with hot-reload enabled
# Changes to settings.json auto-reload

# View logs
docker exec thoth-dev-all-in-one supervisorctl tail -f thoth-api

# Restart if needed
docker restart thoth-dev-all-in-one

# Stop at end of day
make dev-stop
```

### Debugging Individual Services

```bash
# Switch to microservices mode for easier debugging
make dev-stop
make microservices

# Debug specific service
docker logs -f thoth-dev-api

# Restart just one service
docker restart thoth-dev-api

# Switch back to local mode
make dev-stop
make dev
```

### Testing Changes

```bash
# Start fresh
make dev-stop
docker system prune -f

# Build and start
make dev

# Run tests
pytest tests/

# Check health
make health
```

### Updating Thoth

```bash
# Pull latest changes
git pull origin main

# Rebuild containers
make dev-stop
docker compose -f docker-compose.dev.yml build --no-cache

# Start fresh
make dev
```

### Processing PDFs

```bash
# Ensure PDF monitor is running
docker exec thoth-dev-all-in-one supervisorctl status thoth-pdf-monitor

# Add PDFs to watch directory
cp paper.pdf $OBSIDIAN_VAULT_PATH/_thoth/data/pdfs/

# Monitor processing logs
docker exec thoth-dev-all-in-one tail -f /vault/_thoth/logs/monitor-stdout.log
```

### Backing Up Data

```bash
# Backup volumes
docker run --rm -v letta-postgres:/data -v $(pwd):/backup alpine tar czf /backup/postgres-backup.tar.gz /data
docker run --rm -v letta-data:/data -v $(pwd):/backup alpine tar czf /backup/letta-backup.tar.gz /data

# Backup vault (separate from Docker)
tar czf vault-backup.tar.gz $OBSIDIAN_VAULT_PATH/_thoth/
```

## Troubleshooting

### Services Won't Start

**Problem:** Containers fail to start

**Solutions:**
```bash
# Check logs
docker logs thoth-dev-all-in-one

# Check supervisor status
docker exec thoth-dev-all-in-one supervisorctl status

# Verify vault path
echo $OBSIDIAN_VAULT_PATH
ls $OBSIDIAN_VAULT_PATH/_thoth/settings.json

# Rebuild
make dev-stop
docker compose -f docker-compose.dev.yml build --no-cache
make dev
```

### Health Checks Failing

**Problem:** `make health` shows services as down

**Solutions:**
```bash
# Wait for startup (can take 60s)
sleep 60 && make health

# Check if containers are running
docker ps | grep thoth

# Check service logs
docker logs thoth-dev-all-in-one 2>&1 | tail -50

# Verify ports
netstat -tulpn | grep -E '8000|8082|8283'
```

### Memory Issues

**Problem:** Out of memory errors

**Solutions:**
```bash
# Check current usage
docker stats --no-stream

# Increase Docker memory limit (Docker Desktop)
# Settings → Resources → Memory → Set to 8GB+

# Use local mode instead of microservices
make dev-stop
make dev

# Clean up unused images
docker image prune -a
```

### Port Conflicts

**Problem:** Port already in use

**Solutions:**
```bash
# Find process using port
lsof -i :8000
# OR
netstat -tulpn | grep 8000

# Kill process or change Thoth ports in docker-compose.yml
# Example: Change "8000:8000" to "8010:8000"
```

### Data Not Persisting

**Problem:** Data lost after restart

**Solutions:**
```bash
# Check volumes exist
docker volume ls | grep thoth

# Verify vault mount
docker exec thoth-dev-all-in-one ls /vault/_thoth

# Check volume permissions
docker exec thoth-dev-all-in-one ls -la /vault/_thoth
```

### Switching Modes Fails

**Problem:** Can't switch between local/microservices

**Solutions:**
```bash
# Complete shutdown both profiles
docker compose -f docker-compose.dev.yml --profile microservices down
docker ps -a | grep thoth | awk '{print $1}' | xargs docker rm -f

# Clean start
make dev  # or make microservices
```

### Supervisor Issues

**Problem:** Services not running in unified container

**Solutions:**
```bash
# Check supervisor
docker exec thoth-dev-all-in-one supervisorctl status

# Restart supervisor
docker restart thoth-dev-all-in-one

# View supervisor logs
docker exec thoth-dev-all-in-one cat /vault/_thoth/logs/supervisord.log

# Manually start service
docker exec thoth-dev-all-in-one supervisorctl start thoth-api
```

## Migration Guide

### From Old Architecture

**What Changed:**
- ChromaDB removed (use PostgreSQL+pgvector)
- Default is now unified container (3 containers vs 7)
- New Makefile targets

**Migration Steps:**

```bash
# 1. Stop old deployment
docker compose down

# 2. Pull latest code
git checkout main
git pull origin main

# 3. Export any ChromaDB data (if needed)
# Note: Most users didn't use ChromaDB, only PostgreSQL

# 4. Start with new architecture
make dev

# 5. Verify everything works
make health
```

**Breaking Changes:**
- `make dev` now uses local mode (was microservices)
- ChromaDB service removed
- `THOTH_CHROMADB_URL` environment variable removed

### From ChromaDB to PostgreSQL

If you were using ChromaDB:

1. All vector storage now uses PostgreSQL+pgvector
2. No data migration needed (embeddings regenerate automatically)
3. Better performance and reliability with PostgreSQL

## Advanced Topics

### Custom Supervisor Configuration

Edit `docker/supervisor/supervisord.conf` to customize services:

```ini
# Example: Increase retry count
[program:thoth-api]
startretries=10  # Default is 3

# Example: Change log levels
stdout_logfile_maxbytes=50MB  # Default is 10MB
```

Rebuild after changes:
```bash
docker compose -f docker-compose.dev.yml build thoth-all-in-one
```

### Resource Limits

Adjust in `docker-compose.yml`:

```yaml
thoth-all-in-one:
  deploy:
    resources:
      limits:
        memory: 4G    # Adjust as needed
        cpus: '2.0'   # Adjust as needed
```

### Network Configuration

Custom network settings in `docker-compose.yml`:

```yaml
networks:
  thoth-dev-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.21.0.0/16
```

### Production Best Practices

1. **Use Production Mode:** `make prod` (not `make dev`)
2. **Set Resource Limits:** Configure memory/CPU limits
3. **Enable HTTPS:** Use Nginx or Caddy reverse proxy
4. **Backup Regularly:** Automate volume and vault backups
5. **Monitor Resources:** Use Prometheus + Grafana
6. **Log Management:** Configure log rotation
7. **Security:** Keep API keys secret, use environment variables

### CI/CD Integration

```yaml
# Example GitHub Actions workflow
- name: Test Docker Deployment
  run: |
    export OBSIDIAN_VAULT_PATH=/tmp/test-vault
    mkdir -p /tmp/test-vault/_thoth
    make dev
    make health
    make dev-stop
```

## Support and Resources

- **Documentation:** `/docs` directory
- **Issues:** https://github.com/acertainKnight/project-thoth/issues
- **Testing:** See `TESTING_DOCKER_MODES.md`
- **Architecture:** See project memory blocks in Letta Code

## Appendix

### Complete Command Reference

```bash
# Development - Local Mode
make dev                # Start local mode (default)
make dev-status         # Check status
make dev-logs           # View logs
make dev-stop           # Stop services

# Development - Microservices
make microservices      # Start microservices mode

# Production
make prod               # Production local mode
make prod-microservices # Production microservices
make prod-status        # Check status
make prod-logs          # View logs
make prod-stop          # Stop production

# Utilities
make health             # Health check all services
make test-config        # Test configuration
make deploy-plugin      # Deploy Obsidian plugin
```

### File Locations

- **Source Code:** `/src/thoth`
- **Docker Files:** `/docker`
- **Compose Files:** `docker-compose.yml`, `docker-compose.dev.yml`
- **Supervisor Config:** `/docker/supervisor/supervisord.conf`
- **Unified Dockerfile:** `/docker/all-in-one/Dockerfile`
- **Service Dockerfiles:** `/docker/{api,mcp,discovery,pdf-monitor}/Dockerfile`
- **Documentation:** `/docs`
- **Vault Data:** `$OBSIDIAN_VAULT_PATH/_thoth`
- **Logs:** `$OBSIDIAN_VAULT_PATH/_thoth/logs`
