# Quick Start Guide

Get Thoth up and running in 5 minutes - no Python knowledge required!

## Installation

### Linux/Mac (One Command)

```bash
curl -fsSL https://raw.githubusercontent.com/acertainKnight/project-thoth/main/install.sh | bash
```

### Windows (WSL2)

```powershell
# 1. Install WSL2 (PowerShell as Administrator, one-time setup)
wsl --install

# 2. Restart your computer

# 3. Open Ubuntu terminal (installed with WSL2) and run:
curl -fsSL https://raw.githubusercontent.com/acertainKnight/project-thoth/main/install.sh | bash
```

**Note:** Windows users run Thoth through WSL2 for best compatibility. After installation, use `wsl` from PowerShell or open the Ubuntu app directly.

### What the Installer Does

1. Checks for Docker (guides you to install if missing)
2. Downloads or builds Thoth
3. Runs interactive setup wizard
4. Installs `thoth` command globally
5. Optionally starts services immediately

**Time:** 5 minutes (first time), 1 minute (if Docker already installed)

## Interactive Setup Wizard

The installer launches a friendly wizard that guides you through:

### Step 1: Vault Selection
Select your Obsidian vault directory (where your notes live)

### Step 2: Letta Mode (Choose One)

**Option A: Letta Cloud** (Easiest)
- Hosted agents at app.letta.com
- Just need an API key (free tier available)
- Get key: https://app.letta.com/api-keys
- No local infrastructure

**Option B: Self-Hosted** (Full Control)
- Agents run locally in Docker
- Works offline
- More RAM (~500MB extra)
- Full privacy

### Step 3: Dependencies
Wizard checks Docker, PostgreSQL, Letta connection

### Step 4: LLM Provider
Choose your AI provider:
- Mistral (recommended)
- OpenRouter  
- OpenAI
- Anthropic

Paste your API key from the provider's website.

### Step 5: Optional Features
Enable what you want:
- RAG (semantic search)
- Paper discovery
- Citation analysis

### Step 6: Review
Review your choices, click Install

### Step 7: Start Services?
Wizard asks: "Start Thoth now?"
- **Yes** - Services start immediately, ready to use!
- **No** - You'll run `thoth start` manually later

## Daily Usage

### Starting Thoth

```bash
thoth start
```

**What starts:**
- PostgreSQL (~50MB RAM)
- Thoth API Server (~200MB RAM)  
- MCP Server (~100MB RAM)
- Letta (if self-hosted, ~500MB RAM)

**Total RAM:** 1-1.5GB depending on Letta mode

### Checking Status

```bash
thoth status
```

Shows all running containers and their health.

### Stopping Thoth (Save RAM)

```bash
thoth stop
```

Frees up 1-1.5GB RAM immediately. Your data stays safe.

### Viewing Logs

```bash
# All logs
thoth logs

# Follow logs in real-time
thoth logs -f

# Specific service
thoth logs api
thoth logs mcp
```

### Restarting

```bash
thoth restart
```

Stops and starts all services.

### Updating

```bash
thoth update
```

Pulls latest code and Docker images, restarts services.

## Using Thoth

### Via Obsidian Plugin (Recommended)

1. Open Obsidian
2. Settings → Community Plugins → Browse
3. Search "Thoth"
4. Install and enable
5. Click Thoth icon in left ribbon
6. Chat with your research assistant!

### Via Command Line

```bash
# Process a PDF
thoth pdf process paper.pdf

# Search for papers
thoth discovery search "machine learning" --source arxiv

# Upload vault files to Letta
thoth letta sync

# Check Letta connection
thoth letta status
```

## Uploading Vault Files

After setup, upload your existing notes to Letta so agents can read them:

```bash
thoth letta sync
```

This uploads files from `vault/_thoth/notes/` to Letta (works with both cloud and self-hosted).

## Common Workflows

### Morning Routine
```bash
cd ~/thoth  # or wherever you installed
thoth start
# Services starting...
# Open Obsidian and start researching!
```

### Processing PDFs
1. Drop PDF into `vault/_thoth/data/pdfs/`
2. Thoth automatically:
   - Extracts text and metadata
   - Finds citations
   - Generates structured note
   - Adds to knowledge base
3. Note appears in `vault/_thoth/notes/`

### Discovery Workflow
```bash
# Search ArXiv for recent papers
thoth discovery search "transformer architectures" --source arxiv

# Papers are downloaded and processed automatically
```

### Evening Shutdown
```bash
thoth stop
# Frees 1-1.5GB RAM
# All data persists safely
```

## Troubleshooting

### "Command not found: thoth"

**Solution:** Restart your terminal
```bash
# Or manually reload PATH
source ~/.bashrc  # or ~/.zshrc
```

### Services won't start

```bash
# Check Docker is running
docker ps

# Check for port conflicts
thoth status

# Try restarting
thoth restart

# View error logs
thoth logs
```

### High RAM usage

**Normal usage:** 1-1.5GB total
- Cloud mode: ~1GB
- Self-hosted: ~1.5GB

**To reduce:**
```bash
# Stop when not in use
thoth stop

# Check memory usage
docker stats

# Switch to Letta Cloud (saves ~500MB)
thoth letta configure cloud --api-key=your-key
```

### Port conflicts (8000, 8001, 8283 already in use)

```bash
# Find what's using the port
lsof -i :8000  # Linux/Mac
netstat -ano | findstr :8000  # Windows

# Stop the conflicting service or change Thoth ports in settings
```

### Can't connect to Letta

```bash
# Check Letta status
thoth letta status

# For self-hosted: restart Letta
docker compose -f docker-compose.letta.yml restart

# For cloud: verify API key
thoth letta configure cloud --api-key=your-key
```

## Next Steps

- [Full Setup Guide](setup.md) - Detailed installation options
- [Letta Cloud Setup](LETTA_CLOUD_SETUP.md) - Using Letta Cloud
- [MCP Configuration](MCP_LETTA_CLOUD.md) - Expose MCP tools to cloud
- [Usage Examples](usage.md) - Advanced usage patterns

## Getting Help

- **Issues:** https://github.com/acertainKnight/project-thoth/issues
- **Documentation:** Check `/docs` folder in repository
- **Letta Support:** https://discord.gg/letta

## Uninstalling

```bash
# Stop all services
thoth stop

# Remove Docker containers and images
docker compose down
docker compose -f docker-compose.letta.yml down
docker system prune -a  # Frees ~5GB

# Remove Thoth code
rm -rf ~/thoth  # or your install location

# Remove thoth command
rm ~/.local/bin/thoth

# Remove configuration (optional)
rm -rf ~/.config/thoth
```

---

**That's it!** You're now ready to use Thoth for your research. Start with `thoth start` and open Obsidian!
