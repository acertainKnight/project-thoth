# 🚀 Thoth Quick Reference Guide

## Service Management Commands

### 🏃 Quick Start
```bash
# Start all services (development)
./scripts/start-all-services.sh dev

# Start all services (production)
./scripts/start-all-services.sh prod

# Check status
./scripts/start-all-services.sh status

# Stop everything
./scripts/stop-all-services.sh
```

### 🎯 Individual Services

| Command | Service | URL |
|---------|---------|-----|
| `make -f Makefile.services start-memory` | Memory (Letta) | http://localhost:8283 |
| `make -f Makefile.services start-chat` | Chat Agent | http://localhost:8000 |
| `make -f Makefile.services start-vector-db` | Vector DB | http://localhost:8003 |
| `make -f Makefile.services start-monitoring` | Monitoring | http://localhost:9090 |

### 🔧 Service Operations

```bash
# Health checks
make -f Makefile.services health-check      # All services
curl http://localhost:8283/health           # Memory service
curl http://localhost:8000/health           # Main API
curl http://localhost:8003/api/v1/heartbeat # Vector DB

# Logs
make -f Makefile.services logs-all          # All logs
make -f Makefile.services logs-memory       # Memory service
make -f Makefile.services logs-chat         # Chat service

# Scaling
make -f Makefile.services scale-memory      # Scale memory replicas
make -f Makefile.services scale-chat        # Scale chat replicas

# Backup
make -f Makefile.services backup-all        # Backup all data
make -f Makefile.services backup-memory     # Memory service only
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
python -m thoth server start               # Unified server
python -m thoth server status             # Server status

# Traditional commands
python -m thoth api                       # API server only
python -m thoth mcp http                  # MCP server only
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
| Service | URL | Login |
|---------|-----|-------|
| Main API | http://localhost:8000 | None |
| MCP Server | http://localhost:8001 | None |
| Memory Service | http://localhost:8283 | None |
| Vector Database | http://localhost:8003 | None |
| Prometheus | http://localhost:9090 | None |
| Grafana | http://localhost:3000 | admin/admin |

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
