#!/usr/bin/env python3
"""Force refresh MCP tools in Letta."""

import json

import requests

LETTA_URL = 'http://localhost:8283'
LETTA_TOKEN = 'letta_dev_password'
MCP_SERVER_ID = 'mcp_server-593fdb27-ca90-46aa-9965-9fa7b3544925'
MCP_URL = 'http://thoth-mcp:8001'

headers = {'Authorization': f'Bearer {LETTA_TOKEN}', 'Content-Type': 'application/json'}

# Get tools from MCP server directly
print('📡 Fetching tools from MCP server...')
mcp_response = requests.post(
    f'{MCP_URL}/mcp',
    json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}},
    timeout=10,
)
mcp_tools = mcp_response.json()['result']['tools']
print(f'✅ Found {len(mcp_tools)} tools from MCP server')

# Register each tool with Letta
print('\n🔧 Registering tools with Letta...')
registered = 0
for tool in mcp_tools:
    try:
        # Create tool in Letta
        tool_data = {
            'name': tool['name'],
            'description': tool['description'],
            'source_type': 'mcp',
            'source_code': json.dumps(tool),  # Store schema
            'tags': ['mcp', 'thoth'],
            'json_schema': tool['inputSchema'],
        }

        response = requests.post(
            f'{LETTA_URL}/v1/tools', headers=headers, json=tool_data, timeout=10
        )

        if response.status_code in [200, 201]:
            registered += 1
            print(f'  ✓ {tool["name"]}')
        elif response.status_code == 409:
            print(f'  → {tool["name"]} (already exists)')
        else:
            print(f'  ✗ {tool["name"]}: {response.status_code}')

    except Exception as e:
        print(f'  ✗ {tool["name"]}: {e}')

print(f'\n✅ Registered {registered} new tools')
print(f'📊 Total: {len(mcp_tools)} tools from MCP server')
