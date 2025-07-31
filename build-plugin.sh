#!/bin/bash

# =============================================================================
# Thoth Obsidian Plugin Build and Deploy Script
# =============================================================================

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PLUGIN_DIR="obsidian-plugin/thoth-obsidian"

# Parse command line arguments
OBSIDIAN_VAULT=""
AUTO_DEPLOY=false

show_help() {
    echo -e "${BLUE}Thoth Obsidian Plugin Build & Deploy Script${NC}"
    echo "=============================================="
    echo ""
    echo "Usage: $0 [OPTIONS] [OBSIDIAN_VAULT_PATH]"
    echo ""
    echo "OPTIONS:"
    echo "  -h, --help              Show this help message"
    echo "  -d, --deploy            Auto-deploy after building"
    echo "  --vault PATH            Obsidian vault path"
    echo ""
    echo "EXAMPLES:"
    echo "  $0                                           # Just build"
    echo "  $0 -d \"/path/to/vault\"                      # Build and deploy"
    echo "  $0 --vault \"/path/to/vault\" --deploy        # Build and deploy"
    echo "  $0 ~/Documents/ObsidianVault                # Build and deploy to specified path"
    echo ""
    echo "COMMON VAULT LOCATIONS:"
    echo "  Linux/WSL: /mnt/c/Users/\$USER/Documents/Obsidian\\ Vault"
    echo "  macOS:     /Users/\$USER/Documents/Obsidian\\ Vault"
    echo "  Windows:   C:/Users/\$USER/Documents/Obsidian\\ Vault"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -d|--deploy)
            AUTO_DEPLOY=true
            shift
            ;;
        --vault)
            OBSIDIAN_VAULT="$2"
            AUTO_DEPLOY=true
            shift 2
            ;;
        -*)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
        *)
            # Assume it's the vault path
            OBSIDIAN_VAULT="$1"
            AUTO_DEPLOY=true
            shift
            ;;
    esac
done

echo -e "${YELLOW}🔧 Building Thoth Obsidian Plugin${NC}"
echo "========================================"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed. Please install Node.js first.${NC}"
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo -e "${RED}❌ npm is not installed. Please install npm first.${NC}"
    exit 1
fi

echo -e "${YELLOW}📦 Installing dependencies...${NC}"
cd "$PLUGIN_DIR"
npm install

echo -e "${YELLOW}🏗️  Building plugin...${NC}"
npm run build

echo -e "${GREEN}✅ Plugin built successfully!${NC}"

# Auto-deploy if requested
if [ "$AUTO_DEPLOY" = true ]; then
    if [ -z "$OBSIDIAN_VAULT" ]; then
        echo -e "${YELLOW}🔍 Auto-detecting Obsidian vault...${NC}"

        # Try to find Obsidian vault in common locations
        POSSIBLE_VAULTS=(
            "$HOME/Documents/Obsidian Vault"
            "$HOME/Documents/ObsidianVault"
            "$HOME/Documents/Obsidian"
            "$HOME/Obsidian Vault"
            "/mnt/c/Users/$USER/Documents/Obsidian Vault"
            "/mnt/c/Users/$USER/Documents/ObsidianVault"
        )

        for vault in "${POSSIBLE_VAULTS[@]}"; do
            if [ -d "$vault" ]; then
                OBSIDIAN_VAULT="$vault"
                echo -e "${GREEN}📁 Found Obsidian vault at: $vault${NC}"
                break
            fi
        done

        if [ -z "$OBSIDIAN_VAULT" ]; then
            echo -e "${RED}❌ Could not find Obsidian vault automatically.${NC}"
            echo -e "${YELLOW}Please specify the path:${NC}"
            echo "   $0 --vault \"/path/to/your/obsidian/vault\""
            exit 1
        fi
    fi

    # Verify vault exists
    if [ ! -d "$OBSIDIAN_VAULT" ]; then
        echo -e "${RED}❌ Obsidian vault not found at: $OBSIDIAN_VAULT${NC}"
        echo -e "${YELLOW}Please check the path and try again.${NC}"
        exit 1
    fi

    echo -e "${YELLOW}🚀 Deploying plugin to Obsidian vault...${NC}"

    PLUGIN_DEST="$OBSIDIAN_VAULT/.obsidian/plugins/thoth-obsidian"

    # Create plugin directory
    echo "Creating plugin directory: $PLUGIN_DEST"
    mkdir -p "$PLUGIN_DEST"

    # Copy plugin files
    echo "Copying plugin files..."
    cp -r dist/* "$PLUGIN_DEST/"
    cp manifest.json "$PLUGIN_DEST/"
    cp styles.css "$PLUGIN_DEST/" 2>/dev/null || true

    echo -e "${GREEN}✅ Plugin deployed successfully!${NC}"
    echo -e "${YELLOW}📍 Plugin location: $PLUGIN_DEST${NC}"
    echo ""
    echo -e "${BLUE}🎯 Next Steps:${NC}"
    echo "1. Open Obsidian"
    echo "2. Go to Settings → Community plugins"
    echo "3. Enable 'Thoth Research Assistant'"
    echo "4. Start the Thoth API server: make start-api"
    echo ""
    echo -e "${GREEN}🎉 Ready to test your enhanced plugin!${NC}"
else
    echo ""
    echo -e "${YELLOW}📁 Build output location:${NC}"
    echo "   $(pwd)/dist/"
    echo ""
    echo -e "${YELLOW}🚀 To deploy the plugin:${NC}"
    echo "   $0 --deploy --vault \"/path/to/your/vault\""
    echo "   Or: make deploy-plugin OBSIDIAN_VAULT=\"/path/to/your/vault\""
    echo ""
    echo -e "${YELLOW}📋 Built files:${NC}"
    ls -la dist/ 2>/dev/null || echo "   dist/ folder not found - build may have failed"
fi
