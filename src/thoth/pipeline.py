"""
Pipeline for Thoth.

This module contains the main pipeline that orchestrates the processing of PDF documents:
1. OCR conversion of PDF to Markdown
2. LLM analysis of content
3. Citation extraction and processing
4. Note generation for Obsidian
"""  # noqa: W505

from pathlib import Path
from typing import Any

from loguru import logger

from thoth.ingestion.filter import Filter
from thoth.knowledge.graph import CitationGraph
from thoth.services.service_manager import ServiceManager
from thoth.utilities.config import get_config
from thoth.utilities.schemas import Citation, SearchResult


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

        # Initialize filter with service manager
        self.filter = Filter(service_manager=self.services)

        # Set filter function on discovery service
        self.services.set_filter_function(self.filter.process_article)

        # Initialize components that aren't yet services
        # TODO: CitationGraph should eventually be converted to a service
        self.citation_tracker = CitationGraph(
            knowledge_base_dir=self.config.knowledge_base_dir,
            graph_storage_path=self.config.graph_storage_path,
            note_generator=None,  # Deprecated - using ServiceManager
            pdf_dir=self.config.pdf_dir,
            markdown_dir=self.config.markdown_dir,
            notes_dir=self.config.notes_dir,
            service_manager=self.services,  # Pass ServiceManager for note generation
        )

        # Set citation tracker in services that need it
        self.services.set_citation_tracker(self.citation_tracker)

        logger.info('Thoth pipeline initialized with service layer')

    def process_pdf(self, pdf_path: str | Path) -> Path:
        """
        Process a PDF file through the complete pipeline.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Path: Path to the generated note.

        Raises:
            PipelineError: If any step in the pipeline fails.
        """
        pdf_path = Path(pdf_path)
        logger.info(f'Processing PDF: {pdf_path}')

        # Step 1: OCR conversion
        markdown_path, no_images_markdown = self._ocr_convert(pdf_path)
        logger.info(f'OCR conversion completed: {markdown_path}')

        # Step 2: LLM analysis
        analysis = self._analyze_content(no_images_markdown)
        logger.info('Content analysis completed')

        # Step 3: Citation extraction
        citations = self._extract_citations(no_images_markdown)
        logger.info(f'Citation extraction completed: {len(citations)} citations found')

        # Step 4: Generate note
        note_path, new_pdf_path, new_markdown_path = self._generate_note(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )
        logger.info(f'Note generation completed: {note_path}')

        # Step 5: Index markdown and note in RAG system (optional)
        # This is done asynchronously to not slow down the main pipeline
        try:
            self._index_to_rag(new_markdown_path)
            self._index_to_rag(Path(note_path))
        except Exception as e:
            logger.warning(f'Failed to index documents to RAG system: {e}')
            # Don't fail the pipeline if RAG indexing fails

        return Path(note_path), Path(new_pdf_path), Path(new_markdown_path)

    def _ocr_convert(self, pdf_path: Path) -> tuple[Path, Path]:
        """
        Convert PDF to Markdown using OCR.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            tuple[Path, Path]: Path to the generated Markdown file and the path to the generated Markdown file without images.

        Raises:
            OCRError: If OCR conversion fails.
        """  # noqa: W505
        try:
            return self.services.processing.ocr_convert(
                pdf_path=pdf_path, output_dir=self.markdown_dir
            )
        except Exception as e:
            raise PipelineError(f'OCR conversion failed for {pdf_path}: {e!s}') from e

    def _analyze_content(self, markdown_path: Path):
        """
        Analyze content with LLM.

        Args:
            markdown_path: The path to the markdown file to analyze.

        Returns:
            AnalysisResponse: The analysis result.

        Raises:
            LLMError: If LLM analysis fails.
        """
        return self.services.processing.analyze_document(markdown_path)

    def _extract_citations(self, markdown_path: Path) -> list[Citation]:
        """
        Extract citations from content.

        Args:
            markdown_path: The path to the markdown file to extract citations from.

        Returns:
            list[Citation]: The extracted citations.
        """
        return self.services.citation.extract_from_document(markdown_path)

    def _generate_note(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis,
        citations: list[Citation],
    ) -> tuple[str, str, str]:
        """
        Generate an Obsidian note and update file paths in the citation tracker.

        Args:
            pdf_path: Path to the PDF file.
            markdown_path: Path to the Markdown file.
            analysis: Analysis results.
            citations: Extracted citations.

        Returns:
            str: Path to the generated note.
        """
        # Use NoteService to create the note
        note_path, new_pdf_path, new_markdown_path = self.services.note.create_note(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )

        # Process citations in the citation tracker
        article_id = self.citation_tracker.process_citations(
            pdf_path=new_pdf_path,
            markdown_path=new_markdown_path,
            analysis=analysis,
            citations=citations,
        )

        if article_id:
            self.citation_tracker.update_article_file_paths(
                article_id=article_id,
                new_pdf_path=new_pdf_path,
                new_markdown_path=new_markdown_path,
            )
        else:
            logger.warning(
                'Could not obtain article_id from process_citations. '
                'File paths in citation tracker may not be updated for the renamed files.'
            )

        return str(note_path), str(new_pdf_path), str(new_markdown_path)

    def _index_to_rag(self, file_path: Path) -> None:
        """
        Index a file to the RAG system if available.

        Args:
            file_path: Path to the file to index.
        """
        try:
            if file_path.exists() and file_path.suffix == '.md':
                self.services.rag.index_file(file_path)
                logger.debug(f'Indexed {file_path} to RAG system')
        except Exception as e:
            logger.debug(f'Failed to index {file_path} to RAG: {e}')

    def regenerate_all_notes(self) -> list[tuple[Path, Path]]:
        """
        Regenerate all markdown notes for all articles in the citation graph.

        This method delegates to the CitationGraph's regenerate_all_notes method
        and returns a list of (final_pdf_path, final_note_path) for successfully
        regenerated notes.

        Returns:
            list[tuple[Path, Path]]: A list of (PDF path, note path) tuples for successes.
        """  # noqa: W505
        if not self.citation_tracker:
            logger.error(
                'CitationGraph is not initialized. Cannot regenerate all notes.'
            )
            return []
        if not self.citation_tracker.note_generator:
            logger.error(
                'NoteGenerator not configured in CitationGraph. Cannot regenerate all notes.'
            )
            return []

        logger.info('Pipeline initiating regeneration of all notes.')
        successful_files = self.citation_tracker.regenerate_all_notes()
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

    def index_knowledge_base(self) -> dict[str, Any]:
        """
        Index all markdown files in the knowledge base into the RAG system.

        This method indexes:
        - All markdown files in the markdown directory (OCR'd articles)
        - All markdown files in the notes directory (generated notes)

        Returns:
            dict[str, Any]: Summary statistics of the indexing process,
                           including counts of files indexed and any errors.

        Example:
            >>> pipeline = ThothPipeline()
            >>> stats = pipeline.index_knowledge_base()
            >>> print(f'Indexed {stats["total_files"]} files')
        """
        logger.info('Starting knowledge base indexing for RAG system')

        try:
            stats = self.services.rag.index_knowledge_base()

            logger.info(
                f'Knowledge base indexing completed. '
                f'Indexed {stats["total_files"]} files '
                f'({stats["total_chunks"]} chunks)'
            )

            return stats

        except Exception as e:
            logger.error(f'Knowledge base indexing failed: {e}')
            raise PipelineError(f'Knowledge base indexing failed: {e}') from e

    def search_knowledge_base(
        self,
        query: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search the knowledge base for relevant documents.

        Args:
            query: Search query text.
            k: Number of results to return.
            filter: Optional metadata filter (e.g., {'document_type': 'note'}).

        Returns:
            list[dict[str, Any]]: List of search results with content and metadata.

        Example:
            >>> pipeline = ThothPipeline()
            >>> results = pipeline.search_knowledge_base('transformer architecture')
            >>> for result in results:
            ...     print(f'Score: {result["score"]}, Title: {result["title"]}')
        """
        try:
            logger.info(f'Searching knowledge base for: {query}')
            return self.services.rag.search(query, k, filter)

        except Exception as e:
            logger.error(f'Knowledge base search failed: {e}')
            raise PipelineError(f'Knowledge base search failed: {e}') from e

    def ask_knowledge_base(
        self,
        question: str,
        k: int = 4,
        filter: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Ask a question and get an answer based on the knowledge base.

        Args:
            question: The question to ask.
            k: Number of documents to retrieve for context.
            filter: Optional metadata filter for retrieval.

        Returns:
            dict[str, Any]: Answer with sources and metadata.

        Example:
            >>> pipeline = ThothPipeline()
            >>> response = pipeline.ask_knowledge_base(
            ...     'What are the main contributions of the transformer paper?'
            ... )
            >>> print(response['answer'])
            >>> for source in response['sources']:
            ...     print(f'Source: {source["metadata"]["title"]}')
        """
        try:
            logger.info(f'Answering question: {question}')
            return self.services.rag.ask_question(question, k, filter)

        except Exception as e:
            logger.error(f'Failed to answer question: {e}')
            raise PipelineError(f'Failed to answer question: {e}') from e

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

    def clear_rag_index(self) -> None:
        """
        Clear the entire RAG vector index.

        WARNING: This will delete all indexed documents and require re-indexing.

        Example:
            >>> pipeline = ThothPipeline()
            >>> pipeline.clear_rag_index()
            >>> # Now re-index
            >>> pipeline.index_knowledge_base()
        """
        try:
            logger.warning('Clearing RAG vector index')
            self.services.rag.clear_index()
            logger.info('RAG vector index cleared successfully')
        except Exception as e:
            logger.error(f'Failed to clear RAG index: {e}')
            raise PipelineError(f'Failed to clear RAG index: {e}') from e

    def get_rag_stats(self) -> dict[str, Any]:
        """
        Get statistics about the RAG system.

        Returns:
            dict[str, Any]: Statistics including document count, models used, etc.

        Example:
            >>> pipeline = ThothPipeline()
            >>> stats = pipeline.get_rag_stats()
            >>> print(f'Documents indexed: {stats["document_count"]}')
        """
        try:
            return self.services.rag.get_stats()
        except Exception as e:
            logger.error(f'Failed to get RAG stats: {e}')
            raise PipelineError(f'Failed to get RAG stats: {e}') from e


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
