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
        if [ "$(echo "$version >= 3.10" | bc -l 2>/dev/null || echo 0)" -eq 1 ]; then
            echo "$version"
            return 0
        fi
    fi
    return 1
}

# Detect best installation method
echo -e "${BLUE}Detecting best installation method...${NC}\n"

# Check for Docker first (preferred for non-developers)
if command_exists docker && command_exists docker-compose; then
    echo -e "${GREEN}✓ Docker detected${NC}"
    echo -e "${YELLOW}Installing via Docker (no Python required)...${NC}\n"

    # Pull Thoth image
    echo "Pulling Thoth Docker image..."
    docker pull ghcr.io/yourusername/project-thoth:latest || {
        echo -e "${RED}Failed to pull Docker image. Building locally...${NC}"
        docker compose build
    }

    # Run setup wizard in Docker
    echo -e "\n${GREEN}Starting setup wizard...${NC}"
    docker run -it --rm \
        -v ~/.config/thoth:/root/.config/thoth \
        -v ~/Documents:/documents \
        -e OBSIDIAN_VAULT_PATH="${OBSIDIAN_VAULT_PATH:-}" \
        ghcr.io/yourusername/project-thoth:latest setup

    echo -e "\n${GREEN}✓ Setup complete!${NC}"
    echo -e "\nTo start Thoth services:"
    echo -e "  ${BLUE}docker compose up -d${NC}"

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
    echo "   Ubuntu/Debian: sudo apt install docker.io docker-compose"
    echo "   macOS: brew install docker docker-compose"
    echo "   Or visit: https://docs.docker.com/get-docker/"
    echo ""
    echo "2. pipx (Easy Python package manager):"
    echo "   Ubuntu/Debian: sudo apt install pipx"
    echo "   macOS: brew install pipx"
    echo ""
    echo "3. Python 3.10 or later:"
    echo "   Ubuntu/Debian: sudo apt install python3.10"
    echo "   macOS: brew install python@3.10"
    echo "   Or visit: https://www.python.org/downloads/"
    echo ""
    exit 1
fi
