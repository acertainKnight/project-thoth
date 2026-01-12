#!/usr/bin/env python3
"""
Configure Letta ADE to use Thoth MCP Server

This script registers the Thoth MCP server with Letta so that all MCP tools
become available to Letta agents in the Agent Development Environment (ADE).
"""

import sys
import json
import requests
from typing import Any

# Letta server configuration
LETTA_URL = "http://localhost:8283"
LETTA_TOKEN = "letta_dev_password"

# Thoth MCP server configuration
# The MCP server is accessible from the letta-network Docker bridge
THOTH_MCP_URL = "http://thoth-mcp:8000"  # Port 8000 is the HTTP port with streaming support
THOTH_MCP_ENDPOINT = f"{THOTH_MCP_URL}/mcp"  # POST endpoint for requests

HEADERS = {
    "Authorization": f"Bearer {LETTA_TOKEN}",
    "Content-Type": "application/json"
}


def test_letta_connection() -> bool:
    """Test connection to Letta server."""
    try:
        resp = requests.get(f"{LETTA_URL}/v1/health", timeout=5)
        if resp.status_code == 200:
            print("✅ Connected to Letta server")
            return True
        else:
            print(f"❌ Letta server returned {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to Letta server: {e}")
        return False


def test_mcp_connection() -> bool:
    """Test connection to Thoth MCP server."""
    try:
        # Test from within Docker network
        import subprocess
        result = subprocess.run(
            ["docker", "exec", "letta-server", "curl", "-s",
             "-X", "POST",
             "-H", "Content-Type: application/json",
             "-d", '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}',
             "http://thoth-mcp:8000/mcp"],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode == 0:
            data = json.loads(result.stdout)
            tool_count = len(data.get("result", {}).get("tools", []))
            print(f"✅ Connected to Thoth MCP server ({tool_count} tools available)")
            return True
        else:
            print(f"❌ MCP server test failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to MCP server: {e}")
        return False


def add_mcp_server_to_letta() -> dict[str, Any] | None:
    """
    Add Thoth MCP server to Letta configuration.

    Note: As of Letta 0.7+, MCP server configuration is done via environment
    variables or the Letta UI settings, not through the REST API.

    Returns:
        Configuration dict if successful, None otherwise
    """
    print("\n📋 MCP Server Configuration:")
    print(f"   Server Name: thoth-research-tools")
    print(f"   MCP Endpoint: {THOTH_MCP_ENDPOINT}")
    print(f"   Transport: SSE")
    print()

    # Check if Letta has MCP configuration API
    # As of now, Letta typically discovers MCP servers via:
    # 1. Environment variables (LETTA_MCP_SERVERS)
    # 2. Configuration files (~/.letta/settings.json)
    # 3. UI settings

    print("⚠️  Letta MCP Configuration Methods:")
    print()
    print("Option 1: Environment Variable (Recommended)")
    print("-" * 60)
    print("Add to .env.letta:")
    print(f'LETTA_MCP_SERVERS=[\n  {{\n    "name": "thoth-research-tools",\n    "url": "{THOTH_MCP_ENDPOINT}",\n    "transport": "sse"\n  }}\n]')
    print()

    print("Option 2: Docker Compose Environment")
    print("-" * 60)
    print("Add to docker-compose.letta.yml under letta service environment:")
    print(f'- LETTA_MCP_SERVERS=[{{"name":"thoth-research-tools","url":"{THOTH_MCP_ENDPOINT}","transport":"sse"}}]')
    print()

    print("Option 3: Manual Configuration")
    print("-" * 60)
    print("1. Open Letta ADE: http://localhost:8283")
    print("2. Go to Settings > MCP Servers")
    print("3. Add new MCP server:")
    print(f"   - Name: thoth-research-tools")
    print(f"   - URL: {THOTH_MCP_ENDPOINT}")
    print("   - Transport: sse")
    print()

    return {
        "name": "thoth-research-tools",
        "url": THOTH_MCP_ENDPOINT,
        "transport": "sse"
    }


def update_docker_compose_env() -> bool:
    """Update docker-compose.letta.yml with MCP server configuration."""
    print("\n🔧 Updating Docker Compose Configuration...")

    # Read the docker-compose file
    compose_file = "/home/nick-hallmark/Documents/python/project-thoth/docker-compose.letta.yml"

    try:
        with open(compose_file, 'r') as f:
            content = f.read()

        # Check if MCP config already exists
        if 'LETTA_MCP_SERVERS' in content:
            print("⚠️  LETTA_MCP_SERVERS already configured")
            return True

        # Find the letta service environment section
        env_marker = "environment:"
        lines = content.split('\n')

        # Find where to insert the MCP config
        for i, line in enumerate(lines):
            if 'letta:' in line:
                # Found letta service, find its environment section
                for j in range(i, len(lines)):
                    if env_marker in lines[j] and 'letta-postgres' not in lines[j-5:j]:
                        # Insert after the environment line
                        mcp_config = f'      - LETTA_MCP_SERVERS=[{{"name":"thoth-research-tools","url":"{THOTH_MCP_ENDPOINT}","transport":"sse"}}]'
                        lines.insert(j + 1, mcp_config)

                        # Write back
                        with open(compose_file, 'w') as f:
                            f.write('\n'.join(lines))

                        print("✅ Updated docker-compose.letta.yml")
                        print()
                        print("⚠️  You need to restart Letta for changes to take effect:")
                        print("   docker compose -f docker-compose.letta.yml restart letta")
                        return True

        print("❌ Could not find letta service environment section")
        return False

    except Exception as e:
        print(f"❌ Error updating docker-compose: {e}")
        return False


def main():
    """Main configuration workflow."""
    print("=" * 80)
    print("LETTA ADE - THOTH MCP SERVER CONFIGURATION")
    print("=" * 80)
    print()

    # Test connections
    if not test_letta_connection():
        print("\n❌ Cannot proceed: Letta server not accessible")
        return 1

    if not test_mcp_connection():
        print("\n⚠️  Warning: MCP server not accessible from Letta container")
        print("   Make sure thoth-mcp container is running and on letta-network")
        print()
        print("   Check with: docker ps | grep thoth-mcp")
        print("   Network: docker network inspect letta-network")

    # Show configuration options
    mcp_config = add_mcp_server_to_letta()

    # Offer to update docker-compose
    print("\n" + "=" * 80)
    response = input("Update docker-compose.letta.yml automatically? (y/n): ")

    if response.lower() == 'y':
        if update_docker_compose_env():
            print()
            print("✅ Configuration complete!")
            print()
            print("Next steps:")
            print("1. Restart Letta: docker compose -f docker-compose.letta.yml restart letta")
            print("2. Wait ~30 seconds for Letta to restart")
            print("3. Check Letta ADE: http://localhost:8283")
            print("4. Your agents should now have access to 68 Thoth MCP tools!")
        else:
            print()
            print("⚠️  Automatic update failed. Please configure manually.")
    else:
        print()
        print("💡 Manual configuration instructions shown above")
        print("   After configuring, restart Letta to apply changes")

    print()
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())
