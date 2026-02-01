"""
Agent Initialization Service - Auto-creates and updates Letta agents on startup.

This service ensures all required Thoth agents exist with proper configuration:
- Creates agents if missing
- Updates tools/functionality if changed
- Preserves agent memory and conversations
- Attaches filesystem folders for vault access
"""

import os
from typing import Dict, List, Optional

import httpx
from loguru import logger

from thoth.config import config


class AgentInitializationService:
    """Service to initialize and maintain Thoth agents in Letta."""

    def __init__(self):
        """Initialize the agent initialization service."""
        self.letta_base_url = os.getenv('LETTA_BASE_URL', 'http://localhost:8283')
        self.letta_api_key = os.getenv('LETTA_API_KEY', '')
        self.embedding_model = config.rag.embedding_model  # openai/text-embedding-3-small
        
        self.headers = {'Content-Type': 'application/json'}
        if self.letta_api_key:
            self.headers['Authorization'] = f'Bearer {self.letta_api_key}'

    # Agent definitions
    AGENT_CONFIGS = {
        'thoth_research_agent': {
            'name': 'thoth_research_agent',
            'description': """I am the Thoth Orchestrator - your main research assistant.

I coordinate with specialized sub-agents to handle all research tasks:
- Document discovery and acquisition
- PDF processing and analysis
- Citation extraction and organization
- Research query management
- Knowledge organization

I delegate tasks to specialists and synthesize results for you.""",
            'tools': [],  # Orchestrator uses send_message to delegate, no MCP tools
            'memory_blocks': [
                {
                    'label': 'research_context',
                    'value': 'Current research focus and active projects.',
                    'limit': 2000,
                    'description': 'Overall research context'
                },
                {
                    'label': 'user_preferences',
                    'value': 'User preferences and working style.',
                    'limit': 1000,
                    'description': 'User preferences and habits'
                }
            ]
        },
        'discovery_scout': {
            'name': 'discovery_scout',
            'description': """I am the Discovery Scout - your paper discovery specialist.

I handle:
- Research question creation and management
- Multi-source paper discovery (ArXiv, Semantic Scholar, etc.)
- Browser workflow automation
- Discovery scheduling
- Source configuration

I find relevant papers for your research.""",
            'tools': [
                'list_available_sources', 'create_research_question',
                'list_research_questions', 'get_research_question',
                'update_research_question', 'delete_research_question',
                'run_discovery_for_question', 'list_browser_workflows',
                'create_browser_workflow'
            ],
            'memory_blocks': [
                {
                    'label': 'discovery_context',
                    'value': 'Active research questions and discovery status.',
                    'limit': 1500,
                    'description': 'Discovery progress and context'
                }
            ]
        },
        'document_librarian': {
            'name': 'document_librarian',
            'description': """I am the Document Librarian - your PDF and article specialist.

I handle:
- PDF download and acquisition
- PDF processing and metadata extraction
- Article database management
- Article search and retrieval
- Data export

I keep your research collection organized.""",
            'tools': [
                'download_pdf', 'locate_pdf', 'process_pdf', 'batch_process_pdfs',
                'extract_pdf_metadata', 'validate_pdf_sources',
                'list_articles', 'search_articles', 'get_article_details',
                'update_article_metadata', 'delete_article', 'evaluate_article',
                'export_article_data'
            ],
            'memory_blocks': [
                {
                    'label': 'processing_queue',
                    'value': 'PDFs being processed.',
                    'limit': 1000,
                    'description': 'Current processing status'
                }
            ]
        },
        'citation_specialist': {
            'name': 'citation_specialist',
            'description': """I am the Citation Specialist - your citation analysis expert.

I handle:
- Citation extraction from papers
- Citation enrichment and resolution
- Citation network analysis
- Reference validation

I ensure accurate citation tracking.""",
            'tools': [
                'extract_citations', 'enrich_citations',
                'analyze_citation_network', 'validate_citations'
            ],
            'memory_blocks': [
                {
                    'label': 'citation_context',
                    'value': 'Citation analysis progress.',
                    'limit': 1000,
                    'description': 'Citation tracking'
                }
            ]
        },
        'research_analyst': {
            'name': 'research_analyst',
            'description': """I am the Research Analyst - your content analysis specialist.

I handle:
- Semantic search across your collection
- Content analysis and insights
- Advanced RAG queries

I help you understand and query your research.""",
            'tools': [
                'semantic_search', 'analyze_content', 'advanced_rag_query'
            ],
            'memory_blocks': [
                {
                    'label': 'analysis_context',
                    'value': 'Recent analysis results.',
                    'limit': 1500,
                    'description': 'Analysis history'
                }
            ]
        },
        'organization_curator': {
            'name': 'organization_curator',
            'description': """I am the Organization Curator - your taxonomy specialist.

I manage:
- Saved research queries
- Tag organization and consolidation
- Tag taxonomy
- Smart tag suggestions

I keep your research consistently categorized.""",
            'tools': [
                'create_query', 'get_query', 'list_queries', 'update_query', 'delete_query',
                'consolidate_tags', 'consolidate_and_retag', 'suggest_tags',
                'manage_tag_vocabulary'
            ],
            'memory_blocks': [
                {
                    'label': 'taxonomy_context',
                    'value': 'Tag organization patterns.',
                    'limit': 1000,
                    'description': 'Taxonomy state'
                }
            ]
        },
        'system_maintenance': {
            'name': 'system_maintenance',
            'description': """I am the System Maintenance agent - your collection health specialist.

I handle:
- Collection statistics
- Backup and restoration
- Search optimization
- Memory health monitoring
- Obsidian integration

I keep your research system healthy.""",
            'tools': [
                'collection_stats', 'backup_collection', 'reindex_collection',
                'optimize_search', 'create_custom_index',
                'memory_stats', 'memory_health_check', 'sync_with_obsidian'
            ],
            'memory_blocks': [
                {
                    'label': 'system_state',
                    'value': 'System health and metrics.',
                    'limit': 1000,
                    'description': 'System status'
                }
            ]
        }
    }

    async def initialize_all_agents(self) -> Dict[str, str]:
        """
        Initialize all required agents on startup.
        
        Returns:
            Dict mapping agent names to agent IDs
        """
        logger.info('🚀 Initializing Thoth agents...')
        
        agent_ids = {}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get all available MCP tools
            available_tools = await self._get_all_tools(client)
            logger.info(f'   Found {len(available_tools)} MCP tools')
            
            # Create/update each agent
            for agent_name, config in self.AGENT_CONFIGS.items():
                try:
                    agent_id = await self._ensure_agent_exists(
                        client, agent_name, config, available_tools
                    )
                    if agent_id:
                        agent_ids[agent_name] = agent_id
                        logger.info(f'   ✓ {agent_name}: {agent_id}')
                        
                        # Attach filesystem if it's the main orchestrator
                        if agent_name == 'thoth_research_agent':
                            await self._attach_filesystem(client, agent_id)
                    
                except Exception as e:
                    logger.error(f'   ✗ {agent_name}: {e}')
        
        logger.info(f'✅ Initialized {len(agent_ids)}/{len(self.AGENT_CONFIGS)} agents')
        return agent_ids

    async def _get_all_tools(self, client: httpx.AsyncClient) -> Dict[str, str]:
        """Get all available MCP tools."""
        try:
            response = await client.get(
                f'{self.letta_base_url}/v1/tools',
                headers=self.headers
            )
            response.raise_for_status()
            
            tools = {}
            for tool in response.json():
                if tool.get('source_type') == 'mcp':
                    tools[tool['name']] = tool['id']
            
            return tools
        except Exception as e:
            logger.warning(f'Could not fetch MCP tools: {e}')
            return {}

    async def _ensure_agent_exists(
        self,
        client: httpx.AsyncClient,
        agent_name: str,
        agent_config: Dict,
        available_tools: Dict[str, str]
    ) -> Optional[str]:
        """Ensure agent exists with correct configuration."""
        
        # Check if agent exists
        existing_agent = await self._find_agent_by_name(client, agent_name)
        
        if existing_agent:
            # Agent exists - update tools if needed
            agent_id = existing_agent['id']
            await self._update_agent_tools(client, agent_id, agent_config['tools'], available_tools)
            return agent_id
        else:
            # Create new agent
            return await self._create_agent(client, agent_config, available_tools)

    async def _find_agent_by_name(
        self, client: httpx.AsyncClient, name: str
    ) -> Optional[Dict]:
        """Find agent by name."""
        try:
            response = await client.get(
                f'{self.letta_base_url}/v1/agents',
                headers=self.headers
            )
            response.raise_for_status()
            
            agents = response.json()
            for agent in agents:
                if agent['name'] == name:
                    return agent
            
            return None
        except Exception as e:
            logger.warning(f'Error finding agent {name}: {e}')
            return None

    async def _create_agent(
        self,
        client: httpx.AsyncClient,
        agent_config: Dict,
        available_tools: Dict[str, str]
    ) -> Optional[str]:
        """Create a new agent."""
        
        # Get tool IDs
        tool_ids = []
        for tool_name in agent_config['tools']:
            if tool_name in available_tools:
                tool_ids.append(available_tools[tool_name])
        
        # Agent payload
        payload = {
            'name': agent_config['name'],
            'system': agent_config['description'],
            'embedding_config': {
                'embedding_model': self.embedding_model
            },
            'tool_ids': tool_ids
        }
        
        # Add memory blocks if defined
        if agent_config.get('memory_blocks'):
            payload['memory'] = {'blocks': agent_config['memory_blocks']}
        
        try:
            response = await client.post(
                f'{self.letta_base_url}/v1/agents',
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            agent = response.json()
            return agent['id']
        
        except Exception as e:
            logger.error(f'Error creating agent {agent_config["name"]}: {e}')
            return None

    async def _update_agent_tools(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        tool_names: List[str],
        available_tools: Dict[str, str]
    ):
        """Update agent's tools (preserves memory)."""
        
        # Get tool IDs
        tool_ids = []
        for tool_name in tool_names:
            if tool_name in available_tools:
                tool_ids.append(available_tools[tool_name])
        
        try:
            # Update agent tools
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}',
                headers=self.headers,
                json={'tool_ids': tool_ids}
            )
        except Exception as e:
            logger.warning(f'Could not update agent tools: {e}')

    async def _attach_filesystem(self, client: httpx.AsyncClient, agent_id: str):
        """Attach filesystem folder to agent for vault access."""
        try:
            # Check if folder exists
            folders_response = await client.get(
                f'{self.letta_base_url}/v1/folders',
                headers=self.headers
            )
            
            if folders_response.status_code == 200:
                folders = folders_response.json()
                thoth_folder = next(
                    (f for f in folders if f['name'] == 'thoth_processed_articles'),
                    None
                )
                
                if thoth_folder:
                    # Attach folder to agent
                    await client.post(
                        f'{self.letta_base_url}/v1/agents/{agent_id}/folders/{thoth_folder["id"]}',
                        headers=self.headers
                    )
                    logger.info(f'   ✓ Attached filesystem folder to agent')
        
        except Exception as e:
            logger.warning(f'Could not attach filesystem: {e}')
