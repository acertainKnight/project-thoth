#!/bin/bash
# Stop Letta and PostgreSQL services
# Usage: letta-stop.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🛑 Stopping Letta services..."
docker compose stop letta-nginx letta letta-redis letta-postgres

echo ""
echo "✅ Letta services stopped!"
