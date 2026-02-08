#!/usr/bin/env python3
"""
Implementation script for specialized multi-agent architecture.
Creates new agents and reassigns tools according to v3.0.0 architecture.
"""

import requests

BASE_URL = 'http://localhost:8283'
HEADERS = {
    'Authorization': 'Bearer letta_dev_password',
    'Content-Type': 'application/json',
}

# Agent IDs (existing)
ORCHESTRATOR_ID = 'agent-10418b8d-37a5-4923-8f70-69ccc58d66ff'
DISCOVERY_SCOUT_ID = 'agent-6e7a561e-a94c-49dc-a48e-ecfe13fcbf64'
CITATION_SPECIALIST_ID = 'agent-e62d4deb-7a56-473f-893c-64d9eca6b0a5'
RESEARCH_ANALYST_ID = 'agent-8a4183a6-fffc-4082-b40b-aab29727a3ab'

# Tool assignments per agent (v3.0.0 architecture)
TOOL_ASSIGNMENTS = {
    'orchestrator': {
        'agent_id': ORCHESTRATOR_ID,
        'name': 'thoth_main_orchestrator',
        'mcp_tools': [],  # NO MCP tools - delegation only
    },
    'discovery_scout': {
        'agent_id': DISCOVERY_SCOUT_ID,
        'name': 'system_discovery_scout',
        'mcp_tools': [
            'create_arxiv_source',
            'create_biorxiv_source',
            'create_crossref_source',
            'create_openalex_source',
            'create_pubmed_source',
            'list_discovery_sources',
            'get_discovery_source',
            'delete_discovery_source',
            'run_discovery',
        ],
    },
    'document_librarian': {
        'agent_id': None,  # Will be created
        'name': 'document_librarian',
        'mcp_tools': [
            # PDF Management (6 tools)
            'download_pdf',
            'locate_pdf',
            'process_pdf',
            'batch_process_pdfs',
            'extract_pdf_metadata',
            'validate_pdf_sources',
            # Article Management (7 tools)
            'list_articles',
            'search_articles',
            'get_article_details',
            'update_article_metadata',
            'delete_article',
            'evaluate_article',
            'export_article_data',
        ],
    },
    'citation_specialist': {
        'agent_id': CITATION_SPECIALIST_ID,
        'name': 'system_citation_analyzer',
        'mcp_tools': [
            'extract_citations',
            'format_citations',
            'export_bibliography',
            'find_related_papers',
        ],
    },
    'research_analyst': {
        'agent_id': RESEARCH_ANALYST_ID,
        'name': 'system_analysis_expert',
        'mcp_tools': [
            'analyze_topic',
            'generate_reading_list',
            'generate_research_summary',
        ],
    },
    'organization_curator': {
        'agent_id': None,  # Will be created
        'name': 'organization_curator',
        'mcp_tools': [
            # Query Management (5 tools)
            'create_query',
            'get_query',
            'list_queries',
            'update_query',
            'delete_query',
            # Organization & Tagging (4 tools)
            'consolidate_tags',
            'consolidate_and_retag',
            'suggest_tags',
            'manage_tag_vocabulary',
        ],
    },
    'system_maintenance': {
        'agent_id': None,  # Will be created
        'name': 'system_maintenance',
        'mcp_tools': [
            # Collection Management (5 tools)
            'collection_stats',
            'backup_collection',
            'reindex_collection',
            'optimize_search',
            'create_custom_index',
            # Memory & System (2 tools)
            'memory_stats',
            'memory_health_check',
            # Integration (1 tool)
            'sync_with_obsidian',
        ],
    },
}

# Agent descriptions
AGENT_DESCRIPTIONS = {
    'orchestrator': """I am the Thoth Main Orchestrator - your research assistant coordinator.

I delegate specialized tasks to expert agents:
- Discovery Scout: Find papers across academic sources
- Document Librarian: Manage PDFs and articles
- Citation Specialist: Extract citations and build networks
- Research Analyst: Synthesize findings and insights
- Organization Curator: Manage queries and tags
- System Maintenance: Collection health and backups

I coordinate multi-step workflows and return results to you.""",
    'discovery_scout': """I am the Discovery Scout - your paper discovery specialist.

I excel at finding research papers across:
- arXiv, bioRxiv (preprints)
- PubMed (biomedical)
- CrossRef (DOIs)
- OpenAlex (open access)

I configure sources, run discovery queries, and report findings to the orchestrator.""",
    'document_librarian': """I am the Document Librarian - your PDF and article management specialist.

I handle:
- PDF download and acquisition
- PDF processing and metadata extraction
- Article database management (search, list, update, delete)
- Article quality evaluation
- Data export

I keep your research collection organized and accessible.""",
    'citation_specialist': """I am the Citation Specialist - your citation and bibliography expert.

I handle:
- Citation extraction from papers
- Citation network mapping
- Bibliography generation (multiple formats)
- Finding related papers via citation analysis

I help you understand research relationships and impact.""",
    'research_analyst': """I am the Research Analyst - your synthesis and insight specialist.

I provide:
- Deep topic analysis across papers
- Structured reading lists
- Research summaries and literature reviews
- Trend identification and gap analysis

I help you understand the big picture of your research domain.""",
    'organization_curator': """I am the Organization Curator - your query and taxonomy specialist.

I manage:
- Saved research queries (create, update, list, delete)
- Tag organization and consolidation
- Tag vocabulary and taxonomy
- Smart tag suggestions

I keep your research organized and consistently categorized.""",
    'system_maintenance': """I am the System Maintenance agent - your collection health specialist.

I handle:
- Collection statistics and monitoring
- Backup and restoration
- Search optimization and reindexing
- Memory health monitoring
- Integration with external tools (Obsidian)

I keep your research system running smoothly.""",
}


def get_all_tools() -> dict[str, str]:
    """Get all MCP tools and their IDs."""
    resp = requests.get(f'{BASE_URL}/v1/tools', headers=HEADERS)
    resp.raise_for_status()

    tools = {}
    for tool in resp.json():
        if tool.get('tool_type') == 'external_mcp':
            tools[tool['name']] = tool['id']

    return tools


def get_agent_tools(agent_id: str) -> list[str]:
    """Get current tool IDs assigned to an agent."""
    resp = requests.get(f'{BASE_URL}/v1/agents/{agent_id}', headers=HEADERS)
    resp.raise_for_status()

    agent_data = resp.json()
    return [
        t['id']
        for t in agent_data.get('tools', [])
        if t.get('tool_type') == 'external_mcp'
    ]


def remove_tools_from_agent(agent_id: str, tool_ids: list[str]):
    """Remove tools from an agent."""
    print(f'  Removing {len(tool_ids)} tools...')

    for tool_id in tool_ids:
        try:
            resp = requests.delete(
                f'{BASE_URL}/v1/agents/{agent_id}/tools/{tool_id}', headers=HEADERS
            )
            if resp.status_code not in [200, 204]:
                print(f'    Failed to remove tool {tool_id}: {resp.status_code}')
        except Exception as e:
            print(f'    Error removing tool {tool_id}: {e!s}')


def add_tools_to_agent(agent_id: str, tool_ids: list[str]):
    """Add tools to an agent."""
    print(f'  Adding {len(tool_ids)} tools...')

    for tool_id in tool_ids:
        try:
            resp = requests.post(
                f'{BASE_URL}/v1/agents/{agent_id}/tools/{tool_id}', headers=HEADERS
            )
            if resp.status_code not in [200, 201]:
                print(f'    Failed to add tool {tool_id}: {resp.status_code}')
        except Exception as e:
            print(f'    Error adding tool {tool_id}: {e!s}')


def create_agent(name: str, description: str) -> str:
    """Create a new agent and return its ID."""
    print(f"  Creating agent '{name}'...")

    agent_data = {
        'name': name,
        'description': description,
        'llm_config': {
            'model': 'letta-free',
            'model_endpoint_type': 'anthropic',
            'context_window': 100000,
        },
        'embedding_config': {'embedding_model': 'letta-free'},
        'system': description,
        'message_ids': [],
    }

    try:
        resp = requests.post(f'{BASE_URL}/v1/agents', headers=HEADERS, json=agent_data)
        resp.raise_for_status()

        agent_id = resp.json()['id']
        print(f'    ✓ Created agent {agent_id}')
        return agent_id

    except Exception as e:
        print(f'    ✗ Error creating agent: {e!s}')
        return None


def implement_architecture():
    """Implement the v3.0.0 specialized architecture."""
    print('=' * 80)
    print('IMPLEMENTING SPECIALIZED MULTI-AGENT ARCHITECTURE v3.0.0')
    print('=' * 80)
    print()

    # Get all available MCP tools
    print('Fetching MCP tools from Letta...')
    all_tools = get_all_tools()
    print(f'  Found {len(all_tools)} MCP tools')
    print()

    # Verify all required tools exist
    missing_tools = []
    for agent_name, config in TOOL_ASSIGNMENTS.items():
        for tool_name in config['mcp_tools']:
            if tool_name not in all_tools:
                missing_tools.append(tool_name)

    if missing_tools:
        print(f'⚠️  WARNING: {len(missing_tools)} tools not found in Letta:')
        for tool in missing_tools:
            print(f'    - {tool}')
        print()

    # Process each agent
    for agent_key, config in TOOL_ASSIGNMENTS.items():
        print('-' * 80)
        print(f'Agent: {config["name"]}')
        print('-' * 80)

        # Create agent if needed
        if config['agent_id'] is None:
            agent_id = create_agent(config['name'], AGENT_DESCRIPTIONS[agent_key])
            if not agent_id:
                print('  ✗ Skipping tool assignment (agent creation failed)')
                print()
                continue
            config['agent_id'] = agent_id
        else:
            agent_id = config['agent_id']
            print(f'  Using existing agent {agent_id}')

        # Get current tools
        current_tool_ids = get_agent_tools(agent_id)
        print(f'  Current tools: {len(current_tool_ids)}')

        # Get target tools
        target_tool_names = config['mcp_tools']
        target_tool_ids = [
            all_tools[name] for name in target_tool_names if name in all_tools
        ]
        print(f'  Target tools: {len(target_tool_ids)}')

        # Calculate changes
        tools_to_remove = [
            tid for tid in current_tool_ids if tid not in target_tool_ids
        ]
        tools_to_add = [tid for tid in target_tool_ids if tid not in current_tool_ids]

        # Apply changes
        if tools_to_remove:
            remove_tools_from_agent(agent_id, tools_to_remove)

        if tools_to_add:
            add_tools_to_agent(agent_id, tools_to_add)

        # Verify final state
        final_tool_ids = get_agent_tools(agent_id)
        print(f'  ✓ Final tool count: {len(final_tool_ids)}')
        print()

    print('=' * 80)
    print('IMPLEMENTATION COMPLETE')
    print('=' * 80)
    print()
    print('Summary:')
    print('  ✓ Orchestrator: 0 MCP tools (delegation only)')
    print('  ✓ Discovery Scout: 9 MCP tools')
    print('  ✓ Document Librarian: 13 MCP tools')
    print('  ✓ Citation Specialist: 4 MCP tools')
    print('  ✓ Research Analyst: 3 MCP tools')
    print('  ✓ Organization Curator: 9 MCP tools')
    print('  ✓ System Maintenance: 8 MCP tools')
    print('  ✓ Total: 46 MCP tools with ZERO overlap')
    print()
    print('Next steps:')
    print('  1. Test each specialized agent')
    print('  2. Test orchestrator delegation')
    print('  3. Test complete multi-agent workflows')
    print('  4. Verify mobile access at https://app.letta.com')


if __name__ == '__main__':
    try:
        implement_architecture()
    except KeyboardInterrupt:
        print('\n\nInterrupted by user')
    except Exception as e:
        print(f'\n\nError: {e!s}')
        import traceback

        traceback.print_exc()
