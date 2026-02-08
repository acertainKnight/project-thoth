#!/bin/bash
# Test Thoth installation as a real user would experience it
# This creates a completely isolated test environment

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
TEST_USER="thoth-test-user"
TEST_HOME="/tmp/thoth-test-home-$$"
TEST_VAULT="$TEST_HOME/Documents/MyResearchVault"
PROJECT_DIR="/home/nick-hallmark/Documents/python/project-thoth"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Thoth User Installation Test${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

# Choose test mode
echo "Select test mode:"
echo "  1) Docker-based install (simulates user with Docker only)"
echo "  2) Python-based install (simulates user with Python)"
echo "  3) Full clean install (clones repo like fresh user)"
echo ""
read -p "Choose [1-3]: " TEST_MODE

echo ""
echo -e "${GREEN}Creating isolated test environment...${NC}"

# Create isolated test environment
mkdir -p "$TEST_HOME"
mkdir -p "$TEST_VAULT/thoth/_thoth"

echo -e "${GREEN}✓ Created test home: $TEST_HOME${NC}"
echo -e "${GREEN}✓ Created test vault: $TEST_VAULT${NC}"

# Set up isolated environment
export HOME="$TEST_HOME"
export USER="$TEST_USER"
export OBSIDIAN_VAULT_PATH="$TEST_VAULT"
export THOTH_DISABLE_AUTODETECT=1

# Create minimal .bashrc for test user
cat > "$TEST_HOME/.bashrc" << 'EOF'
export PATH="$HOME/.local/bin:$PATH"
PS1='\[\033[01;32m\]test-user\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '
EOF

echo ""
echo -e "${YELLOW}Test environment ready:${NC}"
echo -e "  Test Home: ${BLUE}$TEST_HOME${NC}"
echo -e "  Test Vault: ${BLUE}$TEST_VAULT${NC}"
echo -e "  Docker: $(command -v docker &>/dev/null && echo '✓ Available' || echo '✗ Not found')"
echo -e "  Python: $(python3 --version 2>/dev/null || echo '✗ Not found')"

echo ""
read -p "Press Enter to start installation wizard..."

# Run installation based on chosen mode
case $TEST_MODE in
    1)
        echo -e "\n${GREEN}Starting Docker-based installation...${NC}\n"
        cd "$PROJECT_DIR"

        # Build setup image if needed
        if ! docker images | grep -q "thoth-setup"; then
            echo "Building setup image..."
            docker build -f Dockerfile.setup -t thoth-setup:test .
        fi

        # Run setup wizard in Docker with test environment
        docker run -it --rm \
            -v "$TEST_HOME/.config/thoth:/root/.config/thoth" \
            -v "$TEST_VAULT:/vault" \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -e OBSIDIAN_VAULT_PATH="/vault" \
            -e HOME="/root" \
            thoth-setup:test
        ;;

    2)
        echo -e "\n${GREEN}Starting Python-based installation...${NC}\n"

        # Create isolated venv
        python3 -m venv "$TEST_HOME/.thoth-venv"
        source "$TEST_HOME/.thoth-venv/bin/activate"

        # Install from local development
        cd "$PROJECT_DIR"
        pip install --quiet --upgrade pip
        pip install -e .

        # Run setup wizard
        python -m thoth setup-wizard
        ;;

    3)
        echo -e "\n${GREEN}Starting fresh clone installation...${NC}\n"

        # Clone to test directory
        TEST_CLONE="$TEST_HOME/project-thoth"
        git clone "$PROJECT_DIR" "$TEST_CLONE"
        cd "$TEST_CLONE"

        # Run install script
        bash install.sh
        ;;

    *)
        echo -e "${RED}Invalid option${NC}"
        exit 1
        ;;
esac

# Show results
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Installation Test Complete!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

echo "Test environment details:"
echo -e "  Config: ${BLUE}$TEST_HOME/.config/thoth/${NC}"
echo -e "  Vault: ${BLUE}$TEST_VAULT${NC}"
echo ""

# Offer to inspect results
echo "What would you like to do?"
echo "  1) View generated settings"
echo "  2) Explore test environment"
echo "  3) Test 'thoth start' command"
echo "  4) Clean up and exit"
echo ""
read -p "Choose [1-4]: " ACTION

case $ACTION in
    1)
        echo -e "\n${BLUE}Generated Settings:${NC}"
        find "$TEST_HOME/.config/thoth" -name "*.json" -exec echo -e "\n--- {} ---" \; -exec cat {} \;
        ;;
    2)
        echo -e "\n${BLUE}Opening test environment shell...${NC}"
        echo -e "${YELLOW}Type 'exit' to return${NC}\n"
        cd "$TEST_HOME"
        bash --rcfile "$TEST_HOME/.bashrc"
        ;;
    3)
        echo -e "\n${BLUE}Testing thoth command...${NC}"
        if [ -f "$TEST_HOME/.local/bin/thoth" ]; then
            "$TEST_HOME/.local/bin/thoth" status || true
        else
            echo "thoth command not found (expected for some test modes)"
        fi
        ;;
esac

# Cleanup prompt
echo ""
read -p "Clean up test environment? [y/N]: " CLEANUP
if [[ "$CLEANUP" =~ ^[Yy]$ ]]; then
    echo -e "\n${YELLOW}Cleaning up...${NC}"

    # Stop any test containers
    docker ps -a | grep thoth-test | awk '{print $1}' | xargs -r docker rm -f 2>/dev/null || true

    # Remove test directory
    rm -rf "$TEST_HOME"

    echo -e "${GREEN}✓ Test environment cleaned up${NC}"
else
    echo -e "\n${YELLOW}Test environment preserved:${NC}"
    echo -e "  ${BLUE}$TEST_HOME${NC}"
    echo ""
    echo "To clean up later, run:"
    echo -e "  ${BLUE}rm -rf $TEST_HOME${NC}"
fi

echo ""
echo -e "${GREEN}Test complete!${NC}"
