# Thoth AI Research Assistant - Microservices Architecture

## Overview

This document describes the complete microservices Docker architecture for the Thoth AI Research Assistant system. The architecture splits the monolithic application into separate, scalable services that can be independently deployed, scaled, and maintained.

## Architecture Summary

### Previous Architecture Issues
- **Monolithic container**: All services running in single container
- **Port conflicts**: ChromaDB and API server competing for port 8000
- **Limited scalability**: Cannot scale individual services
- **Debugging challenges**: Mixed logs and processes
- **Production limitations**: Single point of failure

### New Microservices Architecture
- **Service separation**: Each service in its own container
- **Independent scaling**: Scale services based on load
- **Port isolation**: Dedicated ports for each service
- **Service discovery**: Internal networking for communication
- **Production-ready**: Monitoring, secrets management, load balancing

## Service Architecture

### Core Services
1. **Thoth API Server** (`thoth-api`)
   - Port: 8000
   - Replicas: 3 (production)
   - Purpose: Main REST API and WebSocket endpoints
   - Dockerfile: `/home/nick/python/project-thoth/docker/api/Dockerfile`

2. **MCP Server** (`thoth-mcp`)
   - Port: 8001
   - Replicas: 2 (production)
   - Purpose: Model Context Protocol server
   - Dockerfile: `/home/nick/python/project-thoth/docker/mcp/Dockerfile`

3. **Discovery Service** (`thoth-discovery`)
   - Port: 8004
   - Replicas: 2 (production)
   - Purpose: Paper discovery and web scraping
   - Dockerfile: `/home/nick/python/project-thoth/docker/discovery/Dockerfile`

4. **Research Agent** (`thoth-agent`)
   - Port: 8005
   - Replicas: 2 (production)
   - Purpose: Interactive AI research assistant
   - Dockerfile: `/home/nick/python/project-thoth/docker/agent/Dockerfile`

5. **PDF Monitor** (`thoth-pdf-monitor`)
   - Background service
   - Replicas: 1 (production)
   - Purpose: Monitor and process PDF files
   - Dockerfile: `/home/nick/python/project-thoth/docker/pdf-monitor/Dockerfile`

### Infrastructure Services
1. **ChromaDB** (`chromadb`)
   - Port: 8003 (fixed port conflict)
   - Purpose: Vector database for RAG operations
   - Image: `chromadb/chroma:latest`

2. **PostgreSQL** (`letta-postgres`)
   - Port: 5432 (internal)
   - Purpose: Database for Letta memory system
   - Image: `postgres:15-alpine`

3. **Redis** (`redis`)
   - Port: 6379 (internal)
   - Purpose: Session management and caching
   - Image: `redis:7-alpine`

4. **Letta Memory** (`letta`)
   - Port: 8283
   - Purpose: Advanced persistent memory system
   - Image: `letta/letta:latest`

### Supporting Services
1. **Nginx Load Balancer** (`nginx`)
   - Ports: 80, 443
   - Purpose: Reverse proxy and load balancing
   - Config: `/home/nick/python/project-thoth/docker/nginx/prod.conf`

2. **Prometheus** (`prometheus`)
   - Purpose: Metrics collection
   - Config: `/home/nick/python/project-thoth/docker/prometheus/prometheus.yml`

3. **Grafana** (`grafana`)
   - Purpose: Monitoring dashboards

## Docker Compose Configurations

### Development Configuration
- **File**: `/home/nick/python/project-thoth/docker-compose.dev.yml`
- **Features**:
  - Source code mounting for live development
  - Debug logging enabled
  - Exposed ports for direct access
  - Development tools included in containers
  - Faster health check intervals

### Production Configuration
- **File**: `/home/nick/python/project-thoth/docker-compose.prod.yml`
- **Features**:
  - Docker secrets for sensitive data
  - Resource limits and reservations
  - Health checks and restart policies
  - Network isolation (frontend/backend)
  - SSL termination at load balancer
  - Monitoring and observability stack

## Port Allocation

### Production Ports
- `80/443`: Nginx (HTTP/HTTPS)
- `8000`: Thoth API Server
- `8001`: MCP Server
- `8003`: ChromaDB (fixed conflict)
- `8004`: Discovery Service
- `8005`: Research Agent
- `8283`: Letta Memory Service
- `5432`: PostgreSQL (internal)
- `6379`: Redis (internal)

### Development Ports
- `80`: Nginx proxy
- `8000`: Thoth API Server
- `8001`: MCP Server
- `8003`: ChromaDB
- `8004`: Discovery Service
- `8005`: Research Agent
- `8283`: Letta Memory Service
- `5432`: PostgreSQL (exposed for debugging)

## Key Features

### Service Discovery
- Internal Docker networking
- Service-to-service communication via container names
- Environment variables for service URLs
- Health checks for dependency management

### Scaling Capabilities
- Horizontal scaling for stateless services
- Load balancing with Nginx
- Independent service scaling
- Resource allocation per service

### Security
- Docker secrets for sensitive data
- Network isolation (frontend/backend networks)
- Non-root users in containers
- SSL/TLS termination
- Rate limiting and CORS configuration

### Monitoring
- Prometheus metrics collection
- Grafana dashboards
- Structured logging with loguru
- Health check endpoints
- Resource usage monitoring

### Development Experience
- Live code reloading
- Debug-friendly logging
- Direct service access
- Development tools in containers
- Easy service isolation testing

## Deployment Files

### Core Files
1. **Development Compose**: `/home/nick/python/project-thoth/docker-compose.dev.yml`
2. **Production Compose**: `/home/nick/python/project-thoth/docker-compose.prod.yml`
3. **Environment Templates**:
   - `/home/nick/python/project-thoth/.env.example`
   - `/home/nick/python/project-thoth/.env.prod.example`

### Individual Dockerfiles
1. **API Server**: `/home/nick/python/project-thoth/docker/api/Dockerfile`
2. **MCP Server**: `/home/nick/python/project-thoth/docker/mcp/Dockerfile`
3. **Discovery Service**: `/home/nick/python/project-thoth/docker/discovery/Dockerfile`
4. **PDF Monitor**: `/home/nick/python/project-thoth/docker/pdf-monitor/Dockerfile`
5. **Research Agent**: `/home/nick/python/project-thoth/docker/agent/Dockerfile`

### Configuration Files
1. **Nginx Dev**: `/home/nick/python/project-thoth/docker/nginx/dev.conf`
2. **Nginx Prod**: `/home/nick/python/project-thoth/docker/nginx/prod.conf`
3. **Prometheus**: `/home/nick/python/project-thoth/docker/prometheus/prometheus.yml`

### Deployment Tools
1. **Deployment Script**: `/home/nick/python/project-thoth/docker/deploy.sh`
2. **Deployment Guide**: `/home/nick/python/project-thoth/docker/docker-deployment-guide.md`

## Quick Start

### Development
```bash
# Clone repository and navigate to project root
cd /home/nick/python/project-thoth

# Copy and edit environment file
cp .env.example .env.dev
# Edit .env.dev with your API keys

# Deploy development environment
./docker/deploy.sh --env dev

# View logs
./docker/deploy.sh --action logs

# Stop services
./docker/deploy.sh --action stop
```

### Production
```bash
# Setup production environment
./docker/deploy.sh --env prod

# Scale API service
./docker/deploy.sh --scale thoth-api=5

# Check status
./docker/deploy.sh --action status
```

## Benefits of New Architecture

### Scalability
- Independent service scaling
- Load balancing capabilities
- Resource optimization per service
- Better performance under load

### Maintainability
- Service isolation
- Independent deployments
- Cleaner logging and debugging
- Service-specific configurations

### Reliability
- Service redundancy
- Health checks and auto-restart
- Graceful failure handling
- Production monitoring

### Security
- Network isolation
- Secrets management
- SSL termination
- Rate limiting and CORS

### Development Experience
- Faster development cycles
- Service-specific debugging
- Easy testing of individual components
- Live code reloading

## Migration from Monolithic Setup

The new architecture maintains backward compatibility while providing significant improvements:

1. **Same APIs**: External interfaces remain unchanged
2. **Same functionality**: All existing features preserved
3. **Better performance**: Improved scalability and resource usage
4. **Enhanced monitoring**: Better observability and debugging
5. **Production ready**: Security, secrets, and scaling built-in

This microservices architecture provides a solid foundation for scaling the Thoth AI Research Assistant system in production environments while maintaining an excellent development experience.
