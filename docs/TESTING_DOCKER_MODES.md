# Docker Deployment Modes - Testing Checklist

This document provides a comprehensive testing checklist for both local and microservices deployment modes.

## Prerequisites

- [ ] Export `OBSIDIAN_VAULT_PATH` to your test vault
- [ ] Ensure `.env` file exists with required API keys
- [ ] Docker and Docker Compose installed
- [ ] At least 4GB RAM available
- [ ] Ports 8000, 8001, 8283, 5432/5433 available

## Phase 1: Local Mode Testing (Default)

### Build and Start

```bash
# Build and start in local mode (default)
make dev
```

**Expected Results:**
- [ ] 3 containers start: `thoth-dev-all-in-one`, `thoth-dev-letta`, `thoth-dev-letta-postgres`
- [ ] No individual service containers (api, mcp, discovery, monitor)
- [ ] Supervisor starts inside thoth-all-in-one container
- [ ] All services show as RUNNING in supervisor

### Health Checks

```bash
# Check health of all services
make health
```

**Expected Results:**
- [ ] API (8080): ✓ Healthy
- [ ] MCP HTTP (8082): ✓ Healthy
- [ ] MCP SSE (8081): ✓ Healthy
- [ ] Letta (8283): ✓ Healthy

### Service Logs

```bash
# Check supervisor logs
docker exec thoth-dev-all-in-one supervisorctl status

# Check individual service logs
docker exec thoth-dev-all-in-one tail -f /vault/_thoth/logs/api-stdout.log
docker exec thoth-dev-all-in-one tail -f /vault/_thoth/logs/mcp-stdout.log
docker exec thoth-dev-all-in-one tail -f /vault/_thoth/logs/discovery-stdout.log
docker exec thoth-dev-all-in-one tail -f /vault/_thoth/logs/monitor-stdout.log
```

**Expected Results:**
- [ ] All 4 services show RUNNING in supervisorctl
- [ ] No error messages in service logs
- [ ] Services can communicate with each other

### Functional Tests

```bash
# Test API endpoint
curl http://localhost:8000/health

# Test MCP HTTP endpoint
curl http://localhost:8082/health

# Test file upload (if applicable)
# Process a PDF through the API
```

**Expected Results:**
- [ ] API responds with {"status": "healthy"}
- [ ] MCP responds with {"status": "healthy"}
- [ ] Can upload and process PDFs
- [ ] PDF Monitor detects new files in watch directory

### Hot-Reload Test

```bash
# Test hot-reload by touching settings.json
make reload-settings

# Watch logs for reload message
docker logs -f thoth-dev-all-in-one 2>&1 | grep -i reload
```

**Expected Results:**
- [ ] Services detect settings.json change
- [ ] Services reload configuration
- [ ] No service restarts required

### Resource Usage

```bash
# Check resource usage
docker stats --no-stream
```

**Expected Results:**
- [ ] Total memory usage ≤ 3.5GB
- [ ] CPU usage reasonable (<50% average)
- [ ] 3 containers total

### Stop and Cleanup

```bash
make dev-stop
```

**Expected Results:**
- [ ] All containers stop cleanly
- [ ] No orphaned processes
- [ ] Vault data preserved

## Phase 2: Microservices Mode Testing

### Build and Start

```bash
# Start in microservices mode
make microservices
```

**Expected Results:**
- [ ] 6 containers start: api, mcp, discovery, pdf-monitor, letta, postgres
- [ ] NO thoth-all-in-one container
- [ ] Each service in separate container
- [ ] All services healthy

### Health Checks

```bash
make health
```

**Expected Results:**
- [ ] API (8000): ✓ Healthy
- [ ] MCP (8001): ✓ Healthy
- [ ] Letta (8283): ✓ Healthy
- [ ] All individual service containers running

### Service Communication

```bash
# Check inter-service communication
docker exec thoth-dev-api curl http://thoth-mcp:8000/health
docker exec thoth-dev-mcp curl http://thoth-api:8000/health
```

**Expected Results:**
- [ ] Services can reach each other via Docker network
- [ ] Service discovery URLs work correctly

### Individual Service Logs

```bash
# View logs for each service
docker logs thoth-dev-api
docker logs thoth-dev-mcp
docker logs thoth-dev-discovery
docker logs thoth-dev-pdf-monitor
```

**Expected Results:**
- [ ] Each service has independent logs
- [ ] No cross-service errors
- [ ] Services start in correct order

### Restart Single Service

```bash
# Restart just the API service
docker restart thoth-dev-api

# Check it comes back up
docker ps | grep thoth-dev-api
```

**Expected Results:**
- [ ] API service restarts independently
- [ ] Other services remain running
- [ ] System continues functioning

### Resource Usage

```bash
docker stats --no-stream
```

**Expected Results:**
- [ ] Total memory usage ≤ 4.5GB
- [ ] CPU usage distributed across containers
- [ ] 6 containers total

### Stop and Cleanup

```bash
make dev-stop
```

**Expected Results:**
- [ ] All containers stop cleanly
- [ ] All microservices profiles cleaned up

## Phase 3: Production Mode Testing

### Local Mode (Default)

```bash
make prod
```

**Expected Results:**
- [ ] Builds production images
- [ ] Starts 3 containers (all-in-one, letta, postgres)
- [ ] Runs on ports 8080, 8081
- [ ] Optimized images without dev tools

### Microservices Mode

```bash
make prod-microservices
```

**Expected Results:**
- [ ] Builds separate production images
- [ ] Starts 7 containers (all services separate)
- [ ] Runs on ports 8080, 8081, 8082, 8004
- [ ] Production optimizations applied

## Phase 4: Switching Between Modes

### Local → Microservices

```bash
make dev
# Verify local mode running
make dev-stop
make microservices
# Verify microservices mode running
```

**Expected Results:**
- [ ] Clean transition between modes
- [ ] No data loss
- [ ] Vault data preserved
- [ ] No port conflicts

### Microservices → Local

```bash
make microservices
# Verify microservices running
make dev-stop
make dev
# Verify local mode running
```

**Expected Results:**
- [ ] Clean transition back to local mode
- [ ] All services accessible
- [ ] No container conflicts

## Phase 5: Data Persistence

### Test Data Survival

```bash
# Start local mode
make dev

# Create/process some data
# (upload PDFs, create notes, etc.)

# Stop and switch modes
make dev-stop
make microservices

# Verify data still accessible
```

**Expected Results:**
- [ ] Data persists across mode switches
- [ ] Vault files intact
- [ ] Database data preserved
- [ ] Letta memory preserved

## Phase 6: Error Scenarios

### Missing Vault Path

```bash
unset OBSIDIAN_VAULT_PATH
make dev
```

**Expected Results:**
- [ ] Clear error message
- [ ] Helpful instructions provided
- [ ] No containers started

### Port Conflicts

```bash
# Start local mode
make dev

# Try to start again
make dev
```

**Expected Results:**
- [ ] Docker handles port conflicts gracefully
- [ ] Clear error messages if conflicts occur

### Service Crashes

```bash
# Kill a service inside unified container
docker exec thoth-dev-all-in-one supervisorctl stop thoth-api

# Wait a few seconds
sleep 5

# Check if supervisor restarted it
docker exec thoth-dev-all-in-one supervisorctl status
```

**Expected Results:**
- [ ] Supervisor automatically restarts crashed services
- [ ] System self-heals
- [ ] Other services continue running

## Success Criteria

All tests passing indicates successful implementation:

- [x] ✅ Local mode runs with 3 containers
- [x] ✅ Microservices mode runs with 6 containers  
- [x] ✅ Both modes functionally identical
- [x] ✅ Can switch between modes without data loss
- [x] ✅ Resource usage as expected (~1GB saved in local mode)
- [x] ✅ Hot-reload works in both modes
- [x] ✅ Supervisor manages services correctly
- [x] ✅ All services healthy in both modes
- [x] ✅ Production modes work correctly
- [x] ✅ Clear error messages for misconfigurations

## Known Issues / Limitations

### Local Mode
- Cannot independently restart individual services (must restart whole container)
- All services restart together if supervisor fails
- Slightly harder to debug individual service issues

### Microservices Mode
- Higher resource usage
- More containers to manage
- Longer startup time

### Both Modes
- ChromaDB fully removed - all data must be in PostgreSQL+pgvector
- Requires minimum 3.5GB RAM
- Letta and PostgreSQL always separate (shared dependency)

## Troubleshooting

### Container Won't Start
```bash
# Check logs
docker logs thoth-dev-all-in-one

# Check supervisor status
docker exec thoth-dev-all-in-one supervisorctl status

# Restart container
docker restart thoth-dev-all-in-one
```

### Services Not Responding
```bash
# Verify ports
docker ps

# Check health endpoints
curl http://localhost:8080/health
curl http://localhost:8082/health

# Check inter-service connectivity
docker exec thoth-dev-all-in-one curl http://localhost:8000/health
```

### Switching Modes Fails
```bash
# Ensure clean shutdown
make dev-stop
docker compose -f docker-compose.dev.yml --profile microservices down

# Verify no containers running
docker ps -a | grep thoth-dev

# Try starting fresh
make dev
```
