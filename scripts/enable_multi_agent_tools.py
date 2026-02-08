#!/usr/bin/env python3
"""
Enable multi-agent communication tools for orchestrator and specialists.
Uses direct tool IDs since organization filtering prevents list queries.
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

# Multi-agent tool IDs (from database query)
TOOL_ASYNC = 'tool-640603e9-1be0-4ddb-abbf-ff58bd08b047'  # send_message_to_agent_async
TOOL_SYNC = 'tool-85848c67-6187-456b-b5e5-71a8f0cbcb41'  # send_message_to_agent_and_wait_for_reply


def get_agent(agent_id):
    """Get agent details."""
    resp = requests.get(f'{BASE_URL}/v1/agents/{agent_id}', headers=HEADERS)
    resp.raise_for_status()
    return resp.json()


def add_tool_to_agent(agent_id, tool_id, agent_name):
    """Add a tool to an agent without removing existing tools."""
    # Get current agent
    agent = get_agent(agent_id)

    # Get current tool IDs
    current_tool_ids = [t['id'] for t in agent['tools']]

    # Check if tool already present
    if tool_id in current_tool_ids:
        return True, 'already present'

    # Add new tool
    updated_tool_ids = current_tool_ids + [tool_id]

    # Update agent
    resp = requests.patch(
        f'{BASE_URL}/v1/agents/{agent_id}',
        headers=HEADERS,
        json={'tool_ids': updated_tool_ids},
    )

    if resp.status_code in [200, 201]:
        return True, 'added'
    else:
        return False, f'error: {resp.status_code}'


def main():
    print('=' * 80)
    print('ENABLING MULTI-AGENT COMMUNICATION TOOLS')
    print('=' * 80)
    print()
    print('Tool IDs (from database):')
    print(f'  - Synchronous: {TOOL_SYNC}')
    print('    (send_message_to_agent_and_wait_for_reply)')
    print()

    # Add synchronous tool to orchestrator
    print('-' * 80)
    print('ORCHESTRATOR (needs synchronous tool to receive responses)')
    print('-' * 80)

    success, status = add_tool_to_agent(ORCHESTRATOR_ID, TOOL_SYNC, 'Orchestrator')
    if success:
        print(f'✓ Orchestrator: send_message_to_agent_and_wait_for_reply ({status})')
    else:
        print(f'✗ Orchestrator: failed - {status}')

    print()

    # Add synchronous tool to all specialists
    print('-' * 80)
    print('SPECIALISTS (need synchronous tool to respond to orchestrator)')
    print('-' * 80)

    for name, agent_id in SPECIALIST_IDS.items():
        success, status = add_tool_to_agent(agent_id, TOOL_SYNC, name)
        if success:
            print(f'✓ {name:30} {status}')
        else:
            print(f'✗ {name:30} {status}')

    print()
    print('=' * 80)
    print('CONFIGURATION COMPLETE')
    print('=' * 80)
    print()
    print('All agents now have: send_message_to_agent_and_wait_for_reply')
    print()
    print('Multi-Agent Communication Pattern:')
    print('  1. User sends request → Orchestrator')
    print('  2. Orchestrator checks agent_registry for specialist ID')
    print('  3. Orchestrator calls: send_message_to_agent_and_wait_for_reply(')
    print("       agent_id='agent-<uuid>',")
    print("       message='<task description>'")
    print('     )')
    print('  4. Specialist receives message and processes with specialized tools')
    print('  5. Specialist returns response (synchronously)')
    print('  6. Orchestrator receives response as tool output')
    print('  7. Orchestrator synthesizes and returns to user')
    print()
    print('Pattern: User → Orchestrator ⇄ Specialist → User')
    print('         (synchronous delegation with responses)')
    print()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'\nError: {e!s}')
        import traceback

        traceback.print_exc()
