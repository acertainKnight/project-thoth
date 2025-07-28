"""
Citation processor for extracting and analyzing citations from academic documents.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, TypedDict

from jinja2 import ChoiceLoader, Environment, FileSystemLoader
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langgraph.graph import END, StateGraph
from loguru import logger

from thoth.analyze.citations.enhancer import CitationEnhancer
from thoth.analyze.citations.extractor import ReferenceExtractor
from thoth.services.pdf_locator_service import PdfLocatorService
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
    """Processes citations from a document."""

    def __init__(self, llm, config, prompts_dir: Path | None = None):
        self.llm = llm
        self.config = config
        self.enhancer = CitationEnhancer(config)
        self.citation_batch_size = self.config.citation_config.citation_batch_size
        self._pdf_locator = None

        # Set up prompts directory based on model provider
        if prompts_dir is None:
            prompts_dir = Path(config.prompts_dir)

        # Determine model provider from llm model name or config
        model_provider = 'openai'  # Default provider
        if hasattr(llm, 'model_name'):
            model_provider = llm.model_name.split('/')[0]
        elif hasattr(config, 'llm_config') and hasattr(config.llm_config, 'provider'):
            model_provider = config.llm_config.provider.lower()

        self.prompts_dir = prompts_dir / model_provider
        # Default prompts packaged with Thoth
        self.default_prompts_dir = (
            Path(__file__).resolve().parents[3]
            / 'templates'
            / 'prompts'
            / model_provider
        )

        # Fall back to google templates if provider-specific templates don't exist
        if not self.prompts_dir.exists():
            self.prompts_dir = prompts_dir / 'google'

        # Fall back to default google templates if provider templates don't exist
        if not self.default_prompts_dir.exists():
            self.default_prompts_dir = (
                Path(__file__).resolve().parents[3] / 'templates' / 'prompts' / 'google'
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

        # Load prompts from templates
        document_citation_prompt = self._create_prompt_from_template(
            'extract_document_citation.j2'
        )
        clean_references_prompt = self._create_prompt_from_template(
            'clean_references_section.j2'
        )
        extract_citations_prompt = self._create_prompt_from_template(
            'extract_citations.j2'
        )
        extract_citations_json_prompt = self._create_prompt_from_template(
            'extract_citations.j2'
        )
        single_citation_prompt = self._create_prompt_from_template(
            'extract_citations_single.j2'
        )
        identify_heading_prompt = self._create_prompt_from_template(
            'identify_references_section.j2'
        )

        # Initialize the chains using granular models
        self.extract_document_citation_chain = (
            document_citation_prompt
            | self.llm.with_structured_output(
                Citation, include_raw=False, method='json_schema'
            )
        )
        self.clean_references_section_chain = clean_references_prompt | self.llm

        self.extract_citations_chain_json = (
            extract_citations_json_prompt
            | self.llm.bind(response_format={'type': 'json_object'})
        )
        self.extract_citations_chain = (
            extract_citations_prompt
            | self.llm.with_structured_output(
                CitationExtractionResponse, include_raw=False, method='json_schema'
            )
        )

        self.single_citation_chain = (
            single_citation_prompt
            | self.llm.with_structured_output(
                Citation, include_raw=False, method='json_schema'
            )
        )

        # Store the identify heading prompt for the extractor
        self.identify_heading_prompt = identify_heading_prompt

    @property
    def pdf_locator(self) -> PdfLocatorService:
        """Get or create the PDF locator service."""
        if self._pdf_locator is None:
            self._pdf_locator = PdfLocatorService(self.config)
            self._pdf_locator.initialize()
        return self._pdf_locator

    def _create_prompt_from_template(self, template_name: str) -> ChatPromptTemplate:
        """
        Create a ChatPromptTemplate from a Jinja2 template file.

        Args:
            template_name: Name of the template file (e.g., "extract_citations.j2").

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
            raise FileNotFoundError(
                f'Template {template_name} not found in {self.prompts_dir}'
            ) from e

    def extract_citations(self, markdown_path: Path) -> list[Citation]:
        """
        Extracts citations from a markdown file.
        This is the main entrypoint for the citation extraction process.
        """
        content = markdown_path.read_text(encoding='utf-8')
        document_citation = self._extract_document_citation(content)
        references_section = self._extract_references_section(content)
        cleaned_references_section = self._clean_references_section(references_section)
        raw_citations = self._split_references_to_raw_citations(
            cleaned_references_section
        )
        # Always use parallel single-citation processing for reliability
        citations = self._extract_structured_citations_parallel(raw_citations)

        enhanced_citations = self._enhance_citations_with_external_services(
            citations + ([document_citation] if document_citation else [])
        )
        return enhanced_citations

    def _extract_document_citation(self, content: str) -> Citation | None:
        """Extract the citation for the document itself."""
        logger.debug('Extracting document citation')
        try:
            citation = self.extract_document_citation_chain.invoke(
                {'document_text': content, 'json_schema': Citation.model_json_schema()}
            )
            if citation:
                citation.is_document_citation = True
            return citation
        except Exception as e:
            logger.error(f'Error extracting document citation: {e}')
            return None

    def _extract_references_section(self, content: str) -> str:
        """Extract the references section from the document."""
        logger.debug('Extracting references section text')
        extractor = ReferenceExtractor(self.llm, self.identify_heading_prompt)
        return extractor.extract(content)

    def _clean_references_section(self, references_section: str) -> str:
        """Clean the references section text with an LLM."""
        if not references_section:
            logger.warning('No references section text to clean.')
            return ''
        logger.debug('Cleaning references section text with LLM')
        response = self.clean_references_section_chain.invoke(
            {'references_section_text': references_section}
        )
        return response.content

    def _split_references_to_raw_citations(
        self, cleaned_references_section: str
    ) -> list[str]:
        """Split the cleaned references section into individual raw citation strings."""
        if not cleaned_references_section:
            return []
        logger.debug('Splitting cleaned references section into raw citations')
        # Simple split by newline, can be improved with more robust logic
        return [
            line.strip()
            for line in cleaned_references_section.split('\n')
            if line.strip()
        ]

    def _extract_structured_citations_single(
        self, raw_citations: list[str]
    ) -> list[Citation]:
        """
        Use an LLM to extract structured information from raw citation strings.

        This method processes citations individually to be robust against parsing
        errors.
        """
        if not raw_citations:
            return []

        logger.debug(
            f'Extracting structured citations for {len(raw_citations)} raw strings one by one.'
        )

        # Create a schema that excludes the 'is_document_citation' field
        reference_schema = Citation.model_json_schema()
        if 'is_document_citation' in reference_schema.get('properties', {}):
            del reference_schema['properties']['is_document_citation']
        if (
            'required' in reference_schema
            and 'is_document_citation' in reference_schema.get('required', [])
        ):
            reference_schema['required'].remove('is_document_citation')

        results = []
        for raw_citation in raw_citations:
            try:
                # Invoke the chain for a single citation
                result = self.single_citation_chain.invoke(
                    {
                        'raw_citation': raw_citation,
                        'json_schema': reference_schema,
                    }
                )

                # Ensure the result is a valid Citation object
                if isinstance(result, Citation):
                    # Explicitly set to False as a safeguard
                    result.is_document_citation = False
                    results.append(result)
                else:
                    logger.warning(
                        f"LLM did not return a valid Citation object for: '{raw_citation}'"
                    )
            except Exception as e:
                # This will catch Pydantic validation errors and other exceptions
                logger.warning(
                    f"Failed to parse structured citation for: '{raw_citation}'. Error: {e}"
                )

        logger.info(
            f'Successfully extracted {len(results)} out of {len(raw_citations)} citations.'
        )
        return results

    def _extract_structured_citations_parallel(
        self, raw_citations: list[str]
    ) -> list[Citation]:
        """
        Extract structured citations using parallel processing.

        This method combines the reliability of single-citation processing with
        the performance benefits of parallelization. Each citation is processed
        individually in parallel threads, avoiding batch processing issues.
        """
        if not raw_citations:
            return []

        logger.debug(
            f'Extracting structured citations for {len(raw_citations)} raw strings in parallel.'
        )

        # Create a schema that excludes the 'is_document_citation' field
        reference_schema = Citation.model_json_schema()
        if 'is_document_citation' in reference_schema.get('properties', {}):
            del reference_schema['properties']['is_document_citation']
        if (
            'required' in reference_schema
            and 'is_document_citation' in reference_schema.get('required', [])
        ):
            reference_schema['required'].remove('is_document_citation')

        def process_single_citation(raw_citation: str) -> Citation | None:
            """Process a single raw citation string. Returns Citation or None."""
            try:
                # Invoke the chain for a single citation
                result = self.single_citation_chain.invoke(
                    {
                        'raw_citation': raw_citation,
                        'json_schema': reference_schema,
                    }
                )

                # Ensure the result is a valid Citation object
                if isinstance(result, Citation):
                    # Explicitly set to False as a safeguard
                    result.is_document_citation = False
                    return result
                else:
                    logger.warning(
                        f"LLM did not return a valid Citation object for: '{raw_citation}'"
                    )
                    return None
            except Exception as e:
                # This will catch Pydantic validation errors and other exceptions
                logger.warning(
                    f"Failed to parse structured citation for: '{raw_citation}'. Error: {e}"
                )
                return None

        # Process citations in parallel with configurable concurrency
        max_workers = getattr(self.config, 'performance_config', None)
        if max_workers:
            max_workers = max_workers.citation_extraction_workers
        else:
            max_workers = 4  # Fallback default

        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_citation = {
                executor.submit(process_single_citation, raw_citation): raw_citation
                for raw_citation in raw_citations
            }

            for future in as_completed(future_to_citation):
                try:
                    result = future.result()
                    if result is not None:
                        results.append(result)
                except Exception as e:
                    raw_citation = future_to_citation[future]
                    logger.error(
                        f'Unexpected error processing citation "{raw_citation}": {e}'
                    )

        logger.info(
            f'Successfully extracted {len(results)} out of {len(raw_citations)} citations using parallel processing.'
        )
        return results

    def _extract_structured_citations_batch(
        self, raw_citations: list[str]
    ) -> list[Citation]:
        """Extract structured citations from raw citation strings in batches."""
        logger.debug('Extracting structured citations from raw strings in batch mode.')
        if not raw_citations:
            return []

        all_citations = []
        failed_batches = []

        for i in range(0, len(raw_citations), self.citation_batch_size):
            batch = raw_citations[i : i + self.citation_batch_size]
            success = False

            # Try up to 3 times for each batch
            for attempt in range(3):
                if self._process_citation_batch(batch, all_citations):
                    success = True
                    break
                else:
                    logger.warning(
                        f'Batch processing attempt {attempt + 1}/3 failed for batch starting at index {i}'
                    )

            if not success:
                # Track failed batches for fallback processing
                failed_batches.extend(batch)
                logger.error(
                    f'Batch processing failed after 3 attempts for {len(batch)} citations. '
                    f'Will fallback to single citation processing.'
                )

        # Convert successfully processed citations
        processed_citations_list = [
            Citation.from_citation_extraction(c) for c in all_citations
        ]

        # If we have failed batches, process them individually
        if failed_batches:
            logger.info(
                f'Falling back to single citation processing for {len(failed_batches)} citations'
            )
            single_processed = self._extract_structured_citations_single(failed_batches)
            processed_citations_list.extend(single_processed)

        # Final safeguard: ensure no reference citation has the flag set
        for citation in processed_citations_list:
            citation.is_document_citation = False

        return processed_citations_list

    def _parse_citation_response(self, response: Any) -> list[Citation] | None:
        """
        Parse citation response from various formats.

        Args:
            response: Response from LLM (could be various formats)

        Returns:
            list[Citation] | None: Parsed citations or None if parsing fails
        """
        import json

        # If it's already a CitationExtractionResponse, extract citations
        if hasattr(response, 'citations'):
            citations = response.citations
            # If citations are already Citation objects, return them
            if citations and all(isinstance(c, Citation) for c in citations):
                return citations
            # If they're CitationExtraction objects, convert them
            elif citations and all(
                isinstance(c, CitationExtraction) for c in citations
            ):
                return [Citation.from_citation_extraction(c) for c in citations]

        # If it's a dict with 'citations' key
        if isinstance(response, dict) and 'citations' in response:
            citations_data = response['citations']
            if isinstance(citations_data, list):
                parsed_citations = []
                for item in citations_data:
                    try:
                        if isinstance(item, Citation):
                            parsed_citations.append(item)
                        elif isinstance(item, dict):
                            parsed_citations.append(Citation(**item))
                        elif isinstance(item, str):
                            # Try to parse as JSON
                            try:
                                item_dict = json.loads(item)
                                parsed_citations.append(Citation(**item_dict))
                            except Exception:
                                logger.warning(
                                    f'Could not parse citation string: {item}'
                                )
                    except Exception as e:
                        logger.warning(f'Failed to parse citation item: {e}')
                return parsed_citations

        # If it's a string, try to parse as JSON
        if isinstance(response, str):
            try:
                data = json.loads(response)
                return self._parse_citation_response(data)
            except Exception:
                logger.error(
                    f'Could not parse response string as JSON: {response[:100]}...'
                )

        return None

    def _process_citation_batch(self, batch: list[str], all_citations: list) -> bool:
        """
        Processes a batch of citations.

        Returns:
            bool: True if successful, False if failed
        """
        batch_text = '\n\n'.join(batch)

        # First try JSON mode
        try:
            json_result = self.extract_citations_chain_json.invoke(
                {'references_section': batch_text}
            )

            # Parse JSON response
            if hasattr(json_result, 'content'):
                import json

                try:
                    json_data = json.loads(json_result.content)
                    parsed_citations = self._parse_citation_response(json_data)
                    if parsed_citations:
                        # Convert to CitationExtraction objects
                        for citation in parsed_citations:
                            citation_extraction = CitationExtraction(
                                text=citation.text,
                                authors=citation.authors,
                                title=citation.title,
                                year=citation.year,
                                journal=citation.journal,
                                venue=citation.venue,
                                doi=citation.doi,
                                url=citation.url,
                                volume=citation.volume,
                                issue=citation.issue,
                                pages=citation.pages,
                            )
                            all_citations.append(citation_extraction)
                        return True
                except json.JSONDecodeError as e:
                    logger.warning(f'JSON parsing failed: {e}')
        except Exception as e:
            logger.warning(f'JSON mode failed: {e}')

        # Fall back to structured output
        try:
            batch_result = self.extract_citations_chain.invoke(
                {'references_section': batch_text}
            )

            # Try to parse the response robustly
            parsed_citations = self._parse_citation_response(batch_result)

            if parsed_citations:
                # Convert to CitationExtraction objects for compatibility
                for citation in parsed_citations:
                    citation_extraction = CitationExtraction(
                        text=citation.text,
                        authors=citation.authors,
                        title=citation.title,
                        year=citation.year,
                        journal=citation.journal,
                        venue=citation.venue,
                        doi=citation.doi,
                        url=citation.url,
                        volume=citation.volume,
                        issue=citation.issue,
                        pages=citation.pages,
                    )
                    all_citations.append(citation_extraction)
                return True
            else:
                logger.error('Failed to parse any citations from batch result')
                return False

        except Exception as e:
            logger.error(f'Error processing batch: {e}')
            return False

    def _enhance_citations_with_external_services(
        self, citations: list[Citation]
    ) -> list[Citation]:
        """Enhance citations with external services including PDF location."""
        logger.debug('Enhancing citations with external services')

        # First enhance with parallel enhancer for better performance
        enhanced_citations = self.enhancer.enhance_parallel(citations)

        # Then try to locate PDFs in parallel
        logger.debug('Locating PDFs for citations')
        pdf_found_count = self._locate_pdfs_parallel(enhanced_citations)

        if pdf_found_count > 0:
            logger.info(
                f'Located PDFs for {pdf_found_count}/{len(enhanced_citations)} citations'
            )

        return enhanced_citations

    def _locate_pdfs_parallel(self, citations: list[Citation]) -> int:
        """Locate PDFs for citations in parallel."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Filter citations that need PDF location
        citations_needing_pdfs = [
            citation
            for citation in citations
            if (citation.doi or citation.arxiv_id) and not citation.pdf_url
        ]

        if not citations_needing_pdfs:
            return 0

        pdf_found_count = 0

        def locate_single_pdf(citation: Citation) -> bool:
            """Locate PDF for a single citation. Returns True if found."""
            try:
                location = self.pdf_locator.locate(
                    doi=citation.doi, arxiv_id=citation.arxiv_id
                )

                if location:
                    citation.pdf_url = location.url
                    citation.pdf_source = location.source
                    citation.is_open_access = location.is_oa
                    logger.debug(
                        f"Found PDF for '{citation.title[:50]}' from {location.source}"
                    )
                    return True
            except Exception as e:
                logger.warning(
                    f"Failed to locate PDF for citation '{citation.title[:50]}': {e}"
                )
            return False

        # Process PDF location in parallel with configurable concurrency
        max_workers = getattr(self.config, 'performance_config', None)
        if max_workers:
            max_workers = max_workers.citation_pdf_workers
        else:
            max_workers = 5  # Fallback default
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_citation = {
                executor.submit(locate_single_pdf, citation): citation
                for citation in citations_needing_pdfs
            }

            for future in as_completed(future_to_citation):
                if future.result():  # True if PDF was found
                    pdf_found_count += 1

        return pdf_found_count

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
            'extract_structured_citations', self._extract_structured_citations
        )
        workflow.add_node(
            'enhance_citations_with_external_services',
            self._enhance_citations_with_external_services,
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
            'split_references_to_raw_citations', 'extract_structured_citations'
        )
        workflow.add_edge(
            'extract_structured_citations', 'enhance_citations_with_external_services'
        )
        workflow.add_edge(
            'enhance_citations_with_external_services', 'prepare_final_citations'
        )
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
