# Easy Installation Guide

This guide provides multiple installation methods for Thoth, from simplest (no Python required) to most flexible.

## 🚀 Quick Install (Recommended for Users)

### Option 1: Using pipx (Isolated Python Environment)

**Best for:** Users who want Thoth isolated from system Python

```bash
# Install pipx (one-time setup)
# Ubuntu/Debian:
sudo apt install pipx
pipx ensurepath

# macOS:
brew install pipx
pipx ensurepath

# Install Thoth
pipx install project-thoth

# Run setup wizard
thoth setup
```

**Advantages:**
- ✅ No Python knowledge required
- ✅ Isolated from system Python
- ✅ Easy updates: `pipx upgrade project-thoth`
- ✅ Clean uninstall: `pipx uninstall project-thoth`

### Option 2: Docker (No Python Required)

**Best for:** Users who prefer containerized applications

```bash
# Pull the Thoth image
docker pull ghcr.io/yourusername/project-thoth:latest

# Run setup wizard
docker run -it --rm \
  -v ~/.config/thoth:/root/.config/thoth \
  -v ~/Documents/Obsidian:/vaults \
  ghcr.io/yourusername/project-thoth:latest setup

# Start Thoth services
docker compose up -d
```

**Advantages:**
- ✅ No Python installation needed
- ✅ Isolated environment
- ✅ Easy updates: `docker pull`
- ✅ Works on all platforms (Linux, macOS, Windows)

### Option 3: Standalone Executable (Coming Soon)

**Best for:** Users who want a simple .exe/.app file

```bash
# Download for your platform
# Linux:
wget https://github.com/yourusername/project-thoth/releases/latest/download/thoth-linux-x64
chmod +x thoth-linux-x64
./thoth-linux-x64 setup

# macOS:
# Download thoth-macos-x64.dmg from releases
# Install and run Thoth.app

# Windows:
# Download thoth-windows-x64.exe from releases
# Run the installer
```

**Advantages:**
- ✅ Zero dependencies
- ✅ Double-click to run
- ✅ No command line required

---

## 💻 Developer Installation

### Option 4: uv (Modern Python Package Manager)

**Best for:** Developers contributing to Thoth

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Install in development mode
uv pip install -e ".[all]"

# Run setup wizard
thoth setup
```

**Advantages:**
- ✅ Fast dependency resolution
- ✅ Editable installation
- ✅ Easy testing and debugging

### Option 5: Traditional pip

**Best for:** Users with existing Python environments

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Thoth
pip install project-thoth

# Run setup wizard
thoth setup
```

---

## 📋 Prerequisites

### All Installation Methods:
- **Obsidian** (will be detected during setup, download link provided if not found)
- **~10 GB free disk space**
- **Internet connection**

### For Docker Installation:
- Docker (version 20.10+)
- Docker Compose (version 2.0+)

### For Python Installations:
- Python 3.10+ (for pip/uv methods)
- PostgreSQL 14+ (auto-installed via Docker Compose during setup)

---

## 🔧 Setup Wizard

After installation, run the interactive setup wizard:

```bash
thoth setup
```

The wizard will guide you through:

1. **Vault Selection** - Choose your Obsidian vault
2. **LLM Configuration** - Set up API keys (OpenAI, Anthropic, Google, etc.)
3. **Dependency Check** - Verify Docker, PostgreSQL, Letta
4. **Installation** - Auto-install components and plugins
5. **Completion** - Next steps and documentation links

### Environment Variables (For CI/CD or Headless Setup)

Skip the interactive wizard by setting environment variables:

```bash
# Vault path
export OBSIDIAN_VAULT_PATH="/path/to/your/vault"

# LLM provider (choose one or more)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export GOOGLE_API_KEY="..."

# Database
export DATABASE_URL="postgresql://thoth:password@localhost:5432/thoth"

# Letta
export LETTA_BASE_URL="http://localhost:8283"

# Run headless setup
thoth setup --headless
```

---

## 🚀 Starting Thoth

After setup, start the services:

```bash
# Start all services (Docker Compose)
docker compose up -d

# Check status
thoth status

# Start discovery
thoth discover

# Open in Obsidian
# Enable the Thoth plugin in Settings → Community Plugins
```

---

## 🔄 Updating Thoth

### pipx:
```bash
pipx upgrade project-thoth
```

### Docker:
```bash
docker compose pull
docker compose up -d
```

### uv/pip:
```bash
pip install --upgrade project-thoth
```

---

## 🗑️ Uninstalling

### pipx:
```bash
pipx uninstall project-thoth
```

### Docker:
```bash
docker compose down -v  # Remove containers and volumes
docker rmi ghcr.io/yourusername/project-thoth:latest
```

### uv/pip:
```bash
pip uninstall project-thoth
```

### Clean up data:
```bash
# Remove Thoth workspace (optional)
rm -rf ~/Documents/your-vault/_thoth

# Remove Obsidian plugin (optional)
rm -rf ~/Documents/your-vault/.obsidian/plugins/thoth
```

---

## 🆘 Troubleshooting

### "Python not found"
- Use **pipx** or **Docker** methods (no Python required)
- Or install Python 3.10+ from [python.org](https://www.python.org)

### "Vault search taking too long"
- Set `OBSIDIAN_VAULT_PATH` environment variable before running setup
- Or manually enter vault path in the wizard

### "PostgreSQL connection failed"
- Ensure Docker Compose is running: `docker compose ps`
- Check PostgreSQL health: `docker compose logs postgres`
- Restart services: `docker compose restart`

### "Letta not available"
- Start Letta service: `docker compose up -d letta`
- Check logs: `docker compose logs letta`

For more help, see:
- [Troubleshooting Guide](./troubleshooting.md)
- [GitHub Issues](https://github.com/yourusername/project-thoth/issues)
- [Documentation](https://docs.thoth.ai)

---

## 🎯 Recommended Installation Path

**For most users:**
1. Install **pipx**: `brew install pipx` (macOS) or `sudo apt install pipx` (Linux)
2. Install **Thoth**: `pipx install project-thoth`
3. Run **setup**: `thoth setup`
4. Start **services**: `docker compose up -d`

**For developers:**
1. Install **uv**: `curl -LsSf https://astral.sh/uv/install.sh | sh`
2. Clone **repo**: `git clone https://github.com/yourusername/project-thoth.git`
3. Install **dev mode**: `uv pip install -e ".[all]"`
4. Run **setup**: `thoth setup`

**For Docker users:**
1. Install **Docker**: [Get Docker](https://docs.docker.com/get-docker/)
2. Pull **image**: `docker pull ghcr.io/yourusername/project-thoth:latest`
3. Run **setup**: `docker run -it ... thoth setup`
4. Start **services**: `docker compose up -d`
