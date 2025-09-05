# Letta Memory Service - Standalone Deployment

This deployment configuration runs Letta as a **separate, scalable memory service** that can be deployed independently from your main Thoth application.

## 🏗️ Architecture Options

### Option 1: Integrated (Development)
```
Thoth Server → Embedded Letta → Local SQLite
```
- Simple development setup
- Single container deployment
- Limited scalability

### Option 2: Separate Memory Service (Recommended)
```
Thoth Server → HTTP API → Letta Memory Server → PostgreSQL + Redis
```
- Independent scaling
- Better fault isolation
- Production-ready persistence

### Option 3: Microservices (Enterprise)
```
Load Balancer → Multiple Thoth Instances
             → Letta Memory Cluster → Primary/Replica DBs
```
- High availability
- Horizontal scaling
- Multi-tenant support

## 🚀 Quick Start

### 1. Copy Configuration
```bash
cd deployment/letta-memory-service
cp .env.example .env
# Edit .env with your API keys and passwords
```

### 2. Start Memory Service
```bash
# Start with basic setup
docker-compose up -d

# Or start with monitoring
docker-compose --profile monitoring up -d

# Or start with proxy + monitoring
docker-compose --profile proxy --profile monitoring up -d
```

### 3. Verify Service
```bash
# Check health
curl http://localhost:8283/health

# Check through proxy (if enabled)
curl http://localhost:8284/health

# View logs
docker-compose logs letta
```

### 4. Configure Thoth to Use Memory Service
```bash
# In your main Thoth .env file
LETTA_SERVER_URL=http://localhost:8283
# Or for remote deployment:
# LETTA_SERVER_URL=https://memory.yourdomain.com
```

## 📊 Monitoring & Health

### Built-in Health Checks
```bash
# Service health
curl http://localhost:8283/health

# Memory statistics
curl http://localhost:8283/api/memory/stats

# Agent status
curl http://localhost:8283/api/agents
```

### Prometheus Metrics (Optional)
```bash
# Start with monitoring
docker-compose --profile monitoring up -d

# View metrics
open http://localhost:9090
```

### Database Monitoring
```bash
# Connect to PostgreSQL
docker exec -it letta-postgres psql -U letta_user -d letta_memory_db

# Check memory usage
\l+
\dt+ thoth_memory.*
```

## 🔧 Production Configuration

### Environment Variables
```bash
# Security
LETTA_SERVER_PASSWORD=your_secure_password
LETTA_SECURE_MODE=true

# Performance
LETTA_POOL_SIZE=100
LETTA_PG_POOL_SIZE=50
LETTA_PG_MAX_OVERFLOW=100

# High Availability
LETTA_DB_PASSWORD=complex_secure_password
POSTGRES_REPLICAS=2
```

### SSL/TLS Setup
1. Uncomment SSL configuration in `nginx.conf`
2. Mount SSL certificates
3. Update CORS origins for HTTPS

### Scaling Configuration
```yaml
# docker-compose.override.yml
version: '3.8'
services:
  letta:
    deploy:
      replicas: 3
      resources:
        limits:
          memory: 4G
          cpus: '2.0'
    environment:
      LETTA_POOL_SIZE: 100

  postgres:
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4.0'
```

## 🔌 Integration with Thoth

### Connection Configuration
```python
# In your Thoth configuration
LETTA_SERVER_URL=http://letta-memory-service:8283  # Internal Docker network
# Or for external service:
LETTA_SERVER_URL=https://memory.yourdomain.com
```

### MCP Tools Access Memory
Your Thoth agent uses memory through MCP tools:
```python
# Agent automatically has these tools available:
await agent.call_tool('core_memory_append', {
    'memory_block': 'research_focus',
    'content': 'User researching transformers'
})

await agent.call_tool('archival_memory_search', {
    'query': 'attention mechanisms',
    'top_k': 5
})
```

## 📈 Scaling Strategies

### Horizontal Scaling
```bash
# Scale Letta instances
docker-compose up -d --scale letta=3

# Add database replicas
# (Requires custom PostgreSQL setup with primary/replica)
```

### Vertical Scaling
```bash
# Increase resources in docker-compose.yml
services:
  letta:
    deploy:
      resources:
        limits:
          memory: 8G
          cpus: '4.0'
```

### Caching Strategy
- **Redis**: Session and query caching
- **PostgreSQL**: Persistent memory storage
- **Vector Store**: Semantic search optimization

## 🛠️ Maintenance

### Backup Memory Data
```bash
# Database backup
docker exec letta-postgres pg_dump -U letta_user letta_memory_db > memory_backup.sql

# Export agent states
curl -X GET http://localhost:8283/api/agents/export > agents_backup.json
```

### Update Letta Version
```bash
# Pull latest image
docker-compose pull letta

# Restart with new version
docker-compose up -d letta
```

### Performance Tuning
```bash
# Monitor resource usage
docker stats

# Check database performance
docker exec -it letta-postgres psql -U letta_user -d letta_memory_db -c "
SELECT schemaname,tablename,attname,n_distinct,correlation
FROM pg_stats
WHERE schemaname = 'thoth_memory';"
```

## 🚨 Troubleshooting

### Common Issues

1. **Connection Refused**
   ```bash
   # Check if Letta is running
   docker-compose ps
   curl http://localhost:8283/health
   ```

2. **Memory Limits Exceeded**
   ```bash
   # Check memory usage
   docker exec letta curl http://localhost:8283/api/memory/stats
   ```

3. **Database Connection Issues**
   ```bash
   # Check PostgreSQL
   docker-compose logs postgres
   docker exec -it letta-postgres pg_isready
   ```

### Recovery Procedures

1. **Service Recovery**
   ```bash
   docker-compose restart letta
   ```

2. **Database Recovery**
   ```bash
   docker-compose down
   docker volume rm letta-memory-service_letta_postgres_data
   docker-compose up -d
   ```

## 💡 Benefits of Separate Memory Service

- **Independent Scaling**: Scale memory service based on usage
- **Fault Isolation**: Memory issues don't affect main Thoth service
- **Resource Optimization**: Dedicated resources for memory operations
- **Multi-Tenant Support**: Single memory service for multiple Thoth instances
- **Backup & Recovery**: Separate backup strategies for memory data
- **Performance**: Specialized hardware/configuration for memory workloads

This setup gives you enterprise-grade memory capabilities while maintaining clean separation of concerns!
