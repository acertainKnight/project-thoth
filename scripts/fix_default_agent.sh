#!/bin/bash
# Fix for mobile ADE accessing invalid cached agent
# This script prints the correct URLs to access each agent

echo "=================================="
echo "  MOBILE ADE FIX - Direct Links"
echo "=================================="
echo ""

# Get your server IP
SERVER_IP=$(hostname -I | awk '{print $1}')

echo "🖥️  Your Server IP: $SERVER_IP"
echo ""
echo "📱 Copy one of these URLs to your mobile browser:"
echo ""

curl -s http://localhost:8283/v1/agents | python3 -c "
import sys, json
try:
    agents = json.load(sys.stdin)
    server_ip = '$SERVER_IP'

    # Priority order: orchestrator first
    agent_order = ['orchestrator', 'scout', 'analyzer', 'expert']

    for keyword in agent_order:
        for agent in agents:
            if keyword in agent['name'].lower():
                print(f\"✅ {agent['name']}:\")
                print(f\"   http://{server_ip}:8283/agents/{agent['id']}\")
                print()
                break

    print('💡 Recommended: Use thoth_main_orchestrator (first link)')
    print()
except:
    print('❌ Could not fetch agents. Is Letta running?')
"

echo ""
echo "=================================="
echo "  Alternative: Use localhost"
echo "=================================="
echo ""
echo "If accessing from the same machine:"
echo "http://localhost:8283/agents/agent-10418b8d-37a5-4923-8f70-69ccc58d66ff"
