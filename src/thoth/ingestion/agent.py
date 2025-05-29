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
        *,
        use_tool_agent: bool = True,
        enable_persistent_memory: bool = False,
        memory_file: str | Path | None = None,
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
            use_tool_agent: Whether to use the tool-based agent (defaults to True).
            enable_persistent_memory: Whether to enable persistent memory
                (defaults to False).
            memory_file: Path to the file for persistent memory (optional).
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

        self.prompts_dir = Path(prompts_dir or self.config.prompts_dir) / 'agent'

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

        # Initialize Discovery Manager
        # Lazy loaded to avoid circular import
        self._discovery_manager = None

        # Initialize persistent memory if enabled
        self.enable_persistent_memory = enable_persistent_memory
        self.memory_file = Path(
            memory_file or (self.agent_storage_dir / 'conversation_memory.json')
        )
        self._persistent_conversation_history: list[dict[str, str]] = []

        if self.enable_persistent_memory:
            self._load_conversation_memory()
            logger.info(f'Persistent memory enabled, using: {self.memory_file}')

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

        # ------------------------------------------------------------------
        #  Tool-calling agent (Model Context Protocol)
        # ------------------------------------------------------------------
        # Opt-in to the new LangChain "model context" approach where the LLM
        # decides which tools to invoke.  This provides far greater
        # flexibility compared to the legacy keyword-parsing flow above and
        # makes it trivial to add new capabilities - simply register a new
        # Tool instance.

        self.use_tool_agent = use_tool_agent
        self.agent_executor = None
        self.use_modern_agent = (
            False  # Will be set to True if modern LangGraph agent initializes
        )
        self.modern_agent = None
        self._current_conversation_context = ''  # Initialize conversation context

        if self.use_tool_agent:
            try:
                self._init_tool_agent()
                logger.info('Tool-calling agent initialised successfully')

            except Exception as e:
                # If tool agent initialisation fails fall back to legacy flow
                logger.warning(
                    'Failed to initialise tool-calling agent - falling back to '
                    f'legacy mode: {e}',
                )
                self.use_tool_agent = False

        logger.info('Research Assistant Agent initialized successfully')

    @property
    def discovery_manager(self):
        """Lazy-loaded discovery manager to avoid circular imports."""
        if self._discovery_manager is None:
            try:
                from thoth.discovery import DiscoveryManager

                # Always point to the canonical discovery_sources_dir defined in
                # the global configuration so the agent sees the same sources
                # as the CLI and scheduler.
                self._discovery_manager = DiscoveryManager(
                    sources_config_dir=self.config.discovery_sources_dir,
                )
            except ImportError as e:
                logger.warning(f'Discovery manager not available: {e}')
                self._discovery_manager = None
        return self._discovery_manager

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
            logger.error(
                f'Failed to load template {template_name} from {self.prompts_dir}: {e}'
            )
            raise FileNotFoundError(
                f'Template {template_name} not found in {self.prompts_dir}'
            ) from e

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

    # --- Discovery Source Management Methods ---

    def _list_discovery_sources(self) -> list[str]:
        """List all available discovery source names."""
        try:
            sources = (
                self.discovery_manager.list_sources() if self.discovery_manager else []
            )
            return [source.name for source in sources]
        except Exception as e:
            logger.error(f'Failed to list discovery sources: {e}')
            return []

    def _get_discovery_source(self, source_name: str):
        """Get a discovery source by name."""
        try:
            return (
                self.discovery_manager.get_source(source_name)
                if self.discovery_manager
                else None
            )
        except Exception as e:
            logger.error(f'Failed to get discovery source {source_name}: {e}')
            return None

    def _create_discovery_source(self, source_config: dict[str, Any]) -> bool:
        """Create a new discovery source."""
        try:
            from thoth.utilities.models import DiscoverySource

            source = DiscoverySource(**source_config)
            self.discovery_manager.create_source(source)
            logger.info(f'Created discovery source: {source.name}')
            return True
        except Exception as e:
            logger.error(f'Failed to create discovery source: {e}')
            return False

    def _update_discovery_source(self, source) -> bool:
        """Update an existing discovery source."""
        try:
            self.discovery_manager.update_source(source)
            logger.info(f'Updated discovery source: {source.name}')
            return True
        except Exception as e:
            logger.error(f'Failed to update discovery source: {e}')
            return False

    def _delete_discovery_source(self, source_name: str) -> bool:
        """Delete a discovery source."""
        try:
            self.discovery_manager.delete_source(source_name)
            logger.info(f'Deleted discovery source: {source_name}')
            return True
        except Exception as e:
            logger.error(f'Failed to delete discovery source {source_name}: {e}')
            return False

    def _run_discovery(
        self, source_name: str | None = None, max_articles: int | None = None
    ) -> dict[str, Any]:
        """Run discovery for sources."""
        try:
            result = self.discovery_manager.run_discovery(
                source_name=source_name, max_articles=max_articles
            )
            return {
                'success': True,
                'articles_found': result.articles_found,
                'articles_filtered': result.articles_filtered,
                'articles_downloaded': result.articles_downloaded,
                'execution_time': result.execution_time_seconds,
                'errors': result.errors,
            }
        except Exception as e:
            logger.error(f'Failed to run discovery: {e}')
            return {'success': False, 'error': str(e)}

    def _parse_and_create_source(self, user_message: str) -> dict[str, Any]:
        """Parse user message and attempt to create a discovery source."""
        import re

        user_message = user_message.lower()

        # Try to extract source name
        name_patterns = [
            r"called?\s+['\"]([^'\"]+)['\"]",
            r"named?\s+['\"]([^'\"]+)['\"]",
            r"call\s+it\s+['\"]([^'\"]+)['\"]",
        ]

        source_name = None
        for pattern in name_patterns:
            match = re.search(pattern, user_message)
            if match:
                source_name = match.group(1)
                break

        if not source_name:
            return {
                'success': False,
                'error': 'Please specify a name for the source in quotes, e.g., "ml_papers"',
            }

        # Determine source type and create config
        if 'arxiv' in user_message:
            return self._create_arxiv_source(user_message, source_name)
        elif 'pubmed' in user_message:
            return self._create_pubmed_source(user_message, source_name)
        else:
            return {
                'success': False,
                'error': 'Please specify source type (ArXiv or PubMed)',
            }

    def _create_arxiv_source(
        self, user_message: str, source_name: str
    ) -> dict[str, Any]:
        """Create an ArXiv discovery source from user input."""
        import re

        # Extract categories
        categories = []
        category_patterns = [
            r'cs\.lg',
            r'cs\.ai',
            r'cs\.cl',
            r'cs\.cv',
            r'cs\.ne',
            r'cs\.ro',
            r'stat\.ml',
            r'math\.st',
            r'physics\.data-an',
        ]

        for pattern in category_patterns:
            if re.search(pattern, user_message):
                categories.append(pattern.replace(r'\.', '.'))

        if not categories:
            # Default categories based on keywords
            if any(
                word in user_message for word in ['machine learning', 'ml', 'neural']
            ):
                categories = ['cs.LG', 'cs.AI']
            elif any(word in user_message for word in ['nlp', 'language', 'text']):
                categories = ['cs.CL', 'cs.AI']
            elif any(
                word in user_message for word in ['vision', 'image', 'computer vision']
            ):
                categories = ['cs.CV', 'cs.AI']
            else:
                categories = ['cs.AI']  # Default

        # Extract keywords
        keywords = []
        keyword_patterns = [
            r'keywords?\s+([^.]+)',
            r'searching?\s+for\s+([^.]+)',
            r'about\s+([^.]+)',
        ]

        for pattern in keyword_patterns:
            match = re.search(pattern, user_message)
            if match:
                keyword_text = match.group(1)
                # Split on common separators
                keywords.extend(
                    [
                        k.strip().strip('"\'')
                        for k in re.split(r'[,;]|\s+and\s+', keyword_text)
                    ]
                )
                break

        if not keywords:
            # Extract common ML/AI terms
            common_terms = [
                'machine learning',
                'deep learning',
                'neural networks',
                'transformers',
                'artificial intelligence',
                'computer vision',
                'natural language processing',
            ]
            for term in common_terms:
                if term in user_message:
                    keywords.append(term)

        if not keywords:
            keywords = ['artificial intelligence']  # Default

        # Create source configuration
        source_config = {
            'name': source_name,
            'source_type': 'api',
            'description': f'ArXiv source for {", ".join(categories)} papers',
            'is_active': True,
            'api_config': {
                'source': 'arxiv',
                'categories': categories,
                'keywords': keywords,
                'sort_by': 'lastUpdatedDate',
                'sort_order': 'descending',
            },
            'schedule_config': {
                'interval_minutes': 120,
                'max_articles_per_run': 10,
                'enabled': True,
            },
            'query_filters': [],
        }

        try:
            success = self._create_discovery_source(source_config)
            if success:
                return {
                    'success': True,
                    'source_name': source_name,
                    'categories': categories,
                    'keywords': keywords,
                }
            else:
                return {'success': False, 'error': 'Failed to create source'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _create_pubmed_source(
        self, user_message: str, source_name: str
    ) -> dict[str, Any]:
        """Create a PubMed discovery source from user input."""
        import re

        # Extract search terms
        keywords = []
        keyword_patterns = [
            r'searching?\s+for\s+([^.]+)',
            r'about\s+([^.]+)',
            r'terms?\s+([^.]+)',
        ]

        for pattern in keyword_patterns:
            match = re.search(pattern, user_message)
            if match:
                keyword_text = match.group(1)
                keywords.extend(
                    [
                        k.strip().strip('"\'')
                        for k in re.split(r'[,;]|\s+and\s+', keyword_text)
                    ]
                )
                break

        if not keywords:
            # Extract common medical/bio terms
            bio_terms = [
                'neuroscience',
                'brain',
                'neural networks',
                'genetics',
                'cancer',
                'medicine',
            ]
            for term in bio_terms:
                if term in user_message:
                    keywords.append(term)

        if not keywords:
            keywords = ['biomedical research']  # Default

        # Create source configuration
        source_config = {
            'name': source_name,
            'source_type': 'api',
            'description': f'PubMed source for {", ".join(keywords)} research',
            'is_active': True,
            'api_config': {
                'source': 'pubmed',
                'keywords': keywords,
                'sort_by': 'date',
                'sort_order': 'descending',
            },
            'schedule_config': {
                'interval_minutes': 240,
                'max_articles_per_run': 5,
                'enabled': True,
            },
            'query_filters': [],
        }

        try:
            success = self._create_discovery_source(source_config)
            if success:
                return {
                    'success': True,
                    'source_name': source_name,
                    'keywords': keywords,
                }
            else:
                return {'success': False, 'error': 'Failed to create source'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    # --- LangGraph Nodes ---

    def _process_user_input(self, state: ResearchAgentState) -> ResearchAgentState:
        """Process user input and determine the appropriate action."""
        logger.info('Processing user input...')
        user_message = state.get('user_message', '').lower().strip()

        # Simple intent detection based on keywords
        if user_message == 'help' or user_message == '?':
            state['action'] = 'help'
        elif any(word in user_message for word in ['create', 'new', 'make']):
            if 'query' in user_message:
                state['action'] = 'create_query'
            elif any(
                word in user_message
                for word in ['source', 'discovery', 'scraper', 'api']
            ):
                state['action'] = 'create_discovery_source'
            else:
                state['action'] = 'create_query'  # Default to query creation
        elif any(
            word in user_message for word in ['edit', 'modify', 'update', 'change']
        ):
            if any(word in user_message for word in ['source', 'discovery', 'scraper']):
                state['action'] = 'edit_discovery_source'
            else:
                state['action'] = 'edit_query'
        elif any(word in user_message for word in ['evaluate', 'test', 'check']):
            state['action'] = 'evaluate_article'
        elif any(word in user_message for word in ['refine', 'improve', 'suggest']):
            state['action'] = 'refine_query'
        elif any(word in user_message for word in ['list', 'show']):
            if any(word in user_message for word in ['source', 'discovery', 'scraper']):
                state['action'] = 'list_discovery_sources'
            elif 'queries' in user_message or 'query' in user_message:
                state['action'] = 'list_queries'
            else:
                state['action'] = 'list_queries'  # Default to queries
        elif any(word in user_message for word in ['delete', 'remove']):
            if any(word in user_message for word in ['source', 'discovery', 'scraper']):
                state['action'] = 'delete_discovery_source'
            else:
                state['action'] = 'delete_query'
        elif any(word in user_message for word in ['run', 'start', 'execute']):
            if any(word in user_message for word in ['discovery', 'scraper', 'source']):
                state['action'] = 'run_discovery'
            else:
                state['action'] = 'chat'
        elif any(word in user_message for word in ['exit', 'quit', 'bye', 'done']):
            state['action'] = 'end'
        else:
            state['action'] = 'chat'

        # Load available queries and discovery sources for context
        state['available_queries'] = self._list_queries()
        state['available_discovery_sources'] = self._list_discovery_sources()

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
                    'available_discovery_sources': state.get(
                        'available_discovery_sources', []
                    ),
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

    def _handle_help(self, state: ResearchAgentState) -> ResearchAgentState:
        """Handle help command and show all available capabilities."""
        logger.info('Handling help request...')

        state['agent_response'] = """
🤖 **Enhanced Thoth Research Assistant - Full Capabilities**

I'm an AI assistant that helps you manage both research queries AND discovery sources for automatic article collection and filtering.

**🔍 Discovery Source Management:**
• `list discovery sources` - Show all configured discovery sources
• `create an arxiv source called "ml_papers" for machine learning` - Create ArXiv source
• `create a pubmed source called "bio_research" searching for neuroscience` - Create PubMed source
• `run discovery for arxiv_test` - Run discovery for a specific source
• `run discovery with max 5 articles` - Run all active sources with article limit
• `edit arxiv_test source` - Modify an existing source
• `delete old_source` - Remove a discovery source

**📝 Research Query Management:**
• `create query` - Create a new research query to filter articles
• `list queries` - Show all existing research queries
• `edit query_name` - Modify an existing query
• `delete query_name` - Remove a research query
• `show_queries_location` - Show where queries are stored (debugging)
• `evaluate article` - Test how well an article matches your queries

**🎯 How It Works:**
1. **Discovery Sources** automatically find new research articles from:
   - ArXiv API (computer science, physics, math papers)
   - PubMed API (biomedical research)
   - Web scrapers (journal websites)

2. **Research Queries** define what you're interested in:
   - Keywords, required/preferred/excluded topics
   - Your queries automatically filter discovered articles
   - Only relevant articles are downloaded and processed

**💡 Examples:**
• "Create an arxiv source called 'ai_research' for artificial intelligence"
• "List my discovery sources"
• "Run discovery for ai_research"
• "Create a query for transformer architecture papers"

**🚀 Quick Start:**
1. Create a discovery source: `create an arxiv source`
2. Create research queries: `create query`
3. Run discovery: `run discovery`

Type any command or describe what you want to do!
"""
        state['needs_user_input'] = True
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

    def _handle_create_discovery_source(
        self, state: ResearchAgentState
    ) -> ResearchAgentState:
        """Handle creating a new discovery source."""
        logger.info('Handling discovery source creation...')

        user_message = state.get('user_message', '').lower()

        # First, try to parse and create if user provided enough info
        if any(word in user_message for word in ['called', 'named', 'call it']) and (
            '"' in user_message or "'" in user_message
        ):
            try:
                result = self._parse_and_create_source(user_message)
                if result['success']:
                    if 'arxiv' in user_message:
                        state['agent_response'] = f"""
✅ **ArXiv Discovery Source Created Successfully!**

**Source Details:**
- Name: `{result['source_name']}`
- Type: ArXiv API
- Categories: {', '.join(result['categories'])}
- Keywords: {', '.join(result['keywords'])}
- Schedule: Every 2 hours, max 10 articles

🚀 **Ready to use!** You can now:
- Run it: "run discovery for {result['source_name']}"
- View it: "list discovery sources"
- Edit it: "edit {result['source_name']}"
"""
                    else:  # PubMed
                        state['agent_response'] = f"""
✅ **PubMed Discovery Source Created Successfully!**

**Source Details:**
- Name: `{result['source_name']}`
- Type: PubMed API
- Keywords: {', '.join(result['keywords'])}
- Schedule: Every 4 hours, max 5 articles

🚀 **Ready to use!** You can now:
- Run it: "run discovery for {result['source_name']}"
- View it: "list discovery sources"
- Edit it: "edit {result['source_name']}"
"""
                    state['needs_user_input'] = True
                    return state
                else:
                    state['agent_response'] = (
                        f'❌ **Creation failed:** {result["error"]}\n\n'
                    )
                    # Fall through to guidance
            except Exception as e:
                logger.error(f'Error creating source: {e}')
                state['agent_response'] = f'❌ **Error creating source:** {e}\n\n'
                # Fall through to guidance

        # Provide guidance based on what user mentioned
        if 'arxiv' in user_message:
            state['agent_response'] = """
🔬 **Creating an ArXiv Discovery Source**

I can help you create an ArXiv source! Here's what I need:

**Required Information:**
1. **Name**: What should we call this source? (e.g., "ml_papers", "ai_research")
2. **Categories**: Which ArXiv categories? (e.g., cs.LG, cs.AI, cs.CL)
3. **Keywords**: What terms to search for? (e.g., "machine learning", "neural networks")

**Example:** "Create an ArXiv source called 'ml_papers' for categories cs.LG and cs.AI with keywords machine learning and transformers"

Please provide these details and I'll create the source for you!
"""
        elif 'pubmed' in user_message:
            state['agent_response'] = """
🧬 **Creating a PubMed Discovery Source**

I can help you create a PubMed source! Here's what I need:

**Required Information:**
1. **Name**: What should we call this source? (e.g., "neuroscience_papers")
2. **Search Terms**: What medical/biological terms to search for?
3. **Filters**: Any specific filters (publication date, study types, etc.)?

**Example:** "Create a PubMed source called 'neuroscience_papers' searching for 'neural networks' and 'brain imaging'"

Please provide these details and I'll create the source for you!
"""
        elif any(word in user_message for word in ['scraper', 'website', 'journal']):
            state['agent_response'] = """
🕷️ **Creating a Web Scraper Discovery Source**

I can help you create a web scraper! Here's what I need:

**Required Information:**
1. **Name**: What should we call this source? (e.g., "nature_ml")
2. **Website URL**: Which website to scrape? (e.g., "https://www.nature.com/subjects/machine-learning")
3. **Target Elements**: What parts of the page contain articles?

**Note:** Web scrapers require technical configuration. For now, I recommend using the CLI command:
`python -m thoth discovery create --name "your_name" --type "scraper" --description "Your description"`

Or try creating an API source first with "Create an ArXiv source" or "Create a PubMed source"
"""
        else:
            state['agent_response'] = """
🎯 **Create a Discovery Source**

I can help you create sources to automatically find research articles!

**Available Types:**

🔬 **ArXiv Sources** - Academic papers from arXiv.org
- Say: "Create an ArXiv source for machine learning"
- Categories: cs.LG, cs.AI, cs.CL, physics, math, etc.

🧬 **PubMed Sources** - Medical/biological research papers
- Say: "Create a PubMed source for neuroscience"
- Search medical databases and journals

🕷️ **Web Scrapers** - Extract from journal websites
- Say: "Create a scraper for Nature journal"
- Requires technical configuration

**What type would you like to create?**
"""

        state['needs_user_input'] = True
        return state

    def _handle_list_discovery_sources(
        self, state: ResearchAgentState
    ) -> ResearchAgentState:
        """Handle listing discovery sources."""
        logger.info('Handling discovery source listing...')

        try:
            if not self.discovery_manager:
                state['agent_response'] = (
                    '❌ Discovery manager not available. Please check your installation.'
                )
                state['needs_user_input'] = True
                return state

            sources = self.discovery_manager.list_sources()
            if sources:
                source_list = ['**Discovery Sources:**\n']
                for source in sources:
                    status = '🟢 Active' if source.is_active else '🔴 Inactive'
                    source_list.append(
                        f'**{source.name}** ({source.source_type}) - {status}'
                    )
                    source_list.append(f'  Description: {source.description}')
                    if source.last_run:
                        source_list.append(f'  Last run: {source.last_run}')
                    if source.schedule_config:
                        source_list.append(
                            f'  Schedule: Every {source.schedule_config.interval_minutes} minutes'
                        )
                        source_list.append(
                            f'  Max articles: {source.schedule_config.max_articles_per_run}'
                        )
                    source_list.append('')

                state['agent_response'] = '\n'.join(source_list)
                state['agent_response'] += '\n💡 **What you can do:**'
                state['agent_response'] += (
                    "\n- 'run discovery for [source_name]' - Run a specific source"
                )
                state['agent_response'] += "\n- 'edit [source_name]' - Modify a source"
                state['agent_response'] += (
                    "\n- 'delete [source_name]' - Remove a source"
                )
                state['agent_response'] += (
                    "\n- 'create discovery source' - Add a new source"
                )
            else:
                state['agent_response'] = (
                    '📭 No discovery sources found.\n\n'
                    '💡 **Get started:** Say "create discovery source" to add your first source!'
                )
        except Exception as e:
            logger.error(f'Error listing discovery sources: {e}')
            state['agent_response'] = f'❌ Error listing discovery sources: {e}'

        state['needs_user_input'] = True
        return state

    def _handle_edit_discovery_source(
        self, state: ResearchAgentState
    ) -> ResearchAgentState:
        """Handle editing a discovery source."""
        logger.info('Handling discovery source editing...')

        sources = self._list_discovery_sources()
        if sources:
            source_list = '\\n'.join(f'- {source}' for source in sources)
            state['agent_response'] = f"""
I can help you edit an existing discovery source.

**Available sources:**
{source_list}

**What you can edit:**
- Description
- Active/inactive status
- API configuration (keywords, categories)
- Scraper configuration (selectors, URLs)
- Schedule settings

Please specify which source you'd like to edit and what changes you want to make.

**Example:** "Edit the arxiv_test source to add 'transformers' keyword"
"""
        else:
            state['agent_response'] = (
                'No discovery sources found to edit. Would you like to create one?'
            )

        state['needs_user_input'] = True
        return state

    def _handle_delete_discovery_source(
        self, state: ResearchAgentState
    ) -> ResearchAgentState:
        """Handle deleting a discovery source."""
        logger.info('Handling discovery source deletion...')

        sources = self._list_discovery_sources()
        if sources:
            source_list = '\\n'.join(f'- {source}' for source in sources)
            state['agent_response'] = f"""
I can help you delete a discovery source.

**Available sources:**
{source_list}

⚠️ **Warning:** Deleting a source will permanently remove its configuration. This cannot be undone.

Please specify which source you'd like to delete.

**Example:** "Delete the old_arxiv_source"
"""
        else:
            state['agent_response'] = 'No discovery sources found to delete.'

        state['needs_user_input'] = True
        return state

    def _handle_run_discovery(self, state: ResearchAgentState) -> ResearchAgentState:
        """Handle running discovery."""
        logger.info('Handling discovery run...')

        try:
            if not self.discovery_manager:
                state['agent_response'] = (
                    '❌ Discovery manager not available. Please check your installation.'
                )
                state['needs_user_input'] = True
                return state

            user_message = state.get('user_message', '').lower()

            # Extract source name if specified
            source_name = None
            max_articles = None

            # Parse user input for specific source
            sources = self._list_discovery_sources()
            for source in sources:
                if source.lower() in user_message:
                    source_name = source
                    break

            # Parse max articles if specified
            import re

            max_match = re.search(r'(?:max|limit|up to)\s+(\d+)', user_message)
            if max_match:
                max_articles = int(max_match.group(1))

            # Execute discovery
            if source_name:
                state['agent_response'] = (
                    f"🚀 **Running discovery for '{source_name}'**...\n\n"
                )
            else:
                state['agent_response'] = (
                    '🚀 **Running discovery for all active sources**...\n\n'
                )

            result = self._run_discovery(
                source_name=source_name, max_articles=max_articles
            )

            if result.get('success'):
                state['agent_response'] += (
                    '✅ **Discovery completed successfully!**\n\n'
                )
                state['agent_response'] += '📊 **Results:**\n'
                state['agent_response'] += (
                    f'- Articles found: {result["articles_found"]}\n'
                )
                state['agent_response'] += (
                    f'- Articles filtered: {result["articles_filtered"]}\n'
                )
                state['agent_response'] += (
                    f'- Articles downloaded: {result["articles_downloaded"]}\n'
                )
                state['agent_response'] += (
                    f'- Execution time: {result["execution_time"]:.2f}s\n'
                )

                if result.get('errors'):
                    state['agent_response'] += '\n⚠️ **Warnings:**\n'
                    for error in result['errors'][:3]:  # Show first 3 errors
                        state['agent_response'] += f'- {error}\n'

                if result['articles_downloaded'] > 0:
                    state['agent_response'] += (
                        '\n📁 **New articles saved to:** `knowledge/agent/pdfs/`'
                    )
                    state['agent_response'] += (
                        '\n📝 **Filter log:** `knowledge/agent/filter.log`'
                    )
            else:
                state['agent_response'] += (
                    f'❌ **Discovery failed:** {result.get("error", "Unknown error")}'
                )

        except Exception as e:
            logger.error(f'Error running discovery: {e}')
            state['agent_response'] = f'❌ Error running discovery: {e}'

        state['needs_user_input'] = True
        return state

    # --- LangGraph Conditional Edges ---

    def _decide_next_action(
        self, state: ResearchAgentState
    ) -> Literal[
        'handle_chat',
        'handle_help',
        'handle_create_query',
        'handle_list_queries',
        'handle_evaluate_article',
        'handle_create_discovery_source',
        'handle_list_discovery_sources',
        'handle_edit_discovery_source',
        'handle_delete_discovery_source',
        'handle_run_discovery',
        'handle_end',
    ]:
        """Decide which action to take based on the determined action."""
        action = state.get('action')

        if action == 'help':
            return 'handle_help'
        elif action == 'create_query':
            return 'handle_create_query'
        elif action == 'list_queries':
            return 'handle_list_queries'
        elif action == 'evaluate_article':
            return 'handle_evaluate_article'
        elif action == 'create_discovery_source':
            return 'handle_create_discovery_source'
        elif action == 'list_discovery_sources':
            return 'handle_list_discovery_sources'
        elif action == 'edit_discovery_source':
            return 'handle_edit_discovery_source'
        elif action == 'delete_discovery_source':
            return 'handle_delete_discovery_source'
        elif action == 'run_discovery':
            return 'handle_run_discovery'
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
        workflow.add_node('handle_help', self._handle_help)
        workflow.add_node('handle_create_query', self._handle_create_query)
        workflow.add_node('handle_list_queries', self._handle_list_queries)
        workflow.add_node('handle_evaluate_article', self._handle_evaluate_article)
        workflow.add_node(
            'handle_create_discovery_source', self._handle_create_discovery_source
        )
        workflow.add_node(
            'handle_list_discovery_sources', self._handle_list_discovery_sources
        )
        workflow.add_node(
            'handle_edit_discovery_source', self._handle_edit_discovery_source
        )
        workflow.add_node(
            'handle_delete_discovery_source', self._handle_delete_discovery_source
        )
        workflow.add_node('handle_run_discovery', self._handle_run_discovery)
        workflow.add_node('handle_end', self._handle_end)

        # Set entry point
        workflow.set_entry_point('process_user_input')

        # Add conditional edges from process_user_input
        workflow.add_conditional_edges(
            'process_user_input',
            self._decide_next_action,
            {
                'handle_chat': 'handle_chat',
                'handle_help': 'handle_help',
                'handle_create_query': 'handle_create_query',
                'handle_list_queries': 'handle_list_queries',
                'handle_evaluate_article': 'handle_evaluate_article',
                'handle_create_discovery_source': 'handle_create_discovery_source',
                'handle_list_discovery_sources': 'handle_list_discovery_sources',
                'handle_edit_discovery_source': 'handle_edit_discovery_source',
                'handle_delete_discovery_source': 'handle_delete_discovery_source',
                'handle_run_discovery': 'handle_run_discovery',
                'handle_end': 'handle_end',
            },
        )

        # Add edges to END (except for handle_end which continues conversation)
        workflow.add_edge('handle_chat', END)
        workflow.add_edge('handle_help', END)
        workflow.add_edge('handle_create_query', END)
        workflow.add_edge('handle_list_queries', END)
        workflow.add_edge('handle_evaluate_article', END)
        workflow.add_edge('handle_create_discovery_source', END)
        workflow.add_edge('handle_list_discovery_sources', END)
        workflow.add_edge('handle_edit_discovery_source', END)
        workflow.add_edge('handle_delete_discovery_source', END)
        workflow.add_edge('handle_run_discovery', END)
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

        This method implements a hybrid MCP framework that:
        1. Uses the tool-calling agent for most structured requests
        2. Falls back to legacy graph-based handlers for conversational flows
        3. Provides intelligent routing between the two approaches

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

        # Combine persistent memory with session memory if enabled
        combined_history = []
        if self.enable_persistent_memory:
            combined_history.extend(self._persistent_conversation_history)
        if conversation_history:
            combined_history.extend(conversation_history)

        # Set conversation context for tools to access
        self._current_conversation_context = self._build_conversation_context(
            user_message, combined_history
        )

        # ------------------------------------------------------------------
        #  Enhanced Tool-agent mode with intelligent routing
        # ------------------------------------------------------------------
        if self.use_tool_agent:
            # Try modern LangGraph agent first (best practice)
            if self.use_modern_agent and self.modern_agent is not None:
                try:
                    return self._handle_with_modern_agent(
                        user_message, combined_history, config
                    )
                except Exception as e:
                    logger.warning(f'Modern agent failed, falling back to legacy: {e}')
                    # Fall through to legacy agent

            # Legacy tool-calling agent
            if self.agent_executor is not None:
                try:
                    # Check if this is a simple conversational request
                    # that should use legacy mode
                    user_lower = user_message.lower().strip()

                    # Conversational patterns that work better with legacy handlers
                    conversational_patterns = [
                        'hello',
                        'hi',
                        'hey',
                        'what can you do',
                        'what are you',
                        'how are you',
                        'thanks',
                        'thank you',
                        'goodbye',
                        'bye',
                        'exit',
                        'quit',
                        'done',
                        'help me understand',
                        'explain',
                        'i need help',
                        'can you help',
                        'guide me',
                        'walk me through',
                    ]

                    # If it's a simple conversational request, use legacy mode for
                    # better UX
                    if any(
                        pattern in user_lower for pattern in conversational_patterns
                    ):
                        logger.debug('Using legacy mode for conversational request')
                        return self._handle_with_legacy_mode(
                            user_message, combined_history, config
                        )

                    # For structured requests, enhance the message with tool guidance
                    enhanced_message = self._enhance_message_for_tools(user_message)

                    # Convert conversation history to the format expected by LangChain
                    chat_history = []
                    if combined_history:
                        for msg in combined_history:
                            role = msg.get('role', '')
                            content = msg.get('content', '')
                            if role == 'user':
                                chat_history.append(('human', content))
                            elif role in ['agent', 'assistant']:
                                chat_history.append(('ai', content))

                    # Use the tool-calling agent with conversation history
                    agent_reply = self.agent_executor.invoke(
                        {'input': enhanced_message, 'chat_history': chat_history}
                    )

                    # Debug: Log the full agent response
                    logger.debug(f'Full agent response: {agent_reply}')

                    # Extract the actual content from the agent response
                    if isinstance(agent_reply, dict):
                        content = (
                            agent_reply.get('output')
                            or agent_reply.get('content')
                            or agent_reply.get('text')
                            or agent_reply.get('response')
                            or str(agent_reply)
                        )
                    elif hasattr(agent_reply, 'content'):
                        content = agent_reply.content
                    else:
                        content = str(agent_reply)

                    # Debug: Log the extracted content
                    logger.debug(f'Extracted content: {content}')

                    # If we got an empty response, try to handle the request directly
                    if not content or not str(content).strip():
                        logger.warning(
                            'Agent returned empty response, handling directly'
                        )

                        # Try to extract tool name from the enhanced message
                        import re

                        tool_match = re.search(
                            r'(create_arxiv_source|create_pubmed_source|list_discovery_sources|run_discovery|list_queries|get_query|delete_query)',
                            enhanced_message,
                        )
                        tool_name = tool_match.group(1) if tool_match else None

                        if tool_name:
                            try:
                                tools = self._create_tools()
                                tool = next(
                                    (t for t in tools if t.name == tool_name), None
                                )
                                if tool:
                                    logger.debug(f'Calling tool directly: {tool_name}')
                                    content = tool.func('')
                                    logger.debug(f'Direct tool output: {content}')
                            except Exception as e:
                                logger.error(f'Error calling {tool_name} directly: {e}')
                                content = f'I can help you with {tool_name}, but encountered an error: {e}'

                        # Generic fallback
                        if not content or not str(content).strip():
                            content = '⚠️ The tool did not return any output. Please try again or check the tool implementation.'
                            logger.debug('Using generic fallback for empty tool output')

                    # Save conversation to persistent memory if enabled
                    if self.enable_persistent_memory and content:
                        self._persistent_conversation_history.append(
                            {'role': 'user', 'content': user_message}
                        )
                        self._persistent_conversation_history.append(
                            {'role': 'agent', 'content': content}
                        )
                        self._save_conversation_memory()

                    return {
                        'agent_response': content,
                        'action': 'tool_agent',
                        'needs_user_input': True,
                        'error_message': None,
                        'available_queries': self._list_queries(),
                    }

                except Exception as e:
                    logger.warning(
                        f'Tool-agent processing failed, falling back to legacy mode: {e}'
                    )
                    # Fall back to legacy mode if tool agent fails
                    return self._handle_with_legacy_mode(
                        user_message, combined_history, config
                    )

        # ------------------------------------------------------------------
        #  Legacy keyword-parsing mode (fallback)
        # ------------------------------------------------------------------
        return self._handle_with_legacy_mode(user_message, combined_history, config)

    def _enhance_message_for_tools(self, user_message: str) -> str:
        """
        Enhance a user message with context about available tools and expected JSON
        formats.

        This helps the LLM understand how to structure requests for the MCP framework.

        Args:
            user_message: The original user message.

        Returns:
            str: Enhanced message with tool guidance.
        """
        # Get conversation context
        context = getattr(self, '_current_conversation_context', '')

        # Analyze message to suggest specific tools
        suggested_tools = []
        message_lower = user_message.lower()

        if (
            any(word in message_lower for word in ['create', 'make', 'build'])
            and 'arxiv' in message_lower
        ):
            suggested_tools.append(
                'create_arxiv_source - Use this to create the ArXiv source we discussed'
            )
        if (
            any(word in message_lower for word in ['create', 'make', 'build'])
            and 'pubmed' in message_lower
        ):
            suggested_tools.append(
                'create_pubmed_source - Use this to create the PubMed source'
            )
        if 'list' in message_lower and 'source' in message_lower:
            suggested_tools.append(
                'list_discovery_sources - Show all configured sources'
            )
        if 'run' in message_lower and 'discovery' in message_lower:
            suggested_tools.append('run_discovery - Execute discovery for sources')

        # Build enhanced message
        enhanced = f"""{user_message}

Recent conversation context: {context}

Available tools:
- Query management: list_queries, create_query, get_query, delete_query
- Discovery sources: list_discovery_sources, create_arxiv_source, create_pubmed_source, run_discovery
- Help: get_help"""

        if suggested_tools:
            enhanced += '\n\nSuggested tools for this request:\n- ' + '\n- '.join(
                suggested_tools
            )

        enhanced += '\n\nUse appropriate tools to complete the request. For ArXiv sources, use JSON format like: {"name": "source_name", "keywords": ["keyword1", "keyword2"], "categories": ["cs.LG", "cs.AI"]}'

        return enhanced

    def _handle_with_legacy_mode(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        config: RunnableConfig | None = None,
    ) -> dict[str, Any]:
        """
        Handle a request using the legacy graph-based mode.

        This provides the conversational experience and handles edge cases
        that the tool-calling agent might not handle well.

        Args:
            user_message: The user's input message.
            conversation_history: Previous conversation messages.
            config: Optional LangChain RunnableConfig.

        Returns:
            dict: Response from the legacy graph-based agent.
        """
        logger.debug('Using legacy graph-based mode')

        # Construct initial state for the LangGraph workflow
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
            final_state = self.app.invoke(initial_state, config=config)

            # Save conversation to persistent memory if enabled
            response_content = final_state.get('agent_response')
            if self.enable_persistent_memory and response_content:
                self._persistent_conversation_history.append(
                    {'role': 'user', 'content': user_message}
                )
                self._persistent_conversation_history.append(
                    {'role': 'agent', 'content': response_content}
                )
                self._save_conversation_memory()

            return {
                'agent_response': final_state.get('agent_response'),
                'action': final_state.get('action'),
                'needs_user_input': final_state.get('needs_user_input', True),
                'error_message': final_state.get('error_message'),
                'available_queries': final_state.get('available_queries', []),
            }

        except Exception as e:
            logger.error(f'Error processing user message (legacy mode): {e}')
            raise ResearchAgentError(
                f'Failed to process message: {e!s}',
            ) from e

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

    # --- Discovery Source Management Public Methods ---

    def list_discovery_sources(self) -> list[str]:
        """
        List all available discovery source names.

        Returns:
            list[str]: List of discovery source names.
        """
        return self._list_discovery_sources()

    def get_discovery_source(self, source_name: str):
        """
        Get a discovery source by name.

        Args:
            source_name: Name of the source to retrieve.

        Returns:
            DiscoverySource: The source if found, None otherwise.
        """
        return self._get_discovery_source(source_name)

    def create_discovery_source(self, source_config: dict[str, Any]) -> bool:
        """
        Create a new discovery source.

        Args:
            source_config: Dictionary containing source configuration.

        Returns:
            bool: True if successful, False otherwise.
        """
        return self._create_discovery_source(source_config)

    def update_discovery_source(self, source) -> bool:
        """
        Update an existing discovery source.

        Args:
            source: Updated DiscoverySource object.

        Returns:
            bool: True if successful, False otherwise.
        """
        return self._update_discovery_source(source)

    def delete_discovery_source(self, source_name: str) -> bool:
        """
        Delete a discovery source.

        Args:
            source_name: Name of the source to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        return self._delete_discovery_source(source_name)

    def run_discovery(
        self, source_name: str | None = None, max_articles: int | None = None
    ) -> dict[str, Any]:
        """
        Run discovery for sources.

        Args:
            source_name: Specific source to run (optional).
            max_articles: Maximum articles to process (optional).

        Returns:
            dict: Discovery results including articles found, filtered, and downloaded.
        """
        return self._run_discovery(source_name, max_articles)

    # ------------------------------------------------------------------
    #  Tool-agent helpers
    # ------------------------------------------------------------------

    def _create_tools(self):
        """Create a comprehensive list of LangChain Tool objects backed by internal
        methods."""

        from langchain.tools import Tool

        tools: list[Tool] = []

        # --- Query Management Tools ---

        def _list_queries_tool(_input: str) -> str:
            """Return a newline-separated list of available research queries."""
            queries = self._list_queries()
            return '\n'.join(queries) if queries else 'No research queries found.'

        tools.append(
            Tool(
                name='list_queries',
                description='List all available research queries.',
                func=_list_queries_tool,
            ),
        )

        def _show_queries_location_tool(_input: str) -> str:
            """Show where queries are stored and provide detailed path information."""
            from pathlib import Path

            result = ['**Query Storage Information:**\n']
            result.append(f'📁 **Configured queries directory:** {self.queries_dir}')
            result.append(f'🔍 **Directory exists:** {self.queries_dir.exists()}')
            result.append(f'📍 **Absolute path:** {self.queries_dir.resolve()}')

            # List actual query files in the configured directory
            if self.queries_dir.exists():
                query_files = list(self.queries_dir.glob('*.json'))
                result.append(
                    f'\n📝 **Query files in configured directory:** {len(query_files)}'
                )
                for f in query_files:
                    result.append(f'   - {f.name}')
            else:
                result.append('\n❌ **Configured directory does not exist!**')

            # Check for legacy queries directory
            legacy_dir = Path('queries')
            if legacy_dir.exists():
                legacy_files = list(legacy_dir.glob('*.json'))
                result.append(
                    f'\n📁 **Legacy queries directory found:** {legacy_dir.resolve()}'
                )
                result.append(f'📝 **Legacy query files:** {len(legacy_files)}')
                for f in legacy_files:
                    result.append(f'   - {f.name}')

            # Check planning/queries too
            planning_dir = Path('planning/queries')
            if planning_dir.exists():
                planning_files = list(planning_dir.glob('*.json'))
                result.append(
                    f'\n📁 **Planning queries directory found:** {planning_dir.resolve()}'
                )
                result.append(f'📝 **Planning query files:** {len(planning_files)}')
                for f in planning_files:
                    result.append(f'   - {f.name}')

            return '\n'.join(result)

        tools.append(
            Tool(
                name='show_queries_location',
                description='Show where research queries are stored and provide detailed path information for debugging.',
                func=_show_queries_location_tool,
            ),
        )

        def _get_query_tool(input_json: str) -> str:
            """Get details of a specific research query. Input should be JSON with
            'query_name' key."""
            import json as _json

            try:
                params = _json.loads(input_json) if input_json else {}
                query_name = params.get('query_name')

                if not query_name:
                    return "Error: Please provide 'query_name' in JSON format."

                query = self._load_query(query_name)
                if not query:
                    return f"Query '{query_name}' not found."

                return _json.dumps(query.model_dump(), indent=2)

            except Exception as e:
                return f'Error getting query: {e}'

        tools.append(
            Tool(
                name='get_query',
                description='Get detailed information about a specific research query. Provide JSON with query_name.',
                func=_get_query_tool,
            ),
        )

        def _create_query_tool(input_json: str) -> str:
            """Create a new research query. Input should be JSON with query
            configuration."""
            import json as _json

            from thoth.utilities.models import ResearchQuery

            try:
                if not input_json:
                    return 'Error: Please provide query configuration in JSON format.'

                query_data = _json.loads(input_json)
                query = ResearchQuery(**query_data)

                if self._save_query(query):
                    return f'Successfully created research query: {query.name}'
                else:
                    return f'Failed to create query: {query.name}'

            except Exception as e:
                return f'Error creating query: {e}'

        tools.append(
            Tool(
                name='create_query',
                description='Create a new research query. Provide JSON with query configuration including name, research_question, keywords, etc.',
                func=_create_query_tool,
            ),
        )

        def _delete_query_tool(input_json: str) -> str:
            """Delete a research query. Input should be JSON with 'query_name' key."""
            import json as _json

            try:
                params = _json.loads(input_json) if input_json else {}
                query_name = params.get('query_name')

                if not query_name:
                    return "Error: Please provide 'query_name' in JSON format."

                if self._delete_query(query_name):
                    return f'Successfully deleted query: {query_name}'
                else:
                    return f'Failed to delete query: {query_name} (may not exist)'

            except Exception as e:
                return f'Error deleting query: {e}'

        tools.append(
            Tool(
                name='delete_query',
                description='Delete a research query. Provide JSON with query_name.',
                func=_delete_query_tool,
            ),
        )

        # --- Discovery Source Management Tools ---

        def _list_discovery_sources_tool(_input: str) -> str:
            """Return a detailed list of discovery sources with status information."""
            try:
                if not self.discovery_manager:
                    return 'Discovery manager not available. Please check your installation.'

                sources = self.discovery_manager.list_sources()
                if not sources:
                    return 'No discovery sources configured.'

                result = ['Discovery Sources:\n']
                for source in sources:
                    status = '🟢 Active' if source.is_active else '🔴 Inactive'
                    result.append(
                        f'**{source.name}** ({source.source_type}) - {status}'
                    )
                    result.append(f'  Description: {source.description}')
                    if source.last_run:
                        result.append(f'  Last run: {source.last_run}')
                    if source.schedule_config:
                        result.append(
                            f'  Schedule: Every {source.schedule_config.interval_minutes} minutes'
                        )
                        result.append(
                            f'  Max articles: {source.schedule_config.max_articles_per_run}'
                        )
                    result.append('')

                return '\n'.join(result)

            except Exception as e:
                return f'Error listing discovery sources: {e}'

        tools.append(
            Tool(
                name='list_discovery_sources',
                description='List all configured discovery sources with detailed status information.',
                func=_list_discovery_sources_tool,
            ),
        )

        def _get_discovery_source_tool(input_json: str) -> str:
            """Get detailed information about a specific discovery source. Input should
            be JSON with 'source_name' key."""
            import json as _json

            try:
                params = _json.loads(input_json) if input_json else {}
                source_name = params.get('source_name')

                if not source_name:
                    return "Error: Please provide 'source_name' in JSON format."

                source = self._get_discovery_source(source_name)
                if not source:
                    return f"Discovery source '{source_name}' not found."

                return _json.dumps(source.model_dump(), indent=2)

            except Exception as e:
                return f'Error getting discovery source: {e}'

        tools.append(
            Tool(
                name='get_discovery_source',
                description='Get detailed information about a specific discovery source. Provide JSON with source_name.',
                func=_get_discovery_source_tool,
            ),
        )

        def _create_discovery_source_tool(input_json: str) -> str:
            """Create a new discovery source. Input should be JSON with source
            configuration."""
            import json as _json

            try:
                if not input_json:
                    return 'Error: Please provide source configuration in JSON format.'

                source_config = _json.loads(input_json)

                if self._create_discovery_source(source_config):
                    return f'Successfully created discovery source: {source_config.get("name", "unknown")}'
                else:
                    return f'Failed to create discovery source: {source_config.get("name", "unknown")}'

            except Exception as e:
                return f'Error creating discovery source: {e}'

        tools.append(
            Tool(
                name='create_discovery_source',
                description='Create a new discovery source. Provide JSON with complete source configuration including name, source_type, description, api_config/scraper_config, etc.',
                func=_create_discovery_source_tool,
            ),
        )

        def _create_arxiv_source_tool(input_json: str) -> str:
            """Create an ArXiv discovery source with simplified parameters. Input should
            be JSON with 'name', 'keywords', and optional 'categories'."""
            import json as _json

            try:
                params = _json.loads(input_json) if input_json else {}
                name = params.get('name')
                keywords = params.get('keywords', [])
                categories = params.get('categories', ['cs.LG', 'cs.AI'])

                # If parameters are missing, try to extract from recent conversation
                # context
                if not name or not keywords:
                    # Access conversation history to understand context
                    recent_context = ''
                    if hasattr(self, '_current_conversation_context'):
                        recent_context = self._current_conversation_context

                    # Provide helpful guidance based on missing parameters
                    missing_params = []
                    if not name:
                        missing_params.append("name (e.g., 'Daily ML & Econ ArXiv')")
                    if not keywords:
                        missing_params.append(
                            "keywords (e.g., ['machine learning', 'economics'])"
                        )

                    guidance = (
                        f'Missing required parameters: {", ".join(missing_params)}. '
                    )
                    if recent_context:
                        guidance += f'Based on our conversation, you mentioned: {recent_context[:200]}... '
                    guidance += 'Please provide the missing information.'

                    return guidance

                # Create source configuration
                source_config = {
                    'name': name,
                    'source_type': 'api',
                    'description': f'ArXiv source for {", ".join(categories)} papers',
                    'is_active': True,
                    'api_config': {
                        'source': 'arxiv',
                        'categories': categories,
                        'keywords': keywords,
                        'sort_by': 'lastUpdatedDate',
                        'sort_order': 'descending',
                    },
                    'schedule_config': {
                        'interval_minutes': 1440,  # Daily (24 hours) as requested
                        'max_articles_per_run': 50,  # More articles for daily runs
                        'enabled': True,
                    },
                    'query_filters': [],
                }

                if self._create_discovery_source(source_config):
                    return f"✅ Successfully created ArXiv source '{name}'!\n\n📋 **Configuration:**\n- Categories: {categories}\n- Keywords: {keywords}\n- Schedule: Daily (every 24 hours)\n- Max articles per run: 50\n\n🚀 The source is now active and will automatically discover new papers daily."
                else:
                    return f"❌ Failed to create ArXiv source '{name}'. Please check the logs for more details."

            except json.JSONDecodeError as e:
                return f"❌ Invalid JSON format: {e}. Please provide valid JSON with 'name' and 'keywords' fields."
            except Exception as e:
                return f'❌ Error creating ArXiv source: {e}'

        tools.append(
            Tool(
                name='create_arxiv_source',
                description='IMMEDIATELY create an ArXiv discovery source when user wants an ArXiv source. Use this tool directly - do NOT just explain what you would do. Provide JSON with name (required), keywords (required list), and optional categories (defaults to cs.LG, cs.AI). Example: {"name": "daily_ml_source", "keywords": ["machine learning", "neural networks"], "categories": ["cs.LG", "cs.AI", "cs.CL"]}',
                func=_create_arxiv_source_tool,
            ),
        )

        def _create_pubmed_source_tool(input_json: str) -> str:
            """Create a PubMed discovery source with simplified parameters. Input should
            be JSON with 'name' and 'keywords'."""
            import json as _json

            try:
                params = _json.loads(input_json) if input_json else {}
                name = params.get('name')
                keywords = params.get('keywords', [])

                if not name:
                    return "Error: Please provide 'name' for the PubMed source."

                if not keywords:
                    return (
                        "Error: Please provide 'keywords' list for the PubMed source."
                    )

                # Create source configuration
                source_config = {
                    'name': name,
                    'source_type': 'api',
                    'description': f'PubMed source for {", ".join(keywords)} research',
                    'is_active': True,
                    'api_config': {
                        'source': 'pubmed',
                        'keywords': keywords,
                        'sort_by': 'date',
                        'sort_order': 'descending',
                    },
                    'schedule_config': {
                        'interval_minutes': 240,
                        'max_articles_per_run': 5,
                        'enabled': True,
                    },
                    'query_filters': [],
                }

                if self._create_discovery_source(source_config):
                    return f"Successfully created PubMed source '{name}' with keywords {keywords}"
                else:
                    return f"Failed to create PubMed source '{name}'"

            except Exception as e:
                return f'Error creating PubMed source: {e}'

        tools.append(
            Tool(
                name='create_pubmed_source',
                description='Create a PubMed discovery source with simplified parameters. Provide JSON with name (required) and keywords (required list).',
                func=_create_pubmed_source_tool,
            ),
        )

        def _update_discovery_source_tool(input_json: str) -> str:
            """Update an existing discovery source. Input should be JSON with
            'source_name' and updated configuration."""
            import json as _json

            try:
                params = _json.loads(input_json) if input_json else {}
                source_name = params.get('source_name')

                if not source_name:
                    return "Error: Please provide 'source_name' in JSON format."

                # Get existing source
                source = self._get_discovery_source(source_name)
                if not source:
                    return f"Discovery source '{source_name}' not found."

                # Update with provided parameters
                updates = {k: v for k, v in params.items() if k != 'source_name'}

                # Update the source object
                for key, value in updates.items():
                    if hasattr(source, key):
                        setattr(source, key, value)

                if self._update_discovery_source(source):
                    return f'Successfully updated discovery source: {source_name}'
                else:
                    return f'Failed to update discovery source: {source_name}'

            except Exception as e:
                return f'Error updating discovery source: {e}'

        tools.append(
            Tool(
                name='update_discovery_source',
                description='Update an existing discovery source. Provide JSON with source_name and any fields to update (description, is_active, api_config, etc.).',
                func=_update_discovery_source_tool,
            ),
        )

        def _delete_discovery_source_tool(input_json: str) -> str:
            """Delete a discovery source. Input should be JSON with 'source_name'
            key."""
            import json as _json

            try:
                params = _json.loads(input_json) if input_json else {}
                source_name = params.get('source_name')

                if not source_name:
                    return "Error: Please provide 'source_name' in JSON format."

                if self._delete_discovery_source(source_name):
                    return f'Successfully deleted discovery source: {source_name}'
                else:
                    return f'Failed to delete discovery source: {source_name} (may not exist)'

            except Exception as e:
                return f'Error deleting discovery source: {e}'

        tools.append(
            Tool(
                name='delete_discovery_source',
                description='Delete a discovery source. Provide JSON with source_name.',
                func=_delete_discovery_source_tool,
            ),
        )

        def _run_discovery_tool(input_json: str) -> str:
            """Run discovery. Input should be JSON with optional keys 'source_name'
            (str) and 'max_articles' (int). Returns the discovery result as a JSON
            string."""
            import json as _json

            if not input_json:
                params: dict[str, Any] = {}
            else:
                try:
                    params = _json.loads(input_json)
                except Exception:
                    params = {}

            result = self._run_discovery(
                source_name=params.get('source_name'),
                max_articles=params.get('max_articles'),
            )

            return _json.dumps(result, indent=2)

        tools.append(
            Tool(
                name='run_discovery',
                description=(
                    'Run article discovery for a specific source or for all '
                    'active sources. Provide JSON input with optional '
                    'source_name and max_articles.'
                ),
                func=_run_discovery_tool,
            ),
        )

        # --- Article Evaluation Tools ---

        def _evaluate_article_tool(input_json: str) -> str:
            """Evaluate an article against a research query. Input should be JSON with
            'query_name', 'article_title', 'article_abstract', and optionally
            'article_content'."""
            import json as _json

            try:
                params = _json.loads(input_json) if input_json else {}
                query_name = params.get('query_name')

                if not query_name:
                    return "Error: Please provide 'query_name' in JSON format."

                # This would need actual article data - for now return guidance
                return f"To evaluate an article against query '{query_name}', please provide article data including title, abstract, and optionally full content."

            except Exception as e:
                return f'Error evaluating article: {e}'

        tools.append(
            Tool(
                name='evaluate_article',
                description='Evaluate an article against a research query. Provide JSON with query_name, article_title, article_abstract, and optionally article_content.',
                func=_evaluate_article_tool,
            ),
        )

        # --- Help and Information Tools ---

        def _get_help_tool(_input: str) -> str:
            """Get comprehensive help information about all available capabilities."""
            return """
🤖 **Enhanced Thoth Research Assistant - Full Capabilities**

I'm an AI assistant that helps you manage both research queries AND discovery sources for automatic article collection and filtering.

**🔍 Discovery Source Management:**
• Use `list_discovery_sources` - Show all configured discovery sources
• Use `create_arxiv_source` with JSON: {"name": "ml_papers", "keywords": ["machine learning", "neural networks"]}
• Use `create_pubmed_source` with JSON: {"name": "bio_research", "keywords": ["neuroscience", "brain imaging"]}
• Use `run_discovery` with JSON: {"source_name": "arxiv_test"} - Run discovery for specific source
• Use `run_discovery` with JSON: {"max_articles": 5} - Run all active sources with article limit
• Use `update_discovery_source` - Modify an existing source
• Use `delete_discovery_source` - Remove a discovery source

**📝 Research Query Management:**
• Use `create_query` - Create a new research query to filter articles
• Use `list_queries` - Show all existing research queries
• Use `get_query` - Get details about a specific query
• Use `delete_query` - Remove a research query
• Use `show_queries_location` - Show where queries are stored (debugging)
• Use `evaluate_article` - Test how well an article matches your queries

**📚 Knowledge Base RAG (NEW):**
• Use `search_knowledge` - Search through your research papers and notes
• Use `ask_knowledge` - Ask questions about your research collection
• Use `index_knowledge` - Index all documents into the RAG system
• Use `rag_stats` - Get statistics about the indexed knowledge base

**🎯 How It Works:**
1. **Discovery Sources** automatically find new research articles from:
   - ArXiv API (computer science, physics, math papers)
   - PubMed API (biomedical research)
   - Web scrapers (journal websites)

2. **Research Queries** define what you're interested in:
   - Keywords, required/preferred/excluded topics
   - Your queries automatically filter discovered articles
   - Only relevant articles are downloaded and processed

3. **Knowledge Base RAG** helps you explore your research:
   - Search through all your papers and notes
   - Ask questions and get answers with citations
   - Find connections between different papers

**💡 Tool Usage Examples:**
• Create ArXiv source: Use create_arxiv_source with {"name": "ai_research", "keywords": ["artificial intelligence"], "categories": ["cs.AI", "cs.LG"]}
• Search knowledge: Use search_knowledge with {"query": "transformer architecture"}
• Ask question: Use ask_knowledge with {"question": "What are the main contributions of attention mechanisms?"}

**🚀 Quick Start:**
1. Use list_discovery_sources to see current sources
2. Use create_arxiv_source or create_pubmed_source to add sources
3. Use create_query to define filtering criteria
4. Use run_discovery to start finding articles
5. Use search_knowledge or ask_knowledge to explore your collection

I can intelligently choose the right tools based on your requests!
"""

        tools.append(
            Tool(
                name='get_help',
                description='Get comprehensive help information about all available capabilities and tool usage examples.',
                func=_get_help_tool,
            ),
        )

        # --- RAG Knowledge Base Tools ---

        def _search_knowledge_tool(input_json: str) -> str:
            """Search the knowledge base for relevant documents. Input should be JSON
            with 'query' and optional 'k' (number of results) and 'filter'
            parameters."""
            import json as _json

            try:
                # Get pipeline instance to access RAG manager
                from thoth.pipeline import ThothPipeline

                pipeline = ThothPipeline()

                params = _json.loads(input_json) if input_json else {}
                query = params.get('query')

                if not query:
                    return "Error: Please provide 'query' in JSON format."

                k = params.get('k', 4)
                filter_dict = params.get('filter')

                results = pipeline.search_knowledge_base(
                    query=query,
                    k=k,
                    filter=filter_dict,
                )

                if not results:
                    return f"No results found for query: '{query}'"

                response = [f"Search results for: '{query}'\n"]
                for i, result in enumerate(results, 1):
                    response.append(f'\n**Result {i}:**')
                    response.append(f'Title: {result["title"]}')
                    response.append(f'Type: {result["document_type"]}')
                    response.append(f'Score: {result["score"]:.3f}')
                    response.append(f'Preview: {result["content"][:200]}...')

                return '\n'.join(response)

            except Exception as e:
                return f'Error searching knowledge base: {e}'

        tools.append(
            Tool(
                name='search_knowledge',
                description='Search the knowledge base for relevant documents. Provide JSON with query and optional k (number of results, default 4).',
                func=_search_knowledge_tool,
            ),
        )

        def _ask_knowledge_tool(input_json: str) -> str:
            """Ask a question about the knowledge base. Input should be JSON with
            'question' and optional 'k' (number of context docs) parameters."""
            import json as _json

            try:
                # Get pipeline instance to access RAG manager
                from thoth.pipeline import ThothPipeline

                pipeline = ThothPipeline()

                params = _json.loads(input_json) if input_json else {}
                question = params.get('question')

                if not question:
                    return "Error: Please provide 'question' in JSON format."

                k = params.get('k', 4)
                filter_dict = params.get('filter')

                result = pipeline.ask_knowledge_base(
                    question=question,
                    k=k,
                    filter=filter_dict,
                )

                response = [f'**Question:** {result["question"]}\n']
                response.append(f'**Answer:** {result["answer"]}\n')

                if result.get('sources'):
                    response.append('**Sources:**')
                    for i, source in enumerate(result['sources'], 1):
                        title = source['metadata'].get('title', 'Unknown')
                        doc_type = source['metadata'].get('document_type', 'Unknown')
                        response.append(f'{i}. {title} ({doc_type})')

                return '\n'.join(response)

            except Exception as e:
                return f'Error asking knowledge base: {e}'

        tools.append(
            Tool(
                name='ask_knowledge',
                description='Ask a question about your research knowledge base. Provide JSON with question and optional k (number of context documents, default 4).',
                func=_ask_knowledge_tool,
            ),
        )

        def _index_knowledge_tool(_input: str) -> str:
            """Index all documents in the knowledge base for RAG search."""
            try:
                # Get pipeline instance to access RAG manager
                from thoth.pipeline import ThothPipeline

                pipeline = ThothPipeline()

                stats = pipeline.index_knowledge_base()

                response = ['**Knowledge Base Indexing Complete!**\n']
                response.append(f'Total files indexed: {stats["total_files"]}')
                response.append(f'- Markdown files: {stats["markdown_files"]}')
                response.append(f'- Note files: {stats["note_files"]}')
                response.append(f'Total chunks created: {stats["total_chunks"]}')

                if stats['errors']:
                    response.append('\n**Errors encountered:**')
                    for error in stats['errors']:
                        response.append(f'- {error}')

                if 'vector_store' in stats:
                    response.append('\n**Vector Store Info:**')
                    response.append(
                        f'- Collection: {stats["vector_store"]["collection_name"]}'
                    )
                    response.append(
                        f'- Documents: {stats["vector_store"]["document_count"]}'
                    )

                return '\n'.join(response)

            except Exception as e:
                return f'Error indexing knowledge base: {e}'

        tools.append(
            Tool(
                name='index_knowledge',
                description='Index all documents in the knowledge base for RAG search. This enables semantic search and question answering.',
                func=_index_knowledge_tool,
            ),
        )

        def _rag_stats_tool(_input: str) -> str:
            """Get statistics about the RAG knowledge base."""
            try:
                # Get pipeline instance to access RAG manager
                from thoth.pipeline import ThothPipeline

                pipeline = ThothPipeline()

                stats = pipeline.get_rag_stats()

                response = ['**RAG System Statistics:**\n']
                response.append(f'Documents indexed: {stats.get("document_count", 0)}')
                response.append(
                    f'Collection name: {stats.get("collection_name", "Unknown")}'
                )
                response.append(
                    f'Embedding model: {stats.get("embedding_model", "Unknown")}'
                )
                response.append(f'QA model: {stats.get("qa_model", "Unknown")}')
                response.append(f'Chunk size: {stats.get("chunk_size", "Unknown")}')
                response.append(
                    f'Chunk overlap: {stats.get("chunk_overlap", "Unknown")}'
                )

                return '\n'.join(response)

            except Exception as e:
                return f'Error getting RAG stats: {e}'

        tools.append(
            Tool(
                name='rag_stats',
                description='Get statistics about the RAG knowledge base system.',
                func=_rag_stats_tool,
            ),
        )

        logger.info(f'Created {len(tools)} tools for the MCP framework')
        return tools

    def _init_tool_agent(self) -> None:
        """Initialise the LangChain AgentExecutor that uses function calling
        (legacy approach)."""

        # Try modern approach first
        if self._init_modern_langgraph_agent():
            self.use_modern_agent = True
            return

        # Fallback to legacy approach
        self.use_modern_agent = False

        from langchain.agents import AgentExecutor, create_openai_functions_agent
        from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

        tools = self._create_tools()

        # Simpler, more natural prompt (closer to LangChain best practices)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    'system',
                    'You are a helpful research assistant for the Thoth system. You help users manage research queries and discovery sources for automatic article collection and filtering. Pay attention to conversation context and previous discussions when selecting and using tools. Be conversational and remember what was discussed earlier.',
                ),
                MessagesPlaceholder(variable_name='chat_history'),
                ('user', '{input}'),
                MessagesPlaceholder(variable_name='agent_scratchpad'),
            ]
        )

        # Create the agent using the legacy approach
        agent = create_openai_functions_agent(llm=self.llm, tools=tools, prompt=prompt)

        # Create the agent executor with memory support
        self.agent_executor = AgentExecutor(
            agent=agent,
            tools=tools,
            verbose=False,
            return_intermediate_steps=False,
            handle_parsing_errors=True,
        )

    def _init_modern_langgraph_agent(self) -> None:
        """Initialize a modern LangGraph-based agent following current LangChain best
        practices."""
        try:
            from langgraph.checkpoint.memory import MemorySaver
            from langgraph.prebuilt import create_react_agent

            tools = self._create_tools()

            # Use modern LangGraph approach with built-in memory (simplest approach)
            memory = MemorySaver()

            self.modern_agent = create_react_agent(self.llm, tools, checkpointer=memory)

            logger.info('Modern LangGraph agent initialized successfully')
            return True

        except ImportError:
            logger.warning('LangGraph not available, falling back to legacy agent')
            return False
        except Exception as e:
            logger.warning(f'Failed to initialize modern LangGraph agent: {e}')
            return False

    # --- Memory Management Methods ---

    def _load_conversation_memory(self) -> None:
        """Load conversation history from persistent storage."""
        try:
            if self.memory_file.exists():
                with open(self.memory_file, encoding='utf-8') as f:
                    data = json.load(f)
                    self._persistent_conversation_history = data.get(
                        'conversation_history', []
                    )
                    logger.debug(
                        f'Loaded {len(self._persistent_conversation_history)} messages from memory'
                    )
            else:
                self._persistent_conversation_history = []
                logger.debug('No existing memory file found, starting fresh')
        except Exception as e:
            logger.warning(f'Failed to load conversation memory: {e}')
            self._persistent_conversation_history = []

    def _save_conversation_memory(self) -> None:
        """Save conversation history to persistent storage."""
        try:
            # Keep only the last 100 messages to prevent file from growing too large
            trimmed_history = self._persistent_conversation_history[-100:]

            data = {
                'conversation_history': trimmed_history,
                'last_updated': datetime.now().isoformat(),
            }

            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug(f'Saved {len(trimmed_history)} messages to memory')
        except Exception as e:
            logger.warning(f'Failed to save conversation memory: {e}')

    def get_conversation_history(self) -> list[dict[str, str]]:
        """
        Get the current conversation history.

        Returns:
            list[dict[str, str]]: The conversation history with role and content.
        """
        if self.enable_persistent_memory:
            return self._persistent_conversation_history.copy()
        return []

    def clear_conversation_memory(self) -> None:
        """Clear all conversation history."""
        if self.enable_persistent_memory:
            self._persistent_conversation_history.clear()
            self._save_conversation_memory()
            logger.info('Conversation memory cleared')

    def _build_conversation_context(
        self, current_message: str, conversation_history: list[dict[str, str]]
    ) -> str:
        """
        Build a conversation context summary for tools to understand references.

        Args:
            current_message: The current user message
            conversation_history: Recent conversation messages

        Returns:
            str: Summarized context for tools
        """
        context_parts = []

        # Add current message context
        context_parts.append(f'Current request: {current_message}')

        # Add recent conversation context (last 3 exchanges)
        if conversation_history:
            recent_messages = conversation_history[-6:]  # Last 6 messages (3 exchanges)
            for msg in recent_messages:
                role = msg.get('role', '')
                content = msg.get('content', '')[:150]  # Truncate long messages
                if role == 'user':
                    context_parts.append(f'User previously said: {content}')
                elif role in ['agent', 'assistant']:
                    context_parts.append(f'Agent previously responded: {content}')

        return ' | '.join(context_parts)

    def _handle_with_modern_agent(
        self,
        user_message: str,
        conversation_history: list[dict[str, str]] | None = None,
        config: RunnableConfig | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """
        Handle a request using the modern LangGraph agent (LangChain best practice).

        Uses thread-based conversation management and natural tool selection.

        Args:
            user_message: The user's input message.
            conversation_history: Previous conversation messages
                (used for thread_id generation).
            config: Optional LangChain RunnableConfig.

        Returns:
            dict: Response from the modern LangGraph agent.
        """
        from langchain_core.messages import AIMessage, HumanMessage

        logger.debug('Using modern LangGraph agent')

        try:
            # Use a stable thread_id so LangGraph can maintain proper conversation
            # memory. Don't hash conversation - use a consistent ID for this session
            thread_id = 'main_conversation'  # Stable ID for memory persistence

            # Modern LangGraph approach with thread-based memory
            agent_config = {'configurable': {'thread_id': thread_id}}

            # Build the full conversation context for LangGraph
            messages = []

            # Add conversation history to messages
            if conversation_history:
                for msg in conversation_history:
                    role = msg.get('role', '')
                    content = msg.get('content', '')
                    if role == 'user':
                        messages.append(HumanMessage(content=content))
                    elif role in ['agent', 'assistant']:
                        messages.append(AIMessage(content=content))

            # Add the current user message
            messages.append(HumanMessage(content=user_message))

            result = self.modern_agent.invoke(
                {'messages': messages},  # Full conversation context
                config=agent_config,
            )

            # Extract the response from LangGraph result
            result_messages = result.get('messages', [])
            if result_messages:
                last_message = result_messages[-1]
                content = getattr(last_message, 'content', str(last_message))
            else:
                content = (
                    "I'm here to help with research queries and discovery sources."
                )

            return {
                'agent_response': content,
                'action': 'modern_agent',
                'needs_user_input': True,
                'error_message': None,
                'available_queries': self._list_queries(),
            }

        except Exception as e:
            logger.error(f'Error in modern agent processing: {e}')
            raise  # Re-raise to trigger fallback
