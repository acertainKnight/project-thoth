#!/bin/bash
set -e

# Docker-based Thoth Setup (NO PYTHON REQUIRED)
# This script runs the setup wizard entirely in Docker

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════╗"
echo "║   Thoth Setup (Docker Mode)          ║"
echo "║   No Python Installation Required    ║"
echo "╚═══════════════════════════════════════╝"
echo -e "${NC}\n"

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker not found. Installing Docker...${NC}"
    echo "Please visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Get vault path from user if not set
if [ -z "$OBSIDIAN_VAULT_PATH" ]; then
    echo -e "${BLUE}Enter your Obsidian vault path:${NC}"
    read -r vault_path
    export OBSIDIAN_VAULT_PATH="$vault_path"
fi

# Build Docker image if needed
if ! docker images | grep -q "project-thoth"; then
    echo -e "${YELLOW}Building Thoth Docker image...${NC}"
    docker compose build
fi

# Run setup wizard in Docker
echo -e "\n${GREEN}Starting setup wizard in Docker...${NC}\n"

docker run -it --rm \
    -v ~/.config/thoth:/root/.config/thoth \
    -v "$(dirname "$OBSIDIAN_VAULT_PATH"):/vaults" \
    -e OBSIDIAN_VAULT_PATH="/vaults/$(basename "$OBSIDIAN_VAULT_PATH")" \
    project-thoth:latest \
    python -m thoth setup

echo -e "\n${GREEN}✓ Setup complete!${NC}"
echo -e "\nTo start Thoth services:"
echo -e "  ${BLUE}docker compose up -d${NC}"
echo -e "\nTo check status:"
echo -e "  ${BLUE}docker compose ps${NC}"
