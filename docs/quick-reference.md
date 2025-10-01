# 🚀 Thoth Quick Reference Guide

## Service Management Commands

### 🏃 Quick Start
```bash
# One-command deployment (recommended)
export OBSIDIAN_VAULT="/path/to/your/vault"
make deploy-and-start OBSIDIAN_VAULT="$OBSIDIAN_VAULT"

# Start all services
make start

# Check status
make status

# View logs
make logs

# Stop everything
make stop
```

### 🎯 Service Management

| Command | Purpose |
|---------|---------|
| `make deploy-and-start` | Complete deployment + start all services |
| `make deploy-plugin` | Deploy Obsidian plugin only |
| `make start` | Start all Docker services |
| `make stop` | Stop all services |
| `make restart` | Restart all services |
| `make status` | Check service health |
| `make logs` | View service logs |
| `make clean` | Clean build artifacts |

### 🔧 Service Operations

```bash
# Health checks
curl http://localhost:8000/health           # API server
curl http://localhost:8001/health           # MCP server (52 tools)
curl http://localhost:8003/api/v1/heartbeat # ChromaDB
curl http://localhost:8283/health           # Letta memory

# Docker container management
docker ps                                   # View running containers
docker logs thoth-dev-api                   # API server logs
docker logs thoth-dev-mcp                   # MCP server logs
docker logs thoth-dev-letta                 # Letta memory logs
docker logs thoth-dev-chromadb              # ChromaDB logs

# Service monitoring
make status                                 # Check all services
docker compose ps                           # Docker service status
```

## Memory System Commands

### 🧠 Letta Memory Service

```bash
# Memory service management
cd deployment/letta-memory-service
make start                   # Start memory service
make start-prod             # Start with monitoring
make health                 # Check health
make logs                   # View logs
make backup                 # Backup data
make scale                  # Scale replicas
```

### 🧰 Memory Tools (via Agent)

```bash
# Start agent with memory tools
python -m thoth agent

# In chat, use memory tools:
"Use core_memory_append to store my research focus on transformers"
"Use archival_memory_insert to save this key finding: [finding]"
"Use archival_memory_search to find information about attention mechanisms"
"Use memory_stats to show memory usage"
"Use memory_health_check to verify the memory system"
```

## Agent and Chat Commands

### 💬 Interactive Agent
```bash
# Start research assistant
python -m thoth agent

# Test memory integration
python scripts/test_memory_mcp_integration.py

# Agent with specific memory settings
python -m thoth agent --use-letta-memory --enable-memory
```

### 🔧 System Commands
```bash
# Server management
python -m thoth api --host 0.0.0.0 --port 8000   # API server
python -m thoth mcp http --host 0.0.0.0 --port 8001  # MCP server (52 tools)

# MCP tools available to agents
python -m thoth agent                     # Agent with all 52 MCP tools
# In chat: "Use thoth_search_papers to find papers on transformers"
# In chat: "Use memory_stats to show memory usage"
```

## Discovery and Research Commands

### 🔍 Discovery Management
```bash
# Discovery sources
python -m thoth discovery list            # List sources
python -m thoth discovery create          # Create source
python -m thoth discovery run             # Run discovery
python -m thoth discovery server          # Start discovery server
```

### 📚 Knowledge Base
```bash
# RAG operations
python -m thoth rag index                 # Index documents
python -m thoth rag search --query "..."  # Search knowledge base
python -m thoth rag ask --question "..."  # Ask questions
python -m thoth rag stats                 # RAG statistics
```

### 📄 Document Processing
```bash
# PDF processing
python -m thoth monitor --watch-dir ./pdfs --optimized
python -m thoth process --pdf-path ./paper.pdf
```

## Configuration Files

### 📁 Environment Files
```bash
.env                                      # Main application
deployment/letta-memory-service/.env      # Memory service
docker/monitoring/.env                    # Monitoring stack
```

### 🔑 Key Variables
```bash
# Cross-service communication
LETTA_SERVER_URL=http://localhost:8283
THOTH_CHROMADB_URL=http://localhost:8003

# API Keys
API_OPENROUTER_KEY=your_key
API_MISTRAL_KEY=your_key
OPENAI_API_KEY=your_key

# Memory configuration
LETTA_ARCHIVAL_MEMORY_ENABLED=true
LETTA_FALLBACK_ENABLED=true
```

## Service URLs

### 🌐 Development URLs
| Service | URL | Description |
|---------|-----|-------------|
| API Server | http://localhost:8000 | Main REST API + WebSocket |
| MCP Server | http://localhost:8001 | 52 MCP tools |
| ChromaDB | http://localhost:8003 | Vector database |
| Letta Memory | http://localhost:8283 | Persistent agent memory |
| Discovery | http://localhost:8004 | Multi-source paper discovery |

### 🔒 Production URLs
| Service | URL | Access |
|---------|-----|--------|
| Main API | https://thoth.yourdomain.com | Public |
| Memory Service | Internal only | Service-to-service |
| Vector Database | Internal only | Service-to-service |
| Monitoring | https://monitoring.yourdomain.com | VPN/Internal |

## Troubleshooting Quick Fixes

### 🚨 Common Issues

#### Service Won't Start
```bash
# Check logs
./scripts/start-all-services.sh status
make -f Makefile.services logs-memory

# Restart service
docker-compose restart thoth-chat
make -f Makefile.services restart-all
```

#### Memory Service Connection
```bash
# Check Letta health
curl http://localhost:8283/health

# Restart memory service
cd deployment/letta-memory-service
make restart
```

#### Port Conflicts
```bash
# Find what's using ports
netstat -tulpn | grep :8283
sudo fuser -k 8283/tcp

# Use different ports
# Edit docker-compose.yml port mappings
```

#### Resource Issues
```bash
# Check Docker resources
docker system df
docker stats

# Clean up
docker system prune -f
make -f Makefile.services clean-all  # WARNING: deletes data
```

### 🔧 Quick Fixes

```bash
# Full system restart
./scripts/stop-all-services.sh
./scripts/start-all-services.sh dev

# Reset development environment
make -f Makefile.services dev-reset

# Health check all services
make -f Makefile.services health-check

# View all logs
make -f Makefile.services logs-all
```

## Development Workflows

### 🛠️ Service Development

```bash
# Develop memory integration
make -f Makefile.services start-memory
python scripts/test_memory_mcp_integration.py

# Develop chat agent
make -f Makefile.services start-core  # Memory + Vector DB
docker-compose -f docker-compose.dev.yml up -d thoth-app

# Full stack development
./scripts/start-all-services.sh dev
# All services with hot-reload
```

### 🧪 Testing

```bash
# Test service integration
make -f Makefile.services test-integration

# Test memory system
python scripts/test_memory_mcp_integration.py

# Test individual components
python -m thoth agent
# In chat: "Use memory_health_check"
```

## Performance Tuning

### ⚡ Scaling
```bash
# Scale based on load
make -f Makefile.services scale-memory    # Memory service
make -f Makefile.services scale-chat      # Chat service

# Monitor performance
make -f Makefile.services view-metrics
docker stats
```

### 🎛️ Configuration
```bash
# Memory service tuning
LETTA_POOL_SIZE=100                      # Increase connection pool
LETTA_PG_POOL_SIZE=50                    # Database connections

# Main application tuning
THOTH_AGENT_MAX_TOOL_CALLS=30            # More tool calls
THOTH_AGENT_TIMEOUT_SECONDS=600          # Longer timeouts
```

## 📚 Documentation Links

- **[Setup Guide](setup.md)** - Installation and configuration
- **[Service Management](service-management.md)** - Comprehensive service guide
- **[Usage Guide](usage.md)** - Day-to-day usage
- **[API Documentation](api.md)** - REST API and WebSocket reference
- **[Architecture](architecture.md)** - System design overview
- **[Deployment](deployment.md)** - Production deployment guide

---

**Need Help?** Check the full documentation or create an issue on GitHub!
