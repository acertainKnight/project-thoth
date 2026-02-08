#!/usr/bin/env python3
"""
Test all 46 MCP tools to identify which ones are working and which are broken.
"""

import sys

import requests

BASE_URL = 'http://localhost:8283'
HEADERS = {
    'Authorization': 'Bearer letta_dev_password',
    'Content-Type': 'application/json',
}

# Test agent with all tools
TEST_AGENT_ID = 'agent-02e9a5db-c6f2-4c24-934e-3e8039a6accf'  # Document Librarian


def get_all_mcp_tools():
    """Get all MCP tools from database."""
    import subprocess

    result = subprocess.run(
        [
            'docker',
            'exec',
            'thoth-letta-postgres',
            'psql',
            '-U',
            'letta',
            '-d',
            'letta',
            '-t',
            '-c',
            "SELECT name FROM tools WHERE tool_type = 'external_mcp' ORDER BY name;",
        ],
        capture_output=True,
        text=True,
    )

    tools = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    return tools


# Tool categories with safe test parameters
TOOL_TESTS = {
    # Discovery tools (9)
    'create_arxiv_source': {'name': 'test-arxiv', 'categories': ['cs.AI']},
    'create_biorxiv_source': {'name': 'test-biorxiv', 'subject': 'bioinformatics'},
    'create_crossref_source': {'name': 'test-crossref', 'query': 'machine learning'},
    'create_openalex_source': {'name': 'test-openalex', 'query': 'AI'},
    'create_pubmed_source': {'name': 'test-pubmed', 'query': 'neuroscience'},
    'list_discovery_sources': {},
    'get_discovery_source': {'name': 'test-source'},  # Will fail if doesn't exist
    'delete_discovery_source': {'name': 'test-arxiv'},  # Cleanup
    'run_discovery': {'name': 'test-arxiv', 'max_results': 1},
    # PDF Management (6)
    'download_pdf': {'doi': '10.1234/test'},  # Will fail - test DOI
    'locate_pdf': {'doi': '10.1234/test'},
    'process_pdf': {'pdf_path': '/vault/test.pdf'},  # Will fail if doesn't exist
    'batch_process_pdfs': {'pdf_dir': '/vault/Research'},
    'extract_pdf_metadata': {'pdf_path': '/vault/test.pdf'},
    'validate_pdf_sources': {},
    # Article Management (7)
    'list_articles': {'limit': 5},
    'search_articles': {'query': 'test', 'limit': 5},
    'get_article_details': {'article_id': 'test-id'},  # Will fail
    'update_article_metadata': {'article_id': 'test-id', 'metadata': {}},
    'delete_article': {'article_id': 'test-id'},
    'evaluate_article': {'article_id': 'test-id'},
    'export_article_data': {'format': 'json'},
    # Citation tools (4)
    'extract_citations': {'text': 'Smith et al. (2020) showed that...'},
    'format_citations': {'citations': [], 'style': 'apa'},
    'export_bibliography': {'format': 'bibtex'},
    'find_related_papers': {'doi': '10.1234/test'},
    # Analysis tools (3)
    'analyze_topic': {'topic': 'machine learning', 'max_papers': 5},
    'generate_reading_list': {'topic': 'AI', 'max_papers': 5},
    'generate_research_summary': {'topic': 'neural networks'},
    # Query Management (5)
    'create_query': {'name': 'test-query', 'description': 'Test query'},
    'get_query': {'query_id': 'test-query-id'},  # Will fail
    'list_queries': {},
    'update_query': {'query_id': 'test-id', 'updates': {}},
    'delete_query': {'query_id': 'test-id'},
    # Organization (4)
    'consolidate_tags': {},
    'consolidate_and_retag': {},
    'suggest_tags': {'text': 'machine learning paper'},
    'manage_tag_vocabulary': {'action': 'list'},
    # Collection Management (5)
    'collection_stats': {},
    'backup_collection': {'backup_path': '/vault/_thoth/backups/test'},
    'reindex_collection': {},
    'optimize_search': {},
    'create_custom_index': {'field': 'title'},
    # System (2)
    'memory_stats': {},
    'memory_health_check': {},
    # Integration (1)
    'sync_with_obsidian': {},
}


def test_tool(tool_name, params):
    """Test a single MCP tool by calling it via MCP server."""
    try:
        # Call MCP server directly
        mcp_url = 'http://localhost:8082'
        response = requests.post(
            f'{mcp_url}/call', json={'tool': tool_name, 'arguments': params}, timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            if result.get('success') or result.get('status') == 'ok':
                return True, 'OK', result
            else:
                return False, result.get('error', 'Unknown error'), result
        else:
            return False, f'HTTP {response.status_code}', response.text

    except requests.exceptions.Timeout:
        return False, 'Timeout (>10s)', None
    except Exception as e:
        return False, str(e), None


def main():
    print('=' * 80)
    print('COMPREHENSIVE MCP TOOL TEST')
    print('=' * 80)
    print()

    # Get all tools from database
    all_tools = get_all_mcp_tools()
    print(f'Found {len(all_tools)} MCP tools in database')
    print()

    # Test each tool
    results = {'passed': [], 'failed': [], 'untested': []}

    for i, tool_name in enumerate(all_tools, 1):
        print(f'[{i}/{len(all_tools)}] Testing {tool_name}...', end=' ')

        if tool_name in TOOL_TESTS:
            params = TOOL_TESTS[tool_name]
            success, message, data = test_tool(tool_name, params)

            if success:
                print('✓ PASS')
                results['passed'].append(tool_name)
            else:
                print(f'✗ FAIL: {message}')
                results['failed'].append((tool_name, message))
        else:
            print('⚠ UNTESTED (no test params)')
            results['untested'].append(tool_name)

    # Summary
    print()
    print('=' * 80)
    print('TEST RESULTS SUMMARY')
    print('=' * 80)
    print()
    print(f'✓ PASSED:  {len(results["passed"])}/{len(all_tools)}')
    print(f'✗ FAILED:  {len(results["failed"])}/{len(all_tools)}')
    print(f'⚠ UNTESTED: {len(results["untested"])}/{len(all_tools)}')
    print()

    if results['failed']:
        print('FAILED TOOLS:')
        for tool, error in results['failed']:
            print(f'  - {tool}: {error}')
        print()

    if results['untested']:
        print('UNTESTED TOOLS:')
        for tool in results['untested']:
            print(f'  - {tool}')
        print()

    # Exit code
    sys.exit(0 if len(results['failed']) == 0 else 1)


if __name__ == '__main__':
    main()
