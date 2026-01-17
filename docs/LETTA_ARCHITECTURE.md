# Letta Architecture - Shared Service Design

## 🎯 Overview

Letta is now a **shared, independent service** that runs separately from Thoth. This prevents the issue where `make dev` would start a new Letta instance with an empty database, causing your agents to "disappear".

## 🏗️ Architecture

### Before (❌ Problem)
```
make dev → docker-compose.dev.yml
    ├── thoth-dev-letta (NEW, EMPTY database)
    ├── thoth-dev-letta-postgres (NEW, EMPTY database)
    └── Your agents were in the OLD standalone Letta

Result: Agents appeared to be gone!
```

### After (✅ Solution)
```
Standalone Letta (docker-compose.letta.yml)
    ├── letta-server (persistent, shared)
    ├── letta-postgres (persistent, shared)
    ├── letta-redis (persistent, shared)
    └── letta-nginx (persistent, shared)

make dev → docker-compose.dev.yml
    ├── thoth-all-in-one
    │   └── Connects to standalone Letta via external network
    └── No Letta services (uses external)

Result: All agents preserved across restarts!
```

## 📋 Services

### Standalone Letta Stack
Managed by `docker-compose.letta.yml`:

1. **letta-postgres** (port 5432)
   - PostgreSQL with pgvector extension
   - Stores all agent data, conversations, and memory
   - Volume: `letta-postgres` (persistent)

2. **letta-server** (port 8283)
   - Main Letta API server
   - Connects to letta-postgres
   - Volume: `letta-data`, `letta-home` (persistent)

3. **letta-redis** (port 6379)
   - Required for streaming and job queuing

4. **letta-nginx** (port 8284)
   - Optimized SSE proxy for streaming

### Thoth Services
Managed by `docker-compose.dev.yml`:

- **thoth-all-in-one** (default)
  - API, MCP, Discovery, PDF Monitor
  - Connects to standalone Letta via `external_links`
  - Uses `letta-network` to communicate

## 🔒 Safeguards

### 1. Pre-flight Check Script
**Location**: `scripts/check-letta.sh`

Automatically runs before `make dev` and `make microservices`:
- ✅ Checks if Letta is running
- ✅ Offers to start Letta if not running
- ✅ Verifies API accessibility
- ✅ Prevents starting duplicate instances

### 2. Docker Compose Configuration
**Changes in `docker-compose.dev.yml`**:

```yaml
# Letta services are now commented out and moved to profiles
# Only start with --profile dev-letta (for testing)
letta:
  profiles: ["dev-letta"]  # Won't start by default
  # ... commented out

# Thoth services connect to external Letta
thoth-all-in-one:
  networks:
    - thoth-dev-network
    - letta-network  # External network
  external_links:
    - letta-server:letta
    - letta-postgres:letta-postgres
```

### 3. Makefile Integration
**Updated commands**:

```makefile
dev: ## Start development environment
    @bash scripts/check-letta.sh || exit 1  # Pre-flight check
    @docker compose -f docker-compose.dev.yml up -d

microservices: ## Start microservices mode
    @bash scripts/check-letta.sh || exit 1  # Pre-flight check
    @docker compose -f docker-compose.dev.yml --profile microservices up -d
```

## 📚 Usage

### Starting Services

#### Option 1: Automatic (Recommended)
```bash
make dev  # Automatically checks and starts Letta if needed
```

#### Option 2: Manual Control
```bash
# Start Letta first
make letta-start
# or
docker compose -f docker-compose.letta.yml up -d

# Then start Thoth
make dev
```

### Checking Letta Status
```bash
# Check if Letta is running
docker ps | grep letta

# Check Letta API
curl http://localhost:8283/v1/health

# List your agents (via database)
docker exec letta-postgres psql -U letta -d letta -c "SELECT id, name FROM agents;"

# Check with script
bash scripts/check-letta.sh
```

### Managing Letta

```bash
# Start standalone Letta
make letta-start

# Stop Letta (WARNING: affects ALL projects)
make letta-stop

# Check status
make letta-status

# View logs
make letta-logs

# Restart Letta
make letta-restart
```

## ⚠️ Important Notes

### 1. Letta is Shared
Letta can be used by **multiple projects**, not just Thoth. Be careful when stopping or restarting Letta as it may affect other projects.

### 2. Port Conflicts
- **5432**: letta-postgres (standalone)
- **5433**: thoth-dev-letta-postgres (only if using --profile dev-letta)
- **8283**: letta-server (main API)
- **8284**: letta-nginx (SSE proxy)

### 3. Data Persistence
All agent data is stored in Docker volumes:
- `letta-postgres`: PostgreSQL database
- `letta-data`: Letta persistent data
- `letta-home`: Letta home directory

**These volumes persist even if containers are stopped/removed.**

### 4. Network Connectivity
Thoth services connect to Letta via:
- **Network**: `letta-network` (172.22.0.0/16)
- **DNS**: `letta-server`, `letta-postgres`
- **Environment**: `THOTH_LETTA_URL=http://letta-server:8283`

## 🐛 Troubleshooting

### Problem: "No agents found"
```bash
# Check which Letta is running
docker ps | grep letta

# If thoth-dev-letta is running, stop it
docker stop thoth-dev-letta thoth-dev-letta-postgres
docker rm thoth-dev-letta thoth-dev-letta-postgres

# Start standalone Letta
make letta-start
```

### Problem: "Connection refused to Letta"
```bash
# Check Letta is running
docker ps | grep letta-server

# Check health
docker inspect letta-server | jq '.[0].State.Health.Status'

# View logs
docker logs letta-server --tail 50
```

### Problem: "Port already in use"
```bash
# Check what's using port 5432
sudo lsof -i :5432

# If system PostgreSQL is running, use different port
# Standalone Letta uses 5432 by default
```

## 🔄 Migration Path

If you have existing agents in the old `thoth-dev-letta-postgres` volume:

```bash
# 1. Export agents from old database
docker run --rm -v thoth-dev-letta-postgres:/old \
  -v letta-postgres:/new pgvector/pgvector:pg15 \
  bash -c "pg_dump -U letta -d letta | psql -U letta -d letta"

# 2. Or manually recreate agents via Letta API
```

## ✅ Summary

**Benefits**:
- ✅ Agents persist across `make dev` restarts
- ✅ Letta can be shared across multiple projects
- ✅ Automatic safeguards prevent duplicate instances
- ✅ Clear separation of concerns

**Trade-offs**:
- Letta must be started separately (but automated by `make dev`)
- Stopping Letta affects all projects using it
- Slightly more complex setup (but better architecture)
