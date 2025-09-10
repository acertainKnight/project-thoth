"""
Subagent Factory for creating specialized agents from natural language descriptions.

This module implements Claude Code-style agent creation where users can describe
what they want and get a specialized agent automatically created.
"""

import re
from datetime import datetime
from pathlib import Path

from loguru import logger

from thoth.tools.unified_registry import UnifiedToolRegistry

from .schemas import AgentConfig

try:
    from letta_client import AgentState
    from letta_client import Letta as LettaClient

    LETTA_AVAILABLE = True
    logger.info('Letta client available for subagent factory')
except ImportError as e:
    LETTA_AVAILABLE = False
    logger.error(
        f'Letta client not available - subagent creation will not function: {e}'
    )
    raise ImportError(f'Letta client required for subagent creation: {e}') from e


class SubagentFactory:
    """
    Creates specialized agents from natural language descriptions.

    This factory uses LLM analysis to extract agent requirements from user descriptions
    and creates appropriately configured Letta agents with the right tools and memory.
    """

    @classmethod
    def get_tool_sets(cls) -> dict[str, list[str]]:
        """Get tool sets for different agent types."""
        return {
            'research': [
                'thoth_search_papers',
                'thoth_analyze_document',
                'thoth_rag_search',
                'thoth_web_search',
            ],
            'analysis': [
                'thoth_analyze_document',
                'thoth_extract_citations',
                'thoth_rag_search',
                'analyze_document',  # LangGraph pipeline
            ],
            'discovery': [
                'thoth_discover_papers',
                'thoth_search_papers',
                'thoth_web_search',
                'thoth_monitor_sources',
            ],
            'citation': [
                'thoth_extract_citations',
                'thoth_analyze_citations',
                'extract_citations',  # LangGraph pipeline
                'thoth_search_papers',
            ],
            'synthesis': [
                'thoth_rag_search',
                'thoth_generate_summary',
                'thoth_analyze_document',
                'thoth_search_papers',
            ],
        }

    @classmethod
    def get_prompt_templates(cls) -> dict[str, str]:
        """Get system prompt templates for different agent types."""
        return {
            'research': """You are a specialized research assistant focused on {domain}. Your role is to:

1. Help users find and analyze relevant research papers
2. Provide insights on current research trends and gaps
3. Assist with literature reviews and research methodology
4. Connect related research across different papers and authors

Always cite your sources and provide evidence-based responses. Focus on academic rigor and scientific accuracy.""",
            'analysis': """You are a document analysis specialist focused on {domain}. Your expertise includes:

1. Deep analysis of research papers and academic documents
2. Extraction of key findings, methodologies, and conclusions
3. Critical evaluation of research quality and methodology
4. Comparison and synthesis of multiple documents

Provide thorough, analytical responses with specific references to document sections and evidence.""",
            'discovery': """You are a research discovery agent specializing in {domain}. Your mission is to:

1. Find new and relevant research papers across multiple sources
2. Monitor emerging trends and breakthrough research
3. Identify influential authors and research groups
4. Track the evolution of research topics over time

Stay current with the latest research and help users discover relevant work they might have missed.""",
            'citation': """You are a citation analysis expert specializing in {domain}. You excel at:

1. Extracting and analyzing citation patterns in research papers
2. Identifying key influential papers and authors
3. Mapping citation networks and research genealogies
4. Evaluating research impact and influence

Provide detailed citation analysis with quantitative insights and network visualizations when possible.""",
            'synthesis': """You are a knowledge synthesis specialist for {domain}. Your strengths include:

1. Combining insights from multiple research papers
2. Identifying common themes and contradictions across research
3. Creating comprehensive overviews of research areas
4. Generating research summaries and reports

Focus on creating coherent, well-structured syntheses that highlight key insights and relationships.""",
        }

    def __init__(
        self,
        letta_client: LettaClient,
        workspace_dir: Path,
        service_manager,
        tool_registry: UnifiedToolRegistry | None = None,
    ):
        """
        Initialize the subagent factory.

        Args:
            letta_client: Connected Letta client instance (required)
            workspace_dir: Directory for storing agent configurations
            service_manager: Service manager for tool access
            tool_registry: Optional unified tool registry for assigning tools to agents
        """
        # Note: letta_client can be None initially, will be set later in orchestrator

        self.client = letta_client
        self.workspace_dir = workspace_dir
        self.service_manager = service_manager
        self.tool_registry = tool_registry

        logger.info('SubagentFactory initialized with Letta client')

    async def setup(self) -> None:
        """Set up the factory with default templates and system agents."""
        try:
            await self._create_agent_templates()
            await self._create_default_system_agents()
            logger.info('Subagent factory setup completed')
        except Exception as e:
            logger.error(f'Error setting up subagent factory: {e}')

    async def create_from_chat(self, description: str, user_id: str) -> str:
        """
        Create agent from natural language description using Letta.

        Args:
            description: User's description of desired agent
            user_id: ID of user creating the agent

        Returns:
            Success message with agent details
        """
        if not self.client:
            raise ValueError('Letta client must be set before creating agents')

        try:
            # Extract agent configuration from description
            logger.info(
                f'Creating Letta agent from description: {description[:100]}...'
            )
            config = await self._extract_agent_config(description, user_id)

            # Generate unique agent name for Letta
            letta_agent_name = f'{user_id}_{config.name.replace("-", "_")}'

            # Check if agent already exists in Letta
            existing_agents = self.client.agents.list()
            if any(agent.name == letta_agent_name for agent in existing_agents):
                return f' Agent @{config.name} already exists. Please choose a different name or description.'

            # Create Letta agent
            letta_agent = await self._create_letta_agent(config, letta_agent_name)
            if not letta_agent:
                return ' Failed to create agent in Letta. Please try again.'

            # Generate success response
            success_message = f""" **Created @{config.name}**

**Type:** {config.type.title()} Agent
**Description:** {config.description}

**Capabilities:**
{self._format_capabilities_list(config.capabilities)}

**Tools:** {len(config.tools)} specialized tools assigned
**Memory:** Persistent memory with {len(config.memory_blocks)} blocks

 **Usage:** Mention @{config.name} in your messages to use this agent
 **Example:** "@{config.name} help me analyze this paper"

🔗 **Letta Agent ID:** {letta_agent.id}
"""

            logger.info(
                f'Successfully created Letta agent {letta_agent_name} for user {user_id}'
            )
            return success_message

        except Exception as e:
            logger.error(f'Error creating Letta agent from chat: {e}')
            return f' Error creating agent: {e!s}. Please try with a different description.'

    async def _extract_agent_config(
        self, description: str, user_id: str
    ) -> AgentConfig:
        """
        Extract agent configuration from natural language description using LLM.

        This method uses the LLM service to intelligently parse user intent
        and create an appropriate agent configuration.
        """
        try:
            # Use LLM to extract structured configuration
            extraction_prompt = f"""
            Parse this agent creation request and return a JSON configuration:
            "{description}"

            Return JSON with these fields:
            {{
                "type": "research|analysis|discovery|citation|synthesis",
                "name": "short-descriptive-name-in-kebab-case",
                "domain": "specific academic field if mentioned, null if general",
                "focus": "primary focus area in 2-3 words",
                "capabilities": ["capability1", "capability2", "capability3"]
            }}

            Guidelines:
            - Choose the most specific type based on the request
            - Name should be concise and descriptive (e.g. "ml-paper-analyst")
            - Domain should be specific (e.g. "machine learning", "neuroscience")
            - Capabilities should be concrete and actionable
            """

            # Extract configuration using LLM service
            config_json = await self.service_manager.llm_service.extract_json(
                prompt=extraction_prompt
            )

            # Validate and set defaults
            agent_type = config_json.get('type', 'research')
            prompt_templates = self.get_prompt_templates()
            if agent_type not in prompt_templates:
                agent_type = 'research'

            agent_name = config_json.get('name', 'custom-agent')
            domain = config_json.get('domain')
            focus = config_json.get('focus', 'academic research')

            # Generate system prompt
            template = prompt_templates[agent_type]
            system_prompt = template.format(domain=domain or focus)

            # Select tools using unified registry or fallback to hardcoded sets
            if self.tool_registry:
                tools = self.tool_registry.get_tools_for_agent(agent_type)
            else:
                tool_sets = self.get_tool_sets()
                tools = tool_sets.get(agent_type, tool_sets['research']).copy()

            # Use LLM-provided capabilities or generate defaults
            capabilities = config_json.get(
                'capabilities', self._get_default_capabilities(agent_type)
            )

            # Create memory blocks for agent type
            memory_blocks = self._create_memory_blocks(agent_type)

            config = AgentConfig(
                name=agent_name,
                description=self._clean_description(description),
                type=agent_type,
                system_prompt=system_prompt,
                tools=tools,
                memory_blocks=memory_blocks,
                capabilities=capabilities,
                created_by=user_id,
                created_at=datetime.now(),
                is_system=False,
            )

            return config

        except Exception as e:
            logger.error(f'LLM-based config extraction failed: {e}')
            # Fallback to simple default agent
            return self._create_fallback_agent_config(description, user_id)

    def _get_default_capabilities(self, agent_type: str) -> list[str]:
        """Get default capabilities for agent type."""
        base_capabilities = {
            'research': ['Literature search', 'Research methodology', 'Trend analysis'],
            'analysis': [
                'Document analysis',
                'Critical evaluation',
                'Methodology assessment',
            ],
            'discovery': ['Source monitoring', 'Trend detection', 'Author tracking'],
            'citation': ['Citation extraction', 'Impact analysis', 'Network mapping'],
            'synthesis': [
                'Knowledge synthesis',
                'Summary generation',
                'Cross-paper analysis',
            ],
        }
        return base_capabilities.get(agent_type, base_capabilities['research'])

    def _create_fallback_agent_config(
        self, description: str, user_id: str
    ) -> AgentConfig:
        """Create a simple fallback agent when LLM extraction fails."""
        prompt_templates = self.get_prompt_templates()
        tool_sets = self.get_tool_sets()
        return AgentConfig(
            name='custom-research-agent',
            description=self._clean_description(description),
            type='research',
            system_prompt=prompt_templates['research'].format(
                domain='academic research'
            ),
            tools=tool_sets['research'].copy(),
            memory_blocks=self._create_memory_blocks('research'),
            capabilities=self._get_default_capabilities('research'),
            created_by=user_id,
            created_at=datetime.now(),
            is_system=False,
        )

    def _clean_description(self, description: str) -> str:
        """Clean and format the description."""
        # Remove creation language and normalize
        cleaned = re.sub(
            r'^(create?|make|build|new)\s+(an?\s+)?agent\s+(that\s+|to\s+|for\s+)?',
            '',
            description.lower(),
        )
        return cleaned.strip().capitalize()

    def _create_memory_blocks(self, agent_type: str) -> dict[str, int]:
        """Create appropriate memory blocks for agent type."""
        base_blocks = {'identity': 2000, 'context': 3000}

        type_specific = {
            'research': {'research_focus': 4000, 'key_papers': 3000},
            'analysis': {'analysis_methods': 3000, 'findings': 4000},
            'discovery': {'sources': 3000, 'recent_papers': 4000},
            'citation': {'citation_patterns': 4000, 'key_authors': 3000},
            'synthesis': {'synthesis_themes': 4000, 'connections': 3000},
        }

        base_blocks.update(type_specific.get(agent_type, type_specific['research']))
        return base_blocks

    async def _create_letta_agent(
        self, config: AgentConfig, letta_agent_name: str
    ) -> AgentState | None:
        """Create Letta agent from configuration using proper Letta API."""
        try:
            # Create memory blocks following current Letta API format
            memory_blocks = [
                {
                    'label': 'persona',
                    'value': f'I am {config.name}, a specialized {config.type} agent. {config.description}. My expertise includes: {", ".join(config.capabilities)}.',
                },
                {
                    'label': 'human',
                    'value': 'The user is a researcher who needs specialized assistance with academic research tasks.',
                },
            ]

            # Add specialized memory blocks based on agent type
            if config.type == 'research':
                memory_blocks.append(
                    {
                        'label': 'research_context',
                        'value': 'Current research topics and active investigations will be tracked here.',
                    }
                )
            elif config.type == 'citation':
                memory_blocks.append(
                    {
                        'label': 'citation_patterns',
                        'value': 'Citation networks and bibliographic patterns will be stored here.',
                    }
                )
            elif config.type == 'discovery':
                memory_blocks.append(
                    {
                        'label': 'sources_tracked',
                        'value': 'Research sources and monitoring targets will be maintained here.',
                    }
                )
            elif config.type == 'analysis':
                memory_blocks.append(
                    {
                        'label': 'analysis_findings',
                        'value': 'Key findings and analysis results will be accumulated here.',
                    }
                )
            elif config.type == 'synthesis':
                memory_blocks.append(
                    {
                        'label': 'synthesis_themes',
                        'value': 'Cross-paper themes and connections will be organized here.',
                    }
                )

            # Create agent using Letta's built-in sleep-time memory management
            agent = self.client.agents.create(
                name=letta_agent_name,
                memory_blocks=memory_blocks,
                system=config.system_prompt,
                tools=config.tools,  # Tools assigned during creation
                enable_sleeptime=True,  # Enable Letta's automatic memory management
                # Optional: specify LLM and embedding models
                # llm_config={'model': 'openai/gpt-4'},
                # embedding_config={'model': 'openai/text-embedding-3-small'}
            )

            # Log successful tool assignment (tools assigned during creation)
            if config.tools:
                logger.info(
                    f'Created agent {agent.name} with {len(config.tools)} tools: {config.tools}'
                )

            # Additional tool assignment via registry if needed
            if self.tool_registry and hasattr(
                self.tool_registry, 'assign_tools_to_agent'
            ):
                additional_success = self.tool_registry.assign_tools_to_agent(
                    agent.id, config.tools
                )
                if additional_success:
                    logger.info(
                        f'Additional tool registry assignment successful for agent {agent.name}'
                    )
                else:
                    logger.warning(
                        f'Additional tool assignment partially failed for agent {agent.name}'
                    )

            logger.info(f'Created Letta agent: {agent.name} with ID: {agent.id}')
            return agent

        except Exception as e:
            logger.error(f'Failed to create Letta agent {letta_agent_name}: {e}')
            return None

    async def _agent_exists(self, agent_name: str, user_id: str) -> bool:
        """Check if agent already exists in Letta."""
        try:
            existing_agents = self.client.agents.list()
            letta_agent_name = f'{user_id}_{agent_name.replace("-", "_")}'

            # Check if agent with this name already exists
            return any(agent.name == letta_agent_name for agent in existing_agents)

        except Exception as e:
            logger.error(f'Error checking agent existence: {e}')
            return False

    def _format_capabilities_list(self, capabilities: list[str]) -> str:
        """Format capabilities as bullet points."""
        return '\n'.join(f'  • {cap}' for cap in capabilities)

    async def _create_agent_templates(self) -> None:
        """Create agent templates for common use cases."""
        # This would create template YAML files
        logger.info('Agent templates creation not yet implemented')
        pass

    async def _create_default_system_agents(self) -> None:
        """Create default system agents directly in Letta if they don't exist."""
        try:
            # Check existing agents in Letta
            existing_agents = self.client.agents.list()
            existing_names = [agent.name for agent in existing_agents]

            default_agents = [
                {
                    'name': 'system_citation_analyzer',
                    'description': 'Extracts and analyzes citations in research papers',
                    'type': 'citation',
                },
                {
                    'name': 'system_paper_reviewer',
                    'description': 'Reviews papers for quality, methodology, and insights',
                    'type': 'analysis',
                },
                {
                    'name': 'system_discovery_scout',
                    'description': 'Finds new papers and tracks research trends',
                    'type': 'discovery',
                },
                {
                    'name': 'system_synthesis_expert',
                    'description': 'Synthesizes insights across multiple research papers',
                    'type': 'synthesis',
                },
            ]

            for agent_info in default_agents:
                if agent_info['name'] not in existing_names:
                    try:
                        # Create system agent configuration
                        prompt_templates = self.get_prompt_templates()
                        tool_sets = self.get_tool_sets()
                        config = AgentConfig(
                            name=agent_info['name'],
                            description=agent_info['description'],
                            type=agent_info['type'],
                            system_prompt=prompt_templates[agent_info['type']].format(
                                domain='academic research'
                            ),
                            tools=tool_sets[agent_info['type']],
                            memory_blocks=self._create_memory_blocks(
                                agent_info['type']
                            ),
                            capabilities=self._get_default_capabilities(
                                agent_info['type']
                            ),
                            created_by='system',
                            is_system=True,
                        )

                        # Create agent directly in Letta
                        await self._create_letta_agent(config, agent_info['name'])
                        logger.info(
                            f'Created default system agent: {agent_info["name"]}'
                        )

                    except Exception as e:
                        logger.error(
                            f'Failed to create system agent {agent_info["name"]}: {e}'
                        )

            logger.info('Default system agents setup completed')

        except Exception as e:
            logger.error(f'Error setting up default system agents: {e}')
