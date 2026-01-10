# Letta Docker Volumes - Important Information

## ⚠️ Warning: Multiple PostgreSQL Volumes

Your system has **two separate Letta PostgreSQL setups** that use different volumes:

### 1. Production Setup (RECOMMENDED)
- **Compose file**: `docker-compose.yml`
- **Volume**: `letta-postgres`
- **Container**: `letta-postgres`
- **Agents**: 12 (most recent data)
- **Start command**: `letta-start` or `docker compose -f docker-compose.yml up -d letta-postgres letta letta-redis letta-nginx`

### 2. Dev/Microservices Setup
- **Compose file**: `docker-compose.dev.yml`
- **Volume**: `thoth-dev-letta-postgres`
- **Container**: `thoth-dev-letta-postgres`
- **Agents**: 6 (older test data from Nov 2025)
- **Start command**: `docker compose -f docker-compose.dev.yml up`

## 🎯 Default Behavior

The `letta-start` alias and script have been configured to **always use production mode** to prevent accidental data loss.

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

## 📅 Last Updated
January 9, 2026 - After recovery of production agents
