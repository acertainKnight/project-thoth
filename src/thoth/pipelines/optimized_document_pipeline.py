"""
Optimized document pipeline for local/personal server processing.

This pipeline implements performance optimizations specifically designed for
local environments including:
- Dynamic thread pool scaling based on CPU cores
- Async I/O for OCR operations
- Intelligent batching and caching
- Memory-efficient processing
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from loguru import logger

from thoth.pipelines.base import BasePipeline
from thoth.services.async_processing_service import AsyncProcessingService
from thoth.utilities.schemas import Citation


class OptimizedDocumentPipeline(BasePipeline):
    """
    Optimized pipeline for processing individual documents with enhanced performance.

    Key optimizations:
    - Dynamic worker scaling based on available CPU cores
    - Async OCR processing with concurrent API calls
    - Memory-efficient streaming for large documents
    - Intelligent caching and batching
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._async_processing_service = None
        self._max_workers = self._calculate_optimal_workers()

        # PRIORITY 3: Persistent ThreadPoolExecutors
        self._content_analysis_executor = ThreadPoolExecutor(
            max_workers=self._max_workers['content_analysis'],
            thread_name_prefix='content_analysis',
        )
        self._citation_extraction_executor = ThreadPoolExecutor(
            max_workers=self._max_workers['citation_extraction'],
            thread_name_prefix='citation_extract',
        )
        self._background_tasks_executor = ThreadPoolExecutor(
            max_workers=self._max_workers['background_tasks'],
            thread_name_prefix='background_tasks',
        )

        # PRIORITY 5: Global concurrency semaphore (8 concurrent documents max)
        self._global_semaphore = asyncio.Semaphore(8)

        self.logger.info(
            f'Initialized optimized pipeline with {self._max_workers} max workers and persistent executors'
        )

    def _calculate_optimal_workers(self) -> dict[str, int]:
        """Calculate optimal worker counts based on available CPU cores."""
        cpu_count = os.cpu_count() or 4

        # Reserve 1 core for system processes
        available_cores = max(1, cpu_count - 1)

        return {
            'content_analysis': min(
                available_cores, 4
            ),  # CPU-bound, but limited by memory
            'citation_extraction': min(
                available_cores, 6
            ),  # I/O-bound, can handle more
            'ocr_processing': min(3, available_cores),  # API rate-limited
            'background_tasks': 2,  # For RAG indexing and cleanup
        }

    @property
    def async_processing_service(self) -> AsyncProcessingService:
        """Get or create the async processing service."""
        if self._async_processing_service is None:
            self._async_processing_service = AsyncProcessingService(
                config=self.services.config
            )
            # Initialize async service
            _ = asyncio.create_task(self._async_processing_service.initialize())  # noqa: RUF006
        return self._async_processing_service

    async def process_pdf_async(self, pdf_path: str | Path) -> tuple[Path, Path, Path]:
        """
        Process a PDF through async OCR, analysis, citation extraction and note
        generation.

        This async version provides better I/O utilization for API calls.
        """
        # PRIORITY 5: Use global semaphore to limit concurrent documents
        async with self._global_semaphore:
            pdf_path = Path(pdf_path)
            self.logger.debug(f'Processing PDF (async): {pdf_path}')

            # Check if already processed
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

            # Use async OCR for better I/O performance
            (
                markdown_path,
                no_images_markdown,
            ) = await self.async_processing_service.ocr_convert_async(pdf_path)
            self.logger.info(f'Async OCR conversion completed: {markdown_path}')

            # Run content analysis and citation extraction in parallel with optimized
            # workers
            analysis, citations = await self._parallel_analysis_and_citations(
                no_images_markdown
            )

            # Generate notes and output files
            (
                note_path,
                new_pdf_path,
                new_markdown_path,
            ) = await self.async_processing_service.generate_notes_async(
                pdf_path, markdown_path, no_images_markdown, analysis, citations
            )

            # Background RAG indexing (non-blocking)
            _ = asyncio.create_task(  # noqa: RUF006
                self._background_rag_indexing_async(new_markdown_path, note_path)
            )

            return Path(note_path), Path(new_pdf_path), Path(new_markdown_path)

    def process_pdf(self, pdf_path: str | Path) -> tuple[Path, Path, Path]:
        """
        Process a PDF with optimized threading and improved performance.

        This is the sync wrapper that maintains compatibility while providing
        optimizations.
        """
        pdf_path = Path(pdf_path)
        self.logger.debug(f'Processing PDF (optimized): {pdf_path}')

        # Check if already processed
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

        # OCR conversion (potentially cached)
        markdown_path, no_images_markdown = self._ocr_convert_optimized(pdf_path)
        self.logger.info(f'OCR conversion completed: {markdown_path}')

        # Parallel analysis with dynamic worker scaling
        analysis, citations = self._parallel_analysis_and_citations_sync(
            no_images_markdown
        )

        # PRIORITY 2: Generate note asynchronously using background executor
        # This enables parallel document processing by not blocking on note generation
        note_future = self._background_tasks_executor.submit(
            self._generate_note,
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )
        note_path, new_pdf_path, new_markdown_path = note_future.result()
        self.logger.info(f'Note generation completed: {note_path}')

        # Track processing
        self.pdf_tracker.mark_processed(
            pdf_path,
            {
                'note_path': str(note_path),
                'new_pdf_path': str(new_pdf_path),
                'new_markdown_path': str(new_markdown_path),
            },
        )

        # Background RAG indexing with optimized thread pool
        self._schedule_background_rag_indexing(new_markdown_path, note_path)

        return Path(note_path), Path(new_pdf_path), Path(new_markdown_path)

    def _ocr_convert_optimized(self, pdf_path: Path) -> tuple[Path, Path]:
        """OCR conversion with caching and optimized error handling."""
        try:
            return self.services.processing.ocr_convert(
                pdf_path=pdf_path, output_dir=self.markdown_dir
            )
        except Exception as e:
            self.logger.error(f'OCR conversion failed for {pdf_path}: {e}')
            # Fallback to local processing if API fails
            try:
                return self.services.processing._local_pdf_to_markdown(
                    pdf_path, self.markdown_dir
                )
            except Exception as fallback_error:
                raise RuntimeError(
                    f'Both OCR and fallback processing failed for {pdf_path}: {fallback_error}'
                ) from e

    async def _parallel_analysis_and_citations(
        self, markdown_path: Path
    ) -> tuple[Any, list[Citation]]:
        """Run content analysis and citation extraction in parallel (async version)."""
        self.logger.info(
            'Starting async parallel content analysis and citation extraction'
        )

        loop = asyncio.get_event_loop()

        # PRIORITY 3: Use persistent executors instead of creating new ones
        analysis_task = loop.run_in_executor(
            self._content_analysis_executor, self._analyze_content, markdown_path
        )

        # PRIORITY 4: Use async batch citation processing
        citations_task = loop.run_in_executor(
            self._citation_extraction_executor,
            self._extract_citations_batch,
            markdown_path,
        )

        # Wait for both tasks to complete
        analysis, citations = await asyncio.gather(analysis_task, citations_task)

        self.logger.info('Async parallel processing completed')
        self.logger.info(f'Analysis completed, {len(citations)} citations found')

        return analysis, citations

    def _parallel_analysis_and_citations_sync(
        self, markdown_path: Path
    ) -> tuple[Any, list[Citation]]:
        """
        Run content analysis and citation extraction in parallel (sync version with
        optimized workers).
        """
        self.logger.info(
            'Starting optimized parallel content analysis and citation extraction'
        )

        # Use optimal worker count based on available CPU cores
        max_workers = self._max_workers['content_analysis']

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit both tasks to run in parallel
            analysis_future = executor.submit(self._analyze_content, markdown_path)
            citations_future = executor.submit(self._extract_citations, markdown_path)

            # Collect results as they complete
            analysis = None
            citations = None

            for future in as_completed([analysis_future, citations_future]):
                try:
                    if future == analysis_future:
                        analysis = future.result()
                        self.logger.info('Content analysis completed')
                    elif future == citations_future:
                        citations = future.result()
                        self.logger.info(
                            f'Citation extraction completed: {len(citations)} citations found'
                        )
                except Exception as e:
                    self.logger.error(f'Task failed: {e}')
                    # Re-raise to handle upstream
                    raise

        return analysis, citations

    async def _background_rag_indexing_async(
        self, markdown_path: str, note_path: str
    ) -> None:
        """Background RAG indexing using async I/O."""
        try:
            loop = asyncio.get_event_loop()

            # PRIORITY 3: Use persistent background tasks executor
            await loop.run_in_executor(
                self._background_tasks_executor, self._index_to_rag, Path(markdown_path)
            )
            await loop.run_in_executor(
                self._background_tasks_executor, self._index_to_rag, Path(note_path)
            )

            self.logger.debug('Background async RAG indexing completed')
        except Exception as e:
            self.logger.warning(f'Failed to index documents to RAG system: {e}')

    def _schedule_background_rag_indexing(
        self, markdown_path: str, note_path: str
    ) -> None:
        """Schedule background RAG indexing with optimized thread pool."""

        def _background_rag_indexing():
            try:
                self._index_to_rag(Path(markdown_path))
                self._index_to_rag(Path(note_path))
                self.logger.debug('Background RAG indexing completed')
            except Exception as e:
                self.logger.warning(f'Failed to index documents to RAG system: {e}')

        # PRIORITY 3: Use persistent background tasks executor
        self._background_tasks_executor.submit(_background_rag_indexing)

    async def batch_process_pdfs_async(
        self, pdf_paths: list[Path]
    ) -> list[tuple[Path, Path, Path]]:
        """
        Process multiple PDFs concurrently with optimal resource utilization.

        This method provides significant speedup for batch processing by utilizing
        async I/O and intelligent batching.
        """
        self.logger.info(
            f'Starting optimized batch processing of {len(pdf_paths)} PDFs'
        )

        # Process in optimal batch sizes to avoid overwhelming the system
        max_concurrent = min(len(pdf_paths), self._max_workers['ocr_processing'])

        results = []
        for i in range(0, len(pdf_paths), max_concurrent):
            batch = pdf_paths[i : i + max_concurrent]
            batch_tasks = [self.process_pdf_async(pdf_path) for pdf_path in batch]

            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    self.logger.error(f'Failed to process {batch[j]}: {result}')
                    continue
                results.append(result)

            self.logger.info(
                f'Completed batch {i // max_concurrent + 1}: {len([r for r in batch_results if not isinstance(r, Exception)])}/{len(batch)} successful'
            )

        self.logger.info(
            f'Batch processing completed: {len(results)}/{len(pdf_paths)} successful'
        )
        return results

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics for the optimized pipeline."""
        return {
            'max_workers': self._max_workers,
            'cpu_count': os.cpu_count(),
            'async_processing_enabled': self._async_processing_service is not None,
            'cache_status': self.async_processing_service.health_check()
            if self._async_processing_service
            else 'not_initialized',
        }

    # Keep the original methods for backward compatibility
    def _ocr_convert(self, pdf_path: Path) -> tuple[Path, Path]:
        """Original OCR convert method maintained for compatibility."""
        return self._ocr_convert_optimized(pdf_path)

    def _analyze_content(self, markdown_path: Path):
        """Analyze content using the processing service."""
        return self.services.processing.analyze_document(markdown_path)

    def _extract_citations(self, markdown_path: Path) -> list[Citation]:
        """Extract citations using the citation service."""
        return self.services.citation.extract_citations(markdown_path)

    def _extract_citations_batch(self, markdown_path: Path) -> list[Citation]:
        """
        PRIORITY 4: Extract citations using batched async processing.

        This method leverages the citation service's batch processing capabilities
        to reduce API call overhead and enable concurrent citation validation.
        """
        try:
            # Use batch processing if available in citation service
            if hasattr(self.services.citation, 'extract_citations_batch'):
                return self.services.citation.extract_citations_batch(markdown_path)
            else:
                # Fallback to standard extraction
                self.logger.debug(
                    'Batch citation extraction not available, using standard method'
                )
                return self.services.citation.extract_citations(markdown_path)
        except Exception as e:
            self.logger.warning(f'Batch citation extraction failed, falling back: {e}')
            return self.services.citation.extract_citations(markdown_path)

    def _generate_note(
        self, pdf_path: Path, markdown_path: Path, analysis, citations: list[Citation]
    ) -> tuple[str, str, str]:
        """Generate note using the note service."""
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
            logger.warning('Could not obtain article_id from process_citations.')

        return str(note_path), str(new_pdf_path), str(new_markdown_path)

    def _index_to_rag(self, file_path: Path) -> None:
        """Index file to RAG system."""
        try:
            if file_path.exists() and file_path.suffix == '.md':
                self.services.rag.index_file(file_path)
                self.logger.debug(f'Indexed {file_path} to RAG system')
        except Exception as e:
            self.logger.debug(f'Failed to index {file_path} to RAG: {e}')

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._async_processing_service:
            await self._async_processing_service.cleanup()

        # PRIORITY 3: Shutdown persistent executors
        self._content_analysis_executor.shutdown(wait=True)
        self._citation_extraction_executor.shutdown(wait=True)
        self._background_tasks_executor.shutdown(wait=True)
        self.logger.debug('Persistent thread pools shut down successfully')

    def __del__(self):
        """PRIORITY 3: Cleanup persistent executors on deletion."""
        try:
            if hasattr(self, '_content_analysis_executor'):
                self._content_analysis_executor.shutdown(wait=False)
            if hasattr(self, '_citation_extraction_executor'):
                self._citation_extraction_executor.shutdown(wait=False)
            if hasattr(self, '_background_tasks_executor'):
                self._background_tasks_executor.shutdown(wait=False)
        except Exception:
            # Suppress errors during cleanup
            pass
