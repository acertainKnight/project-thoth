#!/usr/bin/env python3
"""
Create message queue shared memory block for agent coordination.
This enables asynchronous communication between agents via shared memory.
"""

import json
from pathlib import Path

import requests

API_BASE = 'http://localhost:8283/v1'


def create_message_queue_block():
    """Create the message_queue shared memory block."""
    block_config = {
        'label': 'message_queue',
        'value': '=== Agent Message Queue ===\n\n[No messages]\n\n=== Message Format ===\n[timestamp] sender -> receiver\nTask: description\nPriority: high/medium/low\nStatus: pending/in_progress/complete\n---',
        'limit': 3000,
        'description': 'Agent-to-agent message queue for async communication',
    }

    response = requests.post(f'{API_BASE}/blocks/', json=block_config)

    if response.status_code in [200, 201]:
        block_data = response.json()
        block_id = block_data['id']
        print(f'✅ Created message_queue block: {block_id}')

        # Save to blocks file
        blocks_file = Path(__file__).parent / 'shared_memory_blocks.json'
        if blocks_file.exists():
            with open(blocks_file) as f:
                blocks = json.load(f)
        else:
            blocks = {}

        blocks['message_queue'] = block_id

        with open(blocks_file, 'w') as f:
            json.dump(blocks, f, indent=2)

        print(f'✅ Saved block ID to {blocks_file}')
        return block_id
    else:
        print(f'❌ Failed to create block: {response.status_code}')
        print(response.text)
        return None


def attach_to_all_agents(block_id):
    """Attach message_queue block to all agents."""
    agent_ids = {
        'thoth_main_orchestrator': 'agent-10418b8d-37a5-4923-8f70-69ccc58d66ff',
        'system_citation_analyzer': 'agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5',
        'system_discovery_scout': 'agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64',
        'system_analysis_expert': 'agent-8a4183a6-fffc-4082-b40b-aab29727a3ab',
    }

    for agent_name, agent_id in agent_ids.items():
        # Get current blocks
        response = requests.get(f'{API_BASE}/agents/{agent_id}')
        if response.status_code != 200:
            print(f'❌ Failed to get agent {agent_name}: {response.status_code}')
            continue

        agent_data = response.json()
        current_block_ids = [
            b['id'] for b in agent_data.get('memory', {}).get('blocks', [])
        ]

        # Add message_queue if not already attached
        if block_id not in current_block_ids:
            new_block_ids = current_block_ids + [block_id]

            update = {'block_ids': new_block_ids}
            response = requests.patch(f'{API_BASE}/agents/{agent_id}', json=update)

            if response.status_code == 200:
                print(f'✅ Attached message_queue to {agent_name}')
            else:
                print(f'❌ Failed to attach to {agent_name}: {response.status_code}')
        else:
            print(f'ℹ️  {agent_name} already has message_queue attached')


if __name__ == '__main__':
    print('Creating message queue shared memory block...\n')
    block_id = create_message_queue_block()

    if block_id:
        print('\nAttaching to all agents...\n')
        attach_to_all_agents(block_id)
        print('\n✅ Message queue setup complete!')
    else:
        print('\n❌ Failed to create message queue')
