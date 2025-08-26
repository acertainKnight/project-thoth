#!/bin/bash
# ==============================================================================
# Thoth Service Dependency Wait Script
# Waits for required services to be healthy before starting main application
# ==============================================================================

set -e

# Configuration
CHROMADB_URL="${CHROMADB_URL:-http://chromadb:8003}"
MAX_WAIT_TIME=300  # 5 minutes
CHECK_INTERVAL=5   # 5 seconds
TIMEOUT=10         # 10 seconds for individual checks

echo "=== Thoth Service Dependency Checker ==="
echo "Waiting for required services to be healthy..."
echo "Max wait time: ${MAX_WAIT_TIME} seconds"
echo "Check interval: ${CHECK_INTERVAL} seconds"
echo "==========================================="

# Function to check if a service is healthy
check_service() {
    local service_name=$1
    local url=$2
    local expected_status=${3:-200}

    echo -n "Checking ${service_name} at ${url}... "

    if curl -f -s -m ${TIMEOUT} "${url}" > /dev/null 2>&1; then
        echo "✓ Healthy"
        return 0
    else
        echo "✗ Not ready"
        return 1
    fi
}

# Function to wait for a service with timeout
wait_for_service() {
    local service_name=$1
    local url=$2
    local expected_status=${3:-200}
    local waited=0

    echo "Waiting for ${service_name} to be ready..."

    while [ $waited -lt $MAX_WAIT_TIME ]; do
        if check_service "${service_name}" "${url}" "${expected_status}"; then
            echo "✓ ${service_name} is ready!"
            return 0
        fi

        waited=$((waited + CHECK_INTERVAL))
        echo "Waiting... (${waited}/${MAX_WAIT_TIME}s)"
        sleep $CHECK_INTERVAL
    done

    echo "✗ Timeout waiting for ${service_name} after ${MAX_WAIT_TIME} seconds"
    return 1
}

# Function to initialize workspace directories
initialize_workspace() {
    echo "Initializing workspace directories..."

    # Create required directories if they don't exist
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/pdfs"
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/notes"
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/data"
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/queries"
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/discovery"
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/knowledge"
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/logs"
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/cache"
    mkdir -p "${THOTH_WORKSPACE_DIR:-/workspace}/tmp"

    echo "✓ Workspace directories initialized"
}

# Function to check ChromaDB collections
initialize_chromadb() {
    echo "Initializing ChromaDB collections..."

    # Check if ChromaDB is accessible
    if ! curl -f -s -m ${TIMEOUT} "${CHROMADB_URL}/api/v1/heartbeat" > /dev/null; then
        echo "✗ ChromaDB not accessible for initialization"
        return 1
    fi

    # List existing collections
    collections=$(curl -s -m ${TIMEOUT} "${CHROMADB_URL}/api/v1/collections" 2>/dev/null || echo "[]")

    echo "✓ ChromaDB collections check complete"
    echo "Found collections: ${collections}"
}

# Function to perform system readiness check
system_readiness_check() {
    echo "Performing system readiness check..."

    # Check required environment variables
    local required_vars=("THOTH_WORKSPACE_DIR" "THOTH_API_HOST" "THOTH_API_PORT")
    local missing_vars=()

    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -gt 0 ]; then
        echo "✗ Missing required environment variables: ${missing_vars[*]}"
        return 1
    fi

    # Check if workspace is writable
    if [ ! -w "${THOTH_WORKSPACE_DIR:-/workspace}" ]; then
        echo "✗ Workspace directory is not writable: ${THOTH_WORKSPACE_DIR:-/workspace}"
        return 1
    fi

    echo "✓ System readiness check passed"
}

# Main execution
main() {
    echo "Starting Thoth service dependency checks..."

    # Initialize workspace
    initialize_workspace

    # System readiness check
    system_readiness_check

    # Wait for ChromaDB
    if ! wait_for_service "ChromaDB" "${CHROMADB_URL}/api/v1/heartbeat"; then
        echo "✗ ChromaDB failed to become ready"
        exit 1
    fi

    # Initialize ChromaDB
    initialize_chromadb

    # Final readiness message
    echo "=========================================="
    echo "✓ All services are ready!"
    echo "✓ Thoth application can now start safely"
    echo "=========================================="

    # If a command was passed, execute it
    if [ $# -gt 0 ]; then
        echo "Executing command: $*"
        exec "$@"
    fi
}

# Handle script termination
cleanup() {
    echo
    echo "Service dependency check interrupted"
    exit 130
}

trap cleanup INT TERM

# Run main function with all arguments
main "$@"
