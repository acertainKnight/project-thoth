#!/usr/bin/env python3
"""
Register the Thoth MCP server with Letta and attach tools to agents.
"""
import os
import sys

# Add project to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from letta import create_client
    from letta.schemas.tool import Tool
except ImportError:
    print("❌ Letta SDK not installed. Install with: pip install letta")
    sys.exit(1)

def main():
    # Connect to Letta server
    client = create_client(
        base_url="http://localhost:8283",
        token="letta_dev_password"
    )
    
    print("✅ Connected to Letta server")
    
    # MCP server configuration
    mcp_config = {
        "name": "thoth-research-tools",
        "url": "http://thoth-mcp:8000",  # Docker network
        "transport": "sse"
    }
    
    print(f"\n📡 Registering MCP server: {mcp_config['name']}")
    print(f"   URL: {mcp_config['url']}")
    
    # Register MCP server
    try:
        # Note: The exact API method depends on Letta version
        # This is pseudocode - check Letta docs for exact method
        mcp_server = client.add_mcp_server(**mcp_config)
        print(f"✅ MCP server registered: {mcp_server.id}")
    except Exception as e:
        print(f"⚠️  MCP server registration: {e}")
        print("   (May already be registered)")
    
    # List available tools from MCP
    print("\n🔧 Available tools from MCP server:")
    try:
        tools = client.list_tools(source="mcp")
        print(f"   Found {len(tools)} MCP tools")
        
        # Show skill-related tools
        skill_tools = [t for t in tools if 'skill' in t.name.lower()]
        if skill_tools:
            print("\n   Skill tools:")
            for tool in skill_tools:
                print(f"     - {tool.name}: {tool.description[:60]}...")
    except Exception as e:
        print(f"   Error listing tools: {e}")
    
    # Get current agent
    agent_id = "agent-726c7561-fe3d-4380-ba99-163b15c204c8"
    print(f"\n👤 Checking agent: {agent_id}")
    
    try:
        agent = client.get_agent(agent_id)
        print(f"   Agent name: {agent.name}")
        print(f"   Current tools: {len(agent.tools)}")
        
        # TODO: Attach MCP tools to agent
        # This depends on Letta's API - may need to update agent config
        
    except Exception as e:
        print(f"   Error accessing agent: {e}")
    
    print("\n" + "="*60)
    print("NEXT STEPS:")
    print("1. Open Letta Web UI: http://localhost:8283")
    print("2. Login: admin / letta_dev_password")
    print("3. Go to agent settings")
    print("4. Attach MCP tools to your agent")
    print("="*60)

if __name__ == "__main__":
    main()
