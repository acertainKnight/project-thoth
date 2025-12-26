#!/usr/bin/env python3
"""
Setup orchestrator with agent registry memory block and proper system prompt.
"""

import requests
import json

BASE_URL = "http://localhost:8283"
HEADERS = {
    "Authorization": "Bearer letta_dev_password",
    "Content-Type": "application/json"
}

ORCHESTRATOR_ID = "agent-10418b8d-37a5-4923-8f70-69ccc58d66ff"

# Agent registry content
AGENT_REGISTRY = """=== SPECIALIZED AGENT REGISTRY ===

1. DISCOVERY SCOUT
   ID: agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64
   Role: Paper discovery across academic sources
   Use for: Finding papers, configuring discovery sources, running searches
   Capabilities: arXiv, bioRxiv, CrossRef, OpenAlex, PubMed
   Tools: 9 discovery tools

2. DOCUMENT LIBRARIAN
   ID: agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf
   Role: PDF acquisition and article database management
   Use for: Downloading PDFs, managing articles, searching collection
   Capabilities: PDF processing, article CRUD, metadata extraction
   Tools: 13 document tools

3. CITATION SPECIALIST
   ID: agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5
   Role: Citation extraction and bibliography management
   Use for: Extracting citations, building networks, formatting bibliographies
   Capabilities: Citation analysis, related paper discovery
   Tools: 4 citation tools

4. RESEARCH ANALYST
   ID: agent-8a4183a6-fffc-4082-b40b-aab29727a3ab
   Role: Deep analysis and research synthesis
   Use for: Topic analysis, reading lists, research summaries
   Capabilities: Synthesis, trend identification, insight generation
   Tools: 3 analysis tools

5. ORGANIZATION CURATOR
   ID: agent-547e81f7-6ea6-4600-ba51-c536e6a5bf2e
   Role: Query management and taxonomy organization
   Use for: Managing queries, organizing tags, maintaining vocabulary
   Capabilities: Query CRUD, tag consolidation, taxonomy management
   Tools: 9 organization tools

6. SYSTEM MAINTENANCE
   ID: agent-544c0035-e3eb-42bf-a146-3c9eaada4979
   Role: Collection health, backups, and system integration
   Use for: Statistics, backups, optimization, Obsidian sync
   Capabilities: Collection management, health monitoring
   Tools: 8 system tools

=== DELEGATION RULES ===

ALWAYS use agent IDs (agent-<uuid>) when calling send_message_to_agent_async.
NEVER use names or shortcuts - IDs only!

Example: send_message_to_agent_async(agent_id="agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64", ...)

Check this registry to find the correct agent ID for each task.
"""

# Updated system prompt
SYSTEM_PROMPT = """You are the Thoth Main Orchestrator - the entry point for users interacting with a specialized multi-agent research system.

=== YOUR ROLE ===

You coordinate research workflows by delegating specialized tasks to expert agents. You have NO MCP tools - you ONLY delegate.

=== HOW TO DELEGATE ===

1. Read the user's request
2. Check the 'agent_registry' memory block to find the right specialist
3. Use send_message_to_agent_async with the EXACT agent ID from the registry
4. Wait for the response
5. Synthesize and return results to the user

CRITICAL: Always use full agent IDs like "agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf"
NEVER use shortened names like "agent-uuid-research" - this will fail!

=== MEMORY BLOCKS ===

- agent_registry: Contains all specialist agent IDs and capabilities (READ THIS FIRST)
- research_context: Current research topic and questions
- active_papers: Papers being processed
- citation_network: Citation relationships
- research_findings: Synthesized insights
- workflow_state: Current workflow status
- message_queue: Task queue for tracking

=== DELEGATION EXAMPLES ===

User: "Find papers on quantum computing"
→ Check agent_registry for Discovery Scout ID
→ send_message_to_agent_async(agent_id="agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64",
                              message="Run discovery for papers on quantum computing from 2024")

User: "Download PDFs for these papers"
→ Check agent_registry for Document Librarian ID
→ send_message_to_agent_async(agent_id="agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf",
                              message="Download PDFs for papers: [list]")

User: "Generate a literature review"
→ Check agent_registry for Research Analyst ID
→ send_message_to_agent_async(agent_id="agent-8a4183a6-fffc-4082-b40b-aab29727a3ab",
                              message="Generate research summary for papers in active_papers")

=== WORKFLOW COORDINATION ===

For complex tasks requiring multiple agents:
1. Break down the task into specialist subtasks
2. Delegate to appropriate agents in sequence or parallel
3. Update workflow_state to track progress
4. Synthesize results from all agents
5. Return comprehensive response to user

=== WHAT YOU DO NOT DO ===

- You do NOT have MCP tools for research tasks
- You do NOT search for papers directly (delegate to Discovery Scout)
- You do NOT download PDFs directly (delegate to Document Librarian)
- You do NOT analyze citations directly (delegate to Citation Specialist)
- You do NOT generate summaries directly (delegate to Research Analyst)

You are a coordinator, not a worker. Always delegate to specialists.
"""


def get_agent(agent_id):
    """Get agent details."""
    resp = requests.get(f"{BASE_URL}/v1/agents/{agent_id}", headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def update_agent_system_and_memory(agent_id, system_prompt, agent_registry_content):
    """Update orchestrator system prompt and add agent registry memory block."""
    print(f"Updating orchestrator (agent-{agent_id[-12:]})...")

    # Get current agent state
    agent = get_agent(agent_id)

    # Check if agent_registry block exists
    existing_blocks = agent['memory']['blocks']
    registry_block = None

    for block in existing_blocks:
        if block['label'] == 'agent_registry':
            registry_block = block
            break

    # Update or create agent_registry block
    if registry_block:
        print("  Updating existing agent_registry block...")
        block_id = registry_block['id']

        # Update block content
        resp = requests.post(
            f"{BASE_URL}/v1/blocks/{block_id}",
            headers=HEADERS,
            json={"value": agent_registry_content}
        )

        if resp.status_code in [200, 201]:
            print("    ✓ Updated agent_registry block")
        else:
            print(f"    ✗ Failed to update block: {resp.status_code}")
    else:
        print("  Creating new agent_registry block...")

        # Create new block
        block_data = {
            "label": "agent_registry",
            "value": agent_registry_content,
            "limit": 3000,
            "description": "Registry of all specialized agents with IDs and capabilities"
        }

        resp = requests.post(
            f"{BASE_URL}/v1/blocks",
            headers=HEADERS,
            json=block_data
        )

        if resp.status_code in [200, 201]:
            new_block = resp.json()
            block_id = new_block['id']
            print(f"    ✓ Created agent_registry block: {block_id}")

            # Attach block to agent
            agent['memory']['blocks'].append(new_block)
        else:
            print(f"    ✗ Failed to create block: {resp.status_code}")
            return False

    # Update system prompt
    print("  Updating system prompt...")

    resp = requests.patch(
        f"{BASE_URL}/v1/agents/{agent_id}",
        headers=HEADERS,
        json={"system": system_prompt}
    )

    if resp.status_code in [200, 201]:
        print("    ✓ Updated system prompt")
        return True
    else:
        print(f"    ✗ Failed to update system: {resp.status_code}")
        return False


def main():
    print("=" * 80)
    print("CONFIGURING ORCHESTRATOR FOR MULTI-AGENT DELEGATION")
    print("=" * 80)
    print()

    success = update_agent_system_and_memory(
        ORCHESTRATOR_ID,
        SYSTEM_PROMPT,
        AGENT_REGISTRY
    )

    print()
    print("=" * 80)

    if success:
        print("✓ CONFIGURATION COMPLETE")
        print()
        print("Orchestrator now has:")
        print("  ✓ Agent registry memory block with all specialist IDs")
        print("  ✓ Updated system prompt with delegation instructions")
        print("  ✓ Clear guidance on using send_message_to_agent_async")
        print()
        print("The orchestrator will now:")
        print("  1. Check agent_registry for the correct agent ID")
        print("  2. Use full UUIDs when delegating (e.g., agent-02e9a5db...)")
        print("  3. Never use shortened names that cause errors")
    else:
        print("✗ CONFIGURATION FAILED")
        print("  Check the errors above and try again")

    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        traceback.print_exc()
