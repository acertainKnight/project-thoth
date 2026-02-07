#!/bin/bash
# ==============================================================================
# Thoth All-in-One Container Entrypoint
# Initializes environment and starts all services via Supervisor
# ==============================================================================

set -e

echo "🚀 Starting Thoth All-in-One Container..."
echo "========================================="

# Create log directory if it doesn't exist (new and legacy paths)
if [ -d /vault/thoth/_thoth ]; then
  LOG_DIR=/vault/thoth/_thoth/logs
elif [ -d /vault/_thoth ]; then
  LOG_DIR=/vault/_thoth/logs
else
  LOG_DIR=/vault/thoth/_thoth/logs
fi
mkdir -p "$LOG_DIR"
chmod 755 "$LOG_DIR"

# Ensure proper permissions
chown -R thoth:thoth "$LOG_DIR" 2>/dev/null || true

# Check database connection
echo "📊 Checking PostgreSQL connection..."
until python -c "import psycopg2; psycopg2.connect('${DATABASE_URL}')" 2>/dev/null; do
    echo "⏳ Waiting for PostgreSQL..."
    sleep 2
done
echo "✅ PostgreSQL is ready"

# Check Letta service
echo "🧠 Checking Letta service..."
until curl -sf "${THOTH_LETTA_URL}/v1/health" >/dev/null 2>&1; do
    echo "⏳ Waiting for Letta..."
    sleep 2
done
echo "✅ Letta is ready"

# Run any database migrations if needed
echo "🔄 Running database migrations..."
# Add migration commands here if needed

echo ""
echo "✨ All prerequisites met!"
echo "📦 Starting all Thoth services via Supervisor..."
echo ""
echo "Services:"
echo "  • API Server:      http://0.0.0.0:8000"
echo "  • MCP Server:      http://0.0.0.0:8000 (HTTP transport with /mcp and /sse endpoints)"
echo "  • Discovery:       (scheduler)"
echo "  • PDF Monitor:     (file watcher)"
echo ""
echo "Logs: $LOG_DIR"
echo "========================================="
echo ""

# Start supervisor
exec /usr/bin/supervisord -c /etc/supervisor/supervisord.conf
