# Docker Workflow & Best Practices

**Based on UV's Official Docker Documentation**  
See: https://docs.astral.sh/uv/guides/integration/docker/

---

## Development Workflow (UV Best Practice)

### For Code Changes: Use `docker compose watch`

**NO REBUILDS NEEDED!** Source code changes sync automatically:

```bash
# Start development with auto-sync
docker compose watch

# Edit code in your editor
# Changes sync to container automatically
# Service restarts automatically (if configured)
```

**That's it!** No manual rebuilds, no restarts.

---

## When to Rebuild

### ONLY rebuild for dependency changes:

```bash
# Changed pyproject.toml or uv.lock?
docker compose build thoth-mcp
docker compose up -d thoth-mcp
```

**With `docker compose watch`**, this happens automatically!

### One-Liner Alternative

```bash
docker compose down && docker compose build thoth-mcp && docker compose up -d thoth-mcp
```

Or force recreation:

```bash
docker compose up -d --build --force-recreate thoth-mcp
```

---

## Common Docker Pitfalls

### ❌ WRONG: Using `restart`

```bash
docker compose restart thoth-mcp
```

**Problem**: Does NOT pick up new code or new Docker images. Uses old container with old image.

### ❌ WRONG: Using `up -d` without removing

```bash
docker compose build thoth-mcp
docker compose up -d thoth-mcp
```

**Problem**: May reuse existing container instead of creating fresh one with new image.

### ✅ CORRECT: Stop, remove, build, start

```bash
docker compose stop thoth-mcp
docker compose rm -f thoth-mcp
docker compose build thoth-mcp
docker compose up -d thoth-mcp
```

**Why**: Forces Docker to create new container from new image.

---

## Docker Build Stages

### Multi-Stage Build Structure

MCP Dockerfile has multiple stages:

```dockerfile
FROM python:3.11-slim as builder
# ... install dependencies ...

FROM python:3.11-slim as production  # ← Used by docker-compose
# ... copy from builder ...
# ... setup permissions ...
# ... create directories ...
USER thoth  # ← Switch to non-root user

FROM production as development
# ... additional dev tools ...
```

### Important Rules

1. **Check docker-compose.yml for target**:
   ```yaml
   build:
     target: production  # ← This stage is used
   ```

2. **Changes must be in correct stage**:
   - If target is `production`, changes in `development` stage are IGNORED
   - Add setup steps BEFORE the `USER thoth` line in production stage

3. **Permission-sensitive operations**:
   - Create directories as `root` (before USER switch)
   - Then `chown` to `thoth:thoth`
   - Then switch to `USER thoth`

### Example: Adding Cache Directories

```dockerfile
# ❌ WRONG - After USER switch
USER thoth
RUN mkdir -p /app/cache/ocr  # Permission denied!

# ✅ CORRECT - Before USER switch
RUN mkdir -p /app/cache/{ocr,analysis,citations} && \
    chown -R thoth:thoth /app/cache && \
    chmod -R 755 /app/cache
USER thoth
```

---

## Permission Issues

### Common Problem

```
PermissionError: [Errno 13] Permission denied: '/app/cache/ocr'
```

### Root Cause

- Service tries to create directory at runtime
- Container runs as user `thoth` (non-root)
- User `thoth` doesn't have permission to create dirs in `/app`

### Solution

**Create directories in Dockerfile, not at runtime:**

```dockerfile
# In production stage, BEFORE USER switch:
RUN mkdir -p /app/cache/{subdir1,subdir2,subdir3} && \
    chown -R thoth:thoth /app/cache && \
    chmod -R 755 /app/cache

USER thoth  # Now switch to non-root user
```

---

## Debugging Docker Issues

### Check Container Status

```bash
# Is it healthy?
docker compose ps thoth-mcp

# What's in the logs?
docker compose logs thoth-mcp --tail=50

# Is it crash-looping?
docker compose logs thoth-mcp --follow
```

### Check Image Build Date

```bash
# When was the image built?
docker images --format "{{.Repository}}:{{.Tag}}\t{{.CreatedAt}}" | grep thoth-mcp

# Is container using latest image?
docker compose ps thoth-mcp  # Check IMAGE column
```

### Check File Timestamps in Container

```bash
# Check if files are up-to-date
docker compose exec thoth-mcp stat /app/src/thoth/cli/main.py | grep Modify

# Compare with local file
stat src/thoth/cli/main.py | grep Modify
```

### Force Clean Rebuild

```bash
# Nuclear option - rebuild everything from scratch
docker compose down
docker compose build --no-cache thoth-mcp
docker compose up -d thoth-mcp
```

---

## Best Practices

1. **Always commit before rebuilding** - So you can track what code is in which image
2. **Tag images with git hash** - For production deployments
3. **Check logs immediately** - Don't wait to see if it "seems to work"
4. **Test in container, not just locally** - Permissions differ
5. **Document permission needs** - Note which dirs need creation in Dockerfile

---

## Quick Reference

```bash
# Full rebuild workflow
docker compose stop SERVICE && \
docker compose rm -f SERVICE && \
docker compose build SERVICE && \
docker compose up -d SERVICE && \
docker compose logs SERVICE --tail=20

# Check if healthy
docker compose ps SERVICE | grep healthy

# Watch logs in real-time
docker compose logs SERVICE --follow

# Check files in container
docker compose exec SERVICE ls -la /app/src/thoth/cli/

# Run command in container
docker compose exec SERVICE python -m thoth letta folders
```

---

## Current Project Setup

- **Services**: thoth-mcp, thoth-api, thoth-pdf-monitor, thoth-discovery, postgres
- **Main service**: thoth-mcp (MCP server with 62 tools)
- **Build target**: production
- **User**: thoth (UID 1000, GID 1000)
- **Ports**: 8081 (SSE), 8082 (HTTP)
- **Critical dirs**: /app/cache/* (must exist in image)
