"""
Research Assistant Agent for Thoth.

This module provides a conversational agent that helps users create and refine
research queries for automatic article filtering and collection.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from jinja2 import Environment, FileSystemLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END, StateGraph
from loguru import logger

from thoth.utilities.config import get_config
from thoth.utilities.models import (
    AnalysisResponse,
    QueryEvaluationResponse,
    QueryRefinementSuggestion,
    ResearchAgentState,
    ResearchQuery,
)
from thoth.utilities.openrouter import OpenRouterClient


class ResearchAgentError(Exception):
    """Exception raised for errors in the research agent processing."""

    pass


class ResearchAssistantAgent:
    """
    Research Assistant Agent for Thoth using LangGraph.

    This agent helps users create, refine, and manage research queries that are used
    to automatically evaluate and filter research articles. It provides a conversational
    interface for building structured queries and evaluating articles against them.
    """

    def __init__(
        self,
        model: str | None = None,
        max_output_tokens: int | None = None,
        max_context_length: int | None = None,
        openrouter_api_key: str | None = None,
        prompts_dir: str | Path | None = None,
        queries_dir: str | Path | None = None,
        agent_storage_dir: str | Path | None = None,
        model_kwargs: dict[str, Any] | None = None,
    ):
        """
        Initialize the Research Assistant Agent.

        Args:
            model: The model to use for API calls (defaults to config).
            max_output_tokens: Maximum output tokens for the model (defaults to config).
            max_context_length: Maximum context length for the model (defaults to
                config).
            openrouter_api_key: The OpenRouter API key (optional, uses config if not
                provided).
            prompts_dir: Directory containing Jinja2 prompt templates (defaults to
                config).
            queries_dir: Directory for storing query files (defaults to config).
            agent_storage_dir: Directory for storing agent-managed articles (defaults to
                config).
            model_kwargs: Additional keyword arguments for the model.
        """
        # Load configuration
        self.config = get_config()

        # Set up directories
        self.queries_dir = Path(queries_dir or self.config.queries_dir)
        self.agent_storage_dir = Path(
            agent_storage_dir or self.config.agent_storage_dir
        )
        # Set up model configuration
        self.model = model or self.config.research_agent_llm_config.model
        self.max_output_tokens = (
            max_output_tokens or self.config.research_agent_llm_config.max_output_tokens
        )
        self.max_context_length = (
            max_context_length
            or self.config.research_agent_llm_config.max_context_length
        )
        self.model_kwargs = (
            model_kwargs
            or self.config.research_agent_llm_config.model_settings.model_dump()
        )

        self.prompts_dir = (
            Path(prompts_dir or self.config.prompts_dir) / (self.model).split('/')[0]
        )

        # Create directories if they don't exist
        self.queries_dir.mkdir(parents=True, exist_ok=True)
        self.agent_storage_dir.mkdir(parents=True, exist_ok=True)

        logger.debug(f'Research agent using model: {self.model}')
        logger.debug(f'Max output tokens: {self.max_output_tokens}')
        logger.debug(f'Max context length: {self.max_context_length}')
        logger.debug(f'Queries directory: {self.queries_dir}')
        logger.debug(f'Agent storage directory: {self.agent_storage_dir}')
        logger.debug(f'Prompts directory: {self.prompts_dir}')

        # Initialize the LLM
        self.llm = OpenRouterClient(
            api_key=openrouter_api_key or self.config.api_keys.openrouter_key,
            model=self.model,
            **self.model_kwargs,
        )

        # Create structured LLMs for different tasks
        self.evaluation_llm = self.llm.with_structured_output(
            QueryEvaluationResponse,
            include_raw=False,
            method='json_schema',
        )

        self.refinement_llm = self.llm.with_structured_output(
            QueryRefinementSuggestion,
            include_raw=False,
            method='json_schema',
        )

        # Initialize Jinja environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Load prompt templates
        self.chat_prompt = self._create_prompt_from_template('research_agent_chat.j2')
        self.evaluation_prompt = self._create_prompt_from_template(
            'evaluate_article_query.j2'
        )
        self.refinement_prompt = self._create_prompt_from_template(
            'refine_research_query.j2'
        )

        # Build processing chains
        self.chat_chain = self.chat_prompt | self.llm
        self.evaluation_chain = self.evaluation_prompt | self.evaluation_llm
        self.refinement_chain = self.refinement_prompt | self.refinement_llm

        # Build the LangGraph workflow
        self.app = self._build_graph()

        logger.info('Research Assistant Agent initialized successfully')

    def _create_prompt_from_template(self, template_name: str) -> ChatPromptTemplate:
        """
        Create a ChatPromptTemplate from a Jinja2 template file.

        Args:
            template_name: Name of the template file (e.g., "research_agent_chat.j2").

        Returns:
            ChatPromptTemplate: The prompt template for use in LangChain.

        Raises:
            FileNotFoundError: If the template file doesn't exist.
        """
        try:
            template_source, _filename, _uptodate = self.jinja_env.loader.get_source(
                self.jinja_env, template_name
            )
            return ChatPromptTemplate.from_template(
                template_source, template_format='jinja2'
            )
        except Exception as e:
            logger.error(f'Failed to load template {template_name}: {e}')
            raise FileNotFoundError(f'Template {template_name} not found') from e

    # --- Query Management Methods ---

    def _load_query(self, query_name: str) -> ResearchQuery | None:
        """Load a research query from file."""
        query_path = self.queries_dir / f'{query_name}.json'
        if not query_path.exists():
            return None

        try:
            with open(query_path, encoding='utf-8') as f:
                query_data = json.load(f)
            return ResearchQuery(**query_data)
        except Exception as e:
            logger.error(f'Failed to load query {query_name}: {e}')
            return None

    def _save_query(self, query: ResearchQuery) -> bool:
        """Save a research query to file."""
        query_path = self.queries_dir / f'{query.name}.json'
        try:
            # Update timestamps
            now = datetime.now().isoformat()
            if not query.created_at:
                query.created_at = now
            query.updated_at = now

            with open(query_path, 'w', encoding='utf-8') as f:
                json.dump(query.model_dump(), f, indent=2)
            logger.info(f'Saved query {query.name} to {query_path}')
            return True
        except Exception as e:
            logger.error(f'Failed to save query {query.name}: {e}')
            return False

    def _list_queries(self) -> list[str]:
        """List all available query names."""
        query_files = list(self.queries_dir.glob('*.json'))
        return [f.stem for f in query_files]

    def _delete_query(self, query_name: str) -> bool:
        """Delete a query file."""
        query_path = self.queries_dir / f'{query_name}.json'
        try:
            if query_path.exists():
                query_path.unlink()
                logger.info(f'Deleted query {query_name}')
                return True
            return False
        except Exception as e:
            logger.error(f'Failed to delete query {query_name}: {e}')
            return False

    # --- LangGraph Nodes ---

    def _process_user_input(self, state: ResearchAgentState) -> ResearchAgentState:
        """Process user input and determine the appropriate action."""
        logger.info('Processing user input...')
        user_message = state.get('user_message', '').lower().strip()

        # Simple intent detection based on keywords
        if any(word in user_message for word in ['create', 'new', 'make']):
            if 'query' in user_message:
                state['action'] = 'create_query'
        elif any(
            word in user_message for word in ['edit', 'modify', 'update', 'change']
        ):
            state['action'] = 'edit_query'
        elif any(word in user_message for word in ['evaluate', 'test', 'check']):
            state['action'] = 'evaluate_article'
        elif any(word in user_message for word in ['refine', 'improve', 'suggest']):
            state['action'] = 'refine_query'
        elif any(word in user_message for word in ['list', 'show', 'queries']):
            state['action'] = 'list_queries'
        elif any(word in user_message for word in ['delete', 'remove']):
            state['action'] = 'delete_query'
        elif any(word in user_message for word in ['exit', 'quit', 'bye', 'done']):
            state['action'] = 'end'
        else:
            state['action'] = 'chat'

        # Load available queries for context
        state['available_queries'] = self._list_queries()

        logger.debug(f'Determined action: {state["action"]}')
        return state

    def _handle_chat(self, state: ResearchAgentState) -> ResearchAgentState:
        """Handle general chat and provide guidance."""
        logger.info('Handling general chat...')

        try:
            response = self.chat_chain.invoke(
                {
                    'user_message': state.get('user_message'),
                    'conversation_history': state.get('conversation_history', []),
                    'current_query': state.get('current_query'),
                    'available_queries': state.get('available_queries', []),
                }
            )

            state['agent_response'] = response.content
            state['needs_user_input'] = True

        except Exception as e:
            logger.error(f'Error in chat handling: {e}')
            state['error_message'] = f'Error processing your message: {e!s}'
            state['agent_response'] = (
                'I encountered an error processing your message. Please try again.'
            )

        return state

    def _handle_create_query(self, state: ResearchAgentState) -> ResearchAgentState:
        """Handle creating a new research query."""
        logger.info('Handling query creation...')

        # For now, provide guidance on creating a query
        # In a full implementation, this would involve multiple steps of gathering
        # information
        state['agent_response'] = """
I'll help you create a new research query. To create an effective query, I need to understand:

1. **Research Question**: What specific research question or area are you interested in?
2. **Keywords**: What key terms should appear in relevant articles?
3. **Required Topics**: What topics must be present for an article to be relevant?
4. **Preferred Topics**: What topics would make an article more interesting but aren't required?
5. **Excluded Topics**: What topics should exclude an article from consideration?
6. **Methodology Preferences**: Do you prefer certain research methodologies?

Please describe your research interests, and I'll help you build a structured query.
"""
        state['needs_user_input'] = True
        return state

    def _handle_list_queries(self, state: ResearchAgentState) -> ResearchAgentState:
        """Handle listing available queries."""
        logger.info('Handling query listing...')

        queries = self._list_queries()
        if queries:
            query_list = '\n'.join(f'- {query}' for query in queries)
            state['agent_response'] = f'Available research queries:\n{query_list}'
        else:
            state['agent_response'] = (
                'No research queries found. Would you like to create one?'
            )

        state['needs_user_input'] = True
        return state

    def _handle_evaluate_article(self, state: ResearchAgentState) -> ResearchAgentState:
        """Handle evaluating an article against a query."""
        logger.info('Handling article evaluation...')

        # This would need to be implemented with actual article data
        state['agent_response'] = """
To evaluate an article against a research query, I need:

1. The name of the query to use for evaluation
2. The article data (title, abstract, content analysis)

Please specify which query you'd like to use and provide the article information.
"""
        state['needs_user_input'] = True
        return state

    def _handle_end(self, state: ResearchAgentState) -> ResearchAgentState:
        """Handle ending the conversation."""
        logger.info('Ending conversation...')
        state['agent_response'] = (
            'Thank you for using the Research Assistant! Your queries have been saved '
            'and will be used to filter new articles automatically.'
        )
        state['needs_user_input'] = False
        return state

    # --- LangGraph Conditional Edges ---

    def _decide_next_action(
        self, state: ResearchAgentState
    ) -> Literal[
        'handle_chat',
        'handle_create_query',
        'handle_list_queries',
        'handle_evaluate_article',
        'handle_end',
    ]:
        """Decide which action to take based on the determined action."""
        action = state.get('action')

        if action == 'create_query':
            return 'handle_create_query'
        elif action == 'list_queries':
            return 'handle_list_queries'
        elif action == 'evaluate_article':
            return 'handle_evaluate_article'
        elif action == 'end':
            return 'handle_end'
        else:
            return 'handle_chat'

    # --- Build the Graph ---

    def _build_graph(self) -> Runnable:
        """Build the LangGraph workflow for the research assistant."""
        workflow = StateGraph(ResearchAgentState)

        # Add nodes
        workflow.add_node('process_user_input', self._process_user_input)
        workflow.add_node('handle_chat', self._handle_chat)
        workflow.add_node('handle_create_query', self._handle_create_query)
        workflow.add_node('handle_list_queries', self._handle_list_queries)
        workflow.add_node('handle_evaluate_article', self._handle_evaluate_article)
        workflow.add_node('handle_end', self._handle_end)

        # Set entry point
        workflow.set_entry_point('process_user_input')

        # Add conditional edges from process_user_input
        workflow.add_conditional_edges(
            'process_user_input',
            self._decide_next_action,
            {
                'handle_chat': 'handle_chat',
                'handle_create_query': 'handle_create_query',
                'handle_list_queries': 'handle_list_queries',
                'handle_evaluate_article': 'handle_evaluate_article',
                'handle_end': 'handle_end',
            },
        )

        # Add edges to END (except for handle_end which continues conversation)
        workflow.add_edge('handle_chat', END)
        workflow.add_edge('handle_create_query', END)
        workflow.add_edge('handle_list_queries', END)
        workflow.add_edge('handle_evaluate_article', END)
        workflow.add_edge('handle_end', END)

        # Compile the graph
        app = workflow.compile()
        logger.info('Research Assistant workflow compiled')
        logger.debug(f'Graph structure:\n{app.get_graph().draw_ascii()}')
        return app

    # --- Public Methods ---

    def chat(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        """
        Process a user message and return the agent's response.

        Args:
            user_message: The user's input message.
            conversation_history: Previous conversation messages.
            config: Optional LangChain RunnableConfig for the graph invocation.

        Returns:
            dict: Contains the agent's response and updated state information.

        Raises:
            ResearchAgentError: If the processing fails.
        """
        logger.info(f'Processing user message: {user_message[:100]}...')

        # Construct initial state
        initial_state: ResearchAgentState = {
            'user_message': user_message,
            'agent_response': None,
            'conversation_history': conversation_history or [],
            'current_query': None,
            'query_name': None,
            'available_queries': None,
            'current_article': None,
            'evaluation_result': None,
            'action': None,
            'needs_user_input': None,
            'error_message': None,
        }

        try:
            # Invoke the graph
            final_state = self.app.invoke(initial_state, config=config)

            # Extract response information
            response = {
                'agent_response': final_state.get('agent_response'),
                'action': final_state.get('action'),
                'needs_user_input': final_state.get('needs_user_input', True),
                'error_message': final_state.get('error_message'),
                'available_queries': final_state.get('available_queries', []),
            }

            logger.info('Successfully processed user message')
            return response

        except Exception as e:
            logger.error(f'Error processing user message: {e}')
            raise ResearchAgentError(f'Failed to process message: {e!s}') from e

    def evaluate_article(
        self, article: AnalysisResponse, query_name: str
    ) -> QueryEvaluationResponse | None:
        """
        Evaluate an article against a specific research query.

        Args:
            article: The article analysis to evaluate.
            query_name: Name of the query to use for evaluation.

        Returns:
            QueryEvaluationResponse: The evaluation result, or None if query not found.

        Raises:
            ResearchAgentError: If the evaluation fails.
        """
        logger.info(f'Evaluating article against query: {query_name}')

        # Load the query
        query = self._load_query(query_name)
        if not query:
            logger.error(f'Query {query_name} not found')
            return None

        try:
            # Perform evaluation
            evaluation = self.evaluation_chain.invoke(
                {'query': query.model_dump(), 'article': article.model_dump()}
            )

            logger.info(
                f'Article evaluation completed: score={evaluation.relevance_score}, '
                f'recommendation={evaluation.recommendation}'
            )
            return evaluation

        except Exception as e:
            logger.error(f'Error evaluating article: {e}')
            raise ResearchAgentError(f'Failed to evaluate article: {e!s}') from e

    def create_query(self, query: ResearchQuery) -> bool:
        """
        Create and save a new research query.

        Args:
            query: The research query to create.

        Returns:
            bool: True if successful, False otherwise.
        """
        logger.info(f'Creating new query: {query.name}')
        return self._save_query(query)

    def get_query(self, query_name: str) -> ResearchQuery | None:
        """
        Get a research query by name.

        Args:
            query_name: Name of the query to retrieve.

        Returns:
            ResearchQuery: The query if found, None otherwise.
        """
        return self._load_query(query_name)

    def list_queries(self) -> list[str]:
        """
        List all available research query names.

        Returns:
            list[str]: List of query names.
        """
        return self._list_queries()

    def delete_query(self, query_name: str) -> bool:
        """
        Delete a research query.

        Args:
            query_name: Name of the query to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        return self._delete_query(query_name)
