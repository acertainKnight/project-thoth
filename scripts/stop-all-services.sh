#!/bin/bash
# ==============================================================================
# Thoth Multi-Service Stop Script
# Gracefully stop all Thoth services
# ==============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SERVICES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOYMENT_DIR="$SERVICES_ROOT/deployment"
MEMORY_SERVICE_DIR="$DEPLOYMENT_DIR/letta-memory-service"
MONITORING_DIR="$SERVICES_ROOT/docker/monitoring"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🛑 Stopping All Thoth Services${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Function to stop a service
stop_service() {
    local service_name=$1
    local service_dir=$2
    local compose_file=$3

    echo -e "${YELLOW}Stopping ${service_name}...${NC}"

    if [ ! -d "$service_dir" ]; then
        echo -e "${RED}✗ Service directory not found: $service_dir${NC}"
        return 1
    fi

    cd "$service_dir"

    if [ -f "Makefile" ]; then
        make stop 2>/dev/null || true
    elif [ -f "$compose_file" ]; then
        docker-compose -f "$compose_file" down 2>/dev/null || true
    else
        echo -e "${YELLOW}○ No deployment configuration found for ${service_name}${NC}"
    fi

    echo -e "${GREEN}✓ ${service_name} stopped${NC}"
}

# Stop services in reverse order (dependencies first)

# 1. Stop Main Application
echo -e "${PURPLE}1. Stopping Main Thoth Application...${NC}"
cd "$SERVICES_ROOT"
docker-compose down 2>/dev/null || true
docker-compose -f docker-compose.dev.yml down 2>/dev/null || true
docker-compose -f docker-compose.prod.yml down 2>/dev/null || true
echo -e "${GREEN}✓ Main application stopped${NC}"
echo ""

# 2. Stop Monitoring Stack
echo -e "${PURPLE}2. Stopping Monitoring Stack...${NC}"
stop_service "Monitoring Stack" "$MONITORING_DIR" "docker-compose.monitoring.yml"
echo ""

# 3. Stop Memory Service
echo -e "${PURPLE}3. Stopping Memory Service...${NC}"
stop_service "Memory Service (Letta)" "$MEMORY_SERVICE_DIR" "docker-compose.yml"
echo ""

# 4. Clean up any remaining containers
echo -e "${YELLOW}Cleaning up remaining Thoth containers...${NC}"
docker ps -a --filter "name=thoth" --format "table {{.Names}}\t{{.Status}}" | grep -v "NAMES" | while read line; do
    container_name=$(echo $line | awk '{print $1}')
    if [ -n "$container_name" ]; then
        echo -e "${CYAN}Stopping orphaned container: $container_name${NC}"
        docker stop "$container_name" 2>/dev/null || true
        docker rm "$container_name" 2>/dev/null || true
    fi
done

# 5. Clean up any remaining networks
echo -e "${YELLOW}Cleaning up networks...${NC}"
docker network ls --filter "name=thoth" --format "{{.Name}}" | while read network_name; do
    if [ -n "$network_name" ] && [ "$network_name" != "NETWORK" ]; then
        echo -e "${CYAN}Removing network: $network_name${NC}"
        docker network rm "$network_name" 2>/dev/null || true
    fi
done

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}🎉 All Thoth Services Stopped${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Show final status
echo -e "${YELLOW}Final Status Check:${NC}"
echo "===================="

# Check if any Thoth containers are still running
running_containers=$(docker ps --filter "name=thoth" --filter "name=letta" --format "{{.Names}}" | wc -l)
if [ "$running_containers" -eq 0 ]; then
    echo -e "${GREEN}✓ All services stopped successfully${NC}"
else
    echo -e "${YELLOW}⚠ Some containers may still be running:${NC}"
    docker ps --filter "name=thoth" --filter "name=letta" --format "table {{.Names}}\t{{.Status}}"
fi

echo ""
echo -e "${YELLOW}To restart services:${NC}"
echo "  ./scripts/start-all-services.sh dev     # Development"
echo "  ./scripts/start-all-services.sh prod    # Production"
echo "  ./scripts/start-all-services.sh all     # Full stack"
