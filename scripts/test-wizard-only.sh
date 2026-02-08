#!/bin/bash
# Test setup wizard WITHOUT starting containers
# Safe to run alongside production

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_DIR="/home/nick-hallmark/Documents/python/project-thoth"
TEST_VAULT="/tmp/thoth-wizard-test-$$"
TEST_CONFIG="/tmp/thoth-wizard-config-$$"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Thoth Wizard Test (No Container Startup)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${GREEN}This test runs the wizard WITHOUT starting containers${NC}"
echo -e "${GREEN}Safe to run while production is running${NC}\n"

mkdir -p "$TEST_VAULT/thoth/_thoth"
mkdir -p "$TEST_CONFIG"

echo -e "${YELLOW}Building setup image...${NC}"
cd "$PROJECT_DIR"
docker build -f Dockerfile.setup -t thoth-setup:test-wizard . 2>&1 | grep -v "^#" || true

echo -e "\n${GREEN}Starting wizard (config only)...${NC}\n"

# Run wizard WITHOUT Docker socket (can't start containers)
docker run -it --rm \
  -v "$TEST_VAULT:/vault" \
  -v "$TEST_CONFIG:/root/.config/thoth" \
  -e OBSIDIAN_VAULT_PATH="/vault" \
  -e THOTH_SKIP_SERVICE_START=1 \
  thoth-setup:test-wizard

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Wizard Test Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "Generated files:"
echo -e "  Vault: ${BLUE}$TEST_VAULT${NC}"
echo -e "  Config: ${BLUE}$TEST_CONFIG${NC}"

SETTINGS_FILE="$TEST_VAULT/thoth/_thoth/settings.json"
[ ! -f "$SETTINGS_FILE" ] && SETTINGS_FILE="$TEST_VAULT/_thoth/settings.json"
if [ -f "$SETTINGS_FILE" ]; then
    echo -e "\n${YELLOW}Generated settings.json:${NC}"
    cat "$SETTINGS_FILE" | jq '.' 2>/dev/null || cat "$SETTINGS_FILE"
fi

echo -e "\n${YELLOW}View test results or clean up?${NC}"
echo "  1) View all generated files"
echo "  2) Compare with production settings"
echo "  3) Clean up"
echo "  4) Keep for inspection"
echo ""
read -p "Choose [1-4]: " ACTION

case $ACTION in
    1)
        echo -e "\n${BLUE}Generated Files:${NC}"
        find "$TEST_VAULT" -type f -exec echo -e "\n--- {} ---" \; -exec head -20 {} \;
        ;;
    2)
        PROD_SETTINGS=~/Documents/thoth/thoth/_thoth/settings.json
        [ ! -f "$PROD_SETTINGS" ] && PROD_SETTINGS=~/Documents/thoth/_thoth/settings.json
        if [ -f "$PROD_SETTINGS" ]; then
            echo -e "\n${BLUE}Comparing with production:${NC}"
            diff -u "$PROD_SETTINGS" "$SETTINGS_FILE" || true
        else
            echo "Production settings not found at expected location"
        fi
        ;;
    3)
        rm -rf "$TEST_VAULT" "$TEST_CONFIG"
        docker rmi thoth-setup:test-wizard 2>/dev/null || true
        echo -e "${GREEN}✓ Cleaned up${NC}"
        exit 0
        ;;
    4)
        echo -e "\n${GREEN}Preserved at:${NC}"
        echo -e "  ${BLUE}$TEST_VAULT${NC}"
        echo -e "  ${BLUE}$TEST_CONFIG${NC}"
        exit 0
        ;;
esac

# Cleanup
echo -e "\n${RED}Clean up test files?${NC}"
read -p "[y/N]: " CLEANUP
if [[ "$CLEANUP" =~ ^[Yy]$ ]]; then
    rm -rf "$TEST_VAULT" "$TEST_CONFIG"
    docker rmi thoth-setup:test-wizard 2>/dev/null || true
    echo -e "${GREEN}✓ Cleaned up${NC}"
fi
