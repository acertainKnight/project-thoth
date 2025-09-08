# 🚀 Thoth Service Management Guide

This comprehensive guide covers all aspects of managing Thoth's multi-service architecture, from development to production deployment.

## 🏗️ Service Architecture Overview

Thoth consists of these independent, scalable services:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Thoth Service Ecosystem                      │
├─────────────────────────────────────────────────────────────────┤
│ 🧠 Memory Service     │ 💬 Chat Agent      │ 🔍 Discovery       │
│   (Letta)            │   (Main App)       │   (Optional)       │
│ ┌─────────────────┐  │ ┌─────────────────┐ │ ┌─────────────────┐ │
│ │ Core Memory     │  │ │ Research Agent  │ │ │ ArXiv Sources   │ │
│ │ Recall Memory   │  │ │ MCP Tools       │ │ │ PubMed Sources  │ │
│ │ Archival Memory │  │ │ API Endpoints   │ │ │ Auto-Discovery  │ │
│ │ PostgreSQL      │  │ │ WebSocket       │ │ │ Scheduler       │ │
│ │ Redis Cache     │  │ └─────────────────┘ │ └─────────────────┘ │
│ └─────────────────┘  │                    │                    │
├─────────────────────────────────────────────────────────────────┤
│ 🗄️ Vector Database   │ 📊 Monitoring      │ ⚖️ Load Balancer   │
│   (ChromaDB)         │   (Prometheus)     │   (Nginx)          │
│ ┌─────────────────┐  │ ┌─────────────────┐ │ ┌─────────────────┐ │
│ │ RAG Embeddings  │  │ │ Metrics         │ │ │ SSL Termination │ │
│ │ Semantic Search │  │ │ Dashboards      │ │ │ Load Balancing  │ │
│ │ Document Store  │  │ │ Alerting        │ │ │ Health Checks   │ │
│ └─────────────────┘  │ └─────────────────┘ │ └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start Commands

### All Services Management

```bash
# Start all services (development)
./scripts/start-all-services.sh dev

# Start all services (production)
./scripts/start-all-services.sh prod

# Check status of all services
./scripts/start-all-services.sh status

# Stop all services
./scripts/stop-all-services.sh
```

### Individual Service Management

```bash
# Using service-specific Makefile
make -f Makefile.services help                 # Show all commands

# Start individual services
make -f Makefile.services start-memory         # Memory service only
make -f Makefile.services start-chat           # Chat agent only
make -f Makefile.services start-discovery      # Discovery only
make -f Makefile.services start-monitoring     # Monitoring only
make -f Makefile.services start-vector-db      # Vector database only

# Service combinations
make -f Makefile.services start-core           # Memory + Vector DB
make -f Makefile.services start-app            # Chat + Discovery
make -f Makefile.services start-full           # Everything + Monitoring
```

## 🎯 Service-Specific Management

### 1. 🧠 Memory Service (Letta)

The memory service provides hierarchical memory with self-editing capabilities.

#### Basic Operations
```bash
cd deployment/letta-memory-service

# Start memory service
make start                    # Basic setup
make start-prod              # With monitoring & load balancing

# Service management
make stop                    # Stop service
make restart                 # Restart service
make health                  # Check health
make logs                    # View logs
make status                  # Service status

# Scaling and maintenance
make scale                   # Interactive scaling
make backup                  # Backup memory data
make restore                 # Restore from backup
make clean                   # Clean everything (WARNING: deletes data)
```

#### Advanced Operations
```bash
# Scale to multiple replicas
make scale
# Enter number of replicas when prompted

# Performance testing
make test-memory
make benchmark

# Database operations
make shell                   # Connect to container
# Inside container: psql -U letta_user letta_memory_db
```

#### Configuration
```bash
# Edit memory service configuration
nano deployment/letta-memory-service/.env

# Key settings:
LETTA_SERVER_URL=http://localhost:8283
LETTA_DB_PASSWORD=secure_password
LETTA_POOL_SIZE=50
LETTA_ARCHIVAL_MEMORY_ENABLED=true
LETTA_FALLBACK_ENABLED=true
```

### 2. 💬 Chat Agent Service

The main application containing the research agent, MCP tools, and API endpoints.

#### Basic Operations
```bash
# Start chat service (development)
docker-compose -f docker-compose.dev.yml up -d thoth-app

# Start chat service (production)
docker-compose -f docker-compose.prod.yml up -d thoth-app

# Service management
docker-compose logs -f thoth-app           # View logs
docker-compose restart thoth-app           # Restart service
docker-compose stop thoth-app              # Stop service
```

#### Using Service Management
```bash
# Via service manager
make -f Makefile.services start-chat       # Start chat service
make -f Makefile.services logs-chat        # View logs
make -f Makefile.services scale-chat       # Scale replicas

# Health checks
curl http://localhost:8000/health          # Main API health
curl http://localhost:8001/health          # MCP server health
```

#### Configuration
```bash
# Edit main application configuration
nano .env

# Key settings for service integration:
LETTA_SERVER_URL=http://localhost:8283     # Connect to memory service
THOTH_CHROMADB_URL=http://localhost:8003   # Connect to vector DB
API_OPENROUTER_KEY=your_key
API_MISTRAL_KEY=your_key
```

### 3. 🔍 Discovery Service

Automated paper discovery can run integrated or as a separate service.

#### Integrated Mode (Default)
```bash
# Discovery runs within the chat service
# No additional setup needed

# Manage via CLI
python -m thoth discovery list
python -m thoth discovery run --source "arxiv_ml"
python -m thoth discovery create --name "new_source"
```

#### Standalone Mode
```bash
# Start as separate service
docker-compose -f deployment/docker-compose.services.yml up -d thoth-discovery

# Or via Python
python -m thoth discovery server

# Management
make -f Makefile.services logs-discovery
```

### 4. 🗄️ Vector Database (ChromaDB)

Semantic search and RAG capabilities.

#### Operations
```bash
# Start vector database
docker-compose up -d chromadb

# Or via service manager
make -f Makefile.services start-vector-db

# Health check
curl http://localhost:8003/api/v1/heartbeat

# View collections
curl http://localhost:8003/api/v1/collections

# Management
docker-compose logs chromadb
docker-compose restart chromadb
```

#### Backup and Restore
```bash
# Backup vector database
make -f Makefile.services backup-vector

# Manual backup
docker exec thoth-vector-db tar czf - /chroma/chroma > chromadb_backup.tar.gz

# Restore
docker run --rm -v thoth-vector-data:/data -v $(pwd):/backup alpine tar xzf /backup/chromadb_backup.tar.gz -C /data
```

### 5. 📊 Monitoring Stack

Comprehensive monitoring with Prometheus and Grafana.

#### Operations
```bash
# Start monitoring stack
docker-compose -f docker/monitoring/docker-compose.monitoring.yml --profile monitoring up -d

# Or via service manager
make -f Makefile.services start-monitoring

# Access dashboards
make -f Makefile.services open-grafana      # http://localhost:3000
make -f Makefile.services open-prometheus   # http://localhost:9090

# View metrics summary
make -f Makefile.services view-metrics
```

#### Configuration
```bash
# Edit monitoring configuration
nano docker/monitoring/prometheus/prometheus.yml
nano docker/monitoring/grafana/provisioning/

# Custom dashboards
# Add .json files to docker/monitoring/grafana/dashboards/
```

## 🔄 Scaling and Load Management

### Horizontal Scaling

#### Scale Individual Services
```bash
# Scale memory service
cd deployment/letta-memory-service
make scale
# Enter desired number of replicas

# Scale chat service
make -f Makefile.services scale-chat

# Scale via Docker Compose
docker-compose -f deployment/docker-compose.services.yml up -d --scale thoth-chat=3 --scale letta-memory=2
```

#### Load Balancing Setup
```bash
# Start with load balancer
docker-compose -f deployment/docker-compose.services.yml --profile loadbalancer up -d

# Access via load balancer
curl http://localhost:80/health
```

### Vertical Scaling

Edit resource limits in docker-compose files:

```yaml
# deployment/docker-compose.services.yml
services:
  letta-memory:
    deploy:
      resources:
        limits:
          memory: 8G        # Increase memory
          cpus: '4.0'       # Increase CPU
        reservations:
          memory: 2G
          cpus: '1.0'

  thoth-chat:
    deploy:
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
```

## 📊 Monitoring and Health Management

### Health Checks

#### All Services
```bash
# Comprehensive health check
make -f Makefile.services health-check

# Or via orchestration script
./scripts/start-all-services.sh status
```

#### Individual Services
```bash
# Memory service
curl http://localhost:8283/health
cd deployment/letta-memory-service && make health

# Main API
curl http://localhost:8000/health

# MCP server
curl http://localhost:8001/health

# Vector database
curl http://localhost:8003/api/v1/heartbeat

# Monitoring
curl http://localhost:9090/-/healthy
```

### Metrics and Logs

#### Centralized Logging
```bash
# View all service logs
make -f Makefile.services logs-all

# Individual service logs
make -f Makefile.services logs-memory
make -f Makefile.services logs-chat
make -f Makefile.services logs-discovery

# Real-time log monitoring
docker-compose -f deployment/docker-compose.services.yml logs -f
```

#### Metrics Collection
```bash
# View service metrics summary
make -f Makefile.services view-metrics

# Access Prometheus metrics
curl http://localhost:9090/api/v1/query?query=up

# Memory service specific metrics
curl http://localhost:8283/api/memory/stats
```

### Performance Monitoring

#### Resource Usage
```bash
# Container resource usage
docker stats

# Service-specific resource monitoring
docker stats thoth-memory-service thoth-chat-service thoth-vector-db
```

#### Performance Testing
```bash
# Memory service performance
cd deployment/letta-memory-service
make benchmark

# Integration testing
make -f Makefile.services test-integration

# Load testing
python scripts/load_test_services.py
```

## 🛠️ Maintenance Operations

### Backup and Recovery

#### Automated Backups
```bash
# Backup all services
make -f Makefile.services backup-all

# Individual service backups
make -f Makefile.services backup-memory     # Memory service data
make -f Makefile.services backup-vector     # Vector database
```

#### Manual Backup Procedures
```bash
# Memory service backup
cd deployment/letta-memory-service
make backup
# Creates timestamped backup in ./backups/

# Vector database backup
docker exec thoth-vector-db tar czf - /chroma/chroma > chromadb_backup_$(date +%Y%m%d_%H%M%S).tar.gz

# Configuration backup
tar czf config_backup_$(date +%Y%m%d_%H%M%S).tar.gz .env deployment/letta-memory-service/.env docker/monitoring/
```

#### Restore Procedures
```bash
# Memory service restore
cd deployment/letta-memory-service
make restore
# Select backup file when prompted

# Vector database restore
docker run --rm -v thoth-vector-data:/data -v $(pwd):/backup alpine tar xzf /backup/chromadb_backup.tar.gz -C /data
```

### Updates and Upgrades

#### Service Updates
```bash
# Update all services
./scripts/stop-all-services.sh
git pull
./scripts/start-all-services.sh prod

# Update individual services
docker-compose pull letta-memory
docker-compose up -d letta-memory

# Update main application
docker-compose pull thoth-app
docker-compose up -d thoth-app
```

#### Rolling Updates
```bash
# Update without downtime (requires multiple replicas)
docker-compose -f deployment/docker-compose.services.yml up -d --scale thoth-chat=2
# Update one instance at a time
```

### Clean Maintenance

#### Clean Restart
```bash
# Development environment reset
make -f Makefile.services dev-reset

# Clean restart (preserves data)
./scripts/stop-all-services.sh
docker system prune -f
./scripts/start-all-services.sh prod
```

#### Full Cleanup (WARNING: Deletes Data)
```bash
# Complete cleanup
make -f Makefile.services clean-all
# Type 'DELETE' when prompted to confirm
```

## 🔧 Development Workflows

### Service-by-Service Development

#### Memory Service Development
```bash
# Start only memory service for development
make -f Makefile.services start-memory

# Test memory integration
python scripts/test_memory_mcp_integration.py

# Develop memory tools
# Edit src/thoth/mcp/tools/memory_tools.py
# Test via: python -m thoth agent
# In chat: "Use memory_health_check to test"
```

#### Chat Agent Development
```bash
# Start core services (memory + vector DB)
make -f Makefile.services start-core

# Start chat service with hot-reload
docker-compose -f docker-compose.dev.yml up -d thoth-app

# Develop and test
# Edit src/thoth/ingestion/agent_v2/
# Changes auto-reload in development mode
```

#### Discovery Service Development
```bash
# Start discovery in standalone mode
python -m thoth discovery server

# Or integrated mode
make -f Makefile.services start-app

# Test discovery
python -m thoth discovery run --source "test_source"
```

### Full Stack Development
```bash
# Start complete development environment
./scripts/start-all-services.sh dev

# This provides:
# - Hot-reload for main application
# - Full memory service with Letta
# - Vector database for RAG
# - Optional monitoring stack
# - All MCP tools available
```

## 🎛️ Configuration Management

### Environment Files

```bash
# Main application configuration
.env                                          # Main app settings

# Service-specific configurations
deployment/letta-memory-service/.env          # Memory service
docker/monitoring/.env                        # Monitoring (if used)

# Docker-specific configurations
.env.docker                                   # Single container mode
.env.prod                                     # Production settings
```

### Key Configuration Variables

#### Cross-Service Communication
```bash
# In main .env file
LETTA_SERVER_URL=http://localhost:8283       # Memory service connection
THOTH_CHROMADB_URL=http://localhost:8003     # Vector DB connection

# In memory service .env
LETTA_SERVER_URL=http://localhost:8283
LETTA_DB_PASSWORD=secure_password
LETTA_POOL_SIZE=50
```

#### Service-Specific Settings
```bash
# Memory Service (deployment/letta-memory-service/.env)
LETTA_CORE_MEMORY_LIMIT=10000
LETTA_ARCHIVAL_MEMORY_ENABLED=true
LETTA_RECALL_MEMORY_ENABLED=true
LETTA_CONSOLIDATION_INTERVAL_HOURS=24

# Main Application (.env)
API_OPENROUTER_KEY=your_openrouter_key
API_MISTRAL_KEY=your_mistral_key
THOTH_AGENT_MAX_TOOL_CALLS=20
THOTH_AGENT_TIMEOUT_SECONDS=300

# Monitoring (docker/monitoring/.env)
GRAFANA_PASSWORD=secure_admin_password
PROMETHEUS_RETENTION=30d
```

## 🚨 Troubleshooting

### Service-Specific Issues

#### Memory Service Issues
```bash
# Check Letta connectivity
curl http://localhost:8283/health

# Check database
cd deployment/letta-memory-service
docker-compose logs letta-postgres

# Check memory service logs
make logs

# Common fixes
make restart                 # Restart service
make clean && make start     # Clean restart (loses data)
```

#### Chat Service Issues
```bash
# Check main API
curl http://localhost:8000/health

# Check MCP server
curl http://localhost:8001/health

# View logs
docker-compose logs -f thoth-app

# Common fixes
docker-compose restart thoth-app
docker-compose down && docker-compose up -d
```

#### Vector Database Issues
```bash
# Check ChromaDB
curl http://localhost:8003/api/v1/heartbeat

# View collections
curl http://localhost:8003/api/v1/collections

# Restart database
docker-compose restart chromadb

# Rebuild index if needed
python -m thoth rag index --force
```

### Cross-Service Issues

#### Network Connectivity
```bash
# Check Docker networks
docker network ls | grep thoth

# Test inter-service connectivity
docker exec thoth-chat-service curl http://letta-memory:8283/health
docker exec thoth-chat-service curl http://chromadb:8003/api/v1/heartbeat
```

#### Port Conflicts
```bash
# Check port usage
netstat -tulpn | grep :8283  # Memory service
netstat -tulpn | grep :8000  # Main API
netstat -tulpn | grep :8001  # MCP server
netstat -tulpn | grep :8003  # Vector DB

# Kill conflicting processes
sudo fuser -k 8283/tcp
sudo fuser -k 8000/tcp
```

#### Resource Exhaustion
```bash
# Check Docker resources
docker system df
docker stats

# Clean up if needed
docker system prune -f
docker volume prune -f

# Adjust resource limits
# Edit docker-compose files to increase memory/CPU limits
```

## 🏭 Production Deployment

### Production Architecture Options

#### Option 1: Single Server Multi-Service
```bash
# Deploy all services on one server
./scripts/start-all-services.sh prod

# Services available:
# - Memory Service: http://localhost:8283
# - Main API: http://localhost:8000
# - MCP Server: http://localhost:8001
# - Vector DB: http://localhost:8003
# - Monitoring: http://localhost:9090, http://localhost:3000
```

#### Option 2: Distributed Services
```bash
# Memory service on dedicated server
# Server 1: Memory + Database
cd deployment/letta-memory-service
make start-prod

# Server 2: Chat Agent + Vector DB
# Edit .env: LETTA_SERVER_URL=http://memory-server:8283
make -f Makefile.services start-app

# Server 3: Monitoring
make -f Makefile.services start-monitoring
```

#### Option 3: Kubernetes Deployment
```bash
# Deploy to Kubernetes
kubectl apply -f deployment/kubernetes/letta-memory-service.yaml

# Scale in Kubernetes
kubectl scale deployment letta-memory --replicas=3 -n thoth-memory
kubectl scale deployment thoth-chat --replicas=2 -n thoth
```

### Production Security

#### Secure Configuration
```bash
# Use secure passwords
LETTA_DB_PASSWORD=complex_secure_password_change_in_production
LETTA_SERVER_PASSWORD=api_access_password
GRAFANA_PASSWORD=monitoring_password

# Enable SSL
# Configure nginx with SSL certificates
# Use Docker secrets for sensitive data
```

#### Network Security
```bash
# Configure firewall
ufw allow 22/tcp     # SSH
ufw allow 80/tcp     # HTTP (nginx)
ufw allow 443/tcp    # HTTPS (nginx)
ufw deny 8000/tcp    # Block direct API access
ufw deny 8283/tcp    # Block direct memory service access
```

### Production Monitoring

#### Health Monitoring
```bash
# Automated health checks
make -f Makefile.services health-check

# Set up monitoring alerts
# Configure Grafana alerts for service downtime
# Set up Prometheus alerting rules
```

#### Performance Monitoring
```bash
# Service metrics
curl http://localhost:9090/api/v1/query?query=up

# Memory service metrics
curl http://localhost:8283/api/memory/stats

# Application metrics
curl http://localhost:8000/metrics
```

## 📋 Service Management Cheat Sheet

### Daily Operations
```bash
# Check all services
./scripts/start-all-services.sh status

# Restart problematic service
docker-compose restart thoth-chat

# View recent logs
make -f Makefile.services logs-chat | tail -100

# Check resource usage
docker stats --no-stream
```

### Weekly Maintenance
```bash
# Backup all data
make -f Makefile.services backup-all

# Update services
docker-compose pull
./scripts/stop-all-services.sh
./scripts/start-all-services.sh prod

# Clean old data
docker system prune -f
```

### Emergency Procedures
```bash
# Service completely down
./scripts/stop-all-services.sh
./scripts/start-all-services.sh prod

# Data corruption
# Restore from backup
cd deployment/letta-memory-service
make restore

# Network issues
docker network prune
docker-compose down && docker-compose up -d
```

## 🎉 Service URLs Quick Reference

| Service | Development URL | Production URL | Purpose |
|---------|----------------|----------------|---------|
| **Main API** | http://localhost:8000 | https://yourdomain.com | Research agent, chat interface |
| **MCP Server** | http://localhost:8001 | Internal only | Tool protocol server |
| **Memory Service** | http://localhost:8283 | Internal only | Letta hierarchical memory |
| **Vector Database** | http://localhost:8003 | Internal only | ChromaDB for RAG |
| **Prometheus** | http://localhost:9090 | Internal/VPN | Metrics collection |
| **Grafana** | http://localhost:3000 | https://monitoring.yourdomain.com | Dashboards (admin/admin) |
| **Load Balancer** | http://localhost:80 | https://yourdomain.com | High availability proxy |

## 💡 Best Practices

### Development
- Use `./scripts/start-all-services.sh dev` for full development stack
- Start only needed services: `make -f Makefile.services start-core`
- Test memory integration: `python scripts/test_memory_mcp_integration.py`
- Monitor logs: `make -f Makefile.services logs-all`

### Production
- Use `./scripts/start-all-services.sh prod` for production deployment
- Enable monitoring: Include `--profile monitoring` in Docker commands
- Set up automated backups: `make -f Makefile.services backup-all`
- Configure SSL/TLS for external access
- Use secure passwords and API keys
- Monitor service health: `make -f Makefile.services health-check`

### Scaling
- Scale memory service based on conversation volume
- Scale chat service based on user load
- Monitor resource usage: `docker stats`
- Use load balancer for high availability
- Implement database replicas for large deployments

This comprehensive service management system gives you complete control over your Thoth deployment, from development to enterprise production!
