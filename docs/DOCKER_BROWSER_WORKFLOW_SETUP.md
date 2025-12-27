# Docker Setup for Browser Workflow System

**Date**: 2025-12-26
**Status**: ✅ Complete

---

## Overview

The browser workflow system has been fully integrated into the Docker setup with:
- ✅ Playwright and Chromium browser installation
- ✅ Automatic database migration on startup
- ✅ Thoth database creation alongside Letta
- ✅ All browser dependencies included
- ✅ Production-ready configuration

---

## What Was Added

### 1. PostgreSQL Database Setup

**File**: `docker/postgres/init-databases.sh`

Creates both `letta` and `thoth` databases on PostgreSQL startup:
- Creates `thoth` user and database
- Creates `letta` user and database
- Installs `uuid-ossp` and `vector` extensions
- Sets up proper permissions

**Updated**: `docker-compose.yml`
- PostgreSQL healthcheck now verifies both databases
- Init scripts run in order: `01-init-databases.sh`, `02-init-vector.sql`

### 2. Browser Dependencies (Playwright)

**Updated Files**:
- `Dockerfile` (main)
- `docker/api/Dockerfile`
- `docker/mcp/Dockerfile`

**Added Dependencies**:
```dockerfile
# Playwright browser dependencies
libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0
libcups2 libdrm2 libdbus-1-3 libxkbcommon0
libxcomposite1 libxdamage1 libxfixes3 libxrandr2
libgbm1 libpango-1.0-0 libcairo2 libasound2
libatspi2.0-0 libxshmfence1
```

**Playwright Installation**:
```dockerfile
# Install Playwright browsers (run as thoth user)
RUN /app/.venv/bin/playwright install --with-deps chromium
```

### 3. Automatic Migration on Startup

**File**: `docker/entrypoint.sh`

Runs before the main service starts:
1. Waits for PostgreSQL to be ready
2. Runs browser workflow migration
3. Creates all 5 workflow tables if they don't exist
4. Starts the requested service

**Integration**:
```dockerfile
# Set entrypoint to handle migrations
ENTRYPOINT ["/entrypoint.sh"]

# Service command runs after migration
CMD ["python", "-m", "thoth", "server", "start", ...]
```

---

## Docker Compose Services

### thoth-api (Port 8080)
- **Purpose**: Main REST API for browser workflows
- **Browser Support**: ✅ Chromium installed
- **Migrations**: ✅ Auto-run on startup
- **Dependencies**: PostgreSQL (thoth database)

### thoth-mcp (Ports 8081-8082)
- **Purpose**: MCP server for Claude integration
- **Browser Support**: ✅ Chromium installed
- **Migrations**: ✅ Auto-run on startup
- **Dependencies**: PostgreSQL (thoth database)

### letta-postgres (Port 5432)
- **Purpose**: PostgreSQL server for both Letta and Thoth
- **Databases**: `letta` and `thoth`
- **Extensions**: uuid-ossp, vector
- **Initialization**: Automatic on first start

---

## Building and Running

### First Time Setup

```bash
# Build all images (takes 5-10 minutes)
docker compose build

# Start all services
docker compose up -d

# Check logs
docker compose logs -f thoth-api thoth-mcp letta-postgres
```

### Database Verification

```bash
# Check PostgreSQL logs to verify database creation
docker compose logs letta-postgres | grep -E "Created|thoth|letta"

# Connect to PostgreSQL
docker compose exec letta-postgres psql -U thoth -d thoth

# List browser workflow tables
\dt *workflow*

# Expected output:
#   browser_workflows
#   workflow_actions
#   workflow_search_config
#   workflow_credentials
#   workflow_executions
```

### Migration Verification

```bash
# Check API startup logs for migration
docker compose logs thoth-api | grep -E "migration|Migration"

# Expected output:
#   ==> Running database migrations...
#   ✓ Migrations complete!
```

### Browser Verification

```bash
# Check if Playwright is installed
docker compose exec thoth-api /app/.venv/bin/playwright --version

# Test browser launch
docker compose exec thoth-api python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch()
    print('✓ Chromium launched successfully')
    browser.close()
"
```

---

## Rebuild After Changes

### Rebuild Specific Service

```bash
# Rebuild API service only
docker compose build thoth-api

# Restart with new image
docker compose up -d thoth-api
```

### Full Rebuild

```bash
# Stop all services
docker compose down

# Remove old images (optional)
docker compose down --rmi local

# Rebuild everything
docker compose build --no-cache

# Start fresh
docker compose up -d
```

---

## Environment Variables

### Required in `.env`

```bash
# Database URL (automatically set in docker-compose.yml)
DATABASE_URL=postgresql://thoth:thoth_password@letta-postgres:5432/thoth

# Obsidian Vault Path (required)
OBSIDIAN_VAULT_PATH=/path/to/your/vault

# API Keys (optional)
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
```

### Docker-Specific Variables

Set in `docker-compose.yml`:
- `THOTH_DOCKER=1` - Indicates running in Docker
- `DOCKER_ENV=true` - Docker environment flag
- `PYTHONPATH=/app/src` - Python module path

---

## Troubleshooting

### Migration Fails

```bash
# Check if database is accessible
docker compose exec thoth-api python3 -c "
import asyncpg, asyncio
asyncio.run(asyncpg.connect('postgresql://thoth:thoth_password@letta-postgres:5432/thoth'))
print('✓ Database connection OK')
"

# Manually run migration
docker compose exec thoth-api python3 -m thoth.migration.run_browser_workflow_migration
```

### Playwright Not Found

```bash
# Reinstall Playwright browsers
docker compose exec thoth-api /app/.venv/bin/playwright install chromium

# Check browser path
docker compose exec thoth-api find /home/thoth -name "chromium*"
```

### Permission Issues

```bash
# Check file permissions
docker compose exec thoth-api ls -la /app/src/thoth/

# Fix if needed (run as root)
docker compose exec -u root thoth-api chown -R thoth:thoth /app
```

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is healthy
docker compose ps letta-postgres

# Check PostgreSQL logs
docker compose logs letta-postgres

# Test connection
docker compose exec letta-postgres psql -U thoth -d thoth -c "SELECT version();"
```

---

## Performance Considerations

### Image Sizes

- **Base image**: ~200MB (Python 3.11 slim)
- **With dependencies**: ~500MB
- **With Playwright**: ~800MB
- **Total per service**: ~800-1000MB

### Resource Limits

Configured in `docker-compose.yml`:

**API Service**:
- Memory: 256MB min, 1GB max
- CPU: 0.1 cores min, 0.5 cores max

**MCP Service**:
- Memory: 128MB min, 512MB max
- CPU: 0.05 cores min, 0.25 cores max

### Build Time

- **First build**: 5-10 minutes
- **Rebuild (cached)**: 1-2 minutes
- **Playwright install**: 2-3 minutes

---

## Security Notes

- Services run as non-root `thoth` user (UID 999)
- Playwright browsers installed in user home directory
- PostgreSQL credentials configurable via environment
- No hardcoded secrets in images
- Database data persists in named volumes

---

## Volume Management

### Persistent Volumes

```bash
# List volumes
docker volume ls | grep thoth

# Volumes created:
#   thoth-letta-postgres  - PostgreSQL data (includes both databases)
#   thoth-letta-data      - Letta application data
#   thoth-letta-home      - Letta home directory
#   thoth-app-home        - Thoth application home
#   thoth-tmp-cache       - Temporary cache
```

### Backup Database

```bash
# Backup thoth database
docker compose exec letta-postgres pg_dump -U thoth thoth > thoth_backup.sql

# Restore
docker compose exec -T letta-postgres psql -U thoth thoth < thoth_backup.sql
```

---

## Testing the Setup

### Quick Health Check

```bash
# All services healthy
docker compose ps

# Expected STATUS: "healthy" or "running"
```

### API Endpoint Test

```bash
# Health check
curl http://localhost:8080/health

# List workflows
curl http://localhost:8080/browser-workflows/workflows

# Create test workflow (requires authentication)
curl -X POST http://localhost:8080/browser-workflows/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Workflow",
    "website_domain": "example.com",
    "start_url": "https://example.com",
    "requires_authentication": false,
    "extraction_rules": {}
  }'
```

### MCP Tool Test

```bash
# Check MCP server
curl http://localhost:8082/health

# List available tools
curl http://localhost:8082/tools
```

---

## Next Steps

1. **Configure Workflows**: Create browser workflows via API
2. **Add Credentials**: Store encrypted credentials for authenticated sites
3. **Test Execution**: Run a workflow and verify article extraction
4. **Monitor Logs**: Watch execution logs for debugging
5. **Scale Services**: Adjust resource limits based on usage

---

## Summary

✅ **Docker setup is complete and operational:**
- PostgreSQL with both letta and thoth databases
- Playwright and Chromium fully integrated
- Automatic migrations on startup
- All services configured and tested
- Production-ready with proper security

**The browser workflow system is ready to use in Docker!**
