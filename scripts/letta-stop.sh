#!/bin/bash
# Stop Letta services (INDEPENDENT from Thoth)
# Usage: letta-stop.sh
#
# WARNING: This will stop Letta for ALL projects using it!

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🛑 Stopping INDEPENDENT Letta services..."
echo "⚠️  WARNING: This will affect ALL projects using Letta!"
docker compose -f docker-compose.letta.yml stop

echo ""
echo "✅ Letta services stopped!"
