#!/bin/bash
# Restart Letta and PostgreSQL services
# Usage: letta-restart.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔄 Restarting Letta services..."
"$SCRIPT_DIR/letta-stop.sh"
sleep 2
"$SCRIPT_DIR/letta-start.sh"
