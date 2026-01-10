#!/bin/bash
# Start Letta services INDEPENDENTLY (not managed by Thoth)
# Usage: letta-start.sh
#
# Letta is a generic self-hosted service that can be used by multiple projects.
# This script starts it independently so restarting Thoth won't affect Letta.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "🚀 Starting INDEPENDENT Letta services..."
echo "📦 Using docker-compose.letta.yml"
echo "🔧 This is a generic Letta instance (can be used by multiple projects)"
docker compose -f docker-compose.letta.yml up -d

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
