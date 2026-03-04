#!/bin/bash
set -e

# Letta Migration Script
# Safely migrates Letta to a new version using in-place schema migration.
# Falls back to destructive recreate only if the user explicitly chooses it.
#
# Usage: ./letta-migrate.sh [new-version]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NEW_VERSION=${1:-"latest"}
BACKUP_DIR=~/letta-backup-$(date +%Y%m%d-%H%M%S)
LETTA_URL="http://localhost:8283"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Letta Migration Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# --- Step 1: Check current version ---
echo -e "${YELLOW}[1/5] Checking current Letta version...${NC}"
CURRENT_VERSION=$(docker exec letta-server letta version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "unknown")
echo "Current version: $CURRENT_VERSION"
echo "Target version:  $NEW_VERSION"
echo ""

# --- Step 2: Backup agents ---
echo -e "${YELLOW}[2/5] Backing up agents...${NC}"
mkdir -p "$BACKUP_DIR"
AGENT_COUNT=0

while read -r agent_id; do
    if [ -n "$agent_id" ]; then
        curl -s "${LETTA_URL}/v1/agents/${agent_id}" > "${BACKUP_DIR}/${agent_id}.json"
        ((AGENT_COUNT++))
        echo "  Backed up: ${agent_id:0:16}..."
    fi
done < <(curl -s "${LETTA_URL}/v1/agents/?limit=1000" | jq -r '.[].id' 2>/dev/null)

echo -e "${GREEN}Backed up $AGENT_COUNT agents to: $BACKUP_DIR${NC}"
echo ""

# --- Step 3: Stop Letta and update image ---
echo -e "${YELLOW}[3/5] Stopping Letta and pulling new image...${NC}"
docker compose -f docker-compose.letta.yml stop letta

if [ "$NEW_VERSION" = "latest" ]; then
    sed -i 's|image: letta/letta:.*|image: letta/letta:latest|' docker-compose.letta.yml
else
    sed -i "s|image: letta/letta:.*|image: letta/letta:$NEW_VERSION|" docker-compose.letta.yml
fi

docker compose -f docker-compose.letta.yml pull letta
echo -e "${GREEN}Image updated${NC}"
echo ""

# --- Step 4: Start Letta (init-schema.sh handles migration) ---
echo -e "${YELLOW}[4/5] Starting Letta with new version...${NC}"
echo "The init script will automatically handle database schema migration."
echo ""
docker compose -f docker-compose.letta.yml up -d letta

echo "Waiting for Letta to initialize (this may take a minute on first migration)..."
MAX_WAIT=180
WAITED=0
until curl -sf "${LETTA_URL}/v1/health" > /dev/null 2>&1; do
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo ""
        echo -e "${RED}Letta did not start within ${MAX_WAIT}s.${NC}"
        echo -e "${YELLOW}Check logs with: docker logs letta-server${NC}"
        echo ""
        echo "If the migration failed, you can try the destructive migration:"
        echo "  1. docker compose -f docker-compose.letta.yml stop letta"
        echo "  2. docker exec letta-postgres psql -U letta -d postgres -c 'DROP DATABASE letta;'"
        echo "  3. docker exec letta-postgres psql -U letta -d postgres -c 'CREATE DATABASE letta OWNER letta;'"
        echo "  4. docker exec letta-postgres psql -U letta -d letta -c 'CREATE EXTENSION IF NOT EXISTS vector;'"
        echo "  5. docker compose -f docker-compose.letta.yml up -d letta"
        echo "  6. python3 scripts/restore-agents-complete.py $BACKUP_DIR $LETTA_URL"
        exit 1
    fi
    sleep 3
    WAITED=$((WAITED + 3))
    echo "  Waiting... (${WAITED}s)"
done

echo -e "${GREEN}Letta is healthy (took ~${WAITED}s)${NC}"
echo ""

# --- Step 5: Verify agents ---
echo -e "${YELLOW}[5/5] Verifying agents...${NC}"
AGENT_COUNT_AFTER=$(curl -s "${LETTA_URL}/v1/agents/?limit=1000" | jq 'length' 2>/dev/null || echo "0")
echo "Agents found after migration: $AGENT_COUNT_AFTER (was: $AGENT_COUNT)"

if [ "$AGENT_COUNT_AFTER" -ge "$AGENT_COUNT" ]; then
    echo -e "${GREEN}All agents preserved${NC}"
else
    echo -e "${YELLOW}Some agents may need to be recreated. Backup is at: $BACKUP_DIR${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Migration Complete${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Backup:  $BACKUP_DIR"
echo "Version: $NEW_VERSION"
echo ""
echo "Next: restart Thoth to pick up agent tool changes:"
echo "  make dev-thoth-restart"
