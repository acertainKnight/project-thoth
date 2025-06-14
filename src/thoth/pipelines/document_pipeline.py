from __future__ import annotations

from pathlib import Path

from loguru import logger

from thoth.utilities.schemas import Citation

from .base import BasePipeline


class DocumentPipeline(BasePipeline):
    """Pipeline for processing individual documents."""

    def process_pdf(self, pdf_path: str | Path) -> tuple[Path, Path, Path]:
        """Process a PDF through OCR, analysis, citation extraction and note
        generation."""
        pdf_path = Path(pdf_path)
        self.logger.info(f'Processing PDF: {pdf_path}')

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

        analysis = self._analyze_content(no_images_markdown)
        self.logger.info('Content analysis completed')

        citations = self._extract_citations(no_images_markdown)
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

        try:
            self._index_to_rag(new_markdown_path)
            self._index_to_rag(Path(note_path))
        except Exception as e:  # pragma: no cover - optional integration
            self.logger.warning(f'Failed to index documents to RAG system: {e}')

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
