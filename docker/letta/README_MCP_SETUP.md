# Letta MCP Auto-Configuration

This directory contains scripts for automatically configuring Letta to connect to the Thoth MCP server.

## How It Works

When Letta starts via `docker-compose.letta.yml`, two init scripts run:

1. **init-mcp-config.sh** - Configures MCP server connection
   - Creates `/letta/.letta/mcp-servers.json` if missing
   - Adds Thoth MCP server configuration
   - Tests connectivity to `thoth-mcp:8000`
   
2. **init-schema.sh** - Initializes Letta database schema  
   - Creates necessary database tables
   - Runs Letta's standard startup

## MCP Configuration

The auto-generated configuration in `/letta/.letta/mcp-servers.json`:

```json
{
  "servers": {
    "thoth": {
      "name": "Thoth Research MCP Server",
      "description": "Access all 68 Thoth research tools",
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

**Key Settings:**
- **URL**: `http://thoth-mcp:8000/mcp` - HTTP transport with SSE streaming
- **Transport**: `sse` - Server-Sent Events for real-time communication
- **Network**: Both containers must be on `letta-network`

## Port Configuration

**Internal Docker Network (Letta → Thoth MCP):**
- Port 8000: HTTP transport with SSE streaming support

**External Access (Host → Thoth MCP):**
- Port 8082: Maps to internal 8000 (HTTP transport - includes /mcp and /sse endpoints)
- Port 8082: Maps to internal 8000 (HTTP transport with /mcp and /sse endpoints)

## Verifying Setup

### 1. Check MCP Configuration

```bash
docker exec letta-server cat /letta/.letta/mcp-servers.json
```

Should show Thoth server configuration.

### 2. Test Connectivity

```bash
# From inside Letta container
docker exec letta-server curl http://thoth-mcp:8000/health

# Should return: {"status":"healthy"}
```

### 3. Test MCP Tools

```bash
# From host machine
curl -X POST http://localhost:8082/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

# Should return 68 tools
```

### 4. Check Letta Logs

```bash
docker logs letta-server | grep -i mcp

# Should show MCP server discovery and connection
```

## Troubleshooting

### MCP Tools Not Appearing

**Symptom**: Letta ADE doesn't show Thoth tools

**Solutions**:
1. Verify both containers on same network:
   ```bash
   docker network inspect letta-network
   # Should show both letta-server and thoth-mcp
   ```

2. Restart Letta:
   ```bash
   docker compose -f docker-compose.letta.yml restart letta
   ```

3. Check MCP server is running:
   ```bash
   docker ps | grep thoth-mcp
   ```

### Connection Refused

**Symptom**: `Connection refused to thoth-mcp:8000`

**Solutions**:
1. Ensure thoth-mcp is on letta-network:
   ```bash
   docker inspect thoth-mcp | grep letta-network
   ```

2. Add to docker-compose.yml if missing:
   ```yaml
   thoth-mcp:
     networks:
       - letta-network
   ```

3. Restart both services:
   ```bash
   docker compose up -d thoth-mcp
   docker compose -f docker-compose.letta.yml restart letta
   ```

### Wrong Port Error

**Symptom**: Using port 8001 instead of 8000

**Solution**: Update MCP URL to `http://thoth-mcp:8000/mcp`
- Port 8000 is the only port (HTTP transport includes /mcp POST and /sse streaming)
- Port 8001 no longer exists (removed redundant SSE-only transport)
- Port 8001 is SSE-only transport (legacy)

## Manual Configuration

If auto-configuration fails, manually create the config:

```bash
docker exec -it letta-server bash
mkdir -p /letta/.letta
cat > /letta/.letta/mcp-servers.json << 'EOF'
{
  "servers": {
    "thoth": {
      "name": "Thoth Research MCP Server",
      "enabled": true,
      "transport": "sse",
      "url": "http://thoth-mcp:8000/mcp",
      "health_check": {
        "endpoint": "http://thoth-mcp:8000/health"
      }
    }
  }
}
EOF
exit
```

Then restart Letta:
```bash
docker compose -f docker-compose.letta.yml restart letta
```

## Environment Variables

The init script uses:
- `THOTH_MCP_URL` - Defaults to `http://thoth-mcp:8000`

Set in `docker-compose.letta.yml`:
```yaml
environment:
  - THOTH_MCP_URL=http://thoth-mcp:8000
```

## Files

- `init-mcp-config.sh` - MCP configuration script
- `init-schema.sh` - Letta database initialization
- `README_MCP_SETUP.md` - This file

## References

- [Letta MCP Troubleshooting](../../docs/LETTA_MCP_TROUBLESHOOTING.md)
- [MCP Architecture](../../docs/MCP_ARCHITECTURE.md)
- [Docker Deployment](../../docs/DOCKER_DEPLOYMENT.md)
