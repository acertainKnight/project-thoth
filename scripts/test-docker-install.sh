#!/bin/bash
# Safe Docker test with complete isolation including container names

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/home/nick-hallmark/Documents/python/project-thoth"
TEST_VAULT="/tmp/thoth-test-vault-$$"
TEST_CONFIG="/tmp/thoth-test-config-$$"
TEST_PREFIX="thoth-test-$$"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Thoth Installation Test (Full Docker)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo -e "${GREEN}Setting up isolated test environment...${NC}"
mkdir -p "$TEST_VAULT/thoth/_thoth"
mkdir -p "$TEST_CONFIG"

echo -e "${GREEN}✓ Test vault: $TEST_VAULT${NC}"
echo -e "${GREEN}✓ Test config: $TEST_CONFIG${NC}"

# Build test image
echo -e "\n${YELLOW}Building setup image...${NC}"
cd "$PROJECT_DIR"
docker build -f Dockerfile.setup -t thoth-setup:test .

echo -e "\n${GREEN}Starting setup wizard...${NC}"
echo -e "${YELLOW}Note: Wizard can start Docker containers (isolated by name prefix)${NC}\n"

# Create test docker-compose with prefixed names
export COMPOSE_PROJECT_NAME="$TEST_PREFIX"

# Run wizard with Docker socket access
docker run -it --rm \
  -v "$TEST_VAULT:/vault" \
  -v "$TEST_CONFIG:/root/.config/thoth" \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PROJECT_DIR:$PROJECT_DIR:ro" \
  -e OBSIDIAN_VAULT_PATH="/vault" \
  -e COMPOSE_PROJECT_NAME="$TEST_PREFIX" \
  -e THOTH_TEST_MODE=1 \
  --network host \
  thoth-setup:test

echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Setup Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Show results
echo "Test environment:"
echo -e "  Vault: ${BLUE}$TEST_VAULT${NC}"
echo -e "  Config: ${BLUE}$TEST_CONFIG${NC}"

# Check if containers were started
CONTAINERS=$(docker ps --filter "name=$TEST_PREFIX" --format "table {{.Names}}\t{{.Status}}" | tail -n +2)
if [ -n "$CONTAINERS" ]; then
    echo -e "\n${YELLOW}Test containers running:${NC}"
    echo "$CONTAINERS"
else
    echo -e "\n${YELLOW}No test containers started${NC}"
fi

# Offer actions
echo -e "\n${YELLOW}What would you like to do?${NC}"
echo "  1) View generated settings.json"
echo "  2) Check test containers"
echo "  3) Test API endpoint (if running)"
echo "  4) View container logs"
echo "  5) Clean up everything"
echo "  6) Keep environment for inspection"
echo ""
read -p "Choose [1-6]: " ACTION

case $ACTION in
    1)
        echo -e "\n${BLUE}Generated Settings:${NC}"
        SF="$TEST_VAULT/thoth/_thoth/settings.json"
        [ ! -f "$SF" ] && SF="$TEST_VAULT/_thoth/settings.json"
        if [ -f "$SF" ]; then
            cat "$SF" | jq '.' 2>/dev/null || cat "$SF"
        else
            echo "Settings file not found"
        fi
        ;;
    2)
        echo -e "\n${BLUE}Test Containers:${NC}"
        docker ps --filter "name=$TEST_PREFIX" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
        ;;
    3)
        echo -e "\n${BLUE}Testing API endpoint...${NC}"
        curl -s http://localhost:8000/health 2>/dev/null && echo "" || echo "API not responding"
        ;;
    4)
        echo -e "\n${BLUE}Container Logs:${NC}"
        docker ps --filter "name=$TEST_PREFIX" --format "{{.Names}}" | while read container; do
            echo -e "\n${YELLOW}=== $container ===${NC}"
            docker logs --tail 20 "$container" 2>&1
        done
        ;;
    5)
        # Clean up everything
        ;;
    6)
        echo -e "\n${GREEN}Environment preserved for inspection${NC}"
        echo -e "To clean up later, run:"
        echo -e "  ${BLUE}docker rm -f \$(docker ps -a --filter name=$TEST_PREFIX -q)${NC}"
        echo -e "  ${BLUE}rm -rf $TEST_VAULT $TEST_CONFIG${NC}"
        exit 0
        ;;
esac

# Cleanup prompt
echo -e "\n${RED}Clean up test environment?${NC}"
read -p "This will remove containers and test files [y/N]: " CLEANUP

if [[ "$CLEANUP" =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Cleaning up...${NC}"

    # Stop and remove test containers
    TEST_CONTAINERS=$(docker ps -a --filter "name=$TEST_PREFIX" -q)
    if [ -n "$TEST_CONTAINERS" ]; then
        echo "Stopping test containers..."
        docker rm -f $TEST_CONTAINERS 2>/dev/null || true
    fi

    # Remove test volumes
    TEST_VOLUMES=$(docker volume ls --filter "name=$TEST_PREFIX" -q)
    if [ -n "$TEST_VOLUMES" ]; then
        echo "Removing test volumes..."
        docker volume rm $TEST_VOLUMES 2>/dev/null || true
    fi

    # Remove test directories
    rm -rf "$TEST_VAULT" "$TEST_CONFIG"

    # Remove test image
    docker rmi thoth-setup:test 2>/dev/null || true

    echo -e "${GREEN}✓ Test environment cleaned up${NC}"
else
    echo -e "\n${YELLOW}Test environment preserved:${NC}"
    echo -e "  Vault: ${BLUE}$TEST_VAULT${NC}"
    echo -e "  Config: ${BLUE}$TEST_CONFIG${NC}"
    echo -e "  Containers: ${BLUE}docker ps --filter name=$TEST_PREFIX${NC}"
    echo ""
    echo "To clean up later:"
    echo -e "  ${BLUE}docker rm -f \$(docker ps -a --filter name=$TEST_PREFIX -q)${NC}"
    echo -e "  ${BLUE}docker volume rm \$(docker volume ls --filter name=$TEST_PREFIX -q)${NC}"
    echo -e "  ${BLUE}rm -rf $TEST_VAULT $TEST_CONFIG${NC}"
fi

echo -e "\n${GREEN}Test complete!${NC}"
