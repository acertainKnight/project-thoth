#!/bin/bash

# Thoth API Server Startup Script
# This script activates the virtual environment and starts the Thoth API server

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR"

# Activate virtual environment and run thoth
if command -v uv &> /dev/null; then
    # Use uv if available
    uv run python -m thoth api "$@"
elif [ -d ".venv" ]; then
    # Use traditional venv
    source .venv/bin/activate
    python -m thoth api "$@"
else
    # Try system python
    python3 -m thoth api "$@"
fi
