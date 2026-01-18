# Letta Database Migration - January 17, 2026

## Problem
- Letta Docker `latest` tag auto-upgraded from 0.11.3 to 0.16.2
- Database schema incompatibility between versions
- Missing columns: `runs.conversation_id`, `steps.request_id`, `messages.sequence_id`
- Letta Code 0.13.0 failing with 500/409 errors

## Solution
Complete database recreation with schema migration from 0.11.3 to 0.16.2.

## What Was Done

### 1. Agent Backup
All 16 agents exported to JSON:
```bash
~/letta-backup-20260117/*.json
```

### 2. Database Recreation
```bash
# Stopped Letta server
docker compose -f docker-compose.letta.yml stop letta

# Dropped and recreated letta database (thoth database untouched)
docker exec letta-postgres psql -U letta -d postgres -c "DROP DATABASE letta;"
docker exec letta-postgres psql -U letta -d postgres -c "CREATE DATABASE letta OWNER letta;"

# Installed pgvector extension
docker exec letta-postgres psql -U letta -d letta -c "CREATE EXTENSION vector;"

# Restarted Letta to create fresh 0.16.2 schema
docker compose -f docker-compose.letta.yml up -d letta
```

### 3. Schema Fix for Letta Code 0.13.0 Compatibility
Added auto-increment default for `sequence_id`:
```sql
CREATE SEQUENCE messages_sequence_id_seq OWNED BY messages.sequence_id;
ALTER TABLE messages ALTER COLUMN sequence_id SET DEFAULT nextval('messages_sequence_id_seq');
```

### 4. Agent Restoration (with Memory Blocks)

**Initial Issue:** First restoration attempt only restored agents with 2 default memory blocks (loaded_skills, skills), losing all custom memory (24 blocks for Lead Engineer including project knowledge, persona, component documentation).

**Solution:** Per [Letta API documentation](https://docs.letta.com/api-reference/agents/create), use `memory_blocks` parameter (not `blocks`) with simplified block structure:

```python
payload = {
    "name": agent['name'],
    "memory_blocks": [  # Correct parameter name
        {
            "label": block['label'],
            "value": block['value'],
            "limit": block.get('limit', 10000),
            # Strip auto-generated fields: id, created_by_id, created_at, etc.
        }
    ]
}
```

**Result:** Successfully restored agents with full memory:
- ✅ Lead Engineer: 24 memory blocks restored
- ✅ Lead Engineer - Autolabeler: 9 memory blocks restored
- ✅ thoth_main_orchestrator, system agents, etc.
- ❌ AI/ML Expert (name contains "/" - validation failed)

### 5. Configuration Changes

**~/.bashrc:**
```bash
# Changed from port 8284 (nginx) to 8283 (direct API)
export LETTA_BASE_URL="http://localhost:8283"
export LETTA_API_KEY="letta_dev_password"
```

**docker-compose.letta.yml:**
```yaml
# Pinned version to prevent auto-upgrades
image: letta/letta:0.16.2  # Was: letta/letta:latest
```

## Version Compatibility

| Component | Version | Status |
|-----------|---------|--------|
| Letta Server | 0.16.2 | ✅ Working |
| Letta Code CLI | 0.13.0 | ✅ Working |
| PostgreSQL | 15 (pgvector) | ✅ Working |
| Docker Compose | v2 | ✅ Working |

## Verification

```bash
# Check agents restored
curl -s http://localhost:8283/v1/agents/?limit=100 | jq 'length'
# Output: 23 (15 restored + 8 defaults)

# Test Letta Code
LETTA_BASE_URL="http://localhost:8283" LETTA_API_KEY="letta_dev_password" letta --info
# Output: Shows all agents correctly

# Check health
curl http://localhost:8283/v1/health/
# Output: {"version":"0.16.2","status":"ok"}
```

## Backup Location
```
~/letta-backup-20260117/
  ├── agent-10418b8d-37a5-4923-8f70-69ccc58d66ff.json (thoth_main_orchestrator)
  ├── agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5.json (system_citation_analyzer)
  └── ... (14 more agents)
```

## Automated Migration System

Created comprehensive migration automation for future upgrades:

### Scripts
1. **`scripts/letta-migrate.sh [version]`** - Full migration workflow
   - Backs up all agents to `~/letta-backup-YYYYMMDD-HHMMSS/`
   - Updates Docker image version
   - Recreates database with fresh schema
   - Installs pgvector extension
   - Restores agents with full memory blocks
   - Applies compatibility fixes

2. **`scripts/restore-agents.py <backup_dir> <letta_url>`** - Agent restoration
   - Uses proper `memory_blocks` parameter per Letta API spec
   - Strips auto-generated fields (id, created_by_id, etc.)
   - Verifies memory block restoration
   - Handles agents with invalid names

3. **`scripts/letta-update.sh [version]`** - Simple wrapper for migrations

### Usage

```bash
# Migrate to specific version
./scripts/letta-migrate.sh 0.16.3

# Update to latest
./scripts/letta-update.sh latest

# Manual restoration from backup
python3 scripts/restore-agents.py ~/letta-backup-20260117 http://localhost:8283
```

## Future Migrations

To ensure safe upgrades:
1. **Use automation**: Run `./scripts/letta-migrate.sh [version]` instead of manual steps
2. **Pin versions**: Never use `latest` tag in production
3. **Test first**: Try migration on dev environment
4. **Check compatibility**: Verify Letta Server/Code version compatibility
5. **Review release notes**: Check for breaking schema changes

## Rollback Procedure (if needed)

```bash
# 1. Stop Letta
./scripts/letta-stop.sh

# 2. Restore previous Docker version
sed -i 's|image: letta/letta:.*|image: letta/letta:0.16.2|' docker-compose.letta.yml

# 3. Recreate database
docker exec letta-postgres psql -U letta -d postgres -c "DROP DATABASE letta;"
docker exec letta-postgres psql -U letta -d postgres -c "CREATE DATABASE letta OWNER letta;"
docker exec letta-postgres psql -U letta -d letta -c "CREATE EXTENSION vector;"

# 4. Start Letta
./scripts/letta-start.sh

# 5. Restore agents with memory
python3 scripts/restore-agents.py ~/letta-backup-20260117 http://localhost:8283
```

## References
- Letta Server: https://github.com/letta-ai/letta
- Letta Code: https://github.com/letta-ai/letta-code
- Migration completed: 2026-01-17 6:10 PM EST
