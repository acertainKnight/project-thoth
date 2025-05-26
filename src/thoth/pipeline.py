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

from thoth.analyze.citations.citations import CitationProcessor
from thoth.analyze.citations.formatter import CitationFormatter
from thoth.analyze.llm_processor import AnalysisResponse, LLMProcessor
from thoth.analyze.tag_consolidator import TagConsolidator
from thoth.monitor.tracker import CitationTracker
from thoth.notes.note_generator import NoteGenerator
from thoth.ocr.ocr_manager import MistralOCR, OCRError
from thoth.utilities.config import get_config
from thoth.utilities.models import Citation


class PipelineError(Exception):
    """Exception raised for errors in the processing pipeline."""

    pass


class ThothPipeline:
    """
    Main processing pipeline for Thoth.

    This class orchestrates the complete document processing workflow:
    1. OCR conversion of PDF to Markdown using MistralOCR
    2. Content analysis using LLMProcessor
    3. Citation extraction using CitationProcessor
    4. Note generation using NoteGenerator
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

        # Initialize components
        # OCR Manager
        self.ocr_manager = MistralOCR(
            api_key=ocr_api_key or self.config.api_keys.mistral_key
        )

        # Note Generator (must be initialized before CitationTracker)
        self.note_generator = NoteGenerator(
            templates_dir=self.config.templates_dir,
            notes_dir=self.config.notes_dir,
            api_base_url=self.config.api_server_config.base_url,
        )

        # Ensure workspace_dir is not duplicated by removing it from api_keys if present

        self.llm_processor = LLMProcessor(
            model=self.config.llm_config.model,
            max_output_tokens=self.config.llm_config.max_output_tokens,
            max_context_length=self.config.llm_config.max_context_length,
            chunk_size=self.config.llm_config.chunk_size,
            chunk_overlap=self.config.llm_config.chunk_overlap,
            openrouter_api_key=llm_api_key or self.config.api_keys.openrouter_key,
            prompts_dir=self.prompts_dir,
            model_kwargs=self.config.llm_config.model_settings.model_dump(),
            refine_threshold_multiplier=self.config.llm_config.refine_threshold_multiplier,
            map_reduce_threshold_multiplier=self.config.llm_config.map_reduce_threshold_multiplier,
        )

        # Log the value of use_scholarly from config before passing it
        logger.debug(
            f'PIPELINE: Initializing CitationProcessor with use_scholarly={self.config.citation_config.use_scholarly}'
        )

        # Citation Processor
        self.citation_processor = CitationProcessor(
            model=self.config.citation_llm_config.model,
            openrouter_api_key=self.config.api_keys.openrouter_key,
            prompts_dir=self.prompts_dir,
            use_opencitations=self.config.citation_config.use_opencitations,
            use_scholarly=self.config.citation_config.use_scholarly,
            opencitations_token=self.config.api_keys.opencitations_key,
            model_kwargs=self.config.citation_llm_config.model_settings.model_dump(),
            use_semanticscholar=self.config.citation_config.use_semanticscholar,
            semanticscholar_api_key=self.config.api_keys.semanticscholar_api_key,
            use_arxiv=self.config.citation_config.use_arxiv,
            citation_batch_size=self.config.citation_config.citation_batch_size,
        )

        self.citation_formatter = CitationFormatter()
        self.citation_tracker = CitationTracker(
            knowledge_base_dir=self.config.knowledge_base_dir,
            graph_storage_path=self.config.graph_storage_path,
            note_generator=self.note_generator,
            pdf_dir=self.config.pdf_dir,
            markdown_dir=self.config.markdown_dir,
            notes_dir=self.config.notes_dir,
        )

        # Tag Consolidator (initialized lazily when needed)
        self._tag_consolidator = None

        logger.info('Thoth pipeline initialized')

    @property
    def tag_consolidator(self) -> TagConsolidator:
        """
        Lazy initialization of TagConsolidator.

        Returns:
            TagConsolidator: The initialized tag consolidator instance.
        """
        if self._tag_consolidator is None:
            self._tag_consolidator = TagConsolidator(
                consolidate_model=self.config.tag_consolidator_llm_config.consolidate_model,
                suggest_model=self.config.tag_consolidator_llm_config.suggest_model,
                map_model=self.config.tag_consolidator_llm_config.map_model,
                openrouter_api_key=self.config.api_keys.openrouter_key,
                prompts_dir=self.prompts_dir,
                model_kwargs=self.config.tag_consolidator_llm_config.model_settings.model_dump(),
            )
        return self._tag_consolidator

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
            return self.ocr_manager.convert_pdf_to_markdown(
                pdf_path=pdf_path, output_dir=self.markdown_dir
            )
        except Exception as e:
            raise OCRError(f'OCR conversion failed for {pdf_path}: {e!s}') from e

    def _analyze_content(self, markdown_path: Path) -> AnalysisResponse:
        """
        Analyze content with LLM.

        Args:
            markdown_path: The path to the markdown file to analyze.

        Returns:
            AnalysisResponse: The analysis result.

        Raises:
            LLMError: If LLM analysis fails.
        """
        return self.llm_processor.analyze_content(markdown_path)

    def _extract_citations(self, markdown_path: Path) -> list[Citation]:
        """
        Extract citations from content.

        Args:
            markdown_path: The path to the markdown file to extract citations from.

        Returns:
            list[Citation]: The extracted citations.
        """
        citations = self.citation_processor.process_document(markdown_path)
        return self.citation_formatter.format_citations(citations)

    def _generate_note(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis: AnalysisResponse,
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
        article_id = self.citation_tracker.process_citations(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )

        note_path_str, new_pdf_path, new_markdown_path = (
            self.note_generator.create_note(
                pdf_path=pdf_path,
                markdown_path=markdown_path,
                analysis=analysis,
                citations=citations,
            )
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

        return note_path_str, str(new_pdf_path), str(new_markdown_path)

    def regenerate_all_notes(self) -> list[tuple[Path, Path]]:
        """
        Regenerate all markdown notes for all articles in the citation graph.

        This method delegates to the CitationTracker's regenerate_all_notes method
        and returns a list of (final_pdf_path, final_note_path) for successfully
        regenerated notes.

        Returns:
            list[tuple[Path, Path]]: A list of (PDF path, note path) tuples for successes.
        """  # noqa: W505
        if not self.citation_tracker:
            logger.error(
                'CitationTracker is not initialized. Cannot regenerate all notes.'
            )
            return []
        if not self.citation_tracker.note_generator:
            logger.error(
                'NoteGenerator not configured in CitationTracker. Cannot regenerate all notes.'
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
            logger.error('CitationTracker is not initialized. Cannot consolidate tags.')
            return {
                'articles_processed': 0,
                'articles_updated': 0,
                'tags_consolidated': 0,
                'original_tag_count': 0,
                'final_tag_count': 0,
                'consolidation_mappings': {},
                'all_available_tags': [],
            }

        logger.info(
            'Pipeline initiating tag consolidation process (consolidation only).'
        )

        try:
            # Step 1: Extract all existing tags
            existing_tags = self.tag_consolidator.extract_all_tags_from_graph(
                self.citation_tracker
            )
            if not existing_tags:
                logger.warning('No existing tags found in the citation graph')
                return {
                    'articles_processed': 0,
                    'articles_updated': 0,
                    'tags_consolidated': 0,
                    'original_tag_count': 0,
                    'final_tag_count': 0,
                    'consolidation_mappings': {},
                    'all_available_tags': [],
                }

            # Step 2: Consolidate tags
            consolidation_response = self.tag_consolidator.consolidate_tags(
                existing_tags
            )
            all_available_tags = consolidation_response.consolidated_tags

            # Step 3: Apply consolidation mappings to existing articles
            articles_processed = 0
            articles_updated = 0

            for article_id, node_data in self.citation_tracker.graph.nodes(data=True):
                analysis_dict = node_data.get('analysis')
                metadata = node_data.get('metadata', {})

                if not analysis_dict:
                    logger.debug(
                        f'No analysis data found for article {article_id}, skipping'
                    )
                    continue

                # Get article info
                title = metadata.get('title', article_id)
                current_tags = analysis_dict.get('tags', [])

                # Apply tag consolidation mappings to current tags
                updated_tags = []
                for tag in current_tags or []:
                    canonical_tag = consolidation_response.tag_mappings.get(tag, tag)
                    updated_tags.append(canonical_tag)

                # Remove duplicates while preserving order
                final_tags = list(dict.fromkeys(updated_tags))

                # Update the analysis with new tags if they changed
                if final_tags != current_tags:
                    analysis_dict['tags'] = final_tags
                    articles_updated += 1
                    logger.info(
                        f'Updated tags for "{title}": {len(current_tags or [])} -> {len(final_tags)} tags'
                    )

                # Step 3e: Save the updated graph
                if articles_updated > 0:
                    self.citation_tracker._save_graph()
                    logger.info('Saved updated citation graph with consolidated tags')

                articles_processed += 1

            # Step 5: Return summary statistics
            stats = {
                'articles_processed': articles_processed,
                'articles_updated': articles_updated,
                'tags_consolidated': len(consolidation_response.tag_mappings),
                'original_tag_count': len(existing_tags),
                'final_tag_count': len(all_available_tags),
                'consolidation_mappings': consolidation_response.tag_mappings,
                'all_available_tags': all_available_tags,
                'total_vocabulary_size': len(all_available_tags),
            }

            logger.info(
                f'Tag consolidation completed. '
                f'Processed {articles_processed} articles, '
                f'updated {articles_updated} articles, '
                f'consolidated {len(consolidation_response.tag_mappings)} tags.'
            )

            return stats

        except Exception as e:
            logger.error(f'Tag consolidation failed: {e}')
            raise PipelineError(f'Tag consolidation failed: {e}') from e

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
                'CitationTracker is not initialized. Cannot suggest additional tags.'
            )
            return {
                'articles_processed': 0,
                'articles_updated': 0,
                'tags_added': 0,
                'vocabulary_size': 0,
            }

        logger.info('Pipeline initiating tag suggestion process.')

        try:
            # Step 1: Extract all existing tags to use as vocabulary
            available_tags = self.tag_consolidator.extract_all_tags_from_graph(
                self.citation_tracker
            )
            if not available_tags:
                logger.warning(
                    'No existing tags found in the citation graph to use as vocabulary'
                )
                return {
                    'articles_processed': 0,
                    'articles_updated': 0,
                    'tags_added': 0,
                    'vocabulary_size': 0,
                }

            logger.info(
                f'Using {len(available_tags)} tags as vocabulary for suggestions (includes canonical, category, and aggregate tags)'
            )

            # Step 2: Process each article for tag suggestions
            articles_processed = 0
            articles_updated = 0
            total_tags_added = 0

            for article_id, node_data in self.citation_tracker.graph.nodes(data=True):
                analysis_dict = node_data.get('analysis')
                metadata = node_data.get('metadata', {})

                if not analysis_dict:
                    logger.trace(
                        f'No analysis data found for article {article_id}, skipping'
                    )
                    continue

                # Get article info
                title = metadata.get('title', article_id)
                abstract = analysis_dict.get('abstract', '')
                current_tags = analysis_dict.get('tags', [])

                # Skip if no abstract available
                if not abstract:
                    logger.debug(
                        f'No abstract available for article "{title}", skipping tag suggestions'
                    )
                    articles_processed += 1
                    continue

                # Suggest additional tags
                try:
                    suggestion_response = self.tag_consolidator.suggest_additional_tags(
                        title=title,
                        abstract=abstract,
                        current_tags=current_tags or [],
                        available_tags=available_tags,
                    )
                    suggested_tags = suggestion_response.suggested_tags

                    if suggested_tags:
                        # Combine current tags with suggested tags and remove duplicates
                        final_tags = list(
                            dict.fromkeys((current_tags or []) + suggested_tags)
                        )

                        # Update the analysis with new tags
                        analysis_dict['tags'] = final_tags
                        articles_updated += 1
                        total_tags_added += len(suggested_tags)

                        logger.info(
                            f'Added {len(suggested_tags)} tags to "{title}": {suggested_tags}'
                        )

                except Exception as e:
                    logger.warning(
                        f'Failed to suggest tags for article {article_id}: {e}'
                    )

                # Step 3e: Save the updated graph
                if articles_updated > 0:
                    self.citation_tracker._save_graph()
                    logger.info('Saved updated citation graph with suggested tags')

                articles_processed += 1

            # Step 4: Return summary statistics
            stats = {
                'articles_processed': articles_processed,
                'articles_updated': articles_updated,
                'tags_added': total_tags_added,
                'vocabulary_size': len(available_tags),
            }

            logger.info(
                f'Tag suggestion completed. '
                f'Processed {articles_processed} articles, '
                f'updated {articles_updated} articles, '
                f'added {total_tags_added} new tags.'
            )

            return stats

        except Exception as e:
            logger.error(f'Tag suggestion failed: {e}')
            raise PipelineError(f'Tag suggestion failed: {e}') from e

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
                'CitationTracker is not initialized. Cannot consolidate and retag articles.'
            )
            return {
                'articles_processed': 0,
                'tags_consolidated': 0,
                'tags_added': 0,
                'original_tag_count': 0,
                'final_tag_count': 0,
            }

        logger.info('Pipeline initiating tag consolidation and re-tagging process.')

        try:
            # Step 1: Extract all existing tags
            existing_tags = self.tag_consolidator.extract_all_tags_from_graph(
                self.citation_tracker
            )
            if not existing_tags:
                logger.warning('No existing tags found in the citation graph')
                return {
                    'articles_processed': 0,
                    'tags_consolidated': 0,
                    'tags_added': 0,
                    'original_tag_count': 0,
                    'final_tag_count': 0,
                }

            # Step 2: Consolidate tags
            consolidation_response = self.tag_consolidator.consolidate_tags(
                existing_tags
            )
            all_available_tags = consolidation_response.consolidated_tags

            # Step 3: Process each article
            articles_processed = 0
            articles_updated = 0
            total_tags_added = 0

            for article_id, node_data in self.citation_tracker.graph.nodes(data=True):
                analysis_dict = node_data.get('analysis')
                metadata = node_data.get('metadata', {})

                if not analysis_dict:
                    logger.debug(
                        f'No analysis data found for article {article_id}, skipping'
                    )
                    continue

                # Get article info
                title = metadata.get('title', article_id)
                abstract = analysis_dict.get('abstract', '')
                current_tags = analysis_dict.get('tags', [])

                # Step 3a: Apply tag consolidation mappings to current tags
                updated_tags = []
                for tag in current_tags or []:
                    canonical_tag = consolidation_response.tag_mappings.get(tag, tag)
                    updated_tags.append(canonical_tag)

                # Step 3b: Suggest additional tags if we have an abstract
                additional_tags = []
                if abstract and all_available_tags:
                    try:
                        suggestion_response = (
                            self.tag_consolidator.suggest_additional_tags(
                                title=title,
                                abstract=abstract,
                                current_tags=updated_tags,
                                available_tags=all_available_tags,
                            )
                        )
                        additional_tags = suggestion_response.suggested_tags
                        total_tags_added += len(additional_tags)
                    except Exception as e:
                        logger.warning(
                            f'Failed to suggest tags for article {article_id}: {e}'
                        )

                # Step 3c: Combine and deduplicate tags
                final_tags = list(dict.fromkeys(updated_tags + additional_tags))

                # Step 3d: Update the analysis with new tags
                if final_tags != current_tags:
                    analysis_dict['tags'] = final_tags
                    articles_updated += 1
                    logger.info(
                        f'Updated tags for "{title}": {len(current_tags or [])} -> {len(final_tags)} tags'
                    )

                articles_processed += 1

                # Step 3e: Save the updated graph
                if articles_updated > 0:
                    self.citation_tracker._save_graph()
                    logger.info('Saved updated citation graph with consolidated tags')

            # Step 5: Return summary statistics
            stats = {
                'articles_processed': articles_processed,
                'articles_updated': articles_updated,
                'tags_consolidated': len(consolidation_response.tag_mappings),
                'tags_added': total_tags_added,
                'original_tag_count': len(existing_tags),
                'final_tag_count': len(all_available_tags),
                'consolidation_mappings': consolidation_response.tag_mappings,
                'all_available_tags': all_available_tags,
                'total_vocabulary_size': len(all_available_tags),
            }

            logger.info(
                f'Pipeline completed tag consolidation and re-tagging. '
                f'Processed {articles_processed} articles, '
                f'updated {articles_updated} articles, '
                f'consolidated {len(consolidation_response.tag_mappings)} tags, '
                f'added {total_tags_added} new tags.'
            )

            return stats

        except Exception as e:
            logger.error(f'Tag consolidation and re-tagging failed: {e}')
            raise PipelineError(f'Tag consolidation and re-tagging failed: {e}') from e


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
