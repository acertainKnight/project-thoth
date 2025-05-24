"""
Citation processor for extracting and analyzing citations from academic documents.
"""

import re
from pathlib import Path
from typing import Any, TypedDict

from jinja2 import Environment, FileSystemLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END, StateGraph
from loguru import logger
from pydantic import ValidationError

from thoth.analyze.citations.arxivcitation import ArxivClient
from thoth.analyze.citations.opencitation import OpenCitationsAPI
from thoth.analyze.citations.scholarly import ScholarlyAPI
from thoth.analyze.citations.semanticscholar import SemanticScholarAPI
from thoth.utilities.models import (
    Citation,
    CitationExtraction,
    CitationExtractionResponse,
    ReferencesSection,
)
from thoth.utilities.openrouter import OpenRouterClient


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
    Citation processor for extracting and analyzing citations from academic documents.

    This class provides functionality to:
    1. Identify and extract references sections from documents
    2. Clean the references section using an LLM to ensure one citation per line
    3. Extract structured citations from text
    4. Enhance citations with missing information using LLM and OpenCitations API
    5. Use web search as a fallback when OpenCitations doesn't have required information

    The processing follows a LangGraph workflow with distinct nodes and edges.
    """

    def __init__(
        self,
        model: str = 'openai/gpt-4',  # Using GPT-4 as citations require high accuracy
        openrouter_api_key: str | None = None,
        prompts_dir: str | Path = 'templates/prompts',
        opencitations_token: str | None = None,
        semanticscholar_api_key: str | None = None,
        use_semanticscholar: bool | None = None,
        use_opencitations: bool | None = None,
        use_scholarly: bool | None = None,
        use_arxiv: bool | None = None,
        citation_batch_size: int = 1,  # Added batch size parameter
        model_kwargs: dict[str, Any] | None = None,
    ):
        """
        Initialize the CitationProcessor.

        Args:
            model: The model to use for API calls.
            openrouter_api_key: The OpenRouter API key (optional, will use env var if not provided).
            prompts_dir: Directory containing Jinja2 prompt templates.
            opencitations_token: OpenCitations API token for enhanced lookups.
            semanticscholar_api_key: Semantic Scholar API key for higher rate limits.
            use_semanticscholar: Whether to use Semantic Scholar API for enhancement.
            use_opencitations: Whether to use OpenCitations API for enhancement.
            use_scholarly: Whether to use Scholarly for Google Scholar search.
            use_arxiv: Whether to use arXiv API for enhancement.
            citation_batch_size: Number of potential citations to process in each LLM call.
            model_kwargs: Additional keyword arguments for the model.
        """  # noqa: W505
        logger.debug(
            f'CITATIONPROCESSOR __init__: Received use_scholarly parameter = {use_scholarly}'
        )

        self.model = model
        self.prompts_dir = Path(prompts_dir)
        self.model_kwargs = model_kwargs if model_kwargs else {}
        self.citation_batch_size = citation_batch_size  # Store batch size

        # Use configuration values if not explicitly provided
        self.use_semanticscholar = (
            use_semanticscholar if use_semanticscholar is not None else True
        )
        self.use_opencitations = (
            use_opencitations if use_opencitations is not None else False
        )
        self.use_scholarly = (
            use_scholarly if use_scholarly is not None else False
        )  # Default to False if not provided
        logger.debug(
            f'CITATIONPROCESSOR __init__: self.use_scholarly is set to = {self.use_scholarly}'
        )
        self.use_arxiv = use_arxiv if use_arxiv is not None else False

        # Get API keys from configuration if not explicitly provided
        self.opencitations_token = opencitations_token or None
        self.semanticscholar_api_key = semanticscholar_api_key or None

        # Initialize the LLM
        self.llm = OpenRouterClient(
            api_key=openrouter_api_key,
            model=model,
            **self.model_kwargs,
        )

        # Initialize Semantic Scholar tool if enabled
        if self.use_semanticscholar:
            self.semanticscholar_tool = SemanticScholarAPI(
                api_key=self.semanticscholar_api_key,
            )
        else:
            self.semanticscholar_tool = None

        # Initialize OpenCitations tool if enabled
        if self.use_opencitations and self.opencitations_token:
            self.opencitations_tool = OpenCitationsAPI(
                access_token=self.opencitations_token,
            )
        elif self.use_opencitations:
            logger.warning(
                'OpenCitations is enabled but token is missing. OpenCitations functionality will be disabled.'
            )
            self.use_opencitations = False
            self.opencitations_tool = None
        else:
            self.opencitations_tool = None

        # Initialize web search if enabled
        if self.use_scholarly:
            logger.info('Scholarly lookup enabled via configuration.')
            self.scholarly_tool = ScholarlyAPI()
        else:
            logger.info('Scholarly lookup disabled via configuration.')
            self.scholarly_tool = None

        # Initialize arXiv client if enabled
        if self.use_arxiv:
            self.arxiv_tool = ArxivClient()
        else:
            self.arxiv_tool = None

        # Create structured LLMs for different outputs
        logger.debug(
            'Creating structured LLMs for different outputs with include_raw=True'
        )
        self.references_llm = self.llm.with_structured_output(
            ReferencesSection,
            include_raw=False,
            method='json_schema',  # Use json_schema for structured output
        )
        logger.debug(f'References LLM created with model: {self.model}')

        self.extract_citation_single_llm = self.llm.with_structured_output(
            CitationExtraction,
            include_raw=False,
            method='json_schema',  # Use json_schema for structured output
        )
        logger.debug(f'Extract citation single LLM created with model: {self.model}')

        self.citations_llm = self.llm.with_structured_output(
            CitationExtractionResponse,
            include_raw=True,
            method='json_schema',  # Use json_schema for structured output
        )
        logger.debug(f'Citations LLM created with model: {self.model}')
        logger.debug(
            f'CitationExtractionResponse schema: {CitationExtractionResponse.model_json_schema()}'
        )

        self.metadata_llm = self.llm.with_structured_output(
            CitationExtraction,
            include_raw=False,
            method='json_schema',
        )
        logger.debug(f'Enrich LLM created with model: {self.model}')

        # Initialize Jinja environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.prompts_dir),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Initialize processing chains
        self._init_processing_chains()

        # Build the LangGraph workflow
        self.app = self._build_graph()

    def _create_prompt_from_template(self, template_name: str) -> ChatPromptTemplate:
        """
        Create a ChatPromptTemplate from a Jinja2 template file.

        Args:
            template_name: Name of the template file (with extension)

        Returns:
            ChatPromptTemplate: The prompt template for use in LangChain

        Raises:
            FileNotFoundError: If the template file doesn't exist
        """
        logger.debug(f'Creating prompt from template: {template_name}')
        logger.debug(f'Template directory: {self.prompts_dir}')

        # Get the template using the already initialized Jinja environment
        template_content = self.jinja_env.loader.get_source(
            self.jinja_env, template_name
        )[0]
        logger.debug(f'Template loaded successfully: {template_name}')

        # Create a ChatPromptTemplate with jinja2 template format
        prompt_template = ChatPromptTemplate.from_template(
            template=template_content,  # Pass raw template string
            template_format='jinja2',
        )
        logger.debug(f'ChatPromptTemplate created successfully from {template_name}')

        return prompt_template

    def _init_processing_chains(self) -> None:
        """Initialize the LangChain processing chains for citation extraction."""
        logger.debug('Initializing processing chains')

        # References section identification chain
        logger.debug('Setting up references section identification chain')
        self.find_references_prompt = self._create_prompt_from_template(
            'identify_references_section.j2'
        )
        self.find_references_chain = self.find_references_prompt | self.references_llm
        logger.debug('References section identification chain initialized')

        # References section cleaning chain
        logger.debug('Setting up references section cleaning chain')
        self.clean_references_prompt = self._create_prompt_from_template(
            'clean_references_section.j2'
        )
        self.clean_references_chain = (
            self.clean_references_prompt | self.llm
        )  # Use the base LLM
        logger.debug('References section cleaning chain initialized')

        # Citation extraction chain with cleaning
        logger.debug('Setting up citation extraction chain')
        self.extract_citation_single_prompt = self._create_prompt_from_template(
            'extract_citations_single.j2'
        )
        self.extract_citations_prompt = self._create_prompt_from_template(
            'extract_citations.j2'
        )

        # Use the structured LLM directly, which includes parsing
        self.extract_citation_single_chain = (
            self.extract_citation_single_prompt | self.extract_citation_single_llm
        )
        self.extract_citations_chain = (
            self.extract_citations_prompt | self.citations_llm
        )
        logger.debug('Citation extraction chain initialized (using structured LLM)')

        # Set up metadata extraction chain
        logger.debug('Setting up metadata extraction chain')
        self.extract_document_metadata_prompt = self._create_prompt_from_template(
            'extract_document_metadata.j2'
        )
        self.extract_document_metadata_chain = (
            self.extract_document_metadata_prompt | self.metadata_llm
        )
        logger.debug('Metadata extraction chain initialized')

        logger.debug('All processing chains initialized successfully')

    # --- LangGraph Nodes ---

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

        # Get the first 1000 characters for metadata extraction
        first_section = content[:1000] if len(content) > 1000 else content
        logger.debug(
            f'Extracted first {len(first_section)} characters for metadata extraction'
        )

        # Run the extraction chain
        document_citation = self.extract_document_metadata_chain.invoke(
            {
                'content': first_section,
                'json_schema': CitationExtraction.model_json_schema(),
            }
        )
        document_citation = Citation.from_citation_extraction(document_citation)
        document_citation.is_document_citation = True
        logger.debug(f'Document citation extracted: {document_citation}')

        state['document_citation'] = document_citation
        return state

    def _get_section_headings(self, state: CitationState) -> CitationState:
        """Extract all section headings from the content."""
        logger.debug('Extracting section headings')
        content = state['content']

        # Find all ATX style headers (# Header)
        atx_headers = re.findall(r'^(#{1,6})\s+(.+?)(?:\s+#+)?$', content, re.MULTILINE)
        atx_heading_texts = [text.strip() for _, text in atx_headers]

        # Find all Setext style headers (Header\n===== or Header\n-----)
        setext_headers = re.findall(r'^([^\n]+)\n([=\-]+)$', content, re.MULTILINE)
        setext_heading_texts = [text.strip() for text, _ in setext_headers]

        # Combine all headings
        all_headings = atx_heading_texts + setext_heading_texts
        logger.debug(f'Found {len(all_headings)} headings')

        state['headings'] = all_headings
        return state

    def _identify_references_heading(self, state: CitationState) -> CitationState:
        """Identify the heading for the references section."""
        logger.debug('Identifying references section heading')
        headings = state['headings']

        # First try with common patterns
        default_options = ['references', 'bibliography', 'citations']
        for heading in headings:
            if any(option in heading.lower() for option in default_options):
                logger.debug(
                    f'Found references section heading using default options: {heading}'
                )
                state['references_heading'] = heading
                return state

        # If no default options found, use LLM
        logger.debug('No default references heading found, using LLM')
        result = self.find_references_chain.invoke(
            {'headings': headings, 'json_schema': ReferencesSection.model_json_schema()}
        )
        if isinstance(result, dict) and 'parsed' in result:
            # Handle include_raw=True wrapper
            parsed_result = result['parsed']
            state['references_heading'] = parsed_result.heading
        else:
            state['references_heading'] = result.heading

        logger.debug(
            f'LLM identified references heading: {state["references_heading"]}'
        )
        return state

    def _extract_references_section(self, state: CitationState) -> CitationState:
        """Extract the references section text using the identified heading."""
        logger.debug('Extracting references section text')
        content = state['content']
        heading = state['references_heading']

        if not heading:
            logger.warning('No references section heading found')
            state['references_section'] = ''
            return state

        # Find all headings with their positions
        heading_positions = []

        # ATX style headers
        for match in re.finditer(
            r'^(#{1,6})\s+(.+?)(?:\s+#+)?$', content, re.MULTILINE
        ):
            level = len(match.group(1))
            text = match.group(2).strip()
            heading_positions.append((match.start(), text, level))

        # Setext style headers
        for match in re.finditer(r'^([^\n]+)\n([=\-]+)$', content, re.MULTILINE):
            text = match.group(1).strip()
            level = 1 if match.group(2).startswith('=') else 2
            heading_positions.append((match.start(), text, level))

        # Sort by position
        heading_positions.sort()

        # Find the target heading position
        target_pos = -1
        next_pos = len(content)

        for i, (pos, text, _) in enumerate(heading_positions):
            if text == heading:
                target_pos = pos
                # Find the next heading's position
                if i < len(heading_positions) - 1:
                    next_pos = heading_positions[i + 1][0]
                break

        if target_pos == -1:
            logger.warning(f"References heading '{heading}' not located in document")
            state['references_section'] = ''
            return state

        # Extract the section content
        heading_end = content.find('\n', target_pos)
        if heading_end == -1:
            heading_end = len(content)

        # Extract text between current heading and next heading
        section_text = content[heading_end + 1 : next_pos].strip()
        logger.debug(
            f'Extracted references section with {len(section_text)} characters'
        )

        state['references_section'] = section_text
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
            # Assuming the LLM directly returns the cleaned string or an AIMessage with content  # noqa: W505
            cleaned_text = (
                response.content if hasattr(response, 'content') else str(response)
            )
            state['cleaned_references_section'] = cleaned_text.strip()
            logger.info(
                f'Successfully cleaned references section. Original length: {len(references_section_text)}, Cleaned length: {len(cleaned_text)}'
            )
        except Exception as e:
            logger.error(f'Error cleaning references section text with LLM: {e}')
            logger.warning(
                'Falling back to using the original references section text.'
            )
            state['cleaned_references_section'] = references_section_text  # Fallback

        return state

    def _split_references_to_raw_citations(self, state: CitationState) -> CitationState:
        """Split the cleaned references section into individual citation strings."""
        logger.debug('Splitting cleaned references section into raw citations')
        # Use the cleaned references section if available, otherwise fall back to original  # noqa: W505
        references_section_to_split = state.get(
            'cleaned_references_section', state.get('references_section')
        )

        if not references_section_to_split:
            logger.warning('No references section (cleaned or original) to split')
            state['raw_citations'] = []
            return state

        # Split based on newlines, as the LLM should have formatted each citation on its own line  # noqa: W505
        raw_citations = references_section_to_split.split('\n')

        # Clean up empty strings and whitespace
        raw_citations = [c.strip() for c in raw_citations if c.strip()]
        logger.debug(
            f'Split cleaned references section into {len(raw_citations)} potential citation strings'
        )

        state['raw_citations'] = raw_citations
        return state

    def _extract_citations_from_raw(self, state: CitationState) -> CitationState:
        """Extract structured citations from raw citation strings using LLM."""
        logger.debug('Extracting structured citations from raw strings')
        raw_citations = state['raw_citations']

        if not raw_citations:
            logger.warning('No raw citations to process')
            state['citations'] = []
            return state

        all_citations = []

        # Process in batches
        for i in range(0, len(raw_citations), self.citation_batch_size):
            batch = raw_citations[i : i + self.citation_batch_size]
            batch_text = '\n\n'.join(batch)
            batch_num = (i // self.citation_batch_size) + 1

            logger.debug(f'Processing batch {batch_num} with {len(batch)} citations')
            logger.debug(f'Batch text: {batch_text}')

            successful_extraction = False
            # Retry logic: 1 initial attempt + 1 retry
            for attempt in range(2):  # 0 for initial, 1 for retry
                try:
                    if self.citation_batch_size == 1:
                        batch_result = self.extract_citation_single_chain.invoke(
                            {
                                'citation': batch_text,
                                'json_schema': CitationExtraction.model_json_schema(),
                            }
                        )
                        all_citations.append(batch_result)
                        successful_extraction = True
                        break  # Success, exit retry loop
                    else:
                        batch_invoke_result = self.extract_citations_chain.invoke(
                            {
                                'references_section': batch_text,
                                'response_schema': CitationExtractionResponse.model_json_schema(),
                                'item_schema': CitationExtraction.model_json_schema(),
                            }
                        )
                        logger.debug(
                            f'LLM invocation result for batch {batch_num}, attempt {attempt + 1}: {batch_invoke_result}'
                        )

                        parsed_output = batch_invoke_result.get('parsed')

                        if parsed_output and hasattr(parsed_output, 'citations'):
                            try:
                                all_citations.extend(parsed_output.citations)
                                logger.debug(
                                    f'Successfully extracted {len(parsed_output.citations)} citations from batch {batch_num}, attempt {attempt + 1}'
                                )
                                successful_extraction = True
                                break  # Success, exit retry loop
                            except ValidationError as ve:
                                logger.error(
                                    f'Validation error processing parsed citations for batch {batch_num}, attempt {attempt + 1}: {ve}'
                                )
                                logger.error(
                                    f'Problematic parsed output for batch {batch_num}, attempt {attempt + 1}:\n{parsed_output}'
                                )
                                # Fall through to retry or final error log
                            except Exception as e:  # General exception handler
                                logger.error(
                                    f'Unexpected error processing parsed citations for batch {batch_num}, attempt {attempt + 1}: {e}'
                                )
                                logger.error(
                                    f'Problematic parsed output for batch {batch_num}, attempt {attempt + 1}:\n{parsed_output}'
                                )
                                # Fall through to retry or final error log
                        else:
                            logger.error(
                                f"Failed to parse citation extraction output or 'citations' attribute missing for batch {batch_num}, attempt {attempt + 1}."
                            )
                            raw_output = batch_invoke_result.get(
                                'raw', 'Raw output not available.'
                            )
                            logger.error(
                                f'Raw LLM output for failing batch {batch_num}, attempt {attempt + 1}: {raw_output}'
                            )
                            # Fall through to retry or final error log
                except ValidationError as ve:
                    logger.error(
                        f'Validation error during single citation extraction for batch {batch_num}, attempt {attempt + 1}: {ve}'
                    )
                    logger.error(
                        f'Problematic batch text for single extraction, batch {batch_num}, attempt {attempt + 1}:\n{batch_text}'
                    )
                    # Fall through to retry or final error log
                except Exception as e:
                    logger.error(
                        f'Exception during citation extraction for batch {batch_num}, attempt {attempt + 1}: {e}'
                    )
                    logger.error(
                        f'Problematic batch text for batch {batch_num}, attempt {attempt + 1}:\n{batch_text}'
                    )
                    # Fall through to retry or final error log

                # If an error occurred and this was the first attempt, log retry
                if not successful_extraction and attempt == 0:
                    logger.warning(f'Retrying batch {batch_num} (attempt 2 of 2)...')

            # After both attempts, if still not successful, log skipping the batch
            if not successful_extraction:
                logger.error(
                    f'Both attempts failed for batch {batch_num}. Skipping this batch.'
                )

        logger.info(f'Extracted a total of {len(all_citations)} raw citation objects')

        processed_citations_list = []
        for idx, citation_data in enumerate(all_citations):
            try:
                processed_citations_list.append(
                    Citation.from_citation_extraction(citation_data)
                )
            except ValidationError as ve:
                logger.error(
                    f'Validation error converting CitationExtraction to Citation for item {idx}: {ve}'
                )
                logger.error(f'Problematic citation data: {citation_data}')
            except Exception as e:
                logger.error(
                    f'Unexpected error converting CitationExtraction to Citation for item {idx}: {e}'
                )
                logger.error(f'Problematic citation data: {citation_data}')

        state['citations'] = processed_citations_list
        logger.info(
            f'Successfully converted {len(processed_citations_list)} citations to Citation model.'
        )
        return state

    def _enhance_citations_with_services(self, state: CitationState) -> CitationState:
        """Enhance citations with external services if enabled."""
        logger.debug('Enhancing citations with external services')

        document_citation = state.get('document_citation')
        reference_citations = state.get('citations', [])  # Renamed for clarity

        if not document_citation and not reference_citations:
            logger.warning('No citations to enhance')
            state['processed_citations'] = []
            return state

        all_processed_citations = []

        # Process document citation if available
        if document_citation:
            logger.info(
                f'Enhancing document citation: {document_citation.title or "N/A"}'
            )
            # Put document_citation in a list to use the lookup helpers
            temp_doc_citation_list = [document_citation]
            enhanced_doc_citation = None

            has_identifier, has_missing_fields = self._check_citation(document_citation)

            if (
                self.use_semanticscholar
                and self.semanticscholar_tool
                and has_missing_fields
            ):
                logger.debug(
                    'Attempting Semantic Scholar lookup for document citation.'
                )
                temp_doc_citation_list = self._semantic_scholar_lookup(
                    temp_doc_citation_list
                )

            # Re-check after Semantic Scholar
            # Ensure we take the first element as _semantic_scholar_lookup returns a list  # noqa: W505
            current_doc_cit = (
                temp_doc_citation_list[0]
                if temp_doc_citation_list
                else document_citation
            )
            has_identifier, has_missing_fields = self._check_citation(current_doc_cit)

            if (
                has_identifier
                and has_missing_fields
                and self.use_opencitations
                and self.opencitations_tool
            ):
                logger.debug('Attempting OpenCitations lookup for document citation.')
                temp_doc_citation_list = self._opencitations_lookup(
                    [current_doc_cit]
                )  # Pass the potentially updated citation

            current_doc_cit = (
                temp_doc_citation_list[0] if temp_doc_citation_list else current_doc_cit
            )
            has_identifier, has_missing_fields = self._check_citation(current_doc_cit)

            if (
                self.use_arxiv
                and self.arxiv_tool
                and (not has_identifier or has_missing_fields)
            ):
                # Assuming _arxiv_lookup takes a list and returns a list, similar to others  # noqa: W505
                # And that it can handle cases where arxiv_id might be missing or found via title  # noqa: W505
                logger.debug('Attempting arXiv lookup for document citation.')
                temp_doc_citation_list = self._arxiv_lookup([current_doc_cit])

            current_doc_cit = (
                temp_doc_citation_list[0] if temp_doc_citation_list else current_doc_cit
            )
            has_identifier, has_missing_fields = self._check_citation(current_doc_cit)

            if (
                self.use_scholarly
                and self.scholarly_tool
                and (not has_identifier or has_missing_fields)
            ):
                logger.debug('Attempting Scholarly lookup for document citation.')
                temp_doc_citation_list = self._scholarly_lookup([current_doc_cit])

            enhanced_doc_citation = (
                temp_doc_citation_list[0]
                if temp_doc_citation_list
                else document_citation
            )

            if enhanced_doc_citation:
                enhanced_doc_citation.is_document_citation = (
                    True  # Ensure flag is maintained
                )
                all_processed_citations.append(enhanced_doc_citation)
                logger.info(
                    f'Finished enhancing document citation. Title: {enhanced_doc_citation.title}, DOI: {enhanced_doc_citation.doi}'
                )
            else:
                logger.warning(
                    'Document citation enhancement resulted in None, keeping original.'
                )
                document_citation.is_document_citation = True
                all_processed_citations.append(
                    document_citation
                )  # Fallback to original

        # Process reference citations (similar logic as before, but separated)
        processed_reference_citations = []
        if reference_citations:
            logger.info(f'Enhancing {len(reference_citations)} reference citations.')
            citations_to_process_further = []

            # First pass with Semantic Scholar if enabled
            if self.use_semanticscholar and self.semanticscholar_tool:
                logger.debug('Processing reference citations with Semantic Scholar.')
                # Filter citations that need enhancement
                needing_enhancement_s2 = [
                    c for c in reference_citations if self._check_citation(c)[1]
                ]
                others_s2 = [
                    c for c in reference_citations if not self._check_citation(c)[1]
                ]

                enhanced_by_s2 = self._semantic_scholar_lookup(needing_enhancement_s2)
                processed_reference_citations.extend(
                    others_s2
                )  # Add those not needing s2 lookup
                citations_to_process_further.extend(enhanced_by_s2)
            else:
                citations_to_process_further.extend(reference_citations)

            # Second pass with OpenCitations, arXiv, Scholarly for remaining/partially enhanced  # noqa: W505
            final_reference_citations = []
            for citation in citations_to_process_further:
                has_identifier, has_missing_fields = self._check_citation(citation)
                temp_cit_list = [citation]

                if (
                    has_identifier
                    and has_missing_fields
                    and self.use_opencitations
                    and self.opencitations_tool
                ):
                    logger.debug(
                        f'Attempting OpenCitations for ref: {citation.title or "N/A"}'
                    )
                    temp_cit_list = self._opencitations_lookup(temp_cit_list)

                current_ref_cit = temp_cit_list[0] if temp_cit_list else citation
                has_identifier, has_missing_fields = self._check_citation(
                    current_ref_cit
                )

                if (
                    self.use_arxiv
                    and self.arxiv_tool
                    and (not has_identifier or has_missing_fields)
                ):
                    logger.debug(
                        f'Attempting arXiv for ref: {current_ref_cit.title or "N/A"}'
                    )
                    temp_cit_list = self._arxiv_lookup([current_ref_cit])

                current_ref_cit = temp_cit_list[0] if temp_cit_list else current_ref_cit
                has_identifier, has_missing_fields = self._check_citation(
                    current_ref_cit
                )

                if (
                    self.use_scholarly
                    and self.scholarly_tool
                    and (not has_identifier or has_missing_fields)
                ):
                    logger.debug(
                        f'Attempting Scholarly for ref: {current_ref_cit.title or "N/A"}'
                    )
                    temp_cit_list = self._scholarly_lookup([current_ref_cit])

                final_reference_citations.append(
                    temp_cit_list[0] if temp_cit_list else current_ref_cit
                )

            processed_reference_citations.extend(final_reference_citations)

        all_processed_citations.extend(processed_reference_citations)

        logger.info(
            f'Total enhanced citations (doc + refs): {len(all_processed_citations)}'
        )
        state['processed_citations'] = all_processed_citations
        return state

    def _prepare_final_citations(self, state: CitationState) -> CitationState:
        """Prepare the final list of citations for return."""
        logger.debug('Preparing final citations')

        processed_citations = state.get('processed_citations', [])
        state['final_citations'] = processed_citations
        logger.info(f'Final citation count: {len(processed_citations)}')

        return state

    # --- Helper methods ---

    def _check_citation(self, citation: Citation) -> tuple[bool, bool]:
        """
        Check if a citation has a DOI or backup ID and if it has any missing attributes.

        Args:
            citation: The citation to check.

        Returns:
            tuple[bool, bool]: A tuple containing:
                - bool: True if the citation has a DOI or backup ID, False otherwise.
                - bool: True if the citation has any missing attributes, False otherwise.
        """  # noqa: W505
        # Check if DOI or backup_id exists
        has_identifier = (citation.doi is not None and citation.doi != '') or (
            citation.backup_id is not None and citation.backup_id != ''
        )

        # Check for any missing fields (all fields in the Citation model)
        has_missing_fields = any(
            getattr(citation, field) is None for field in citation.model_fields.keys()
        )

        return has_identifier, has_missing_fields

    def _opencitations_lookup(self, citations: list[Citation]) -> list[Citation]:
        """
        Lookup citations in OpenCitations.

        Args:
            citations: The citations to lookup.

        Returns:
            list[Citation]: The citations with the missing information.
        """
        if not self.opencitations_tool:
            return citations

        # Create lookup IDs prioritizing DOI but using backup_id if DOI is unavailable
        ids = []
        for citation in citations:
            if citation.doi:
                ids.append(f'doi:{citation.doi}')
            elif citation.backup_id:
                ids.append(
                    citation.backup_id
                )  # Assume backup_id is already formatted with prefix (e.g., arxiv:1234.5678)

        if not ids:
            return citations

        # Use synchronous method directly
        opencitations = self.opencitations_tool.lookup_metadata_sync(ids)

        for citation in citations:
            for opencitation in opencitations:
                # Match by DOI if available
                if citation.doi and opencitation.id == f'doi:{citation.doi}':
                    citation.update_from_opencitation(opencitation)
                # Match by backup_id if DOI not available
                elif (
                    not citation.doi
                    and citation.backup_id
                    and opencitation.id == citation.backup_id
                ):
                    citation.update_from_opencitation(opencitation)

        return citations

    def _scholarly_lookup(self, citations: list[Citation]) -> list[Citation]:
        """
        Lookup citations using web search to find missing DOI numbers and PDF URLs.
        Also attempts to find alternative identifiers like arXiv IDs when DOI is unavailable.

        Args:
            citations: The citations to lookup.

        Returns:
            list[Citation]: The citations with the missing information.
        """  # noqa: W505
        if not self.scholarly_tool:
            return citations

        for citation in citations:
            # Find missing DOI if needed
            if not citation.doi:
                doi = self.scholarly_tool.find_doi_sync(citation)
                if doi:
                    citation.doi = doi
                    logger.info(f'Found DOI for citation: {doi}')
                else:
                    # If DOI not found, attempt to find alternative identifier
                    backup_id = self.scholarly_tool.find_alternative_id_sync(citation)
                    if backup_id:
                        citation.backup_id = backup_id
                        logger.info(f'Found alternative ID for citation: {backup_id}')

            # Find PDF URL if needed
            if not citation.url:
                pdf_url = self.scholarly_tool.find_pdf_url_sync(citation)
                if pdf_url:
                    citation.url = pdf_url
                    logger.info(f'Found PDF URL for citation: {pdf_url}')

            # If we found a DOI or backup_id, try to get more information from OpenCitations  # noqa: W505
            if self.use_opencitations and self.opencitations_tool:
                if citation.doi:
                    opencitations = self.opencitations_tool.lookup_metadata_sync(
                        [f'doi:{citation.doi}']
                    )
                    for opencitation in opencitations:
                        if opencitation.id == f'doi:{citation.doi}':
                            citation.update_from_opencitation(opencitation)
                            break
                elif citation.backup_id and not citation.backup_id.startswith('arxiv:'):
                    opencitations = self.opencitations_tool.lookup_metadata_sync(
                        [citation.backup_id]
                    )
                    for opencitation in opencitations:
                        if opencitation.id == citation.backup_id:
                            citation.update_from_opencitation(opencitation)
                            break

            # If we found an arXiv ID as backup_id, use ArxivClient to get more information  # noqa: W505
            if (
                self.use_arxiv
                and self.arxiv_tool
                and citation.backup_id
                and citation.backup_id.startswith('arxiv:')
            ):
                # Extract the actual arXiv ID from the backup_id
                arxiv_id = citation.backup_id.split(':', 1)[1]
                # Get the paper by ID
                arxiv_citation = self.arxiv_tool.get_by_id(arxiv_id)[0]
                if arxiv_citation.id == arxiv_id:
                    citation.update_from_arxiv(arxiv_citation)

        return citations

    def _semantic_scholar_lookup(self, citations: list[Citation]) -> list[Citation]:
        """
        Lookup citations in Semantic Scholar.

        Args:
            citations: The citations to lookup.

        Returns:
            list[Citation]: The citations with the missing information.
        """
        if not self.semanticscholar_tool:
            return citations

        logger.debug(f'Looking up {len(citations)} citations in Semantic Scholar')
        enhanced_citations = self.semanticscholar_tool.semantic_scholar_lookup(
            citations
        )
        logger.debug(
            f'Enhanced {len(enhanced_citations)} citations with Semantic Scholar'
        )

        return enhanced_citations

    def _arxiv_lookup(self, citations: list[Citation]) -> list[Citation]:
        """
        Lookup citations in arXiv.

        Args:
            citations: The citations to lookup.

        Returns:
            list[Citation]: The citations with the missing information.
        """
        if not self.arxiv_tool:
            return citations
        logger.debug(f'Looking up {len(citations)} citations in arXiv')
        # This assumes ArxivClient has a method similar to semantic_scholar_lookup
        # or we adapt the logic from _scholarly_lookup for arXiv specific searches.
        # For now, let's assume a direct lookup method exists or needs to be implemented in ArxivClient.  # noqa: W505

        # Placeholder: Actual implementation would involve ArxivClient calls
        # similar to how _semantic_scholar_lookup or _scholarly_lookup work,
        # potentially searching by title if backup_id (arxiv_id) is not present.
        enhanced_citations = []
        for citation in citations:
            # Attempt to get by arXiv ID if backup_id is an arXiv ID
            if citation.backup_id and citation.backup_id.startswith('arxiv:'):
                arxiv_id = citation.backup_id.split(':', 1)[1]
                try:
                    arxiv_papers = self.arxiv_tool.get_by_id(arxiv_id)
                    if arxiv_papers:
                        citation.update_from_arxiv(arxiv_papers[0])
                        logger.info(
                            f'Enhanced citation from arXiv (ID: {arxiv_id}): {citation.title}'
                        )
                except Exception as e:
                    logger.warning(f'Error looking up arXiv ID {arxiv_id}: {e}')
            # Fallback: if no arXiv ID, and title exists, try searching arXiv by title
            # This part of ArxivClient might need a `search_by_title` like method.
            # For now, this is a conceptual addition.
            # elif citation.title and not citation.doi: # Only search if no DOI and has title  # noqa: W505
            #     try:
            #         # This assumes ArxivClient is updated to have a search method that can take a title  # noqa: W505
            #         # and return ArxivPaper objects, and then we update the citation.
            #         # search_results = self.arxiv_tool.search(query=f'ti:"{citation.title}"', max_results=1)  # noqa: W505
            #         # if search_results:
            #         #     citation.update_from_arxiv(search_results[0])
            #         #     logger.info(f"Enhanced citation from arXiv (title search): {citation.title}")  # noqa: W505
            #        pass # Placeholder for title search logic in ArxivClient
            enhanced_citations.append(citation)

        logger.debug(f'Enhanced {len(enhanced_citations)} citations with arXiv')
        return enhanced_citations

    # --- Build the Graph ---

    def _build_graph(self) -> Runnable:
        """Build the LangGraph workflow for citation processing."""
        workflow = StateGraph(CitationState)

        # Add nodes
        workflow.add_node('load_content', self._load_content)
        workflow.add_node('extract_document_citation', self._extract_document_citation)
        workflow.add_node('get_section_headings', self._get_section_headings)
        workflow.add_node(
            'identify_references_heading', self._identify_references_heading
        )
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

        # Set entry point
        workflow.set_entry_point('load_content')

        # Define the linear flow
        workflow.add_edge('load_content', 'extract_document_citation')
        workflow.add_edge('extract_document_citation', 'get_section_headings')
        workflow.add_edge('get_section_headings', 'identify_references_heading')
        workflow.add_edge('identify_references_heading', 'extract_references_section')
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

        # Add edge to END
        workflow.add_edge('prepare_final_citations', END)

        # Compile the graph
        app = workflow.compile()
        logger.info('Citation processing workflow compiled')
        logger.debug(f'Graph structure:\n{app.get_graph().draw_ascii()}')
        return app

    def process_document(
        self,
        markdown_path: Path | str,
        config: RunnableConfig | None = None,
    ) -> list[Citation]:
        """
        Process a document to extract and enhance citations.

        Args:
            markdown_path: The path to the markdown file to process or the markdown content directly.
            config: Optional LangChain RunnableConfig for the graph invocation.

        Returns:
            list[Citation]: The extracted and enhanced citations with document citation marked.

        Raises:
            ValueError: If no path is provided.
            FileNotFoundError: If the markdown file does not exist.
            CitationProcessorError: If processing fails.
        """  # noqa: W505
        logger.info(
            f'Starting citation processing for {markdown_path} with LangGraph workflow'
        )

        if not markdown_path:
            logger.error('No markdown path provided for processing')
            raise ValueError('No markdown path provided for processing')

        # Construct initial state
        initial_state: CitationState = {
            'markdown_path': markdown_path,
            'content': None,
            'document_citation': None,
            'headings': None,
            'references_heading': None,
            'references_section': None,
            'cleaned_references_section': None,
            'raw_citations': None,
            'citations': None,
            'processed_citations': None,
            'final_citations': None,
        }

        # Invoke the graph
        final_state = self.app.invoke(initial_state, config=config)

        # Extract the final citations from the state
        citations_result = final_state.get('final_citations')

        if not citations_result:
            logger.error(
                'Citation processing finished, but no citations found in final state'
            )
            raise CitationProcessorError(
                'Citation processing completed without producing results'
            )

        logger.info(
            f'Citation processing completed successfully with {len(citations_result)} citations'
        )
        return citations_result
