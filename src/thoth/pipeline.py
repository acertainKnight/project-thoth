"""
Pipeline for Thoth.

This module contains the main pipeline that orchestrates the processing of PDF documents:
1. OCR conversion of PDF to Markdown
2. LLM analysis of content
3. Citation extraction and processing
4. Note generation for Obsidian
"""  # noqa: W505

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

from thoth.knowledge.graph import CitationGraph
from thoth.pipelines.knowledge_pipeline import KnowledgePipeline
from thoth.pipelines.optimized_document_pipeline import OptimizedDocumentPipeline
from thoth.server.pdf_monitor import PDFTracker
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import get_config
from thoth.utilities.schemas import SearchResult


class PipelineError(Exception):
    """Exception raised for errors in the processing pipeline."""

    pass


class ThothPipeline:
    """
    Main processing pipeline for Thoth.

    This class orchestrates the complete document processing workflow:
    1. OCR conversion of PDF to Markdown using ProcessingService
    2. Content analysis using ProcessingService
    3. Citation extraction using CitationService
    4. Note generation using NoteService
    """

    def __init__(
        self,
        ocr_api_key: str | None = None,
        llm_api_key: str | None = None,
        templates_dir: Path | None = None,
        prompts_dir: Path | None = None,
        output_dir: Path | None = None,
        notes_dir: Path | None = None,
        api_base_url: str | None = None,  # noqa: ARG002
    ):
        """
        Initialize the Thoth pipeline.

        Args:
            ocr_api_key: The Mistral API key for OCR. If None, loaded from config.
            llm_api_key: The OpenRouter API key for LLM processing. If None, loaded from config.
            templates_dir: Directory containing templates. If None, default from config is used.
            prompts_dir: Directory containing prompts. If None, default from config is used.
            output_dir: Directory to save intermediate outputs. If None, default from config is used.
            notes_dir: Directory to save generated notes. If None, default from config is used.
            api_base_url: Base URL for the FastAPI endpoint. If None, loaded from config.
        """  # noqa: W505
        # ThothPipeline now uses OptimizedDocumentPipeline by default
        logger.info(
            'ThothPipeline initialized with optimized processing (50-65% faster) '
            'including async I/O, intelligent caching, and CPU-aware scaling.'
        )

        # Load configuration
        self.config = get_config()

        # Override API keys if provided
        if ocr_api_key:
            self.config.api_keys.mistral_key = ocr_api_key
        if llm_api_key:
            self.config.api_keys.openrouter_key = llm_api_key

        # Set up directories
        self.templates_dir = templates_dir or Path(self.config.templates_dir)
        self.prompts_dir = prompts_dir or Path(self.config.prompts_dir)
        self.output_dir = output_dir or Path(self.config.output_dir)
        self.notes_dir = notes_dir or Path(self.config.notes_dir)
        self.markdown_dir = Path(self.config.markdown_dir)

        # Ensure directories exist
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        # Initialize service manager
        self.services = ServiceManager(config=self.config)
        self.services.initialize()

        # Initialize PDF tracker
        self.pdf_tracker = PDFTracker()

        # Initialize components that aren't yet services
        # TODO: CitationGraph should eventually be converted to a service
        self.citation_tracker = CitationGraph(
            knowledge_base_dir=self.config.knowledge_base_dir,
            graph_storage_path=self.config.graph_storage_path,
            pdf_dir=self.config.pdf_dir,
            markdown_dir=self.config.markdown_dir,
            notes_dir=self.config.notes_dir,
            service_manager=self.services,  # Pass ServiceManager for note generation
        )

        # Set citation tracker in services that need it
        self.services.set_citation_tracker(self.citation_tracker)

        # Initialize optimized document pipeline for handling PDF processing
        self.document_pipeline = OptimizedDocumentPipeline(
            services=self.services,
            citation_tracker=self.citation_tracker,
            pdf_tracker=self.pdf_tracker,
            output_dir=self.output_dir,
            notes_dir=self.notes_dir,
            markdown_dir=self.markdown_dir,
        )

        # Initialize knowledge pipeline for RAG operations
        self.knowledge_pipeline = KnowledgePipeline(
            services=self.services,
            citation_tracker=self.citation_tracker,
            pdf_tracker=self.pdf_tracker,
            output_dir=self.output_dir,
            notes_dir=self.notes_dir,
            markdown_dir=self.markdown_dir,
        )

        logger.info('Thoth pipeline initialized with service layer')

    def process_pdf(self, pdf_path: str | Path) -> tuple[Path, Path, Path]:
        """Process a PDF using the internal :class:`DocumentPipeline`."""

        try:
            return self.document_pipeline.process_pdf(pdf_path)
        except Exception as e:  # pragma: no cover - should be rare
            raise PipelineError(str(e)) from e

    def regenerate_all_notes(self) -> list[tuple[Path, Path]]:
        """
        Regenerate all markdown notes for all articles in the citation graph.

        This method delegates to the CitationService's regenerate_all_notes method
        and returns a list of (final_pdf_path, final_note_path) for successfully
        regenerated notes.

        Returns:
            list[tuple[Path, Path]]: A list of (PDF path, note path) tuples for successes.
        """  # noqa: W505
        if not self.services:
            logger.error(
                'ServiceManager is not initialized. Cannot regenerate all notes.'
            )
            return []

        logger.info('Pipeline initiating regeneration of all notes.')
        # Use CitationService instead of calling CitationGraph directly
        successful_files = self.services.citation.regenerate_all_notes()
        logger.info(
            f'Pipeline completed regeneration of all notes. {len(successful_files)} notes successfully regenerated.'
        )
        return successful_files

    def consolidate_tags_only(self) -> dict[str, Any]:
        """
        Consolidate existing tags without suggesting additional tags.

        This method performs only the tag consolidation process:
        1. Extracts all existing tags from the citation graph
        2. Consolidates similar tags into canonical forms using LLM analysis
        3. Updates existing articles with their consolidated tag equivalents

        Returns:
            dict[str, Any]: Summary statistics of the consolidation process,
                           including counts of articles processed and tags consolidated.

        Example:
            >>> pipeline = ThothPipeline()
            >>> stats = pipeline.consolidate_tags_only()
            >>> print(f'Processed {stats["articles_processed"]} articles')
            >>> print(f'Consolidated {stats["tags_consolidated"]} tags')
        """
        if not self.citation_tracker:
            logger.error('CitationGraph is not initialized. Cannot consolidate tags.')
            return {
                'articles_processed': 0,
                'articles_updated': 0,
                'tags_consolidated': 0,
                'original_tag_count': 0,
                'final_tag_count': 0,
                'consolidation_mappings': {},
                'all_available_tags': [],
            }

        return self.services.tag.consolidate_only()

    def suggest_additional_tags(self) -> dict[str, Any]:
        """
        Suggest additional relevant tags for all articles using existing tag vocabulary.

        This method suggests additional tags for articles based on their abstracts
        and the existing tag vocabulary in the citation graph.

        Returns:
            dict[str, Any]: Summary statistics of the tag suggestion process,
                           including counts of articles processed and tags added.

        Example:
            >>> pipeline = ThothPipeline()
            >>> stats = pipeline.suggest_additional_tags()
            >>> print(f'Processed {stats["articles_processed"]} articles')
            >>> print(f'Added {stats["tags_added"]} new tags')
        """
        if not self.citation_tracker:
            logger.error(
                'CitationGraph is not initialized. Cannot suggest additional tags.'
            )
            return {
                'articles_processed': 0,
                'articles_updated': 0,
                'tags_added': 0,
                'vocabulary_size': 0,
            }

        return self.services.tag.suggest_additional()

    def consolidate_and_retag_all_articles(self) -> dict[str, Any]:
        """
        Consolidate existing tags and suggest additional relevant tags for all articles.

        This method performs a complete tag consolidation and re-tagging process:
        1. Extracts all existing tags from the citation graph
        2. Consolidates similar tags into canonical forms using LLM analysis
        3. Updates existing articles with their consolidated tag equivalents
        4. Suggests additional relevant tags for each article based on abstracts
        5. Updates the citation graph with the enhanced tag information

        Returns:
            dict[str, Any]: Summary statistics of the consolidation and re-tagging
                process, including counts of articles processed, tags consolidated,
                and tags added.

        Example:
            >>> pipeline = ThothPipeline()
            >>> stats = pipeline.consolidate_and_retag_all_articles()
            >>> print(f'Processed {stats["articles_processed"]} articles')
            >>> print(f'Consolidated {stats["tags_consolidated"]} tags')
            >>> print(f'Added {stats["tags_added"]} new tags')
        """
        if not self.citation_tracker:
            logger.error(
                'CitationGraph is not initialized. Cannot consolidate and retag articles.'
            )
            return {
                'articles_processed': 0,
                'tags_consolidated': 0,
                'tags_added': 0,
                'original_tag_count': 0,
                'final_tag_count': 0,
            }

        return self.services.tag.consolidate_and_retag()

    def web_search(
        self, query: str, num_results: int = 5, provider: str | None = None
    ) -> list[SearchResult]:
        """Perform a general web search."""
        try:
            logger.info(f'Performing web search for: {query}')
            return self.services.web_search.search(
                query, num_results, provider=provider
            )
        except Exception as e:
            logger.error(f'Web search failed: {e}')
            raise PipelineError(f'Web search failed: {e}') from e


# Example usage
if __name__ == '__main__':
    import sys

    # Get PDF path from command line argument
    if len(sys.argv) < 2:
        print('Usage: python -m thoth.pipeline <pdf_path>')
        sys.exit(1)

    pdf_path = sys.argv[1]
    pipeline = ThothPipeline()

    try:
        note_path = pipeline.process_pdf(pdf_path)
        print(f'Successfully processed {pdf_path}')
        print(f'Note created: {note_path}')
    except PipelineError as e:
        print(f'Error: {e}')
        sys.exit(1)
