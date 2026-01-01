#!/bin/bash
# MCP Server Wrapper - Ensures Node 20 is loaded via nvm before starting MCP servers

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Execute the command passed as arguments
exec "$@"
