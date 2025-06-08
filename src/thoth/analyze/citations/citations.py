"""
Citation processor for extracting and analyzing citations from academic documents.
"""

from pathlib import Path
from typing import Any, TypedDict

from jinja2 import Environment, FileSystemLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END, StateGraph
from loguru import logger

from thoth.analyze.citations.enhancer import CitationEnhancer
from thoth.analyze.citations.extractor import ReferenceExtractor
from thoth.utilities import OpenRouterClient
from thoth.utilities.schemas import (
    Citation,
    CitationExtraction,
    CitationExtractionResponse,
)


# Define the state for the citation processor graph
class CitationState(TypedDict):
    """Represents the state of the citation processing workflow."""

    markdown_path: Path | None
    content: str | None
    document_citation: Citation | None
    headings: list[str] | None
    references_heading: str | None
    references_section: str | None
    cleaned_references_section: str | None  # New field for cleaned text
    raw_citations: list[str] | None
    citations: list[Citation] | None
    processed_citations: list[Citation] | None
    final_citations: list[Citation] | None


class CitationProcessorError(Exception):
    """Exception raised for errors in the citation processing."""

    pass


class CitationProcessor:
    """
    Orchestrates the citation extraction and enhancement workflow.
    """

    def __init__(
        self,
        model: str = 'openai/gpt-4',
        openrouter_api_key: str | None = None,
        prompts_dir: str | Path = 'templates/prompts',
        citation_batch_size: int = 10,
        model_kwargs: dict[str, Any] | None = None,
        config=None,
    ):
        """
        Initialize the CitationProcessor.
        """
        self.config = config
        self.model = model
        self.prompts_dir = Path(prompts_dir) / model.split('/')[0]
        self.model_kwargs = model_kwargs if model_kwargs else {}
        self.citation_batch_size = max(1, min(citation_batch_size, 20))

        self.llm = OpenRouterClient(
            api_key=openrouter_api_key, model=model, **self.model_kwargs
        )

        self.enhancer = CitationEnhancer(config)

        self.jinja_env = Environment(
            loader=FileSystemLoader(self.prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._init_processing_chains()

        self.app = self._build_graph()

    def _init_processing_chains(self) -> None:
        """Initialize the LangChain processing chains."""
        self.find_references_prompt = self._create_prompt_from_template(
            'identify_references_section.j2'
        )
        self.reference_extractor = ReferenceExtractor(
            self.llm, self.find_references_prompt
        )

        self.clean_references_prompt = self._create_prompt_from_template(
            'clean_references_section.j2'
        )
        self.clean_references_chain = self.clean_references_prompt | self.llm

        self.extract_citations_prompt = self._create_prompt_from_template(
            'extract_citations.j2'
        )
        self.citations_llm = self.llm.with_structured_output(
            CitationExtractionResponse, include_raw=True, method='json_schema'
        )
        self.extract_citations_chain = (
            self.extract_citations_prompt | self.citations_llm
        )

        self.extract_document_metadata_prompt = self._create_prompt_from_template(
            'extract_document_metadata.j2'
        )
        self.metadata_llm = self.llm.with_structured_output(
            CitationExtraction, include_raw=False, method='json_schema'
        )
        self.extract_document_metadata_chain = (
            self.extract_document_metadata_prompt | self.metadata_llm
        )

    def _create_prompt_from_template(self, template_name: str) -> ChatPromptTemplate:
        """Create a ChatPromptTemplate from a Jinja2 template file."""
        template_source, _, _ = self.jinja_env.loader.get_source(
            self.jinja_env, template_name
        )
        return ChatPromptTemplate.from_template(
            template=template_source, template_format='jinja2'
        )

    def _load_content(self, state: CitationState) -> CitationState:
        """Loads content from the markdown file path in the state."""
        logger.info('Loading content from markdown file...')
        markdown_path = state.get('markdown_path')
        if isinstance(markdown_path, str):
            state['content'] = markdown_path
            logger.info('Using provided markdown content directly')
            return state

        if not markdown_path or not isinstance(markdown_path, Path):
            raise ValueError('Markdown path not found or invalid in state.')

        if not markdown_path.is_file():
            raise FileNotFoundError(f'Markdown file not found: {markdown_path}')

        content = markdown_path.read_text(encoding='utf-8')
        state['content'] = content
        logger.info(f'Successfully loaded content from {markdown_path}')

        return state

    def _extract_document_citation(self, state: CitationState) -> CitationState:
        """Extract citation data for the document itself."""
        logger.debug('Extracting document citation')
        content = state['content']
        first_section = content[:1000] if len(content) > 1000 else content

        document_citation = self.extract_document_metadata_chain.invoke(
            {
                'content': first_section,
                'json_schema': CitationExtraction.model_json_schema(),
            }
        )
        document_citation = Citation.from_citation_extraction(document_citation)
        document_citation.is_document_citation = True
        state['document_citation'] = document_citation
        return state

    def _extract_references_section(self, state: CitationState) -> CitationState:
        """Extract the references section text."""
        logger.debug('Extracting references section text')
        content = state['content']
        references_section_text = self.reference_extractor.extract(content)
        state['references_section'] = references_section_text
        return state

    def _clean_references_section_text(self, state: CitationState) -> CitationState:
        """Clean the references section text using LLM for better parsing."""
        logger.debug('Cleaning references section text with LLM')
        references_section_text = state.get('references_section')

        if not references_section_text:
            logger.warning('No references section text to clean.')
            state['cleaned_references_section'] = ''
            return state

        try:
            response = self.clean_references_chain.invoke(
                {'references_section_text': references_section_text}
            )
            cleaned_text = (
                response.content if hasattr(response, 'content') else str(response)
            )
            state['cleaned_references_section'] = cleaned_text.strip()
        except Exception as e:
            logger.error(f'Error cleaning references section text with LLM: {e}')
            state['cleaned_references_section'] = references_section_text
        return state

    def _split_references_to_raw_citations(self, state: CitationState) -> CitationState:
        """Split the cleaned references section into individual citation strings."""
        logger.debug('Splitting cleaned references section into raw citations')
        references_section_to_split = state.get(
            'cleaned_references_section', state.get('references_section')
        )

        if not references_section_to_split:
            state['raw_citations'] = []
            return state

        raw_citations = [
            c.strip() for c in references_section_to_split.split('\\n') if c.strip()
        ]
        state['raw_citations'] = raw_citations
        return state

    def _extract_citations_from_raw(self, state: CitationState) -> CitationState:
        """Extract structured citations from raw citation strings."""
        logger.debug('Extracting structured citations from raw strings')
        raw_citations = state.get('raw_citations')
        if not raw_citations:
            state['citations'] = []
            return state

        all_citations = []
        for i in range(0, len(raw_citations), self.citation_batch_size):
            batch = raw_citations[i : i + self.citation_batch_size]
            self._process_citation_batch(batch, all_citations)

        processed_citations_list = [
            Citation.from_citation_extraction(c) for c in all_citations
        ]
        state['citations'] = processed_citations_list
        return state

    def _process_citation_batch(self, batch: list[str], all_citations: list):
        """Processes a batch of citations."""
        batch_text = '\\n\\n'.join(batch)
        try:
            batch_result = self.extract_citations_chain.invoke(
                {'references_section': batch_text}
            )
            parsed_output = (
                batch_result.get('parsed')
                if isinstance(batch_result, dict)
                else batch_result
            )
            if parsed_output and hasattr(parsed_output, 'citations'):
                all_citations.extend(parsed_output.citations)
        except Exception as e:
            logger.error(f'Error processing batch: {e}')

    def _enhance_citations_with_services(self, state: CitationState) -> CitationState:
        """Enhance citations with external services."""
        logger.debug('Enhancing citations with external services')
        citations_to_enhance = state.get('citations', [])
        if state.get('document_citation'):
            citations_to_enhance.insert(0, state['document_citation'])

        enhanced_citations = self.enhancer.enhance(citations_to_enhance)

        state['processed_citations'] = enhanced_citations
        return state

    def _prepare_final_citations(self, state: CitationState) -> CitationState:
        """Prepare the final list of citations for return."""
        logger.debug('Preparing final citations')
        processed_citations = state.get('processed_citations', [])
        state['final_citations'] = processed_citations
        logger.info(f'Final citation count: {len(processed_citations)}')
        return state

    def _build_graph(self) -> Runnable:
        """Build the LangGraph workflow for citation processing."""
        workflow = StateGraph(CitationState)

        workflow.add_node('load_content', self._load_content)
        workflow.add_node('extract_document_citation', self._extract_document_citation)
        workflow.add_node(
            'extract_references_section', self._extract_references_section
        )
        workflow.add_node(
            'clean_references_section_text', self._clean_references_section_text
        )
        workflow.add_node(
            'split_references_to_raw_citations', self._split_references_to_raw_citations
        )
        workflow.add_node(
            'extract_citations_from_raw', self._extract_citations_from_raw
        )
        workflow.add_node(
            'enhance_citations_with_services', self._enhance_citations_with_services
        )
        workflow.add_node('prepare_final_citations', self._prepare_final_citations)

        workflow.set_entry_point('load_content')

        workflow.add_edge('load_content', 'extract_document_citation')
        workflow.add_edge('extract_document_citation', 'extract_references_section')
        workflow.add_edge('extract_references_section', 'clean_references_section_text')
        workflow.add_edge(
            'clean_references_section_text', 'split_references_to_raw_citations'
        )
        workflow.add_edge(
            'split_references_to_raw_citations', 'extract_citations_from_raw'
        )
        workflow.add_edge(
            'extract_citations_from_raw', 'enhance_citations_with_services'
        )
        workflow.add_edge('enhance_citations_with_services', 'prepare_final_citations')
        workflow.add_edge('prepare_final_citations', END)

        return workflow.compile()

    def process_document(
        self, markdown_path: Path | str, config: RunnableConfig | None = None
    ) -> list[Citation]:
        """Process a document to extract and enhance citations."""
        logger.info(f'Starting citation processing for {markdown_path}')
        if not markdown_path:
            raise ValueError('No markdown path provided for processing')

        initial_state = {'markdown_path': markdown_path}
        final_state = self.app.invoke(initial_state, config=config)

        citations_result = final_state.get('final_citations')
        if not citations_result:
            raise CitationProcessorError(
                'Citation processing completed without producing results'
            )

        return citations_result
