"""
Pipeline for Thoth.

This module contains the main pipeline that orchestrates the processing of PDF documents:
1. OCR conversion of PDF to Markdown
2. LLM analysis of content
3. Citation extraction and processing
4. Note generation for Obsidian
"""  # noqa: W505

from pathlib import Path

from loguru import logger

from thoth.analyze.citations.citations import CitationProcessor
from thoth.analyze.citations.formatter import CitationFormatter
from thoth.analyze.citations.tracker import CitationTracker
from thoth.analyze.llm_processor import AnalysisResponse, LLMProcessor
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

        # Ensure workspace_dir is not duplicated by removing it from api_keys if present

        self.llm_processor = LLMProcessor(
            model=self.config.llm_config.model,
            max_tokens=self.config.llm_config.max_tokens,
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
        )

        # Note Generator
        self.note_generator = NoteGenerator(
            templates_dir=self.config.templates_dir,
            notes_dir=self.config.notes_dir,
            api_base_url=self.config.api_server_config.base_url,
        )

        logger.info('Thoth pipeline initialized')

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
        markdown_path = self._ocr_convert(pdf_path)
        logger.info(f'OCR conversion completed: {markdown_path}')

        # Step 2: LLM analysis
        analysis = self._analyze_content(markdown_path)
        logger.info('Content analysis completed')

        # Step 3: Citation extraction
        citations = self._extract_citations(markdown_path)
        logger.info(f'Citation extraction completed: {len(citations)} citations found')

        # Step 4: Generate note
        note_path = self._generate_note(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )
        logger.info(f'Note generation completed: {note_path}')

        return Path(note_path)

    def _ocr_convert(self, pdf_path: Path) -> Path:
        """
        Convert PDF to Markdown using OCR.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Path: Path to the generated Markdown file.

        Raises:
            OCRError: If OCR conversion fails.
        """
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
        self.citation_tracker.process_citations(citations)
        return self.citation_formatter.format_citations(citations)

    def _generate_note(
        self,
        pdf_path: Path,
        markdown_path: Path,
        analysis: AnalysisResponse,
        citations: list[Citation],
    ) -> str:
        """
        Generate an Obsidian note.

        Args:
            pdf_path: Path to the PDF file.
            markdown_path: Path to the Markdown file.
            analysis: Analysis results.
            citations: Extracted citations.

        Returns:
            str: Path to the generated note.
        """
        return self.note_generator.create_note(
            pdf_path=pdf_path,
            markdown_path=markdown_path,
            analysis=analysis,
            citations=citations,
        )


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
