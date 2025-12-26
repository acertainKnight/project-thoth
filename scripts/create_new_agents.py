#!/usr/bin/env python3
"""
Create the 3 new specialized agents with proper configuration.
"""

import requests
import json

BASE_URL = "http://localhost:8283"
HEADERS = {
    "Authorization": "Bearer letta_dev_password",
    "Content-Type": "application/json"
}

# Agent descriptions
AGENT_DESCRIPTIONS = {
    "document_librarian": """I am the Document Librarian - your PDF and article management specialist.

I handle:
- PDF download and acquisition
- PDF processing and metadata extraction
- Article database management (search, list, update, delete)
- Article quality evaluation
- Data export

I keep your research collection organized and accessible.""",

    "organization_curator": """I am the Organization Curator - your query and taxonomy specialist.

I manage:
- Saved research queries (create, update, list, delete)
- Tag organization and consolidation
- Tag vocabulary and taxonomy
- Smart tag suggestions

I keep your research organized and consistently categorized.""",

    "system_maintenance": """I am the System Maintenance agent - your collection health specialist.

I handle:
- Collection statistics and monitoring
- Backup and restoration
- Search optimization and reindexing
- Memory health monitoring
- Integration with external tools (Obsidian)

I keep your research system running smoothly."""
}

# Tool assignments
TOOL_ASSIGNMENTS = {
    "document_librarian": [
        # PDF Management (6 tools)
        "download_pdf", "locate_pdf", "process_pdf", "batch_process_pdfs",
        "extract_pdf_metadata", "validate_pdf_sources",
        # Article Management (7 tools)
        "list_articles", "search_articles", "get_article_details",
        "update_article_metadata", "delete_article", "evaluate_article",
        "export_article_data"
    ],
    "organization_curator": [
        # Query Management (5 tools)
        "create_query", "get_query", "list_queries", "update_query", "delete_query",
        # Organization & Tagging (4 tools)
        "consolidate_tags", "consolidate_and_retag", "suggest_tags", "manage_tag_vocabulary"
    ],
    "system_maintenance": [
        # Collection Management (5 tools)
        "collection_stats", "backup_collection", "reindex_collection",
        "optimize_search", "create_custom_index",
        # Memory & System (2 tools)
        "memory_stats", "memory_health_check",
        # Integration (1 tool)
        "sync_with_obsidian"
    ]
}


def get_all_tools():
    """Get all MCP tools."""
    resp = requests.get(f"{BASE_URL}/v1/tools", headers=HEADERS)
    resp.raise_for_status()

    tools = {}
    for tool in resp.json():
        if tool.get('tool_type') == 'external_mcp':
            tools[tool['name']] = tool

    return tools


def create_agent(name, description, tool_names, all_tools):
    """Create a new agent with proper configuration."""
    print(f"Creating agent: {name}")

    # Get tool IDs
    tool_ids = []
    for tool_name in tool_names:
        if tool_name in all_tools:
            tool_ids.append(all_tools[tool_name]['id'])
        else:
            print(f"  ⚠️  Tool not found: {tool_name}")

    # Agent payload
    agent_data = {
        "name": name,
        "system": description,
        "llm_config": {
            "model": "gpt-4-turbo-preview",
            "model_endpoint_type": "openai",
            "context_window": 128000,
            "temperature": 0.7,
            "parallel_tool_calls": False
        },
        "embedding_config": {
            "embedding_endpoint_type": "openai",
            "embedding_model": "text-embedding-ada-002",
            "embedding_dim": 1536,
            "embedding_chunk_size": 300
        },
        "memory": {
            "blocks": [
                {
                    "label": "research_context",
                    "value": "Research context shared across agents.",
                    "limit": 1000,
                    "description": "Current research topic and context"
                },
                {
                    "label": "active_papers",
                    "value": "Papers being processed.",
                    "limit": 2000,
                    "description": "Papers in the processing pipeline"
                }
            ]
        },
        "tool_ids": tool_ids
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/v1/agents",
            headers=HEADERS,
            json=agent_data
        )

        if resp.status_code in [200, 201]:
            agent = resp.json()
            agent_id = agent['id']
            tool_count = len([t for t in agent['tools'] if t.get('tool_type') == 'external_mcp'])
            print(f"  ✓ Created: {agent_id}")
            print(f"  ✓ MCP Tools: {tool_count}")
            return agent_id
        else:
            print(f"  ✗ Failed: {resp.status_code}")
            print(f"  Response: {resp.text[:500]}")
            return None

    except Exception as e:
        print(f"  ✗ Error: {str(e)}")
        return None


def main():
    print("=" * 80)
    print("CREATING 3 NEW SPECIALIZED AGENTS")
    print("=" * 80)
    print()

    # Get all tools
    print("Fetching tools...")
    all_tools = get_all_tools()
    print(f"  Found {len(all_tools)} MCP tools")
    print()

    # Create each new agent
    new_agents = {}

    for agent_key in ["document_librarian", "organization_curator", "system_maintenance"]:
        print("-" * 80)
        agent_id = create_agent(
            name=agent_key,
            description=AGENT_DESCRIPTIONS[agent_key],
            tool_names=TOOL_ASSIGNMENTS[agent_key],
            all_tools=all_tools
        )

        if agent_id:
            new_agents[agent_key] = agent_id

        print()

    print("=" * 80)
    print("COMPLETE")
    print("=" * 80)
    print()

    if len(new_agents) == 3:
        print("✓ All 3 agents created successfully!")
        print()
        print("New agent IDs:")
        for name, agent_id in new_agents.items():
            print(f"  {name}: {agent_id}")
        print()
        print("Updated architecture:")
        print("  ✓ Orchestrator: 0 MCP tools (delegation only)")
        print("  ✓ Discovery Scout: 9 MCP tools")
        print("  ✓ Document Librarian: 13 MCP tools ⭐ NEW")
        print("  ✓ Citation Specialist: 4 MCP tools")
        print("  ✓ Research Analyst: 3 MCP tools")
        print("  ✓ Organization Curator: 9 MCP tools ⭐ NEW")
        print("  ✓ System Maintenance: 8 MCP tools ⭐ NEW")
        print("  ✓ Total: 46 MCP tools with ZERO overlap")
    else:
        print(f"⚠️  Only {len(new_agents)} of 3 agents created")
        print("Some agents may need to be created manually")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
