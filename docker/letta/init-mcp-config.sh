#!/bin/bash
# ==============================================================================
# Initialize Letta MCP Configuration
# Automatically configures Thoth MCP server in Letta on startup
# ==============================================================================

set -e

MCP_CONFIG_FILE="/letta/.letta/mcp-servers.json"
THOTH_MCP_URL="${THOTH_MCP_URL:-http://thoth-mcp:8000}"

echo "==================================================================="
echo "Letta MCP Configuration Setup"
echo "==================================================================="

# Create .letta directory if it doesn't exist
mkdir -p /letta/.letta

# Check if MCP config already exists
if [ -f "$MCP_CONFIG_FILE" ]; then
    echo "✓ MCP configuration file exists"
    
    # Check if thoth server is already configured
    if grep -q '"thoth"' "$MCP_CONFIG_FILE"; then
        echo "✓ Thoth MCP server already configured"
    else
        echo "⚠ Adding Thoth MCP server to existing configuration..."
        # Add thoth server to existing config (using jq if available)
        if command -v jq &> /dev/null; then
            jq '.servers.thoth = {
                "name": "Thoth Research MCP Server",
                "description": "Access all 68 Thoth research tools dynamically via MCP protocol",
                "enabled": true,
                "transport": "sse",
                "url": "'$THOTH_MCP_URL'/mcp",
                "connection": {
                    "timeout": 30,
                    "read_timeout": 300,
                    "max_retries": 3
                },
                "health_check": {
                    "enabled": true,
                    "interval": 60,
                    "endpoint": "'$THOTH_MCP_URL'/health"
                }
            }' "$MCP_CONFIG_FILE" > "$MCP_CONFIG_FILE.tmp"
            mv "$MCP_CONFIG_FILE.tmp" "$MCP_CONFIG_FILE"
        fi
    fi
else
    echo "⚙ Creating new MCP configuration..."
    cat > "$MCP_CONFIG_FILE" << EOF
{
  "servers": {
    "thoth": {
      "name": "Thoth Research MCP Server",
      "description": "Access all 68 Thoth research tools dynamically via MCP protocol",
      "enabled": true,
      "transport": "sse",
      "url": "$THOTH_MCP_URL/mcp",
      "connection": {
        "timeout": 30,
        "read_timeout": 300,
        "max_retries": 3
      },
      "health_check": {
        "enabled": true,
        "interval": 60,
        "endpoint": "$THOTH_MCP_URL/health"
      }
    }
  }
}
EOF
    echo "✓ MCP configuration created"
fi

# Set proper permissions
chmod 644 "$MCP_CONFIG_FILE"

# Verify Thoth MCP server is accessible
echo ""
echo "Checking Thoth MCP server connectivity..."
if command -v curl &> /dev/null; then
    if curl -sf "$THOTH_MCP_URL/health" > /dev/null 2>&1; then
        echo "✓ Thoth MCP server is accessible at $THOTH_MCP_URL"
        
        # Try to get tool count
        TOOL_COUNT=$(curl -sf -X POST \
            -H "Content-Type: application/json" \
            -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
            "$THOTH_MCP_URL/mcp" 2>/dev/null | grep -o '"tools":\[' | wc -l || echo "0")
        
        if [ "$TOOL_COUNT" -gt 0 ]; then
            echo "✓ MCP tools endpoint responding"
        fi
    else
        echo "⚠ Warning: Cannot connect to Thoth MCP server at $THOTH_MCP_URL"
        echo "  Make sure thoth-mcp container is running on the same network"
    fi
else
    echo "⚠ curl not available, skipping connectivity check"
fi

echo ""
echo "==================================================================="
echo "MCP Configuration Complete!"
echo "==================================================================="
echo "Configuration file: $MCP_CONFIG_FILE"
echo "Thoth MCP URL: $THOTH_MCP_URL"
echo ""
echo "All Thoth MCP tools should now be available in Letta ADE."
echo "==================================================================="
