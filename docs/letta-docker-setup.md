# Letta Docker Setup Guide

This guide provides comprehensive instructions for setting up Letta memory service with Docker in the Thoth project, aligned with official Letta documentation and best practices.

## Overview

Letta is an advanced persistent memory system for AI agents, providing multi-scope memory (core/episodic/archival), salience-based retention, and cross-session persistence. This setup integrates Letta with PostgreSQL and pgvector for optimal performance.

## Prerequisites

- Docker and Docker Compose installed
- PostgreSQL with pgvector extension support
- API keys for LLM providers (OpenAI, Anthropic, etc.)

## Architecture

The Letta service runs alongside:
- **PostgreSQL with pgvector**: Vector storage and database persistence
- **Thoth Application**: Main research assistant that uses Letta for memory
- **ChromaDB**: Separate vector store for RAG operations

## Configuration

### Environment Variables

The following environment variables are properly configured according to Letta's official documentation:

#### Core Server Configuration
```bash
LETTA_SERVER_HOST=0.0.0.0
LETTA_SERVER_PORT=8283
LETTA_PG_URI=postgresql://letta:letta_password@letta-postgres:5432/letta
```

#### PostgreSQL Connection Pool (Official Letta Variables)
```bash
LETTA_PG_POOL_SIZE=20           # Database connection pool size
LETTA_PG_MAX_OVERFLOW=30        # Maximum overflow connections
LETTA_PG_POOL_TIMEOUT=30        # Connection timeout in seconds
LETTA_PG_POOL_RECYCLE=1800      # Connection recycle time in seconds
```

#### Security Configuration
```bash
SECURE=true                                    # Enable security features
LETTA_SERVER_PASSWORD=${LETTA_SERVER_PASSWORD} # Server access password
```

#### Tool Execution Environment
```bash
TOOL_EXEC_VENV_NAME=letta-tools    # Virtual environment for custom tools
```

#### File System Configuration
```bash
LETTA_DATA_DIR=/letta/.persist     # Data persistence directory
HOME=/letta                        # Home directory for Letta
```

### Docker Compose Configuration

The Letta service is configured in `docker-compose.yml` with:

1. **Proper startup command**: `letta server --host 0.0.0.0 --port 8283`
2. **Health check**: Uses `/health` endpoint (not `/v1/health`)
3. **Volume mounts**: Persistent data and home directories
4. **Service dependencies**: Waits for PostgreSQL to be healthy
5. **Network isolation**: Uses dedicated bridge network

### PostgreSQL Setup

The PostgreSQL service includes:

1. **pgvector extension**: For vector similarity operations
2. **UUID extension**: For unique identifier generation
3. **Proper initialization**: Via `/docker/postgres/init-vector.sql`
4. **Health checks**: Database readiness verification

## Common Issues and Solutions

### Issue 1: Invalid Environment Variables

**Problem**: Using non-existent Letta environment variables
```bash
# ❌ INCORRECT - These don't exist in Letta
LETTA_ARCHIVAL_MEMORY_ENABLED=true
LETTA_RECALL_MEMORY_ENABLED=true
LETTA_FALLBACK_ENABLED=true
LETTA_CORE_MEMORY_LIMIT=10000
LETTA_POOL_SIZE=50
```

**Solution**: Use official PostgreSQL pool configuration variables
```bash
# ✅ CORRECT - Official Letta environment variables
LETTA_PG_POOL_SIZE=20
LETTA_PG_MAX_OVERFLOW=30
LETTA_PG_POOL_TIMEOUT=30
LETTA_PG_POOL_RECYCLE=1800
```

### Issue 2: Incorrect Health Check

**Problem**: Wrong health check endpoint
```bash
# ❌ INCORRECT
test: ["CMD", "curl", "-f", "http://localhost:8283/v1/health"]
```

**Solution**: Use correct Letta health endpoint
```bash
# ✅ CORRECT
test: ["CMD", "curl", "-f", "http://localhost:8283/health"]
```

### Issue 3: Missing PostgreSQL Extensions

**Problem**: Letta requires pgvector but it's not initialized

**Solution**: The `init-vector.sql` script automatically creates:
- `vector` extension for similarity search
- `uuid-ossp` extension for UUID generation
- Proper user privileges

### Issue 4: Security Configuration

**Problem**: No password protection in production

**Solution**: Always set security variables:
```bash
SECURE=true
LETTA_SERVER_PASSWORD=your-secure-password
```

## Startup Procedure

### 1. Environment Setup

Copy and configure environment file:
```bash
cp .env.example .env
# Edit .env with your API keys and passwords
```

**IMPORTANT**: Do NOT create any `.letta` directories in the workspace. Letta data persistence is handled entirely by Docker volumes (`thoth-letta-data`, `thoth-letta-postgres`) as configured in `docker-compose.yml`.

### 2. Start Services

Start all services with dependency resolution:
```bash
docker-compose up -d
```

Services start in this order:
1. PostgreSQL (with pgvector initialization)
2. Letta (waits for database health)
3. ChromaDB
4. Thoth Application

### 3. Verify Services

Check service health:
```bash
# Check all containers
docker-compose ps

# Check Letta health specifically
curl http://localhost:8283/health

# Check PostgreSQL
docker-compose exec letta-postgres pg_isready -U letta -d letta

# Check Letta logs
docker-compose logs letta
```

### 4. Test Letta Integration

Test from Thoth application:
```python
from thoth.memory.letta_service import LettaMemoryService

service = LettaMemoryService()
await service.initialize()
print("Letta integration successful!")
```

## Production Considerations

### Security
- Use strong passwords for `LETTA_SERVER_PASSWORD`
- Consider using Docker secrets for sensitive values
- Enable `SECURE=true` in production

### Performance
- Adjust `LETTA_PG_POOL_SIZE` based on expected load
- Monitor PostgreSQL connection usage
- Consider increasing `LETTA_PG_MAX_OVERFLOW` for high concurrency

### Backup
- Regular PostgreSQL backups for agent memory data
- Backup Letta data directory (`/letta/.persist`)
- Version control for configuration changes

### Monitoring
- Monitor Letta service health endpoint
- Track PostgreSQL connection pool usage
- Log aggregation for troubleshooting

## Troubleshooting

### Container Won't Start

1. **Check environment variables**:
   ```bash
   docker-compose config
   ```

2. **Verify PostgreSQL connection**:
   ```bash
   docker-compose exec letta-postgres psql -U letta -d letta -c "SELECT version();"
   ```

3. **Check Letta logs**:
   ```bash
   docker-compose logs letta --tail=50
   ```

### Common Mistake: Workspace .letta Directory

**Problem**: User creates `workspace/.letta` directory thinking it's needed for Letta data

**Solution**:
- **Delete** any `workspace/.letta` directory if created
- Letta data is stored in Docker volumes, not workspace directories
- The correct storage locations are:
  - Container: `/letta/.persist` → Docker volume: `thoth-letta-data`
  - Container: `/letta` → Docker volume: `thoth-letta-home`
  - Database: PostgreSQL → Docker volume: `thoth-letta-postgres`

### Memory Issues

1. **Check agent memory usage**:
   ```bash
   # Connect to Letta service
   curl -X GET http://localhost:8283/agents
   ```

2. **Verify PostgreSQL extensions**:
   ```bash
   docker-compose exec letta-postgres psql -U letta -d letta -c "SELECT * FROM pg_extension;"
   ```

### Tool Execution Problems

1. **Verify tool environment**:
   ```bash
   docker-compose exec letta bash
   # Inside container: check if TOOL_EXEC_VENV_NAME is set
   echo $TOOL_EXEC_VENV_NAME
   ```

2. **Check E2B configuration** (if using sandboxed tools):
   ```bash
   # Verify E2B API key is set
   echo $E2B_API_KEY
   ```

## Best Practices

1. **Use official environment variables** as documented in Letta's self-hosting guide
2. **Enable security features** with `SECURE=true` and strong passwords
3. **Monitor service health** using provided health check endpoints
4. **Regular backups** of PostgreSQL data and Letta persistence directory
5. **Resource limits** in production to prevent memory leaks
6. **Log aggregation** for effective troubleshooting
7. **Version pinning** for Letta Docker image in production

## Integration with Thoth

Thoth's memory system (`src/thoth/memory/`) automatically detects and uses Letta when available:

```python
# Automatic fallback system
if letta_service.is_available():
    memory_service = LettaMemoryService()
else:
    memory_service = MemorySaverService()  # Fallback
```

This ensures graceful degradation if Letta is unavailable while providing advanced memory capabilities when properly configured.

## References

- [Official Letta Documentation](https://docs.letta.com)
- [Letta Self-Hosting Guide](https://docs.letta.com/self_hosting)
- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [Thoth Memory System](../src/thoth/memory/)

## Version Compatibility

- Letta: `latest` (compatible with current API)
- PostgreSQL: `15` with pgvector extension
- Docker Compose: `3.8+`

Last updated: September 2024
