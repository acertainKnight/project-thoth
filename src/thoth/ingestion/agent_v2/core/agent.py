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

from thoth.ingestion.agent_v2.core.state import ResearchAgentState
from thoth.ingestion.agent_v2.tools.analysis_tools import (
    AnalyzeTopicTool,
    EvaluateArticleTool,
    FindRelatedTool,
)
from thoth.ingestion.agent_v2.tools.base_tool import ToolRegistry
from thoth.ingestion.agent_v2.tools.discovery_tools import (
    CreateArxivSourceTool,
    CreatePubmedSourceTool,
    DeleteDiscoverySourceTool,
    ListDiscoverySourcesTool,
    RunDiscoveryTool,
)
from thoth.ingestion.agent_v2.tools.query_tools import (
    CreateQueryTool,
    DeleteQueryTool,
    EditQueryTool,
    GetQueryTool,
    ListQueriesTool,
)
from thoth.ingestion.agent_v2.tools.rag_tools import (
    AskKnowledgeTool,
    ExplainConnectionsTool,
    GetRAGStatsTool,
    IndexKnowledgeTool,
    SearchKnowledgeTool,
)


class ResearchAssistant:
    """
    Modern research assistant agent using LangGraph and MCP framework.

    This agent provides a clean, modular interface for managing research activities
    including discovery sources, query management, and knowledge base exploration.
    """

    def __init__(
        self,
        llm,
        pipeline,
        enable_memory: bool = True,
        system_prompt: str | None = None,
    ):
        """
        Initialize the research assistant.

        Args:
            llm: The language model to use for reasoning
            pipeline: ThothPipeline instance for accessing core functionality
            enable_memory: Whether to enable conversation memory
            system_prompt: Custom system prompt (uses default if None)
        """
        self.llm = llm
        self.pipeline = pipeline
        self.enable_memory = enable_memory

        # Initialize tool registry and register all tools
        self.tool_registry = ToolRegistry(pipeline=pipeline)
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
        """Register all available tools with the registry."""
        # Query management tools
        self.tool_registry.register('list_queries', ListQueriesTool)
        self.tool_registry.register('create_query', CreateQueryTool)
        self.tool_registry.register('get_query', GetQueryTool)
        self.tool_registry.register('edit_query', EditQueryTool)
        self.tool_registry.register('delete_query', DeleteQueryTool)

        # Discovery tools
        self.tool_registry.register('list_discovery_sources', ListDiscoverySourcesTool)
        self.tool_registry.register('create_arxiv_source', CreateArxivSourceTool)
        self.tool_registry.register('create_pubmed_source', CreatePubmedSourceTool)
        self.tool_registry.register('run_discovery', RunDiscoveryTool)
        self.tool_registry.register(
            'delete_discovery_source', DeleteDiscoverySourceTool
        )

        # RAG tools
        self.tool_registry.register('search_knowledge', SearchKnowledgeTool)
        self.tool_registry.register('ask_knowledge', AskKnowledgeTool)
        self.tool_registry.register('index_knowledge', IndexKnowledgeTool)
        self.tool_registry.register('explain_connections', ExplainConnectionsTool)
        self.tool_registry.register('rag_stats', GetRAGStatsTool)

        # Analysis tools
        self.tool_registry.register('evaluate_article', EvaluateArticleTool)
        self.tool_registry.register('analyze_topic', AnalyzeTopicTool)
        self.tool_registry.register('find_related', FindRelatedTool)

    def _get_default_system_prompt(self) -> str:
        """Get the default system prompt for the agent."""
        return """You are Thoth, an advanced research assistant specialized in academic literature management and analysis.

Your capabilities include:

1. **Discovery Management**: Create and manage sources (ArXiv, PubMed) that automatically find new papers
2. **Query Management**: Create research queries that filter articles based on your interests
3. **Knowledge Exploration**: Search, analyze, and answer questions about the research collection
4. **Paper Analysis**: Evaluate articles, find connections, and analyze research topics

Key behaviors:
- Be proactive: When users express research interests, suggest creating sources and queries
- Be comprehensive: Use multiple tools to provide complete answers
- Be analytical: Help users understand connections between papers and research trends
- Be efficient: Use tools in parallel when possible

When users ask about their research or express interests:
1. Check existing queries and sources with list tools
2. Suggest creating new sources/queries if relevant
3. Use RAG tools to explore existing knowledge
4. Provide actionable next steps

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

        # Get response from LLM with tools
        response = self.llm_with_tools.invoke(messages)

        # Return the response (LangGraph will handle adding it to messages)
        return {'messages': [response]}

    def chat(
        self,
        message: str,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message and return the agent's response.

        Args:
            message: User's input message
            session_id: Optional session ID for memory persistence
            context: Optional context to pass to the agent

        Returns:
            dict: Response containing agent's message and any tool results
        """
        # Prepare initial state
        initial_state = ResearchAgentState(
            messages=[HumanMessage(content=message)],
            session_id=session_id,
            user_context=context or {},
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


def create_research_assistant(
    llm,
    pipeline,
    enable_memory: bool = True,
    system_prompt: str | None = None,
) -> ResearchAssistant:
    """
    Factory function to create a research assistant.

    Args:
        llm: Language model instance
        pipeline: ThothPipeline instance
        enable_memory: Whether to enable conversation memory
        system_prompt: Custom system prompt

    Returns:
        ResearchAssistant: Configured research assistant instance
    """
    return ResearchAssistant(
        llm=llm,
        pipeline=pipeline,
        enable_memory=enable_memory,
        system_prompt=system_prompt,
    )
