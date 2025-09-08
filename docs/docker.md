# Docker Deployment Guide for Thoth AI Research Assistant

This guide provides comprehensive instructions for deploying Thoth using Docker containers for both development and production environments.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture Overview](#architecture-overview)
- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Production Deployment](#production-deployment)
- [Configuration](#configuration)
- [Maintenance and Operations](#maintenance-and-operations)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

## Quick Start

### Development Environment

1. **Initialize Docker environment**:
   ```bash
   make docker-init
   ```

2. **Configure environment variables**:
   ```bash
   # Edit .env.docker with your API keys
   cp .env.docker.example .env.docker
   nano .env.docker
   ```

3. **Start development services**:
   ```bash
   make docker-dev
   ```

4. **Access services**:
   - API Server: http://localhost:8000
   - MCP Server: http://localhost:8001
   - ChromaDB: http://localhost:8003

### Production Environment

1. **Configure production environment**:
   ```bash
   cp .env.prod.example .env.prod
   nano .env.prod
   ```

2. **Deploy production services**:
   ```bash
   make docker-prod
   ```

## Recent Updates (v0.1.0+)

### Compatibility Improvements

The Docker infrastructure has been updated to ensure full compatibility with the current repository state:

- **CLI Integration**: Updated Docker commands to use `python -m thoth server start` (replaces deprecated `api` subcommand)
- **UV Package Manager**: Migrated to `uv` for faster Python package management with proper caching
- **Environment Variables**: Fixed service startup configuration and environment variable references
- **Build Optimization**: Implemented uv best practices with cache mounting and multi-stage builds

### Migration Notes

If you're updating from a previous version:
1. Rebuild all Docker images: `make docker-rebuild`
2. Update environment files to match new `.env.docker.example` format
3. Review volume mappings if you have custom configurations

## Architecture Overview

### Container Architecture

Thoth uses a **hybrid multi-container architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Network (thoth-network)           │
│                                                             │
│  ┌─────────────────┐              ┌─────────────────┐      │
│  │   thoth-app     │              │   chromadb      │      │
│  │  ┌─────────────┐│              │  ┌─────────────┐│      │
│  │  │ API Server  ││──────────────│  │ Vector DB   ││      │
│  │  │ (Port 8000) ││              │  │ (Port 8003) ││      │
│  │  └─────────────┘│              │  └─────────────┘│      │
│  │  ┌─────────────┐│              └─────────────────┘      │
│  │  │ MCP Server  ││                                       │
│  │  │ (Port 8001) ││              ┌─────────────────┐      │
│  │  └─────────────┘│              │   Volumes       │      │
│  │  ┌─────────────┐│              │  ┌─────────────┐│      │
│  │  │ Agent System││              │  │ Workspace   ││      │
│  │  │ + Services  ││              │  │ Data        ││      │
│  │  └─────────────┘│              │  │ Logs        ││      │
│  └─────────────────┘              │  │ Cache       ││      │
│                                   │  └─────────────┘│      │
│                                   └─────────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Key Components

1. **thoth-app**: Main application container containing:
   - FastAPI server (REST API + WebSocket)
   - MCP (Model Context Protocol) server
   - Research agent system with LangGraph
   - All Thoth services (LLM, RAG, Discovery, Citation, etc.)

2. **chromadb**: Dedicated ChromaDB container for:
   - Vector embeddings storage
   - Semantic search capabilities
   - Persistent knowledge base

3. **Persistent Volumes**: Data persistence for:
   - Workspace files (PDFs, notes, queries)
   - Application data and cache
   - Log files
   - ChromaDB collections

## Prerequisites

### System Requirements

- **Docker**: Version 20.10 or higher (with BuildKit support for cache mounting)
- **Docker Compose**: Version 2.0 or higher
- **Memory**: Minimum 4GB RAM (8GB recommended)
- **Storage**: Minimum 10GB free space (additional space for uv cache)
- **Platform**: Linux, macOS, or Windows with WSL2

### API Keys Required

At minimum, you need one of the following LLM provider API keys:
- **Mistral API Key**: For OCR and basic LLM operations
- **OpenRouter API Key**: For multi-provider LLM access

Optional API keys for enhanced functionality:
- **OpenCitations API Key**: For citation validation
- **Google API Key**: For web search capabilities
- **Semantic Scholar API Key**: For academic paper discovery

### Installation

1. **Install Docker and Docker Compose**:
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install docker.io docker-compose-plugin

   # macOS (using Homebrew)
   brew install docker docker-compose

   # Or install Docker Desktop
   ```

2. **Verify installation**:
   ```bash
   docker --version
   docker compose version
   ```

3. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd project-thoth
   ```

## Development Setup

### Initialize Development Environment

1. **Create environment configuration**:
   ```bash
   make docker-init
   ```

2. **Configure API keys**:
   ```bash
   # Edit the generated .env.docker file
   nano .env.docker

   # Add your API keys:
   API_MISTRAL_KEY=your_mistral_api_key_here
   API_OPENROUTER_KEY=your_openrouter_api_key_here
   ```

3. **Start development services**:
   ```bash
   # Build and start all services
   make docker-dev

   # Or step by step:
   make docker-build-dev
   make docker-up-dev
   ```

### Development Features

The development environment includes:

- **Hot Reload**: Source code changes automatically restart services
- **Debug Support**: Python debugger accessible on port 5678
- **Volume Mounting**: Source code is mounted for real-time editing
- **Verbose Logging**: Debug-level logging enabled
- **Development Tools**: Pre-installed debugging and testing tools

### Development Workflow

1. **Edit source code** in your preferred editor
2. **Changes are automatically detected** and services restart
3. **View logs** in real-time:
   ```bash
   make docker-logs-dev
   ```
4. **Access interactive shell**:
   ```bash
   make docker-shell-dev
   ```

### Testing in Development

```bash
# Run tests in development container
docker exec thoth-app-dev python -m pytest tests/

# Or access container shell for manual testing
make docker-shell-dev
python -m pytest tests/ -v

# Test specific server functionality
docker exec thoth-app-dev python -m thoth server status
```

## Production Deployment

### Production Configuration

1. **Create production environment file**:
   ```bash
   cp .env.prod.example .env.prod
   nano .env.prod
   ```

2. **Configure production settings**:
   ```bash
   # Essential production configuration
   API_MISTRAL_KEY=prod_mistral_key
   API_OPENROUTER_KEY=prod_openrouter_key

   # Security settings
   THOTH_AUTH_ENABLED=true
   THOTH_JWT_SECRET_KEY=your_secure_jwt_secret
   THOTH_CORS_ALLOWED_ORIGINS=https://yourdomain.com

   # Performance settings
   THOTH_CACHE_TTL=7200
   THOTH_MAX_CONCURRENT_REQUESTS=5
   ```

### Production Deployment Options

#### Single Server Deployment

```bash
# Build production images
make docker-build-prod

# Start production services
make docker-up-prod

# Verify deployment
make docker-health
```

#### Cloud Deployment

For cloud deployment, create persistent directories:

```bash
# Create production data directories
sudo mkdir -p /opt/thoth/{data,workspace,logs,cache}
sudo chown -R 1000:1000 /opt/thoth/

# Deploy with external volumes
docker compose -f docker-compose.prod.yml up -d
```

### Production Security

1. **Use Docker secrets for API keys**:
   ```bash
   echo "your_api_key" | docker secret create mistral_api_key -
   echo "your_other_key" | docker secret create openrouter_api_key -
   ```

2. **Configure firewall**:
   ```bash
   # Only expose necessary ports
   ufw allow 8000/tcp  # API server
   ufw allow 443/tcp   # HTTPS (if using reverse proxy)
   ```

3. **Set up SSL/TLS** (recommended with reverse proxy like nginx)

## Configuration

### Environment Variables

#### Core Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `API_MISTRAL_KEY` | Mistral API key | - | Yes* |
| `API_OPENROUTER_KEY` | OpenRouter API key | - | Yes* |
| `THOTH_API_HOST` | API server host | 0.0.0.0 | No |
| `THOTH_API_PORT` | API server port | 8000 | No |
| `CHROMADB_URL` | ChromaDB URL | http://chromadb:8003 | No |

*At least one LLM provider API key is required.

#### Directory Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `THOTH_WORKSPACE_DIR` | Main workspace | /workspace |
| `THOTH_PDF_DIR` | PDF storage | /workspace/pdfs |
| `THOTH_NOTES_DIR` | Notes directory | /workspace/notes |
| `THOTH_LOGS_DIR` | Log files | /workspace/logs |

#### Performance Settings

| Variable | Description | Default | Production |
|----------|-------------|---------|------------|
| `THOTH_LOG_LEVEL` | Logging level | INFO | INFO |
| `THOTH_CACHE_TTL` | Cache TTL (seconds) | 3600 | 7200 |
| `THOTH_MAX_CONCURRENT_REQUESTS` | Max concurrent requests | 10 | 5 |
| `THOTH_AGENT_TIMEOUT_SECONDS` | Agent timeout | 300 | 180 |

### Volume Configuration

#### Development Volumes

```yaml
volumes:
  - ./src:/app/src                    # Source code hot-reload
  - thoth-workspace-dev:/workspace    # Development data
  - thoth-logs-dev:/workspace/logs    # Development logs
```

#### Production Volumes

```yaml
volumes:
  - thoth-workspace-prod:/workspace   # Production data
  - /opt/thoth/logs:/workspace/logs   # External log directory
  - /opt/thoth/cache:/workspace/cache # External cache directory
```

## Maintenance and Operations

### Service Management

```bash
# Check service status
make docker-ps

# View service logs
make docker-logs

# Restart services
make docker-restart

# Health check
make docker-health
```

### Data Management

#### Backup

```bash
# Create backup directory
mkdir -p backups/$(date +%Y-%m-%d)

# Backup workspace data
docker run --rm -v thoth-workspace-prod:/data -v $(pwd)/backups/$(date +%Y-%m-%d):/backup alpine tar czf /backup/workspace.tar.gz -C /data .

# Backup ChromaDB
docker run --rm -v thoth-chroma-data-prod:/data -v $(pwd)/backups/$(date +%Y-%m-%d):/backup alpine tar czf /backup/chromadb.tar.gz -C /data .
```

#### Restore

```bash
# Restore workspace
docker run --rm -v thoth-workspace-prod:/data -v $(pwd)/backups/2024-01-01:/backup alpine tar xzf /backup/workspace.tar.gz -C /data

# Restore ChromaDB
docker run --rm -v thoth-chroma-data-prod:/data -v $(pwd)/backups/2024-01-01:/backup alpine tar xzf /backup/chromadb.tar.gz -C /data
```

### Updates and Upgrades

```bash
# Pull latest images
docker compose pull

# Rebuild and restart
make docker-rebuild

# Or for production
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Monitoring

#### Log Analysis

```bash
# View real-time logs
make docker-logs

# View specific service logs
docker compose logs -f thoth-app

# Search logs
docker compose logs | grep "ERROR"
```

#### Performance Monitoring

```bash
# Container resource usage
docker stats

# Service health check
make docker-health

# Detailed health report
docker exec thoth-app python /app/docker/healthcheck.py
```

## Troubleshooting

### Package Management (UV)

The Docker containers use `uv` (a fast Python package manager) for dependency management:

#### Benefits
- **Faster Builds**: Up to 10x faster than pip for dependency installation
- **Better Caching**: Improved Docker layer caching with mount points
- **Reproducible Builds**: Lock file support for consistent environments
- **Reduced Image Size**: Multi-stage builds with optimized final images

#### UV-Related Troubleshooting

```bash
# Clear uv cache if build issues occur
docker builder prune --filter type=cache

# Rebuild with no cache to force fresh uv sync
docker build --no-cache -t thoth-app:latest .

# Check uv version in container
docker exec thoth-app uv --version
```

### Common Issues

#### 1. Container Won't Start

**Symptoms**: Container exits immediately or fails to start

**Solutions**:
```bash
# Check container logs
docker compose logs thoth-app

# Check resource usage
docker system df

# Clean up if needed
make docker-clean
```

#### 2. ChromaDB Connection Failed

**Symptoms**: API errors related to ChromaDB connectivity

**Solutions**:
```bash
# Check ChromaDB container status
docker compose logs chromadb

# Verify network connectivity
docker exec thoth-app curl -f http://chromadb:8003/api/v1/heartbeat

# Restart services
make docker-restart
```

#### 3. Health Check Failures

**Symptoms**: Health checks continuously fail

**Solutions**:
```bash
# Run manual health check
docker exec thoth-app python /app/docker/healthcheck.py

# Check API server status
curl http://localhost:8000/health

# Restart unhealthy containers
docker compose restart thoth-app
```

#### 4. CLI Command Issues

**Symptoms**: Container starts but server doesn't respond

**Diagnosis**: Check if the container is using the correct CLI commands
```bash
# Check running process in container
docker exec thoth-app ps aux

# Should show: python -m thoth server start --api-host 0.0.0.0 --api-port 8000 --no-discovery --no-mcp
```

**Solutions**:
```bash
# Manual server start for debugging
docker exec -it thoth-app python -m thoth server start --api-host 0.0.0.0 --api-port 8000

# Check available CLI commands
docker exec thoth-app python -m thoth --help

# Test server startup
docker exec thoth-app python -m thoth server status
```

#### 5. Permission Issues

**Symptoms**: File permission errors in logs

**Solutions**:
```bash
# Fix ownership of volume directories
sudo chown -R 1000:1000 /opt/thoth/

# Or in development
docker exec -u root thoth-app chown -R thoth:thoth /workspace
```

#### 6. Out of Memory

**Symptoms**: Container gets killed (OOMKilled)

**Solutions**:
```bash
# Increase container memory limits
# Edit docker-compose.yml:
deploy:
  resources:
    limits:
      memory: 4G

# Or add swap space to host system
```

### Debug Mode

Enable debug mode for detailed troubleshooting:

```bash
# Set environment variable
echo "THOTH_LOG_LEVEL=DEBUG" >> .env.docker

# Restart services
make docker-restart

# View debug logs
make docker-logs
```

### Container Shell Access

```bash
# Access main application container
make docker-shell

# Access as root (for system troubleshooting)
docker exec -u root -it thoth-app /bin/bash

# Access ChromaDB container
docker exec -it thoth-chromadb /bin/bash
```

## Advanced Usage

### Custom Network Configuration

```yaml
# docker-compose.override.yml
networks:
  thoth-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.25.0.0/16
    driver_opts:
      com.docker.network.mtu: 1450
```

### Resource Limits

```yaml
# Production resource limits
services:
  thoth-app:
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.5'
        reservations:
          memory: 1G
          cpus: '0.5'
```

### Multiple Environments

```bash
# Run multiple environments simultaneously
docker compose -p thoth-dev -f docker-compose.dev.yml up -d
docker compose -p thoth-staging -f docker-compose.yml up -d
docker compose -p thoth-prod -f docker-compose.prod.yml up -d
```

### Integration with CI/CD

```yaml
# .github/workflows/docker.yml
name: Docker Build and Deploy
on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Build Docker images
        run: make docker-build-prod
      - name: Deploy to production
        run: make docker-up-prod
```

### Custom SSL/TLS Setup

```yaml
# docker-compose.prod.yml with nginx proxy
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/ssl:/etc/nginx/ssl:ro
    depends_on:
      - thoth-app
```

## Support and Community

- **Documentation**: [docs/](../docs/)
- **Issues**: [GitHub Issues](../../issues)
- **Discussions**: [GitHub Discussions](../../discussions)

### Recent Improvements

The Docker infrastructure has been significantly improved in version 0.1.0+:

- **UV Package Manager**: 10x faster builds with better caching
- **CLI Compatibility**: Full integration with current `server start` command structure
- **Build Optimization**: Multi-stage builds reduce final image size
- **Environment Fixes**: Corrected all environment variable references
- **Health Checks**: Comprehensive service health monitoring

For additional support, please check the troubleshooting section or open an issue on GitHub.
