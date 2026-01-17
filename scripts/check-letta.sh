#!/bin/bash
# ==============================================================================
# Letta Service Check - Prevents duplicate Letta instances
# ==============================================================================
# This script ensures Letta is running before starting Thoth services
# Prevents "make dev" from starting a conflicting Letta instance
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🔍 Checking Letta service status...${NC}"

# Check if .env.letta exists, create from example if not
if [ ! -f ".env.letta" ]; then
    echo -e "${YELLOW}⚠️  .env.letta not found${NC}"

    if [ -f ".env.letta.example" ]; then
        echo -e "${YELLOW}Creating .env.letta from .env.letta.example...${NC}"
        cp .env.letta.example .env.letta
        echo -e "${GREEN}✅ Created .env.letta${NC}"
        echo -e "${YELLOW}📝 Note: Edit .env.letta to add your API keys${NC}"
        echo ""
    else
        echo -e "${RED}❌ .env.letta.example not found${NC}"
        echo -e "${YELLOW}Please create .env.letta with Letta configuration${NC}"
        exit 1
    fi
fi

# Check if Letta containers are running
if docker ps --format '{{.Names}}' | grep -q '^letta-server$'; then
    echo -e "${GREEN}✅ Letta server is running${NC}"
    LETTA_RUNNING=true
elif docker ps --format '{{.Names}}' | grep -q '^thoth-dev-letta$'; then
    echo -e "${GREEN}✅ Thoth-dev Letta is running${NC}"
    LETTA_RUNNING=true
else
    echo -e "${RED}❌ No Letta service is running${NC}"
    LETTA_RUNNING=false
fi

# Check if Letta postgres is running
if docker ps --format '{{.Names}}' | grep -q '^letta-postgres$'; then
    echo -e "${GREEN}✅ Letta postgres is running (port 5432)${NC}"
    POSTGRES_RUNNING=true
elif docker ps --format '{{.Names}}' | grep -q '^thoth-dev-letta-postgres$'; then
    echo -e "${GREEN}✅ Thoth-dev postgres is running (port 5433)${NC}"
    POSTGRES_RUNNING=true
else
    echo -e "${RED}❌ No Letta postgres is running${NC}"
    POSTGRES_RUNNING=false
fi

# If neither Letta nor postgres is running, offer to start them
if [ "$LETTA_RUNNING" = false ] && [ "$POSTGRES_RUNNING" = false ]; then
    echo ""
    echo -e "${YELLOW}⚠️  Letta is not running. Thoth requires Letta to be running.${NC}"
    echo ""
    echo -e "${YELLOW}Would you like to start the standalone Letta service?${NC}"
    echo -e "  ${GREEN}y${NC} - Start standalone Letta (recommended, preserves agents)"
    echo -e "  ${RED}n${NC} - Continue without Letta (services will fail)"
    echo ""
    read -p "Start Letta? (y/n): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Starting standalone Letta...${NC}"
        docker compose -f docker-compose.letta.yml up -d

        # Wait for Letta to be healthy
        echo -e "${YELLOW}Waiting for Letta to be healthy...${NC}"
        timeout 60 bash -c 'until docker inspect letta-server 2>/dev/null | jq -r ".[0].State.Health.Status" | grep -q "healthy"; do echo "  Waiting..."; sleep 3; done' || {
            echo -e "${RED}❌ Letta failed to become healthy${NC}"
            exit 1
        }
        echo -e "${GREEN}✅ Letta is ready!${NC}"
    else
        echo -e "${RED}⚠️  Continuing without Letta. Services may fail.${NC}"
    fi
fi

# Check API accessibility
echo ""
echo -e "${YELLOW}🔍 Checking Letta API...${NC}"
if curl -sf http://localhost:8283/v1/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Letta API is responding on port 8283${NC}"
else
    echo -e "${RED}❌ Letta API is not responding${NC}"
    echo -e "${YELLOW}   This is normal during startup. Check with: docker logs letta-server${NC}"
fi

echo ""
echo -e "${GREEN}✅ Letta check complete${NC}"
