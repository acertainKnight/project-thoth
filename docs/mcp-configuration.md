# MCP Server Configuration for Thoth

This guide covers the configuration, registration, and troubleshooting of the Thoth Research Tools MCP (Model Context Protocol) server in Letta.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Initial Setup](#initial-setup)
- [Automatic Configuration](#automatic-configuration)
- [Manual Attachment](#manual-attachment)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)
- [Migration Process](#migration-process)

---

## Overview

The Thoth Research Tools MCP server provides 60 research tools to Letta agents via the Model Context Protocol. These tools include:

- Article search across multiple sources (arXiv, bioRxiv, CrossRef, OpenAlex, PubMed)
- Citation extraction and analysis
- PDF processing and note generation
- Research query management
- Knowledge graph operations
- And more...

**Key Concepts:**
- **MCP Server**: The Thoth backend service that exposes research tools
- **Server Registration**: Registering the MCP server in Letta's database
- **Agent Attachment**: Connecting registered MCP servers to specific agents
- **Tool Availability**: Tools only appear when server is attached to an agent

---

## Architecture

```
┌─────────────────────┐
│   Letta Agent       │
│  (Port 8283/8284)   │
└──────────┬──────────┘
           │ Attached via
           │ mcp_server_ids
           ▼
┌─────────────────────┐
│  MCP Server Entry   │
│  (Database Record)  │
│  ID: mcp_server-... │
└──────────┬──────────┘
           │ Points to
           ▼
┌─────────────────────┐
│ Thoth MCP Server    │
│ (Port 8000/8082)    │
│ 60 Research Tools   │
└─────────────────────┘
```

**Communication Flow:**
1. Agent makes tool call
2. Letta routes to MCP server via SSE transport
3. Thoth MCP server executes tool
4. Results returned to agent

---

## Initial Setup

### Prerequisites

- Letta server running (v0.16.3+)
- Thoth MCP server running on Docker network
- Proper network connectivity between containers

### Container Configuration

The MCP server is automatically configured during Letta container startup via `/docker/letta/init-schema.sh`:

**Key Configuration:**
```bash
# MCP Server URL (Docker internal network)
THOTH_MCP_URL=http://thoth-mcp:8000

# MCP Server Registration
- ID Format: mcp_server-<uuid> (underscore, not hyphen!)
- Server Name: thoth-research-tools
- Transport: SSE (Server-Sent Events)
- Endpoint: /mcp
```

**Environment Variables** (.env.letta):
```bash
# MCP Servers configuration (optional, for reference)
LETTA_MCP_SERVERS=[{"name":"thoth-research-tools","url":"http://thoth-mcp:8000/mcp","transport":"sse"}]
```

---

## Automatic Configuration

### During Container Startup

The `docker/letta/init-schema.sh` script automatically:

1. Creates MCP server entry in database
2. Verifies connectivity to Thoth MCP server
3. Validates tool endpoint is responding
4. **Does NOT** attach server to agents (must be done separately)

**Startup Logs:**
```
=== MCP Configuration Complete! ===
MCP configuration file exists
Thoth MCP server already configured
Thoth MCP server is accessible at http://thoth-mcp:8000
MCP tools endpoint responding
Registered Thoth MCP server: mcp_server-4dbdb8a0-2c57-445e-96fd-b48e5fc36f5f
```

### During Agent Restoration

The `scripts/restore-agents-complete.py` script automatically:

1. Restores agent from backup
2. Looks up Thoth MCP server ID
3. Attaches MCP server to restored agent
4. Reports attachment status

**Restoration Output:**
```
Lead Engineer
  ID: agent-abc123...
  Memory blocks: 24/24
  Tools: 3/7
  Tool rules: 18/18
  Tags: 3/3
  System prompt: 14567 chars
  MCP server: Thoth Research Tools
```

---

## Manual Attachment

### Using the Attachment Script

For existing agents that don't have the MCP server attached:

```bash
# Attach to all agents
python3 scripts/attach-mcp-to-agents.py

# Specify custom Letta URL
python3 scripts/attach-mcp-to-agents.py http://localhost:8283
```

**Expected Output:**
```
============================================================
Attaching Thoth MCP Server to Agents
============================================================

Looking for Thoth MCP server...
Found Thoth MCP server: mcp_server-4dbdb8a0-2c57-445e-96fd-b48e5fc36f5f

Retrieving agents...
Found 27 agent(s)

  Lead Engineer - MCP server attached
  thoth_main_orchestrator - MCP server attached
  Memo - already has MCP server
  ...

Results:
  Attached:       25
  Already had:    2
  Failed:         0
  Total agents:   27
```

### Using the Letta ADE (Web Interface)

**IMPORTANT**: In Letta 0.16+, MCP server attachment through the ADE is the recommended approach for new agents.

1. **Open Letta ADE**: Navigate to http://localhost:8284 (or http://localhost:8283)
2. **Create/Edit Agent**: Click on an agent or create a new one
3. **MCP Servers Section**: Look for MCP servers configuration
4. **Select Server**: Add "thoth-research-tools" to the agent
5. **Save**: The 60 tools will now be available

### Using the Letta API

```python
import requests

LETTA_URL = "http://localhost:8283"
LETTA_PASSWORD = "letta_dev_password"

# Get MCP server ID
response = requests.get(
    f"{LETTA_URL}/v1/mcp-servers/",
    headers={"Authorization": f"Bearer {LETTA_PASSWORD}"}
)
servers = response.json()
thoth_mcp_id = next(s['id'] for s in servers if s['server_name'] == 'thoth-research-tools')

# Attach to agent
response = requests.patch(
    f"{LETTA_URL}/v1/agents/{agent_id}",
    headers={"Authorization": f"Bearer {LETTA_PASSWORD}"},
    json={"mcp_server_ids": [thoth_mcp_id]}
)
```

---

## Verification

### Check MCP Server Registration

```bash
# Via API
curl -s http://localhost:8283/v1/mcp-servers/ \
  -H "Authorization: Bearer letta_dev_password" | jq

# Expected output:
[
  {
    "id": "mcp_server-4dbdb8a0-2c57-445e-96fd-b48e5fc36f5f",
    "server_name": "thoth-research-tools",
    "mcp_server_type": "sse",
    "server_url": "http://thoth-mcp:8000/mcp",
    ...
  }
]

# Via Database
docker exec letta-postgres psql -U letta -d letta \
  -c "SELECT id, server_name, server_url FROM mcp_server;"
```

### Check MCP Server Connectivity

```bash
# Health check
curl -s http://localhost:8082/health

# Expected output:
{"status":"ok","protocol":"MCP","version":"2025-06-18"}

# List tools via MCP protocol
curl -s http://localhost:8082/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq '.result.tools | length'

# Expected output: 60 tools
```

### Check Agent Attachment

```bash
# Via attachment script
python3 scripts/attach-mcp-to-agents.py

# Via API (check specific agent)
curl -s "http://localhost:8283/v1/agents/{agent_id}" \
  -H "Authorization: Bearer letta_dev_password" | jq '.mcp_server_ids'

# Expected output:
["mcp_server-4dbdb8a0-2c57-445e-96fd-b48e5fc36f5f"]
```

### Verify Tools in Agent

Once attached via the ADE, verify tools are available:

```bash
curl -s "http://localhost:8283/v1/agents/{agent_id}/tools" \
  -H "Authorization: Bearer letta_dev_password" | jq '[.[] | select(.source_type == "mcp")] | length'

# Expected output: 60 (number of MCP tools)
```

---

## Troubleshooting

### Issue: MCP Server Not Found

**Symptoms:**
```
Thoth MCP server not found in Letta
```

**Causes:**
1. Server not registered in database
2. Wrong server name
3. Database connection issues

**Solutions:**
```bash
# Check database registration
docker exec letta-postgres psql -U letta -d letta \
  -c "SELECT id, server_name FROM mcp_server;"

# If empty, restart Letta container (runs init-schema.sh)
docker restart letta-server

# Wait for health check
curl -f http://localhost:8283/v1/health
```

### Issue: Wrong ID Format

**Symptoms:**
```
ValidationError: 1 validation error for MCPServer
id
  String should match pattern '^mcp_server-[a-fA-F0-9]{8}'
```

**Cause:** ID using hyphen (`mcp-server-`) instead of underscore (`mcp_server-`)

**Solution:**
```bash
# Delete incorrect entry
docker exec letta-postgres psql -U letta -d letta \
  -c "DELETE FROM mcp_server WHERE id LIKE 'mcp-server-%';"

# Restart to recreate with correct format
docker restart letta-server
```

### Issue: Tools Not Appearing in Agent

**Symptoms:**
- Agent has MCP server attached
- Tools still don't appear in agent's toolset

**Causes:**
1. MCP server not attached via ADE
2. Agent cache not refreshed
3. MCP server connectivity issues

**Solutions:**
```bash
# 1. Verify MCP server is accessible
curl http://localhost:8082/health

# 2. Check Letta can reach MCP server (from inside container)
docker exec letta-server curl http://thoth-mcp:8000/health

# 3. Attach via ADE (recommended for Letta 0.16+)
#    - Open http://localhost:8284
#    - Edit agent
#    - Add MCP server in UI
#    - Save

# 4. Or use attachment script
python3 scripts/attach-mcp-to-agents.py
```

### Issue: MCP Server Connection Refused

**Symptoms:**
```
Warning: Cannot connect to Thoth MCP server at http://thoth-mcp:8000
```

**Causes:**
1. Thoth MCP container not running
2. Wrong Docker network
3. Port conflicts

**Solutions:**
```bash
# Check Thoth MCP container status
docker ps | grep thoth-mcp

# Check logs
docker logs thoth-dev-mcp

# Verify network connectivity
docker exec letta-server ping -c 1 thoth-mcp

# Restart if needed
docker restart thoth-dev-mcp
```

### Issue: Empty Tool List

**Symptoms:**
```bash
curl http://localhost:8283/v1/mcp-servers/mcp_server-.../tools
# Returns: []
```

**Causes:**
1. Tools not synced from MCP server
2. Letta version doesn't support automatic sync

**Solutions:**
```bash
# For Letta 0.16+, tools are loaded dynamically when agent uses MCP server
# No pre-syncing required - tools are fetched on-demand

# Verify Thoth MCP server has tools
curl -s http://localhost:8082/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | jq '.result.tools | length'

# Should return: 60
```

---

## Migration Process

### When Upgrading Letta

The `scripts/letta-migrate.sh` script handles MCP server configuration:

**Migration Steps:**
1. Backup all agents (including MCP attachments)
2. Drop and recreate database
3. Start new Letta version (auto-registers MCP server)
4. Restore agents with `restore-agents-complete.py` (auto-attaches MCP)

**MCP-Specific Steps:**
```bash
# Run full migration
./scripts/letta-migrate.sh 0.16.3

# Or manually restore agents after migration
python3 scripts/restore-agents-complete.py ~/letta-backup-YYYYMMDD http://localhost:8283

# Verify all agents have MCP server
python3 scripts/attach-mcp-to-agents.py
```

### What Gets Preserved

**Preserved:**
- MCP server URL and configuration
- Server name and transport type
- Agent MCP server attachments (if using restore script)

**Not Preserved:**
- MCP server database ID (regenerated with new UUID)
- Tool cache (tools fetched dynamically)

### Post-Migration Verification

```bash
# 1. Check MCP server registered
curl -s http://localhost:8283/v1/mcp-servers/ \
  -H "Authorization: Bearer letta_dev_password" | jq '.[].server_name'

# 2. Check agents have MCP server
python3 scripts/attach-mcp-to-agents.py

# 3. Test tool availability
curl -s http://localhost:8082/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  | jq '.result.tools[0]'
```

---

## Best Practices

1. **Always use the attachment script after database resets**
   - Run `attach-mcp-to-agents.py` after migrations
   - Verify all agents have MCP server attached

2. **Use the restore script for agent migrations**
   - `restore-agents-complete.py` handles MCP attachment automatically
   - Includes MCP status in output

3. **Monitor MCP server health**
   - Regularly check `/health` endpoint
   - Watch for connectivity issues in logs

4. **Keep ID format correct**
   - Always use `mcp_server-` prefix (underscore!)
   - Never use `mcp-server-` (hyphen)

5. **Document custom MCP servers**
   - Add server details to `.env.letta`
   - Update this documentation with new servers

---

## Quick Reference

### Key Files

- `/docker/letta/init-schema.sh` - MCP server registration on startup
- `/scripts/attach-mcp-to-agents.py` - Bulk attachment script
- `/scripts/restore-agents-complete.py` - Agent restoration with MCP
- `/.env.letta` - Environment configuration
- `/docker/letta/init-mcp-config.sh` - MCP config file generation (legacy)

### Key Endpoints

- Letta API: `http://localhost:8283/v1/`
- Letta ADE: `http://localhost:8284`
- Thoth MCP (internal): `http://thoth-mcp:8000/mcp`
- Thoth MCP (external): `http://localhost:8082/mcp`

### Quick Commands

```bash
# Register MCP server (automatic on container start)
docker restart letta-server

# Attach to all agents
python3 scripts/attach-mcp-to-agents.py

# Verify MCP server
curl http://localhost:8082/health

# List MCP servers
curl -H "Authorization: Bearer letta_dev_password" \
  http://localhost:8283/v1/mcp-servers/ | jq

# Check agent MCP attachment
curl -H "Authorization: Bearer letta_dev_password" \
  "http://localhost:8283/v1/agents/{agent_id}" | jq '.mcp_server_ids'
```

---

## See Also

- [AGENT_RESTORATION.md](./AGENT_RESTORATION.md) - Agent backup and restoration
- [LETTA_MIGRATION_2026-01-17.md](./LETTA_MIGRATION_2026-01-17.md) - Letta upgrade process
- [Letta MCP Documentation](https://docs.letta.com/guides/mcp/setup/)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)

---

**Last Updated:** January 24, 2026
**Letta Version:** 0.16.3
**Thoth Version:** 2024.12
