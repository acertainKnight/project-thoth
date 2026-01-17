# Letta Docker Volumes - Important Information

> **📘 See Also**: [LETTA_ARCHITECTURE.md](./LETTA_ARCHITECTURE.md) for the complete architecture documentation including safeguards and usage patterns.

## ✅ Current Architecture (January 2026)

Letta is now a **standalone shared service** that prevents accidental data loss from `make dev`:

### Standalone Letta Setup (RECOMMENDED ✅)
- **Compose file**: `docker-compose.letta.yml`
- **Volume**: `letta-postgres` (14 agents preserved)
- **Container**: `letta-server`, `letta-postgres`
- **Start command**: `make letta-start` or `docker compose -f docker-compose.letta.yml up -d`
- **Safeguard**: Automatically checked by `make dev`

### Thoth Dev Environment
- **Compose file**: `docker-compose.dev.yml`
- **Behavior**: Connects to standalone Letta (no longer starts its own)
- **Start command**: `make dev` (automatically checks and starts Letta if needed)
- **Old volumes**: `thoth-dev-letta-postgres` (deprecated, no longer used)

## 🎯 Default Behavior

The `make dev` command now:
1. ✅ Checks if standalone Letta is running
2. ✅ Offers to start Letta if not running
3. ✅ Connects to standalone Letta (never starts its own)
4. ✅ Preserves all agents across restarts

## 📊 Check Which Volume is Active

```bash
# See which containers are running
docker ps --filter "name=letta"

# Check which volume a container is using
docker inspect letta-postgres --format '{{range .Mounts}}{{.Name}}{{"\n"}}{{end}}'

# Should output: letta-postgres (for production)
```

## 🔍 Verify Your Agents

```bash
# Count agents in production database
docker exec letta-postgres psql -U letta -d letta -c "SELECT COUNT(*) FROM agents;"

# List all agents
docker exec letta-postgres psql -U letta -d letta -c "SELECT id, name, created_at FROM agents ORDER BY created_at DESC;"
```

## 🛡️ Safety Tips

1. **Always use** `letta-start` to start services (uses production by default)
2. **Avoid** running `docker compose up` without specifying the compose file
3. **Check** which volume is mounted if agents seem to disappear
4. **Backup** your volumes regularly:
   ```bash
   docker run --rm -v letta-postgres:/source -v $(pwd):/backup alpine tar czf /backup/letta-backup-$(date +%Y%m%d).tar.gz -C /source .
   ```

## 🔄 Switching Between Modes

### To Production Mode (Your Main Data):
```bash
docker compose -f docker-compose.dev.yml down  # Stop dev
docker compose -f docker-compose.yml up -d letta-postgres letta-redis letta letta-nginx
```

### To Dev Mode (For Testing):
```bash
docker compose -f docker-compose.yml down  # Stop production
docker compose -f docker-compose.dev.yml up -d
```

## 💾 Volume Locations

All volumes are stored in Docker's volume directory:
```bash
# List all Letta volumes
docker volume ls | grep letta

# Inspect volume details
docker volume inspect letta-postgres
```

## 🔄 Migration Complete (January 16, 2026)

**What Changed:**
- ✅ Letta is now standalone (docker-compose.letta.yml)
- ✅ `make dev` no longer starts its own Letta
- ✅ Automatic safeguards prevent duplicate instances
- ✅ All 14 agents preserved and accessible
- ✅ `scripts/check-letta.sh` verifies Letta before starting

**Breaking Changes:**
- `docker compose up` (without `-f docker-compose.dev.yml`) is deprecated
- `thoth-dev-letta` containers are no longer used
- Must use `make dev` or manually start Letta first

## 📚 Additional Documentation

- **Architecture**: [LETTA_ARCHITECTURE.md](./LETTA_ARCHITECTURE.md) - Complete architectural overview
- **Setup**: [setup.md](./setup.md) - Installation and configuration
- **Docker Deployment**: [DOCKER_DEPLOYMENT.md](./DOCKER_DEPLOYMENT.md) - Docker-specific guidance

## 📅 Last Updated
January 16, 2026 - After migration to standalone Letta architecture
