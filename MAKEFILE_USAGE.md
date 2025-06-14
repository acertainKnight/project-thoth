# Thoth Makefile Usage Guide

This guide explains how to use the Makefile to manage your Thoth Obsidian extension and API server.

## 🚀 Quick Start

### 1. First-time Setup

```bash
# Check if all dependencies are installed
make check-deps

# Set your Obsidian vault path (if different from default)
export OBSIDIAN_VAULT="/path/to/your/obsidian/vault"
```

### 2. Deploy Plugin and Start API

```bash
# Option 1: Deploy plugin and start API in one command
make full-deploy

# Option 2: Step by step
make deploy-plugin
make start-api
```

### 3. Development Mode

```bash
# Start both plugin watcher and API server with auto-reload
make dev
```

## 📋 Available Commands

### Plugin Management

```bash
# Build and deploy the Obsidian extension
make deploy-plugin

# Just build the plugin (without deploying)
make build-plugin

# Watch for changes and rebuild automatically
make watch-plugin

# Clean plugin build artifacts
make clean-plugin
```

### API Server Management

```bash
# Start the Thoth API server
make start-api

# Start with auto-reload for development
make start-api-dev

# Stop the API server
make stop-api
```

### Development Workflow

```bash
# Start development mode (plugin watcher + API server)
make dev

# Deploy plugin and start API server
make full-deploy
```

### Utilities

```bash
# Check service status
make status

# View API server logs
make logs

# Check dependencies
make check-deps

# Clean all build artifacts
make clean
```

## ⚙️ Configuration

### Obsidian Vault Path

The Makefile defaults to `~/Documents/Obsidian Vault`. You can override this:

```bash
# One-time override
make deploy-plugin OBSIDIAN_VAULT="/path/to/your/vault"

# Set permanently in your shell
export OBSIDIAN_VAULT="/path/to/your/vault"
```

### Common Vault Locations

- **Linux/WSL**: `/mnt/c/Users/username/Documents/Obsidian Vault`
- **macOS**: `/Users/username/Documents/Obsidian Vault`
- **Windows**: `C:/Users/username/Documents/Obsidian Vault`

### API Server Configuration

```bash
# Custom host and port
make start-api API_HOST=0.0.0.0 API_PORT=8080

# For WSL/Docker environments
make start-api API_HOST=0.0.0.0
```

## 🔧 Common Workflows

### 1. Daily Development

```bash
# Start development mode
make dev

# This starts:
# - Plugin watcher (rebuilds on changes)
# - API server with auto-reload
# - Both processes run in parallel
```

### 2. Plugin Updates

```bash
# After making changes to plugin code
make deploy-plugin

# Then reload the plugin in Obsidian:
# Ctrl/Cmd+P → "Reload app"
```

### 3. Production Deployment

```bash
# Clean build and deploy
make clean
make deploy-plugin
make start-api
```

### 4. Troubleshooting

```bash
# Check what's running
make status

# View logs
make logs

# Stop everything and restart
make stop-api
make start-api
```

## 🐛 Troubleshooting

### Plugin Not Found in Obsidian

1. Check if the vault path is correct:
   ```bash
   make check-obsidian-vault
   ```

2. Verify the plugin was deployed:
   ```bash
   make status
   ```

3. Enable the plugin in Obsidian:
   - Go to Settings → Community plugins
   - Find "Thoth" and enable it

### API Server Won't Start

1. Check if another process is using port 8000:
   ```bash
   lsof -i :8000
   ```

2. Use a different port:
   ```bash
   make start-api API_PORT=8001
   ```

3. Check Python environment:
   ```bash
   make check-venv
   ```

### Build Errors

1. Clean and rebuild:
   ```bash
   make clean
   make build-plugin
   ```

2. Check Node.js dependencies:
   ```bash
   cd obsidian-plugin/thoth-obsidian
   npm install
   ```

## 💡 Tips

1. **Use `make dev` for active development** - it automatically rebuilds the plugin and restarts the API when you make changes.

2. **Set environment variables** in your shell profile for permanent configuration:
   ```bash
   echo 'export OBSIDIAN_VAULT="/your/vault/path"' >> ~/.bashrc
   ```

3. **Check status regularly** with `make status` to see what's running.

4. **Use `make logs`** to monitor API server activity.

5. **Clean builds** with `make clean` if you encounter weird issues.

## 🎯 Example Session

```bash
# Initial setup
make check-deps
make check-obsidian-vault

# Deploy and start
make full-deploy

# Work on plugin (in another terminal)
make watch-plugin

# Check everything is working
make status

# View logs
make logs

# Stop when done
make stop-api
```

This Makefile streamlines your development workflow and makes it easy to manage both the Obsidian extension and the Thoth API server!
