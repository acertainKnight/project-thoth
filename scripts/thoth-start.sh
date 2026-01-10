#!/bin/bash
# Start Thoth services (requires Letta to be running)
# Usage: thoth-start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Check if Letta is running
if ! docker ps --format '{{.Names}}' | grep -q "letta-server"; then
    echo "⚠️  WARNING: Letta is not running!"
    echo "   Start Letta first: letta-start"
    echo ""
    read -p "Would you like to start Letta now? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        "$SCRIPT_DIR/letta-start.sh"
        echo ""
        echo "⏳ Waiting for Letta to be healthy..."
        sleep 10
    else
        echo "❌ Exiting. Please start Letta first."
        exit 1
    fi
fi

echo "🚀 Starting Thoth services..."
echo "📦 Using docker-compose.yml"
docker compose up -d

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check service status
echo ""
echo "📊 Thoth Service Status:"
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "✅ Thoth services are running!"
echo "   - Thoth API: http://localhost:8080"
echo "   - Thoth MCP: http://localhost:8081"
echo ""
echo "ℹ️  Letta services remain independent:"
echo "   - Letta API: http://localhost:8283"
echo "   - Letta SSE: http://localhost:8284"
