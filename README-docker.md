# 🐳 Thoth AI Research Assistant - Docker Quick Start

Get Thoth running with Docker in minutes! This guide covers the essentials for containerized deployment.

## 🚀 Quick Start

### Development Environment

```bash
# 1. Initialize Docker environment
make docker-init

# 2. Configure API keys
cp .env.docker.example .env.docker
# Edit .env.docker with your API keys

# 3. Start development services
make docker-dev

# 4. Access services
# API Server: http://localhost:8000
# MCP Server: http://localhost:8001
# ChromaDB: http://localhost:8003
```

### Production Environment

```bash
# 1. Configure production
cp .env.prod.example .env.prod
# Edit .env.prod with production settings

# 2. Deploy production services
make docker-prod
```

## 📋 Prerequisites

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Memory**: 4GB+ RAM
- **Storage**: 10GB+ free space
- **API Keys**: Mistral or OpenRouter (minimum)

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│           Docker Network               │
│  ┌─────────────┐  ┌─────────────────┐   │
│  │ thoth-app   │  │   chromadb      │   │
│  │ - API:8000  │──│ - VectorDB:8003 │   │
│  │ - MCP:8001  │  │                 │   │
│  │ - Agent     │  │                 │   │
│  │ - Services  │  │                 │   │
│  └─────────────┘  └─────────────────┘   │
│                                         │
│  ┌─────────────────────────────────────┐ │
│  │        Persistent Volumes           │ │
│  │ - Workspace Data                    │ │
│  │ - Vector Database                   │ │
│  │ - Logs & Cache                      │ │
│  └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

## 🛠️ Available Commands

### Build Commands
```bash
make docker-build         # Build all images
make docker-build-dev      # Build development image
make docker-build-prod     # Build production image
```

### Service Management
```bash
make docker-up             # Start production services
make docker-up-dev         # Start development services
make docker-down           # Stop services
make docker-restart        # Restart services
```

### Development
```bash
make docker-dev            # Complete dev environment
make docker-shell-dev      # Access dev container shell
make docker-logs-dev       # View dev logs
```

### Monitoring
```bash
make docker-ps             # Show service status
make docker-logs           # View all service logs
make docker-health         # Check service health
```

### Maintenance
```bash
make docker-clean          # Clean images/containers
make docker-clean-volumes  # Clean volumes (⚠️ deletes data)
make docker-rebuild        # Rebuild and restart
```

## 🔧 Configuration

### Environment Files

| File | Purpose | Usage |
|------|---------|--------|
| `.env.docker` | Development config | `make docker-up-dev` |
| `.env.prod` | Production config | `make docker-up-prod` |

### Required API Keys

At minimum, provide one of:
- `API_MISTRAL_KEY` - For Mistral AI services
- `API_OPENROUTER_KEY` - For multi-provider access

Optional keys for enhanced features:
- `API_OPENCITATIONS_KEY` - Citation validation
- `API_GOOGLE_KEY` - Web search capabilities
- `API_SEMANTIC_SCHOLAR_KEY` - Academic paper discovery

### Directory Structure

```
workspace/
├── pdfs/          # PDF documents
├── notes/         # Generated notes
├── data/          # Application data
├── queries/       # Research queries
├── discovery/     # Discovery results
├── knowledge/     # Knowledge base
├── logs/          # Application logs
└── cache/         # Cached data
```

## 🏃 Common Workflows

### First-Time Setup

1. **Initialize environment**:
   ```bash
   make docker-init
   ```

2. **Add API keys** to `.env.docker`:
   ```bash
   API_MISTRAL_KEY=your_key_here
   API_OPENROUTER_KEY=your_key_here
   ```

3. **Start services**:
   ```bash
   make docker-dev
   ```

4. **Verify deployment**:
   ```bash
   curl http://localhost:8000/health
   ```

### Development Workflow

1. **Start development environment**:
   ```bash
   make docker-dev
   ```

2. **Edit source code** - changes auto-reload

3. **View logs**:
   ```bash
   make docker-logs-dev
   ```

4. **Run tests**:
   ```bash
   docker exec thoth-app-dev pytest tests/
   ```

5. **Access container for debugging**:
   ```bash
   make docker-shell-dev
   ```

### Production Deployment

1. **Configure production**:
   ```bash
   cp .env.prod.example .env.prod
   # Edit with production values
   ```

2. **Deploy services**:
   ```bash
   make docker-prod
   ```

3. **Set up reverse proxy** (recommended)
4. **Configure SSL/TLS** (recommended)
5. **Set up monitoring**

## 🔍 Troubleshooting

### Service Won't Start

```bash
# Check logs
make docker-logs

# Check resource usage
docker system df

# Clean and rebuild
make docker-clean
make docker-rebuild
```

### Health Check Failures

```bash
# Manual health check
docker exec thoth-app python /app/docker/healthcheck.py

# Check API directly
curl http://localhost:8000/health

# Restart services
make docker-restart
```

### Permission Issues

```bash
# Fix ownership (Linux/macOS)
sudo chown -R 1000:1000 ./workspace

# Or in container
docker exec -u root thoth-app chown -R thoth:thoth /workspace
```

### ChromaDB Connection Issues

```bash
# Check ChromaDB status
docker compose logs chromadb

# Test connectivity
docker exec thoth-app curl http://chromadb:8003/api/v1/heartbeat
```

## 📊 Monitoring

### Health Checks

```bash
# Application health
make docker-health

# Service status
make docker-ps

# Resource usage
docker stats
```

### Log Analysis

```bash
# All services
make docker-logs

# Specific service
docker compose logs -f thoth-app

# Search logs
docker compose logs | grep "ERROR"
```

### Performance Monitoring

```bash
# Container resource usage
docker stats

# Disk usage
docker system df

# Network status
docker network ls
```

## 💾 Data Management

### Backup

```bash
# Create backup directory
mkdir -p backups/$(date +%Y-%m-%d)

# Backup workspace
docker run --rm -v thoth-workspace:/data \
  -v $(pwd)/backups/$(date +%Y-%m-%d):/backup alpine \
  tar czf /backup/workspace.tar.gz -C /data .

# Backup ChromaDB
docker run --rm -v thoth-chroma-data:/data \
  -v $(pwd)/backups/$(date +%Y-%m-%d):/backup alpine \
  tar czf /backup/chromadb.tar.gz -C /data .
```

### Restore

```bash
# Restore workspace
docker run --rm -v thoth-workspace:/data \
  -v $(pwd)/backups/2024-01-01:/backup alpine \
  tar xzf /backup/workspace.tar.gz -C /data

# Restore ChromaDB
docker run --rm -v thoth-chroma-data:/data \
  -v $(pwd)/backups/2024-01-01:/backup alpine \
  tar xzf /backup/chromadb.tar.gz -C /data
```

## 🔒 Security

### Container Security

- ✅ Non-root user execution
- ✅ Read-only filesystems
- ✅ Security scanning with health checks
- ✅ Minimal base images

### Network Security

```bash
# Only expose necessary ports
docker compose ps  # Check exposed ports

# Use internal networks for service communication
# (already configured in docker-compose.yml)
```

### Secrets Management

- Use environment files (`.env.docker`, `.env.prod`)
- Never commit API keys to version control
- Consider external secret management for production

## 📚 Additional Resources

- **[Complete Docker Guide](docs/DOCKER.md)** - Detailed documentation
- **[Deployment Guide](docs/DEPLOYMENT.md)** - Production deployment options
- **[Main README](README.md)** - Project overview and features

## 🆘 Support

- **Issues**: [GitHub Issues](../../issues)
- **Discussions**: [GitHub Discussions](../../discussions)
- **Documentation**: [docs/](docs/)

---

## 🎯 Next Steps

After getting Thoth running with Docker:

1. **Configure Obsidian Plugin** - See [main README](README.md)
2. **Set up Discovery Sources** - Automate paper collection
3. **Customize Prompts** - Tailor AI responses to your needs
4. **Monitor Performance** - Use built-in health checks and logging

Happy researching! 🔬✨
