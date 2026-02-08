#!/usr/bin/env python3
"""
Fix agent tools according to Letta specifications:
- Orchestrator: ONLY send_message_to_agent_and_wait_for_reply (remove async)
- Specialists: REMOVE all multi-agent tools (they shouldn't initiate delegation)
"""

import requests

BASE_URL = 'http://localhost:8283'
HEADERS = {
    'Authorization': 'Bearer letta_dev_password',
    'Content-Type': 'application/json',
}

# Agent IDs
ORCHESTRATOR_ID = 'agent-10418b8d-37a5-4923-8f70-69ccc58d66ff'
SPECIALIST_IDS = {
    'Discovery Scout': 'agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64',
    'Document Librarian': 'agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf',
    'Citation Specialist': 'agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5',
    'Research Analyst': 'agent-8a4183a6-fffc-4082-b40b-aab29727a3ab',
    'Organization Curator': 'agent-547e81f7-6ea6-4600-ba51-c536e6a5bf2e',
    'System Maintenance': 'agent-544c0035-e3eb-42bf-a146-3c9eaada4979',
}

# Tool IDs
TOOL_SYNC = 'tool-85848c67-6187-456b-b5e5-71a8f0cbcb41'  # send_message_to_agent_and_wait_for_reply


def get_agent(agent_id):
    """Get agent details."""
    resp = requests.get(f'{BASE_URL}/v1/agents/{agent_id}', headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def update_agent_tools(agent_id, agent_name):
    """Update agent tools according to Letta specs."""
    agent = get_agent(agent_id)

    # Get all current tools
    current_tools = agent['tools']

    # Separate multi-agent tools from other tools
    multi_agent_tools = [
        t for t in current_tools if t.get('tool_type') == 'letta_multi_agent_core'
    ]
    other_tools = [
        t for t in current_tools if t.get('tool_type') != 'letta_multi_agent_core'
    ]

    print(f'\n{agent_name}:')
    print(f'  Current multi-agent tools: {[t["name"] for t in multi_agent_tools]}')

    if agent_id == ORCHESTRATOR_ID:
        # Orchestrator: ONLY synchronous tool (remove async if present)
        new_tool_ids = [t['id'] for t in other_tools] + [TOOL_SYNC]
        print('  Action: Keep ONLY send_message_to_agent_and_wait_for_reply')
    else:
        # Specialists: NO multi-agent tools (they don't initiate delegation)
        new_tool_ids = [t['id'] for t in other_tools]
        print("  Action: REMOVE all multi-agent tools (specialists don't delegate)")

    # Update agent
    resp = requests.patch(
        f'{BASE_URL}/v1/agents/{agent_id}',
        headers=HEADERS,
        json={'tool_ids': new_tool_ids},
    )

    if resp.status_code in [200, 201]:
        print('  ✓ Updated successfully')
        return True
    else:
        print(f'  ✗ Failed: {resp.status_code}')
        return False


def main():
    print('=' * 80)
    print('FIXING MULTI-AGENT TOOLS PER LETTA SPECIFICATIONS')
    print('=' * 80)
    print()
    print("Letta docs: 'We recommend only attaching ONE tool, not both.'")
    print()
    print('Configuration:')
    print('  - Orchestrator: send_message_to_agent_and_wait_for_reply ONLY')
    print("  - Specialists: NO multi-agent tools (they respond, don't delegate)")
    print()
    print('-' * 80)

    # Fix orchestrator
    update_agent_tools(ORCHESTRATOR_ID, 'Orchestrator')

    # Fix specialists
    for name, agent_id in SPECIALIST_IDS.items():
        update_agent_tools(agent_id, name)

    print()
    print('=' * 80)
    print('CONFIGURATION COMPLETE')
    print('=' * 80)
    print()
    print('Multi-Agent Pattern:')
    print('  1. User → Orchestrator')
    print('  2. Orchestrator calls: send_message_to_agent_and_wait_for_reply()')
    print('  3. Specialist receives message, processes with tools, returns response')
    print('  4. Orchestrator receives response as return value')
    print('  5. Orchestrator synthesizes → User')
    print()
    print("Key: Specialists DON'T need multi-agent tools - they just respond!")
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'\nError: {e!s}')
        import traceback

        traceback.print_exc()
