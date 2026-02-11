# Using Thoth on iOS/Android Mobile

The Thoth Obsidian plugin works perfectly on iOS and Android! The entire UX (chat, research, UI) is available on mobile by connecting to a Thoth server running elsewhere.

## How It Works

```
┌─────────────────────┐
│  Desktop/Server     │
│  Running Thoth      │ ← Backend services
│  (via thoth start)  │
└──────────┬──────────┘
           │
           │ HTTP/WebSocket
           │
┌──────────▼──────────┐
│  Mobile Device      │
│  Obsidian + Plugin  │ ← Full UX
│  (Connected)        │
└─────────────────────┘
```

**What runs where:**
- **Server** (desktop/cloud): All Thoth services (API, MCP, Letta, processing)
- **Mobile**: Only the UI/UX (chat interface, research queries, all visual features)

## Setup Guide

### Step 1: Set Up Server

On your desktop/server where Thoth is installed:

```bash
# Start Thoth services
cd /path/to/project-thoth
thoth start

# The services are now running on:
# - API: http://localhost:8000
# - MCP: http://localhost:8001
```

### Step 2: Expose Server to Mobile

You need to make your Thoth server accessible from your mobile device. Choose one method:

#### Option A: Tailscale Funnel (Recommended)

If you already use Tailscale:

```bash
# On your server
tailscale funnel 8000

# Get your Tailscale hostname
tailscale status
# Look for: your-machine.tail1234.ts.net
```

Your URL: `https://your-machine.tail1234.ts.net:8000`

#### Option B: ngrok (Quick Testing)

```bash
# On your server
ngrok http 8000

# Copy the https URL shown (e.g., https://abc123.ngrok.io)
```

#### Option C: VPN

- Connect both devices to same VPN
- Use local IP address (e.g., `http://192.168.1.100:8000`)

#### Option D: Cloud Server

- Deploy Thoth to a cloud server (AWS, DigitalOcean, etc.)
- Use the server's public IP or domain

### Step 3: Install Plugin on Mobile

1. **Download plugin** from GitHub releases:
   - Get `thoth-obsidian-v1.0.0.zip` from releases page
   - Or use the Obsidian plugin browser (when published)

2. **Install in Obsidian**:
   - Extract zip to `.obsidian/plugins/thoth-obsidian/`
   - Or use Obsidian's plugin installer

3. **Enable plugin**:
   - Settings → Community Plugins → Enable "Thoth Research Assistant"

### Step 4: Configure Remote Connection

The plugin automatically detects mobile and enables remote mode!

1. Open Obsidian Settings → Thoth
2. You'll see: "Mobile requires connecting to a Thoth server..."
3. Enter your **Remote Endpoint URL**:
   - Tailscale: `https://your-machine.tail1234.ts.net:8000`
   - ngrok: `https://abc123.ngrok.io`
   - VPN: `http://192.168.1.100:8000`
   - Cloud: `https://your-server.com:8000`

4. Click **Test Remote Connection** to verify

### Step 5: Use Thoth!

Click the Thoth icon in the ribbon to open chat and start researching!

## What Works on Mobile

**Full UX Available:**
- Chat interface with AI assistant
- Multi-chat sessions
- Research queries
- Real-time streaming responses
- View research results
- Settings management
- All UI features
- WebSocket for live updates

**Not Available on Mobile:**
- Starting/stopping local Thoth agent (requires Node.js)
- Local file system operations (not needed - server handles this)

## Troubleshooting

### "Could not connect to server"

**Check:**
1. Server is running: `thoth status` on server
2. URL is correct (no typos, correct port)
3. Firewall allows port 8000
4. Both devices on same network (if using local IP)

### "403 Forbidden" or CORS errors

**Fix:**
Add your mobile device to allowed origins in server settings:

```json
// In settings.json
{
  "api": {
    "cors_origins": ["https://your-mobile-device.tail1234.ts.net"]
  }
}
```

### Slow responses

**Causes:**
- Internet connection speed
- Server resources (RAM/CPU)
- Distance to server (latency)

**Solutions:**
- Use Tailscale for better performance
- Upgrade server resources
- Deploy server closer geographically

### Plugin doesn't load

**Check:**
1. Obsidian is up to date (v0.15.0+)
2. Plugin is enabled in Community Plugins
3. Clear Obsidian cache: Settings → About → Reload without saving

## Performance Tips

1. **Use Tailscale**: Better performance than ngrok
2. **Persistent URL**: Use static IP or domain (not ngrok free tier)
3. **Server specs**: 2GB+ RAM recommended
4. **WiFi over cellular**: Better latency and no data usage

## Security

**Best practices:**
- Use HTTPS (Tailscale, ngrok, or SSL certificate)
- Don't expose ports directly without authentication
- Use VPN for local network access
- Keep Thoth server updated

**Authentication:**
The MCP server supports Bearer token authentication:
```bash
# On server
export THOTH_MCP_AUTH_TOKEN="your-secret-token"
thoth start
```

Then configure the token in plugin settings (if implemented).

## Example Setups

### Home Setup (Desktop + iPhone)

```
Desktop (Home):
  - Thoth running via `thoth start`
  - Tailscale installed
  - funnel enabled: `tailscale funnel 8000`

iPhone:
  - Obsidian app
  - Thoth plugin
  - Connected to: https://my-desktop.tail1234.ts.net:8000
  - Works at home AND away from home!
```

### Cloud Setup (AWS + iPad)

```
AWS EC2:
  - Thoth running as service
  - Nginx reverse proxy with SSL
  - Domain: thoth.mydomain.com

iPad:
  - Obsidian app
  - Thoth plugin
  - Connected to: https://thoth.mydomain.com
  - Fast, always available
```

## FAQ

**Q: Does mobile use more data?**
A: Yes, since it's remote. Use WiFi to avoid cellular data charges.

**Q: Can I use offline?**
A: No, mobile requires connection to server. Desktop can work offline in local mode.

**Q: Is it slower than desktop?**
A: Slightly, due to network latency. Usually <100ms with good connection.

**Q: Can multiple devices connect?**
A: Yes! Multiple mobile devices can connect to the same server.

**Q: Do I need to expose ports to the internet?**
A: Not required - use Tailscale for secure private connection without port forwarding.

## Getting Help

- Documentation: `docs/` folder in repository
- Issues: https://github.com/acertainKnight/project-thoth/issues
- Tailscale docs: https://tailscale.com/kb/
- Obsidian forum: https://forum.obsidian.md/

## Related Documentation

- [Setup Guide](setup.md) - Installing Thoth
- [MCP Letta Cloud](MCP_LETTA_CLOUD.md) - Cloud Letta setup
- [Remote Setup](REMOTE_SETUP.md) - Remote Thoth configuration
