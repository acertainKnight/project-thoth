#!/usr/bin/env python3
"""
Restore Letta agents from backup with full memory blocks.

Usage:
    python3 restore-agents.py <backup_dir> <letta_url>

Example:
    python3 restore-agents.py ~/letta-backup-20260117 http://localhost:8283
"""

import glob
import json
import os
import sys

import requests


def restore_agents(backup_dir, letta_url):
    """Restore all agents from backup directory with full memory blocks."""
    if not os.path.isdir(backup_dir):
        print(f'Error: Backup directory not found: {backup_dir}')
        return False

    # Find all agent backup files
    backup_files = glob.glob(f'{backup_dir}/agent-*.json')

    if not backup_files:
        print(f'Error: No agent backups found in {backup_dir}')
        return False

    print(f'Found {len(backup_files)} agent backups\n')

    restored = []
    failed = []

    for backup_file in sorted(backup_files):
        try:
            with open(backup_file) as f:
                agent_data = json.load(f)

            agent_name = agent_data.get('name', 'Unknown')
            original_blocks = agent_data.get('blocks', [])

            # Convert blocks to memory_blocks format (as per Letta API spec)
            # Only include: label, value, and optional fields (limit, description, metadata)
            memory_blocks = []
            for block in original_blocks:
                memory_block = {
                    'label': block.get('label'),
                    'value': block.get('value'),
                }

                # Add optional fields if present
                if 'limit' in block:
                    memory_block['limit'] = block['limit']
                if block.get('description'):
                    memory_block['description'] = block['description']
                if block.get('metadata'):
                    memory_block['metadata'] = block['metadata']

                memory_blocks.append(memory_block)

            print(f'Restoring: {agent_name}')
            print(f'  Blocks: {len(memory_blocks)}')

            # Skip agents with invalid names (e.g., containing "/")
            if '/' in agent_name:
                print("  ⊘ Skipping: Name contains invalid character '/'")
                failed.append(agent_name)
                continue

            # Create agent with memory_blocks parameter
            payload = {
                'name': agent_data['name'],
                'description': agent_data.get('description'),
                'system': agent_data.get('system'),
                'agent_type': agent_data.get('agent_type'),
                'llm_config': agent_data.get('llm_config'),
                'embedding_config': agent_data.get('embedding_config'),
                'memory_blocks': memory_blocks,  # Proper parameter name per API docs
            }

            resp = requests.post(f'{letta_url}/v1/agents/', json=payload, timeout=120)

            if resp.status_code in [200, 201]:
                new_agent = resp.json()
                new_id = new_agent['id']

                # Verify memory blocks were restored
                blocks_in_memory = new_agent.get('memory', {}).get('blocks', [])
                blocks_at_top = new_agent.get('blocks', [])
                actual_block_count = (
                    len(blocks_in_memory) if blocks_in_memory else len(blocks_at_top)
                )

                print(f'  ✓ Created: {new_id}')
                print(f'  ✓ Memory: {actual_block_count}/{len(memory_blocks)} blocks')

                if actual_block_count > 0:
                    restored.append((agent_name, new_id, actual_block_count))
                else:
                    print('  ⚠️  WARNING: No memory blocks in response')
                    failed.append(agent_name)
            else:
                error = (
                    resp.json().get('detail', resp.text)[:200]
                    if resp.headers.get('content-type', '').startswith(
                        'application/json'
                    )
                    else resp.text[:200]
                )
                print(f'  ✗ Failed: {error}')
                failed.append(agent_name)

        except Exception as e:
            print(f'  ✗ Error: {str(e)[:100]}')
            failed.append(agent_name)

        print()

    # Summary
    print('=' * 70)
    if restored:
        print(f'✅ Successfully restored: {len(restored)} agents\n')
        for name, new_id, block_count in restored:
            print(f'  • {name}: {new_id} ({block_count} blocks)')
    else:
        print('❌ No agents were successfully restored')

    if failed:
        print(f'\n❌ Failed: {len(failed)} agents')
        for name in failed:
            print(f'  • {name}')

    print('=' * 70)

    return len(restored) > 0


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    backup_dir = os.path.expanduser(sys.argv[1])
    letta_url = sys.argv[2]

    success = restore_agents(backup_dir, letta_url)
    sys.exit(0 if success else 1)
