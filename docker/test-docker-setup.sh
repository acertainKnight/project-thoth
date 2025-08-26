#!/bin/bash
# ==============================================================================
# Thoth Docker Setup Test Script
# Validates Docker configuration and deployment
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
TEST_TIMEOUT=300  # 5 minutes
CHECK_INTERVAL=5  # 5 seconds

echo -e "${BLUE}==============================================================================${NC}"
echo -e "${BLUE} Thoth Docker Setup Test Script${NC}"
echo -e "${BLUE}==============================================================================${NC}"
echo ""

# Function to print status messages
print_status() {
    local status=$1
    local message=$2
    case $status in
        "INFO")
            echo -e "${BLUE}[INFO]${NC} $message"
            ;;
        "SUCCESS")
            echo -e "${GREEN}[SUCCESS]${NC} $message"
            ;;
        "WARNING")
            echo -e "${YELLOW}[WARNING]${NC} $message"
            ;;
        "ERROR")
            echo -e "${RED}[ERROR]${NC} $message"
            ;;
    esac
}

# Function to wait for service to be ready
wait_for_service() {
    local service_name=$1
    local url=$2
    local timeout=${3:-60}
    local waited=0

    print_status "INFO" "Waiting for $service_name to be ready at $url..."

    while [ $waited -lt $timeout ]; do
        if curl -f -s "$url" > /dev/null 2>&1; then
            print_status "SUCCESS" "$service_name is ready!"
            return 0
        fi

        sleep $CHECK_INTERVAL
        waited=$((waited + CHECK_INTERVAL))
        echo -n "."
    done

    echo ""
    print_status "ERROR" "Timeout waiting for $service_name after ${timeout}s"
    return 1
}

# Test 1: Check prerequisites
test_prerequisites() {
    print_status "INFO" "Testing prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_status "ERROR" "Docker is not installed"
        return 1
    fi

    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        print_status "ERROR" "Docker Compose is not available"
        return 1
    fi

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_status "ERROR" "Docker daemon is not running"
        return 1
    fi

    print_status "SUCCESS" "All prerequisites satisfied"
    return 0
}

# Test 2: Validate Docker files
test_docker_files() {
    print_status "INFO" "Validating Docker configuration files..."

    local files=(
        "Dockerfile"
        "Dockerfile.dev"
        "docker-compose.yml"
        "docker-compose.dev.yml"
        "docker-compose.prod.yml"
        ".dockerignore"
    )

    for file in "${files[@]}"; do
        if [[ ! -f "$PROJECT_DIR/$file" ]]; then
            print_status "ERROR" "Missing required file: $file"
            return 1
        fi
    done

    # Validate docker-compose files
    if ! docker compose -f "$PROJECT_DIR/docker-compose.yml" config -q; then
        print_status "ERROR" "Invalid docker-compose.yml"
        return 1
    fi

    if ! docker compose -f "$PROJECT_DIR/docker-compose.dev.yml" config -q; then
        print_status "ERROR" "Invalid docker-compose.dev.yml"
        return 1
    fi

    if ! docker compose -f "$PROJECT_DIR/docker-compose.prod.yml" config -q; then
        print_status "ERROR" "Invalid docker-compose.prod.yml"
        return 1
    fi

    print_status "SUCCESS" "All Docker files are valid"
    return 0
}

# Test 3: Build Docker images
test_docker_build() {
    print_status "INFO" "Testing Docker image builds..."

    cd "$PROJECT_DIR"

    # Build development image
    print_status "INFO" "Building development image..."
    if ! docker build -f Dockerfile.dev -t thoth-app:dev-test . > /tmp/docker-build-dev.log 2>&1; then
        print_status "ERROR" "Failed to build development image"
        echo "Build log:"
        cat /tmp/docker-build-dev.log
        return 1
    fi

    # Build production image
    print_status "INFO" "Building production image..."
    if ! docker build -f Dockerfile --target runtime -t thoth-app:prod-test . > /tmp/docker-build-prod.log 2>&1; then
        print_status "ERROR" "Failed to build production image"
        echo "Build log:"
        cat /tmp/docker-build-prod.log
        return 1
    fi

    print_status "SUCCESS" "Docker images built successfully"
    return 0
}

# Test 4: Test development environment
test_development_environment() {
    print_status "INFO" "Testing development environment..."

    cd "$PROJECT_DIR"

    # Create test environment file
    if [[ ! -f ".env.docker" ]]; then
        cp .env.docker.example .env.docker
        print_status "INFO" "Created .env.docker from example"
    fi

    # Start development services
    print_status "INFO" "Starting development services..."
    docker compose -f docker-compose.dev.yml up -d > /tmp/docker-dev-up.log 2>&1

    # Wait for services
    if ! wait_for_service "ChromaDB" "http://localhost:8003/api/v1/heartbeat" 60; then
        print_status "ERROR" "ChromaDB failed to start"
        docker compose -f docker-compose.dev.yml logs chromadb
        return 1
    fi

    if ! wait_for_service "Thoth API" "http://localhost:8000/health" 120; then
        print_status "ERROR" "Thoth API failed to start"
        docker compose -f docker-compose.dev.yml logs thoth-app
        return 1
    fi

    # Test API functionality
    print_status "INFO" "Testing API functionality..."
    local response=$(curl -s -f http://localhost:8000/health || echo "FAILED")
    if [[ "$response" == "FAILED" ]]; then
        print_status "ERROR" "API health check failed"
        return 1
    fi

    print_status "SUCCESS" "Development environment is working"

    # Cleanup
    print_status "INFO" "Stopping development services..."
    docker compose -f docker-compose.dev.yml down > /dev/null 2>&1

    return 0
}

# Test 5: Test production environment
test_production_environment() {
    print_status "INFO" "Testing production environment..."

    cd "$PROJECT_DIR"

    # Create test production environment file
    if [[ ! -f ".env.prod" ]]; then
        cp .env.prod.example .env.prod
        print_status "INFO" "Created .env.prod from example"
    fi

    # Start production services
    print_status "INFO" "Starting production services..."
    docker compose -f docker-compose.prod.yml up -d > /tmp/docker-prod-up.log 2>&1

    # Wait for services
    if ! wait_for_service "ChromaDB" "http://localhost:8003/api/v1/heartbeat" 60; then
        print_status "ERROR" "Production ChromaDB failed to start"
        docker compose -f docker-compose.prod.yml logs chromadb
        return 1
    fi

    if ! wait_for_service "Thoth API" "http://localhost:8000/health" 120; then
        print_status "ERROR" "Production Thoth API failed to start"
        docker compose -f docker-compose.prod.yml logs thoth-app
        return 1
    fi

    # Test API functionality
    print_status "INFO" "Testing production API functionality..."
    local response=$(curl -s -f http://localhost:8000/health || echo "FAILED")
    if [[ "$response" == "FAILED" ]]; then
        print_status "ERROR" "Production API health check failed"
        return 1
    fi

    print_status "SUCCESS" "Production environment is working"

    # Cleanup
    print_status "INFO" "Stopping production services..."
    docker compose -f docker-compose.prod.yml down > /dev/null 2>&1

    return 0
}

# Test 6: Volume persistence test
test_volume_persistence() {
    print_status "INFO" "Testing volume persistence..."

    cd "$PROJECT_DIR"

    # Start development environment
    docker compose -f docker-compose.dev.yml up -d > /dev/null 2>&1

    # Wait for services
    wait_for_service "Thoth API" "http://localhost:8000/health" 60 > /dev/null

    # Create test data
    local test_file="/workspace/test-persistence.txt"
    local test_content="Docker persistence test $(date)"

    docker exec thoth-app-dev bash -c "echo '$test_content' > $test_file"

    # Restart services
    docker compose -f docker-compose.dev.yml restart thoth-app > /dev/null 2>&1
    wait_for_service "Thoth API" "http://localhost:8000/health" 60 > /dev/null

    # Check if data persists
    local persisted_content=$(docker exec thoth-app-dev cat $test_file 2>/dev/null || echo "MISSING")

    if [[ "$persisted_content" != "$test_content" ]]; then
        print_status "ERROR" "Volume persistence test failed"
        docker compose -f docker-compose.dev.yml down > /dev/null 2>&1
        return 1
    fi

    print_status "SUCCESS" "Volume persistence is working"

    # Cleanup
    docker exec thoth-app-dev rm -f $test_file
    docker compose -f docker-compose.dev.yml down > /dev/null 2>&1

    return 0
}

# Test 7: Resource limits test
test_resource_limits() {
    print_status "INFO" "Testing resource limits..."

    cd "$PROJECT_DIR"

    # Start production services (which have resource limits)
    docker compose -f docker-compose.prod.yml up -d > /dev/null 2>&1
    wait_for_service "Thoth API" "http://localhost:8000/health" 60 > /dev/null

    # Check resource limits are applied
    local memory_limit=$(docker inspect thoth-app-prod --format='{{.HostConfig.Memory}}' 2>/dev/null || echo "0")

    if [[ "$memory_limit" == "0" ]]; then
        print_status "WARNING" "No memory limits detected (this may be expected)"
    else
        print_status "SUCCESS" "Resource limits are applied"
    fi

    # Cleanup
    docker compose -f docker-compose.prod.yml down > /dev/null 2>&1

    return 0
}

# Test 8: Security test
test_security() {
    print_status "INFO" "Testing security configuration..."

    cd "$PROJECT_DIR"

    # Start production services
    docker compose -f docker-compose.prod.yml up -d > /dev/null 2>&1
    wait_for_service "Thoth API" "http://localhost:8000/health" 60 > /dev/null

    # Check if running as non-root user
    local user_id=$(docker exec thoth-app-prod id -u 2>/dev/null || echo "0")
    if [[ "$user_id" == "0" ]]; then
        print_status "WARNING" "Container is running as root user"
    else
        print_status "SUCCESS" "Container is running as non-root user (uid: $user_id)"
    fi

    # Check for read-only filesystem (if configured)
    local readonly_check=$(docker exec thoth-app-prod touch /test-write 2>&1 | grep -c "Read-only" || echo "0")
    if [[ "$readonly_check" -gt "0" ]]; then
        print_status "SUCCESS" "Read-only filesystem is configured"
    else
        print_status "INFO" "Filesystem is writable (this may be expected for development)"
    fi

    # Cleanup
    docker compose -f docker-compose.prod.yml down > /dev/null 2>&1

    return 0
}

# Main test execution
main() {
    local failed_tests=0
    local total_tests=8

    print_status "INFO" "Starting Docker setup validation..."
    print_status "INFO" "Project directory: $PROJECT_DIR"
    echo ""

    # Run all tests
    local tests=(
        "test_prerequisites"
        "test_docker_files"
        "test_docker_build"
        "test_development_environment"
        "test_production_environment"
        "test_volume_persistence"
        "test_resource_limits"
        "test_security"
    )

    for test_func in "${tests[@]}"; do
        echo ""
        print_status "INFO" "Running $test_func..."

        if ! $test_func; then
            failed_tests=$((failed_tests + 1))
            print_status "ERROR" "$test_func FAILED"
        else
            print_status "SUCCESS" "$test_func PASSED"
        fi
    done

    # Summary
    echo ""
    print_status "INFO" "============== Test Summary =============="
    print_status "INFO" "Total tests: $total_tests"
    print_status "INFO" "Passed: $((total_tests - failed_tests))"
    print_status "INFO" "Failed: $failed_tests"

    if [[ $failed_tests -eq 0 ]]; then
        print_status "SUCCESS" "All tests passed! Docker setup is ready."
        echo ""
        print_status "INFO" "You can now use:"
        echo "  make docker-dev     # Start development environment"
        echo "  make docker-prod    # Start production environment"
        echo "  make docker-health  # Check service health"
        return 0
    else
        print_status "ERROR" "$failed_tests tests failed. Please check the configuration."
        return 1
    fi
}

# Handle script interruption
cleanup() {
    print_status "WARNING" "Test interrupted. Cleaning up..."
    cd "$PROJECT_DIR"
    docker compose -f docker-compose.dev.yml down > /dev/null 2>&1 || true
    docker compose -f docker-compose.prod.yml down > /dev/null 2>&1 || true
    exit 130
}

trap cleanup INT TERM

# Run main function
main "$@"
