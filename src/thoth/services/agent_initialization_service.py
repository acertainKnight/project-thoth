"""
Agent Initialization Service - Auto-creates and updates Letta agents on startup.

This service ensures all required Thoth agents exist with proper configuration:
- Creates agents if missing
- Updates tools/functionality if changed
- Preserves agent memory and conversations
- Attaches filesystem folders for vault access
"""

import os
from typing import ClassVar

import httpx
from loguru import logger

from thoth.config import config


class AgentInitializationService:
    """Service to initialize and maintain Thoth agents in Letta."""

    def __init__(self):
        """Initialize the agent initialization service."""
        # Check THOTH_LETTA_URL first (Docker), then LETTA_BASE_URL, then localhost
        self.letta_base_url = (
            os.getenv('THOTH_LETTA_URL')
            or os.getenv('LETTA_BASE_URL')
            or 'http://localhost:8283'
        )
        self.letta_api_key = os.getenv('LETTA_API_KEY', '')
        self.embedding_model = (
            config.settings.rag.embedding_model
        )  # openai/text-embedding-3-small

        # Agent LLM model from settings (empty = use Letta server default)
        self.agent_model = config.settings.memory.letta.agent_model

        self.headers = {'Content-Type': 'application/json'}
        if self.letta_api_key:
            self.headers['Authorization'] = f'Bearer {self.letta_api_key}'

    # Tools every agent needs. These get explicitly attached by _update_agent
    # and protected from detachment by _reset_skill_state.
    #
    # Letta's include_base_tools=True only gives conversation_search,
    # memory_replace, and memory_insert (as of Letta 0.6+). Everything
    # else needs explicit attachment. We include both old-style names
    # (core_memory_*) and new-style names (memory_*) so the protection
    # set works regardless of which version the agent was created under.
    LETTA_CORE_TOOLS: ClassVar[set[str]] = {
        'conversation_search',
        # Letta 0.16+ v1 agent memory tools
        'memory_replace',
        'memory_insert',
        # Old-style names (kept so _reset_skill_state won't detach them
        # from agents that were created on an older Letta version)
        'core_memory_replace',
        'core_memory_append',
        # send_message is implicit in Letta 0.16+ (letta_v1_agent) and
        # removed during agent creation, so we don't force-attach it.
        # Kept here only so _reset_skill_state won't accidentally detach
        # it from agents that still have it.
        'send_message',
    }

    LETTA_ARCHIVAL_TOOLS: ClassVar[set[str]] = {
        'archival_memory_insert',
        'archival_memory_search',
    }

    # Combined set used by _reset_skill_state to know what NOT to detach.
    LETTA_BASE_TOOLS: ClassVar[set[str]] = LETTA_CORE_TOOLS | LETTA_ARCHIVAL_TOOLS

    # Agent definitions - Optimized 2-agent architecture
    # See docs/OPTIMIZED_RESEARCH_ARCHITECTURE.md for details
    AGENT_CONFIGS: ClassVar[dict] = {
        'thoth_main_orchestrator': {
            'name': 'thoth_main_orchestrator',  # Keep this name for Obsidian plugin compatibility
            'description': """You are the Thoth Research Orchestrator - the user's primary research assistant.

Your agent ID is: {{AGENT_ID}}
Your user ID is: {{USER_ID}}
Current server version: {{SERVER_VERSION}}

## Your Role
You coordinate all research activities, loading specialized skills as needed. You start with minimal tools and dynamically load more based on user requests.

## Core Capabilities
1. **Skill Loading**: Use `load_skill` to get specialized tools and guidance
2. **Quick Search**: Use `search_articles` for fast collection queries
3. **Delegation**: For deep analysis, delegate to thoth_research_analyst

## Finding Skills
Use `list_skills` to see all available skills and their descriptions. Common skills include:
- Paper discovery, knowledge base Q&A, research query management
- Deep research, project coordination, onboarding, whats-new
Always check `list_skills` if unsure which skill to use for a task.

## Workflow
1. Understand what the user needs
2. If unsure of capabilities, call `list_skills` first
3. Load the appropriate skill: `load_skill(skill_ids=["skill-name"], agent_id="{{AGENT_ID}}")`
4. Follow the skill's guidance to complete the task
5. For complex analysis, delegate to thoth_research_analyst
6. When a task/project is complete, clear the planning block

## How Skills Work
When you load a skill with `load_skill`, its full instructions appear as a system message in the conversation on the very next turn -- you do not need to read memory blocks to find them. Every subsequent turn while the skill is loaded you will also see a compact reminder at the top of the message. Follow those instructions directly. The `loaded_skills` memory block tracks which skills are loaded; the actual guidance always arrives through the conversation stream.

## First Interaction
On your first conversation, the onboarding skill is pre-loaded. Its full instructions will arrive as a system message on the first user message -- follow them.

## Update Awareness
At the start of a conversation, check the human memory block for last_seen_version. If it is absent or older than the server version shown above, offer to walk the user through what's new. Load the whats-new skill to get the update tools and walkthrough guidance.

## Multi-user Safety
- Always include `user_id: {{USER_ID}}` in MCP tool calls when the tool accepts user_id.
- Never query, mutate, or summarize another user's data.

## Communication Style
- Be warm, helpful, and professional
- Explain what you're doing and why
- Proactively suggest follow-up actions
- Remember user preferences across conversations""",
            'tools': [
                # Minimal core tools - skills add more dynamically.
                # search_documentation, load_documentation, and check_whats_new
                # are loaded on-demand via the onboarding / whats-new skills
                # to avoid wasting context during normal conversations.
                'list_skills',
                'load_skill',
                'search_articles',
            ],
            # Pre-load this skill for brand new agents on first creation only.
            # _update_agent (restarts) resets skill state to empty, which is correct.
            'initial_skill': 'onboarding',
            'tool_rules': [
                # Letta doesn't refresh agent tool lists mid-turn, so skill
                # load/unload must end the turn. The Obsidian plugin sends an
                # auto-follow-up message to resume with the new tools.
                {'tool_name': 'load_skill', 'type': 'exit_loop'},
                {'tool_name': 'unload_skill', 'type': 'exit_loop'},
            ],
            'memory_blocks': [
                {
                    'label': 'persona',
                    'value': 'Research Orchestrator - coordinates research tasks and loads skills as needed.',
                    'limit': 500,
                    'description': 'Your core identity and role. Update this to refine how you present yourself to users. Keep it concise - this appears in every interaction context.',
                },
                {
                    'label': 'human',
                    'value': 'Research user preferences and context will be stored here.',
                    'limit': 2000,
                    'description': 'Store information about the user: their name, research interests, field of study, preferences, past projects, and communication style. Update this as you learn more about them through conversation.',
                },
                {
                    'label': 'research_context',
                    'value': '=== Active Research ===\n\nNo active research projects yet.',
                    'limit': 3000,
                    'description': "Track the user's current research focus: active projects, ongoing literature reviews, research questions being explored, and recent discoveries. Keep this updated as research progresses.",
                },
                {
                    'label': 'loaded_skills',
                    'value': '=== Currently Loaded Skills ===\n\nSlot 1: [empty]\nSlot 2: [empty]\nSlot 3: [empty]',
                    'limit': 1000,
                    'description': 'Tracks which skills are loaded and what tools they provide. Full skill instructions arrive as system messages in the conversation -- they are not stored here.',
                },
                {
                    'label': 'planning',
                    'value': '=== Current Plan ===\n\n[No active plan]\n\nUse this block to track multi-step task plans. Clear this block when the task/project is fully completed.',
                    'limit': 2000,
                    'description': 'Use for multi-step task tracking. Write out your plan with numbered steps, mark progress as you go. IMPORTANT: Clear this block when the task is fully complete to keep it useful for future tasks.',
                },
                {
                    'label': 'scratchpad',
                    'value': '=== Working Memory ===\n\n[Empty]\n\nUse for: breaking down problems, intermediate steps, temporary notes, calculations.',
                    'limit': 2000,
                    'description': 'Temporary working memory for complex reasoning. Use for: intermediate calculations, comparison notes, draft responses, breaking down problems. Can be freely overwritten - not for permanent storage.',
                },
            ],
        },
        'thoth_research_analyst': {
            'name': 'thoth_research_analyst',
            'description': """You are the Thoth Research Analyst - a specialist in deep research analysis.

Your agent ID is: {{AGENT_ID}}
Your user ID is: {{USER_ID}}

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
- Suggest follow-up analyses if relevant

## Multi-user Safety
- Always include `user_id: {{USER_ID}}` in MCP tool calls when the tool accepts user_id.
- Only analyze and reference data scoped to this user.""",
            'tools': [
                # Deep analysis tools
                'answer_research_question',
                'explore_citation_network',
                'compare_articles',
                'evaluate_article',
                'get_citation_context',
                'find_related_papers',
                'read_full_article',
                'unload_article',
                # Supporting tools
                'search_articles',
                # Skill loading for additional capabilities
                'list_skills',
                'load_skill',
            ],
            'tool_rules': [
                {'tool_name': 'load_skill', 'type': 'exit_loop'},
                {'tool_name': 'unload_skill', 'type': 'exit_loop'},
            ],
            'memory_blocks': [
                {
                    'label': 'persona',
                    'value': 'Research Analyst - Deep analysis specialist.',
                    'limit': 500,
                    'description': 'Your core identity as an analysis specialist. Keep concise - defines how you approach analysis tasks and present findings.',
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
                    'description': 'Your standards for evaluating research quality and comparing papers. Reference these criteria when analyzing papers. Update if the user has specific evaluation needs or domain-specific criteria.',
                },
                {
                    'label': 'paper_summaries',
                    'value': '=== Paper Summaries ===\n\nRecently analyzed papers and key findings will be stored here.',
                    'limit': 3000,
                    'description': "Store summaries of papers you've analyzed recently. Include: title, key findings, methodology, and your assessment. Keep the most relevant/recent analyses. Remove old entries when space is needed.",
                },
                {
                    'label': 'planning',
                    'value': '=== Analysis Plan ===\n\n[No active analysis plan]\n\nUse this block to track multi-step analysis tasks. Clear when the analysis is complete.',
                    'limit': 1500,
                    'description': 'Track multi-step analysis tasks. Write numbered steps, mark progress. IMPORTANT: Clear this block when analysis is complete to keep it useful for the next task.',
                },
                {
                    'label': 'scratchpad',
                    'value': '=== Working Memory ===\n\n[Empty]\n\nUse for: analysis notes, comparisons in progress, citation tracking, intermediate findings.',
                    'limit': 2000,
                    'description': 'Temporary working space for analysis in progress. Use for: comparison tables, citation lists being built, draft findings, notes between tool calls. Can be freely overwritten - not for permanent storage.',
                },
            ],
        },
    }

    async def initialize_agents_for_user(
        self,
        user_context,
        existing_agent_ids: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """
        Initialize or update Letta agents for a user.

        When ``existing_agent_ids`` is provided (e.g. from the DB), those agents
        are updated in-place (tools, system prompt, memory blocks) without
        creating new ones.  This preserves conversation history and memory.

        When no existing IDs are given, new namespaced agents are created
        (e.g. ``thoth_main_orchestrator_alice``) to avoid global collisions.

        Args:
            user_context: UserContext with user_id, username, vault_path.
            existing_agent_ids: Optional dict with ``orchestrator`` and/or
                ``analyst`` keys mapped to Letta agent IDs that already belong
                to this user.  Pass these to update rather than recreate.

        Returns:
            Dict with 'orchestrator' and 'analyst' keys mapped to agent IDs.
            Empty dict if initialization fails.

        Example:
            >>> ids = await svc.initialize_agents_for_user(user_context)
            >>> ids == {'orchestrator': 'agent-xxx', 'analyst': 'agent-yyy'}
        """
        username = user_context.username
        existing = existing_agent_ids or {}
        logger.info(f'Initializing Letta agents for user: {username}')

        agent_ids: dict[str, str] = {}

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                available_tools = await self._get_all_tools(client)

                for agent_key, base_config in self.AGENT_CONFIGS.items():
                    user_config = dict(base_config)
                    user_config['user_id'] = user_context.user_id
                    role = (
                        'orchestrator'
                        if agent_key == 'thoth_main_orchestrator'
                        else 'analyst'
                    )
                    existing_id = existing.get(role)

                    try:
                        if existing_id:
                            await self._update_agent(
                                client,
                                existing_id,
                                user_config,
                                available_tools,
                            )

                            if config.settings.memory.letta.archival_memory_enabled:
                                if not await self._verify_archival_memory(
                                    client, existing_id
                                ):
                                    logger.warning(
                                        f'{role} agent for user {username} '
                                        f'({existing_id[:16]}) has broken '
                                        f'archival memory'
                                    )

                            agent_ids[role] = existing_id
                            if role == 'orchestrator':
                                await self._attach_filesystem(client, existing_id)
                            logger.info(f'  Updated {role}: {existing_id[:16]}...')
                        else:
                            # No existing agent -- create a new namespaced one
                            user_config['name'] = f'{base_config["name"]}_{username}'

                            agent_id = await self._ensure_agent_exists(
                                client,
                                user_config['name'],
                                user_config,
                                available_tools,
                            )
                            if agent_id:
                                agent_ids[role] = agent_id
                                if role == 'orchestrator':
                                    await self._attach_filesystem(client, agent_id)
                                logger.info(
                                    f'  Created {user_config["name"]}: {agent_id[:16]}...'
                                )
                    except Exception as e:
                        logger.error(
                            f'Failed to init {role} agent for user {username}: {e}'
                        )
        except Exception as e:
            logger.error(f'Agent initialization failed for user {username}: {e}')

        logger.info(
            f'Initialized {len(agent_ids)}/{len(self.AGENT_CONFIGS)} agents '
            f'for user {username}'
        )
        return agent_ids

    async def initialize_all_agents(self, service_manager=None) -> dict[str, str]:
        """
        Initialize all required agents on startup.

        This creates agents if they don't exist, or updates their tools/persona
        if they do exist (preserving memory and conversation history).

        Args:
            service_manager: Optional ServiceManager instance to use for dependencies

        Returns:
            Dict mapping agent names to agent IDs
        """
        # Store service_manager for later use
        self._service_manager = service_manager

        logger.info('Initializing Thoth research agents...')

        agent_ids = {}

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            # Get all available tools
            available_tools = await self._get_all_tools(client)
            logger.info(f'Found {len(available_tools)} available tools')

            # Create/update each agent
            for agent_name, config in self.AGENT_CONFIGS.items():
                agent_config = dict(config)
                agent_config['user_id'] = 'default_user'
                try:
                    agent_id = await self._ensure_agent_exists(
                        client, agent_name, agent_config, available_tools
                    )
                    if agent_id:
                        agent_ids[agent_name] = agent_id
                        tools_count = len(
                            [t for t in config['tools'] if t in available_tools]
                        )
                        logger.info(
                            f'    {agent_name}: {agent_id[:16]}... ({tools_count} tools)'
                        )

                        # Attach filesystem if it's the main orchestrator
                        if agent_name == 'thoth_main_orchestrator':
                            await self._attach_filesystem(client, agent_id)

                except Exception as e:
                    logger.error(f'{agent_name}: {e}')

        logger.info(f'Initialized {len(agent_ids)}/{len(self.AGENT_CONFIGS)} agents')

        # Sync external MCP tools to agents
        await self._sync_external_mcp_tools(agent_ids)

        return agent_ids

    async def _upsert_base_tools(self, client: httpx.AsyncClient) -> dict[str, str]:
        """Call Letta's ``POST /v1/tools/add-base-tools`` to register internal tools.

        Letta's base tools (``memory_replace``, ``memory_insert``,
        ``conversation_search``, ``send_message``, etc.) don't appear in
        ``/v1/tools/`` by default. This endpoint upserts them so they can
        be looked up by name and attached to agents by ID.

        Returns:
            Dict mapping tool name to tool ID for all base tools.
        """
        try:
            resp = await client.post(
                f'{self.letta_base_url}/v1/tools/add-base-tools',
                headers=self.headers,
            )
            if resp.status_code == 200:
                return {
                    t['name']: t['id']
                    for t in resp.json()
                    if t.get('name') and t.get('id')
                }
        except Exception as e:
            logger.warning(f'Could not upsert base tools: {e}')
        return {}

    async def _get_all_tools(self, client: httpx.AsyncClient) -> set[str]:
        """Get all available tool names from Letta.

        Calls ``_upsert_base_tools`` first to register Letta's internal
        tools, then queries custom tools and MCP servers.

        MCP tools are stored with prefixed names (e.g.
        ``thoth__search_documentation``). We store both prefixed and
        unprefixed forms so config lookups work either way.
        """
        tools = set()
        try:
            # Register and cache base tools so they're discoverable.
            self._base_tool_ids = await self._upsert_base_tools(client)
            tools.update(self._base_tool_ids.keys())

            response = await client.get(
                f'{self.letta_base_url}/v1/tools/', headers=self.headers
            )
            response.raise_for_status()
            tools.update(tool['name'] for tool in response.json())

            mcp_resp = await client.get(
                f'{self.letta_base_url}/v1/mcp-servers/', headers=self.headers
            )
            if mcp_resp.status_code == 200:
                for server in mcp_resp.json():
                    server_id = server.get('id')
                    if not server_id:
                        continue
                    tools_resp = await client.get(
                        f'{self.letta_base_url}/v1/mcp-servers/{server_id}/tools',
                        headers=self.headers,
                    )
                    if tools_resp.status_code == 200:
                        for t in tools_resp.json():
                            name = t.get('name', '')
                            tools.add(name)
                            if '__' in name:
                                tools.add(name.split('__', 1)[1])

            return tools
        except Exception as e:
            logger.warning(f'Could not fetch tools: {e}')
            return tools

    async def _ensure_agent_exists(
        self,
        client: httpx.AsyncClient,
        agent_name: str,
        agent_config: dict,
        available_tools: set[str],
    ) -> str | None:
        """Ensure agent exists with correct configuration (preserves memory)."""

        existing_agent = await self._find_agent_by_name(client, agent_name)

        if existing_agent:
            agent_id = existing_agent['id']
            await self._update_agent(client, agent_id, agent_config, available_tools)

            if config.settings.memory.letta.archival_memory_enabled:
                if not await self._verify_archival_memory(client, agent_id):
                    logger.warning(
                        f'Agent {agent_name} ({agent_id[:16]}) has broken '
                        f'archival memory. archival_memory_insert/search may '
                        f'fail until the agent is manually recreated.'
                    )

            return agent_id
        else:
            return await self._create_agent(client, agent_config, available_tools)

    async def _find_agent_by_name(
        self, client: httpx.AsyncClient, name: str
    ) -> dict | None:
        """Find agent by name."""
        try:
            response = await client.get(
                f'{self.letta_base_url}/v1/agents/', headers=self.headers
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

    async def _validate_agent_in_letta(
        self, client: httpx.AsyncClient, agent_id: str
    ) -> bool:
        """Check whether an agent ID still exists in Letta.

        Args:
            client: Active httpx client.
            agent_id: Letta agent ID to validate.

        Returns:
            True if the agent exists, False if it returned 404 or an error.
        """
        try:
            resp = await client.get(
                f'{self.letta_base_url}/v1/agents/{agent_id}',
                headers=self.headers,
                timeout=10,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f'Could not validate agent {agent_id[:16]}: {e}')
            return False

    async def sync_all_user_agents(self, postgres) -> None:
        """Update every registered user's agents to match current AGENT_CONFIGS.

        Runs after initialize_all_agents on startup. For each active user:
        - If their agent ID exists in Letta: update in place (preserves memory
          and conversations)
        - If their agent ID is missing or stale: create a new agent and update
          the users table with the new ID

        This is the mechanism that propagates config changes (new tools, updated
        system prompts, new memory blocks) to per-user agents on every restart.

        Args:
            postgres: PostgresService instance for DB access.
        """
        if postgres is None:
            logger.warning(
                'sync_all_user_agents: postgres service not available, skipping'
            )
            return

        try:
            rows = await postgres.fetch(
                'SELECT id, username, orchestrator_agent_id, analyst_agent_id '
                'FROM users WHERE is_active = TRUE'
            )
        except Exception as e:
            logger.error(f'sync_all_user_agents: could not fetch users: {e}')
            return

        if not rows:
            logger.info('sync_all_user_agents: no active users found')
            return

        logger.success(f'Syncing per-user agents for {len(rows)} user(s)...')

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            available_tools = await self._get_all_tools(client)

            for row in rows:
                username = row['username']
                user_id = str(row['id'])
                new_ids: dict[str, str] = {}

                role_map = {
                    'orchestrator': (
                        row['orchestrator_agent_id'],
                        'thoth_main_orchestrator',
                    ),
                    'analyst': (
                        row['analyst_agent_id'],
                        'thoth_research_analyst',
                    ),
                }

                for role, (existing_id, base_name) in role_map.items():
                    base_config = self.AGENT_CONFIGS[base_name]
                    user_config = dict(base_config)
                    user_config['user_id'] = user_id

                    try:
                        if existing_id and await self._validate_agent_in_letta(
                            client, existing_id
                        ):
                            # Agent still exists -- update it in place
                            await self._update_agent(
                                client, existing_id, user_config, available_tools
                            )
                            if role == 'orchestrator':
                                await self._attach_filesystem(client, existing_id)
                            logger.info(
                                f'  {username}/{role}: updated {existing_id[:16]}...'
                            )
                        else:
                            # Agent is missing -- create a fresh one
                            if existing_id:
                                logger.warning(
                                    f'  {username}/{role}: agent {existing_id[:16]} '
                                    f'not found in Letta -- creating replacement'
                                )
                            else:
                                logger.warning(
                                    f'  {username}/{role}: no agent ID -- creating'
                                )

                            user_config['name'] = f'{base_name}_{username}'
                            new_id = await self._create_agent(
                                client, user_config, available_tools
                            )
                            if new_id:
                                new_ids[role] = new_id
                                if role == 'orchestrator':
                                    await self._attach_filesystem(client, new_id)
                                logger.info(
                                    f'  {username}/{role}: created {new_id[:16]}...'
                                )
                    except Exception as e:
                        logger.error(f'  {username}/{role}: sync failed: {e}')

                # Write any new IDs back to the users table
                if new_ids:
                    try:
                        updates = []
                        params: list = []
                        idx = 1
                        if 'orchestrator' in new_ids:
                            updates.append(f'orchestrator_agent_id = ${idx}')
                            params.append(new_ids['orchestrator'])
                            idx += 1
                        if 'analyst' in new_ids:
                            updates.append(f'analyst_agent_id = ${idx}')
                            params.append(new_ids['analyst'])
                            idx += 1
                        params.append(row['id'])
                        await postgres.execute(
                            f'UPDATE users SET {", ".join(updates)} WHERE id = ${idx}',
                            *params,
                        )
                        logger.info(
                            f'  {username}: updated users table with new agent IDs'
                        )
                    except Exception as e:
                        logger.error(f'  {username}: failed to update users table: {e}')

    async def _resolve_embedding_config(
        self,
        client: httpx.AsyncClient,
    ) -> dict | None:
        """Fetch the full embedding config from Letta for the configured model.

        Letta requires ``embedding_endpoint_type`` and ``embedding_dim`` in the
        ``embedding_config`` payload.  Rather than hard-coding these, we query
        the ``/v1/models/embedding`` endpoint and match by model name.

        Returns:
            dict: Full embedding config dict, or None if the model was not found.
        """
        if hasattr(self, '_cached_embedding_config'):
            return self._cached_embedding_config

        try:
            resp = await client.get(
                f'{self.letta_base_url}/v1/models/embedding',
                headers=self.headers,
            )
            resp.raise_for_status()

            # Match on the short model name (e.g. "text-embedding-3-small")
            # self.embedding_model may be "openai/text-embedding-3-small"
            model_short = (
                self.embedding_model.split('/')[-1]
                if '/' in self.embedding_model
                else self.embedding_model
            )

            for model in resp.json():
                if (
                    model.get('embedding_model') == model_short
                    or model.get('handle') == self.embedding_model
                ):
                    cfg = {
                        'embedding_endpoint_type': model['embedding_endpoint_type'],
                        'embedding_endpoint': model['embedding_endpoint'],
                        'embedding_model': model['embedding_model'],
                        'embedding_dim': model['embedding_dim'],
                        'embedding_chunk_size': model.get('embedding_chunk_size', 300),
                    }
                    self._cached_embedding_config = cfg
                    return cfg

            logger.warning(
                f'Embedding model {self.embedding_model!r} not found in Letta'
            )
        except Exception as e:
            logger.warning(f'Could not fetch embedding models from Letta: {e}')

        return None

    async def _resolve_llm_config(
        self,
        client: httpx.AsyncClient,
    ) -> dict | None:
        """Fetch the full LLM config from Letta for the configured agent model.

        Letta requires ``model_endpoint_type`` in the ``llm_config`` payload.
        We query ``/v1/models/`` and match by model name or handle.

        Returns:
            dict: Full LLM config dict, or None if no model configured / not found.
        """
        if not self.agent_model:
            return None

        if hasattr(self, '_cached_llm_config'):
            return self._cached_llm_config

        try:
            resp = await client.get(
                f'{self.letta_base_url}/v1/models/',
                headers=self.headers,
            )
            resp.raise_for_status()

            model_short = (
                self.agent_model.split('/')[-1]
                if '/' in self.agent_model
                else self.agent_model
            )

            for model in resp.json():
                if (
                    model.get('model') == model_short
                    or model.get('handle') == self.agent_model
                ):
                    cfg = {
                        'model': model['model'],
                        'model_endpoint_type': model['model_endpoint_type'],
                        'model_endpoint': model['model_endpoint'],
                        'context_window': model.get('context_window', 128000),
                    }
                    self._cached_llm_config = cfg
                    return cfg

            logger.warning(f'LLM model {self.agent_model!r} not found in Letta')
        except Exception as e:
            logger.warning(f'Could not fetch LLM models from Letta: {e}')

        return None

    async def _create_agent(
        self, client: httpx.AsyncClient, agent_config: dict, available_tools: set[str]
    ) -> str | None:
        """Create a new agent with full model configuration from Letta."""

        tool_names = [t for t in agent_config['tools'] if t in available_tools]
        missing = [t for t in agent_config['tools'] if t not in available_tools]
        if missing:
            logger.warning(f'Missing tools for {agent_config["name"]}: {missing}')

        system_prompt = self._render_system_prompt(agent_config, 'PENDING')

        # Resolve full embedding config from Letta (required fields: endpoint_type, dim)
        embedding_cfg = await self._resolve_embedding_config(client)
        if not embedding_cfg:
            logger.error(
                f'Cannot create agent {agent_config["name"]}: '
                f'embedding model {self.embedding_model!r} not available in Letta'
            )
            return None

        payload: dict = {
            'name': agent_config['name'],
            'system': system_prompt,
            'embedding_config': embedding_cfg,
            'tools': tool_names,
            'include_base_tools': True,
        }

        # Resolve full LLM config from Letta (required fields: endpoint_type)
        llm_cfg = await self._resolve_llm_config(client)
        if llm_cfg:
            payload['llm_config'] = llm_cfg
            logger.info(f'Using configured model: {llm_cfg["model"]}')

        if agent_config.get('memory_blocks'):
            payload['memory_blocks'] = agent_config['memory_blocks']

        if agent_config.get('tool_rules'):
            payload['tool_rules'] = agent_config['tool_rules']

        try:
            response = await client.post(
                f'{self.letta_base_url}/v1/agents/',
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()

            agent = response.json()
            agent_id = agent['id']

            # Update system prompt with actual agent_id and user_id
            updated_system = self._render_system_prompt(agent_config, agent_id)
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}',
                headers=self.headers,
                json={'system': updated_system},
            )

            # include_base_tools=True only gives conversation_search,
            # memory_replace, memory_insert in Letta 0.6+. We need to
            # explicitly attach send_message and archival tools.
            await self._attach_core_tools(client, agent_id, available_tools)

            # Pre-load the initial skill if one is configured
            initial_skill = agent_config.get('initial_skill')
            if initial_skill:
                await self._preload_initial_skill(client, agent_id, initial_skill)

            return agent_id

        except Exception as e:
            logger.error(f'Error creating agent {agent_config["name"]}: {e}')
            return None

    async def _attach_core_tools(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        available_tools: set[str],
    ) -> None:
        """Explicitly attach Letta core + archival tools that include_base_tools misses.

        Letta 0.6+ auto-attaches conversation_search, memory_replace, and
        memory_insert via include_base_tools=True but does NOT attach
        send_message or archival tools. This fills the gap.

        Args:
            client: Active httpx client.
            agent_id: Letta agent ID to attach tools to.
            available_tools: Set of all tool names known to Letta.
        """
        needed = self.LETTA_CORE_TOOLS & available_tools
        if config.settings.memory.letta.archival_memory_enabled:
            needed |= self.LETTA_ARCHIVAL_TOOLS & available_tools

        # Get what the agent already has so we don't double-attach
        resp = await client.get(
            f'{self.letta_base_url}/v1/agents/{agent_id}', headers=self.headers
        )
        resp.raise_for_status()
        current = {t['name'] for t in resp.json().get('tools', [])}

        to_attach = needed - current
        if not to_attach:
            return

        tool_map = await self._fetch_tool_id_map(client)
        for name in to_attach:
            tid = tool_map.get(name)
            if tid:
                try:
                    await client.patch(
                        f'{self.letta_base_url}/v1/agents/{agent_id}/tools/attach/{tid}',
                        headers=self.headers,
                    )
                except Exception as e:
                    logger.warning(
                        f'Could not attach {name} to new agent {agent_id[:8]}: {e}'
                    )

        logger.debug(
            f'Attached {len(to_attach)} core tool(s) to new agent {agent_id[:8]}'
        )

    async def _fetch_tool_id_map(self, client: httpx.AsyncClient) -> dict[str, str]:
        """Fetch all tool name->ID mappings from Letta.

        Combines:
        1. Base tool IDs cached from ``_upsert_base_tools``
        2. Custom tools from ``/v1/tools/``
        3. MCP server tools (both prefixed and unprefixed entries)
        """
        # Start with base tool IDs from the upsert call
        tool_map: dict[str, str] = dict(getattr(self, '_base_tool_ids', {}))
        try:
            resp = await client.get(
                f'{self.letta_base_url}/v1/tools/', headers=self.headers
            )
            if resp.status_code == 200:
                for t in resp.json():
                    if t.get('name') and t.get('id'):
                        tool_map[t['name']] = t['id']

            mcp_resp = await client.get(
                f'{self.letta_base_url}/v1/mcp-servers/', headers=self.headers
            )
            if mcp_resp.status_code == 200:
                for server in mcp_resp.json():
                    server_id = server.get('id')
                    if not server_id:
                        continue
                    tools_resp = await client.get(
                        f'{self.letta_base_url}/v1/mcp-servers/{server_id}/tools',
                        headers=self.headers,
                    )
                    if tools_resp.status_code == 200:
                        for t in tools_resp.json():
                            name = t.get('name', '')
                            tid = t.get('id', '')
                            if name and tid:
                                tool_map[name] = tid
                                if '__' in name:
                                    tool_map[name.split('__', 1)[1]] = tid
        except Exception as e:
            logger.warning(f'Could not fetch tool ID map: {e}')
        return tool_map

    async def _preload_initial_skill(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        skill_id: str,
    ) -> None:
        """Pre-load a skill into a newly created agent's first skill slot.

        Mirrors what load_skill does at runtime: attaches required tools, writes
        skill content into skill_1, updates the loaded_skills tracker, and
        persists the load to agent_loaded_skills so the DB stays in sync with
        the memory blocks.

        Only called from _create_agent, never from _update_agent, so it runs
        exactly once per agent lifetime.
        """
        from thoth.services.skill_service import SkillService

        skill_service = SkillService()
        skill_content = skill_service.get_skill_content(skill_id)
        if skill_content is None:
            logger.warning(
                f'Initial skill {skill_id!r} not found -- skipping pre-load for {agent_id[:8]}'
            )
            return

        required_tools = skill_service.get_skill_tools(skill_id)
        tool_id_map = await self._fetch_tool_id_map(client)

        # Attach the skill's required tools
        for tool_name in required_tools:
            tool_id = tool_id_map.get(tool_name)
            if tool_id:
                try:
                    await client.patch(
                        f'{self.letta_base_url}/v1/agents/{agent_id}/tools/attach/{tool_id}',
                        headers=self.headers,
                    )
                except Exception as e:
                    logger.warning(
                        f'Could not attach tool {tool_name!r} for initial skill: {e}'
                    )
            else:
                logger.warning(
                    f'Tool {tool_name!r} not in Letta registry during initial skill pre-load'
                )

        # Attach unload_skill (going from 0 → 1 loaded skill)
        unload_id = tool_id_map.get('unload_skill')
        if unload_id:
            try:
                await client.patch(
                    f'{self.letta_base_url}/v1/agents/{agent_id}/tools/attach/{unload_id}',
                    headers=self.headers,
                )
            except Exception as e:
                logger.warning(
                    f'Could not attach unload_skill during initial skill pre-load: {e}'
                )

        # Persist to agent_loaded_skills so load_skill/unload_skill stay in
        # sync with the memory blocks. Without this row the DB thinks zero
        # skills are loaded and a subsequent load_skill would clobber slot 1.
        postgres = None
        if hasattr(self, '_service_manager') and self._service_manager:
            postgres = getattr(self._service_manager, '_services', {}).get('postgres')

        if postgres:
            try:
                await postgres.execute(
                    'INSERT INTO agent_loaded_skills (agent_id, skill_id) '
                    'VALUES ($1, $2) ON CONFLICT (agent_id, skill_id) DO NOTHING',
                    agent_id,
                    skill_id,
                )
            except Exception as e:
                logger.warning(
                    f'Could not persist initial skill {skill_id!r} to DB for {agent_id[:8]}: {e}'
                )
        else:
            logger.warning(
                f'No postgres connection during initial skill pre-load for {agent_id[:8]} '
                f'-- {skill_id!r} will not be tracked in agent_loaded_skills'
            )

        # Update the loaded_skills tracker so the agent knows what's loaded.
        # Full skill content is injected by the proxy on the first user message.
        try:
            tools_str = ', '.join(required_tools) if required_tools else 'no tools'
            tracker = (
                f'=== Currently Loaded Skills ===\n\n'
                f'Slot 1: {skill_id} (tools: {tools_str})\n'
                f'Slot 2: [empty]\n'
                f'Slot 3: [empty]'
            )
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}/core-memory/blocks/loaded_skills',
                headers=self.headers,
                json={'value': tracker},
            )

            logger.info(
                f'Pre-loaded initial skill {skill_id!r} for new agent {agent_id[:8]}'
            )
        except Exception as e:
            logger.warning(f'Error pre-loading initial skill for {agent_id[:8]}: {e}')

    async def _update_agent(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        agent_config: dict,
        available_tools: set[str],
    ):
        """
        Update agent's tools, persona, and memory blocks.

        Preserves existing memory content.
        """

        # Filter to only tools that exist, always include core Letta tools
        desired_tools = set(t for t in agent_config['tools'] if t in available_tools)
        desired_tools |= self.LETTA_CORE_TOOLS & available_tools
        if config.settings.memory.letta.archival_memory_enabled:
            desired_tools |= self.LETTA_ARCHIVAL_TOOLS & available_tools

        # Update system prompt with actual agent_id and user_id
        updated_system = self._render_system_prompt(agent_config, agent_id)

        try:
            # Build PATCH payload: system prompt + optional model override + tool rules
            patch_payload: dict = {'system': updated_system}
            if self.agent_model:
                patch_payload['llm_config'] = {'model': self.agent_model}

            # Add tool rules if defined in config
            if agent_config.get('tool_rules'):
                patch_payload['tool_rules'] = agent_config['tool_rules']

            # Update agent system prompt, model, and tool rules
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}',
                headers=self.headers,
                json=patch_payload,
            )

            # Get current agent tools
            response = await client.get(
                f'{self.letta_base_url}/v1/agents/{agent_id}', headers=self.headers
            )
            agent_data = response.json()
            current_tools = {t['name']: t['id'] for t in agent_data.get('tools', [])}

            # Build a name->ID map for attaching tools. This also discovers
            # internal Letta tools (memory_replace etc.) by scanning agents.
            all_tools = await self._fetch_tool_id_map(client)

            # Attach missing tools
            tools_to_attach = desired_tools - set(current_tools.keys())
            for tool_name in tools_to_attach:
                tool_id = all_tools.get(tool_name)
                if tool_id:
                    await client.patch(
                        f'{self.letta_base_url}/v1/agents/{agent_id}/tools/attach/{tool_id}',
                        headers=self.headers,
                    )

            if tools_to_attach:
                logger.debug(
                    f'   Attached {len(tools_to_attach)} tools to {agent_config["name"]}'
                )

            # Check for missing memory blocks and add them
            await self._ensure_memory_blocks(client, agent_id, agent_config)

            # Always start with a clean skill state so in-memory blocks,
            # DB records, and attached tools are consistent after restart
            await self._reset_skill_state(client, agent_id, agent_config)

        except Exception as e:
            logger.warning(f'Could not update agent {agent_config["name"]}: {e}')

    def _render_system_prompt(self, agent_config: dict, agent_id: str) -> str:
        """Render system prompt with runtime placeholders."""
        from thoth import __version__

        user_id = agent_config.get('user_id', 'default_user')
        return (
            agent_config['description']
            .replace('{{AGENT_ID}}', agent_id)
            .replace('{{USER_ID}}', user_id)
            .replace('{{SERVER_VERSION}}', __version__)
        )

    async def _ensure_memory_blocks(
        self, client: httpx.AsyncClient, agent_id: str, agent_config: dict
    ):
        """Ensure all required memory blocks exist on the agent (adds missing ones)."""
        try:
            # Get current blocks
            response = await client.get(
                f'{self.letta_base_url}/v1/agents/{agent_id}/core-memory/blocks',
                headers=self.headers,
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

    async def _clear_skill_blocks(
        self, client: httpx.AsyncClient, agent_id: str
    ) -> None:
        """Reset the loaded_skills tracker to its empty default."""
        empty_tracker = (
            '=== Currently Loaded Skills ===\n'
            'Slot 1: [empty]\nSlot 2: [empty]\nSlot 3: [empty]'
        )
        try:
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}/core-memory/blocks/loaded_skills',
                headers=self.headers,
                json={'value': empty_tracker},
            )
        except Exception:
            pass

    async def _attach_tools_by_name(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        tool_names: list[str],
    ) -> None:
        """Attach a list of tools to an agent, looking up IDs from the registry."""
        if not tool_names:
            return
        tool_map = await self._fetch_tool_id_map(client)
        for name in tool_names:
            tid = tool_map.get(name)
            if tid:
                try:
                    await client.patch(
                        f'{self.letta_base_url}/v1/agents/{agent_id}/tools/attach/{tid}',
                        headers=self.headers,
                    )
                except Exception:
                    logger.warning(f'Could not attach {name} to {agent_id[:8]}')

    async def _detach_extra_tools(
        self,
        client: httpx.AsyncClient,
        agent_id: str,
        agent_config: dict,
        keep_extra: set[str] | None = None,
    ) -> None:
        """Detach tools not in the agent's static config or keep_extra set."""
        resp = await client.get(
            f'{self.letta_base_url}/v1/agents/{agent_id}', headers=self.headers
        )
        resp.raise_for_status()
        current_tools = {t['name']: t['id'] for t in resp.json().get('tools', [])}

        allowed = set(agent_config.get('tools', [])) | self.LETTA_BASE_TOOLS
        if keep_extra:
            allowed |= keep_extra

        for name, tid in current_tools.items():
            if name not in allowed:
                try:
                    await client.patch(
                        f'{self.letta_base_url}/v1/agents/{agent_id}/tools/detach/{tid}',
                        headers=self.headers,
                    )
                except Exception:
                    logger.warning(f'Could not detach {name} from {agent_id[:8]}')

    async def _reset_skill_state(
        self, client: httpx.AsyncClient, agent_id: str, agent_config: dict
    ):
        """
        Reconcile skill state on startup.

        If the agent had skills loaded (tracked in agent_loaded_skills),
        re-populate the skill_N memory blocks and re-attach the skill
        tools so they survive a server restart. Otherwise clear everything.
        """
        from thoth.services.skill_service import SkillService

        try:
            postgres = None
            if hasattr(self, '_service_manager') and self._service_manager:
                postgres = getattr(self._service_manager, '_services', {}).get(
                    'postgres'
                )

            # Fetch which skills were loaded before the restart
            previously_loaded: list[str] = []
            if postgres:
                try:
                    rows = await postgres.fetch(
                        'SELECT skill_id FROM agent_loaded_skills '
                        'WHERE agent_id = $1 ORDER BY loaded_at',
                        agent_id,
                    )
                    previously_loaded = [r['skill_id'] for r in rows]
                except Exception as e:
                    logger.warning(
                        f'Could not query loaded skills for {agent_id[:8]}: {e}'
                    )

            if not previously_loaded:
                # Nothing to restore — just make sure blocks and tools are clean
                await self._clear_skill_blocks(client, agent_id)
                await self._detach_extra_tools(client, agent_id, agent_config)
                logger.debug(f'Reset skill state for agent {agent_id[:8]} (no skills)')
                return

            # Re-attach tools for previously loaded skills.
            # Full content is injected by the proxy on the next user message.
            skill_service = SkillService()
            tools_to_attach: list[str] = []
            skill_tools_map: dict[str, list[str]] = {}

            for skill_id in previously_loaded[:3]:
                required_tools = skill_service.get_skill_tools(skill_id)
                skill_tools_map[skill_id] = required_tools
                tools_to_attach.extend(required_tools)

            # Update loaded_skills tracker
            tracker_lines = ['=== Currently Loaded Skills ===']
            for slot in range(1, 4):
                if slot <= len(previously_loaded):
                    sid = previously_loaded[slot - 1]
                    tools = skill_tools_map.get(sid, [])
                    tool_str = ', '.join(tools) if tools else 'no tools'
                    tracker_lines.append(f'Slot {slot}: {sid} (tools: {tool_str})')
                else:
                    tracker_lines.append(f'Slot {slot}: [empty]')

            try:
                await client.patch(
                    f'{self.letta_base_url}/v1/agents/{agent_id}/core-memory/blocks/loaded_skills',
                    headers=self.headers,
                    json={'value': '\n'.join(tracker_lines)},
                )
            except Exception:
                logger.warning(
                    f'Could not update loaded_skills tracker for {agent_id[:8]}'
                )

            # Re-attach skill tools + unload_skill (since skills are loaded)
            unique_tools = list(dict.fromkeys(tools_to_attach))
            if previously_loaded:
                unique_tools.append('unload_skill')
            if len(previously_loaded) >= 3:
                # At capacity — remove load_skill to prevent overload
                pass
            await self._attach_tools_by_name(client, agent_id, unique_tools)

            # Detach anything extra that shouldn't be there
            await self._detach_extra_tools(
                client, agent_id, agent_config, keep_extra=set(unique_tools)
            )

            logger.info(
                f'Restored {len(previously_loaded)} skill(s) for agent {agent_id[:8]}: '
                f'{", ".join(previously_loaded)}'
            )

        except Exception as e:
            logger.warning(f'Could not reconcile skill state for {agent_id[:8]}: {e}')

    async def _verify_archival_memory(
        self, client: httpx.AsyncClient, agent_id: str
    ) -> bool:
        """Quick check that archival memory insert/search works for this agent.

        Agents created without include_base_tools won't have a working passage
        store. Returns False if the endpoint 404s or errors.
        """
        try:
            resp = await client.post(
                f'{self.letta_base_url}/v1/agents/{agent_id}/archival',
                headers=self.headers,
                json={'content': '__thoth_health_check__'},
                timeout=10,
            )
            if resp.status_code in (404, 405):
                return False
            if resp.status_code in (200, 201):
                # Clean up the test entry
                passages = resp.json()
                if isinstance(passages, list):
                    for p in passages:
                        pid = p.get('id')
                        if pid:
                            await client.delete(
                                f'{self.letta_base_url}/v1/agents/{agent_id}/archival/{pid}',
                                headers=self.headers,
                                timeout=10,
                            )
                return True
            return resp.status_code < 400
        except Exception as e:
            logger.warning(f'Archival memory check failed for {agent_id[:8]}: {e}')
            return False

    async def _create_and_attach_block(
        self, client: httpx.AsyncClient, agent_id: str, block_config: dict
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
                    'limit': block_config.get('limit', 2000),
                },
            )
            create_response.raise_for_status()
            block_id = create_response.json()['id']

            # Attach to agent (PATCH, not POST)
            await client.patch(
                f'{self.letta_base_url}/v1/agents/{agent_id}/core-memory/blocks/attach/{block_id}',
                headers=self.headers,
            )
            logger.debug(f'Added missing block: {block_config["label"]}')

        except Exception as e:
            logger.warning(f'Could not add block {block_config["label"]}: {e}')

    async def _attach_filesystem(self, client: httpx.AsyncClient, agent_id: str):
        """Attach filesystem folder to agent for vault access."""
        try:
            # Check if folder exists
            folders_response = await client.get(
                f'{self.letta_base_url}/v1/folders', headers=self.headers
            )

            if folders_response.status_code == 200:
                folders = folders_response.json()
                thoth_folder = next(
                    (f for f in folders if f['name'] == 'thoth_processed_articles'),
                    None,
                )

                if thoth_folder:
                    # Attach folder to agent
                    await client.post(
                        f'{self.letta_base_url}/v1/agents/{agent_id}/folders/{thoth_folder["id"]}',
                        headers=self.headers,
                    )
                    logger.info('Attached filesystem folder to agent')

        except Exception as e:
            logger.warning(f'Could not attach filesystem: {e}')

    async def _sync_external_mcp_tools(self, _agent_ids: dict[str, str]) -> None:
        """
        Sync external MCP tools to initialized agents.

        Args:
            _agent_ids: Dictionary mapping agent names to agent IDs (reserved for
                future per-agent tool attachment).
        """
        try:
            # Use the stored service_manager if available, otherwise create new instance
            if hasattr(self, '_service_manager') and self._service_manager:
                service_manager = self._service_manager
            else:
                from thoth.services.service_manager import ServiceManager

                service_manager = ServiceManager()

            mcp_manager = service_manager.get_service('mcp_servers_manager')

            if not mcp_manager:
                logger.debug(
                    'MCP Servers Manager not available, skipping external tool sync'
                )
                return

            # Trigger tool sync to all agents
            await mcp_manager.sync_tools_to_agents()
            logger.info('Synced external MCP tools to agents')

        except Exception as e:
            logger.warning(f'Could not sync external MCP tools: {e}')
