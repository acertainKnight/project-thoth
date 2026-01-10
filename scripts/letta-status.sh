#!/bin/bash
# Check Letta services status
# Usage: letta-status.sh

echo "📊 Letta Services Status:"
echo ""
docker ps --filter "name=letta" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "🔍 Health Check:"
if curl -sf http://localhost:8283/v1/health > /dev/null 2>&1; then
    echo "✅ Letta API (8283): Healthy"
else
    echo "❌ Letta API (8283): Not responding"
fi

if curl -sf http://localhost:8284/nginx-health > /dev/null 2>&1; then
    echo "✅ Letta SSE Proxy (8284): Healthy"
else
    echo "❌ Letta SSE Proxy (8284): Not responding"
fi
