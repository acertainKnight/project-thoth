#!/bin/bash
set -e

# Letta Migration Script
# Safely migrates Letta database when upgrading versions
# Usage: ./letta-migrate.sh [new-version]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NEW_VERSION=${1:-"latest"}
BACKUP_DIR=~/letta-backup-$(date +%Y%m%d-%H%M%S)
LETTA_URL="http://localhost:8283"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Letta Migration Script${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Check current version
echo -e "${YELLOW}[1/8] Checking current Letta version...${NC}"
CURRENT_VERSION=$(docker exec letta-server letta version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "unknown")
echo "Current version: $CURRENT_VERSION"
echo "Target version: $NEW_VERSION"
echo ""

# Step 2: Backup agents
echo -e "${YELLOW}[2/8] Backing up agents...${NC}"
mkdir -p "$BACKUP_DIR"
AGENT_COUNT=0

# Export all agents to JSON
while read -r agent_id; do
    if [ -n "$agent_id" ]; then
        curl -s "${LETTA_URL}/v1/agents/${agent_id}" > "${BACKUP_DIR}/${agent_id}.json"
        ((AGENT_COUNT++))
        echo "  ✓ Backed up agent: $agent_id"
    fi
done < <(curl -s "${LETTA_URL}/v1/agents/?limit=1000" | jq -r '.[].id')

echo -e "${GREEN}Backed up $AGENT_COUNT agents to: $BACKUP_DIR${NC}"
echo ""

# Step 3: Stop Letta
echo -e "${YELLOW}[3/8] Stopping Letta services...${NC}"
docker compose -f docker-compose.letta.yml stop letta
echo -e "${GREEN}✓ Letta stopped${NC}"
echo ""

# Step 4: Update Docker image
echo -e "${YELLOW}[4/8] Updating Letta Docker image to $NEW_VERSION...${NC}"
if [ "$NEW_VERSION" = "latest" ]; then
    sed -i 's|image: letta/letta:.*|image: letta/letta:latest|' docker-compose.letta.yml
else
    sed -i "s|image: letta/letta:.*|image: letta/letta:$NEW_VERSION|" docker-compose.letta.yml
fi
echo -e "${GREEN}✓ Updated docker-compose.letta.yml${NC}"
echo ""

# Step 5: Recreate database
echo -e "${YELLOW}[5/8] Recreating database with new schema...${NC}"
echo -e "${RED}⚠️  This will delete all current agent data!${NC}"
read -p "Continue? (yes/no): " -r
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Migration cancelled."
    docker compose -f docker-compose.letta.yml start letta
    exit 1
fi

# Drop and recreate database
docker exec letta-postgres psql -U letta -d postgres -c "DROP DATABASE IF EXISTS letta;" 2>/dev/null || true
docker exec letta-postgres psql -U letta -d postgres -c "CREATE DATABASE letta OWNER letta;"

# Install pgvector extension
docker exec letta-postgres psql -U letta -d letta -c "CREATE EXTENSION IF NOT EXISTS vector;"
echo -e "${GREEN}✓ Database recreated${NC}"
echo ""

# Step 6: Start Letta with new version
echo -e "${YELLOW}[6/8] Starting Letta with new version...${NC}"
docker compose -f docker-compose.letta.yml up -d letta

# Wait for Letta to be healthy
echo "Waiting for Letta to initialize..."
timeout 120 bash -c 'until curl -sf http://localhost:8283/v1/health/ >/dev/null 2>&1; do sleep 3; done' || {
    echo -e "${RED}✗ Letta failed to start${NC}"
    exit 1
}
echo -e "${GREEN}✓ Letta started${NC}"
echo ""

# Step 7: Apply compatibility fixes
echo -e "${YELLOW}[7/8] Applying compatibility fixes...${NC}"

# Fix sequence_id for older Letta Code versions
docker exec letta-postgres psql -U letta -d letta -c "
DO \$\$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='messages' AND column_name='sequence_id') THEN
        EXECUTE 'CREATE SEQUENCE IF NOT EXISTS messages_sequence_id_seq OWNED BY messages.sequence_id';
        EXECUTE 'ALTER TABLE messages ALTER COLUMN sequence_id SET DEFAULT nextval(''messages_sequence_id_seq'')';
    END IF;
END \$\$;
" 2>/dev/null || true

echo -e "${GREEN}✓ Compatibility fixes applied${NC}"
echo ""

# Step 8: Restore agents with complete data
echo -e "${YELLOW}[8/8] Restoring agents (memory, tools, rules, tags)...${NC}"

# Use complete restoration script
python3 "$SCRIPT_DIR/restore-agents-complete.py" "$BACKUP_DIR" "$LETTA_URL"
RESTORE_STATUS=$?

if [ $RESTORE_STATUS -eq 0 ]; then
    echo -e "${GREEN}✓ Agent restoration completed successfully${NC}"
else
    echo -e "${RED}⚠️  Some agents failed to restore (see details above)${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Migration Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "Backup location: ${GREEN}$BACKUP_DIR${NC}"
echo -e "New Letta version: ${GREEN}$NEW_VERSION${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Test Letta Code: letta-code --info"
echo "2. Update pinned agents in ~/.letta/settings.json if needed"
echo "3. Commit changes: git add docker-compose.letta.yml && git commit -m 'chore: upgrade Letta to $NEW_VERSION'"
echo ""
