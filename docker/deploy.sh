#!/bin/bash
# ==============================================================================
# Thoth AI Research Assistant - Deployment Script
# Automated deployment script for development and production environments
# ==============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "${SCRIPT_DIR}")"
COMPOSE_PROJECT_NAME="thoth"

# Default values
ENVIRONMENT="dev"
ACTION="deploy"
SERVICES=""
SCALE=""

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
usage() {
    cat << EOF
Thoth Docker Deployment Script

Usage: $0 [OPTIONS]

OPTIONS:
    -e, --env ENVIRONMENT       Environment to deploy (dev|prod) [default: dev]
    -a, --action ACTION         Action to perform (deploy|stop|restart|logs|status|clean) [default: deploy]
    -s, --services SERVICES     Specific services to target (comma-separated)
    --scale SERVICE=COUNT       Scale specific service
    -h, --help                  Show this help message

EXAMPLES:
    # Deploy development environment
    $0 --env dev

    # Deploy production environment
    $0 --env prod

    # Stop all services
    $0 --action stop

    # Restart specific services
    $0 --action restart --services thoth-api,thoth-mcp

    # Scale API service to 3 replicas
    $0 --scale thoth-api=3

    # View logs for specific service
    $0 --action logs --services thoth-api

    # Clean up all containers and volumes
    $0 --action clean

EOF
}

# Function to check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker first."
        exit 1
    fi

    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Function to prepare environment
prepare_environment() {
    print_info "Preparing ${ENVIRONMENT} environment..."

    cd "${PROJECT_ROOT}"

    # Copy environment template if not exists
    if [[ "${ENVIRONMENT}" == "dev" ]]; then
        if [[ ! -f ".env.dev" ]]; then
            if [[ -f ".env.example" ]]; then
                cp ".env.example" ".env.dev"
                print_warning "Created .env.dev from template. Please edit it with your configuration."
            else
                print_error ".env.example template not found"
                exit 1
            fi
        fi
    elif [[ "${ENVIRONMENT}" == "prod" ]]; then
        if [[ ! -f ".env.prod" ]]; then
            if [[ -f ".env.prod.example" ]]; then
                cp ".env.prod.example" ".env.prod"
                print_warning "Created .env.prod from template. Please edit it with your configuration."
            else
                print_error ".env.prod.example template not found"
                exit 1
            fi
        fi

        # Check if secrets directory exists
        if [[ ! -d "secrets" ]]; then
            print_info "Creating secrets directory..."
            mkdir -p secrets

            # Generate default secrets
            echo "$(openssl rand -base64 32)" > secrets/postgres_password.txt
            echo "$(openssl rand -base64 32)" > secrets/api_secret_key.txt
            echo "$(openssl rand -base64 32)" > secrets/chroma_auth_token.txt
            echo "$(openssl rand -base64 32)" > secrets/grafana_admin_password.txt

            # Create placeholder API key files
            echo "your-openai-api-key" > secrets/openai_api_key.txt
            echo "your-anthropic-api-key" > secrets/anthropic_api_key.txt
            echo "your-semantic-scholar-key" > secrets/semantic_scholar_api_key.txt
            echo "your-web-search-key" > secrets/web_search_api_key.txt

            # Set secure permissions
            chmod 600 secrets/*

            print_warning "Created secrets directory with placeholder values. Please update with real API keys."
        fi

        # Check if SSL certificates exist for production
        if [[ ! -f "docker/nginx/ssl/cert.pem" ]] || [[ ! -f "docker/nginx/ssl/key.pem" ]]; then
            print_info "Creating self-signed SSL certificates..."
            mkdir -p docker/nginx/ssl
            openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
                -keyout docker/nginx/ssl/key.pem \
                -out docker/nginx/ssl/cert.pem \
                -subj "/C=US/ST=State/L=City/O=Organization/CN=localhost" \
                &> /dev/null
            print_warning "Created self-signed SSL certificates. Replace with real certificates for production."
        fi

        # Create production directories
        if [[ ! -d "/opt/thoth" ]]; then
            print_info "Creating production directories..."
            sudo mkdir -p /opt/thoth/{workspace,chroma,postgres,redis,letta,logs,prometheus,grafana}
            sudo chown -R $USER:$USER /opt/thoth
        fi
    fi
}

# Function to get compose file
get_compose_file() {
    if [[ "${ENVIRONMENT}" == "dev" ]]; then
        echo "docker-compose.dev.yml"
    else
        echo "docker-compose.prod.yml"
    fi
}

# Function to deploy services
deploy_services() {
    local compose_file
    compose_file=$(get_compose_file)

    print_info "Deploying services using ${compose_file}..."

    # Build and start services
    if [[ -n "${SERVICES}" ]]; then
        docker-compose -f "${compose_file}" up -d --build ${SERVICES//,/ }
    else
        docker-compose -f "${compose_file}" up -d --build
    fi

    # Wait for services to be healthy
    print_info "Waiting for services to be healthy..."
    sleep 10

    # Check service status
    docker-compose -f "${compose_file}" ps

    print_success "Services deployed successfully"
}

# Function to stop services
stop_services() {
    local compose_file
    compose_file=$(get_compose_file)

    print_info "Stopping services..."

    if [[ -n "${SERVICES}" ]]; then
        docker-compose -f "${compose_file}" stop ${SERVICES//,/ }
    else
        docker-compose -f "${compose_file}" down
    fi

    print_success "Services stopped"
}

# Function to restart services
restart_services() {
    local compose_file
    compose_file=$(get_compose_file)

    print_info "Restarting services..."

    if [[ -n "${SERVICES}" ]]; then
        docker-compose -f "${compose_file}" restart ${SERVICES//,/ }
    else
        docker-compose -f "${compose_file}" restart
    fi

    print_success "Services restarted"
}

# Function to show logs
show_logs() {
    local compose_file
    compose_file=$(get_compose_file)

    print_info "Showing logs..."

    if [[ -n "${SERVICES}" ]]; then
        docker-compose -f "${compose_file}" logs -f ${SERVICES//,/ }
    else
        docker-compose -f "${compose_file}" logs -f
    fi
}

# Function to show status
show_status() {
    local compose_file
    compose_file=$(get_compose_file)

    print_info "Service Status:"
    docker-compose -f "${compose_file}" ps

    print_info "Resource Usage:"
    docker stats --no-stream

    print_info "Network Information:"
    docker network ls | grep thoth
}

# Function to scale services
scale_services() {
    local compose_file
    compose_file=$(get_compose_file)

    print_info "Scaling services..."

    # Parse scale parameter
    IFS='=' read -r service_name replica_count <<< "${SCALE}"

    docker-compose -f "${compose_file}" up -d --scale "${service_name}=${replica_count}"

    print_success "Service ${service_name} scaled to ${replica_count} replicas"
}

# Function to clean up
clean_up() {
    local compose_file
    compose_file=$(get_compose_file)

    print_warning "This will remove all containers, networks, and volumes. Are you sure? (y/N)"
    read -r response

    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_info "Cleaning up..."

        # Stop and remove containers
        docker-compose -f "${compose_file}" down -v --remove-orphans

        # Remove dangling images
        docker image prune -f

        # Remove unused networks
        docker network prune -f

        print_success "Cleanup completed"
    else
        print_info "Cleanup cancelled"
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -s|--services)
            SERVICES="$2"
            shift 2
            ;;
        --scale)
            SCALE="$2"
            ACTION="scale"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Validate environment
if [[ ! "${ENVIRONMENT}" =~ ^(dev|prod)$ ]]; then
    print_error "Invalid environment: ${ENVIRONMENT}. Must be 'dev' or 'prod'"
    exit 1
fi

# Validate action
if [[ ! "${ACTION}" =~ ^(deploy|stop|restart|logs|status|scale|clean)$ ]]; then
    print_error "Invalid action: ${ACTION}"
    usage
    exit 1
fi

# Main execution
print_info "Starting Thoth deployment script..."
print_info "Environment: ${ENVIRONMENT}"
print_info "Action: ${ACTION}"

check_prerequisites
prepare_environment

case "${ACTION}" in
    deploy)
        deploy_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    status)
        show_status
        ;;
    scale)
        scale_services
        ;;
    clean)
        clean_up
        ;;
esac

print_success "Script completed successfully!"
