# Docker Setup Guide

Run Thoth in a Docker container and connect from Obsidian.

## 🚀 **Quick Start**

### **Step 1: Create Docker Environment**
```bash
# Clone the repository
git clone https://github.com/yourusername/project-thoth.git
cd project-thoth

# Create .env file with your API keys
cp .env.example .env
nano .env  # Add your API keys
```

### **Step 2: Build and Run with Docker Compose**
```bash
# Build and start services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f thoth
```

### **Step 3: Configure Obsidian Plugin**
1. **Enable Remote Mode** in plugin settings
2. **Set Remote URL**: `http://localhost:8000`
3. **Connect**: Click status bar in Obsidian

## 🔧 **Docker Compose Setup (Recommended)**

The repository includes a complete `docker-compose.yml` for easy deployment:

### **Start the Complete Stack**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### **Services Included**
- **Thoth API**: Main research assistant API
- **Volume Mounts**: Persistent data storage
- **Health Checks**: Automatic service monitoring
- **Environment**: Configurable via `.env` file

## 📁 **Volume Configuration**

### **Important Directories**
The Docker setup automatically mounts these directories:

- **Configuration**: `.env` file with API keys
- **Data**: `./data` for PDFs and processed files
- **Knowledge**: `./knowledge` for the knowledge base
- **Logs**: `./logs` for application logs
- **Obsidian**: `./obsidian-vault` for Obsidian integration

### **Custom Volume Mapping**
Edit `docker-compose.yml` to customize paths:

```yaml
volumes:
  # Map your actual Obsidian vault
  - "/path/to/your/obsidian/vault:/app/obsidian-vault"
  # Map your papers directory
  - "/path/to/your/papers:/app/data/pdfs"
  # Keep knowledge base persistent
  - "./knowledge:/app/knowledge"
```

### **Windows Paths Example**
```yaml
volumes:
  - "C:/Users/Username/Documents/Obsidian Vault:/app/obsidian-vault"
  - "C:/Users/Username/Documents/Papers:/app/data/pdfs"
  - "./knowledge:/app/knowledge"
```

## 🔄 **Development Workflow**

### **Development Mode with Hot Reload**
```bash
# Use development compose file
docker-compose -f docker-compose.dev.yml up -d

# Or run interactive development
docker-compose run --rm thoth-dev bash
```

### **Update Container**
```bash
# Rebuild after code changes
docker-compose build thoth

# Restart services
docker-compose restart thoth
```

### **View Live Logs**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f thoth
```

## 🐛 **Troubleshooting**

### **Container Won't Start**
```bash
# Check logs
docker-compose logs thoth

# Check if port is available
netstat -an | grep 8000

# Try different port
# Edit docker-compose.yml to use 8001:8000
```

### **API Keys Not Found**
```bash
# Verify .env file is present
cat .env

# Check if mounted correctly
docker-compose exec thoth cat /app/.env

# Restart after .env changes
docker-compose restart thoth
```

### **Permission Issues**
```bash
# Fix file permissions (Linux/macOS)
sudo chown -R $(id -u):$(id -g) data/ knowledge/ logs/

# Run as current user
docker-compose run --user $(id -u):$(id -g) thoth
```

### **Volume Mounting Issues**
```bash
# Check volume mounts
docker-compose exec thoth ls -la /app/

# Verify directories exist
mkdir -p data knowledge logs obsidian-vault

# Check Docker daemon (Windows)
# Ensure drive sharing is enabled in Docker Desktop
```

## 🌐 **Network Configuration**

### **Custom Networks**
The compose file creates an isolated network:

```yaml
networks:
  thoth-net:
    driver: bridge
```

### **Port Configuration**
```yaml
ports:
  - "8000:8000"  # API port
  # Add more ports as needed
  - "8001:8001"  # Additional instance
```

### **Multiple Instances**
Run development and production instances:

```bash
# Development on port 8000
docker-compose up -d

# Production on port 8001
docker-compose -f docker-compose.prod.yml up -d
```

## 📊 **Monitoring**

### **Health Checks**
Built-in health monitoring:

```bash
# Check service health
docker-compose ps

# Manual health check
curl http://localhost:8000/health

# Detailed status
docker-compose exec thoth curl http://localhost:8000/agent/status
```

### **Resource Usage**
```bash
# Monitor resources
docker stats

# Check specific container
docker stats project-thoth_thoth_1
```

### **Log Management**
```bash
# Rotate logs
docker-compose logs --since 1h thoth

# Clear old logs
docker system prune -f
```

## 🚀 **Production Deployment**

### **Production Configuration**
Use `docker-compose.prod.yml` for production:

```yaml
version: '3.8'
services:
  thoth:
    build: .
    restart: unless-stopped
    environment:
      - LOG_LEVEL=INFO
    ports:
      - "8000:8000"
    volumes:
      - ./.env:/app/.env:ro
      - ./data:/app/data
      - ./knowledge:/app/knowledge
      - ./logs:/app/logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### **With Reverse Proxy (Nginx)**
```nginx
# /etc/nginx/sites-available/thoth
server {
    listen 80;
    server_name thoth.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### **SSL with Let's Encrypt**
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot --nginx -d thoth.yourdomain.com
```

## 🔒 **Security Considerations**

### **Environment Variables**
- Never commit `.env` file to git
- Use secrets management in production
- Rotate API keys regularly

### **Network Security**
```yaml
# Restrict to local network only
ports:
  - "127.0.0.1:8000:8000"
```

### **Container Security**
```yaml
# Run as non-root user
user: "1000:1000"

# Read-only root filesystem
read_only: true
tmpfs:
  - /tmp
  - /var/tmp
```

## 📦 **Container Registry**

### **Build and Push**
```bash
# Build image
docker build -t thoth-api:latest .

# Tag for registry
docker tag thoth-api:latest yourusername/thoth-api:latest

# Push to registry
docker push yourusername/thoth-api:latest
```

### **Deploy from Registry**
```yaml
# In docker-compose.yml
services:
  thoth:
    image: yourusername/thoth-api:latest
    # No build section needed
```

## 🎯 **Integration Examples**

### **CI/CD Pipeline**
```yaml
# .github/workflows/docker.yml
name: Docker Build and Deploy

on:
  push:
    branches: [ main ]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Build and push Docker images
      run: |
        docker build -t thoth-api:${{ github.sha }} .
        docker push thoth-api:${{ github.sha }}
```

### **Backup Strategy**
```bash
# Backup volumes
docker run --rm -v project-thoth_knowledge:/data -v $(pwd):/backup alpine tar czf /backup/knowledge-backup.tar.gz /data

# Restore volumes
docker run --rm -v project-thoth_knowledge:/data -v $(pwd):/backup alpine tar xzf /backup/knowledge-backup.tar.gz -C /
```

---

**🎉 You now have Thoth running in Docker!**

This setup provides isolation, easy deployment, and consistent environments across different systems. The Docker configuration is production-ready and includes all necessary components for a complete Thoth deployment.
