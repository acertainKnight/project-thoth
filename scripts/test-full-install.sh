#!/bin/bash
# Tests the new-user install pipeline end-to-end.
# Mirrors what install.sh does: build image, run wizard, verify config output.
# No services are started - the wizard is config-only.
# Auto-cleanup after test.

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="/home/nick-hallmark/Documents/python/project-thoth"
TEST_VAULT="/tmp/thoth-install-test-$$"
TEST_CONFIG="/tmp/thoth-install-config-$$"

# Parse arguments
KEEP_ENV=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --keep)
            KEEP_ENV=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--keep] [--help]"
            echo ""
            echo "Options:"
            echo "  --keep    Keep test vault after completion (don't auto-cleanup)"
            echo "  --help    Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Cleanup function
cleanup() {
    if [ "$KEEP_ENV" = true ]; then
        echo -e "\n${YELLOW}Keeping test environment (--keep flag set)${NC}"
        echo -e "  Vault:  ${BLUE}$TEST_VAULT${NC}"
        echo -e "  Config: ${BLUE}$TEST_CONFIG${NC}"
        return
    fi

    echo -e "\n${YELLOW}Cleaning up...${NC}"

    if [ -d "$TEST_VAULT" ]; then
        rm -rf "$TEST_VAULT" 2>/dev/null || sudo rm -rf "$TEST_VAULT"
        echo -e "  ${GREEN}✓ Removed test vault${NC}"
    fi

    if [ -d "$TEST_CONFIG" ]; then
        rm -rf "$TEST_CONFIG" 2>/dev/null || sudo rm -rf "$TEST_CONFIG"
        echo -e "  ${GREEN}✓ Removed test config${NC}"
    fi

    if docker rmi thoth-setup:test 2>/dev/null; then
        echo -e "  ${GREEN}✓ Removed test image${NC}"
    fi

    echo -e "${GREEN}✓ Cleanup complete${NC}"
}

trap cleanup EXIT INT TERM

# ── Header ────────────────────────────────────────────────────────
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Thoth Install Pipeline Test${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e ""
echo -e "Mirrors the real new-user flow (install.sh):"
echo -e "  1. Build setup Docker image"
echo -e "  2. Create a fake Obsidian vault"
echo -e "  3. Run wizard interactively (config only)"
echo -e "  4. Verify generated files (settings.json, .env)"
echo -e ""
echo -e "${YELLOW}No services are started - the wizard only configures.${NC}"
echo -e "${YELLOW}After the wizard, a real user would run 'thoth start'.${NC}"

read -p $'\nContinue? [Y/n]: ' CONTINUE
if [[ "$CONTINUE" =~ ^[Nn]$ ]]; then
    echo "Cancelled"
    exit 0
fi

# ── Step 1: Create fake Obsidian vault ────────────────────────────
echo -e "\n${GREEN}[1/3] Creating test vault...${NC}"
mkdir -p "$TEST_VAULT/_thoth"
mkdir -p "$TEST_VAULT/.obsidian"
mkdir -p "$TEST_CONFIG"

cat > "$TEST_VAULT/.obsidian/app.json" << 'EOF'
{
  "livePreview": true,
  "showLineNumber": true
}
EOF

cat > "$TEST_VAULT/.obsidian/workspace.json" << 'EOF'
{
  "main": { "id": "test-workspace", "type": "leaf" }
}
EOF

cat > "$TEST_VAULT/Welcome.md" << 'EOF'
# My Research Vault
A test vault for the Thoth installation wizard.
EOF

echo -e "  Vault: ${BLUE}$TEST_VAULT${NC}"
echo -e "  .obsidian: $([ -d "$TEST_VAULT/.obsidian" ] && echo "${GREEN}✓${NC}" || echo "${RED}✗${NC}")"

# ── Step 2: Build setup image ────────────────────────────────────
echo -e "\n${GREEN}[2/3] Building setup image...${NC}"
cd "$PROJECT_DIR"
docker build -f Dockerfile.setup -t thoth-setup:test . 2>&1 | tail -5
echo -e "  ${GREEN}✓ Image built${NC}"

# ── Step 3: Run wizard ───────────────────────────────────────────
echo -e "\n${GREEN}[3/3] Starting setup wizard...${NC}"
echo -e "  ${YELLOW}Walk through the wizard as a new user would.${NC}"
echo -e "  ${YELLOW}Vault path inside container: /vault${NC}\n"

docker run -it --rm \
  -v "$TEST_VAULT:/vault" \
  -v "$TEST_CONFIG:/root/.config/thoth" \
  -e OBSIDIAN_VAULT_PATH="/vault" \
  thoth-setup:test

# ── Verify results ───────────────────────────────────────────────
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Results${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

PASS=0
FAIL=0

# settings.json (new location: thoth/_thoth/, legacy: _thoth/)
if [ -f "$TEST_VAULT/thoth/_thoth/settings.json" ]; then
    SETTINGS_PATH="$TEST_VAULT/thoth/_thoth/settings.json"
    echo -e "  settings.json:  ${GREEN}✓ Created${NC}"
    PASS=$((PASS+1))
elif [ -f "$TEST_VAULT/_thoth/settings.json" ]; then
    SETTINGS_PATH="$TEST_VAULT/_thoth/settings.json"
    echo -e "  settings.json:  ${GREEN}✓ Created (legacy path)${NC}"
    PASS=$((PASS+1))
else
    SETTINGS_PATH=""
    echo -e "  settings.json:  ${RED}✗ Missing${NC}"
    FAIL=$((FAIL+1))
fi

# .env (could be in vault/thoth/_thoth, vault/_thoth, or config dir)
# Optional for remote deployments since keys live on the server
if [ -f "$TEST_VAULT/thoth/_thoth/.env" ] || [ -f "$TEST_VAULT/_thoth/.env" ] || [ -f "$TEST_CONFIG/.env" ]; then
    echo -e "  .env:           ${GREEN}✓ Created${NC}"
    PASS=$((PASS+1))
else
    # Detect remote deployment: baseUrl is NOT localhost
    IS_REMOTE=false
    if [ -n "$SETTINGS_PATH" ]; then
        BASE_URL=$(python3 -c "import json; d=json.load(open('$SETTINGS_PATH')); print(d.get('servers',{}).get('api',{}).get('baseUrl',''))" 2>/dev/null)
        if [ -n "$BASE_URL" ] && [[ "$BASE_URL" != *"localhost"* ]] && [[ "$BASE_URL" != *"127.0.0.1"* ]]; then
            IS_REMOTE=true
        fi
    fi

    if [ "$IS_REMOTE" = true ]; then
        echo -e "  .env:           ${YELLOW}– Skipped (remote deployment, keys on server)${NC}"
    else
        echo -e "  .env:           ${RED}✗ Missing${NC}"
        FAIL=$((FAIL+1))
    fi
fi

# Plugin (optional - depends on wizard screen)
if [ -d "$TEST_VAULT/.obsidian/plugins/thoth-obsidian" ] || [ -d "$TEST_VAULT/.obsidian/plugins/thoth" ]; then
    echo -e "  Plugin:         ${GREEN}✓ Installed${NC}"
    PASS=$((PASS+1))
else
    echo -e "  Plugin:         ${YELLOW}– Not installed (optional)${NC}"
fi

# Workspace dirs (new: thoth/_thoth/, legacy: _thoth/)
if [ -d "$TEST_VAULT/thoth/_thoth/data" ] || [ -d "$TEST_VAULT/thoth/_thoth/logs" ] || \
   [ -d "$TEST_VAULT/_thoth/data" ] || [ -d "$TEST_VAULT/_thoth/logs" ]; then
    echo -e "  Workspace dirs: ${GREEN}✓ Created${NC}"
    PASS=$((PASS+1))
else
    echo -e "  Workspace dirs: ${YELLOW}– Not created (optional)${NC}"
fi

# User-facing directories
if [ -d "$TEST_VAULT/thoth/papers/pdfs" ] || [ -d "$TEST_VAULT/thoth/notes" ]; then
    echo -e "  Content dirs:   ${GREEN}✓ Created (thoth/papers/, thoth/notes/)${NC}"
    PASS=$((PASS+1))
else
    echo -e "  Content dirs:   ${YELLOW}– Not created (optional)${NC}"
fi

# Show generated config (redact API keys in output only)
if [ -n "$SETTINGS_PATH" ] && [ -f "$SETTINGS_PATH" ]; then
    echo -e "\n${BLUE}Generated settings.json:${NC}"
    python3 -c "
import json

with open('$SETTINGS_PATH') as f:
    data = json.load(f)

# Keys in settings are fine - only redact for console display
KEY_FIELDS = {'openaiKey', 'anthropicKey', 'openrouterKey', 'googleApiKey',
              'mistralKey', 'lettaApiKey'}

def redact(obj, parent_key=''):
    if isinstance(obj, dict):
        return {k: redact(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str) and parent_key in KEY_FIELDS and len(obj) > 8:
        return obj[:6] + '***' + obj[-4:]
    return obj

print(json.dumps(redact(data), indent=2))
" 2>/dev/null || cat "$TEST_VAULT/_thoth/settings.json"
fi

# ── Summary ──────────────────────────────────────────────────────
echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}  ✓ Install pipeline PASSED ($PASS checks passed)${NC}"
else
    echo -e "${RED}  ✗ Install pipeline FAILED ($FAIL failures, $PASS passed)${NC}"
fi
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

echo -e "\n${YELLOW}Cleaning up in 5 seconds... (Ctrl+C to inspect manually)${NC}"
sleep 5

echo -e "\n${GREEN}Test complete!${NC}"
# Cleanup happens via trap
