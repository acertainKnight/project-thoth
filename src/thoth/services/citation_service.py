"""
Citation service for managing citation extraction and processing.

This module consolidates all citation-related operations that were previously
scattered across CitationProcessor, tracker, and other components.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from thoth.analyze.citations.citations import CitationProcessor
from thoth.analyze.citations.formatter import CitationFormatter, CitationStyle
from thoth.services.base import BaseService, ServiceError
from thoth.services.llm_service import LLMService
from thoth.services.pdf_locator_service import PdfLocatorService
from thoth.utilities.schemas import AnalysisResponse, Citation

if TYPE_CHECKING:
    from thoth.knowledge.graph import CitationGraph


class CitationService(BaseService):
    """
    Service for managing citation operations.

    This service consolidates:
    - Citation extraction from documents
    - Citation formatting
    - Citation tracking and graph management
    - Citation metadata enrichment
    - PDF location for citations
    """

    def __init__(
        self,
        config=None,
        citation_processor: CitationProcessor | None = None,
    ):
        """
        Initialize the CitationService.

        Args:
            config: Optional configuration object
            citation_processor: Optional CitationProcessor instance
        """
        super().__init__(config)
        self._citation_processor = citation_processor
        self._citation_formatter = CitationFormatter()
        self._pdf_locator_service = None

        # Register for config reload notifications
        if self.config:
            from thoth.config import Config

            Config.register_reload_callback('citation_service', self._on_config_reload)
            self.logger.debug(
                'CitationService registered for config reload notifications'
            )

    @property
    def citation_processor(self) -> CitationProcessor:
        """Get or create the citation processor."""
        if self._citation_processor is None:
            llm_service = LLMService(self.config)
            # Pass provider if available in config
            provider = getattr(self.config.llm_config.citation, 'provider', None)
            llm = llm_service.get_client(
                model=self.config.llm_config.citation.model,
                provider=provider,
                temperature=self.config.llm_config.citation.temperature,
                max_tokens=self.config.llm_config.citation.max_tokens,
            )
            self._citation_processor = CitationProcessor(
                llm=llm,
                config=self.config,
                prompts_dir=Path(self.config.prompts_dir)
                if hasattr(self.config, 'prompts_dir')
                else None,
            )
        return self._citation_processor

    @property
    def pdf_locator(self) -> PdfLocatorService:
        """Get or create the PDF locator service."""
        if self._pdf_locator_service is None:
            self._pdf_locator_service = PdfLocatorService(self.config)
            self._pdf_locator_service.initialize()
        return self._pdf_locator_service

    @property
    def citation_tracker(self) -> 'CitationGraph':
        """Get or create the citation graph."""
        if not hasattr(self, '_citation_tracker'):
            from thoth.knowledge.graph import CitationGraph

            self._citation_tracker = CitationGraph(
                knowledge_base_dir=self.config.knowledge_base_dir,
                notes_dir=self.config.notes_dir,
            )
        return self._citation_tracker

    def initialize(self) -> None:
        """Initialize the citation service."""
        self.logger.info('Citation service initialized')

    def _on_config_reload(self) -> None:
        """
        Handle configuration reload for Citation service.

        Updates:
        - Citation API settings
        - Model configuration
        - Processing modes
        - PDF locator settings
        """
        try:
            logger.info('Reloading Citation configuration...')

            # Clear cached processors to force recreation with new config
            self._citation_processor = None
            self._pdf_locator_service = None

            # Log configuration changes
            if hasattr(self.config, 'llm_config') and hasattr(
                self.config.llm_config, 'citation'
            ):
                self.logger.info(
                    f'Citation model: {self.config.llm_config.citation.model}'
                )

            # Log citation config if available
            if hasattr(self.config, 'citation_config'):
                citation_config = self.config.citation_config
                if hasattr(citation_config, 'style'):
                    self.logger.info(f'Citation style: {citation_config.style}')
                if hasattr(citation_config, 'link_format'):
                    self.logger.info(f'Link format: {citation_config.link_format}')

                # Log API usage settings
                if hasattr(citation_config, 'apis'):
                    apis = citation_config.apis
                    self.logger.info(
                        f'Citation APIs enabled: '
                        f'OpenCitations={getattr(apis, "use_opencitations", False)}, '
                        f'Scholarly={getattr(apis, "use_scholarly", False)}, '
                        f'SemanticScholar={getattr(apis, "use_semantic_scholar", False)}'
                    )

            self.logger.success('✅ Citation config reloaded')

        except Exception as e:
            self.logger.error(f'Citation config reload failed: {e}')

    def extract_citations(
        self, markdown_path: Path | str, style: str = 'ieee'
    ) -> list[Citation]:
        """
        Extract citations from a document.

        Args:
            markdown_path: Path to markdown file or content
            style: Citation style to apply

        Returns:
            list[Citation]: Extracted and enriched citations

        Raises:
            ServiceError: If extraction fails
        """
        try:
            self.validate_input(markdown_path=markdown_path)

            # Extract citations
            citations = self.citation_processor.extract_citations(
                markdown_path
                if isinstance(markdown_path, Path)
                else Path(markdown_path)
            )

            # Convert style string to enum
            style_map = {
                'ieee': CitationStyle.IEEE,
                'apa': CitationStyle.APA,
                'mla': CitationStyle.MLA,
                'chicago': CitationStyle.CHICAGO,
                'harvard': CitationStyle.HARVARD,
            }
            citation_style = style_map.get(style.lower())
            if not citation_style:
                raise ServiceError(f'Unsupported citation style: {style}')

            # Format citations
            formatted_citations = self._citation_formatter.format_citations(
                citations, style=citation_style
            )

            self.log_operation(
                'citations_extracted',
                count=len(formatted_citations),
                source=str(markdown_path)
                if isinstance(markdown_path, Path)
                else 'content',
            )

            return formatted_citations

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'extracting citations')) from e

    def format_citation(
        self,
        citation: Citation,
        style: str = 'ieee',
    ) -> Citation:
        """
        Format a citation in the specified style.

        Args:
            citation: Citation to format
            style: Citation style (ieee, apa, mla, chicago, harvard)

        Returns:
            Citation: Citation with formatted field populated

        Raises:
            ServiceError: If formatting fails
        """
        try:
            self.validate_input(citation=citation)

            # Convert style string to enum
            style_map = {
                'ieee': CitationStyle.IEEE,
                'apa': CitationStyle.APA,
                'mla': CitationStyle.MLA,
                'chicago': CitationStyle.CHICAGO,
                'harvard': CitationStyle.HARVARD,
            }

            citation_style = style_map.get(style.lower())
            if not citation_style:
                raise ServiceError(f'Unsupported citation style: {style}')

            # Format the citation
            formatted = self._citation_formatter.format_citation(
                citation, citation_style
            )

            self.log_operation('citation_formatted', style=style)

            return formatted

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f'formatting citation in {style} style')
            ) from e

    def track_citations(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis: AnalysisResponse,
        citations: list[Citation],
    ) -> str | None:
        """
        Process and track citations in the citation graph.

        Args:
            pdf_path: Path to PDF file
            markdown_path: Path to markdown file
            analysis: Analysis results
            citations: Extracted citations

        Returns:
            str: Article ID if successfully tracked

        Raises:
            ServiceError: If tracking fails
        """
        try:
            self.validate_input(
                pdf_path=pdf_path,
                markdown_path=markdown_path,
                analysis=analysis,
            )

            article_id = self.citation_tracker.process_citations(
                pdf_path=pdf_path,
                markdown_path=markdown_path,
                analysis=analysis,
                citations=citations,
            )

            if article_id:
                self.log_operation(
                    'citations_tracked',
                    article_id=article_id,
                    citation_count=len(citations),
                )

            return article_id

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'tracking citations')) from e

    def get_citation_network(
        self,
        article_id: str,
        depth: int = 1,
    ) -> dict[str, Any]:
        """
        Get the citation network for an article.

        Args:
            article_id: ID of the article
            depth: Network depth to retrieve

        Returns:
            dict[str, Any]: Citation network data

        Raises:
            ServiceError: If retrieval fails
        """
        try:
            self.validate_input(article_id=article_id)

            # Get network from tracker
            network = self.citation_tracker.get_citation_network(article_id, depth)

            # Convert to serializable format
            network_data = {
                'nodes': [
                    {
                        'id': node,
                        'metadata': self.citation_tracker.get_article_metadata(node),
                    }
                    for node in network.nodes()
                ],
                'edges': [
                    {
                        'source': source,
                        'target': target,
                        'data': network.edges[source, target],
                    }
                    for source, target in network.edges()
                ],
                'depth': depth,
            }

            self.log_operation(
                'network_retrieved',
                article_id=article_id,
                nodes=len(network_data['nodes']),
                edges=len(network_data['edges']),
            )

            return network_data

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f'getting citation network for {article_id}')
            ) from e

    def search_articles(self, query: str) -> list[dict[str, Any]]:
        """
        Search for articles in the citation graph.

        Args:
            query: Search query

        Returns:
            list[dict[str, Any]]: Matching articles with metadata

        Raises:
            ServiceError: If search fails
        """
        try:
            self.validate_input(query=query)

            # Search in tracker
            article_ids = self.citation_tracker.search_articles(query)

            # Get metadata for each article
            results = []
            for article_id in article_ids:
                metadata = self.citation_tracker.get_article_metadata(article_id)
                if metadata:
                    results.append(
                        {
                            'id': article_id,
                            'metadata': metadata,
                        }
                    )

            self.log_operation(
                'articles_searched',
                query=query,
                results=len(results),
            )

            return results

        except Exception as e:
            raise ServiceError(self.handle_error(e, f"searching for '{query}'")) from e

    def get_article_data(self, article_id: str) -> dict[str, Any] | None:
        """
        Get all data for an article.

        Args:
            article_id: ID of the article

        Returns:
            dict[str, Any]: Article data or None if not found
        """
        try:
            return self.citation_tracker.get_article_data_for_regeneration(article_id)

        except Exception as e:
            self.logger.error(
                self.handle_error(e, f'getting data for article {article_id}')
            )
            return None

    def update_article_paths(
        self,
        article_id: str,
        pdf_path: Path,
        markdown_path: Path,
    ) -> bool:
        """
        Update file paths for an article.

        Args:
            article_id: ID of the article
            pdf_path: New PDF path
            markdown_path: New markdown path

        Returns:
            bool: True if successful
        """
        try:
            self.citation_tracker.update_article_file_paths(
                article_id=article_id,
                new_pdf_path=pdf_path,
                new_markdown_path=markdown_path,
            )

            self.log_operation(
                'paths_updated',
                article_id=article_id,
            )

            return True

        except Exception as e:
            self.logger.error(
                self.handle_error(e, f'updating paths for article {article_id}')
            )
            return False

    def locate_pdfs_for_citations(
        self, citations: list[Citation], update_citations: bool = True
    ) -> list[tuple[Citation, str | None]]:
        """
        Locate PDFs for a list of citations.

        Args:
            citations: List of citations to find PDFs for
            update_citations: Whether to update citation objects with PDF URLs

        Returns:
            list[tuple[Citation, str | None]]: List of (citation, pdf_url) tuples

        Raises:
            ServiceError: If PDF location fails
        """
        try:
            results = []

            for citation in citations:
                pdf_url = None

                # Try to locate PDF using DOI or arXiv ID
                if citation.doi or citation.arxiv_id:
                    try:
                        location = self.pdf_locator.locate(
                            doi=citation.doi, arxiv_id=citation.arxiv_id
                        )

                        if location:
                            pdf_url = location.url

                            # Update citation if requested
                            if update_citations:
                                citation.pdf_url = pdf_url
                                citation.pdf_source = location.source
                                citation.is_open_access = location.is_oa

                            self.log_operation(
                                'pdf_located_for_citation',
                                title=citation.title[:50],
                                source=location.source,
                                doi=citation.doi,
                                arxiv_id=citation.arxiv_id,
                            )
                    except Exception as e:
                        self.logger.warning(
                            f"Failed to locate PDF for citation '{citation.title[:50]}': {e}"
                        )

                results.append((citation, pdf_url))

            # Log summary
            located_count = sum(1 for _, url in results if url is not None)
            self.log_operation(
                'pdfs_located_for_citations',
                total=len(citations),
                located=located_count,
                success_rate=f'{(located_count / len(citations) * 100):.1f}%'
                if citations
                else '0%',
            )

            return results

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, 'locating PDFs for citations')
            ) from e

    def locate_pdf_for_citation(self, citation: Citation) -> str | None:
        """
        Locate PDF for a single citation.

        Args:
            citation: Citation to find PDF for

        Returns:
            str | None: PDF URL if found, None otherwise
        """
        try:
            if not citation.doi and not citation.arxiv_id:
                self.logger.debug(
                    f"No DOI or arXiv ID for citation '{citation.title[:50]}'"
                )
                return None

            location = self.pdf_locator.locate(
                doi=citation.doi, arxiv_id=citation.arxiv_id
            )

            if location:
                self.log_operation(
                    'pdf_located', title=citation.title[:50], source=location.source
                )
                return location.url

            return None

        except Exception as e:
            self.logger.error(
                self.handle_error(e, f"locating PDF for '{citation.title[:50]}'")
            )
            return None

    def regenerate_all_notes(self) -> list[tuple[Path, Path]]:
        """
        Regenerate all markdown notes for all articles in the citation graph.

        This method iterates through each article in the citation graph,
        retrieves its data, uses the NoteService to recreate its
        markdown note, and returns a list of (PDF path, note path) tuples
        for successfully regenerated notes.

        Returns:
            list[tuple[Path, Path]]: A list of tuples, where each tuple
                                     contains the final Path to the PDF file
                                     and the final Path to its regenerated note.

        Raises:
            ServiceError: If note regeneration fails
        """
        try:
            self.validate_input()

            if not hasattr(self, '_service_manager') or not self._service_manager:
                # Get service manager from global if not set
                from thoth.services.service_manager import ServiceManager  # noqa: I001
                from thoth.config import config

                self._service_manager = ServiceManager(config)
                self._service_manager.initialize()

            graph = self.citation_tracker.graph
            logger.info(
                f'Starting regeneration of all notes for {len(graph.nodes)} articles.'
            )

            regenerated_count = 0
            failed_count = 0
            successfully_regenerated_files: list[tuple[Path, Path]] = []

            for article_id in list(graph.nodes):  # Iterate over a copy of node IDs
                article_title = (
                    graph.nodes[article_id].get('metadata', {}).get('title', article_id)
                )
                self.logger.info(f'Attempting to regenerate note for: {article_title}')

                # Get regeneration data from citation tracker
                regeneration_data = (
                    self.citation_tracker.get_article_data_for_regeneration(article_id)
                )

                if regeneration_data:
                    try:
                        # Use NoteService through ServiceManager
                        (
                            note_path,
                            final_pdf_path,
                            markdown_path,
                        ) = self._service_manager.note.create_note(
                            pdf_path=regeneration_data['pdf_path'],
                            markdown_path=regeneration_data['markdown_path'],
                            analysis=regeneration_data['analysis'],
                            citations=regeneration_data['citations'],
                        )

                        self.logger.info(
                            f'Successfully regenerated note for: {article_title} at {note_path}'
                        )
                        regenerated_count += 1
                        successfully_regenerated_files.append(
                            (final_pdf_path, note_path)
                        )

                    except Exception as e:
                        self.logger.error(
                            f'Failed to regenerate note for {article_title} (ID: {article_id}): {e}'
                        )
                        failed_count += 1
                else:
                    self.logger.warning(
                        f'No regeneration data found for article: {article_title}'
                    )
                    failed_count += 1

            self.log_operation(
                'notes_regenerated',
                total_articles=len(graph.nodes),
                regenerated=regenerated_count,
                failed=failed_count,
            )

            return successfully_regenerated_files

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'regenerating all notes')) from e

    def update_obsidian_links(self, article_id: str) -> bool:
        """
        Update Obsidian markdown links for an article's citations.

        This method finds all citations from the article and updates the
        corresponding Obsidian markdown note with proper wiki-links to
        existing notes for cited articles.

        Args:
            article_id: ID of the article to update

        Returns:
            bool: True if update was successful

        Raises:
            ServiceError: If link update fails
        """
        try:
            self.validate_input(article_id=article_id)

            # Delegate core link updating logic to citation tracker
            # but handle it as a service operation with proper error handling
            self.citation_tracker.update_obsidian_links(article_id)

            self.log_operation('obsidian_links_updated', article_id=article_id)
            return True

        except Exception as e:
            self.logger.error(
                self.handle_error(
                    e, f'updating Obsidian links for article {article_id}'
                )
            )
            return False

    def health_check(self) -> dict[str, str]:
        """Basic health status for the CitationService."""
        return super().health_check()
