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

### 4. Agent Restoration
Restored 15/16 agents via Letta API (AI/ML Expert failed due to "/" in name):
- ✅ thoth_main_orchestrator
- ✅ system_citation_analyzer
- ✅ system_discovery_scout
- ✅ system_analysis_expert
- ✅ system_maintenance
- ✅ organization_curator
- ✅ document_librarian
- ✅ Lead Engineer (3 variants)
- ✅ Nameless Agent (3 instances)
- ✅ Memo, Incognito
- ❌ AI/ML Expert (name validation failed)

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

## Future Migrations

To avoid this issue:
1. **Never use `latest` tag** - always pin specific versions
2. **Backup before upgrades**: `~/letta-backup-YYYYMMDD/`
3. **Test compatibility** between Letta Server and Letta Code versions
4. **Check release notes** for breaking schema changes

## Rollback Procedure (if needed)

```bash
# 1. Stop Letta
docker compose -f docker-compose.letta.yml stop

# 2. Restore from backup (if you have pg_dump)
docker exec -i letta-postgres pg_restore -U letta -d letta < backup.dump

# 3. Or recreate database and restore agents
python3 /tmp/restore-agents-simple.py
```

## References
- Letta Server: https://github.com/letta-ai/letta
- Letta Code: https://github.com/letta-ai/letta-code
- Migration completed: 2026-01-17 6:10 PM EST
