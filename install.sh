#!/bin/bash
set -e

# Thoth Easy Installer
# No Python knowledge required - automatically chooses best installation method
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/acertainKnight/project-thoth/main/install.sh | bash
#
# Options (pass after `bash -s --`):
#   --version <ver>   Install a specific version (e.g., 0.3.0, 0.3.0-alpha.2)
#   --alpha           Install the latest alpha/pre-release
#   --nightly         Install the latest nightly build (from main)
#   --list            List available releases and exit
#   (no flags)        Install the latest stable release

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

GITHUB_REPO="acertainKnight/project-thoth"
INSTALL_CHANNEL="stable"
INSTALL_VERSION=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --version)
            INSTALL_VERSION="$2"
            INSTALL_CHANNEL="specific"
            shift 2
            ;;
        --alpha)
            INSTALL_CHANNEL="alpha"
            shift
            ;;
        --nightly)
            INSTALL_CHANNEL="nightly"
            shift
            ;;
        --list)
            INSTALL_CHANNEL="list"
            shift
            ;;
        *)
            shift
            ;;
    esac
done

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

# Function to check Python version (3.12 required)
check_python_version() {
    if command_exists python3; then
        version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -eq 3 ] && [ "$minor" -eq 12 ]; then
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

# ── Version Resolution ──────────────────────────────────────────────────────

resolve_version() {
    local api_url="https://api.github.com/repos/${GITHUB_REPO}/releases"

    case "$INSTALL_CHANNEL" in
        list)
            echo -e "${BLUE}Available Thoth releases:${NC}\n"
            echo -e "${GREEN}Stable releases:${NC}"
            curl -fsSL "${api_url}" 2>/dev/null \
                | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' \
                | grep -v 'nightly\|alpha\|beta\|rc' \
                | head -5 \
                | while read -r tag; do echo "  $tag"; done
            echo ""
            echo -e "${YELLOW}Pre-releases (alpha/beta):${NC}"
            curl -fsSL "${api_url}" 2>/dev/null \
                | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' \
                | grep -E 'alpha|beta|rc' \
                | head -5 \
                | while read -r tag; do echo "  $tag"; done
            echo ""
            echo -e "${CYAN}Nightly:${NC}"
            if curl -fsSL "${api_url}/tags/nightly" >/dev/null 2>&1; then
                echo "  nightly (rolling, built from latest main)"
            else
                echo "  (no nightly release found)"
            fi
            echo ""
            echo -e "Install a specific version with:"
            echo -e "  ${BLUE}curl -fsSL ... | bash -s -- --version 0.3.0${NC}"
            exit 0
            ;;

        stable)
            echo -e "${BLUE}Resolving latest stable release...${NC}"
            RESOLVED_TAG=$(curl -fsSL "${api_url}/latest" 2>/dev/null \
                | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' \
                | head -1)
            if [ -z "$RESOLVED_TAG" ]; then
                echo -e "${YELLOW}No stable release found. Falling back to main branch.${NC}"
                RESOLVED_TAG=""
                RESOLVED_REF="main"
            else
                echo -e "${GREEN}Found stable release: ${RESOLVED_TAG}${NC}"
                RESOLVED_REF="$RESOLVED_TAG"
            fi
            ;;

        alpha)
            echo -e "${BLUE}Resolving latest alpha/pre-release...${NC}"
            RESOLVED_TAG=$(curl -fsSL "${api_url}" 2>/dev/null \
                | sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' \
                | grep -v 'nightly' \
                | head -1)
            if [ -z "$RESOLVED_TAG" ]; then
                echo -e "${YELLOW}No pre-release found. Falling back to main branch.${NC}"
                RESOLVED_TAG=""
                RESOLVED_REF="main"
            else
                echo -e "${GREEN}Found pre-release: ${RESOLVED_TAG}${NC}"
                RESOLVED_REF="$RESOLVED_TAG"
            fi
            ;;

        nightly)
            echo -e "${BLUE}Using nightly build (latest main)...${NC}"
            RESOLVED_TAG="nightly"
            RESOLVED_REF="main"
            echo -e "${GREEN}Channel: nightly${NC}"
            ;;

        specific)
            echo -e "${BLUE}Using specified version: ${INSTALL_VERSION}${NC}"
            # Normalize: add 'v' prefix if missing
            if [[ "$INSTALL_VERSION" != v* ]]; then
                RESOLVED_TAG="v${INSTALL_VERSION}"
            else
                RESOLVED_TAG="${INSTALL_VERSION}"
            fi
            RESOLVED_REF="$RESOLVED_TAG"
            # Verify the tag exists
            if ! curl -fsSL "${api_url}/tags/${RESOLVED_TAG}" >/dev/null 2>&1; then
                echo -e "${YELLOW}Warning: Release ${RESOLVED_TAG} not found on GitHub.${NC}"
                echo -e "${YELLOW}Will attempt to use git tag directly.${NC}"
            else
                echo -e "${GREEN}Found release: ${RESOLVED_TAG}${NC}"
            fi
            ;;
    esac
}

resolve_version

# Determine Docker image tag based on channel
get_docker_image_tag() {
    case "$INSTALL_CHANNEL" in
        stable)
            echo "setup"
            ;;
        alpha)
            echo "setup"
            ;;
        nightly)
            echo "setup-nightly"
            ;;
        specific)
            # For specific versions, try version-specific tag, fall back to setup
            echo "setup"
            ;;
    esac
}

DOCKER_IMAGE_TAG=$(get_docker_image_tag)

echo ""

# Detect best installation method
echo -e "${BLUE}Detecting best installation method...${NC}\n"

# Check for Docker first (preferred for non-developers)
# Verify both the CLI exists AND the daemon is running
if command_exists docker && docker info >/dev/null 2>&1; then
    echo -e "${GREEN}✓ Docker detected and running${NC}"
    echo -e "${YELLOW}Installing via Docker (no Python required)...${NC}\n"

    # Determine current directory or clone repo
    if [ -f "Dockerfile.setup" ]; then
        PROJECT_ROOT="$(pwd)"
        echo -e "${GREEN}✓ Already in project directory${NC}"
        # Checkout the resolved ref if specified
        if [ -n "$RESOLVED_REF" ] && [ "$RESOLVED_REF" != "main" ]; then
            echo -e "${BLUE}Checking out ${RESOLVED_REF}...${NC}"
            git fetch --tags 2>/dev/null || true
            git checkout "$RESOLVED_REF" 2>/dev/null || echo -e "${YELLOW}Could not checkout ${RESOLVED_REF}, using current branch${NC}"
        fi
    else
        CLONE_DIR="${HOME}/thoth"
        if [ -d "$CLONE_DIR" ]; then
            echo -e "${YELLOW}Directory $CLONE_DIR already exists. Updating...${NC}"
            cd "$CLONE_DIR"
            git fetch --all --tags 2>/dev/null || true
            if [ -n "$RESOLVED_REF" ] && [ "$RESOLVED_REF" != "main" ]; then
                git checkout "$RESOLVED_REF" 2>/dev/null || echo -e "${YELLOW}Could not checkout ${RESOLVED_REF}${NC}"
            else
                git pull origin main 2>/dev/null || true
            fi
        else
            echo "Cloning Thoth repository..."
            if [ -n "$RESOLVED_REF" ] && [ "$RESOLVED_REF" != "main" ]; then
                git clone --branch "$RESOLVED_REF" https://github.com/${GITHUB_REPO}.git "$CLONE_DIR" 2>/dev/null \
                    || git clone https://github.com/${GITHUB_REPO}.git "$CLONE_DIR"
            else
                git clone https://github.com/${GITHUB_REPO}.git "$CLONE_DIR"
            fi
            cd "$CLONE_DIR"
            echo -e "${GREEN}✓ Repository cloned to $CLONE_DIR${NC}"
        fi
        PROJECT_ROOT="$CLONE_DIR"
    fi

    echo -e "${CYAN}Channel: ${INSTALL_CHANNEL}${NC}"
    [ -n "$RESOLVED_TAG" ] && echo -e "${CYAN}Version: ${RESOLVED_TAG}${NC}"

    # Try to pull pre-built image, fall back to local build
    SETUP_IMAGE=""
    echo -e "\n${BLUE}Preparing setup environment...${NC}"

    # Use timeout if available (GNU/Linux), otherwise pull without timeout (macOS)
    pull_cmd="docker pull ghcr.io/acertainknight/project-thoth:${DOCKER_IMAGE_TAG}"
    if command_exists timeout; then
        pull_cmd="timeout 300 ${pull_cmd}"
    fi
    if $pull_cmd 2>/dev/null; then
        echo -e "${GREEN}✓ Pre-built image downloaded (${DOCKER_IMAGE_TAG})${NC}"
        SETUP_IMAGE="ghcr.io/acertainknight/project-thoth:${DOCKER_IMAGE_TAG}"
    else
        echo -e "${YELLOW}Building setup image locally (first-time: ~5-10 min)...${NC}"
        docker build -f Dockerfile.setup -t thoth-setup:local .
        SETUP_IMAGE="thoth-setup:local"
        echo -e "${GREEN}✓ Build complete${NC}"
    fi

    # Install CLI wrapper first (so it's available after wizard)
    install_cli_to_path "$PROJECT_ROOT"

    # Run setup wizard in Docker
    # Mount ~/Documents to /root/Documents so Path.home()/'Documents' works
    # inside the container for vault auto-detection.
    # Pass THOTH_HOST_HOME so the wizard can translate container paths back
    # to host paths when saving config.
    DOCKER_ARGS=(
        -v "$HOME/.config/thoth:/root/.config/thoth"
        -v "$HOME/Documents:/root/Documents"
        -v /var/run/docker.sock:/var/run/docker.sock
        -e "THOTH_DOCKER_SETUP=1"
        -e "THOTH_HOST_HOME=$HOME"
        -e "OBSIDIAN_VAULT_PATH=${OBSIDIAN_VAULT_PATH:-}"
    )

    # Mount additional common vault locations if they exist
    for dir_name in Obsidian obsidian; do
        if [ -d "$HOME/$dir_name" ]; then
            DOCKER_ARGS+=(-v "$HOME/$dir_name:/root/$dir_name")
        fi
    done

    # When run via `curl | bash`, stdin is the pipe — not the user's terminal.
    # Re-attach /dev/tty so the interactive wizard can read user input.
    echo -e "\n${GREEN}Starting interactive setup wizard...${NC}\n"
    if [ -t 0 ]; then
        # stdin is already a terminal (script was run directly, not piped)
        docker run -it --rm "${DOCKER_ARGS[@]}" "$SETUP_IMAGE"
    elif [ -e /dev/tty ]; then
        # Piped execution (curl | bash) — reconnect to the real terminal
        docker run -it --rm "${DOCKER_ARGS[@]}" "$SETUP_IMAGE" < /dev/tty
    else
        # No TTY available at all (CI, headless) — run non-interactively
        echo -e "${YELLOW}No interactive terminal detected. Running setup in non-interactive mode.${NC}"
        echo -e "${YELLOW}You can run the setup wizard later with: thoth setup${NC}\n"
        docker run --rm "${DOCKER_ARGS[@]}" "$SETUP_IMAGE"
    fi

    echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ Thoth installation complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    echo -e "Quick start:"
    echo -e "  ${BLUE}thoth start${NC}   - Start services (~1-1.5GB RAM)"
    echo -e "  ${BLUE}thoth status${NC}  - Check what's running"
    echo -e "  ${BLUE}thoth stop${NC}    - Stop services (free RAM)"
    echo -e "  ${BLUE}thoth --help${NC}  - See all commands\n"

    exit 0

# No Docker (or daemon not running) — fall back to git clone + local Python setup
elif python_version=$(check_python_version); then
    # Warn if Docker CLI exists but daemon isn't running
    if command_exists docker && ! docker info >/dev/null 2>&1; then
        echo -e "${YELLOW}⚠ Docker CLI found but the Docker daemon is not running.${NC}"
        echo -e "${YELLOW}  Start Docker Desktop and re-run for the recommended experience.${NC}"
        echo -e "${YELLOW}  Falling back to local Python installation...${NC}\n"
    fi
    echo -e "${GREEN}✓ Python $python_version detected (no Docker)${NC}"
    echo -e "${YELLOW}Installing via git clone + local Python environment...${NC}\n"

    # Clone repo at the resolved ref
    CLONE_DIR="${HOME}/thoth"
    if [ -d "$CLONE_DIR" ]; then
        echo -e "${YELLOW}Directory $CLONE_DIR already exists. Updating...${NC}"
        cd "$CLONE_DIR"
        git fetch --all --tags 2>/dev/null || true
        if [ -n "$RESOLVED_REF" ] && [ "$RESOLVED_REF" != "main" ]; then
            git checkout "$RESOLVED_REF" 2>/dev/null || echo -e "${YELLOW}Could not checkout ${RESOLVED_REF}${NC}"
        else
            git pull origin main 2>/dev/null || true
        fi
    else
        if [ -n "$RESOLVED_REF" ] && [ "$RESOLVED_REF" != "main" ]; then
            git clone --branch "$RESOLVED_REF" "https://github.com/${GITHUB_REPO}.git" "$CLONE_DIR" 2>/dev/null \
                || git clone "https://github.com/${GITHUB_REPO}.git" "$CLONE_DIR"
        else
            git clone "https://github.com/${GITHUB_REPO}.git" "$CLONE_DIR"
        fi
        cd "$CLONE_DIR"
    fi
    PROJECT_ROOT="$CLONE_DIR"

    echo -e "${CYAN}Channel: ${INSTALL_CHANNEL}${NC}"
    [ -n "$RESOLVED_TAG" ] && echo -e "${CYAN}Version: ${RESOLVED_TAG}${NC}"

    # Set up Python environment with uv (preferred) or pip
    if command_exists uv; then
        echo -e "${GREEN}✓ uv detected — using uv for dependency management${NC}"
        uv venv
        uv sync
    else
        echo -e "${YELLOW}uv not found — using pip (slower)${NC}"
        python3 -m venv .venv
        source .venv/bin/activate
        pip install --upgrade pip
        pip install -e .
    fi

    # Install CLI wrapper
    install_cli_to_path "$PROJECT_ROOT"

    echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ Thoth installation complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"
    echo -e "${YELLOW}Note: Docker is recommended for the full experience.${NC}"
    echo -e "${YELLOW}Install Docker: https://docs.docker.com/engine/install/${NC}\n"
    echo -e "Quick start:"
    echo -e "  ${BLUE}thoth start${NC}   - Start services (requires Docker)"
    echo -e "  ${BLUE}thoth status${NC}  - Check what's running"
    echo -e "  ${BLUE}thoth --help${NC}  - See all commands\n"
    exit 0

else
    # No suitable method found
    echo -e "${RED}✗ No suitable installation method found${NC}\n"

    # Specific hint if Docker CLI exists but daemon is not running
    if command_exists docker && ! docker info >/dev/null 2>&1; then
        echo -e "${YELLOW}Docker is installed but not running!${NC}"
        echo -e "${YELLOW}Please open Docker Desktop and re-run this installer.${NC}\n"
    fi

    echo "Please install one of the following:"
    echo ""
    echo "1. Docker (Recommended - no Python required):"
    echo "   Linux: https://docs.docker.com/engine/install/"
    echo "   Mac: https://docs.docker.com/desktop/install/mac-install/"
    echo "   Windows: https://docs.docker.com/desktop/install/windows-install/"
    echo ""
    echo "2. Python 3.12 + Git (for local development):"
    echo "   https://www.python.org/downloads/"
    echo ""
    exit 1
fi
