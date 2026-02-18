#!/bin/bash
set -e

# Thoth Easy Installer
# Docker-based installation for the Thoth AI Research Assistant
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
#
# Prerequisites:
#   - Docker installed and running
#   - Obsidian installed (will be prompted to download if missing)

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

# Function to install thoth CLI to PATH
install_cli_to_path() {
    local project_root="$1"

    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"

    # Add to PATH via shell rc files if not already there
    for rc in ~/.bashrc ~/.zshrc ~/.profile; do
        if [ -f "$rc" ] && ! grep -q '.local/bin' "$rc"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
        fi
    done

    # On macOS the default shell is zsh; create ~/.zshrc if it doesn't exist
    # so the PATH export is picked up by new terminals
    if [ "$(uname)" = "Darwin" ] && [ ! -f "$HOME/.zshrc" ]; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' > "$HOME/.zshrc"
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
export THOTH_IMAGE_TAG="${THOTH_IMAGE_TAG:-latest}"

case "$1" in
    start)
        echo "🚀 Starting Thoth services..."
        echo "   Image tag: ${THOTH_IMAGE_TAG}"
        cd "$PROJECT_ROOT"

        if [ ! -f ".env" ] || ! grep -q 'OBSIDIAN_VAULT_PATH' .env 2>/dev/null; then
            echo "❌ .env file missing or OBSIDIAN_VAULT_PATH not set."
            echo "   Run the setup wizard first, or create .env from .env.example:"
            echo "   cp .env.example .env && edit .env"
            exit 1
        fi

        if [ -f "$HOME/.config/thoth/settings.json" ]; then
            LETTA_MODE=$(grep -o '"mode": *"[^"]*"' "$HOME/.config/thoth/settings.json" 2>/dev/null | cut -d'"' -f4 || echo "self-hosted")
        else
            LETTA_MODE="self-hosted"
        fi

        if [ "$LETTA_MODE" = "self-hosted" ]; then
            echo "  Starting Letta (self-hosted mode)..."
            docker compose -f docker-compose.letta.yml up -d 2>/dev/null || true
            sleep 3
        fi

        echo "  Pulling Thoth images (${THOTH_IMAGE_TAG})..."
        docker compose -f docker-compose.dev.yml --profile microservices pull 2>/dev/null || {
            echo "  (Pre-built images not available, building locally...)"
        }

        echo "  Starting Thoth containers..."
        docker compose -f docker-compose.dev.yml --profile microservices up -d

        echo "✅ Thoth is running!"
        [ "$LETTA_MODE" = "cloud" ] && echo "   Letta: Cloud" || echo "   Letta: localhost:8283"
        echo "   API: http://localhost:8000"
        echo "   MCP: http://localhost:8082"
        ;;

    stop)
        echo "🛑 Stopping Thoth services..."
        cd "$PROJECT_ROOT"
        docker compose -f docker-compose.dev.yml --profile microservices stop

        echo "✅ Thoth stopped (RAM freed)"
        echo ""
        echo "   Tip: Letta containers still running (if self-hosted)"
        echo "   To stop Letta: docker compose -f docker-compose.letta.yml stop"
        ;;

    restart)
        "$0" stop
        sleep 2
        "$0" start
        ;;

    status)
        cd "$PROJECT_ROOT"
        echo "📊 Thoth Service Status (image tag: ${THOTH_IMAGE_TAG}):"
        docker compose -f docker-compose.dev.yml --profile microservices ps
        echo ""
        echo "Letta Status:"
        docker compose -f docker-compose.letta.yml ps 2>/dev/null || echo "  (Not using self-hosted Letta)"
        ;;

    logs)
        cd "$PROJECT_ROOT"
        docker compose -f docker-compose.dev.yml --profile microservices logs -f "${@:2}"
        ;;

    update)
        cd "$PROJECT_ROOT"
        CHANNEL="stable"
        NEW_TAG=""
        shift
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --nightly)  CHANNEL="nightly"; NEW_TAG="nightly"; shift ;;
                --alpha)    CHANNEL="alpha"; NEW_TAG="alpha"; shift ;;
                --version)  CHANNEL="specific"; NEW_TAG="${2#v}"; shift 2 ;;
                --stable)   CHANNEL="stable"; NEW_TAG="latest"; shift ;;
                *)          shift ;;
            esac
        done

        if [ -z "$NEW_TAG" ]; then
            NEW_TAG="latest"
        fi

        echo "⬆️  Updating Thoth (${CHANNEL}: ${NEW_TAG})..."

        case "$CHANNEL" in
            nightly)
                git fetch origin main
                git checkout main 2>/dev/null || true
                git pull origin main
                ;;
            specific)
                git fetch --tags
                local_tag="v${NEW_TAG}"
                git checkout "$local_tag" 2>/dev/null || {
                    echo "❌ Version ${local_tag} not found"; exit 1
                }
                ;;
            alpha)
                git fetch --tags
                ALPHA_TAG=$(git tag -l '*alpha*' --sort=-v:refname | head -1)
                if [ -n "$ALPHA_TAG" ]; then
                    git checkout "$ALPHA_TAG"
                    NEW_TAG="${ALPHA_TAG#v}"
                else
                    echo "❌ No alpha release found"; exit 1
                fi
                ;;
            *)
                git pull origin main
                ;;
        esac

        export THOTH_IMAGE_TAG="$NEW_TAG"
        sed -i.bak "s/^THOTH_IMAGE_TAG=.*/THOTH_IMAGE_TAG=\"${NEW_TAG}\"/" "$HOME/.config/thoth/cli.conf" 2>/dev/null \
            || echo "THOTH_IMAGE_TAG=\"${NEW_TAG}\"" >> "$HOME/.config/thoth/cli.conf"
        rm -f "$HOME/.config/thoth/cli.conf.bak"

        echo "  Pulling images (${NEW_TAG})..."
        docker compose -f docker-compose.dev.yml --profile microservices pull 2>/dev/null || true
        "$0" restart
        echo "✅ Updated to ${CHANNEL} (${NEW_TAG})"
        ;;

    version)
        echo "Thoth version info:"
        echo "  Image tag: ${THOTH_IMAGE_TAG}"
        cd "$PROJECT_ROOT"
        if git describe --tags --exact-match HEAD 2>/dev/null; then
            echo "  Git tag:   $(git describe --tags --exact-match HEAD)"
        else
            echo "  Git ref:   $(git rev-parse --short HEAD) ($(git rev-parse --abbrev-ref HEAD))"
        fi
        ;;

    *)
        if [ -f "$PROJECT_ROOT/src/thoth/__main__.py" ]; then
            cd "$PROJECT_ROOT"
            python3 -m thoth "$@"
        else
            echo "Thoth Service Manager"
            echo ""
            echo "Usage: thoth <command> [options]"
            echo ""
            echo "Commands:"
            echo "  start      Start Thoth services"
            echo "  stop       Stop Thoth services"
            echo "  restart    Restart all services"
            echo "  status     Show service status"
            echo "  logs       View service logs"
            echo "  update     Update to latest stable version"
            echo "  version    Show installed version info"
            echo ""
            echo "Update options:"
            echo "  thoth update              Update to latest stable"
            echo "  thoth update --nightly    Switch to nightly builds"
            echo "  thoth update --alpha      Switch to latest alpha"
            echo "  thoth update --version X  Switch to specific version"
            echo "  thoth update --stable     Switch back to stable"
            echo ""
            echo "Run 'thoth setup' to configure Thoth"
        fi
        ;;
esac
EOFCLI

    chmod +x "$INSTALL_DIR/thoth"

    # Save project root and image tag
    mkdir -p "$HOME/.config/thoth"
    cat > "$HOME/.config/thoth/cli.conf" << EOFCONF
THOTH_PROJECT_ROOT="$project_root"
THOTH_IMAGE_TAG="${THOTH_IMAGE_TAG:-latest}"
EOFCONF

    echo -e "${GREEN}✓ Installed 'thoth' command to $INSTALL_DIR${NC}"

    # Check if in PATH and tell user how to activate
    if ! echo "$PATH" | grep -q "$INSTALL_DIR"; then
        # Detect the user's shell for the correct rc file
        case "${SHELL:-/bin/bash}" in
            */zsh)  RC_FILE="~/.zshrc" ;;
            */bash) RC_FILE="~/.bashrc" ;;
            *)      RC_FILE="~/.profile" ;;
        esac
        echo -e "${YELLOW}Note: Please restart your terminal or run:${NC}"
        echo -e "  ${BLUE}source ${RC_FILE}${NC}"
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

# Determine Docker image tag for the setup container
get_docker_image_tag() {
    case "$INSTALL_CHANNEL" in
        nightly)  echo "setup-nightly" ;;
        *)        echo "setup" ;;
    esac
}

# Determine image tag for the dev microservice images
get_dev_image_tag() {
    case "$INSTALL_CHANNEL" in
        nightly)   echo "nightly" ;;
        alpha)     echo "alpha" ;;
        specific)
            local tag="${RESOLVED_TAG#v}"
            echo "$tag"
            ;;
        *)         echo "latest" ;;
    esac
}

DOCKER_IMAGE_TAG=$(get_docker_image_tag)
THOTH_IMAGE_TAG=$(get_dev_image_tag)
export THOTH_IMAGE_TAG

echo -e "${CYAN}Channel: ${INSTALL_CHANNEL}${NC}"
[ -n "$RESOLVED_TAG" ] && echo -e "${CYAN}Version: ${RESOLVED_TAG}${NC}"
echo -e "${CYAN}Image tag: ${THOTH_IMAGE_TAG}${NC}"
echo ""

# ── Installation ────────────────────────────────────────────────────────────

echo -e "${BLUE}Checking prerequisites...${NC}\n"

# Docker is required - check both CLI and daemon
if ! command_exists docker; then
    echo -e "${RED}✗ Docker not found${NC}\n"
    echo "Thoth requires Docker to run. Please install Docker:"
    echo ""
    echo "  macOS:   https://docs.docker.com/desktop/install/mac-install/"
    echo "  Linux:   https://docs.docker.com/engine/install/"
    echo "  Windows: https://docs.docker.com/desktop/install/windows-install/"
    echo ""
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon not running${NC}\n"
    echo "Docker is installed but not running."
    echo "Please start Docker Desktop and try again."
    echo ""
    exit 1
fi

echo -e "${GREEN}✓ Docker detected and running${NC}"
echo -e "${YELLOW}Installing via Docker...${NC}\n"

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
        -v "$PROJECT_ROOT:/thoth-project"
        -e "THOTH_DOCKER_SETUP=1"
        -e "THOTH_HOST_HOME=$HOME"
        -e "THOTH_PROJECT_ROOT=/thoth-project"
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
    echo -e "${GREEN}✓ Thoth setup complete!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}\n"

    # Ensure .env.letta exists (Letta compose requires it)
    if [ ! -f "$PROJECT_ROOT/.env.letta" ]; then
        touch "$PROJECT_ROOT/.env.letta"
    fi

    # Offer to start services now
    echo -e "${BLUE}Would you like to start Thoth services now? (y/n)${NC}"
    if [ -t 0 ]; then
        read -r START_NOW
    elif [ -e /dev/tty ]; then
        read -r START_NOW < /dev/tty
    else
        START_NOW="n"
    fi

    if [ "$START_NOW" = "y" ] || [ "$START_NOW" = "Y" ]; then
        echo -e "\n${BLUE}Starting services (this may take a few minutes on first run)...${NC}\n"
        cd "$PROJECT_ROOT"
        export THOTH_IMAGE_TAG="${THOTH_IMAGE_TAG:-latest}"

        echo -e "  Starting Letta services..."
        docker compose -f docker-compose.letta.yml up -d 2>/dev/null || true
        sleep 3

        echo -e "  Pulling Thoth images (${THOTH_IMAGE_TAG})..."
        docker compose -f docker-compose.dev.yml --profile microservices pull 2>/dev/null || true

        echo -e "  Starting Thoth..."
        docker compose -f docker-compose.dev.yml --profile microservices up -d

        echo -e "\n${GREEN}✓ Thoth is running!${NC}"
        echo -e "  API: http://localhost:8000"
        echo -e "  MCP: http://localhost:8082"
        echo -e "  Letta: http://localhost:8283\n"
    else
        echo -e "\nStart services any time with:"
        echo -e "  ${BLUE}thoth start${NC}\n"
    fi

    echo -e "Commands:"
    echo -e "  ${BLUE}thoth start${NC}   - Start services (~4GB RAM)"
    echo -e "  ${BLUE}thoth status${NC}  - Check what's running"
    echo -e "  ${BLUE}thoth stop${NC}    - Stop services (free RAM)"
    echo -e "  ${BLUE}thoth --help${NC}  - See all commands\n"

    exit 0
