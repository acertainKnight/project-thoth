# Thoth AI Research Assistant - Docker Deployment Guide

## Architecture Overview

This guide covers the microservices Docker architecture for Thoth, featuring:

### Services Architecture
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Nginx Proxy   │    │  API Gateway    │    │ Load Balancer   │
│    (Port 80)    │────│  (Port 443)     │────│  (Production)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Thoth API     │    │   MCP Server    │    │ Research Agent  │
│   (Port 8000)   │    │   (Port 8001)   │    │  (Port 8005)    │
│   [Scalable]    │    │   [Scalable]    │    │   [Scalable]    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Discovery Svc   │    │ PDF Monitor     │    │  ChromaDB       │
│  (Port 8004)    │    │  (Background)   │    │  (Port 8003)    │
│   [Scalable]    │    │  [Scalable]     │    │   [Database]    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │     Redis       │    │     Letta       │
│  (Port 5432)    │    │  (Port 6379)    │    │  (Port 8283)    │
│   [Database]    │    │    [Cache]      │    │   [Memory]      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Port Allocation

### Production Ports (docker-compose.yml - Base Production)
- **8080**: Thoth API Server (external → 8000 internal)
- **8082**: MCP Server HTTP transport (external → 8000 internal)
- **8081**: MCP Server SSE transport (external → 8001 internal)
- **8283**: Letta Memory Service
- **8284**: Letta Nginx SSE Proxy
- **(internal)**: PostgreSQL Database (5432, no external access)
- **(internal)**: thoth-monitor, thoth-dashboard (no external ports)

### Extended Production Ports (docker-compose.prod.yml)
Adds to base production:
- **80/443**: Nginx reverse proxy (HTTP/HTTPS)
- **9090**: Prometheus (internal, accessed via proxy)
- **3000**: Grafana (internal, accessed via proxy)
- **(internal)**: Redis Cache (6379)
- **(internal)**: ChromaDB (8003)
- **(internal)**: thoth-agent (8005, scalable)

### Development Ports (docker-compose.dev.yml)
- **80/443**: Development Nginx proxy (nginx-dev)
- **8000**: Thoth API Server (with hot-reload)
- **8001**: MCP Server
- **8003**: ChromaDB Vector Database
- **8004**: Discovery Service
- **8283**: Letta Memory Service
- **5433**: PostgreSQL Database (external → 5432 internal, exposed for debugging)

## Deployment Instructions

### 1. Development Deployment

```bash
# Clone the repository
git clone <repository-url>
cd project-thoth

# Copy environment template
cp .env.example .env.dev

# Edit environment variables
vim .env.dev

# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Scale specific services
docker-compose -f docker-compose.dev.yml up -d --scale thoth-api=2
```

### 2. Production Deployment

#### Prerequisites
```bash
# Create production directories
sudo mkdir -p /opt/thoth/{workspace,chroma,postgres,redis,letta,logs,prometheus,grafana}
sudo chown -R 1000:1000 /opt/thoth

# Create secrets directory
mkdir -p secrets

# Generate secrets
echo "$(openssl rand -base64 32)" > secrets/postgres_password.txt
echo "$(openssl rand -base64 32)" > secrets/api_secret_key.txt
echo "$(openssl rand -base64 32)" > secrets/chroma_auth_token.txt
echo "your-openai-api-key" > secrets/openai_api_key.txt
echo "your-anthropic-api-key" > secrets/anthropic_api_key.txt
echo "your-semantic-scholar-key" > secrets/semantic_scholar_api_key.txt
echo "your-web-search-key" > secrets/web_search_api_key.txt
echo "$(openssl rand -base64 32)" > secrets/grafana_admin_password.txt

# Set secure permissions
chmod 600 secrets/*
```

#### SSL Certificate Setup
```bash
# Create SSL directory
mkdir -p docker/nginx/ssl

# Generate self-signed certificate (replace with real certificates)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout docker/nginx/ssl/key.pem \
    -out docker/nginx/ssl/cert.pem \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=yourdomain.com"

# Or copy your real certificates
# cp /path/to/your/cert.pem docker/nginx/ssl/
# cp /path/to/your/key.pem docker/nginx/ssl/
```

#### Production Environment
```bash
# Create production environment file
cp .env.example .env.prod

# Edit production settings
vim .env.prod

# Deploy production stack
docker-compose -f docker-compose.prod.yml up -d

# Monitor deployment
docker-compose -f docker-compose.prod.yml ps
docker-compose -f docker-compose.prod.yml logs -f
```

### 3. Service Scaling

```bash
# Scale API servers
docker-compose -f docker-compose.prod.yml up -d --scale thoth-api=5

# Scale MCP servers
docker-compose -f docker-compose.prod.yml up -d --scale thoth-mcp=3

# Scale Discovery services
docker-compose -f docker-compose.prod.yml up -d --scale thoth-discovery=3

# Scale Agent services
docker-compose -f docker-compose.prod.yml up -d --scale thoth-agent=4
```

## Service Configuration

### Environment Variables

#### Global Settings
- `THOTH_LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)
- `THOTH_PRODUCTION`: Enable production mode
- `THOTH_WORKSPACE_DIR`: Workspace directory path

#### Service Discovery
- `THOTH_CHROMADB_URL`: ChromaDB connection URL
- `THOTH_LETTA_URL`: Letta memory service URL
- `THOTH_REDIS_URL`: Redis cache URL
- `THOTH_API_URL`: API server URL (for inter-service communication)

#### Security
- `THOTH_API_SECRET_KEY`: API encryption key
- `THOTH_CORS_ORIGINS`: Allowed CORS origins
- `REDIS_PASSWORD`: Redis authentication password

### Health Checks

All services include comprehensive health checks:

```bash
# Check service health (Production - docker-compose.yml)
curl http://localhost:8080/health  # API Server (external port)
curl http://localhost:8082/health  # MCP HTTP (external port)
curl http://localhost:8283/v1/health  # Letta Memory
curl http://localhost:8284/nginx-health  # Letta Nginx SSE Proxy

# Check service health (Development - docker-compose.dev.yml)
curl http://localhost:8000/health  # API Server
curl http://localhost:8001/health  # MCP Server
curl http://localhost:8004/health  # Discovery Service
curl http://localhost:8003/api/v1/heartbeat  # ChromaDB
curl http://localhost:8283/v1/health  # Letta Memory
```

## Monitoring & Observability

### Prometheus Metrics
- Service metrics available at `/metrics` endpoints
- Grafana dashboards for visualization
- Alert rules for production monitoring

### Log Aggregation
- Structured logging with loguru
- Centralized log collection
- Log rotation and retention policies

### Service Monitoring
```bash
# View service status
docker-compose -f docker-compose.prod.yml ps

# Check resource usage
docker stats

# View service logs
docker-compose -f docker-compose.prod.yml logs thoth-api
docker-compose -f docker-compose.prod.yml logs thoth-mcp
```

## Backup & Recovery

### Database Backups
```bash
# PostgreSQL backup
docker exec thoth-prod-letta-postgres pg_dump -U letta letta > backup.sql

# ChromaDB backup
docker exec thoth-prod-chromadb cp -r /chroma/chroma /backup/

# Redis backup
docker exec thoth-prod-redis redis-cli SAVE
```

### Volume Backups
```bash
# Backup workspace data
sudo tar -czf thoth-workspace-backup.tar.gz /opt/thoth/workspace/

# Backup all data volumes
sudo tar -czf thoth-full-backup.tar.gz /opt/thoth/
```

## Troubleshooting

### Common Issues

1. **Port Conflicts**
   - Check for existing services: `netstat -tulpn | grep :8000`
   - Modify port mappings in compose files

2. **Memory Issues**
   - Monitor resource usage: `docker stats`
   - Adjust memory limits in compose files

3. **Service Communication**
   - Verify network connectivity: `docker network ls`
   - Check service discovery: `docker exec container nslookup service-name`

4. **Permission Issues**
   - Fix volume permissions: `sudo chown -R 1000:1000 /opt/thoth`
   - Check secret file permissions: `chmod 600 secrets/*`

### Debugging Commands
```bash
# Enter service container
docker exec -it thoth-prod-api bash

# View service logs
docker-compose -f docker-compose.prod.yml logs -f thoth-api

# Check network connectivity
docker exec thoth-prod-api ping chromadb

# Restart specific service
docker-compose -f docker-compose.prod.yml restart thoth-api
```

## Security Considerations

### Production Security
1. **Use Docker secrets** for sensitive data
2. **Enable authentication** on all services
3. **Use internal networks** for service communication
4. **Regular security updates** for base images
5. **Monitor access logs** for suspicious activity

### Network Security
- Internal backend network for service communication
- Frontend network for public access
- No direct database access from outside

### Secret Management
- API keys stored as Docker secrets
- Database passwords in separate files
- SSL certificates properly secured

## Performance Optimization

### Resource Allocation
- CPU and memory limits per service
- Appropriate scaling factors
- Load balancing with Nginx

### Caching Strategy
- Redis for session management
- ChromaDB for vector caching
- Nginx proxy caching

### Monitoring
- Prometheus metrics collection
- Grafana dashboard visualization
- Alert rules for performance issues
