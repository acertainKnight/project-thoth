"""
Main research assistant agent implementation using LangGraph.

This module provides the core agent that orchestrates all research activities
using a modern LangGraph architecture with MCP framework.
"""

# Removed legacy tool discovery imports
from typing import Any

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, create_react_agent, tools_condition
from loguru import logger

from thoth.ingestion.agent_v2.core.state import ResearchAgentState
from thoth.ingestion.agent_v2.core.token_tracker import TokenUsageTracker

# Legacy tool imports removed - using MCP tools exclusively
from thoth.services.service_manager import ServiceManager

# Import memory system (optional dependency)
try:
    from thoth.memory import ThothMemoryStore

    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    logger.warning('Thoth memory system not available, using basic MemorySaver')

# Import MCP components
try:
    # MCP imports for availability check only
    import thoth.mcp.base_tools
    import thoth.mcp.tools  # noqa: F401

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning('MCP tools not available, falling back to legacy tools')


class ResearchAssistant:
    """
    Modern research assistant agent using LangGraph and MCP framework.

    This agent provides a clean, modular interface for managing research activities
    including discovery sources, query management, and knowledge base exploration.
    """

    def __init__(
        self,
        service_manager: ServiceManager,
        enable_memory: bool = True,
        system_prompt: str | None = None,
        memory_store: ThothMemoryStore | None = None,
    ):
        """
        Initialize the research assistant.

        Args:
            service_manager: ServiceManager instance for accessing services
            enable_memory: Whether to enable conversation memory
            system_prompt: Custom system prompt (uses default if None)
            use_mcp_tools: Whether to use MCP tools (defaults to True if available)
            memory_store: Optional ThothMemoryStore for persistent memory
        """
        self.service_manager = service_manager
        self.enable_memory = enable_memory
        # Force MCP tools usage - no fallback to legacy tools
        if not MCP_AVAILABLE:
            raise RuntimeError(
                'MCP tools are required but not available. Install dependencies.'
            )
        self.use_mcp_tools = True
        self.memory_store = memory_store

        # Get LLM from service manager
        self.llm = self.service_manager.llm.get_client()

        # Token usage tracker
        self.usage_tracker = TokenUsageTracker()

        # Initialize tools - will be loaded asynchronously
        self.tools = []
        self.mcp_client = None
        self.tool_registry = None
        self._initialized = False

        # Legacy tool registry initialization removed - MCP tools only

        # Set up system prompt
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # Agent graph will be built after async initialization
        self.app = None
        self.llm_with_tools = None

        logger.info(
            'Research Assistant created - call async_initialize() to complete setup'
        )

    async def async_initialize(self) -> None:
        """
        Complete async initialization of the research assistant.

        This method must be called after creating the ResearchAssistant instance
        to properly load MCP tools and build the agent graph.
        """
        if self._initialized:
            return

        # Initialize MCP tools exclusively
        try:
            # Use the new MCP adapter approach
            self.tools = await self._get_mcp_tools_via_adapter()
            logger.info(
                f'MCP tools loaded successfully - {len(self.tools)} tools available'
            )
        except Exception as e:
            logger.error(f'Failed to initialize MCP tools: {e}')
            raise RuntimeError(
                f'MCP tools are required but failed to initialize: {e}'
            ) from e

        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Build the agent graph
        self.app = self._build_graph()

        self._initialized = True
        logger.info(
            f'Research Assistant fully initialized with {len(self.tools)} tools'
        )

    # Legacy tool registration removed - MCP tools only

    async def _get_mcp_tools_via_adapter(self) -> list[Any]:
        """Get MCP tools using official LangChain MCP adapter."""
        if not self.use_mcp_tools:
            return []

        try:
            from langchain_mcp_adapters.client import MultiServerMCPClient

            # Connect to local Thoth MCP server
            # Get the MCP connection details from configuration
            mcp_port = self.service_manager.config.mcp_port
            mcp_host = self.service_manager.config.mcp_host

            self.mcp_client = MultiServerMCPClient(
                {
                    'thoth': {
                        'url': f'http://{mcp_host}:{mcp_port}/mcp',
                        'transport': 'streamable_http',
                    }
                }
            )

            # Get tools directly from MCP server - no manual conversion needed
            logger.info('Connecting to local MCP server for tools...')
            tools = await self.mcp_client.get_tools()
            logger.info(f'Successfully loaded {len(tools)} tools from MCP server')
            return tools

        except ImportError:
            logger.error(
                'langchain-mcp-adapters not installed. Install with: pip install langchain-mcp-adapters'
            )
            return []
        except Exception as e:
            logger.error(f'Failed to connect to MCP server: {e}')
            raise RuntimeError(
                f'MCP connection failed and no fallback available: {e}'
            ) from e

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for the agent."""
        return """You are Thoth, an advanced research assistant specialized in academic literature management and analysis.

Your capabilities include:

1. **Discovery Management**: Create and manage sources (ArXiv, PubMed) that automatically find new papers
2. **Query Management**: Create research queries that filter articles based on your interests
3. **Knowledge Exploration**: Search, analyze, and answer questions about the research collection
4. **Paper Analysis**: Evaluate articles, find connections, and analyze research topics
5. **PDF Location**: Find open-access PDFs for articles using DOI or arXiv identifiers

Key behaviors:
- Be proactive: When users express research interests, suggest creating sources and queries
- Be comprehensive: Use multiple tools to provide complete answers
- Be analytical: Help users understand connections between papers and research trends
- Be efficient: Use tools in parallel when possible
- Be resourceful: Help users find PDFs for articles they're interested in

When users ask about their research or express interests:
1. Check existing queries and sources with list tools
2. Suggest creating new sources/queries if relevant
3. Use RAG tools to explore existing knowledge
4. Help locate PDFs for important papers
5. Provide actionable next steps

Remember: You have direct access to tools - use them immediately rather than just explaining what you would do."""

    def _get_memory_checkpointer(self) -> Any:
        """
        Get the appropriate memory checkpointer.

        Returns:
            LettaCheckpointer if Thoth memory is available and configured,
            otherwise fallback to MemorySaver.
        """
        # For now, always use MemorySaver since LettaCheckpointer doesn't
        # implement async methods
        logger.info(
            'Using basic MemorySaver (LettaCheckpointer async not implemented yet)'
        )
        return MemorySaver()

        # TODO: Re-enable when LettaCheckpointer implements aget_tuple
        # if MEMORY_AVAILABLE and self.memory_store:
        #     # Use Thoth's Letta-based checkpointer
        #     from thoth.memory import LettaCheckpointer
        #
        #     checkpointer = LettaCheckpointer(self.memory_store)
        #     logger.info('Using Letta-based persistent memory checkpointer')
        #     return checkpointer
        # elif MEMORY_AVAILABLE and not self.memory_store:
        #     # Use shared checkpointer if no specific store provided
        #     checkpointer = get_shared_checkpointer()
        #     logger.info('Using shared Letta checkpointer')
        #     return checkpointer
        # else:
        #     # Fallback to basic in-memory checkpointer
        #     logger.info('Using basic MemorySaver (no persistence)')
        #     return MemorySaver()

    def _build_graph(self) -> Any:
        """Build the LangGraph agent graph using MCP tooling."""
        memory = self._get_memory_checkpointer() if self.enable_memory else None

        try:
            # Attempt to use the modern prebuilt agent from LangGraph
            return create_react_agent(
                model=self.llm,
                tools=self.tools,
                prompt=self.system_prompt,
                state_schema=ResearchAgentState,
                checkpointer=memory,
            )
        except Exception as e:  # pragma: no cover - fallback rarely triggered
            logger.warning(f'Falling back to legacy graph: {e}')

        # Legacy graph construction for maximum compatibility
        graph = StateGraph(ResearchAgentState)
        graph.add_node('agent', self._agent_node)
        graph.add_node('tools', ToolNode(self.tools))
        graph.set_entry_point('agent')
        graph.add_conditional_edges(
            'agent',
            tools_condition,
            {
                'tools': 'tools',
                END: END,
            },
        )
        graph.add_edge('tools', 'agent')

        return graph.compile(checkpointer=memory) if memory else graph.compile()

    async def _agent_node(self, state: ResearchAgentState) -> dict[str, Any]:
        """
        Main agent node that processes messages and decides on actions.

        Args:
            state: Current agent state

        Returns:
            dict: Updated state with agent's response
        """
        # Add system message if this is the first message
        messages = list(state.messages)
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages.insert(0, SystemMessage(content=self.system_prompt))

        # Use the specified model or the default
        model_override = state.model_override
        if model_override:
            llm_with_tools = self.llm.bind_tools(self.tools, model=model_override)
        else:
            llm_with_tools = self.llm_with_tools

        # Get response from LLM with tools (use async invocation for MCP tools)
        response = await llm_with_tools.ainvoke(messages)

        # Return the response (LangGraph will handle adding it to messages)
        return {'messages': [response]}

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        user_id: str | None = None,
        context: dict[str, Any] | None = None,
        model_override: str | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message and return the agent's response.

        Args:
            message: User's input message
            session_id: Optional session ID for memory persistence
            user_id: Identifier for the current user
            context: Optional context to pass to the agent
            model_override: Optional model to use for this turn

        Returns:
            dict: Response containing agent's message and any tool results
        """
        # Prepare initial state
        initial_state = ResearchAgentState(
            messages=[HumanMessage(content=message)],
            session_id=session_id,
            user_context=context or {},
            model_override=model_override,
        )

        # Configure thread ID for memory
        config = {}
        if self.enable_memory and session_id:
            config['configurable'] = {'thread_id': session_id}

        try:
            # Run the agent (use async invocation for MCP tools)
            result = await self.app.ainvoke(initial_state, config)

            # Extract the final AI message
            final_message = None
            for msg in reversed(result['messages']):
                if isinstance(msg, AIMessage):
                    final_message = msg
                    break

            if not final_message:
                return {
                    'response': 'I encountered an error processing your request.',
                    'error': 'No AI response generated',
                }

            # Format response
            response = {
                'response': final_message.content,
                'tool_calls': [],
            }

            # Track token usage if available
            if (
                hasattr(final_message, 'usage_metadata')
                and final_message.usage_metadata
            ):
                response['usage'] = final_message.usage_metadata
                if user_id:
                    self.usage_tracker.add_usage(user_id, final_message.usage_metadata)

            # Add tool call information if any
            if hasattr(final_message, 'tool_calls') and final_message.tool_calls:
                for tool_call in final_message.tool_calls:
                    response['tool_calls'].append(
                        {
                            'tool': tool_call['name'],
                            'args': tool_call['args'],
                        }
                    )

            return response

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            logger.error(f'Error in agent chat: {e}')
            logger.error(f'Traceback:\n{error_details}')
            return {
                'response': f'I encountered an error: {e!s}',
                'error': str(e),
                'traceback': error_details,
            }

    async def chat_messages(
        self,
        messages: list[dict[str, Any]],
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process a list of chat messages following MCP format."""

        lc_messages = []
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content', '')
            if role == 'user':
                lc_messages.append(HumanMessage(content=content))
            elif role == 'assistant':
                lc_messages.append(AIMessage(content=content))
            elif role == 'tool':
                lc_messages.append(
                    ToolMessage(
                        content=content,
                        tool_call_id=msg.get('tool_call_id', ''),
                    )
                )
            elif role == 'system':
                lc_messages.append(SystemMessage(content=content))

        initial_state = ResearchAgentState(
            messages=lc_messages,
            session_id=session_id,
            user_context=context or {},
        )

        config = {}
        if self.enable_memory and session_id:
            config['configurable'] = {'thread_id': session_id}

        try:
            # Use async invocation for MCP tools
            result = await self.app.ainvoke(initial_state, config)
            final_message = None
            for m in reversed(result['messages']):
                if isinstance(m, AIMessage):
                    final_message = m
                    break

            if not final_message:
                return {
                    'response': 'I encountered an error processing your request.',
                    'error': 'No AI response generated',
                }

            response = {
                'response': final_message.content,
                'tool_calls': [],
            }

            if hasattr(final_message, 'tool_calls') and final_message.tool_calls:
                for tc in final_message.tool_calls:
                    response['tool_calls'].append(
                        {
                            'tool': tc['name'],
                            'args': tc['args'],
                        }
                    )

            return response

        except Exception as e:  # pragma: no cover - runtime failures
            logger.error(f'Error in agent chat_messages: {e}')
            return {
                'response': f'I encountered an error: {e!s}',
                'error': str(e),
            }

    def get_available_tools(self) -> list[dict[str, str]]:
        """
        Get information about all available tools.

        Returns:
            list[dict]: List of tool information with name and description
        """
        return [
            {
                'name': tool.name,
                'description': tool.description,
            }
            for tool in self.tools
        ]

    def list_tools(self) -> list[str]:
        """Return the names of all available MCP tools."""
        return [tool.name for tool in self.tools] if self.tools else []

    def reset_memory(self, session_id: str | None = None) -> None:
        """
        Reset conversation memory for a session.

        Args:
            session_id: Session ID to reset (resets all if None)
        """
        if self.enable_memory and hasattr(self.app, 'checkpointer'):
            if session_id:
                # Reset specific session
                config = {'configurable': {'thread_id': session_id}}
                self.app.checkpointer.put(config, ResearchAgentState())
            logger.info(f'Reset memory for session: {session_id}')

    def get_token_usage(self, user_id: str) -> dict[str, int]:
        """Return accumulated token usage for a user."""
        return self.usage_tracker.get_usage(user_id)


def create_research_assistant(
    service_manager: ServiceManager | None = None,
    adapter=None,
    enable_memory: bool = True,
    system_prompt: str | None = None,
    memory_store: ThothMemoryStore | None = None,
) -> ResearchAssistant:
    """
    Factory function to create a research assistant.

    Args:
        service_manager: ServiceManager instance (preferred method)
        adapter: AgentAdapter instance (legacy compatibility)
        enable_memory: Whether to enable conversation memory
        system_prompt: Custom system prompt
        memory_store: Optional ThothMemoryStore for persistent memory

    Returns:
        ResearchAssistant: Configured research assistant instance

    Note:
        Either service_manager or adapter must be provided.
        If both are provided, service_manager takes precedence.
        MCP tools are always used (no legacy tool fallback).
    """
    if service_manager is None and adapter is None:
        raise ValueError('Either service_manager or adapter must be provided')

    # Use service_manager if provided, otherwise extract from adapter
    if service_manager is None:
        service_manager = adapter.service_manager

    return ResearchAssistant(
        service_manager=service_manager,
        enable_memory=enable_memory,
        system_prompt=system_prompt,
        memory_store=memory_store,
    )


async def create_research_assistant_async(
    service_manager: ServiceManager | None = None,
    adapter=None,
    enable_memory: bool = True,
    system_prompt: str | None = None,
    use_mcp_tools: bool = True,
    memory_store: ThothMemoryStore | None = None,
) -> ResearchAssistant:
    """
    Async factory function to create and fully initialize a research assistant.

    This function creates a ResearchAssistant and completes its async initialization,
    including loading MCP tools and building the agent graph.

    Args:
        service_manager: ServiceManager instance (preferred method)
        adapter: AgentAdapter instance (legacy compatibility)
        enable_memory: Whether to enable conversation memory
        system_prompt: Custom system prompt
        use_mcp_tools: Whether to use MCP tools (defaults to True)
        memory_store: Optional ThothMemoryStore for persistent memory

    Returns:
        ResearchAssistant: Fully initialized research assistant instance

    Note:
        Either service_manager or adapter must be provided.
        If both are provided, service_manager takes precedence.
    """
    # Create the assistant using the sync factory
    assistant = create_research_assistant(
        service_manager=service_manager,
        adapter=adapter,
        enable_memory=enable_memory,
        system_prompt=system_prompt,
        use_mcp_tools=use_mcp_tools,
        memory_store=memory_store,
    )

    # Complete async initialization
    await assistant.async_initialize()

    return assistant
