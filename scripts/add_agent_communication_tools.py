#!/usr/bin/env python3
"""
Add the correct agent communication tool to orchestrator and specialists.
"""

import requests

BASE_URL = 'http://localhost:8283'
HEADERS = {
    'Authorization': 'Bearer letta_dev_password',
    'Content-Type': 'application/json',
}

ORCHESTRATOR_ID = 'agent-10418b8d-37a5-4923-8f70-69ccc58d66ff'

# All specialist agent IDs
SPECIALIST_IDS = [
    'agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64',  # Discovery Scout
    'agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf',  # Document Librarian
    'agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5',  # Citation Specialist
    'agent-8a4183a6-fffc-4082-b40b-aab29727a3ab',  # Research Analyst
    'agent-547e81f7-6ea6-4600-ba51-c536e6a5bf2e',  # Organization Curator
    'agent-544c0035-e3eb-42bf-a146-3c9eaada4979',  # System Maintenance
]


def get_all_tools():
    """Get all available tools."""
    resp = requests.get(f'{BASE_URL}/v1/tools', headers=HEADERS)
    resp.raise_for_status()
    return {tool['name']: tool for tool in resp.json()}


def get_agent(agent_id):
    """Get agent details."""
    resp = requests.get(f'{BASE_URL}/v1/agents/{agent_id}', headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def update_agent_tools(agent_id, agent_name, target_tool_names, all_tools):
    """Update agent tools."""
    # Get current agent
    agent = get_agent(agent_id)

    # Get current tool IDs (non-communication tools)
    current_tools = agent['tools']

    # Remove any existing communication tools
    communication_tools = [
        'send_message_to_agent_async',
        'send_message_to_agent_and_wait_for_reply',
    ]
    non_comm_tool_ids = [
        t['id'] for t in current_tools if t['name'] not in communication_tools
    ]

    # Add target communication tool IDs
    target_tool_ids = []
    for name in target_tool_names:
        if name in all_tools:
            target_tool_ids.append(all_tools[name]['id'])

    # Combine
    all_tool_ids = non_comm_tool_ids + target_tool_ids

    # Update agent
    resp = requests.patch(
        f'{BASE_URL}/v1/agents/{agent_id}',
        headers=HEADERS,
        json={'tool_ids': all_tool_ids},
    )

    if resp.status_code in [200, 201]:
        # Verify
        agent = get_agent(agent_id)
        comm_tools = [
            t['name'] for t in agent['tools'] if t['name'] in communication_tools
        ]
        return True, comm_tools
    else:
        return False, []


def main():
    print('=' * 80)
    print('CONFIGURING AGENT COMMUNICATION TOOLS')
    print('=' * 80)
    print()
    print('Letta Documentation: https://docs.letta.com/guides/agents/multi-agent/')
    print()

    # Get all tools
    all_tools = get_all_tools()

    # Check if required tools exist
    if 'send_message_to_agent_and_wait_for_reply' not in all_tools:
        print('✗ send_message_to_agent_and_wait_for_reply not found!')
        print('  This tool is required for synchronous agent communication.')
        return

    print('✓ Found required communication tools')
    print()

    # Update orchestrator (needs synchronous tool to get responses)
    print('-' * 80)
    print('ORCHESTRATOR (coordinator - needs responses)')
    print('-' * 80)

    success, comm_tools = update_agent_tools(
        ORCHESTRATOR_ID,
        'orchestrator',
        ['send_message_to_agent_and_wait_for_reply'],  # Synchronous tool
        all_tools,
    )

    if success:
        print('✓ Orchestrator configured')
        print(f'  Communication tools: {comm_tools}')
    else:
        print('✗ Failed to configure orchestrator')

    print()

    # Update specialists (need synchronous tool to respond to orchestrator)
    print('-' * 80)
    print('SPECIALISTS (need to respond to orchestrator)')
    print('-' * 80)

    specialist_names = [
        'Discovery Scout',
        'Document Librarian',
        'Citation Specialist',
        'Research Analyst',
        'Organization Curator',
        'System Maintenance',
    ]

    for agent_id, name in zip(SPECIALIST_IDS, specialist_names):
        success, comm_tools = update_agent_tools(
            agent_id,
            name,
            ['send_message_to_agent_and_wait_for_reply'],  # Synchronous tool
            all_tools,
        )

        if success:
            print(f'✓ {name:30} {comm_tools}')
        else:
            print(f'✗ {name:30} failed')

    print()
    print('=' * 80)
    print('CONFIGURATION COMPLETE')
    print('=' * 80)
    print()
    print('All agents now have: send_message_to_agent_and_wait_for_reply')
    print()
    print('How it works:')
    print(
        '  1. Orchestrator calls: send_message_to_agent_and_wait_for_reply(agent_id=..., message=...)'
    )
    print('  2. Specialist receives message and processes it')
    print('  3. Specialist returns response')
    print('  4. Orchestrator receives response as tool output')
    print('  5. Orchestrator synthesizes and returns to user')
    print()
    print('Pattern: User → Orchestrator → Specialist → Orchestrator → User')
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'\nError: {e!s}')
        import traceback

        traceback.print_exc()
