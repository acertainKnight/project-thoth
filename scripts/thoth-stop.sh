#!/bin/bash
# Stop Thoth services (does NOT stop Letta)
# Usage: thoth-stop.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🛑 Stopping Thoth services..."
echo "ℹ️  Letta services will remain running (independent)"
docker compose stop

echo ""
echo "✅ Thoth services stopped!"
echo ""
echo "💡 To stop Letta (affects all projects): letta-stop"
