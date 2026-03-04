#!/bin/bash
set -e

# --- Database migration ---
# Letta's startup.sh normally runs `alembic upgrade head`, but we bypass
# it by calling `letta server` directly. Run migrations here instead.
#
# Databases created before Letta used Alembic won't have an
# alembic_version table. If we detect that case, stamp the version that
# matches the last known schema so Alembic can apply incremental
# migrations going forward.
echo "==> Running database migrations..."
cd /app

# LETTA_PG_URI is set by docker-compose (e.g. postgresql://letta:pass@host:5432/letta)
DB_URI="${LETTA_PG_URI:-postgresql://letta:letta_password@letta-postgres:5432/letta}"

HAS_ALEMBIC=$(psql "$DB_URI" -tAc \
    "SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version'" 2>/dev/null || echo "")

if [ "$HAS_ALEMBIC" != "1" ]; then
    HAS_TABLES=$(psql "$DB_URI" -tAc \
        "SELECT 1 FROM information_schema.tables WHERE table_name='organizations'" 2>/dev/null || echo "")

    if [ "$HAS_TABLES" = "1" ]; then
        # Pre-Alembic database. Check which era it's from so we can stamp
        # the right revision and let alembic apply only the missing ones.
        HAS_LAST_SYNCED=$(psql "$DB_URI" -tAc \
            "SELECT 1 FROM information_schema.columns WHERE table_name='providers' AND column_name='last_synced'" 2>/dev/null || echo "")

        if [ "$HAS_LAST_SYNCED" = "1" ]; then
            echo "==> Pre-Alembic database detected (already patched), stamping at head"
            alembic stamp head
        else
            # 0.16.3-era schema. Stamp at the last revision whose tables
            # already exist so alembic upgrade head fills the gaps.
            echo "==> Pre-Alembic database detected (0.16.3 era), stamping at 82feb220a9b8"
            alembic stamp 82feb220a9b8
        fi
    fi
    # No tables = fresh install. alembic upgrade head creates everything.
fi

if ! alembic upgrade head; then
    echo "==> WARNING: alembic upgrade head failed, Letta will attempt its own migration"
fi
cd /

echo "==> Starting Letta server..."
letta server --host 0.0.0.0 --port 8283 --ade &
LETTA_PID=$!

# Wait for Letta to become healthy (it creates the schema + default org
# during startup, so the /v1/health endpoint only succeeds after that).
echo "==> Waiting for Letta to be ready..."
MAX_WAIT=180
WAITED=0
until curl -sf http://localhost:8283/v1/health > /dev/null 2>&1; do
    if ! kill -0 "$LETTA_PID" 2>/dev/null; then
        echo "==> ERROR: Letta process exited unexpectedly"
        exit 1
    fi
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo "==> ERROR: Letta did not become healthy within ${MAX_WAIT}s"
        exit 1
    fi
    sleep 3
    WAITED=$((WAITED + 3))
    echo "  Still waiting... (${WAITED}s)"
done

echo "==> Letta is healthy (took ~${WAITED}s)"

# Register the Thoth MCP server via the REST API. This avoids the
# foreign-key issues that come from inserting directly into the DB
# before Letta seeds its default organization.
# THOTH_MCP_URL comes from docker-compose.letta.yml (default: http://thoth-mcp:8001).
# The MCP endpoint path is /mcp under that base URL.
THOTH_MCP_BASE="${THOTH_MCP_URL:-http://thoth-mcp:8001}"
THOTH_MCP_ENDPOINT="${THOTH_MCP_BASE}/mcp"

echo "==> Registering Thoth MCP server via API..."

# Check if already registered
EXISTING=$(curl -sf http://localhost:8283/v1/tools/mcp/servers 2>/dev/null || echo "[]")
if echo "$EXISTING" | grep -q '"thoth-research-tools"'; then
    echo "==> Thoth MCP server already registered"
else
    # The /v1/tools/mcp/servers endpoint registers a new MCP server.
    # Letta 0.16+ uses streamable_http transport.
    RESPONSE=$(curl -sf -X POST http://localhost:8283/v1/tools/mcp/servers \
        -H "Content-Type: application/json" \
        -d "{
            \"server_name\": \"thoth-research-tools\",
            \"server_type\": \"streamable_http\",
            \"server_url\": \"${THOTH_MCP_ENDPOINT}\"
        }" 2>&1) || true

    if echo "$RESPONSE" | grep -q '"id"'; then
        echo "==> Thoth MCP server registered successfully"
    else
        # Non-fatal: the MCP server can be registered later via the UI
        echo "==> Warning: Could not register MCP server via API."
        echo "    Response: ${RESPONSE}"
        echo "    You can register it manually in the Letta ADE."
    fi
fi

echo "==> Letta initialization complete, server running (pid $LETTA_PID)"

# Bring the Letta process to the foreground so Docker can track it
wait "$LETTA_PID"
