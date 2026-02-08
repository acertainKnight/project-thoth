#!/usr/bin/env python3
"""
Complete Letta agent restoration from backup with full data preservation.

Restores:
- Memory blocks (custom memory with project knowledge)
- Tool rules (tool execution policies)
- Tags (agent categorization)
- System prompt (agent personality and instructions)
- Configuration (llm_config, embedding_config, model_settings)
- Server-side tools (only tools available on Letta server)

Does NOT restore:
- Client-side tools (Edit, Write, Bash, etc.) - provided by Letta Code at runtime
- Message history (message_ids) - would require message recreation API
- Conversation state - would need message restoration

Usage:
    python3 restore-agents-complete.py <backup_dir> <letta_url> [agent_names...]

Examples:
    # Restore all agents
    python3 restore-agents-complete.py ~/letta-backup-20260117 http://localhost:8283

    # Restore specific agents
    python3 restore-agents-complete.py ~/letta-backup-20260117 http://localhost:8283 "Lead Engineer" thoth_main_orchestrator
"""

import glob
import json
import os
import sys

import requests


def clean_block_for_api(block):
    """Convert backup block to API-compatible memory_block format."""
    # Strip auto-generated fields
    strip_fields = [
        'id',
        'created_by_id',
        'last_updated_by_id',
        'created_at',
        'updated_at',
    ]

    cleaned = {
        'label': block.get('label'),
        'value': block.get('value'),
    }

    # Add optional fields if present
    for field in ['limit', 'description', 'metadata', 'read_only']:
        if field in block and block[field] is not None:
            cleaned[field] = block[field]

    return cleaned


def filter_server_tools(tools, letta_url):
    """
    Filter tools to only include those available on the Letta server.
    Client-side tools (Edit, Write, Bash, etc.) are provided by Letta Code at runtime.
    """
    try:
        # Get available tools from server
        resp = requests.get(f'{letta_url}/v1/tools/', timeout=10)
        if resp.status_code != 200:
            return []

        server_tools = {t['name'] for t in resp.json()}

        # Filter backup tools to only server-available ones
        filtered = []
        for tool in tools:
            tool_name = None
            if isinstance(tool, str):
                tool_name = tool
            elif isinstance(tool, dict):
                tool_name = tool.get('name') or tool.get('json_schema', {}).get('name')

            if tool_name and tool_name in server_tools:
                filtered.append(tool_name)

        return filtered
    except Exception:
        return []


def get_thoth_mcp_server_id(letta_url):
    """
    Get the ID of the Thoth MCP server from Letta.
    Returns None if not found.
    """
    try:
        resp = requests.get(f'{letta_url}/v1/mcp-servers/', timeout=10)
        if resp.status_code == 200:
            servers = resp.json()
            for server in servers:
                if server.get('server_name') == 'thoth-research-tools':
                    return server.get('id')
        return None
    except Exception:
        return None


def attach_mcp_server_to_agent(agent_id, mcp_server_id, letta_url):
    """
    Attach an MCP server to an agent.
    Returns True if successful, False otherwise.
    """
    try:
        resp = requests.patch(
            f'{letta_url}/v1/agents/{agent_id}',
            json={'mcp_server_ids': [mcp_server_id]},
            timeout=10,
        )
        return resp.status_code in [200, 201]
    except Exception:
        return False


def restore_agent(backup_file, letta_url, delete_existing=True):
    """
    Restore a single agent from backup with complete data.

    Returns: (success: bool, agent_name: str, new_id: str, restored_data: dict)
    """
    try:
        with open(backup_file) as f:
            agent_data = json.load(f)
    except Exception as e:
        return False, 'unknown', None, {'error': f'Failed to read backup: {e}'}

    agent_name = agent_data.get('name', 'Unknown')

    # Skip agents with invalid names
    if '/' in agent_name:
        return False, agent_name, None, {'error': "Name contains invalid character '/'"}

    # Prepare memory blocks
    original_blocks = agent_data.get('blocks', [])
    memory_blocks = [clean_block_for_api(b) for b in original_blocks]

    # Prepare tools - filter to only server-available tools
    # Note: Client-side tools (Edit, Write, Bash, etc.) are provided by Letta Code at runtime
    original_tools = agent_data.get('tools', [])
    tools = filter_server_tools(original_tools, letta_url)

    # Prepare tool rules
    tool_rules = agent_data.get('tool_rules', [])

    # Prepare tags
    tags = agent_data.get('tags', [])

    # Delete existing agent with same name if requested
    if delete_existing:
        try:
            existing_agents = requests.get(
                f'{letta_url}/v1/agents/?limit=1000', timeout=10
            ).json()
            for existing in existing_agents:
                if existing['name'] == agent_name:
                    requests.delete(
                        f'{letta_url}/v1/agents/{existing["id"]}', timeout=10
                    )
                    break
        except Exception:
            pass

    # Create comprehensive payload
    payload = {
        'name': agent_data['name'],
        'agent_type': agent_data.get('agent_type'),
        'llm_config': agent_data.get('llm_config'),
        'embedding_config': agent_data.get('embedding_config'),
        'memory_blocks': memory_blocks,
        'system': agent_data.get('system'),
        'tools': tools,
        'tool_rules': tool_rules,
        'tags': tags,
    }

    # Add optional fields if present
    optional_fields = [
        'description',
        'model_settings',
        'enable_sleeptime',
        'message_buffer_autoclear',
        'timezone',
        'max_files_open',
        'per_file_view_window_char_limit',
    ]
    for field in optional_fields:
        if field in agent_data and agent_data[field] is not None:
            payload[field] = agent_data[field]

    # Create agent
    try:
        resp = requests.post(f'{letta_url}/v1/agents/', json=payload, timeout=120)

        if resp.status_code not in [200, 201]:
            error = (
                resp.json().get('detail', resp.text)[:200]
                if resp.headers.get('content-type', '').startswith('application/json')
                else resp.text[:200]
            )
            return False, agent_name, None, {'error': error, 'status': resp.status_code}

        new_agent = resp.json()
        new_id = new_agent['id']

        # Attach Thoth MCP server (if available)
        mcp_attached = False
        thoth_mcp_id = get_thoth_mcp_server_id(letta_url)
        if thoth_mcp_id:
            mcp_attached = attach_mcp_server_to_agent(new_id, thoth_mcp_id, letta_url)

        # Verify what was restored
        restored_data = {
            'memory_blocks': f'{len(new_agent.get("memory", {}).get("blocks", []))}/{len(memory_blocks)}',
            'tools': f'{len(new_agent.get("tools", []))}/{len(tools)}',
            'tool_rules': f'{len(new_agent.get("tool_rules", []))}/{len(tool_rules)}',
            'tags': f'{len(new_agent.get("tags", []))}/{len(tags)}',
            'system_prompt': len(new_agent.get('system', '')),
            'mcp_server': '✓' if mcp_attached else '✗',
        }

        return True, agent_name, new_id, restored_data

    except Exception as e:
        return False, agent_name, None, {'error': str(e)[:200]}


def restore_agents(backup_dir, letta_url, filter_names=None):
    """
    Restore all or specific agents from backup directory.

    Args:
        backup_dir: Path to backup directory
        letta_url: Letta server URL
        filter_names: Optional list of agent names to restore (None = restore all)

    Returns: (restored_count, failed_count, results)
    """
    if not os.path.isdir(backup_dir):
        print(f'Error: Backup directory not found: {backup_dir}')
        return 0, 0, []

    backup_files = glob.glob(f'{backup_dir}/agent-*.json')

    if not backup_files:
        print(f'Error: No agent backups found in {backup_dir}')
        return 0, 0, []

    # Filter by names if specified
    files_to_restore = []
    if filter_names:
        filter_set = set(filter_names)
        for fpath in backup_files:
            try:
                with open(fpath) as f:
                    agent = json.load(f)
                if agent.get('name') in filter_set:
                    files_to_restore.append(fpath)
            except Exception:
                continue
    else:
        files_to_restore = backup_files

    print(f'Found {len(files_to_restore)} agent(s) to restore\n')

    restored = []
    failed = []

    for backup_file in sorted(files_to_restore):
        success, agent_name, new_id, data = restore_agent(backup_file, letta_url)

        if success:
            print(f'✓ {agent_name}')
            print(f'  ID: {new_id}')
            print(f'  Memory blocks: {data["memory_blocks"]}')
            print(f'  Tools: {data["tools"]}')
            print(f'  Tool rules: {data["tool_rules"]}')
            print(f'  Tags: {data["tags"]}')
            print(f'  System prompt: {data["system_prompt"]} chars')
            print(f'  MCP server: {data["mcp_server"]} Thoth Research Tools')
            restored.append((agent_name, new_id, data))
        else:
            print(f'✗ {agent_name}')
            print(f'  Error: {data.get("error", "Unknown error")}')
            failed.append((agent_name, data))

        print()

    return len(restored), len(failed), (restored, failed)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    backup_dir = os.path.expanduser(sys.argv[1])
    letta_url = sys.argv[2]
    filter_names = sys.argv[3:] if len(sys.argv) > 3 else None

    print('=' * 70)
    print('Letta Agent Complete Restoration')
    print('=' * 70)
    print(f'Backup: {backup_dir}')
    print(f'Server: {letta_url}')
    if filter_names:
        print(f'Agents: {", ".join(filter_names)}')
    else:
        print('Agents: ALL')
    print('=' * 70)
    print()

    restored_count, failed_count, results = restore_agents(
        backup_dir, letta_url, filter_names
    )
    restored_list, failed_list = results

    # Summary
    print('=' * 70)
    print('RESTORATION SUMMARY')
    print('=' * 70)

    if restored_list:
        print(f'\n✅ Successfully restored: {restored_count} agent(s)\n')
        for name, agent_id, data in restored_list:
            print(f'  • {name}')
            print(f'    ID: {agent_id}')
            print(f'    Data: {data["memory_blocks"]} blocks, {data["tools"]} tools')

    if failed_list:
        print(f'\n❌ Failed: {failed_count} agent(s)\n')
        for name, data in failed_list:
            print(f'  • {name}: {data.get("error", "Unknown")}')

    print('\n' + '=' * 70)

    # Update settings reminder
    if restored_list:
        print('\n📝 Remember to update ~/.letta/settings.json if needed:')
        print('  "pinnedAgents": [')
        for name, agent_id, _ in restored_list[:4]:
            print(f'    "{agent_id}",  // {name}')
        print('  ]')

    return 0 if failed_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
