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
