# Thoth Cloud Deployment Guide

## Overview

Thoth is designed for cloud deployment with the production Docker Compose configuration (`docker-compose.prod.yml`) that includes:

- **Docker Swarm/Kubernetes ready**: Resource limits, replicas, health checks
- **Secrets management**: Secure API key handling
- **Service scaling**: Multiple replicas for high availability
- **Monitoring stack**: Prometheus + Grafana
- **Load balancing**: Nginx with SSL termination

## Cloud Platform Options

### 1. Docker Swarm (Easiest)
```bash
# Initialize swarm on cloud VM
docker swarm init

# Create secrets
echo "your-openai-key" | docker secret create openai_api_key -
echo "your-anthropic-key" | docker secret create anthropic_api_key -
echo "secure-postgres-password" | docker secret create postgres_password -
# ... create all secrets

# Deploy stack
docker stack deploy -c docker-compose.prod.yml thoth
```

### 2. Kubernetes
Convert Docker Compose to Kubernetes manifests:
```bash
# Install Kompose
curl -L https://github.com/kubernetes/kompose/releases/latest/download/kompose-linux-amd64 -o kompose
chmod +x kompose && sudo mv kompose /usr/local/bin/

# Convert
kompose convert -f docker-compose.prod.yml
kubectl apply -f .
```

### 3. Cloud Container Services

#### AWS ECS
- Use AWS ECS with Application Load Balancer
- Store secrets in AWS Secrets Manager
- Use EFS for persistent volumes

#### Google Cloud Run
- Deploy as Cloud Run services
- Use Cloud SQL for PostgreSQL
- Store secrets in Secret Manager

#### Azure Container Instances
- Use Azure Container Apps
- Azure Database for PostgreSQL
- Key Vault for secrets

## Pre-Cloud Setup Modifications

### 1. Remove Local Bind Mounts
The current setup uses local directories (`./workspace`, `./data`) which won't work in cloud. Convert to named volumes:

```yaml
volumes:
  - thoth-workspace:/workspace        # Instead of ./workspace
  - thoth-data:/workspace/data        # Instead of ./data
  - thoth-logs:/workspace/logs        # Instead of ./logs
  - thoth-cache:/workspace/cache      # Instead of ./cache
```

### 2. External Database Options
For production scale, consider managed databases:

```yaml
# Replace local PostgreSQL with cloud database
environment:
  - DATABASE_URL=postgresql://user:pass@your-cloud-db:5432/letta

# Replace ChromaDB with managed vector database
environment:
  - THOTH_CHROMADB_URL=https://your-managed-chroma.com
```

### 3. Secret Management Setup

#### Create secrets directory:
```bash
mkdir -p secrets/
echo "your-openai-key" > secrets/openai_api_key.txt
echo "your-anthropic-key" > secrets/anthropic_api_key.txt
echo "secure-postgres-password" > secrets/postgres_password.txt
echo "chroma-auth-token" > secrets/chroma_auth_token.txt
echo "api-secret-key" > secrets/api_secret_key.txt
echo "your-semantic-scholar-key" > secrets/semantic_scholar_api_key.txt
echo "your-web-search-key" > secrets/web_search_api_key.txt
echo "grafana-admin-password" > secrets/grafana_admin_password.txt
```

## Cloud Deployment Steps

### Step 1: Prepare Environment
```bash
# Clone repository on cloud VM
git clone <your-repo>
cd project-thoth

# Create production environment
cp .env.prod.example .env.prod
# Edit with cloud-specific settings

# Setup secrets (see above)
```

### Step 2: Modify for Cloud
```bash
# Update bind mounts to volumes (if needed)
# Configure external databases (if used)
# Set up cloud-specific networking
```

### Step 3: Deploy
```bash
# Build and deploy
make docker-build-prod
make docker-prod

# Or manually:
docker compose -f docker-compose.prod.yml up -d
```

### Step 4: Configure Load Balancer
- Point domain to load balancer
- Configure SSL certificates
- Set up health check endpoints

### Step 5: Monitor
```bash
# Access monitoring
http://your-domain/grafana  # Grafana dashboards
http://your-domain:9090     # Prometheus metrics
```

## Scaling Configuration

The production setup includes automatic scaling:

```yaml
deploy:
  replicas: 3                    # API servers
  replicas: 2                    # Agent workers
  replicas: 2                    # Discovery services
  replicas: 1                    # Memory service (stateful)
```

## Resource Requirements

### Minimum Cloud Resources
- **CPU**: 4 vCPUs total
- **Memory**: 8GB RAM total
- **Storage**: 50GB SSD
- **Network**: 1Gbps

### Recommended Production
- **CPU**: 8-16 vCPUs
- **Memory**: 16-32GB RAM
- **Storage**: 100GB+ SSD
- **Network**: Load balancer + CDN

## Monitoring & Observability

Built-in monitoring stack:
- **Prometheus**: Metrics collection (port 9090)
- **Grafana**: Dashboards (port 3000)
- **Health checks**: All services have health endpoints
- **Structured logging**: JSON logs for aggregation

## Data Persistence

### Cloud Volume Strategy
```yaml
volumes:
  thoth-workspace:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /mnt/efs/workspace    # AWS EFS mount

  thoth-chroma-data:
    external: true                   # Use cloud block storage
    name: thoth-chroma-production
```

### Backup Strategy
```bash
# Automated backups
make backup-memory      # Letta memory data
make backup-vector      # ChromaDB vectors
make backup-all         # Complete backup
```

## Security Considerations

### 1. Network Security
- Use private networks for backend services
- Only expose API gateway/load balancer publicly
- Configure VPC/security groups properly

### 2. Secret Management
- Never commit secrets to git
- Use cloud-native secret services (AWS Secrets Manager, etc.)
- Rotate secrets regularly

### 3. Container Security
- Use non-root users (already configured)
- Scan images for vulnerabilities
- Keep base images updated

## Quick Cloud Setup Commands

### AWS EC2 Example
```bash
# Launch EC2 instance (t3.large or larger)
# SSH into instance

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Clone and deploy
git clone <your-repo>
cd project-thoth
make docker-init
# Edit secrets and environment
make docker-prod
```

### Google Cloud Platform
```bash
# Create Compute Engine instance
gcloud compute instances create thoth-prod --machine-type=e2-standard-4

# SSH and setup (same as above)
# Or use Cloud Run for serverless deployment
```

## Troubleshooting

### Common Cloud Issues
1. **Port conflicts**: Cloud providers often block non-standard ports
2. **Volume permissions**: Ensure proper filesystem permissions
3. **Secret access**: Verify secret mounting works correctly
4. **Network connectivity**: Check security groups/firewall rules
5. **Resource limits**: Monitor CPU/memory usage

### Health Checks
```bash
# Check all services
make docker-status

# Individual health checks
curl http://your-domain:8000/health      # API health
curl http://your-domain:8003/api/v1/heartbeat  # ChromaDB
curl http://your-domain:8283/health      # Letta memory
```

This cloud setup provides:
- ✅ **Scalability**: Horizontal scaling for all services
- ✅ **High Availability**: Multiple replicas + health checks
- ✅ **Security**: Secrets management + network isolation
- ✅ **Monitoring**: Built-in observability stack
- ✅ **Persistence**: Proper volume management for data
