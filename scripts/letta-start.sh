#!/bin/bash
# Start Letta and PostgreSQL services
# Usage: letta-start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🚀 Starting Letta services..."
docker compose up -d letta-postgres letta-redis letta letta-nginx

echo ""
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check service status
echo ""
echo "📊 Service Status:"
docker ps --filter "name=letta" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "✅ Letta services are running!"
echo "   - Letta API: http://localhost:8283"
echo "   - Letta SSE: http://localhost:8284"
echo "   - PostgreSQL: localhost:5432 (internal)"
