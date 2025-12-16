# Letta Remote ADE Access Guide

## Overview

This guide provides comprehensive instructions for accessing your Letta container remotely through the [Agent Development Environment (ADE)](https://app.letta.com). Remote access requires HTTPS for security, with multiple setup options depending on your infrastructure.

## Prerequisites

- Docker container running Letta server
- Port 8283 accessible (Letta default API port)
- PostgreSQL database (included in Docker setup)
- Domain name (optional, for permanent HTTPS setup)

## Understanding the HTTPS Requirement

**Critical**: Letta's web ADE at https://app.letta.com **requires HTTPS** for remote connections. HTTP is only allowed for `localhost` connections.

### Why HTTPS?

- Browser security policies block mixed content (HTTPS page connecting to HTTP endpoint)
- Protects sensitive data (API keys, agent configurations, chat history)
- Prevents man-in-the-middle attacks
- Required by modern browsers for production applications

### Exception: SSH Port Forwarding

SSH tunneling is the **only method** that bypasses the HTTPS requirement, as it makes remote servers appear as `localhost` to your browser.

---

## Docker Setup

Ensure your Letta container is running with the correct port mappings:

```bash
docker run -d \
  --name letta-server \
  -p 8283:8283 \
  -p 5432:5432 \
  -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
  -e OPENAI_API_KEY=your_openai_key \
  -e ANTHROPIC_API_KEY=your_anthropic_key \
  letta/letta:latest
```

### Linux-Specific Networking

On Linux, use `--network host` for simpler networking:

```bash
docker run -d \
  --name letta-server \
  --network host \
  -v ~/.letta/.persist/pgdata:/var/lib/postgresql/data \
  -e OPENAI_API_KEY=your_openai_key \
  letta/letta:latest
```

---

## Option 1: SSH Port Forwarding (Recommended for Development)

**Best for**: Quick testing, development, bypassing HTTPS requirement

### Advantages
- ✅ Bypasses HTTPS requirement (appears as localhost)
- ✅ No certificates needed
- ✅ Encrypted through SSH tunnel
- ✅ Works immediately
- ✅ No firewall configuration needed

### Setup Steps

1. **On your local machine**, establish SSH tunnel:

```bash
ssh -L 8283:localhost:8283 user@your-server-ip
```

2. **Keep the SSH session open** in a terminal

3. **Access Letta ADE** at https://app.letta.com

4. **Add server connection**:
   - Server name: `My Development Server`
   - Server URL: `http://localhost:8283` (HTTP is allowed for localhost)
   - Password: (leave blank if no password set)

### Advanced: Background Tunnel

Run tunnel in background:

```bash
ssh -f -N -L 8283:localhost:8283 user@your-server-ip
```

Stop background tunnel:

```bash
# Find the process
ps aux | grep "ssh.*8283"

# Kill the process
kill <PID>
```

### SSH Config for Convenience

Add to `~/.ssh/config`:

```
Host letta-tunnel
    HostName your-server-ip
    User your-username
    LocalForward 8283 localhost:8283
    ServerAliveInterval 60
```

Then simply run:

```bash
ssh letta-tunnel
```

---

## Option 2: ngrok Tunnel (Quick HTTPS Solution)

**Best for**: Quick demos, temporary access, testing

### Advantages
- ✅ Instant HTTPS without certificates
- ✅ No domain name required
- ✅ Easy setup

### Disadvantages
- ❌ URL changes on restart (free tier)
- ❌ Rate limits on free tier
- ❌ Adds latency
- ❌ Not suitable for production

### Setup Steps

1. **Install ngrok**:

```bash
# Visit https://ngrok.com and sign up
# Download and install ngrok
curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | \
  sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && \
  echo "deb https://ngrok-agent.s3.amazonaws.com buster main" | \
  sudo tee /etc/apt/sources.list.d/ngrok.list && \
  sudo apt update && sudo apt install ngrok
```

2. **Authenticate ngrok**:

```bash
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

3. **Start ngrok tunnel**:

```bash
ngrok http 8283
```

4. **Copy the HTTPS URL** from ngrok output:

```
Forwarding  https://abc123.ngrok.io -> http://localhost:8283
```

5. **Add to Letta ADE**:
   - Server name: `ngrok Server`
   - Server URL: `https://abc123.ngrok.io`
   - Password: (your Letta password if set)

### ngrok Configuration File

Create `~/.ngrok/ngrok.yml` for persistent settings:

```yaml
version: "2"
authtoken: YOUR_NGROK_TOKEN
tunnels:
  letta:
    proto: http
    addr: 8283
    subdomain: my-letta-server  # Requires paid plan
```

Run with:

```bash
ngrok start letta
```

---

## Option 3: Caddy Reverse Proxy (Production HTTPS)

**Best for**: Production deployments, permanent setup

### Advantages
- ✅ Automatic HTTPS certificates (Let's Encrypt)
- ✅ Professional setup
- ✅ Custom domain
- ✅ High performance

### Disadvantages
- ❌ Requires domain name
- ❌ DNS configuration needed
- ❌ More complex setup

### Prerequisites

- Domain name pointing to your server (A record)
- Port 80 and 443 open on firewall

### Installation

```bash
# Debian/Ubuntu
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### Caddy Configuration

Create `/etc/caddy/Caddyfile`:

```caddy
letta.yourdomain.com {
    reverse_proxy localhost:8283

    # Security headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        X-XSS-Protection "1; mode=block"
    }

    # Optional: IP allowlist
    # @allowed {
    #     remote_ip 203.0.113.0/24
    # }
    # handle @allowed {
    #     reverse_proxy localhost:8283
    # }
}
```

### Start Caddy

```bash
sudo systemctl enable caddy
sudo systemctl start caddy
sudo systemctl status caddy
```

### Add to Letta ADE

- Server name: `Production Letta`
- Server URL: `https://letta.yourdomain.com`
- Password: (your Letta password)

---

## Option 4: nginx with Let's Encrypt

**Best for**: Existing nginx infrastructure, advanced configurations

### Installation

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

### nginx Configuration

Create `/etc/nginx/sites-available/letta`:

```nginx
server {
    listen 80;
    server_name letta.yourdomain.com;

    location / {
        return 301 https://$server_name$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name letta.yourdomain.com;

    # Certificates (will be added by certbot)
    ssl_certificate /etc/letsencrypt/live/letta.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/letta.yourdomain.com/privkey.pem;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://localhost:8283;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_read_timeout 86400;
    }
}
```

### Enable Site and Get Certificate

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/letta /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d letta.yourdomain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

---

## Firewall Configuration

### UFW (Ubuntu Firewall)

```bash
# For SSH tunnel only
sudo ufw allow 22/tcp

# For HTTPS access
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# For direct access (not recommended without authentication)
# sudo ufw allow 8283/tcp

sudo ufw enable
sudo ufw status
```

### iptables

```bash
# Allow SSH
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Allow HTTP/HTTPS
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Save rules
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

### Cloud Provider Firewalls

**AWS Security Group**:
- SSH: Port 22 from your IP
- HTTP: Port 80 from 0.0.0.0/0
- HTTPS: Port 443 from 0.0.0.0/0

**Google Cloud Firewall**:
```bash
gcloud compute firewall-rules create allow-letta-https \
    --allow tcp:443,tcp:80 \
    --source-ranges 0.0.0.0/0 \
    --description "Allow HTTPS for Letta"
```

---

## Authentication & Security

### Enable Password Protection

Add to Docker run command:

```bash
docker run -d \
  --name letta-server \
  -p 8283:8283 \
  -e SECURE=true \
  -e LETTA_SERVER_PASSWORD=your_strong_password \
  -e OPENAI_API_KEY=your_openai_key \
  letta/letta:latest
```

Or use environment file:

```bash
# Create .env file
cat > letta.env <<EOF
SECURE=true
LETTA_SERVER_PASSWORD=your_strong_password
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
EOF

# Run with env file
docker run -d \
  --name letta-server \
  -p 8283:8283 \
  --env-file letta.env \
  letta/letta:latest
```

### API Authentication

When `SECURE=true`, include password in requests:

```bash
curl -X GET http://localhost:8283/v1/agents \
  -H "Authorization: Bearer your_strong_password"
```

### Security Best Practices

1. **Never expose port 8283 directly** to the internet without authentication
2. **Always use HTTPS** for remote access (except SSH tunnels)
3. **Set strong passwords** (minimum 16 characters)
4. **Use environment files** instead of command-line arguments (they appear in `ps` output)
5. **Rotate API keys regularly**
6. **Enable tool sandboxing** if allowing untrusted users
7. **Monitor access logs** for suspicious activity
8. **Use IP allowlists** when possible (Caddy/nginx)
9. **Keep Docker images updated**: `docker pull letta/letta:latest`
10. **Backup database regularly**: `docker exec letta-server pg_dump -U letta > backup.sql`

### Environment Variables Reference

| Variable | Purpose | Required |
|----------|---------|----------|
| `SECURE` | Enable authentication | No (default: false) |
| `LETTA_SERVER_PASSWORD` | Server password | If SECURE=true |
| `OPENAI_API_KEY` | OpenAI integration | For OpenAI models |
| `ANTHROPIC_API_KEY` | Anthropic models | For Claude models |
| `GEMINI_API_KEY` | Google AI models | For Gemini models |
| `OLLAMA_BASE_URL` | Local Ollama server | For Ollama models |
| `LETTA_PG_URI` | External database | No (default: internal) |

---

## Connecting from Letta ADE

### Step 1: Access the ADE

Navigate to https://app.letta.com in your browser.

### Step 2: Add Server Connection

1. Click **Settings** (gear icon)
2. Click **Servers** tab
3. Click **Add Server**

### Step 3: Configure Connection

Fill in the connection details based on your setup method:

**SSH Tunnel**:
- Server name: `Development Server`
- Server URL: `http://localhost:8283`
- Password: (leave blank or enter if set)

**ngrok**:
- Server name: `ngrok Tunnel`
- Server URL: `https://abc123.ngrok.io` (your ngrok URL)
- Password: (enter if SECURE=true)

**Caddy/nginx**:
- Server name: `Production Server`
- Server URL: `https://letta.yourdomain.com`
- Password: (enter if SECURE=true)

### Step 4: Test Connection

Click **Test Connection** to verify setup. You should see:
- ✅ Connection successful
- Server version information
- Available agents list

### Step 5: Set as Default (Optional)

Click **Set as Default** to use this server automatically.

---

## Troubleshooting

### Connection Refused

**Symptoms**: "Failed to connect to server"

**Solutions**:
1. Verify Docker container is running: `docker ps`
2. Check port mapping: `docker port letta-server`
3. Test local connection: `curl http://localhost:8283/v1/health`
4. Check firewall: `sudo ufw status`

### HTTPS Required Error

**Symptoms**: "Remote servers require HTTPS"

**Solutions**:
1. Use SSH tunnel (appears as localhost)
2. Set up ngrok for instant HTTPS
3. Configure Caddy/nginx with Let's Encrypt
4. Verify URL starts with `https://` (not `http://`)

### Certificate Errors

**Symptoms**: "SSL certificate invalid"

**Solutions**:
1. Wait for Let's Encrypt propagation (up to 5 minutes)
2. Check DNS: `dig letta.yourdomain.com`
3. Verify certificates: `sudo certbot certificates`
4. Test renewal: `sudo certbot renew --dry-run`

### Authentication Failed

**Symptoms**: "Invalid credentials" or 401 error

**Solutions**:
1. Check password in Docker env: `docker exec letta-server env | grep LETTA_SERVER_PASSWORD`
2. Verify `SECURE=true` is set
3. Test API directly: `curl -H "Authorization: Bearer yourpassword" http://localhost:8283/v1/agents`

### SSH Tunnel Disconnects

**Symptoms**: Connection works then stops

**Solutions**:
1. Add keep-alive: `ssh -o ServerAliveInterval=60 -L 8283:localhost:8283 user@server`
2. Use autossh: `autossh -M 0 -L 8283:localhost:8283 user@server`
3. Add to SSH config:
   ```
   ServerAliveInterval 60
   ServerAliveCountMax 3
   ```

### Port Already in Use

**Symptoms**: "Port 8283 is already allocated"

**Solutions**:
1. Check what's using the port: `sudo lsof -i :8283`
2. Stop conflicting service: `docker stop $(docker ps -q --filter "publish=8283")`
3. Use different port: `-p 8284:8283` (update URLs accordingly)

### Database Connection Issues

**Symptoms**: "Cannot connect to PostgreSQL"

**Solutions**:
1. Check volume mount: `docker inspect letta-server | grep pgdata`
2. Verify database is running: `docker exec letta-server pg_isready`
3. Check logs: `docker logs letta-server | grep postgres`
4. Reset database (⚠️ destroys data):
   ```bash
   docker stop letta-server
   docker rm letta-server
   rm -rf ~/.letta/.persist/pgdata
   # Restart container
   ```

---

## Monitoring & Maintenance

### Check Server Health

```bash
# Health endpoint
curl http://localhost:8283/v1/health

# List agents
curl -H "Authorization: Bearer yourpassword" http://localhost:8283/v1/agents
```

### View Logs

```bash
# Real-time logs
docker logs -f letta-server

# Last 100 lines
docker logs --tail 100 letta-server

# Errors only
docker logs letta-server 2>&1 | grep ERROR
```

### Database Backup

```bash
# Backup
docker exec letta-server pg_dump -U letta -d letta > letta-backup-$(date +%Y%m%d).sql

# Restore
docker exec -i letta-server psql -U letta -d letta < letta-backup-20241213.sql
```

### Update Letta

```bash
# Pull latest image
docker pull letta/letta:latest

# Stop old container
docker stop letta-server
docker rm letta-server

# Start new container (same command as before)
docker run -d --name letta-server ...
```

### Resource Usage

```bash
# CPU and memory
docker stats letta-server

# Disk usage
docker system df
du -sh ~/.letta/.persist/pgdata
```

---

## Production Checklist

Before deploying to production:

- [ ] HTTPS configured with valid certificates
- [ ] Authentication enabled (`SECURE=true`)
- [ ] Strong password set (16+ characters)
- [ ] Firewall configured (allow 80, 443, 22 only)
- [ ] Database backups scheduled
- [ ] Monitoring set up (health checks, logs)
- [ ] API keys secured (environment files, not command-line)
- [ ] Domain name configured with DNS
- [ ] SSL/TLS certificates set to auto-renew
- [ ] Rate limiting configured (Caddy/nginx)
- [ ] IP allowlist considered
- [ ] Documentation updated with production URLs
- [ ] Disaster recovery plan documented

---

## Quick Reference

### Comparison Matrix

| Method | HTTPS | Setup Time | Cost | Production Ready | Bypass HTTPS |
|--------|-------|------------|------|------------------|--------------|
| SSH Tunnel | ✅ (via SSH) | 1 min | Free | ❌ | ✅ |
| ngrok | ✅ | 5 min | Free/Paid | ❌ | ❌ |
| Caddy | ✅ | 15 min | Free | ✅ | ❌ |
| nginx | ✅ | 30 min | Free | ✅ | ❌ |

### Command Quick Reference

```bash
# Start Letta with authentication
docker run -d --name letta-server -p 8283:8283 \
  -e SECURE=true -e LETTA_SERVER_PASSWORD=password \
  letta/letta:latest

# SSH tunnel
ssh -L 8283:localhost:8283 user@server

# ngrok
ngrok http 8283

# Test connection
curl http://localhost:8283/v1/health

# View logs
docker logs -f letta-server

# Backup database
docker exec letta-server pg_dump -U letta > backup.sql
```

---

## Additional Resources

- [Letta ADE Setup Guide](https://docs.letta.com/guides/ade/setup/)
- [Letta Docker Guide](https://docs.letta.com/guides/server/docker)
- [Letta Remote Server Guide](https://docs.letta.com/guides/server/remote)
- [Letta Self-Hosting Guide](https://docs.letta.com/guides/selfhosting)
- [Letta Troubleshooting](https://docs.letta.com/guides/ade/troubleshooting)
- [Caddy Documentation](https://caddyserver.com/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [ngrok Documentation](https://ngrok.com/docs)

---

**Created**: 2025-12-13
**Last Updated**: 2025-12-13
**Version**: 1.0
**Maintainer**: Project Thoth Development Team
