#!/usr/bin/env python3
"""
Attach Thoth MCP server to all Letta agents.

This script connects the Thoth Research Tools MCP server to all agents
that don't already have it attached.

Usage:
    python3 attach-mcp-to-agents.py [letta_url]

Examples:
    # Use default local URL
    python3 attach-mcp-to-agents.py

    # Specify custom Letta URL
    python3 attach-mcp-to-agents.py http://localhost:8283
"""
import sys
import requests


def attach_mcp_to_agents(letta_url="http://localhost:8283"):
    """Attach Thoth MCP server to all agents that don't have it."""
    try:
        print("=" * 60)
        print("Attaching Thoth MCP Server to Agents")
        print("=" * 60)
        print()

        # Get MCP server ID
        print("Looking for Thoth MCP server...")
        mcp_resp = requests.get(f"{letta_url}/v1/mcp-servers/", timeout=10)
        if mcp_resp.status_code != 200:
            print(f"✗ Could not retrieve MCP servers (status: {mcp_resp.status_code})")
            return False

        servers = mcp_resp.json()
        thoth_mcp_id = None
        for server in servers:
            if server.get('server_name') == 'thoth-research-tools':
                thoth_mcp_id = server.get('id')
                print(f"✓ Found Thoth MCP server: {thoth_mcp_id}")
                break

        if not thoth_mcp_id:
            print("✗ Thoth MCP server not found in Letta")
            print("  Make sure Letta has initialized and registered the MCP server")
            return False

        print()
        print("Retrieving agents...")
        # Get all agents
        agents_resp = requests.get(f"{letta_url}/v1/agents/?limit=1000", timeout=10)
        if agents_resp.status_code != 200:
            print(f"✗ Could not retrieve agents (status: {agents_resp.status_code})")
            return False

        agents = agents_resp.json()
        print(f"Found {len(agents)} agent(s)")
        print()

        attached_count = 0
        skipped_count = 0
        failed_count = 0

        for agent in agents:
            agent_id = agent.get('id')
            agent_name = agent.get('name', 'Unknown')
            current_mcps = agent.get('mcp_server_ids', [])

            # Skip if already attached
            if thoth_mcp_id in current_mcps:
                print(f"  ⊙ {agent_name} - already has MCP server")
                skipped_count += 1
                continue

            # Attach MCP server
            patch_resp = requests.patch(
                f"{letta_url}/v1/agents/{agent_id}",
                json={"mcp_server_ids": [thoth_mcp_id]},
                timeout=10
            )

            if patch_resp.status_code in [200, 201]:
                print(f"  ✓ {agent_name} - MCP server attached")
                attached_count += 1
            else:
                print(f"  ✗ {agent_name} - failed (status: {patch_resp.status_code})")
                failed_count += 1

        print()
        print("=" * 60)
        print(f"Results:")
        print(f"  Attached:       {attached_count}")
        print(f"  Already had:    {skipped_count}")
        print(f"  Failed:         {failed_count}")
        print(f"  Total agents:   {len(agents)}")
        print("=" * 60)

        return failed_count == 0

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


if __name__ == '__main__':
    letta_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8283"
    success = attach_mcp_to_agents(letta_url)
    sys.exit(0 if success else 1)
