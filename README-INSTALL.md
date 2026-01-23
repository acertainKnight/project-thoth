# Thoth Installation

## ⚡ Quick Start

### **No Python? No Problem!**

```bash
# One command - works on Linux/macOS
curl -fsSL https://raw.githubusercontent.com/yourusername/project-thoth/main/install.sh | bash
```

This automatically:
- ✅ Detects if you have Docker, pipx, or Python
- ✅ Uses the best available method
- ✅ Installs Thoth without asking questions
- ✅ Runs the setup wizard

---

## 🐳 Docker Install (NO Python Required)

**Prerequisites:** Docker only

```bash
# Method 1: Easy script
curl -fsSL https://raw.githubusercontent.com/yourusername/project-thoth/main/docker-setup.sh | bash

# Method 2: Manual
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth
docker build -f Dockerfile.setup -t thoth-setup .
docker run -it --rm \
  -v ~/.config/thoth:/root/.config/thoth \
  -v ~/Documents:/documents \
  thoth-setup
```

---

## 📦 Python Install Methods

### pipx (Recommended for Python users)

```bash
pipx install project-thoth
thoth setup
```

### pip (Traditional)

```bash
python -m venv venv
source venv/bin/activate
pip install project-thoth
thoth setup
```

### uv (Fast, modern)

```bash
uv pip install project-thoth
thoth setup
```

---

## 📖 Detailed Guides

- **[No Python Installation](./docs/installation/NO-PYTHON-INSTALL.md)** - Complete guide for Docker-based install
- **[Easy Installation Guide](./docs/installation/easy-install.md)** - All methods with details
- **[Troubleshooting](./docs/installation/troubleshooting.md)** - Common issues and fixes

---

## 🎯 What Installation Method Should I Use?

| You have... | Use... | Time | Difficulty |
|------------|--------|------|------------|
| Nothing | One-line installer | 1-5 min | ⭐ Easiest |
| Docker | docker-setup.sh | 2-3 min | ⭐⭐ Easy |
| Python 3.10+ | pipx | 2 min | ⭐⭐ Easy |
| Python + dev tools | uv/pip | 3 min | ⭐⭐⭐ Medium |

---

## 🚀 After Installation

```bash
# Check status
thoth status

# Run setup wizard (if not done automatically)
thoth setup

# Start discovery
thoth discover

# View help
thoth --help
```

---

## 🗑️ Uninstall

### Docker install:
```bash
docker compose down -v
docker rmi thoth-setup project-thoth
rm -rf ~/.config/thoth
```

### pipx install:
```bash
pipx uninstall project-thoth
```

### pip install:
```bash
pip uninstall project-thoth
rm -rf venv
```

---

## 🆘 Need Help?

- 📖 [Documentation](https://docs.thoth.ai)
- 🐛 [Report Issues](https://github.com/yourusername/project-thoth/issues)
- 💬 [Discord Community](#)
