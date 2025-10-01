"""
Main orchestrator for Thoth agent system.

This orchestrator provides Claude Code-style subagent creation and management
using either Letta integration or native Thoth agents as fallback.
"""

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass  # Letta types handled at runtime

from loguru import logger

from thoth.services.service_manager import ServiceManager
from thoth.tools.unified_registry import initialize_unified_registry

# Native agent system removed - using Letta exclusively
from .smart_workflows import SmartWorkflowEngine
from .subagent_factory import SubagentFactory

# Import Letta client for agent orchestration
try:
    from letta_client import Letta as LettaClient

    LETTA_AVAILABLE = True
    logger.info('Letta client available for agent orchestration')
except ImportError as e:
    LETTA_AVAILABLE = False
    LettaClient = None
    logger.warning(f'Letta client not available - using fallback mode: {e}')


class ThothOrchestrator:
    """
    Main orchestrator for agent management.

    This class handles:
    - Routing messages to appropriate agents
    - Creating new agents from chat descriptions
    - Managing agent lifecycle and persistence
    - Coordinating between main agent and subagents

    Uses native Thoth agents with optional Letta integration for enhanced capabilities.
    """

    def __init__(
        self, service_manager: ServiceManager, workspace_dir: Path | None = None
    ):
        """
        Initialize the orchestrator.

        Args:
            service_manager: Thoth service manager for tool access
            workspace_dir: Directory for agent storage
        """
        self.service_manager = service_manager
        self.workspace_dir = workspace_dir or Path('./workspace')

        # Initialize Letta service (handles desktop/server mode automatically)
        self.letta_service = None
        self.letta_client: Any = None
        self._use_fallback = not LETTA_AVAILABLE

        # Core components
        self.main_agent_id: str | None = None
        self.unified_registry = None  # Will be initialized in setup()
        self.smart_workflow_engine = None  # Single unified workflow engine
        self.agent_factory = SubagentFactory(
            letta_client=self.letta_client,
            workspace_dir=self.workspace_dir,
            service_manager=service_manager,
            tool_registry=None,  # Will be set after registry initialization
        )

        logger.info(
            'ThothOrchestrator initialized - Letta service will be configured during setup'
        )

    def _ensure_letta_client(self) -> Any:
        """Ensure Letta client is available and return it."""
        if not self.letta_client:
            raise RuntimeError('Letta client not initialized. Call setup() first.')
        return self.letta_client

    async def setup(self) -> None:
        """
        Set up the orchestrator with main agent and system agents.
        Must be called after initialization.
        """
        try:
            if not LETTA_AVAILABLE:
                logger.info('Letta not available - using fallback mode')
                self._use_fallback = True
                return

            # Initialize Letta service (handles desktop/server mode detection)
            logger.info('Initializing Letta service...')
            self.letta_service = self.service_manager.get_service('letta')
            await self.letta_service.initialize()
            self.letta_client = self.letta_service.get_client()

            # Initialize unified tool registry
            logger.info('Initializing unified tool registry...')
            self.unified_registry = await initialize_unified_registry(
                self.service_manager, self.letta_client
            )

            # Initialize smart workflow engine (unified approach)
            logger.info('Initializing smart multi-agent workflow engine...')
            self.smart_workflow_engine = SmartWorkflowEngine(
                letta_client=self.letta_client, service_manager=self.service_manager
            )
            logger.info(
                'Smart workflow engine initialized - automatically chooses optimal approach'
            )

            # Update agent factory with the registry
            self.agent_factory.tool_registry = self.unified_registry

            # Update agent factory to use the new Letta client
            self.agent_factory.client = self.letta_client

            # Initialize main research agent
            await self._init_main_agent()

            # Load existing system agents
            await self._load_system_agents()

            # Setup agent factory
            await self.agent_factory.setup()

            # Initialize memory management system
            logger.info('Setting up memory management system...')
            await self._setup_memory_management()

            logger.info('ThothOrchestrator setup completed successfully')

        except Exception as e:
            logger.error(f'Failed to setup orchestrator: {e}')
            logger.info('Falling back to basic mode due to setup errors')
            self._use_fallback = True

    async def _setup_memory_management(self) -> None:
        """Setup Letta-native memory management."""
        try:
            # All agents created will use Letta's built-in sleep-time memory management
            # No custom scheduling needed - Letta handles this automatically
            logger.info('Memory management delegated to Letta sleep-time agents')

        except Exception as e:
            logger.error(f'Memory management setup failed: {e}')
            raise

    async def get_agent_memory_info(self, agent_id: str) -> dict[str, Any]:
        """Get memory information for an agent using Letta's APIs."""
        try:
            if not self.letta_service:
                return {'error': 'Letta service not initialized'}

            return await self.letta_service.get_agent_memory_usage(agent_id)

        except Exception as e:
            logger.error(f'Failed to get memory info for agent {agent_id}: {e}')
            return {'error': str(e)}

    async def get_agent_conversation_history(
        self, agent_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Get conversation history for an agent."""
        try:
            if not self.letta_service:
                return []

            return await self.letta_service.get_agent_conversation_history(
                agent_id, limit
            )

        except Exception as e:
            logger.error(
                f'Failed to get conversation history for agent {agent_id}: {e}'
            )
            return []

    async def handle_message(
        self, message: str, user_id: str, _thread_id: str | None = None
    ) -> str:
        """
        Route messages to appropriate agents.

        Args:
            message: User message
            user_id: ID of user sending message
            thread_id: Optional thread ID for conversation tracking

        Returns:
            Agent response
        """
        try:
            # Use fallback mode if Letta is not available
            if self._use_fallback:
                return self._fallback_response(message)

            # Check for agent creation commands
            if self._is_agent_creation(message):
                logger.info(f'Agent creation request detected from user {user_id}')
                return await self.agent_factory.create_from_chat(message, user_id)

            # Check for @agent mentions
            agent_mentions = self._extract_agent_mentions(message)
            if agent_mentions:
                agent_name = agent_mentions[0]  # Use first mentioned agent
                logger.info(f'Routing message to agent: @{agent_name}')
                return await self._route_to_agent(message, agent_name, user_id)

            # Check for list agents request
            if self._is_list_agents(message):
                return await self._list_available_agents(user_id)

            # Check for list workflows request
            if self._is_list_workflows(message):
                return await self.list_workflows()

            # Check for workflow requests (automatic detection)
            workflow_request = self._detect_workflow_request(message)
            if workflow_request:
                logger.info(
                    f'Multi-agent collaboration detected for: {workflow_request}'
                )
                return await self._execute_workflow_from_message(
                    message, workflow_request, user_id
                )

            # Try auto-selection of best agent
            auto_agent = await self._auto_select_agent(message, user_id)
            if auto_agent:
                logger.info(f'Auto-selected agent: {auto_agent}')
                return await self._route_to_agent(message, auto_agent, user_id)

            # Default to main agent
            logger.info('Routing to main research agent')
            return await self._send_to_main_agent(message, user_id)

        except Exception as e:
            logger.error(f'Error handling message: {e}')
            return f' Error processing your request: {e!s}'

    def _is_agent_creation(self, message: str) -> bool:
        """Check if message is requesting agent creation."""
        patterns = [
            r'create.*agent',
            r'make.*agent',
            r'build.*agent',
            r'new.*agent',
            r'add.*agent',
        ]
        message_lower = message.lower()
        return any(re.search(pattern, message_lower) for pattern in patterns)

    def _extract_agent_mentions(self, message: str) -> list[str]:
        """Extract @agent-name mentions from message."""
        # Use word boundary to avoid matching email addresses
        pattern = r'(?<!\w)@([a-z][-a-z]*[a-z]|[a-z]+)(?=\s|$|[^\w.-])'
        matches = re.findall(pattern, message.lower())
        return [
            match for match in matches if match != 'agent'
        ]  # Filter out generic @agent

    def _is_list_agents(self, message: str) -> bool:
        """Check if message is requesting list of agents."""
        patterns = [
            r'list.*agents?',
            r'show.*agents?',
            r'what.*agents?',
            r'available.*agents?',
            r'my.*agents?',
        ]
        message_lower = message.lower()
        return any(re.search(pattern, message_lower) for pattern in patterns)

    def _is_list_workflows(self, message: str) -> bool:
        """Check if message is requesting list of workflows."""
        patterns = [
            r'list.*workflows?',
            r'show.*workflows?',
            r'what.*workflows?',
            r'available.*workflows?',
            r'multi.*agent.*workflows?',
        ]
        message_lower = message.lower()
        return any(re.search(pattern, message_lower) for pattern in patterns)

    async def _route_to_agent(
        self, message: str, agent_name: str, _user_id: str
    ) -> str:
        """Route message to specific Letta agent."""
        try:
            # Get agent from Letta server
            agents = self.letta_client.agents.list()
            target_agent = None

            for agent in agents:
                if agent.name == agent_name:
                    target_agent = agent
                    break

            if not target_agent:
                return f" Agent @{agent_name} not found. Use 'list agents' to see available agents."

            # Send message to Letta agent
            response = self.letta_client.agents.messages.create(
                agent_id=target_agent.id,
                messages=[{'role': 'user', 'content': message}],
            )

            # Extract the assistant's response
            assistant_messages = [
                msg
                for msg in response.messages
                if msg.role == 'assistant' and msg.content
            ]

            if assistant_messages:
                agent_response = assistant_messages[-1].content
                return f'[@{agent_name}]: {agent_response}'
            else:
                return f'[@{agent_name}]: No response generated'

        except Exception as e:
            logger.error(f'Error routing to Letta agent {agent_name}: {e}')
            return f' Error communicating with @{agent_name}: {e!s}'

    async def _auto_select_agent(self, message: str, user_id: str) -> str | None:
        """Automatically select best Letta agent for the task."""
        try:
            # Get available agents from Letta
            available_agents = self.letta_client.agents.list()
            if not available_agents:
                return None

            # Filter to user-created and system agents only
            user_agents = [
                agent
                for agent in available_agents
                if agent.name.startswith(f'{user_id}_')
                or agent.name.startswith('system_')
            ]

            if not user_agents:
                return None

            # Simple rule-based selection based on message content and agent names
            message_lower = message.lower()

            # Check for task-specific keywords in agent names
            for agent in user_agents:
                agent_name_lower = agent.name.lower()

                if 'citation' in agent_name_lower and any(
                    keyword in message_lower
                    for keyword in ['citation', 'reference', 'bibliograph', 'cite']
                ):
                    return agent.name
                elif 'analysis' in agent_name_lower and any(
                    keyword in message_lower
                    for keyword in ['analy', 'review', 'evaluat', 'assess']
                ):
                    return agent.name
                elif 'discovery' in agent_name_lower and any(
                    keyword in message_lower
                    for keyword in ['find', 'discover', 'search']
                ):
                    return agent.name
                elif 'synthesis' in agent_name_lower and any(
                    keyword in message_lower
                    for keyword in ['summary', 'synth', 'combin']
                ):
                    return agent.name

            # If main agent is available, ask it to select
            if self.main_agent_id and len(user_agents) > 0:
                try:
                    agent_names = [agent.name for agent in user_agents]
                    selection_prompt = f"""
                    Given this user message: "{message}"

                    Which of these available agents would be best suited to handle this request?
                    Available agents: {', '.join(agent_names)}

                    Respond with just the agent name (without @), or 'none' if no specific agent is needed.
                    """

                    response = self.letta_client.agents.messages.create(
                        agent_id=self.main_agent_id,
                        messages=[{'role': 'user', 'content': selection_prompt}],
                    )

                    assistant_messages = [
                        msg
                        for msg in response.messages
                        if msg.role == 'assistant' and msg.content
                    ]

                    if assistant_messages:
                        selected_agent = assistant_messages[-1].content.strip().lower()
                        # Validate selection
                        if selected_agent in agent_names and selected_agent != 'none':
                            return selected_agent
                except Exception as e:
                    logger.debug(f'Main agent selection failed: {e}')

            return None

        except Exception as e:
            logger.error(f'Error in auto agent selection: {e}')
            return None

    async def _send_to_main_agent(self, message: str, _user_id: str) -> str:
        """Send message to main Letta orchestrator agent."""
        if not self.main_agent_id:
            return ' Main agent not available. Please try again later.'

        try:
            response = self.letta_client.agents.messages.create(
                agent_id=self.main_agent_id,
                messages=[{'role': 'user', 'content': message}],
            )

            # Extract the assistant's response
            assistant_messages = [
                msg
                for msg in response.messages
                if msg.role == 'assistant' and msg.content
            ]

            if assistant_messages:
                return assistant_messages[-1].content
            else:
                return ' Main agent did not provide a response'

        except Exception as e:
            logger.error(f'Error communicating with main Letta agent: {e}')
            return f' Error processing request: {e!s}'

    async def _init_main_agent(self) -> str | None:
        """Initialize or load the main orchestrator agent using Letta."""
        try:
            # Try to find existing main agent
            agents = self.letta_client.agents.list()
            for agent in agents:
                if agent.name == 'thoth_main_orchestrator':
                    logger.info('Found existing main orchestrator agent')
                    self.main_agent_id = agent.id
                    return agent.id

            # Create new main agent with proper Letta API
            main_agent = self.letta_client.agents.create(
                name='thoth_main_orchestrator',
                llm_config={
                    'model': 'gpt-4o-mini',
                    'model_endpoint_type': 'openai',
                    'context_window': 128000,
                },
                embedding_config={
                    'embedding_model': 'text-embedding-ada-002',
                    'embedding_endpoint_type': 'openai',
                    'embedding_dim': 1536,
                },
                memory_blocks=[
                    {
                        'label': 'persona',
                        'value': 'I am the main Thoth research assistant orchestrator. I coordinate with specialized agents and help users with academic research tasks including paper analysis, literature review, citation management, and knowledge synthesis.',
                    },
                    {
                        'label': 'human',
                        'value': 'The user is a researcher who needs assistance with academic research tasks.',
                    },
                    {
                        'label': 'available_agents',
                        'value': 'List of available specialized agents and their capabilities will be populated here.',
                    },
                ],
                system="""You are the main Thoth research assistant orchestrator. You help users with academic research by:

1. Understanding their research needs and providing direct assistance
2. Routing complex tasks to appropriate specialized agents when they exist
3. Coordinating multi-agent workflows when needed
4. Helping users discover and use available specialized agents
5. Providing comprehensive research assistance including paper analysis, literature reviews, and knowledge synthesis

When users ask about agents, explain what's available and how to use them with @agent-name syntax.
Always be helpful, thorough, and focused on advancing their research goals.

Available tools will include research paper search, document analysis, citation extraction, and knowledge synthesis capabilities.""",
                tools=[],  # Tools will be registered separately
            )

            self.main_agent_id = main_agent.id
            logger.info(f'Created new main orchestrator agent with ID: {main_agent.id}')
            return main_agent.id

        except Exception as e:
            logger.error(f'Failed to initialize main Letta agent: {e}')
            return None

    def _fallback_response(self, _message: str) -> str:
        """Fallback response when Letta is not available."""
        return """ Letta agent system is not available.

This could be because:
- Letta server is not running (check Docker services)
- Connection configuration is incorrect
- Dependencies are missing

Please check the system status and try again."""

    async def _list_available_agents(self, user_id: str) -> str:
        """List all available Letta agents for the user."""
        try:
            # Get all agents from Letta
            all_agents = self.letta_client.agents.list()

            # Filter agents by type
            system_agents = [
                agent
                for agent in all_agents
                if agent.name.startswith('system_')
                or agent.name == 'thoth_main_orchestrator'
            ]
            user_agents = [
                agent for agent in all_agents if agent.name.startswith(f'{user_id}_')
            ]

            response_parts = [' **Available Agents**\n']

            if system_agents:
                response_parts.append('**System Agents:**')
                for agent in system_agents:
                    # Extract description from agent metadata if available
                    description = getattr(agent, 'description', 'Research assistant')
                    if agent.name == 'thoth_main_orchestrator':
                        description = 'Main research orchestrator and coordinator'
                    response_parts.append(f'  • @{agent.name} - {description}')
                response_parts.append('')

            if user_agents:
                response_parts.append('**Your Custom Agents:**')
                for agent in user_agents:
                    # Extract description from agent name or metadata
                    agent_type = (
                        agent.name.replace(f'{user_id}_', '').replace('_', ' ').title()
                    )
                    description = f'Your custom {agent_type} agent'
                    response_parts.append(f'  • @{agent.name} - {description}')
                response_parts.append('')

            if not system_agents and not user_agents:
                response_parts.append('No agents currently available.')
                response_parts.append('')

            response_parts.append(
                ' **Usage:** Mention any agent with @agent-name in your message'
            )
            response_parts.append(
                "✨ **Create:** Say 'create an agent that...' to make new specialized agents"
            )
            response_parts.append(
                "🔄 **Workflows:** Use 'list workflows' to see multi-agent collaboration options"
            )

            return '\n'.join(response_parts)

        except Exception as e:
            logger.error(f'Error listing Letta agents: {e}')
            return ' Error retrieving agent list. Please try again.'

    async def _load_system_agents(self) -> None:
        """Load predefined system agents from Letta server."""
        try:
            # Check if system agents already exist
            agents = self.letta_client.agents.list()
            existing_system_agents = [
                agent.name for agent in agents if agent.name.startswith('system_')
            ]

            # Define default system agents to create if they don't exist
            default_system_agents = [
                {
                    'name': 'system_citation_analyzer',
                    'description': 'Specialized in citation extraction and analysis',
                    'system_prompt': """You are a specialized citation analysis agent. Your expertise includes:

1. Extracting citations from academic papers
2. Analyzing citation patterns and networks
3. Identifying key references and influential works
4. Formatting citations in various academic styles (APA, MLA, IEEE, etc.)
5. Finding bibliographic information for incomplete citations

You have access to research tools and databases to help with citation analysis tasks.""",
                },
                {
                    'name': 'system_discovery_scout',
                    'description': 'Specialized in research paper discovery and literature search',
                    'system_prompt': """You are a specialized research discovery agent. Your expertise includes:

1. Finding relevant academic papers across multiple databases
2. Literature search and systematic reviews
3. Identifying emerging research trends and topics
4. Filtering and ranking papers by relevance
5. Cross-referencing related works and authors

You have access to multiple research databases and search tools.""",
                },
                {
                    'name': 'system_analysis_expert',
                    'description': 'Specialized in deep document analysis and critical evaluation',
                    'system_prompt': """You are a specialized analysis agent. Your expertise includes:

1. Deep critical analysis of research papers
2. Methodology evaluation and critique
3. Identifying strengths and limitations in research
4. Comparative analysis across multiple papers
5. Synthesizing insights from complex documents

You excel at providing thorough, objective analysis of academic content.""",
                },
            ]

            # Create missing system agents
            for agent_config in default_system_agents:
                if agent_config['name'] not in existing_system_agents:
                    try:
                        _system_agent = self.letta_client.agents.create(
                            name=agent_config['name'],
                            llm_config={
                                'model': 'gpt-4o-mini',
                                'model_endpoint_type': 'openai',
                                'context_window': 128000,
                            },
                            embedding_config={
                                'embedding_model': 'text-embedding-ada-002',
                                'embedding_endpoint_type': 'openai',
                                'embedding_dim': 1536,
                            },
                            memory_blocks=[
                                {
                                    'label': 'persona',
                                    'value': agent_config['description'],
                                },
                                {
                                    'label': 'human',
                                    'value': 'The user is a researcher who needs specialized assistance.',
                                },
                            ],
                            system=agent_config['system_prompt'],
                            tools=[],  # Tools will be registered separately
                        )
                        logger.info(f'Created system agent: {agent_config["name"]}')
                    except Exception as e:
                        logger.error(
                            f'Failed to create system agent {agent_config["name"]}: {e}'
                        )

        except Exception as e:
            logger.error(f'Error loading system agents: {e}')

    def _detect_workflow_request(self, message: str) -> str | None:
        """Detect if message is requesting a multi-agent workflow."""
        message_lower = message.lower()

        # Check for explicit workflow mentions
        if any(
            keyword in message_lower
            for keyword in [
                'literature review',
                'lit review',
                'citation network',
                'citation analysis',
                'research validation',
                'validate research',
                'comprehensive analysis',
                'multi-step analysis',
            ]
        ):
            if 'literature review' in message_lower or 'lit review' in message_lower:
                return 'literature_review'
            elif (
                'citation network' in message_lower
                or 'citation analysis' in message_lower
            ):
                return 'citation_network'
            elif (
                'research validation' in message_lower
                or 'validate research' in message_lower
            ):
                return 'research_validation'

        # Check for complex task patterns that would benefit from workflows
        complex_patterns = [
            r'find.*papers?.*analy[sz]e.*summar[yi]ze?',
            r'research.*review.*synthesize',
            r'discover.*assess.*compare',
            r'extract.*citations?.*analy[sz]e.*network',
            r'comprehensive.*study.*multiple.*agents?',
        ]

        if any(re.search(pattern, message_lower) for pattern in complex_patterns):
            return 'dynamic'  # Dynamic workflow creation

        return None

    async def _execute_workflow_from_message(
        self, message: str, workflow_type: str, user_id: str
    ) -> str:
        """Execute workflow using smart unified engine."""
        try:
            if not self.smart_workflow_engine:
                return ' Multi-agent workflow engine not available'

            logger.info(f'Executing multi-agent workflow: {workflow_type}')

            # Single unified engine handles everything automatically
            result = await self.smart_workflow_engine.execute_workflow(
                request_text=message, user_id=user_id, workflow_type=workflow_type
            )

            if result.success:
                # Log approach used for debugging (not visible to user)
                logger.info(f'Workflow executed using {result.approach_used} approach')
                return f"""{result.final_output}

⏱ *Completed in {result.execution_time:.1f}s using {result.approach_used.replace('_', ' ')} coordination*"""
            else:
                logger.error(f'Workflow execution failed: {result.errors}')
                return result.final_output

        except Exception as e:
            logger.error(f'Workflow execution error: {e}')
            return f' Multi-agent workflow execution failed: {e!s}'

    async def list_workflows(self) -> str:
        """List available multi-agent workflows."""
        try:
            if not self.smart_workflow_engine:
                return ' Multi-agent workflow engine not available'

            workflows = self.smart_workflow_engine.list_workflows()

            if not workflows:
                return ' No multi-agent workflows available'

            response_parts = ['🔄 **Available Multi-Agent Workflows**\n']

            # Show workflows from unified engine
            for name, description in workflows.items():
                workflow_name = name.replace('_', ' ').title()
                response_parts.append(f'**{workflow_name}**: {description}')

            response_parts.extend(
                [
                    '',
                    ' **Usage Examples:**',
                    "- 'Do a literature review on quantum computing'",
                    "- 'Analyze the citation network for this paper'",
                    "- 'Validate the research methodology in this study'",
                    '',
                    '✨ **Smart Execution**: Automatically chooses between Letta-native coordination and external orchestration',
                    ' **Multi-Agent Coordination**: Specialized agents collaborate seamlessly on complex research tasks',
                ]
            )

            return '\n'.join(response_parts)

        except Exception as e:
            logger.error(f'Error listing workflows: {e}')
            return ' Error retrieving workflow list'

    async def get_workflow_status(self, _workflow_id: str) -> str:
        """Get status of a running workflow (placeholder for future implementation)."""
        return 'Workflow status tracking not yet implemented'
