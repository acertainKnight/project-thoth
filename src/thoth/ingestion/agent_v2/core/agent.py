"""
Main research assistant agent implementation using LangGraph.

This module provides the core agent that orchestrates all research activities
using a modern LangGraph architecture with MCP framework.
"""

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from loguru import logger
from importlib import import_module
from pkgutil import iter_modules

from thoth.ingestion.agent_v2.tools import __path__ as _tools_path
from thoth.ingestion.agent_v2.tools.decorators import get_registered_tools

from thoth.ingestion.agent_v2.core.state import ResearchAgentState
from thoth.ingestion.agent_v2.core.token_tracker import TokenUsageTracker
from thoth.ingestion.agent_v2.tools.base_tool import ToolRegistry
from thoth.services.service_manager import ServiceManager


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
    ):
        """
        Initialize the research assistant.

        Args:
            service_manager: ServiceManager instance for accessing services
            enable_memory: Whether to enable conversation memory
            system_prompt: Custom system prompt (uses default if None)
        """
        self.service_manager = service_manager
        self.enable_memory = enable_memory

        # Get LLM from service manager
        self.llm = self.service_manager.llm.get_client()

        # Token usage tracker
        self.usage_tracker = TokenUsageTracker()

        # Initialize tool registry and register all tools
        self.tool_registry = ToolRegistry(service_manager=self.service_manager)
        self._register_tools()

        # Get all tool instances
        self.tools = self.tool_registry.create_all_tools()

        # Bind tools to LLM
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        # Set up system prompt
        self.system_prompt = system_prompt or self._get_default_system_prompt()

        # Build the agent graph
        self.app = self._build_graph()

        logger.info(f'Research Assistant initialized with {len(self.tools)} tools')

    def _register_tools(self) -> None:
        """Register all available tools discovered via decorators."""
        # Import all tool modules to trigger decorator registration
        for module in iter_modules(_tools_path):
            import_module(f'thoth.ingestion.agent_v2.tools.{module.name}')

        # Register each discovered tool class
        for name, cls in get_registered_tools().items():
            self.tool_registry.register(name, cls)

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

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph agent graph."""
        # Create the graph
        graph = StateGraph(ResearchAgentState)

        # Add nodes
        graph.add_node('agent', self._agent_node)
        graph.add_node('tools', ToolNode(self.tools))

        # Set entry point
        graph.set_entry_point('agent')

        # Add edges
        graph.add_conditional_edges(
            'agent',
            tools_condition,  # Built-in condition that routes to tools or END
            {
                'tools': 'tools',
                END: END,
            },
        )
        graph.add_edge('tools', 'agent')  # After tools, always go back to agent

        # Compile with memory if enabled
        if self.enable_memory:
            memory = MemorySaver()
            return graph.compile(checkpointer=memory)
        else:
            return graph.compile()

    def _agent_node(self, state: ResearchAgentState) -> dict[str, Any]:
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

        # Get response from LLM with tools
        response = llm_with_tools.invoke(messages)

        # Return the response (LangGraph will handle adding it to messages)
        return {'messages': [response]}

    def chat(
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
            # Run the agent
            result = self.app.invoke(initial_state, config)

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
            logger.error(f'Error in agent chat: {e}')
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
        """Return the names of all available tools."""

        return self.tool_registry.get_tool_names()

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
    service_manager: ServiceManager,
    enable_memory: bool = True,
    system_prompt: str | None = None,
) -> ResearchAssistant:
    """
    Factory function to create a research assistant.

    Args:
        service_manager: ServiceManager instance
        enable_memory: Whether to enable conversation memory
        system_prompt: Custom system prompt

    Returns:
        ResearchAssistant: Configured research assistant instance
    """
    return ResearchAssistant(
        service_manager=service_manager,
        enable_memory=enable_memory,
        system_prompt=system_prompt,
    )
