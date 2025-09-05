#!/bin/bash
# ==============================================================================
# Thoth Multi-Service Orchestration Script
# Start all Thoth services in separate, scalable containers
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-dev}  # dev, prod, or all
SERVICES_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOYMENT_DIR="$SERVICES_ROOT/deployment"

# Service directories
MEMORY_SERVICE_DIR="$DEPLOYMENT_DIR/letta-memory-service"
MONITORING_DIR="$SERVICES_ROOT/docker/monitoring"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}🚀 Thoth Multi-Service Orchestration${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${YELLOW}Environment: ${ENVIRONMENT}${NC}"
echo -e "${YELLOW}Services Root: ${SERVICES_ROOT}${NC}"
echo ""

# Function to check if service is healthy
check_service_health() {
    local service_name=$1
    local health_url=$2
    local max_attempts=${3:-15}

    echo -e "${YELLOW}Waiting for ${service_name} to be healthy...${NC}"

    for i in $(seq 1 $max_attempts); do
        if curl -s -f "$health_url" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ ${service_name} is healthy${NC}"
            return 0
        fi
        echo -n "."
        sleep 3
    done

    echo -e "${YELLOW}⚠ ${service_name} health check timeout, but service may still be starting${NC}"
    # Don't fail completely - service might still be usable
    return 0
}

# Function to start a service
start_service() {
    local service_name=$1
    local service_dir=$2
    local compose_file=$3
    local health_url=$4

    echo -e "${PURPLE}Starting ${service_name}...${NC}"

    if [ ! -d "$service_dir" ]; then
        echo -e "${RED}✗ Service directory not found: $service_dir${NC}"
        return 1
    fi

    cd "$service_dir"

    if [ -f "Makefile" ]; then
        echo -e "${CYAN}Using Makefile for ${service_name}${NC}"
        if [ "$ENVIRONMENT" = "prod" ]; then
            make start-prod 2>/dev/null || make start
        else
            make start
        fi
    elif [ -f "$compose_file" ]; then
        echo -e "${CYAN}Using docker-compose for ${service_name}${NC}"
        if [ "$ENVIRONMENT" = "prod" ]; then
            docker-compose -f "$compose_file" up -d --remove-orphans
        else
            docker-compose -f "$compose_file" up -d --remove-orphans
        fi
    else
        echo -e "${RED}✗ No deployment configuration found for ${service_name}${NC}"
        return 1
    fi

    # Check health if URL provided
    if [ -n "$health_url" ]; then
        check_service_health "$service_name" "$health_url"
    fi

    echo -e "${GREEN}✓ ${service_name} started successfully${NC}"
    echo ""
}

# Function to show service status
show_service_status() {
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${BLUE}📊 Service Status Summary${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    # Memory Service
    echo -e "${PURPLE}Memory Service (Letta):${NC}"
    if curl -s -f "http://localhost:8283/v1/health/" > /dev/null 2>&1; then
        echo -e "  Status: ${GREEN}✓ Healthy${NC}"
        echo -e "  URL: ${CYAN}http://localhost:8283${NC}"
        echo -e "  API Docs: ${CYAN}http://localhost:8283/docs${NC}"
    else
        echo -e "  Status: ${RED}✗ Unhealthy${NC}"
    fi
    echo ""

    # Main Thoth Application
    echo -e "${PURPLE}Main Application:${NC}"
    if curl -s -f "http://localhost:8000/health" > /dev/null 2>&1; then
        echo -e "  API Server: ${GREEN}✓ Healthy${NC}"
        echo -e "  URL: ${CYAN}http://localhost:8000${NC}"
    else
        echo -e "  API Server: ${RED}✗ Unhealthy${NC}"
    fi

    if curl -s -f "http://localhost:8001/health" > /dev/null 2>&1; then
        echo -e "  MCP Server: ${GREEN}✓ Healthy${NC}"
        echo -e "  URL: ${CYAN}http://localhost:8001${NC}"
    else
        echo -e "  MCP Server: ${RED}✗ Unhealthy${NC}"
    fi
    echo ""

    # Vector Database
    echo -e "${PURPLE}Vector Database (ChromaDB):${NC}"
    if curl -s -f "http://localhost:8003/api/v1/heartbeat" > /dev/null 2>&1; then
        echo -e "  Status: ${GREEN}✓ Healthy${NC}"
        echo -e "  URL: ${CYAN}http://localhost:8003${NC}"
    else
        echo -e "  Status: ${RED}✗ Unhealthy${NC}"
    fi
    echo ""

    # Monitoring (if enabled)
    if curl -s -f "http://localhost:9090/-/healthy" > /dev/null 2>&1; then
        echo -e "${PURPLE}Monitoring:${NC}"
        echo -e "  Prometheus: ${GREEN}✓ Healthy${NC} - ${CYAN}http://localhost:9090${NC}"

        if curl -s -f "http://localhost:3000/api/health" > /dev/null 2>&1; then
            echo -e "  Grafana: ${GREEN}✓ Healthy${NC} - ${CYAN}http://localhost:3000${NC} (admin/admin)"
        fi
        echo ""
    fi

    # Discovery Service Status
    echo -e "${PURPLE}Discovery Service:${NC}"
    echo -e "  Status: ${CYAN}Integrated with main app${NC}"
    echo -e "  Access: ${CYAN}python -m thoth discovery${NC}"
    echo ""

    # Chat Agent Status
    echo -e "${PURPLE}Chat Agent:${NC}"
    echo -e "  Status: ${CYAN}Available via MCP tools${NC}"
    echo -e "  Access: ${CYAN}python -m thoth agent${NC}"
    echo ""
}

# Main orchestration logic
main() {
    case $ENVIRONMENT in
        "dev"|"development")
            echo -e "${YELLOW}Starting Development Environment${NC}"
            echo "================================="

            # 1. Start Memory Service
            start_service "Memory Service (Letta)" "$MEMORY_SERVICE_DIR" "docker-compose.yml" "http://localhost:8283/v1/health/"

            # 2. Start Main Application (Development)
            start_service "Main Application (Dev)" "$SERVICES_ROOT" "docker-compose.dev.yml" "http://localhost:8000/health"

            # 3. Optional: Start Monitoring
            read -p "Start monitoring stack? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                start_service "Monitoring Stack" "$MONITORING_DIR" "docker-compose.monitoring.yml" "http://localhost:9090/-/healthy"
            fi
            ;;

        "prod"|"production")
            echo -e "${YELLOW}Starting Production Environment${NC}"
            echo "================================="

            # 1. Start Memory Service with full stack
            cd "$MEMORY_SERVICE_DIR"
            make start-prod

            # 2. Start Main Application (Production)
            start_service "Main Application (Prod)" "$SERVICES_ROOT" "docker-compose.prod.yml" "http://localhost:8000/health"

            # 3. Start Monitoring Stack
            start_service "Monitoring Stack" "$MONITORING_DIR" "docker-compose.monitoring.yml" "http://localhost:9090/-/healthy"
            ;;

        "all"|"full")
            echo -e "${YELLOW}Starting Full Environment (All Services)${NC}"
            echo "======================================="

            # 1. Memory Service
            start_service "Memory Service" "$MEMORY_SERVICE_DIR" "docker-compose.yml" "http://localhost:8283/health"

            # 2. Main Application
            start_service "Main Application" "$SERVICES_ROOT" "docker-compose.yml" "http://localhost:8000/health"

            # 3. Monitoring
            start_service "Monitoring Stack" "$MONITORING_DIR" "docker-compose.monitoring.yml" "http://localhost:9090/-/healthy"

            echo -e "${GREEN}All services started!${NC}"
            ;;

        "memory"|"letta")
            echo -e "${YELLOW}Starting Memory Service Only${NC}"
            start_service "Memory Service (Letta)" "$MEMORY_SERVICE_DIR" "docker-compose.yml" "http://localhost:8283/v1/health/"
            ;;

        "monitoring")
            echo -e "${YELLOW}Starting Monitoring Stack Only${NC}"
            start_service "Monitoring Stack" "$MONITORING_DIR" "docker-compose.monitoring.yml" "http://localhost:9090/-/healthy"
            ;;

        "main"|"thoth")
            echo -e "${YELLOW}Starting Main Thoth Application Only${NC}"
            start_service "Main Application" "$SERVICES_ROOT" "docker-compose.yml" "http://localhost:8000/health"
            ;;

        "status")
            show_service_status
            exit 0
            ;;

        *)
            echo -e "${RED}Invalid environment: $ENVIRONMENT${NC}"
            echo ""
            echo -e "${YELLOW}Usage: $0 [environment]${NC}"
            echo ""
            echo -e "${YELLOW}Environments:${NC}"
            echo "  dev          - Development environment"
            echo "  prod         - Production environment"
            echo "  all          - All services"
            echo "  memory       - Memory service only"
            echo "  monitoring   - Monitoring stack only"
            echo "  main         - Main Thoth app only"
            echo "  status       - Show service status"
            echo ""
            echo -e "${YELLOW}Examples:${NC}"
            echo "  $0 dev       # Start development environment"
            echo "  $0 prod      # Start production environment"
            echo "  $0 memory    # Start only memory service"
            echo "  $0 status    # Check all service status"
            exit 1
            ;;
    esac

    # Show final status
    echo -e "${BLUE}======================================================================${NC}"
    echo -e "${GREEN}🎉 Environment '$ENVIRONMENT' started successfully!${NC}"
    echo -e "${BLUE}======================================================================${NC}"
    echo ""

    show_service_status

    echo -e "${YELLOW}Management Commands:${NC}"
    echo "  $0 status                    # Check service status"
    echo "  ./scripts/stop-all-services.sh  # Stop all services"
    echo "  make docker-logs             # View main app logs"
    echo "  cd $MEMORY_SERVICE_DIR && make logs  # View memory service logs"
    echo ""

    echo -e "${YELLOW}Service URLs:${NC}"
    echo "  Main API: http://localhost:8000"
    echo "  MCP Server: http://localhost:8001"
    echo "  Memory Service: http://localhost:8283"
    echo "  Vector DB: http://localhost:8003"
    echo "  Prometheus: http://localhost:9090"
    echo "  Grafana: http://localhost:3000 (admin/admin)"
}

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"

    # Check Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ Docker not found. Please install Docker.${NC}"
        exit 1
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}✗ docker-compose not found. Please install docker-compose.${NC}"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        echo -e "${RED}✗ Docker daemon not running. Please start Docker.${NC}"
        exit 1
    fi

    echo -e "${GREEN}✓ Prerequisites check passed${NC}"
    echo ""
}

# Main execution
if [ "$1" = "status" ]; then
    show_service_status
else
    check_prerequisites
    main
fi
