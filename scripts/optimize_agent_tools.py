#!/usr/bin/env python3
"""
Optimize agent tool allocation based on specialized roles.
Creates a streamlined, production-ready multi-agent architecture.
"""

import requests
import json

API_BASE = "http://localhost:8283/v1"

# Agent IDs
AGENTS = {
    "thoth_main_orchestrator": "agent-10418b8d-37a5-4923-8f70-69ccc58d66ff",
    "system_citation_analyzer": "agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5",
    "system_discovery_scout": "agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64",
    "system_analysis_expert": "agent-8a4183a6-fffc-4082-b40b-aab29727a3ab",
}

# Define what each agent SHOULD have (tool name patterns)
TOOL_ALLOCATION = {
    "thoth_main_orchestrator": {
        "keep_patterns": [
            "send_message",           # Communication
            "memory",                 # Memory management
            "core_memory",            # Core memory
            "query",                  # Query management (create/get/update/list)
            "collection_stats",       # High-level overview
            "list_articles",          # High-level overview
            "list_queries",           # High-level overview
            "generate_reading_list",  # High-level synthesis
            "generate_research_summary",  # High-level synthesis
        ],
        "role": "Coordinator - delegates tasks, manages workflow"
    },

    "system_discovery_scout": {
        "keep_patterns": [
            "send_message",           # Communication
            "memory",                 # Memory management
            "core_memory",            # Core memory
            "arxiv",                  # Search source
            "pubmed",                 # Search source
            "crossref",               # Search source
            "openalex",               # Search source
            "biorxiv",                # Search source
            "discovery",              # Discovery tools
            "run_discovery",          # Execute discovery
            "search_articles",        # Search existing
            "conversation_search",    # Conversational search
            "download_pdf",           # PDF acquisition
            "locate_pdf",             # PDF location
            "create_query",           # Query creation
            "update_query",           # Query refinement
            "generate_reading_list",  # Can suggest papers found
        ],
        "role": "Discovery - finds and acquires papers"
    },

    "system_citation_analyzer": {
        "keep_patterns": [
            "send_message",           # Communication
            "memory",                 # Memory management
            "core_memory",            # Core memory
            "citation",               # Citation tools
            "reference",              # Citation tools
            "pdf",                    # PDF analysis
            "metadata",               # Metadata extraction
            "validate",               # PDF validation
            "find_related_papers",    # Citation network
            "get_article_details",    # Article info
            "list_articles",          # Collection query
            "search_articles",        # Article search
            "export_bibliography",    # Citation output
        ],
        "role": "Citation Analysis - builds citation networks"
    },

    "system_analysis_expert": {
        "keep_patterns": [
            "send_message",           # Communication
            "memory",                 # Memory management
            "core_memory",            # Core memory
            "analyze",                # Topic analysis
            "summary",                # Research summaries
            "tag",                    # Tag management
            "consolidate",            # Tag consolidation
            "vocabulary",             # Tag vocabulary
            "evaluate",               # Paper evaluation
            "update_article",         # Metadata updates
            "batch_process",          # Batch PDF processing
            "pdf",                    # PDF processing
            "metadata",               # Metadata extraction
            "collection_stats",       # Collection management
            "reindex",                # Collection reindexing
            "get_article_details",    # Article info
            "list_articles",          # Collection query
            "search_articles",        # Article search
            "find_related",           # Related papers
            "generate_reading_list",  # Prioritized lists
            "generate_research_summary",  # Synthesis
        ],
        "role": "Analysis & Synthesis - evaluates and synthesizes"
    }
}


def get_agent_tools(agent_id):
    """Get all tools for an agent."""
    response = requests.get(f"{API_BASE}/agents/{agent_id}")
    if response.status_code == 200:
        agent = response.json()
        return agent['tools']
    return []


def should_keep_tool(tool_name, keep_patterns):
    """Check if tool matches any keep pattern."""
    tool_lower = tool_name.lower()
    return any(pattern.lower() in tool_lower for pattern in keep_patterns)


def optimize_agent_tools(agent_name, agent_id, dry_run=True):
    """Optimize tools for a specific agent."""
    print(f"\n{'='*80}")
    print(f"  {agent_name.upper()}")
    print(f"  Role: {TOOL_ALLOCATION[agent_name]['role']}")
    print(f"{'='*80}\n")

    # Get current tools
    current_tools = get_agent_tools(agent_id)
    keep_patterns = TOOL_ALLOCATION[agent_name]['keep_patterns']

    # Categorize tools
    tools_to_keep = []
    tools_to_remove = []

    for tool in current_tools:
        if should_keep_tool(tool['name'], keep_patterns):
            tools_to_keep.append(tool)
        else:
            tools_to_remove.append(tool)

    print(f"Current tools: {len(current_tools)}")
    print(f"Tools to keep: {len(tools_to_keep)}")
    print(f"Tools to remove: {len(tools_to_remove)}")

    if tools_to_remove:
        print(f"\nRemoving:")
        for tool in tools_to_remove:
            print(f"  ❌ {tool['name']}")

    if tools_to_keep:
        print(f"\nKeeping:")
        for tool in tools_to_keep:
            print(f"  ✅ {tool['name']}")

    # Apply changes
    if not dry_run and tools_to_keep:
        new_tool_ids = [t['id'] for t in tools_to_keep]
        response = requests.patch(
            f"{API_BASE}/agents/{agent_id}",
            json={"tool_ids": new_tool_ids}
        )

        if response.status_code == 200:
            print(f"\n✅ Successfully optimized {agent_name}")
            return True
        else:
            print(f"\n❌ Failed to update {agent_name}: {response.status_code}")
            return False

    return True


def main():
    import sys

    dry_run = "--apply" not in sys.argv

    print("="*80)
    print("  Multi-Agent Architecture Optimization")
    print("="*80)

    if dry_run:
        print("\n⚠️  DRY RUN MODE - No changes will be applied")
        print("Run with --apply flag to apply changes\n")
    else:
        print("\n✅ APPLY MODE - Changes will be applied\n")

    # Optimize each agent
    for agent_name, agent_id in AGENTS.items():
        optimize_agent_tools(agent_name, agent_id, dry_run=dry_run)

    # Summary
    print(f"\n{'='*80}")
    print("  Summary")
    print(f"{'='*80}\n")

    total_before = sum(len(get_agent_tools(aid)) for aid in AGENTS.values())

    print(f"Total tools before: {total_before}")

    if not dry_run:
        total_after = sum(len(get_agent_tools(aid)) for aid in AGENTS.values())
        print(f"Total tools after: {total_after}")
        print(f"Tools removed: {total_before - total_after}")
        print(f"Efficiency gain: {((total_before - total_after) / total_before * 100):.1f}%")
        print("\n✅ Optimization complete!")
    else:
        print("\n💡 Run with --apply to apply these changes")


if __name__ == "__main__":
    main()
