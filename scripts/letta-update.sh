#!/bin/bash
set -e

# Letta Update Script
# Wrapper for safely updating Letta to a new version
# Usage: ./letta-update.sh [version]
#   version: specific version like "0.16.2" or "latest" (default)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION=${1:-"latest"}

echo "🔄 Updating Letta to version: $VERSION"
echo ""

# Check if migration script exists
if [ ! -f "$SCRIPT_DIR/letta-migrate.sh" ]; then
    echo "Error: letta-migrate.sh not found!"
    exit 1
fi

# Make sure it's executable
chmod +x "$SCRIPT_DIR/letta-migrate.sh"

# Run migration
"$SCRIPT_DIR/letta-migrate.sh" "$VERSION"
