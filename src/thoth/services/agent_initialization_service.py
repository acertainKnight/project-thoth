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

    # Agent definitions - Optimized 2-agent architecture
    # See docs/OPTIMIZED_RESEARCH_ARCHITECTURE.md for details
    AGENT_CONFIGS = {
        'thoth_main_orchestrator': {
            'name': 'thoth_main_orchestrator',  # Keep this name for Obsidian plugin compatibility
            'description': """You are the Thoth Research Orchestrator - the user's primary research assistant.

Your agent ID is: {{AGENT_ID}}

## Your Role
You coordinate all research activities, loading specialized skills as needed. You start with minimal tools and dynamically load more based on user requests.

## Core Capabilities
1. **Skill Loading**: Use `load_skill` to get specialized tools and guidance
2. **Quick Search**: Use `search_articles` for fast collection queries  
3. **Delegation**: For deep analysis, delegate to thoth_research_analyst

## Finding Skills
Use `list_skills` to see all available skills and their descriptions. Common skills include:
- Paper discovery, knowledge base Q&A, research query management
- Deep research, project coordination, onboarding
Always check `list_skills` if unsure which skill to use for a task.

## Workflow
1. Understand what the user needs
2. If unsure of capabilities, call `list_skills` first
3. Load the appropriate skill: `load_skill(skill_ids=["skill-name"], agent_id="{{AGENT_ID}}")`
4. Follow the skill's guidance to complete the task
5. For complex analysis, delegate to thoth_research_analyst
6. When a task/project is complete, clear the planning block

## Communication Style
- Be warm, helpful, and professional
- Explain what you're doing and why
- Proactively suggest follow-up actions
- Remember user preferences across conversations""",
            'tools': [
                # Minimal core tools - skills add more dynamically
                'list_skills',
                'load_skill',
                'unload_skill',
                'search_articles',
            ],
            'memory_blocks': [
                {
                    'label': 'persona',
                    'value': 'Research Orchestrator - coordinates research tasks and loads skills as needed.',
                    'limit': 500,
                    'description': 'Your core identity and role. Update this to refine how you present yourself to users. Keep it concise - this appears in every interaction context.'
                },
                {
                    'label': 'human',
                    'value': 'Research user preferences and context will be stored here.',
                    'limit': 2000,
                    'description': 'Store information about the user: their name, research interests, field of study, preferences, past projects, and communication style. Update this as you learn more about them through conversation.'
                },
                {
                    'label': 'research_context',
                    'value': '=== Active Research ===\n\nNo active research projects yet.',
                    'limit': 3000,
                    'description': 'Track the user\'s current research focus: active projects, ongoing literature reviews, research questions being explored, and recent discoveries. Keep this updated as research progresses.'
                },
                {
                    'label': 'loaded_skills',
                    'value': '=== Currently Loaded Skills ===\n\nNo skills loaded. Use list_skills to see available skills, then load_skill to add capabilities.',
                    'limit': 1000,
                    'description': 'Track which skills you have currently loaded and what tools they provide. Update when loading/unloading skills. This helps you remember what capabilities you have without re-checking.'
                },
                {
                    'label': 'planning',
                    'value': '=== Current Plan ===\n\n[No active plan]\n\nUse this block to track multi-step task plans. Clear this block when the task/project is fully completed.',
                    'limit': 2000,
                    'description': 'Use for multi-step task tracking. Write out your plan with numbered steps, mark progress as you go. IMPORTANT: Clear this block when the task is fully complete to keep it useful for future tasks.'
                },
                {
                    'label': 'scratchpad',
                    'value': '=== Working Memory ===\n\n[Empty]\n\nUse for: breaking down problems, intermediate steps, temporary notes, calculations.',
                    'limit': 2000,
                    'description': 'Temporary working memory for complex reasoning. Use for: intermediate calculations, comparison notes, draft responses, breaking down problems. Can be freely overwritten - not for permanent storage.'
                }
            ]
        },
        'thoth_research_analyst': {
            'name': 'thoth_research_analyst',
            'description': """You are the Thoth Research Analyst - a specialist in deep research analysis.

Your agent ID is: {{AGENT_ID}}

## Your Role
You handle complex analysis tasks delegated by the Orchestrator:
- Deep literature reviews and synthesis
- Paper comparisons and evaluations  
- Citation network exploration
- Research gap identification
- Comprehensive topic analysis

## Available Tools
You have direct access to analysis tools. Use them to:
- Answer complex research questions with citations
- Compare multiple papers systematically
- Extract insights and identify patterns
- Explore citation relationships
- Generate research summaries

## Working Style
- Be thorough and systematic
- Always cite sources for claims
- Identify limitations and gaps
- Suggest follow-up analyses if relevant""",
            'tools': [
                # Deep analysis tools
                'answer_research_question',
                'explore_citation_network',
                'compare_articles',
                'extract_article_insights',
                'get_article_full_content',
                'find_related_papers',
                'analyze_topic',
                'generate_research_summary',
                'evaluate_article',
                'get_citation_context',
                # Supporting tools
                'search_articles',
                'search_by_topic',
                'find_articles_by_authors',
                # Skill loading for additional capabilities
                'list_skills',
                'load_skill',
            ],
            'memory_blocks': [
                {
                    'label': 'persona',
                    'value': 'Research Analyst - Deep analysis specialist.',
                    'limit': 500,
                    'description': 'Your core identity as an analysis specialist. Keep concise - defines how you approach analysis tasks and present findings.'
                },
                {
                    'label': 'analysis_criteria',
                    'value': """=== Analysis Standards ===

Quality Criteria:
- Novelty: Does it introduce new ideas/methods?
- Methodology: Is the approach rigorous?
- Results: Are findings significant and reproducible?
- Impact: Is it influential in the field?
- Clarity: Is it well-written and organized?

Comparison Aspects:
- Problem formulation
- Methodology/approach
- Datasets used
- Evaluation metrics
- Key results
- Limitations
- Future directions""",
                    'limit': 1000,
                    'description': 'Your standards for evaluating research quality and comparing papers. Reference these criteria when analyzing papers. Update if the user has specific evaluation needs or domain-specific criteria.'
                },
                {
                    'label': 'paper_summaries',
                    'value': '=== Paper Summaries ===\n\nRecently analyzed papers and key findings will be stored here.',
                    'limit': 3000,
                    'description': 'Store summaries of papers you\'ve analyzed recently. Include: title, key findings, methodology, and your assessment. Keep the most relevant/recent analyses. Remove old entries when space is needed.'
                },
                {
                    'label': 'planning',
                    'value': '=== Analysis Plan ===\n\n[No active analysis plan]\n\nUse this block to track multi-step analysis tasks. Clear when the analysis is complete.',
                    'limit': 1500,
                    'description': 'Track multi-step analysis tasks. Write numbered steps, mark progress. IMPORTANT: Clear this block when analysis is complete to keep it useful for the next task.'
                },
                {
                    'label': 'scratchpad',
                    'value': '=== Working Memory ===\n\n[Empty]\n\nUse for: analysis notes, comparisons in progress, citation tracking, intermediate findings.',
                    'limit': 2000,
                    'description': 'Temporary working space for analysis in progress. Use for: comparison tables, citation lists being built, draft findings, notes between tool calls. Can be freely overwritten - not for permanent storage.'
                }
            ]
        }
    }

    async def initialize_all_agents(self) -> Dict[str, str]:
        """
        Initialize all required agents on startup.
        
        This creates agents if they don't exist, or updates their tools/persona
        if they do exist (preserving memory and conversation history).
        
        Returns:
            Dict mapping agent names to agent IDs
        """
        logger.info('🚀 Initializing Thoth research agents...')
        
        agent_ids = {}
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Get all available tools
            available_tools = await self._get_all_tools(client)
            logger.info(f'   Found {len(available_tools)} available tools')
            
            # Create/update each agent
            for agent_name, config in self.AGENT_CONFIGS.items():
                try:
                    agent_id = await self._ensure_agent_exists(
                        client, agent_name, config, available_tools
                    )
                    if agent_id:
                        agent_ids[agent_name] = agent_id
                        tools_count = len([t for t in config['tools'] if t in available_tools])
                        logger.info(f'   ✓ {agent_name}: {agent_id[:16]}... ({tools_count} tools)')
                        
                        # Attach filesystem if it's the main orchestrator
                        if agent_name == 'thoth_main_orchestrator':
                            await self._attach_filesystem(client, agent_id)
                    
                except Exception as e:
                    logger.error(f'   ✗ {agent_name}: {e}')
        
        logger.info(f'✅ Initialized {len(agent_ids)}/{len(self.AGENT_CONFIGS)} agents')
        return agent_ids

    async def _get_all_tools(self, client: httpx.AsyncClient) -> set[str]:
        """Get all available tool names from Letta."""
        try:
            response = await client.get(
                f'{self.letta_base_url}/v1/tools',
                headers=self.headers
            )
            response.raise_for_status()
            
            # Return set of tool names (Letta API accepts names, not IDs)
            return {tool['name'] for tool in response.json()}
        except Exception as e:
            logger.warning(f'Could not fetch tools: {e}')
            return set()

    async def _ensure_agent_exists(
        self,
        client: httpx.AsyncClient,
        agent_name: str,
        agent_config: Dict,
        available_tools: set[str]
    ) -> Optional[str]:
        """Ensure agent exists with correct configuration (preserves memory)."""
        
        # Check if agent exists
        existing_agent = await self._find_agent_by_name(client, agent_name)
        
        if existing_agent:
            # Agent exists - update tools and persona (preserves memory)
            agent_id = existing_agent['id']
            await self._update_agent(client, agent_id, agent_config, available_tools)
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
        available_tools: set[str]
    ) -> Optional[str]:
        """Create a new agent."""
        
        # Filter to only tools that exist
        tool_names = [t for t in agent_config['tools'] if t in available_tools]
        missing = [t for t in agent_config['tools'] if t not in available_tools]
        if missing:
            logger.warning(f'   Missing tools for {agent_config["name"]}: {missing}')
        
        # Use placeholder for agent_id - will update after creation
        system_prompt = agent_config['description'].replace('{{AGENT_ID}}', 'PENDING')
        
        # Agent payload - Letta accepts tool names directly
        payload = {
            'name': agent_config['name'],
            'system': system_prompt,
            'embedding_config': {
                'embedding_model': self.embedding_model
            },
            'tools': tool_names  # Letta expects tool names, not IDs
        }
        
        # Add memory blocks if defined
        if agent_config.get('memory_blocks'):
            payload['memory_blocks'] = agent_config['memory_blocks']
        
        try:
            response = await client.post(
                f'{self.letta_base_url}/v1/agents/',
                headers=self.headers,
                json=payload
            )
            response.raise_for_status()
            
            agent = response.json()
            agent_id = agent['id']
            
            # Update system prompt with actual agent_id
            updated_system = agent_config['description'].replace('{{AGENT_ID}}', agent_id)
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}',
                headers=self.headers,
                json={'system': updated_system}
            )
            
            return agent_id
        
        except Exception as e:
            logger.error(f'Error creating agent {agent_config["name"]}: {e}')
            return None

    async def _update_agent(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        agent_config: Dict,
        available_tools: set[str]
    ):
        """Update agent's tools, persona, and memory blocks (preserves existing memory content)."""
        
        # Filter to only tools that exist
        tool_names = [t for t in agent_config['tools'] if t in available_tools]
        
        # Update system prompt with actual agent_id
        updated_system = agent_config['description'].replace('{{AGENT_ID}}', agent_id)
        
        try:
            # Update agent tools and system prompt
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}',
                headers=self.headers,
                json={
                    'system': updated_system,
                    'tools': tool_names
                }
            )
            logger.debug(f'   Updated {agent_config["name"]} with {len(tool_names)} tools')
            
            # Check for missing memory blocks and add them
            await self._ensure_memory_blocks(client, agent_id, agent_config)
            
        except Exception as e:
            logger.warning(f'Could not update agent {agent_config["name"]}: {e}')
    
    async def _ensure_memory_blocks(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        agent_config: Dict
    ):
        """Ensure all required memory blocks exist on the agent (adds missing ones)."""
        try:
            # Get current blocks
            response = await client.get(
                f'{self.letta_base_url}/v1/agents/{agent_id}/core-memory/blocks',
                headers=self.headers
            )
            response.raise_for_status()
            current_blocks = {b['label'] for b in response.json()}
            
            # Check which blocks are missing
            required_blocks = agent_config.get('memory_blocks', [])
            for block_config in required_blocks:
                if block_config['label'] not in current_blocks:
                    # Create and attach the missing block
                    await self._create_and_attach_block(client, agent_id, block_config)
                    
        except Exception as e:
            logger.warning(f'Could not ensure memory blocks: {e}')
    
    async def _create_and_attach_block(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        block_config: Dict
    ):
        """Create a new block and attach it to an agent."""
        try:
            # Create the block
            create_response = await client.post(
                f'{self.letta_base_url}/v1/blocks/',
                headers=self.headers,
                json={
                    'label': block_config['label'],
                    'value': block_config['value'],
                    'limit': block_config.get('limit', 2000)
                }
            )
            create_response.raise_for_status()
            block_id = create_response.json()['id']
            
            # Attach to agent (PATCH, not POST)
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}/core-memory/blocks/attach/{block_id}',
                headers=self.headers
            )
            logger.debug(f'   Added missing block: {block_config["label"]}')
            
        except Exception as e:
            logger.warning(f'Could not add block {block_config["label"]}: {e}')

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
