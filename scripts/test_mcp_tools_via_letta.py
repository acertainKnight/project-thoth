#!/usr/bin/env python3
"""
Test MCP tools by having a Letta agent actually call them.
This is the proper way to test since Letta manages the MCP connection.
"""

import time

import requests

BASE_URL = 'http://localhost:8283'
HEADERS = {
    'Authorization': 'Bearer letta_dev_password',
    'Content-Type': 'application/json',
}

# Use Document Librarian which has 13 tools
TEST_AGENT_ID = 'agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf'

# Simple, safe tests for each category
TEST_COMMANDS = {
    # Discovery (read-only list)
    'list_discovery_sources': 'List all discovery sources',
    # Articles (read-only)
    'list_articles': 'List the first 5 articles in the collection',
    'search_articles': "Search articles for 'machine learning' (limit 3 results)",
    # Collection stats (read-only)
    'collection_stats': 'Show me collection statistics',
    'memory_stats': 'Show memory statistics',
    'memory_health_check': 'Run a memory health check',
    # Query management (read-only list)
    'list_queries': 'List all saved queries',
    # Organization (read-only)
    'suggest_tags': "Suggest tags for the text: 'neural network deep learning'",
    # Citations (read-only)
    'export_bibliography': 'Export bibliography in BibTeX format',
    # PDF validation (read-only)
    'validate_pdf_sources': 'Validate PDF sources configuration',
}


def test_tool_via_agent(tool_name, command):
    """Test a tool by asking the agent to use it."""
    print(f'\nTesting: {tool_name}')
    print(f'Command: {command}')

    try:
        resp = requests.post(
            f'{BASE_URL}/v1/agents/{TEST_AGENT_ID}/messages',
            headers=HEADERS,
            json={'messages': [{'role': 'user', 'content': command}], 'stream': False},
            timeout=30,
        )

        if resp.status_code != 200:
            return False, f'HTTP {resp.status_code}', None

        data = resp.json()
        messages = data.get('messages', [])

        # Check if tool was called
        tool_calls = []
        errors = []

        for msg in messages:
            if msg.get('role') == 'tool':
                tool_calls.append(msg.get('name'))
            if 'Error' in str(msg.get('content', '')):
                errors.append(msg.get('content'))

        if tool_name in tool_calls:
            if errors:
                return False, f'Tool called but error: {errors[0][:100]}', tool_calls
            return True, 'Tool executed successfully', tool_calls
        else:
            return False, f'Tool not called. Called: {tool_calls}', None

    except requests.exceptions.Timeout:
        return False, 'Timeout (>30s)', None
    except Exception as e:
        return False, str(e), None


def main():
    print('=' * 80)
    print('MCP TOOL TEST VIA LETTA AGENT')
    print('=' * 80)
    print(f'Test Agent: {TEST_AGENT_ID} (Document Librarian)')
    print(f'Testing {len(TEST_COMMANDS)} tools')
    print()

    results = {'passed': [], 'failed': []}

    for tool_name, command in TEST_COMMANDS.items():
        success, message, data = test_tool_via_agent(tool_name, command)

        if success:
            print(f'✓ PASS: {tool_name}')
            results['passed'].append(tool_name)
        else:
            print(f'✗ FAIL: {tool_name}')
            print(f'  Error: {message}')
            results['failed'].append((tool_name, message))

        # Rate limit
        time.sleep(2)

    # Summary
    print()
    print('=' * 80)
    print('SUMMARY')
    print('=' * 80)
    print(f'✓ PASSED: {len(results["passed"])}/{len(TEST_COMMANDS)}')
    print(f'✗ FAILED: {len(results["failed"])}/{len(TEST_COMMANDS)}')

    if results['failed']:
        print('\nFAILED TOOLS:')
        for tool, error in results['failed']:
            print(f'  - {tool}: {error}')

    return len(results['failed']) == 0


if __name__ == '__main__':
    success = main()
    import sys

    sys.exit(0 if success else 1)
