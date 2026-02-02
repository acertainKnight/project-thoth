# Install Thoth WITHOUT Python

**Three methods that require ZERO Python knowledge:**

---

## Method 1: One-Line Installer (Easiest) 🚀

**Linux/macOS:**
```bash
curl -fsSL https://raw.githubusercontent.com/yourusername/project-thoth/main/install.sh | bash
```

**What happens:**
1. Script detects if you have Docker, pipx, or Python
2. Uses Docker if available (no Python needed)
3. Installs everything automatically
4. Runs setup wizard

**Time:** ~5 minutes (first time), ~1 minute (with Docker)

---

## Method 2: Docker Setup Script 🐳

**Prerequisites:** Docker only (no Python)

```bash
# Install Docker first (if needed)
# Ubuntu: sudo apt install docker.io docker-compose
# macOS: brew install docker docker-compose

# Download setup script
curl -O https://raw.githubusercontent.com/yourusername/project-thoth/main/docker-setup.sh
chmod +x docker-setup.sh

# Run setup
./docker-setup.sh
```

**Advantages:**
- ✅ Completely isolated from your system
- ✅ No Python conflicts
- ✅ Easy to uninstall
- ✅ Works everywhere Docker works

---

## Method 3: Manual Docker Commands 🔧

**For users who want full control:**

```bash
# 1. Clone repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# 2. Build setup wizard image
docker build -f Dockerfile.setup -t thoth-setup .

# 3. Run setup wizard
docker run -it --rm \
  -v ~/.config/thoth:/root/.config/thoth \
  -v ~/Documents:/documents \
  thoth-setup

# 4. Start services
docker compose up -d

# 5. Check status
docker compose ps
```

---

## Comparison Table

| Method | Python Required? | Docker Required? | Time | Difficulty |
|--------|-----------------|------------------|------|------------|
| **One-line installer** | No | No* | 1-5 min | ⭐ Easiest |
| **Docker script** | No | Yes | 2-3 min | ⭐⭐ Easy |
| **Manual Docker** | No | Yes | 5 min | ⭐⭐⭐ Medium |
| pipx | Yes (3.10+) | No | 2 min | ⭐⭐ Easy |
| pip/uv | Yes (3.10+) | No | 3 min | ⭐⭐⭐ Medium |

*Uses Docker automatically if available, otherwise tries pipx/Python

---

## After Installation

All methods end with:
```bash
# Check status
thoth status

# Or with Docker:
docker compose ps

# Start discovery
thoth discover

# Or with Docker:
docker compose exec thoth python -m thoth discover
```

---

## Uninstalling

### If installed via Docker:
```bash
docker compose down -v
docker rmi thoth-setup project-thoth
rm -rf ~/.config/thoth
```

### If installed via one-line installer:
```bash
# Docker-based install:
docker compose down -v
docker rmi thoth-setup

# pipx-based install:
pipx uninstall project-thoth

# pip-based install:
rm -rf ~/.thoth-venv
rm ~/.local/bin/thoth
```

---

## Troubleshooting

### "Docker not found"
**Install Docker:**
- Ubuntu/Debian: `sudo apt install docker.io docker-compose`
- macOS: `brew install docker docker-compose`
- Or visit: https://docs.docker.com/get-docker/

### "Permission denied"
**Add yourself to docker group:**
```bash
sudo usermod -aG docker $USER
newgrp docker
```

### "Setup wizard stuck"
**Press Ctrl+C and try:**
```bash
# Set vault path first
export OBSIDIAN_VAULT_PATH="/path/to/your/vault"

# Run setup again
./docker-setup.sh
```

---

## Why Docker? 🤔

**Advantages:**
1. **No Python conflicts** - Completely isolated
2. **Easy updates** - Just rebuild image
3. **Consistent** - Works same everywhere
4. **Clean uninstall** - Just delete containers
5. **No system pollution** - Everything in containers

**Disadvantages:**
1. Requires ~2GB disk space
2. Slightly slower startup (1-2s)
3. Requires Docker installed

---

## Still Need Help?

- 📖 [Full Installation Guide](./easy-install.md)
- 🐛 [Report Issues](https://github.com/yourusername/project-thoth/issues)
- 💬 [Discord Community](#)
- 📧 [Email Support](#)
