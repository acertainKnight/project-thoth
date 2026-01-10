#!/bin/bash
# Check Thoth and Letta services status
# Usage: thoth-status.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "📊 Thoth Services Status:"
echo ""
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "📊 Letta Services Status (Independent):"
echo ""
docker compose -f docker-compose.letta.yml ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🔍 Health Checks:"

# Check Thoth API
if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    echo "✅ Thoth API (8080): Healthy"
else
    echo "❌ Thoth API (8080): Not responding"
fi

# Check Letta API
if curl -sf http://localhost:8283/v1/health > /dev/null 2>&1; then
    echo "✅ Letta API (8283): Healthy"
else
    echo "❌ Letta API (8283): Not responding"
fi

# Check Letta SSE
if curl -sf http://localhost:8284/nginx-health > /dev/null 2>&1; then
    echo "✅ Letta SSE Proxy (8284): Healthy"
else
    echo "❌ Letta SSE Proxy (8284): Not responding"
fi

echo ""
echo "🔗 Network Connectivity:"
if docker network inspect letta-network >/dev/null 2>&1; then
    echo "✅ letta-network: Connected"
else
    echo "❌ letta-network: Not found (run letta-start first)"
fi
