#!/bin/bash
# Thoth Docker Entrypoint Script
# Runs database migrations and starts the service

set -e

echo "==> Thoth Service Starting..."

# Function to wait for PostgreSQL
wait_for_postgres() {
    echo "==> Waiting for PostgreSQL..."

    until python3 -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('$DATABASE_URL'))" 2>/dev/null; do
        echo "  Waiting for database connection..."
        sleep 2
    done

    echo "  ✓ PostgreSQL is ready!"
}

# Function to ensure cache directories exist
setup_cache_directories() {
    echo "==> Setting up cache directories..."

    # Run as root to fix permissions (only if we're root or can sudo)
    if [ "$(id -u)" = "0" ]; then
        # We're root, do the setup
        mkdir -p /app/cache/ocr /app/cache/analysis /app/cache/citations /app/cache/api_responses /app/cache/embeddings
        chown -R thoth:thoth /app/cache 2>/dev/null || true
        chmod -R 775 /app/cache
    else
        # We're not root, just ensure directories exist (permissions already set in Dockerfile)
        mkdir -p /app/cache/ocr /app/cache/analysis /app/cache/citations /app/cache/api_responses /app/cache/embeddings || true
    fi

    echo "  ✓ Cache directories ready!"
}

# Function to run database migrations
run_migrations() {
    echo "==> Running database migrations..."

    # Check if migration script exists
    if [ -f "/app/src/thoth/migration/run_browser_workflow_migration.py" ]; then
        python3 -m thoth.migration.run_browser_workflow_migration || {
            echo "  ⚠ Migration failed or tables already exist (this is OK)"
        }
    else
        echo "  ⚠ Migration script not found, skipping..."
    fi

    echo "  ✓ Migrations complete!"
}

# Main entrypoint logic
main() {
    # Setup cache directories (always needed)
    setup_cache_directories

    # Wait for dependencies
    wait_for_postgres

    # Run migrations (only for API and MCP services)
    if [[ "$1" == *"server"* ]] || [[ "$1" == *"mcp"* ]]; then
        run_migrations
    fi

    # Execute the provided command
    echo "==> Starting service: $@"
    exec "$@"
}

# Run main entrypoint
main "$@"
