# Exposing Thoth MCP Server to Letta Cloud

This guide explains how to make your self-hosted Thoth MCP server accessible to Letta Cloud agents, enabling them to use all 54 Thoth research tools.

## Overview

**What Works:**
- ✅ **Letta Folders** - Already works with cloud! Upload vault files via API
- ⚠️ **MCP Tools** - Requires public URL (Letta Cloud can't reach localhost)

**Architecture:**
```
Letta Cloud Agents
    ↓ HTTPS
Public URL (ngrok/cloud)
    ↓ HTTP
Thoth MCP Server (localhost:8001)
    ↓
Your Vault & Research Tools
```

## Authentication

Thoth MCP server now supports **Bearer token authentication** for secure external access.

### Setting Up Authentication

**Option 1: Environment Variable (Recommended)**
```bash
export THOTH_MCP_AUTH_TOKEN="your-secure-random-token-here"
```

**Option 2: Programmatically**
```python
from thoth.mcp.server import create_mcp_server
from thoth.services.service_manager import ServiceManager

manager = ServiceManager()
server = create_mcp_server(
    manager,
    auth_token="your-secure-random-token-here"
)
```

**Generate a secure token:**
```bash
# Using Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Using OpenSSL
openssl rand -base64 32
```

## Exposure Methods

### Method 1: Ngrok (Easiest for Development)

**Setup:**
```bash
# 1. Install ngrok
npm install -g ngrok
# or
brew install ngrok

# 2. Start Thoth MCP server with auth
export THOTH_MCP_AUTH_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
python -m thoth mcp start

# 3. In another terminal, expose port 8001
ngrok http 8001

# 4. Note the public URL (e.g., https://abc123.ngrok.io)
```

**Pros:**
- Quick setup (2 minutes)
- Automatic HTTPS
- No infrastructure costs

**Cons:**
- URL changes on restart (free tier)
- Requires ngrok running
- May have bandwidth limits

### Method 2: Tailscale Funnel (Best for Existing Tailscale Users)

If you already use Tailscale for remote access, Funnel is the easiest option!

**Setup:**
```bash
# 1. Enable Funnel for your machine (one-time)
tailscale funnel status
# If not enabled, follow prompts to enable

# 2. Start Thoth MCP server with auth
export THOTH_MCP_AUTH_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
python -m thoth mcp start

# 3. Expose port 8001 via Funnel
tailscale funnel 8001

# 4. Get your public URL
tailscale funnel status
# Shows: https://your-machine.your-tailnet.ts.net
```

**Configure in Letta Cloud:**
```python
mcp_server = client.mcp_servers.create(
    server_name="thoth-research",
    config={
        "mcp_server_type": "sse",
        "server_url": "https://your-machine.your-tailnet.ts.net/sse",
        "auth_header": "Authorization",
        "auth_token": f"Bearer {THOTH_MCP_AUTH_TOKEN}"
    }
)
```

**Pros:**
- ✅ **Stable URL** (doesn't change)
- ✅ **Automatic HTTPS** (Let's Encrypt)
- ✅ **Free** (included with Tailscale)
- ✅ **Fast setup** if you already use Tailscale
- ✅ **Better performance** than ngrok (direct peering)
- ✅ **No domain needed** (uses .ts.net subdomain)

**Cons:**
- Requires Tailscale installed (you already have this!)
- Funnel must stay enabled

**Perfect for your use case** since you already use Tailscale for server access!

**Tailscale Serve vs Funnel:**
- **Serve** - Only accessible within your Tailscale network (private)
- **Funnel** - Publicly accessible on the internet (what you need for Letta Cloud)

**Keeping Funnel Running:**
```bash
# Option 1: Run in tmux/screen
tmux new -s tailscale-funnel
tailscale funnel 8001
# Ctrl+B, D to detach

# Option 2: Systemd service
cat > /etc/systemd/system/tailscale-funnel-thoth.service <<EOF
[Unit]
Description=Tailscale Funnel for Thoth MCP
After=network.target tailscaled.service

[Service]
Type=simple
ExecStart=/usr/bin/tailscale funnel --bg 8001
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl enable tailscale-funnel-thoth
systemctl start tailscale-funnel-thoth
```

### Method 3: Cloudflare Tunnel (Free, Stable URL)

**Setup:**
```bash
# 1. Install cloudflared
brew install cloudflare/cloudflare/cloudflared
# or download from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/

# 2. Login
cloudflared tunnel login

# 3. Create tunnel
cloudflared tunnel create thoth-mcp

# 4. Configure tunnel
cat > ~/.cloudflared/config.yml <<EOF
tunnel: thoth-mcp
credentials-file: /path/to/credentials.json
ingress:
  - hostname: thoth-mcp.yourdomain.com
    service: http://localhost:8001
  - service: http_status:404
EOF

# 5. Create DNS record
cloudflared tunnel route dns thoth-mcp thoth-mcp.yourdomain.com

# 6. Run tunnel
cloudflared tunnel run thoth-mcp
```

**Pros:**
- Free tier
- Stable URL (your domain)
- Automatic HTTPS
- Better performance than ngrok

**Cons:**
- Requires domain name
- More setup steps

### Method 3: Cloud Deployment (Production)

Deploy Thoth MCP server as a standalone service.

**AWS Example (EC2 + ALB):**
```bash
# 1. Create EC2 instance
# 2. Install Thoth
# 3. Configure systemd service
cat > /etc/systemd/system/thoth-mcp.service <<EOF
[Unit]
Description=Thoth MCP Server
After=network.target

[Service]
Type=simple
User=thoth
WorkingDirectory=/opt/thoth
Environment="THOTH_MCP_AUTH_TOKEN=your-token-here"
ExecStart=/usr/bin/python3 -m thoth mcp start
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 4. Enable and start
systemctl enable thoth-mcp
systemctl start thoth-mcp

# 5. Configure ALB with SSL certificate
# 6. Point to EC2 instance
```

**Pros:**
- Production-grade
- Full control
- Scalable

**Cons:**
- Ongoing costs
- Requires cloud expertise
- More maintenance

### Method 4: Docker + Reverse Proxy

Use Docker Compose with Nginx reverse proxy.

**docker-compose.yml:**
```yaml
version: '3.8'

services:
  thoth-mcp:
    build: .
    environment:
      - THOTH_MCP_AUTH_TOKEN=${THOTH_MCP_AUTH_TOKEN}
    ports:
      - "8001:8001"

  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - thoth-mcp
```

**nginx.conf:**
```nginx
server {
    listen 443 ssl;
    server_name mcp.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    location / {
        proxy_pass http://thoth-mcp:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # SSE support
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
    }
}
```

## Configuring Letta Cloud

Once your MCP server is publicly accessible, configure it in Letta Cloud:

### Via Python SDK

```python
from letta_client import Letta
import os

client = Letta(api_key=os.getenv("LETTA_API_KEY"))

# Create MCP server connection
mcp_server = client.mcp_servers.create(
    server_name="thoth-research",
    config={
        "mcp_server_type": "sse",  # or "streamable_http"
        "server_url": "https://your-public-url.ngrok.io/sse",  # or /mcp for HTTP
        "auth_header": "Authorization",
        "auth_token": f"Bearer {os.getenv('THOTH_MCP_AUTH_TOKEN')}"
    }
)

# List available tools
tools = client.mcp_servers.tools.list(mcp_server.id)
print(f"Found {len(tools)} Thoth research tools")

# Attach tools to an agent
agent = client.agents.create(
    name="Research Assistant",
    tools=[tool.id for tool in tools[:10]]  # Attach first 10 tools
)
```

### Via Letta ADE (Web UI)

1. Go to https://app.letta.com
2. Navigate to **Tool Manager** → **Add MCP Server**
3. Choose **SSE** or **Streamable HTTP**
4. Configure:
   - **Server Name**: `thoth-research`
   - **Server URL**: Your public URL + `/sse` (or `/mcp` for HTTP)
   - **Auth Header**: `Authorization`
   - **Auth Token**: `Bearer your-token-here`
5. Click **Test Connection**
6. Click **Save**
7. Go to **Agents** → Your Agent → **Tools** → Select Thoth tools

## Transport Types

Thoth MCP server supports both transports Letta Cloud accepts:

### SSE (Server-Sent Events) - Port 8001
```
POST /mcp       - JSON-RPC requests
GET  /sse       - SSE stream
GET  /health    - Health check
```

**Best for:** Real-time updates, Letta's primary transport

### HTTP (Streamable HTTP) - Port 8002  
```
POST /mcp       - JSON-RPC requests
GET  /health    - Health check
```

**Best for:** Simple request-response, easier debugging

**Recommendation:** Use SSE (port 8001) as it's Letta's primary transport.

## Security Best Practices

1. **Always use authentication** for public exposure
   ```bash
   export THOTH_MCP_AUTH_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   ```

2. **Use HTTPS** (ngrok/cloudflare provide this automatically)

3. **Rotate tokens regularly**
   ```bash
   # Generate new token
   NEW_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
   
   # Update Letta Cloud config
   client.mcp_servers.update(server_id, auth_token=f"Bearer {NEW_TOKEN}")
   
   # Update Thoth
   export THOTH_MCP_AUTH_TOKEN=$NEW_TOKEN
   systemctl restart thoth-mcp
   ```

4. **Limit exposed ports** - Only expose MCP ports (8001/8002), not PostgreSQL, etc.

5. **Monitor access logs**
   ```bash
   # Thoth logs show auth failures
   tail -f ~/.thoth/logs/mcp.log | grep "Unauthorized"
   ```

## Troubleshooting

### Connection Refused
```
Error: Failed to connect to MCP server
```

**Solution:**
- Check if tunnel is running: `curl https://your-url.ngrok.io/health`
- Verify Thoth MCP server is running: `curl http://localhost:8001/health`
- Check firewall rules

### Authentication Failed
```
Error: 401 Unauthorized
```

**Solution:**
- Verify token matches on both sides
- Check Bearer prefix is included: `Bearer your-token`
- Ensure token doesn't have extra whitespace

### Tools Not Showing
```
Found 0 tools from server
```

**Solution:**
- Check Thoth MCP server logs: `tail -f ~/.thoth/logs/mcp.log`
- Verify server is initialized: `curl http://localhost:8001/health`
- Try reconnecting: Delete and recreate MCP server connection

### SSE Stream Disconnects
```
Error: SSE connection closed
```

**Solution:**
- Some tunnels have timeout limits (ngrok free tier: 2 hours)
- Use Cloudflare Tunnel or cloud deployment for production
- Check nginx configuration has SSE support (proxy_buffering off)

## Testing Your Setup

```bash
# 1. Test health locally
curl http://localhost:8001/health

# 2. Test health via tunnel
curl https://your-url.ngrok.io/health

# 3. Test authentication locally
curl -H "Authorization: Bearer wrong-token" http://localhost:8001/health
# Should return 401 Unauthorized

# 4. Test with correct token
curl -H "Authorization: Bearer $THOTH_MCP_AUTH_TOKEN" http://localhost:8001/health
# Should return 200 OK

# 5. Test MCP endpoint
curl -X POST https://your-url.ngrok.io/mcp \
  -H "Authorization: Bearer $THOTH_MCP_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
# Should return list of 54 Thoth tools
```

## Cost Comparison

| Method | Setup Time | Monthly Cost | Stability | Best For |
|--------|-----------|--------------|-----------|----------|
| **Tailscale Funnel** | **2 min** | **$0** | **High** | **Existing Tailscale users** ⭐ |
| Ngrok (free) | 5 min | $0 | Medium (URL changes) | Quick testing |
| Ngrok (paid) | 5 min | $8-25 | High (fixed URL) | Simple setup with support |
| Cloudflare Tunnel | 15 min | $0 | High | Custom domain needed |
| AWS EC2 (t3.micro) | 1 hour | $7-10 | High | Production, full control |
| DigitalOcean Droplet | 30 min | $6 | High | Production, simpler than AWS |

## Recommended Setup Path

**If you already use Tailscale (like you do!):**
```bash
# 1. Generate auth token
export THOTH_MCP_AUTH_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
echo "Save this token: $THOTH_MCP_AUTH_TOKEN"

# 2. Start Thoth MCP
python -m thoth mcp start

# 3. Expose via Tailscale Funnel
tailscale funnel 8001

# 4. Get your URL
tailscale funnel status
# Note: https://your-machine.your-tailnet.ts.net

# 5. Configure in Letta Cloud at https://app.letta.com
```

**If you don't have Tailscale:**
- Use ngrok (fastest: 5 min setup)
- Use Cloudflare Tunnel (free with domain)

## Next Steps

1. ✅ Expose MCP server with authentication (Tailscale Funnel recommended!)
2. ✅ Configure Letta Cloud connection  
3. ✅ Test tools in Letta ADE
4. 📊 Monitor usage and performance
5. 🔒 Set up token rotation schedule
6. 📈 Scale if needed (multiple workers, load balancer)

## Support

**Issues:**
- Thoth MCP: https://github.com/acertainKnight/project-thoth/issues
- Letta: https://discord.gg/letta

**Docs:**
- Letta MCP: https://docs.letta.com/guides/mcp/remote
- Thoth: https://github.com/acertainKnight/project-thoth/docs
