# Letta Memory System Setup

Letta is Thoth's memory and agent management system. It runs as a standalone service shared across all your projects.

## Overview

Letta provides:
- **Agent Storage**: All your AI agents and their configurations
- **Memory Management**: Long-term memory for conversations
- **PostgreSQL + pgvector**: Vector search for semantic memory
- **Streaming**: Real-time updates via Redis and Nginx

## Architecture

```
Standalone Letta Stack (docker-compose.letta.yml)
├── letta-postgres (port 5432) - Database with pgvector
├── letta-server (port 8283) - Main API server
├── letta-redis (port 6379) - Streaming and jobs
└── letta-nginx (port 8284) - SSE proxy

Thoth Services (docker-compose.dev.yml)
└── thoth-all-in-one → Connects to Letta via network
```

## Starting Letta

### First-Time Setup (Automatic)

For new users cloning the repository:

```bash
make dev  # Automatically sets up and starts Letta
```

**What happens on first run:**
1. Creates `.env.letta` from `.env.letta.example` (if missing)
2. Checks if Letta is running
3. Prompts to start Letta if not running
4. Starts Letta with `docker compose -f docker-compose.letta.yml up -d`
5. Waits for Letta to be healthy
6. Connects Thoth services to Letta

**No manual configuration needed!** The default `.env.letta` works out of the box.

### Subsequent Runs (Automatic)

After the first setup, `make dev` will:
1. Check if Letta is running
2. Start Letta if stopped (with your permission)
3. Connect Thoth services to Letta

Your agents and data persist across all restarts!

### Manual Start
```bash
# Start Letta
make letta-start

# Check status
make letta-status

# View logs
make letta-logs
```

## Managing Letta

### Common Commands
```bash
# Start standalone Letta
make letta-start
docker compose -f docker-compose.letta.yml up -d

# Stop Letta (WARNING: affects all projects)
make letta-stop
docker compose -f docker-compose.letta.yml stop

# Restart Letta
make letta-restart

# Check health
make letta-status
curl http://localhost:8283/v1/health
```

### Viewing Agents
```bash
# List all agents (via database)
docker exec letta-postgres psql -U letta -d letta -c \
  "SELECT id, name, created_at FROM agents ORDER BY created_at DESC;"

# Count agents
docker exec letta-postgres psql -U letta -d letta -c \
  "SELECT COUNT(*) as total_agents FROM agents;"

# Via Letta API (requires auth)
curl http://localhost:8283/v1/agents
```

## Configuration

### Environment Variables (.env.letta)

On first run, `.env.letta` is automatically created from `.env.letta.example` with sensible defaults:

```bash
# Server settings (defaults work out of the box)
LETTA_SERVER_HOST=0.0.0.0
LETTA_SERVER_PORT=8283
LETTA_SERVER_PASSWORD=letta_dev_password

# Database connection (automatic in Docker)
LETTA_PG_URI=postgresql://letta:letta_password@letta-postgres:5432/letta

# LLM API keys (optional - add your keys to enable LLM features)
OPENAI_API_KEY=  # Leave empty for now, add later
ANTHROPIC_API_KEY=  # Leave empty for now, add later
GROQ_API_KEY=  # Leave empty for now, add later
```

**For new users:** Letta works without API keys. Add them later when you need LLM features.

### CORS Configuration
Add your application URLs to `LETTA_SERVER_CORS_ORIGINS` in `.env.letta`:
```bash
LETTA_SERVER_CORS_ORIGINS=http://localhost:8283,https://your-domain.com
```

## Data Persistence

All data is stored in Docker volumes that persist across container restarts:

```bash
# View all Letta volumes
docker volume ls | grep letta

# Output:
# letta-postgres - PostgreSQL database (agents, memory)
# letta-data - Persistent data directory
# letta-home - Letta home directory
```

### Backing Up Data
```bash
# Create backup
docker run --rm \
  -v letta-postgres:/source \
  -v $(pwd):/backup \
  alpine tar czf /backup/letta-backup-$(date +%Y%m%d).tar.gz -C /source .

# Restore backup
docker run --rm \
  -v letta-postgres:/target \
  -v $(pwd):/backup \
  alpine tar xzf /backup/letta-backup-20260116.tar.gz -C /target
```

## Network Connectivity

Thoth services connect to Letta via Docker networks:

```yaml
# In docker-compose.dev.yml
networks:
  - letta-network  # External network from docker-compose.letta.yml

external_links:
  - letta-server:letta
  - letta-postgres:letta-postgres
```

### Access URLs
- **From Thoth containers**: `http://letta-server:8283`
- **From host machine**: `http://localhost:8283`
- **SSE Proxy**: `http://localhost:8284`
- **Database**: `localhost:5432` (credentials in .env.letta)

## Ports

| Service | Port | Purpose |
|---------|------|---------|
| letta-server | 8283 | Main API |
| letta-nginx | 8284 | SSE streaming proxy |
| letta-postgres | 5432 | PostgreSQL database |
| letta-redis | 6379 | Redis (internal only) |

## Health Checks

Letta includes built-in health checks:

```bash
# Check via API
curl http://localhost:8283/v1/health

# Check container health
docker ps --filter "name=letta-server"

# View health check logs
docker inspect letta-server | jq '.[0].State.Health'
```

## Troubleshooting

### Letta Not Responding
```bash
# Check if running
docker ps | grep letta-server

# View logs
docker logs letta-server --tail 50

# Restart Letta
make letta-restart
```

### Port Conflicts
```bash
# Check what's using port 5432
sudo lsof -i :5432

# If system PostgreSQL is running, stop it or use different port
sudo systemctl stop postgresql
```

### Connection Issues from Thoth
```bash
# Verify networks
docker network ls | grep letta

# Check if thoth container is on letta network
docker inspect thoth-dev-all-in-one | jq '.[0].NetworkSettings.Networks'

# Should show both "thoth-dev-network" and "letta-network"
```

## Multi-Project Usage

Letta is designed to be shared across multiple projects:

- **Each project** can have its own organization/workspace in Letta
- **Agents are isolated** by organization ID
- **Database is shared** but data is partitioned
- **Be careful** when stopping Letta - it affects all projects

### Best Practices
1. Always use `make letta-start` to ensure Letta is running
2. Don't stop Letta unless you're sure no other projects are using it
3. Use organizations to isolate project data
4. Keep Letta running continuously in the background

## Advanced Configuration

### Custom PostgreSQL Settings
Edit `docker-compose.letta.yml`:
```yaml
letta-postgres:
  environment:
    - POSTGRES_MAX_CONNECTIONS=200
    - POSTGRES_SHARED_BUFFERS=256MB
```

### Custom Letta Settings
Edit `.env.letta` for additional configuration options.

### Tool Execution Sandbox
```bash
# E2B sandbox for secure tool execution
E2B_API_KEY=your_key_here
E2B_SANDBOX_TEMPLATE_ID=your_template_id
```

## See Also

- [LETTA_ARCHITECTURE.md](./LETTA_ARCHITECTURE.md) - Detailed architecture documentation
- [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md) - Docker deployment guide
- [setup.md](./setup.md) - Initial setup instructions
