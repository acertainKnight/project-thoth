"""
Citation service for managing citation extraction and processing.

This module consolidates all citation-related operations that were previously
scattered across CitationProcessor, tracker, and other components.
"""

from pathlib import Path
from typing import Any

from thoth.analyze.citations.citations import CitationProcessor
from thoth.analyze.citations.formatter import CitationFormatter, CitationStyle
from thoth.services.base import BaseService, ServiceError
from thoth.services.llm_service import LLMService
from thoth.utilities.schemas import AnalysisResponse, Citation


class CitationService(BaseService):
    """
    Service for managing citation operations.

    This service consolidates:
    - Citation extraction from documents
    - Citation formatting
    - Citation tracking and graph management
    - Citation metadata enrichment
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

    @property
    def citation_processor(self) -> CitationProcessor:
        """Get or create the citation processor."""
        if self._citation_processor is None:
            llm_service = LLMService(self.config)
            llm = llm_service.get_client(
                model=self.config.citation_llm_config.model,
                **self.config.citation_llm_config.model_settings.model_dump(),
            )
            self._citation_processor = CitationProcessor(
                llm=llm,
                config=self.config,
                prompts_dir=Path(self.config.prompts_dir)
                if hasattr(self.config, 'prompts_dir')
                else None,
            )
        return self._citation_processor

    def initialize(self) -> None:
        """Initialize the citation service."""
        self.logger.info('Citation service initialized')

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
