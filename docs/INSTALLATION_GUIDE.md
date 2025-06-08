# Thoth Installation Guide

This guide provides comprehensive installation instructions for the Thoth Research Assistant across different platforms and deployment scenarios.

## 🎯 **Quick Installation (Recommended)**

### **Prerequisites**
- **Python 3.10+** (Python 3.11 or 3.12 recommended)
- **uv package manager** (for dependency management)
- **Git** (for cloning the repository)

### **5-Minute Setup**

```bash
# 1. Install uv package manager (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # or restart terminal

# 2. Clone the repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# 3. Install dependencies
uv sync

# 4. Set up configuration
cp .env.example .env
# Edit .env with your API keys (minimum: OpenRouter API key)

# 5. Test installation
uv run python -m thoth --help
```

### **Essential Configuration**
1. **Get OpenRouter API Key** from [openrouter.ai](https://openrouter.ai) (required)
2. **Edit `.env` file** and set `API_OPENROUTER_KEY=your-key-here`
3. **Test setup**: `uv run python -m thoth agent`

## 📋 **Installation Methods**

### **Method 1: UV Package Manager (Recommended)**

UV is the fastest and most reliable way to install Thoth with proper dependency management.

#### **Install UV**
```bash
# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Alternative: via pip
pip install uv
```

#### **Install Thoth**
```bash
# Clone repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Install in development mode with all dependencies
uv sync --dev

# Or install minimal dependencies only
uv sync --no-dev

# Create virtual environment and install
uv venv thoth-env
source thoth-env/bin/activate  # Linux/macOS
# thoth-env\Scripts\activate  # Windows
uv pip install -e .
```

### **Method 2: Traditional pip Installation**

For systems where UV is not available or preferred.

```bash
# Clone repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Create virtual environment
python -m venv thoth-env
source thoth-env/bin/activate  # Linux/macOS
# thoth-env\Scripts\activate  # Windows

# Install dependencies
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

### **Method 3: Docker Installation (Containerized)**

Perfect for production deployment or isolated environments.

#### **Using Docker Compose (Recommended)**
```bash
# Clone repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Copy and edit environment
cp .env.example .env
# Edit .env with your API keys

# Start with Docker Compose
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f thoth
```

#### **Using Plain Docker**
```bash
# Build image
docker build -t thoth-research .

# Run container
docker run -d \
  --name thoth \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env \
  thoth-research
```

### **Method 4: Development Installation**

For developers who want to contribute or customize Thoth.

```bash
# Clone with development setup
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Install with development dependencies
uv sync --dev

# Install pre-commit hooks
uv run pre-commit install

# Install test dependencies
uv run pip install pytest pytest-cov pytest-mock

# Run tests to verify installation
uv run pytest

# Install in editable mode for development
uv run pip install -e .
```

## 🖥️ **Platform-Specific Instructions**

### **Linux (Ubuntu/Debian)**

#### **System Dependencies**
```bash
# Update package list
sudo apt update

# Install Python and build tools
sudo apt install python3.11 python3.11-dev python3.11-venv
sudo apt install git curl build-essential

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

#### **Complete Installation**
```bash
# Clone and install
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth
uv sync

# Set up configuration
cp .env.example .env
nano .env  # Edit with your API keys

# Test installation
uv run python -m thoth --help
```

### **macOS**

#### **Using Homebrew**
```bash
# Install dependencies via Homebrew
brew install python@3.11 git

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc

# Clone and install Thoth
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth
uv sync

# Configuration
cp .env.example .env
nano .env  # Add your API keys
```

#### **Using System Python**
```bash
# Ensure Python 3.10+ is installed
python3 --version

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and install
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth
uv sync
```

### **Windows**

#### **Using PowerShell (Recommended)**
```powershell
# Install UV
irm https://astral.sh/uv/install.ps1 | iex

# Clone repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Install dependencies
uv sync

# Set up configuration
copy .env.example .env
notepad .env  # Edit with your API keys
```

#### **Using WSL (Windows Subsystem for Linux)**
```bash
# In WSL terminal, follow Linux instructions
sudo apt update
sudo apt install python3.11 python3.11-dev git curl

# Install UV in WSL
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

# Clone and install
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth
uv sync
```

## 🐳 **Docker Installation Details**

### **Production Docker Setup**

#### **docker-compose.prod.yml**
```yaml
version: '3.8'
services:
  thoth:
    build: .
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./knowledge:/app/knowledge
      - ./logs:/app/logs
      - ./.env:/app/.env:ro
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

#### **Starting Production**
```bash
# Start production setup
docker-compose -f docker-compose.prod.yml up -d

# Monitor logs
docker-compose -f docker-compose.prod.yml logs -f

# Update to latest version
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d
```

### **Development Docker Setup**

#### **docker-compose.dev.yml**
```yaml
version: '3.8'
services:
  thoth-dev:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    volumes:
      - .:/app
      - /app/.venv  # Prevent host venv conflicts
    environment:
      - DEVELOPMENT=true
      - LOG_LEVEL=DEBUG
    command: ["uv", "run", "python", "-m", "thoth", "api", "--reload"]
```

#### **Development Workflow**
```bash
# Start development container
docker-compose -f docker-compose.dev.yml up -d

# Access development shell
docker-compose -f docker-compose.dev.yml exec thoth-dev bash

# Run tests in container
docker-compose -f docker-compose.dev.yml exec thoth-dev uv run pytest

# View live logs
docker-compose -f docker-compose.dev.yml logs -f
```

## 🔧 **Post-Installation Setup**

### **Essential Configuration**

1. **API Keys Setup**
   ```bash
   # Edit configuration file
   nano .env

   # Required: Add OpenRouter API key
   API_OPENROUTER_KEY="sk-or-v1-your-openrouter-key"

   # Optional: Add Mistral API key for OCR
   API_MISTRAL_KEY="your-mistral-key"
   ```

2. **Directory Creation**
   ```bash
   # Create necessary directories
   mkdir -p data/{pdf,markdown,notes,output}
   mkdir -p knowledge/{agent,vector_db}
   mkdir -p logs
   mkdir -p planning/queries
   ```

3. **Test Installation**
   ```bash
   # Run comprehensive health check
   uv run python health_check.py

   # Test CLI access
   uv run python -m thoth --help

   # Test API server
   uv run python -m thoth api --host 127.0.0.1 --port 8000 &
   curl http://127.0.0.1:8000/health

   # Test agent
   uv run python -m thoth agent
   ```

### **Obsidian Plugin Setup**

1. **Install Plugin**
   ```bash
   # Copy plugin files to Obsidian vault
   cp -r obsidian-plugin/thoth-obsidian/* /path/to/vault/.obsidian/plugins/thoth-obsidian/
   ```

2. **Configure Plugin**
   - Enable plugin in Obsidian settings
   - Add API keys in plugin settings
   - Set workspace directory path
   - Test connection

### **Initial Data Setup**

1. **Index Knowledge Base**
   ```bash
   # Index existing documents
   uv run python -m thoth rag index

   # Check RAG status
   uv run python -m thoth rag stats
   ```

2. **Create Sample Queries**
   ```bash
   # Test filter system with sample data
   uv run python -m thoth filter-test --create-sample-queries
   ```

## 🚨 **Troubleshooting Installation**

### **Common Issues and Solutions**

#### **UV Installation Issues**
```bash
# If UV fails to install
pip install uv

# If UV command not found
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
```

#### **Python Version Issues**
```bash
# Check Python version
python3 --version

# Install specific Python version (Ubuntu)
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11 python3.11-dev python3.11-venv
```

#### **Dependency Conflicts**
```bash
# Clear UV cache
uv cache clean

# Reinstall dependencies
rm -rf .venv
uv sync

# Use specific Python version
uv venv --python 3.11
uv sync
```

#### **Permission Issues (Linux/macOS)**
```bash
# Fix permissions for data directories
sudo chown -R $USER:$USER data/
chmod -R 755 data/

# Fix UV permissions
chmod +x ~/.local/bin/uv
```

#### **API Key Issues**
```bash
# Test API key format
echo $API_OPENROUTER_KEY | wc -c  # Should be ~60+ characters

# Test API connectivity
curl -H "Authorization: Bearer $API_OPENROUTER_KEY" \
     "https://openrouter.ai/api/v1/models"
```

#### **Port Conflicts**
```bash
# Check if port 8000 is in use
netstat -an | grep :8000
lsof -i :8000

# Kill process using port
sudo kill -9 $(lsof -t -i:8000)

# Use different port
uv run python -m thoth api --port 8001
```

### **Installation Verification Script**

Create `verify_installation.py`:

```python
#!/usr/bin/env python3
"""Verify Thoth installation."""

import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version >= (3, 10):
        print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} (requires 3.10+)")
        return False

def check_uv_installation():
    """Check UV installation."""
    try:
        result = subprocess.run(['uv', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ UV {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("❌ UV not found")
    return False

def check_thoth_installation():
    """Check Thoth installation."""
    try:
        result = subprocess.run(['uv', 'run', 'python', '-m', 'thoth', '--help'],
                               capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Thoth CLI accessible")
            return True
    except Exception:
        pass
    print("❌ Thoth CLI not accessible")
    return False

def check_configuration():
    """Check configuration file."""
    if Path('.env').exists():
        print("✅ Configuration file exists")
        return True
    else:
        print("❌ Configuration file missing (.env)")
        return False

def check_directories():
    """Check required directories."""
    required_dirs = ['data', 'knowledge', 'logs', 'templates']
    all_exist = True
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"✅ Directory exists: {dir_name}")
        else:
            print(f"⚠️  Directory missing: {dir_name}")
            all_exist = False
    return all_exist

def main():
    """Run verification checks."""
    print("🔍 Verifying Thoth Installation\n")

    checks = [
        check_python_version(),
        check_uv_installation(),
        check_thoth_installation(),
        check_configuration(),
        check_directories(),
    ]

    if all(checks):
        print("\n🎉 Installation verification successful!")
        print("Run 'uv run python -m thoth agent' to get started.")
    else:
        print("\n❌ Installation verification failed.")
        print("Please review the issues above and refer to the installation guide.")

if __name__ == "__main__":
    main()
```

Run verification: `python verify_installation.py`

## 🚀 **Next Steps After Installation**

### **1. Basic Testing**
```bash
# Test CLI functionality
uv run python -m thoth --help

# Start API server
uv run python -m thoth api &

# Test agent interaction
uv run python -m thoth agent
```

### **2. Process Your First PDF**
```bash
# Download a sample PDF or use your own
uv run python -m thoth process --pdf-path /path/to/paper.pdf

# Monitor a directory
uv run python -m thoth monitor --watch-dir /path/to/pdfs
```

### **3. Set Up Discovery**
```bash
# Create an ArXiv source
uv run python -m thoth discovery create --name "test_arxiv" --type "api"

# Run discovery
uv run python -m thoth discovery run --source "test_arxiv" --max-articles 5
```

### **4. Index Knowledge Base**
```bash
# Index your documents
uv run python -m thoth rag index

# Test search
uv run python -m thoth rag search --query "machine learning"

# Ask questions
uv run python -m thoth rag ask --question "What are the main themes in my research?"
```

## 📖 **Advanced Installation Options**

### **Production Deployment**

For production deployment, consider:

1. **Reverse Proxy Setup** (Nginx/Apache)
2. **SSL Certificate** (Let's Encrypt)
3. **Process Management** (systemd/supervisor)
4. **Database Backup** (automated)
5. **Monitoring** (logs, health checks)

### **High-Availability Setup**

For enterprise deployment:

1. **Load Balancer** (multiple instances)
2. **Shared Storage** (NFS/cloud storage)
3. **Container Orchestration** (Kubernetes)
4. **Monitoring Stack** (Prometheus/Grafana)

### **Development Environment**

For development teams:

1. **Shared Configuration** (config templates)
2. **Development Containers** (consistent environments)
3. **Testing Pipeline** (automated testing)
4. **Code Quality** (linting, formatting)

---

This installation guide covers all major installation scenarios. Choose the method that best fits your environment and requirements. For additional help, refer to the troubleshooting section or create an issue in the project repository.
