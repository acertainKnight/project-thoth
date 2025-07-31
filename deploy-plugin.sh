#!/bin/bash

# =============================================================================
# Quick Deploy Script for Thoth Obsidian Plugin
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Show usage if no arguments provided
if [ $# -eq 0 ]; then
    echo -e "${BLUE}Quick Deploy Script for Thoth Obsidian Plugin${NC}"
    echo "================================================"
    echo ""
    echo "Usage: $0 OBSIDIAN_VAULT_PATH"
    echo ""
    echo "EXAMPLES:"
    echo "  $0 \"/home/user/Documents/Obsidian Vault\""
    echo "  $0 ~/Documents/ObsidianVault"
    echo "  $0 \"/mnt/c/Users/user/Documents/Obsidian Vault\""
    echo ""
    echo "This script will:"
    echo "  1. Build the TypeScript plugin"
    echo "  2. Copy it to your Obsidian vault"
    echo "  3. Show next steps for testing"
    echo ""
    exit 1
fi

OBSIDIAN_VAULT="$1"

# Verify vault exists
if [ ! -d "$OBSIDIAN_VAULT" ]; then
    echo -e "${RED}❌ Obsidian vault not found at: $OBSIDIAN_VAULT${NC}"
    echo -e "${YELLOW}Please check the path and try again.${NC}"
    exit 1
fi

echo -e "${BLUE}🚀 Quick Deploy: Thoth Obsidian Plugin${NC}"
echo "============================================="
echo -e "${YELLOW}Target vault: $OBSIDIAN_VAULT${NC}"
echo ""

./build-plugin.sh --vault "$OBSIDIAN_VAULT"

echo ""
echo -e "${GREEN}🎉 Plugin deployed successfully!${NC}"
echo ""
echo -e "${YELLOW}🔥 Quick Start:${NC}"
echo "1. Open Obsidian"
echo "2. Enable the plugin: Settings → Community plugins → Thoth Research Assistant"
echo "3. Start API server: make start-api"
echo "4. Click the Thoth ribbon icon to test!"
echo ""
echo -e "${GREEN}✨ Your enhanced plugin is ready! ✨${NC}"
