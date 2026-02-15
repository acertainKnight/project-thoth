#!/usr/bin/env python3
"""
Check if Letta can see the agentic_research_question tool from the MCP server.

Run this to diagnose the tool registration issue:
    python scripts/debug_letta_tools.py
"""

import json
import os

import requests

# Letta configuration
LETTA_URL = os.environ.get('LETTA_URL', 'http://localhost:8283')
LETTA_TOKEN = os.environ.get('LETTA_TOKEN', 'letta_dev_password')  # nosec B105


def get_headers():
    """Get request headers with auth token."""
    return {
        'Authorization': f'Bearer {LETTA_TOKEN}',
        'Content-Type': 'application/json',
    }


def main():
    print('=' * 70)
    print('LETTA TOOL DISCOVERY DIAGNOSTIC')
    print('=' * 70)

    # 1. Check if Letta is running
    print('\n1. Checking Letta server status...')
    try:
        resp = requests.get(f'{LETTA_URL}/v1/health', timeout=5)
        if resp.status_code == 200:
            print(f'   ✓ Letta server is running at {LETTA_URL}')
        else:
            print(f'   ⚠ Letta returned status {resp.status_code}')
    except requests.exceptions.ConnectionError:
        print(f'   ✗ Cannot connect to Letta at {LETTA_URL}')
        print('   Make sure Letta server is running: docker-compose up letta')
        return
    except Exception as e:
        print(f'   ✗ Error: {e}')
        return

    # 2. List all tools
    print('\n2. Fetching all tools from Letta...')
    try:
        resp = requests.get(
            f'{LETTA_URL}/v1/tools/?limit=500', headers=get_headers(), timeout=30
        )

        if resp.status_code != 200:
            print(f'   ✗ Failed to fetch tools: HTTP {resp.status_code}')
            print(f'   Response: {resp.text}')
            return

        tools = resp.json()
        print(f'   ✓ Found {len(tools)} total tools')

        # 3. Check for MCP tools
        mcp_tools = [
            t
            for t in tools
            if 'mcp' in json.dumps(t.get('tags', [])).lower()
            or 'thoth' in t.get('name', '').lower()
            or t.get('source_type') == 'mcp'
        ]

        print(f'\n3. MCP/Thoth tools: {len(mcp_tools)} found')
        if mcp_tools:
            for tool in mcp_tools[:10]:  # Show first 10
                print(f'     - {tool.get("name")}')
        else:
            print('     ⚠ No MCP tools found!')
            print(
                '     This suggests the MCP server is not properly connected to Letta'
            )

        # 4. Search specifically for agentic_research_question
        print("\n4. Searching for 'agentic_research_question'...")
        agentic_tools = [t for t in tools if 'agentic' in t.get('name', '').lower()]

        if agentic_tools:
            print(f'   ✓ Found {len(agentic_tools)} agentic tool(s):')
            for tool in agentic_tools:
                name = tool.get('name')
                tool_id = tool.get('id')
                source = tool.get('source_type', 'unknown')
                print(f'     - {name}')
                print(f'       ID: {tool_id}')
                print(f'       Source: {source}')

                if name == 'agentic_research_question':
                    print('       ✓✓✓ THIS IS THE TOOL WE NEED ✓✓✓')
        else:
            print("   ✗ 'agentic_research_question' NOT FOUND")
            print('\n   Possible causes:')
            print('   a) MCP server not running')
            print('   b) MCP server not registered with Letta')
            print('   c) MCP server registered but not properly connected')
            print('   d) Tool registration failed during MCP startup')

        # 5. Check for answer_research_question (should exist)
        print("\n5. Checking for 'answer_research_question' (baseline check)...")
        answer_tools = [t for t in tools if t.get('name') == 'answer_research_question']
        if answer_tools:
            print('   ✓ Found answer_research_question')
            print(f'     Source: {answer_tools[0].get("source_type")}')
        else:
            print('   ✗ answer_research_question also missing!')
            print("   This suggests MCP tools aren't being discovered at all")

        # 6. List all research-related tools
        print('\n6. All research/question-related tools:')
        research_tools = [
            t
            for t in tools
            if any(
                kw in t.get('name', '').lower()
                for kw in ['research', 'question', 'answer', 'article']
            )
        ]
        for tool in sorted(research_tools, key=lambda t: t.get('name', ''))[:20]:
            name = tool.get('name')
            source = tool.get('source_type', '?')
            print(f'     - {name:<40} [{source}]')

    except Exception as e:
        print(f'   ✗ Error: {e}')
        import traceback

        traceback.print_exc()
        return

    print('\n' + '=' * 70)
    print('DIAGNOSTIC COMPLETE')
    print('=' * 70)


if __name__ == '__main__':
    main()
