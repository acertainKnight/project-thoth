#!/bin/bash
# Restart Thoth services (does NOT restart Letta)
# Usage: thoth-restart.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔄 Restarting Thoth services..."
echo "ℹ️  Letta will NOT be restarted (independent)"
"$SCRIPT_DIR/thoth-stop.sh"
sleep 2
"$SCRIPT_DIR/thoth-start.sh"
