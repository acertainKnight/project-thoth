# Thoth & Letta Architecture - Independent Services

## 🎯 Overview

**Important Change**: Letta and Thoth now run as **completely independent services**. This architecture prevents database loss, agent corruption, and service crashes that occurred when Thoth services restarted.

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│ LETTA INFRASTRUCTURE (Independent, Multi-Project)       │
├─────────────────────────────────────────────────────────┤
│ • letta-postgres (pgvector, port 5432)                  │
│ • letta-server (port 8283)                              │
│ • letta-redis (caching)                                 │
│ • letta-nginx (SSE proxy, port 8284)                    │
│ Network: letta-network (172.22.0.0/16)                  │
└─────────────────────────────────────────────────────────┘
                           ↓
                    (connects to)
                           ↓
┌─────────────────────────────────────────────────────────┐
│ THOTH SERVICES (Project-Specific)                       │
├─────────────────────────────────────────────────────────┤
│ • thoth-all-in-one (API, MCP, Discovery, Monitor)       │
│   - API: port 8080                                      │
│   - MCP: port 8081                                      │
│ Network: thoth-network (172.20.0.0/16)                  │
│ + External: letta-network (for database access)         │
└─────────────────────────────────────────────────────────┘
```

## 🔑 Key Benefits

### 1. **Data Safety**
- ✅ Restarting Thoth never affects Letta
- ✅ Agents and database remain intact
- ✅ No more accidental data loss

### 2. **Multi-Project Support**
- ✅ Letta can serve multiple projects simultaneously
- ✅ One Letta instance, many applications
- ✅ Shared infrastructure, isolated data

### 3. **Independent Management**
- ✅ Start/stop services separately
- ✅ Debug Thoth without touching Letta
- ✅ Update Thoth without Letta downtime

## 📁 File Structure

```
project-thoth/
├── docker-compose.letta.yml     # Letta infrastructure (INDEPENDENT)
├── docker-compose.yml            # Thoth services (connects to Letta)
├── docker-compose.dev.yml        # Thoth development mode
└── scripts/
    ├── letta-start.sh           # Start Letta (affects all projects)
    ├── letta-stop.sh            # Stop Letta (WARNING: global)
    ├── letta-status.sh          # Check Letta status
    ├── letta-restart.sh         # Restart Letta
    ├── thoth-start.sh           # Start Thoth only
    ├── thoth-stop.sh            # Stop Thoth only
    ├── thoth-status.sh          # Check both services
    └── thoth-restart.sh         # Restart Thoth only
```

## 🚀 Usage

### Quick Start

```bash
# 1. Start Letta (once, shared infrastructure)
letta-start

# 2. Start Thoth (your project)
thoth-start

# 3. Check status
thoth-status

# 4. Stop Thoth (Letta keeps running)
thoth-stop

# 5. Stop Letta (when done with ALL projects)
letta-stop
```

### Make Commands

```bash
# Letta management
make letta-start         # Start Letta services
make letta-stop          # Stop Letta (WARNING: affects all projects)
make letta-status        # Check Letta status
make letta-restart       # Restart Letta
make letta-logs          # View Letta logs

# Thoth management
make thoth-start         # Start Thoth services
make thoth-stop          # Stop Thoth (Letta keeps running)
make thoth-status        # Check both services
make thoth-restart       # Restart Thoth (Letta unaffected)
make thoth-logs          # View Thoth logs
```

### Bash Aliases

Added to `~/.bashrc`:

```bash
# Letta (independent, multi-project)
alias letta-start='bash ~/Documents/python/project-thoth/scripts/letta-start.sh'
alias letta-stop='bash ~/Documents/python/project-thoth/scripts/letta-stop.sh'
alias letta-status='bash ~/Documents/python/project-thoth/scripts/letta-status.sh'
alias letta-restart='bash ~/Documents/python/project-thoth/scripts/letta-restart.sh'
alias letta-logs='docker logs -f letta-server'
alias letta-logs-pg='docker logs -f letta-postgres'

# Thoth (project-specific)
alias thoth-start='bash ~/Documents/python/project-thoth/scripts/thoth-start.sh'
alias thoth-stop='bash ~/Documents/python/project-thoth/scripts/thoth-stop.sh'
alias thoth-status='bash ~/Documents/python/project-thoth/scripts/thoth-status.sh'
alias thoth-restart='bash ~/Documents/python/project-thoth/scripts/thoth-restart.sh'
alias thoth-logs='docker logs -f thoth-all-in-one'

# Navigation
alias thoth-cd='cd ~/Documents/python/project-thoth'
```

## 🔍 Service Details

### Letta Infrastructure

| Service | Port | Purpose | Shared? |
|---------|------|---------|---------|
| letta-postgres | 5432 | Database with pgvector | ✅ Yes |
| letta-server | 8283 | Memory/agent API | ✅ Yes |
| letta-redis | 6379 | Caching/queuing | ✅ Yes |
| letta-nginx | 8284 | SSE streaming proxy | ✅ Yes |

**Databases in PostgreSQL:**
- `letta` - Agent memories, tools, prompts
- `thoth` - Thoth-specific data

### Thoth Services

| Service | Port | Purpose | Shared? |
|---------|------|---------|---------|
| thoth-all-in-one | 8080 | API server | ❌ No |
| thoth-all-in-one | 8081 | MCP server | ❌ No |

## ⚠️ Important Warnings

### 1. **Never Restart Letta Carelessly**
```bash
# ❌ BAD: Affects ALL projects
letta-restart

# ✅ GOOD: Only restart Thoth
thoth-restart
```

### 2. **Check Before Stopping Letta**
```bash
# Check if other projects are using Letta
docker ps | grep letta
letta-status

# Safe to stop Letta when:
# - Only Thoth containers connected
# - No other projects running
```

### 3. **Always Start Letta First**
```bash
# Correct order:
letta-start          # 1. Start Letta
sleep 5              # 2. Wait for health
thoth-start          # 3. Start Thoth
```

## 🔧 Troubleshooting

### Problem: "Letta not responding"
```bash
# Check Letta status
letta-status

# Restart if needed (WARNING: affects all projects)
letta-restart

# Check logs
letta-logs
```

### Problem: "Database connection failed"
```bash
# Ensure Letta network exists
docker network inspect letta-network

# Restart Thoth (not Letta)
thoth-restart
```

### Problem: "Agents disappeared"
```bash
# Check which volume is mounted
docker inspect letta-postgres | grep -A 5 Mounts

# Should be: letta-postgres -> /var/lib/postgresql/data

# Verify agent count
docker exec letta-postgres psql -U letta -d letta -c "SELECT COUNT(*) FROM agents;"
```

## 📊 Health Monitoring

```bash
# Complete status check
thoth-status

# Just Letta
letta-status

# Manual health checks
curl http://localhost:8283/v1/health  # Letta API
curl http://localhost:8080/health      # Thoth API
curl http://localhost:8284/nginx-health # Letta SSE

# Database check
docker exec letta-postgres pg_isready -U letta -d letta
```

## 🔄 Migration from Old Architecture

If you're migrating from the old architecture where Letta was managed by Thoth:

```bash
# 1. Stop everything
docker compose down
docker compose -f docker-compose.dev.yml down

# 2. Check your data is in letta-postgres volume
docker volume inspect letta-postgres

# 3. Start with new architecture
letta-start
thoth-start

# 4. Verify agents
docker exec letta-postgres psql -U letta -d letta -c "SELECT COUNT(*) FROM agents;"
```

## 🛡️ Backup & Recovery

### Backup Letta Data
```bash
# Backup agents database
docker exec letta-postgres pg_dump -U letta letta > backup-letta-$(date +%Y%m%d).sql

# Backup Thoth database
docker exec letta-postgres pg_dump -U thoth thoth > backup-thoth-$(date +%Y%m%d).sql

# Backup Docker volumes
docker run --rm -v letta-postgres:/source -v $(pwd):/backup alpine \
  tar czf /backup/letta-volume-$(date +%Y%m%d).tar.gz -C /source .
```

### Restore from Backup
```bash
# Restore database
docker exec -i letta-postgres psql -U letta letta < backup-letta-20260109.sql
```

## 📚 Additional Resources

- [Docker Volumes Guide](./LETTA_VOLUMES.md) - Understanding volume management
- [Troubleshooting Guide](../README.md#troubleshooting) - Common issues
- [Development Setup](../CONTRIBUTING.md) - For contributors

## 🎓 Best Practices

1. **Always use the aliases/scripts** - Don't run docker commands directly
2. **Check status before operations** - Use `thoth-status` to verify state
3. **Restart Thoth, not Letta** - When debugging Thoth issues
4. **Monitor Letta logs** - Use `letta-logs` to watch for issues
5. **Backup regularly** - Use the backup scripts above

## 📅 Version History

- **v3.0 (Jan 2026)** - Independent Letta architecture
- **v2.0 (Dec 2025)** - Integrated docker-compose
- **v1.0 (Nov 2025)** - Initial Docker setup

---

**Last Updated**: January 9, 2026
**Architecture Version**: 3.0 (Independent Services)
