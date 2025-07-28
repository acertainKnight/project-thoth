"""
LLM Processor for Thoth.

This module handles the analysis of content using LLM.
"""

from pathlib import Path
from typing import Any, Literal

from jinja2 import ChoiceLoader, Environment, FileSystemLoader
from langchain.schema import Document
from langchain.text_splitter import MarkdownTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END, StateGraph
from loguru import logger

from thoth.services.llm_service import LLMService
from thoth.utilities.schemas import AnalysisResponse, AnalysisState


class LLMError(Exception):
    """Exception raised for errors in the LLM processing."""

    pass


class LLMProcessor:
    """
    LLM Processor for Thoth using LangGraph.

    This class provides functionality to analyze content using LLM via LangChain
    and LangGraph to manage different processing strategies based on content length.
    """

    def __init__(
        self,
        llm_service: LLMService,
        model: str,
        prompts_dir: str | Path,
        max_output_tokens: int = 500000,
        max_context_length: int = 8000,
        chunk_size: int = 4000,
        chunk_overlap: int = 200,
        model_kwargs: dict[str, Any] | None = None,
        refine_threshold_multiplier: float = 0.8,  # Threshold multiplier for choosing refine over direct
        map_reduce_threshold_multiplier: float = 2.5,  # Threshold multiplier for choosing map_reduce over refine
    ):
        """
        Initializes the LLMProcessor.

        Args:
            llm_service: The LLM service instance.
            model: The model to use for API calls (e.g., 'openai/gpt-4o-mini').
            prompts_dir: Directory containing Jinja2 prompt templates.
            max_output_tokens: Maximum output tokens for the model.
            max_context_length: Maximum context length for the model in tokens.
                                Used to determine processing strategy.
            chunk_size: Target size of chunks for document splitting in tokens.
            chunk_overlap: Overlap between chunks in tokens.
            model_kwargs: Additional keyword arguments for the model.
            refine_threshold_multiplier: Multiplier for max_context_length to choose
                'refine'.
            map_reduce_threshold_multiplier: Multiplier for max_context_length to
                choose 'map_reduce'.
        """
        self.llm_service = llm_service
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.max_context_length = max_context_length
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.prompts_dir = Path(prompts_dir) / model.split('/')[0]
        # Default prompts packaged with Thoth
        self.default_prompts_dir = (
            Path(__file__).resolve().parents[3]
            / 'templates'
            / 'prompts'
            / model.split('/')[0]
        )
        self.model_kwargs = model_kwargs if model_kwargs else {}
        self.refine_threshold = int(max_context_length * refine_threshold_multiplier)
        self.map_reduce_threshold = int(
            max_context_length * map_reduce_threshold_multiplier
        )
        model_kwargs.pop('max_tokens', None)
        self.llm = self.llm_service.get_client(
            model=self.model,
            max_tokens=self.max_output_tokens,
            **self.model_kwargs,
        )

        logger.debug(f'Refine threshold: {self.refine_threshold}')
        logger.debug(f'Map-reduce threshold: {self.map_reduce_threshold}')
        logger.debug(f'Max context length: {self.max_context_length}')
        logger.debug(f'Max output tokens: {self.max_output_tokens}')
        logger.debug(f'Chunk size: {self.chunk_size}')
        logger.debug(f'Chunk overlap: {self.chunk_overlap}')
        logger.debug(f'Model kwargs: {self.model_kwargs}')

        # Create a structured LLM that returns the AnalysisResponse format
        self.structured_llm = self.llm.with_structured_output(
            AnalysisResponse,
            include_raw=False,  # We only need the parsed object
            method='json_schema',  # Must be json_schema for openrouter
        )

        # Initialize Jinja environment with fallback to default prompts
        self.jinja_env = Environment(
            loader=ChoiceLoader(
                [
                    FileSystemLoader(self.prompts_dir),
                    FileSystemLoader(self.default_prompts_dir),
                ]
            ),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Initialize text splitter with tiktoken length function
        self.text_splitter = MarkdownTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=self._count_tokens,
        )

        # Load prompts
        self.direct_prompt = self._create_prompt_from_template('analyze_content.j2')
        self.map_prompt = self._create_prompt_from_template('analyze_section.j2')
        self.reduce_prompt = self._create_prompt_from_template('reduce_sections.j2')
        self.refine_prompt = self._create_prompt_from_template('refine_analysis.j2')

        # Build analysis chains (simple prompt | llm structure)
        self.direct_chain = self.direct_prompt | self.structured_llm
        self.map_chain = self.map_prompt | self.structured_llm
        self.reduce_chain = self.reduce_prompt | self.structured_llm
        self.refine_chain = self.refine_prompt | self.structured_llm

        # Build the LangGraph workflow
        self.app = self._build_graph()

    def _count_tokens(self, text: str) -> int:
        """Counts tokens using the initialized tiktoken encoder."""
        return len(text) // 4

    def _create_prompt_from_template(self, template_name: str) -> ChatPromptTemplate:
        """
        Create a ChatPromptTemplate from a Jinja2 template file.

        Args:
            template_name: Name of the template file (e.g., "analyze_content.j2").

        Returns:
            ChatPromptTemplate: The prompt template for use in LangChain.

        Raises:
            FileNotFoundError: If the template file doesn't exist.
        """
        template_source, _filename, _uptodate = self.jinja_env.loader.get_source(
            self.jinja_env, template_name
        )
        return ChatPromptTemplate.from_template(
            template_source, template_format='jinja2'
        )

    # --- LangGraph Nodes ---

    def _load_content(self, state: AnalysisState) -> AnalysisState:
        """Loads content from the markdown file path in the state."""
        logger.info('Loading content from markdown file...')
        markdown_path = state.get('markdown_path')

        # If markdown_path is a string, treat it as the content directly
        if isinstance(markdown_path, str):
            state['original_content'] = markdown_path
            logger.info('Using provided markdown content directly')
            return state

        # Otherwise treat as a file path
        if not markdown_path or not isinstance(markdown_path, Path):
            raise ValueError('Markdown path not found or invalid in state.')

        if not markdown_path.is_file():
            raise FileNotFoundError(f'Markdown file not found: {markdown_path}')

        content = markdown_path.read_text(encoding='utf-8')
        state['original_content'] = content
        logger.info(f'Successfully loaded content from {markdown_path}')

        return state

    def _determine_strategy(self, state: AnalysisState) -> AnalysisState:
        """Determines the processing strategy based on token count."""
        logger.info('Determining processing strategy...')
        content = state.get('original_content')  # Get content loaded by previous node
        if not content:
            raise ValueError(
                'Original content not found in state for determining strategy.'
            )

        token_count = self._count_tokens(content)
        logger.debug(f'Token count: {token_count}')
        if token_count <= self.map_reduce_threshold:
            strategy = 'direct'
        elif token_count <= self.refine_threshold:
            strategy = 'map_reduce'
        else:
            strategy = 'refine'

        logger.info(f'Selected strategy: {strategy}')
        state['strategy'] = strategy
        return state

    def _split_content(self, state: AnalysisState) -> AnalysisState:
        """Splits the content into chunks if needed."""
        logger.info('Splitting content into chunks...')
        content = state.get('original_content')
        if not content:
            raise ValueError('Original content not found in state for splitting.')
        texts = self.text_splitter.split_text(content)
        chunks = [Document(page_content=text) for text in texts]
        logger.info(f'Split content into {len(chunks)} chunks.')
        state['content_chunks'] = chunks
        return state

    def _analyze_direct(self, state: AnalysisState) -> AnalysisState:
        """Analyzes the content directly."""
        logger.info('Analyzing content directly...')
        content = state.get('original_content')
        if not content:
            raise ValueError('Original content not found in state for direct analysis.')
        logger.info(f'Analysis schema: {AnalysisResponse.model_json_schema()}')
        result = self.direct_chain.invoke(
            {
                'content': content,
                'analysis_schema': AnalysisResponse.model_json_schema(),
            }
        )
        logger.debug(f'Direct analysis result: {result}')
        state['final_analysis'] = result
        return state

    def _analyze_map_reduce(self, state: AnalysisState) -> AnalysisState:
        """Analyzes content using the map-reduce strategy."""
        logger.info('Analyzing content using map-reduce...')
        chunks = state['content_chunks']
        if not chunks:
            logger.error('Map-Reduce: No chunks to process!')
            raise LLMError('No content chunks to process in map-reduce strategy')

        # Map phase
        chunk_results = []
        logger.info(f'Map phase: Processing {len(chunks)} chunks...')
        for i, chunk in enumerate(chunks):
            logger.debug(f'Processing chunk {i + 1}/{len(chunks)}')
            # Pass only the required input 'content' to map_chain
            result = self.map_chain.invoke(
                {
                    'content': chunk.page_content,
                    'analysis_schema': AnalysisResponse.model_json_schema(),
                }
            )
            chunk_results.append(result)
            logger.debug(f'Chunk {i + 1} analysis: {result}')

        if not chunk_results:
            logger.error('Map-Reduce: Failed to process any chunks in map phase')
            raise LLMError('Failed to process any chunks in map phase')

        state['chunk_analyses'] = chunk_results
        logger.info('Map phase completed.')

        # Reduce phase
        logger.info('Reduce phase: Combining chunk analyses...')
        # Pass the list of AnalysisResponse models directly
        final_result = self.reduce_chain.invoke(
            {
                'section_analyses': chunk_results,
                'analysis_schema': AnalysisResponse.model_json_schema(),
            }
        )
        logger.debug(f'Reduce phase result: {final_result}')
        state['final_analysis'] = final_result
        logger.info('Reduce phase completed.')

        return state

    def _analyze_refine(self, state: AnalysisState) -> AnalysisState:
        """Analyzes content using the refine strategy."""
        logger.info('Analyzing content using refine...')
        chunks = state['content_chunks']
        if not chunks:
            logger.error('Refine: No chunks to process!')
            raise LLMError('No content chunks to process in refine strategy')

        logger.info(f'Refine phase: Processing {len(chunks)} chunks sequentially...')
        current_analysis: AnalysisResponse | None = None  # Initialize before loop

        for i, chunk in enumerate(chunks):
            logger.debug(f'Processing chunk {i + 1}/{len(chunks)}...')

            if i == 0:
                # Process the first chunk to get initial analysis
                logger.debug('Processing initial chunk...')
                current_analysis = self.direct_chain.invoke(
                    {
                        'content': chunk.page_content,
                        'analysis_schema': AnalysisResponse.model_json_schema(),
                    }
                )
                logger.debug(f'Initial analysis: {current_analysis}')
            else:
                # Refine with subsequent chunks
                if current_analysis is None:
                    # This should ideally not happen if the first chunk succeeded
                    logger.error(
                        'Refine error: current_analysis is None before refining chunk {i+1}.'
                    )
                    raise LLMError(
                        f'Failed to get initial analysis before refining chunk {i + 1}.'
                    )

                logger.debug(f'Refining with chunk {i + 1}...')
                # Pass the existing AnalysisResponse and the new content
                refined_analysis = self.refine_chain.invoke(
                    {
                        'existing_analysis': current_analysis.model_dump(),  # Pass as dict
                        'new_section': chunk.page_content,
                        'analysis_schema': AnalysisResponse.model_json_schema(),
                    }
                )
                current_analysis = refined_analysis  # Update for next iteration
                logger.debug(
                    f'Refined analysis after chunk {i + 1}: {current_analysis}'
                )

        if current_analysis is None:
            logger.error('Refine phase completed, but no analysis was generated.')
            raise LLMError('Refine process finished without producing a result.')

        state['final_analysis'] = current_analysis
        logger.info('Refine phase completed.')
        return state

    # --- LangGraph conditional edges ---

    def _decide_next_step(
        self, state: AnalysisState
    ) -> Literal['split_content', 'analyze_direct']:
        """Decides whether to split content or analyze directly."""
        if state['strategy'] == 'direct':
            return 'analyze_direct'
        else:
            # Both map_reduce and refine need splitting first
            return 'split_content'

    def _decide_analysis_path(
        self, state: AnalysisState
    ) -> Literal['analyze_map_reduce', 'analyze_refine']:
        """Decides which analysis path (map-reduce or refine) to take after splitting."""  # noqa: W505
        if state['strategy'] == 'map_reduce':
            return 'analyze_map_reduce'
        elif state['strategy'] == 'refine':
            return 'analyze_refine'
        else:
            # Should not happen if logic is correct, but raise error if it does
            logger.error(
                f"Invalid strategy '{state['strategy']}' at split decision point."
            )
            raise ValueError(f'Invalid strategy: {state["strategy"]}')

    # --- Build the Graph ---

    def _build_graph(self) -> Runnable:
        """Builds the LangGraph workflow."""
        workflow = StateGraph(AnalysisState)

        # Add nodes
        workflow.add_node('load_content', self._load_content)  # New node
        workflow.add_node('determine_strategy', self._determine_strategy)
        workflow.add_node('split_content', self._split_content)
        workflow.add_node('analyze_direct', self._analyze_direct)
        workflow.add_node('analyze_map_reduce', self._analyze_map_reduce)
        workflow.add_node('analyze_refine', self._analyze_refine)

        # Set entry point
        workflow.set_entry_point('load_content')  # New entry point

        # Add edge from load_content to determine_strategy
        workflow.add_edge('load_content', 'determine_strategy')

        # Add conditional edges from determine_strategy
        workflow.add_conditional_edges(
            'determine_strategy',
            self._decide_next_step,
            {
                'split_content': 'split_content',
                'analyze_direct': 'analyze_direct',
            },
        )

        workflow.add_conditional_edges(
            'split_content',
            self._decide_analysis_path,
            {
                'analyze_map_reduce': 'analyze_map_reduce',
                'analyze_refine': 'analyze_refine',
            },
        )

        # Add edges to END
        workflow.add_edge('analyze_direct', END)
        workflow.add_edge('analyze_map_reduce', END)
        workflow.add_edge('analyze_refine', END)

        # Compile the graph
        app = workflow.compile()
        logger.info('LangGraph workflow compiled.')
        logger.debug(
            f'Graph structure:\n{app.get_graph().draw_ascii()}'
        )  # Print graph structure for debugging
        return app

    def analyze_content(
        self,
        markdown_path: Path | str,  # Changed input parameter
        force_processing_strategy: (
            Literal['direct', 'map_reduce', 'refine'] | None
        ) = None,
        config: RunnableConfig | None = None,
    ) -> AnalysisResponse:
        """
        Analyze content with LLM using the LangGraph workflow.

        Args:
            markdown_path: The path to the markdown file to analyze or the markdown content directly. # Updated docstring
            force_processing_strategy: Force a specific processing strategy (overrides dynamic selection).
            config: Optional LangChain RunnableConfig for the graph invocation.

        Returns:
            AnalysisResponse: A Pydantic model containing structured analysis.

        Raises:
            LLMError: If the analysis fails at any step.
            ValueError: If an invalid forced strategy is provided or path is invalid.
            FileNotFoundError: If the markdown file does not exist.
        """  # noqa: W505
        logger.info(
            f'Starting content analysis for {markdown_path} using LangGraph workflow...'
        )

        # Construct initial state with the path
        initial_state: AnalysisState = {
            'markdown_path': markdown_path,
            'original_content': None,
            'content_chunks': None,
            'strategy': None,
            'chunk_analyses': None,
            'current_analysis': None,
            'final_analysis': None,
        }

        if force_processing_strategy:
            logger.warning(
                f'Forcing processing strategy to: {force_processing_strategy}'
            )
            if force_processing_strategy not in ['direct', 'map_reduce', 'refine']:
                raise ValueError(
                    f'Invalid forced strategy: {force_processing_strategy}'
                )

        # Invoke the graph
        final_state = self.app.invoke(initial_state, config=config)

        # Extract the final analysis from the state
        analysis_result = final_state.get('final_analysis')

        if not analysis_result:
            logger.error('Analysis finished, but no result found in the final state.')
            raise LLMError('Analysis completed without producing a result.')

        if not isinstance(analysis_result, AnalysisResponse):
            logger.error(
                f'Analysis result is not of type AnalysisResponse: {type(analysis_result)}'
            )
            raise LLMError(f'Invalid analysis result type: {type(analysis_result)}')

        logger.info('Content analysis completed successfully.')
        return analysis_result
