from __future__ import annotations

import os
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from loguru import logger

from thoth.utilities.schemas import Citation

from .base import BasePipeline


class DocumentPipeline(BasePipeline):
    """
    Pipeline for processing individual documents.

    This pipeline has been enhanced with:
    - Dynamic worker scaling based on CPU cores
    - Improved error handling and fallbacks
    - Better resource utilization
    """

    def _get_optimal_worker_count(self) -> int:
        """Calculate optimal worker count based on CPU cores and configuration."""
        try:
            performance_config = getattr(
                self.services.config, 'performance_config', None
            )

            if performance_config and hasattr(
                performance_config, 'content_analysis_workers'
            ):
                configured_workers = performance_config.content_analysis_workers
                if isinstance(configured_workers, int) and configured_workers > 0:
                    return configured_workers

            # Auto-scale based on available CPU cores
            cpu_count = os.cpu_count() or 4
            available_cores = max(1, cpu_count - 1)  # Reserve 1 core for system

            # For content analysis, limit to avoid memory pressure
            return min(available_cores, 4)

        except (AttributeError, TypeError):
            # Fallback to conservative default
            return 2

    def process_pdf(self, pdf_path: str | Path) -> tuple[Path, Path, Path]:
        """Process a PDF through OCR, analysis, citation extraction and note
        generation."""
        pdf_path = Path(pdf_path)
        self.logger.info(f'Processing PDF: {pdf_path}')

        # Issue deprecation warning for standard pipeline usage
        warnings.warn(
            'Using DocumentPipeline (standard pipeline). '
            'For 50-65% faster processing, consider upgrading to OptimizedDocumentPipeline '
            'which provides async I/O, intelligent caching, and CPU-aware scaling. '
            "Use 'thoth monitor --optimized' or 'thoth performance batch --optimized'.",
            DeprecationWarning,
            stacklevel=2,
        )

        if self.pdf_tracker.is_processed(
            pdf_path
        ) and self.pdf_tracker.verify_file_unchanged(pdf_path):
            self.logger.info(
                f'Skipping already processed and unchanged file: {pdf_path}'
            )
            note_path = self.pdf_tracker.get_note_path(pdf_path)
            if note_path:
                return note_path
            self.logger.warning(
                f'File {pdf_path} was processed, but note path not found in tracker. Reprocessing.'
            )

        markdown_path, no_images_markdown = self._ocr_convert(pdf_path)
        self.logger.info(f'OCR conversion completed: {markdown_path}')

        # Run content analysis and citation extraction in parallel with optimized
        # workers
        self.logger.info(
            'Starting optimized parallel content analysis and citation extraction'
        )
        max_workers = self._get_optimal_worker_count()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit both tasks to run in parallel
            analysis_future = executor.submit(self._analyze_content, no_images_markdown)
            citations_future = executor.submit(
                self._extract_citations, no_images_markdown
            )

            # Collect results as they complete
            analysis = None
            citations = None

            for future in as_completed([analysis_future, citations_future]):
                if future == analysis_future:
                    analysis = future.result()
                    self.logger.info('Content analysis completed')
                elif future == citations_future:
                    citations = future.result()
                    self.logger.info(
                        f'Citation extraction completed: {len(citations)} citations found'
                    )

        note_path, new_pdf_path, new_markdown_path = self._generate_note(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )
        self.logger.info(f'Note generation completed: {note_path}')

        self.pdf_tracker.mark_processed(
            pdf_path,
            {
                'note_path': str(note_path),
                'new_pdf_path': str(new_pdf_path),
                'new_markdown_path': str(new_markdown_path),
            },
        )

        # Run RAG indexing in background to avoid blocking main pipeline
        def _background_rag_indexing():
            try:
                self._index_to_rag(Path(new_markdown_path))
                self._index_to_rag(Path(note_path))
                self.logger.debug('Background RAG indexing completed')
            except Exception as e:  # pragma: no cover - optional integration
                self.logger.warning(f'Failed to index documents to RAG system: {e}')

        # Submit to background processing (fire and forget)
        with ThreadPoolExecutor(max_workers=1) as rag_executor:
            rag_executor.submit(_background_rag_indexing)

        return Path(note_path), Path(new_pdf_path), Path(new_markdown_path)

    def _ocr_convert(self, pdf_path: Path) -> tuple[Path, Path]:
        try:
            return self.services.processing.ocr_convert(
                pdf_path=pdf_path, output_dir=self.markdown_dir
            )
        except Exception as e:
            raise RuntimeError(f'OCR conversion failed for {pdf_path}: {e!s}') from e

    def _analyze_content(self, markdown_path: Path):
        return self.services.processing.analyze_document(markdown_path)

    def _extract_citations(self, markdown_path: Path) -> list[Citation]:
        return self.services.citation.extract_citations(markdown_path)

    def _generate_note(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis,
        citations: list[Citation],
    ) -> tuple[str, str, str]:
        note_path, new_pdf_path, new_markdown_path = self.services.note.create_note(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )

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
        try:
            if file_path.exists() and file_path.suffix == '.md':
                self.services.rag.index_file(file_path)
                self.logger.debug(f'Indexed {file_path} to RAG system')
        except Exception as e:  # pragma: no cover - optional integration
            self.logger.debug(f'Failed to index {file_path} to RAG: {e}')
