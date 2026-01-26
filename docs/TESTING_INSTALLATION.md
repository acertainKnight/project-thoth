# Testing the Installation System

Guide for testing the new seamless installation system without breaking your current dev setup.

## Overview

The new installation system includes:
- One-command installer (`install.sh`)
- Interactive setup wizard with auto-start prompt
- `thoth` CLI command for service management
- Docker image pulling from GitHub Container Registry

This guide shows how to test all of this safely.

---

## Option 1: Test in Clean Container (RECOMMENDED)

### What This Does

Creates a **temporary, isolated Ubuntu environment** that:
- Has NO connection to your current Thoth setup
- Can access Docker on your host (to test the installer)
- **Auto-deletes when you exit** (no trace left)
- Exactly simulates a new user's experience

### Step 1: Start Test Container

```bash
docker run -it --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/Documents:/documents \
  ubuntu:22.04 bash
```

**What each part means:**
- `docker run -it` - Create and run container interactively
- `--rm` - **Auto-delete this container when you exit**
- `-v /var/run/docker.sock:/var/run/docker.sock` - Share Docker so installer can create containers
- `-v ~/Documents:/documents` - Mount Documents folder (for vault access)
- `ubuntu:22.04` - Fresh Ubuntu image
- `bash` - Start bash shell

### Step 2: Inside Container, Test Installation

```bash
# Install minimal tools (fresh Ubuntu has nothing)
apt-get update && apt-get install -y curl git

# Test the installer exactly like a new user
curl -fsSL https://raw.githubusercontent.com/acertainKnight/project-thoth/main/install.sh | bash

# OR test local version:
cd /tmp
git clone https://github.com/acertainKnight/project-thoth.git
cd project-thoth
./install.sh
```

### Step 3: Test the Wizard

The wizard will guide you through:
1. Vault selection
2. Letta mode (cloud/self-hosted)
3. Dependency checks
4. LLM provider config
5. **Auto-start prompt** (new feature!)

### Step 4: Test thoth CLI

```bash
# After wizard completes, test commands:
thoth status   # Should show containers
thoth start    # Should start services
thoth stop     # Should stop services
thoth logs     # Should show logs
```

### Step 5: Exit and Cleanup

```bash
# Exit the test container
exit

# Container auto-deletes due to --rm flag!

# But the Thoth containers it created still exist, so clean up:
docker ps -a | grep thoth

# Remove test containers (NOT your dev ones)
docker stop thoth-all-in-one    # Note: no "dev" prefix
docker rm thoth-all-in-one

# Or remove ALL stopped containers at once
docker container prune -f
```

### Why Your Dev Setup is Safe

- **Dev containers** named: `thoth-dev-all-in-one`, `thoth-dev-api`, etc.
- **Test containers** named: `thoth-all-in-one`, `thoth-api`, etc.
- Different names = no conflicts!
- Your `~/.config/thoth` untouched (test uses container's `/root/.config/thoth`)

---

## Option 2: Test Locally with Backup

Test on your actual machine with safety backups.

### Step 1: Backup Current Setup

```bash
# Backup config
cp -r ~/.config/thoth ~/.config/thoth.backup

# Backup vault data
cp -r ~/Documents/your-vault/_thoth ~/Documents/your-vault/_thoth.backup

# Note: Your dev containers keep running, they're not affected
```

### Step 2: Remove Config (Simulate Fresh Install)

```bash
rm -rf ~/.config/thoth
rm ~/.local/bin/thoth  # if exists

# Dev containers still running, just config removed
```

### Step 3: Test Installer

```bash
cd /tmp
git clone https://github.com/acertainKnight/project-thoth.git thoth-test
cd thoth-test
./install.sh

# Go through wizard, test auto-start
```

### Step 4: Test Commands

```bash
thoth status
thoth start   # Will create NEW containers (conflict with dev?)
thoth stop
thoth logs
```

**Warning:** This might create containers that conflict with your dev setup if ports overlap. Option 1 is safer.

### Step 5: Restore Original Setup

```bash
# Stop test containers
docker compose down

# Remove test files
rm -rf /tmp/thoth-test
rm ~/.local/bin/thoth

# Restore config
rm -rf ~/.config/thoth
mv ~/.config/thoth.backup ~/.config/thoth

# Restore vault data
rm -rf ~/Documents/your-vault/_thoth
mv ~/Documents/your-vault/_thoth.backup ~/Documents/your-vault/_thoth

# Restart your dev containers
cd /home/nick-hallmark/Documents/python/project-thoth
make dev
```

---

## Option 3: Test Just the Setup Wizard

Test only the wizard without running the full installer.

```bash
cd /home/nick-hallmark/Documents/python/project-thoth

# Backup config
cp ~/.config/thoth/settings.json ~/.config/thoth/settings.json.backup

# Run wizard
python -m thoth setup

# Watch for:
# - New Letta mode selection screen
# - Auto-start prompt at completion
# - Services starting if you say "Yes"

# After testing, restore
mv ~/.config/thoth/settings.json.backup ~/.config/thoth/settings.json
```

---

## Option 4: Test thoth CLI Wrapper Only

Test just the CLI commands without full installation.

```bash
cd /home/nick-hallmark/Documents/python/project-thoth

# The wrapper is embedded in install.sh lines 145-228
# Extract it to a test file:
cat > /tmp/test-thoth << 'EOFCLI'
#!/bin/bash
# ... paste the thoth CLI wrapper from install.sh ...
EOFCLI

chmod +x /tmp/test-thoth

# Set project root
export THOTH_PROJECT_ROOT=/home/nick-hallmark/Documents/python/project-thoth

# Create mock config for testing
mkdir -p ~/.config/thoth
echo 'THOTH_PROJECT_ROOT="/home/nick-hallmark/Documents/python/project-thoth"' > ~/.config/thoth/cli.conf

# Test commands
/tmp/test-thoth status
/tmp/test-thoth start
/tmp/test-thoth stop
/tmp/test-thoth logs

# Cleanup
rm /tmp/test-thoth
```

---

## What to Test

### Setup Wizard Checklist

- [ ] Vault selection screen works
- [ ] Letta mode selection screen (NEW)
  - [ ] Cloud option works
  - [ ] Self-hosted option works
  - [ ] API key validation
- [ ] Dependency checks pass
- [ ] LLM provider configuration
- [ ] Review screen shows correct settings
- [ ] **Auto-start prompt appears** (NEW)
- [ ] If "Yes" → services start automatically
- [ ] If "No" → shows manual start instructions

### thoth CLI Checklist

- [ ] `thoth start` works
  - [ ] Detects Letta mode from settings.json
  - [ ] Starts Letta containers (if self-hosted)
  - [ ] Starts Thoth containers
  - [ ] Shows success message with URLs
- [ ] `thoth stop` works
  - [ ] Stops Thoth containers
  - [ ] Asks about stopping Letta (if self-hosted)
  - [ ] Frees RAM
- [ ] `thoth status` works
  - [ ] Shows Thoth containers
  - [ ] Shows Letta status
- [ ] `thoth logs` works
  - [ ] Shows all logs
  - [ ] `-f` follows logs
  - [ ] Service-specific logs work
- [ ] `thoth restart` works
  - [ ] Stops then starts
- [ ] `thoth update` works
  - [ ] Pulls latest code
  - [ ] Pulls latest images
  - [ ] Restarts services

### install.sh Checklist

- [ ] Detects Docker correctly
- [ ] Tries to pull `ghcr.io/acertainknight/project-thoth:setup`
- [ ] Falls back to local build if pull fails
- [ ] Clones repo if not in project directory
- [ ] Runs wizard in Docker container
- [ ] Installs thoth command to `~/.local/bin/`
- [ ] Creates `~/.config/thoth/cli.conf`
- [ ] Adds `~/.local/bin` to PATH if needed
- [ ] Shows success message with next steps

### Docker Images Checklist

- [ ] docker-compose.yml pulls from registry
- [ ] Falls back to local build if pull fails
- [ ] All service images available:
  - [ ] `ghcr.io/acertainknight/project-thoth:setup`
  - [ ] `ghcr.io/acertainknight/project-thoth:latest`
  - [ ] `ghcr.io/acertainknight/project-thoth/api:latest`
  - [ ] `ghcr.io/acertainknight/project-thoth/mcp:latest`
  - [ ] `ghcr.io/acertainknight/project-thoth/pdf-monitor:latest`
  - [ ] `ghcr.io/acertainknight/project-thoth/discovery:latest`

---

## Extra Safe Testing (Isolated Network)

For maximum isolation from your dev setup:

```bash
# Create isolated test network
docker network create thoth-test-network

# Run test container on isolated network
docker run -it --rm \
  --network thoth-test-network \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v ~/Documents:/documents \
  ubuntu:22.04 bash

# After testing, cleanup network
docker network rm thoth-test-network
```

---

## Troubleshooting

### "Command not found: thoth"

**Cause:** PATH not updated yet

**Fix:** 
```bash
# Restart terminal
# OR manually reload PATH
source ~/.bashrc  # or ~/.zshrc
```

### Test containers conflict with dev containers

**Cause:** Same container names or ports

**Fix:** Use Option 1 (container test) or stop dev containers first:
```bash
make dev-stop
# Run tests
# Restart dev
make dev
```

### Registry pull fails during test

**Expected!** The images won't exist until you push a release tag.

**Workaround:** The installer falls back to local build automatically.

---

## After Testing

Once testing is complete and everything works:

1. **Commit changes:**
   ```bash
   git add .
   git commit -m "feat: Add seamless installation system with auto-start wizard"
   ```

2. **Push to main:**
   ```bash
   git push origin setup-wizard  # or main
   ```

3. **Create first release to publish images:**
   ```bash
   git checkout -b release/v1.0.0
   git tag v1.0.0
   git push origin v1.0.0
   ```

4. **Wait for CI/CD** to build and publish images to ghcr.io

5. **Test again** with published images (they'll download fast now!)

---

## Questions?

- Where's the wizard code? `src/thoth/cli/setup/screens/`
- Where's the CLI wrapper? Embedded in `install.sh`
- Where's the service management? `src/thoth/cli/service.py`
- Where's the CI/CD? `.github/workflows/release.yml`

**Need help?** Check the implementation plan at `.letta/plans/warm-breezy-hill.md`
