# Letta ADE MCP Tools Troubleshooting Guide

## Problem

Thoth MCP tools were not visible in Letta Agent Development Environment (ADE), preventing agents from accessing the 68 research tools provided by the Thoth MCP server.

## Root Cause

The issue had two components:

1. **Missing MCP Server Configuration**: Letta ADE was not configured to connect to the Thoth MCP server
2. **Incorrect Endpoint URL**: The initial configuration had the wrong port and endpoint path

## Solution

### 1. MCP Server Configuration File

Letta stores MCP server configurations in `/letta/.letta/mcp-servers.json` (inside the Docker container).

**Correct Configuration:**
```json
{
  "servers": {
    "thoth": {
      "name": "Thoth Research MCP Server",
      "description": "Access all 68 Thoth research tools dynamically via MCP protocol",
      "enabled": true,
      "transport": "sse",
      "url": "http://thoth-mcp:8000/mcp",
      "connection": {
        "timeout": 30,
        "read_timeout": 300,
        "max_retries": 3
      },
      "health_check": {
        "enabled": true,
        "interval": 60,
        "endpoint": "http://thoth-mcp:8000/health"
      }
    }
  }
}
```

**Key Points:**
- **Port**: `8000` (HTTP transport port with streaming support)
- **Endpoint**: `/mcp` (POST endpoint for MCP requests)
- **Transport**: `sse` (Server-Sent Events over HTTP)
- **Docker Network**: Use `thoth-mcp` hostname (Docker bridge network resolution)

### 2. Thoth MCP Server Endpoints

The Thoth MCP server HTTP transport (port 8000) exposes:

```
Port 8000 (HTTP Transport - Handles everything):
  - POST /mcp      → Send MCP requests (tools/list, tools/call, etc.)
  - GET  /sse      → Subscribe to SSE event stream
  - GET  /health   → Health check

Note: Port 8001 runs a separate SSE-only transport but is not used by Letta.
The HTTP transport on port 8000 handles both requests AND streaming.
```

**Letta Configuration Mapping:**
- Letta `url` field → `http://thoth-mcp:8000/mcp` (POST endpoint)
- Letta `health_check.endpoint` → `http://thoth-mcp:8000/health`

### 3. Docker Networking

Both containers must be on the same Docker network:

```bash
# Check network connectivity
docker network inspect letta-network

# Should show both:
# - letta-server (172.22.0.x)
# - thoth-mcp (172.22.0.x)
```

**Connection Test from Letta Container:**
```bash
docker exec letta-server curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
  http://thoth-mcp:8000/mcp
```

Should return 68 tools.

## Step-by-Step Fix

### Method 1: Automated Script

```bash
cd /home/nick-hallmark/Documents/python/project-thoth
python3 scripts/configure_letta_mcp.py
```

### Method 2: Manual Configuration

1. **Update MCP Configuration:**
```bash
docker exec -it letta-server vi /letta/.letta/mcp-servers.json
```

Update the `thoth` server configuration with the correct URL.

2. **Restart Letta:**
```bash
docker compose -f docker-compose.letta.yml restart letta
```

3. **Wait for Startup:**
```bash
# Wait ~30-40 seconds for Letta to fully restart
sleep 40

# Check health
curl http://localhost:8283/v1/health
```

4. **Verify MCP Connection:**
```bash
docker logs letta-server 2>&1 | grep -i "mcp"
```

## Verification

### 1. Test MCP Server Directly

```bash
# From host (port 8082 is mapped to container 8000)
curl -X POST http://localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Should return 68 tools
```

### 2. Test via Letta Agent

```bash
python3 scripts/test_mcp_tools_via_letta.py
```

Should show agents can now call MCP tools.

### 3. Check Letta Web UI

1. Open http://localhost:8283
2. Login with `admin` / `letta_dev_password`
3. Go to agent settings
4. Tools should now include all Thoth MCP tools (search_articles, process_pdf, etc.)

## Common Issues

### Issue: "MCP server not responding"

**Symptoms:**
- Letta logs show connection timeouts
- No MCP tools visible in ADE

**Solutions:**
1. Check if thoth-mcp container is running: `docker ps | grep thoth-mcp`
2. Verify network connectivity: Both containers on `letta-network`
3. Test direct connection from Letta container:
   ```bash
   docker exec letta-server curl http://thoth-mcp:8000/health
   ```

### Issue: "Wrong endpoint / 405 Method Not Allowed"

**Symptoms:**
- Logs show `POST /sse 405 Method Not Allowed`

**Solution:**
- Update URL to use `/mcp` endpoint, not `/sse`
- The `/sse` endpoint is GET-only for event streaming

### Issue: "Tools not appearing after configuration"

**Solutions:**
1. Ensure Letta was restarted AFTER configuration change
2. Clear browser cache and reload Letta ADE
3. Check agent's tool configuration hasn't cached old tool list
4. Verify `mcp-servers.json` has `"enabled": true`

## Architecture Reference

```
User (Letta ADE) → Letta Server (8283)
                        ↓
                   [MCP Protocol]
                        ↓
                   Thoth MCP Server
                   - Port 8000: HTTP transport (streaming)
                   - POST /mcp: Request endpoint
                   - GET /sse: Event stream
                   - GET /health: Health check
                        ↓
                   [68 Research Tools]
                   - Discovery tools
                   - Citation tools
                   - Processing tools
                   - Analysis tools
                   - RAG/search tools
```

## Maintenance

### Updating MCP Configuration

1. Stop Letta: `docker compose -f docker-compose.letta.yml stop letta`
2. Edit config: `docker exec letta-server vi /letta/.letta/mcp-servers.json`
3. Start Letta: `docker compose -f docker-compose.letta.yml start letta`

### Adding New MCP Servers

Add to the `servers` object in `mcp-servers.json`:

```json
{
  "servers": {
    "thoth": { ... },
    "my-new-server": {
      "name": "My MCP Server",
      "enabled": true,
      "transport": "sse",
      "url": "http://my-server:8000/mcp"
    }
  }
}
```

## Scripts

- **configure_letta_mcp.py**: Automated configuration tool
- **test_mcp_tools_via_letta.py**: Verify tools are accessible
- **scripts/register_mcp_server.py**: Legacy registration (not needed with mcp-servers.json)

## Further Reading

- [MCP Architecture](./MCP_ARCHITECTURE.md)
- [Letta Agent Integration](./LETTA_AGENT_INTEGRATION.md)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
