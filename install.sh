#!/bin/bash
set -e

# Thoth Easy Installer
# No Python knowledge required - automatically chooses best installation method

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
cat << "EOF"
  _____ _           _   _
 |_   _| |__   ___ | |_| |__
   | | | '_ \ / _ \| __| '_ \
   | | | | | | (_) | |_| | | |
   |_| |_| |_|\___/ \__|_| |_|

 AI-Powered Research Assistant
EOF
echo -e "${NC}"

echo -e "${GREEN}Starting Thoth installation...${NC}\n"

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ] && [ "$minor" -le 12 ]; then
            echo "$version"
            return 0
        fi
    fi
    return 1
}

# Function to install thoth CLI to PATH
install_cli_to_path() {
    local project_root="$1"
    
    # Determine install location
    if [ -d "$HOME/.local/bin" ]; then
        INSTALL_DIR="$HOME/.local/bin"
    else
        mkdir -p "$HOME/.local/bin"
        INSTALL_DIR="$HOME/.local/bin"
        
        # Add to PATH if not already there
        for rc in ~/.bashrc ~/.zshrc ~/.profile; do
            if [ -f "$rc" ] && ! grep -q ".local/bin" "$rc"; then
                echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
            fi
        done
    fi
    
    # Create thoth CLI wrapper
    cat > "$INSTALL_DIR/thoth" << 'EOFCLI'
#!/bin/bash
# Thoth CLI wrapper

set -e

THOTH_CONFIG="$HOME/.config/thoth/cli.conf"
if [ -f "$THOTH_CONFIG" ]; then
    source "$THOTH_CONFIG"
fi

PROJECT_ROOT="${THOTH_PROJECT_ROOT:-$(pwd)}"

case "$1" in
    start)
        echo "🚀 Starting Thoth services..."
        cd "$PROJECT_ROOT"
        
        # Check Letta mode
        if [ -f "$HOME/.config/thoth/settings.json" ]; then
            LETTA_MODE=$(grep -o '"mode": *"[^"]*"' "$HOME/.config/thoth/settings.json" 2>/dev/null | cut -d'"' -f4 || echo "self-hosted")
        else
            LETTA_MODE="self-hosted"
        fi
        
        # Start Letta if self-hosted
        if [ "$LETTA_MODE" = "self-hosted" ]; then
            echo "  Starting Letta (self-hosted mode)..."
            docker compose -f docker-compose.letta.yml up -d 2>/dev/null || true
            sleep 3
        fi
        
        # Start Thoth services
        docker compose up -d
        
        echo "✅ Thoth is running!"
        [ "$LETTA_MODE" = "cloud" ] && echo "   Letta: Cloud" || echo "   Letta: localhost:8283"
        echo "   API: http://localhost:8000"
        echo "   MCP: http://localhost:8001"
        ;;
    
    stop)
        echo "🛑 Stopping Thoth services..."
        cd "$PROJECT_ROOT"
        docker compose stop
        
        echo "✅ Thoth stopped (RAM freed)"
        echo ""
        echo "💡 Tip: Letta containers still running (if self-hosted)"
        echo "   To stop Letta: docker compose -f docker-compose.letta.yml stop"
        ;;
    
    restart)
        "$0" stop
        sleep 2
        "$0" start
        ;;
    
    status)
        cd "$PROJECT_ROOT"
        echo "📊 Thoth Service Status:"
        docker compose ps
        echo ""
        echo "Letta Status:"
        docker compose -f docker-compose.letta.yml ps 2>/dev/null || echo "  (Not using self-hosted Letta)"
        ;;
    
    logs)
        cd "$PROJECT_ROOT"
        docker compose logs -f "${@:2}"
        ;;
    
    update)
        echo "⬆️  Updating Thoth..."
        cd "$PROJECT_ROOT"
        git pull origin main
        docker compose pull
        "$0" restart
        echo "✅ Updated to latest version"
        ;;
    
    *)
        # Forward to Python CLI if it exists, otherwise show help
        if [ -f "$PROJECT_ROOT/src/thoth/__main__.py" ]; then
            cd "$PROJECT_ROOT"
            python3 -m thoth "$@"
        else
            echo "Thoth Service Manager"
            echo ""
            echo "Usage: thoth <command> [options]"
            echo ""
            echo "Commands:"
            echo "  start     Start Thoth services"
            echo "  stop      Stop Thoth services"
            echo "  restart   Restart all services"
            echo "  status    Show service status"
            echo "  logs      View service logs"
            echo "  update    Update to latest version"
            echo ""
            echo "Run 'thoth setup' to configure Thoth"
        fi
        ;;
esac
EOFCLI
    
    chmod +x "$INSTALL_DIR/thoth"
    
    # Save project root
    mkdir -p "$HOME/.config/thoth"
    echo "THOTH_PROJECT_ROOT=\"$project_root\"" > "$HOME/.config/thoth/cli.conf"
    
    echo -e "${GREEN}✓ Installed 'thoth' command to $INSTALL_DIR${NC}"
    
    # Check if in PATH
    if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
        echo -e "${YELLOW}Note: Please restart your terminal or run:${NC}"
        echo -e "  ${BLUE}source ~/.bashrc${NC}  # or ~/.zshrc"
    fi
}

# Detect best installation method
echo -e "${BLUE}Detecting best installation method...${NC}\n"

# Check for Docker first (preferred for non-developers)
if command_exists docker; then
    echo -e "${GREEN}✓ Docker detected${NC}"
    echo -e "${YELLOW}Installing via Docker (no Python required)...${NC}\n"

    # Determine current directory or clone repo
    if [ -f "Dockerfile.setup" ]; then
        PROJECT_ROOT="$(pwd)"
        echo -e "${GREEN}✓ Already in project directory${NC}"
    else
        echo "Cloning Thoth repository..."
        INSTALL_DIR="${HOME}/thoth"
        git clone https://github.com/acertainKnight/project-thoth.git "$INSTALL_DIR"
        PROJECT_ROOT="$INSTALL_DIR"
        cd "$PROJECT_ROOT"
        echo -e "${GREEN}✓ Repository cloned to $PROJECT_ROOT${NC}"
    fi

    # Try to pull pre-built image, fall back to local build
    SETUP_IMAGE=""
    echo -e "\n${BLUE}Preparing setup environment...${NC}"
    
    if timeout 300 docker pull ghcr.io/acertainknight/project-thoth:setup 2>/dev/null; then
        echo -e "${GREEN}✓ Pre-built image downloaded${NC}"
        SETUP_IMAGE="ghcr.io/acertainknight/project-thoth:setup"
    else
        echo -e "${YELLOW}Building setup image locally (first-time: ~5-10 min)...${NC}"
        docker build -f Dockerfile.setup -t thoth-setup:local .
        SETUP_IMAGE="thoth-setup:local"
        echo -e "${GREEN}✓ Build complete${NC}"
    fi

    # Install CLI wrapper first (so it's available after wizard)
    install_cli_to_path "$PROJECT_ROOT"

    # Run setup wizard in Docker
    echo -e "\n${GREEN}Starting interactive setup wizard...${NC}\n"
    docker run -it --rm \
        -v ~/.config/thoth:/root/.config/thoth \
        -v ~/Documents:/documents \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -e OBSIDIAN_VAULT_PATH="${OBSIDIAN_VAULT_PATH:-}" \
        "$SETUP_IMAGE"

    echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ Thoth installation complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    echo -e "Quick start:"
    echo -e "  ${BLUE}thoth start${NC}   - Start services (~1-1.5GB RAM)"
    echo -e "  ${BLUE}thoth status${NC}  - Check what's running"
    echo -e "  ${BLUE}thoth stop${NC}    - Stop services (free RAM)"
    echo -e "  ${BLUE}thoth --help${NC}  - See all commands\n"

    exit 0

# Check for pipx (best for Python users)
elif command_exists pipx; then
    echo -e "${GREEN}✓ pipx detected${NC}"
    echo -e "${YELLOW}Installing via pipx...${NC}\n"

    pipx install project-thoth
    thoth setup

    echo -e "\n${GREEN}✓ Installation complete!${NC}"
    exit 0

# Check for Python 3.10+
elif python_version=$(check_python_version); then
    echo -e "${GREEN}✓ Python $python_version detected${NC}"
    echo -e "${YELLOW}Installing via pip in virtual environment...${NC}\n"

    # Create venv
    python3 -m venv ~/.thoth-venv
    source ~/.thoth-venv/bin/activate

    # Install Thoth
    pip install --upgrade pip
    pip install project-thoth

    # Run setup
    thoth setup

    # Create wrapper script
    mkdir -p ~/.local/bin
    cat > ~/.local/bin/thoth << 'WRAPPER'
#!/bin/bash
source ~/.thoth-venv/bin/activate
exec python -m thoth "$@"
WRAPPER
    chmod +x ~/.local/bin/thoth

    echo -e "\n${GREEN}✓ Installation complete!${NC}"
    echo -e "\nThoth command available: ${BLUE}thoth${NC}"
    exit 0

else
    # No suitable method found
    echo -e "${RED}✗ No suitable installation method found${NC}\n"
    echo "Please install one of the following:"
    echo ""
    echo "1. Docker (Recommended - no Python required):"
    echo "   Linux: https://docs.docker.com/engine/install/"
    echo "   Mac: https://docs.docker.com/desktop/install/mac-install/"
    echo "   Windows: https://docs.docker.com/desktop/install/windows-install/"
    echo ""
    echo "2. pipx (Easy Python package manager):"
    echo "   Ubuntu/Debian: sudo apt install pipx"
    echo "   macOS: brew install pipx"
    echo ""
    echo "3. Python 3.10, 3.11, or 3.12:"
    echo "   https://www.python.org/downloads/"
    echo ""
    exit 1
fi
