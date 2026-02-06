"""
Processing service for managing document processing pipeline.

This module consolidates all document processing operations including
OCR, content analysis, citation extraction, and note generation.
"""

import warnings
from pathlib import Path
from typing import Any

from mistralai import DocumentURLChunk, Mistral
from mistralai.models import OCRResponse, UploadFileOut
from pypdf import PdfReader

from thoth.analyze.llm_processor import LLMProcessor
from thoth.services.analysis_schema_service import AnalysisSchemaService
from thoth.services.base import BaseService, ServiceError
from thoth.services.llm_service import LLMService
from thoth.utilities.schemas import AnalysisResponse


class ProcessingService(BaseService):
    """
    Service for managing document processing operations.

    This service consolidates:
    - OCR processing for PDFs
    - Content analysis with LLM
    - Document format conversions
    - Processing pipeline orchestration
    """

    def __init__(
        self,
        config=None,
        mistral_client: Mistral | None = None,
        llm_service: LLMService | None = None,
    ):
        """
        Initialize the ProcessingService.

        Args:
            config: Optional configuration object
            mistral_client: Optional Mistral client for OCR
            llm_service: Optional LLM service
        """
        super().__init__(config)
        self._mistral_client = mistral_client
        self._llm_service = llm_service
        self._ocr_service = None
        self._citation_service = None
        self._analysis_schema_service = None

    def _save_markdown_to_postgres(
        self, paper_title: str, markdown_content: str
    ) -> None:
        """Save markdown content directly to PostgreSQL.

        This inserts/updates paper_metadata first, then processed_papers,
        since 'papers' is a VIEW and cannot be directly inserted into.
        """
        import asyncpg  # noqa: I001
        import asyncio

        db_url = (
            getattr(self.config.secrets, 'database_url', None)
            if hasattr(self.config, 'secrets')
            else None
        )
        if not db_url:
            raise ValueError('DATABASE_URL not configured - PostgreSQL is required')

        async def save():
            conn = await asyncpg.connect(db_url)
            try:
                # First, check if paper exists in paper_metadata by title
                paper_id = await conn.fetchval(
                    "SELECT id FROM paper_metadata WHERE LOWER(title) = LOWER($1)",
                    paper_title,
                )

                if paper_id is None:
                    # Insert new paper_metadata record
                    # Normalize title by replacing hyphens with spaces
                    title_normalized = paper_title.lower().replace('-', ' ')
                    paper_id = await conn.fetchval(
                        """
                        INSERT INTO paper_metadata (title, title_normalized, source_of_truth, created_at, updated_at)
                        VALUES ($1, $2, 'processed', NOW(), NOW())
                        RETURNING id
                        """,
                        paper_title,
                        title_normalized,
                    )
                else:
                    # Update existing paper_metadata timestamp
                    await conn.execute(
                        "UPDATE paper_metadata SET updated_at = NOW() WHERE id = $1",
                        paper_id,
                    )

                if paper_id:
                    # Then insert/update processed_papers with markdown_content
                    await conn.execute(
                        """
                        INSERT INTO processed_papers (paper_id, markdown_content, created_at, updated_at)
                        VALUES ($1, $2, NOW(), NOW())
                        ON CONFLICT (paper_id) DO UPDATE SET
                            markdown_content = EXCLUDED.markdown_content,
                            updated_at = NOW()
                        """,
                        paper_id,
                        markdown_content,
                    )
            finally:
                await conn.close()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running, create one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(save())
            loop.close()
        else:
            # Already have a running loop
            asyncio.create_task(save())

    @property
    def mistral_client(self) -> Mistral:
        """Get or create the Mistral client for OCR."""
        if self._mistral_client is None:
            if not self.config.api_keys.mistral_key:
                raise ServiceError('Mistral API key not configured')
            self._mistral_client = Mistral(api_key=self.config.api_keys.mistral_key)
        return self._mistral_client

    @property
    def llm_service(self) -> LLMService:
        """Get or create the LLM service."""
        if self._llm_service is None:
            self._llm_service = LLMService(self.config)
        return self._llm_service
    
    @property
    def analysis_schema_service(self) -> AnalysisSchemaService:
        """Get or create the analysis schema service."""
        if self._analysis_schema_service is None:
            self._analysis_schema_service = AnalysisSchemaService(self.config)
            self._analysis_schema_service.initialize()
        return self._analysis_schema_service

    def initialize(self) -> None:
        """Initialize the processing service."""
        self.logger.debug('Processing service initialized')

    def ocr_convert(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> tuple[Path, Path]:
        """
        Convert a PDF file to markdown using OCR.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Optional output directory

        Returns:
            tuple[Path, Path]: Paths to the full markdown and no-images markdown

        Raises:
            ServiceError: If OCR conversion fails
        """
        # Issue deprecation warning for standard OCR processing
        warnings.warn(
            'Using ProcessingService.ocr_convert (standard OCR). '
            'For better performance, consider using AsyncProcessingService.ocr_convert_async '
            'which provides async I/O, caching, and 50-65% faster processing. '
            "Available through OptimizedDocumentPipeline or 'thoth performance' commands.",
            DeprecationWarning,
            stacklevel=2,
        )

        try:
            self.validate_input(pdf_path=pdf_path)

            if not pdf_path.exists():
                raise ServiceError(f'PDF file not found: {pdf_path}')

            if output_dir is None:
                output_dir = self.config.markdown_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            if not self.config.api_keys.mistral_key:
                self.logger.info('Using local PDF to markdown conversion')
                return self._local_pdf_to_markdown(pdf_path, output_dir)

            self.logger.debug(f'Uploading PDF for OCR: {pdf_path}')
            uploaded_file = self._upload_file_to_mistral(pdf_path)

            signed_url_obj = self.mistral_client.files.get_signed_url(
                file_id=uploaded_file.id, expiry=1
            )
            signed_url = signed_url_obj.url

            self.logger.debug('Processing with Mistral OCR')
            ocr_response = self._call_mistral_ocr(signed_url)

            combined_markdown = self._get_combined_markdown(ocr_response)  # noqa: F841
            output_path = output_dir / f'{pdf_path.stem}.md'

            no_images_markdown = self._join_markdown_pages(ocr_response)
            no_images_output_path = output_dir / f'{pdf_path.stem}_no_images.md'

            # Save to both disk and PostgreSQL
            no_images_output_path.write_text(no_images_markdown)
            self._save_markdown_to_postgres(pdf_path.stem, no_images_markdown)
            self.logger.info(f'Saved markdown to PostgreSQL for {pdf_path.stem}')

            self.log_operation(
                'ocr_completed',
                pdf=str(pdf_path),
                markdown=str(output_path),
                no_images=str(no_images_output_path),
            )

            return output_path, no_images_output_path

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"OCR conversion of '{pdf_path}'")
            ) from e

    def process_pdf_to_markdown(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
    ) -> tuple[Path, Path]:
        """
        Process a PDF file to markdown using OCR.

        This is an alias for ocr_convert for backward compatibility.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Optional output directory

        Returns:
            tuple[Path, Path]: Paths to the copied PDF and generated markdown

        Raises:
            ServiceError: If processing fails
        """
        try:
            # Set output directory
            if output_dir is None:
                output_dir = self.config.markdown_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            # Copy PDF to output directory if needed
            pdf_output_path = output_dir / pdf_path.name
            if pdf_path != pdf_output_path:
                import shutil

                shutil.copy2(pdf_path, pdf_output_path)

            # Convert to markdown
            _, no_images_markdown_path = self.ocr_convert(pdf_output_path, output_dir)

            return pdf_output_path, no_images_markdown_path

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"processing PDF '{pdf_path}'")
            ) from e

    def analyze_content(
        self,
        content: str | Path,
        force_strategy: str | None = None,
    ) -> AnalysisResponse:
        """
        Analyze document content using LLM.

        Args:
            content: Document content or path to markdown file
            force_strategy: Force specific processing strategy

        Returns:
            AnalysisResponse: Analysis results

        Raises:
            ServiceError: If analysis fails
        """
        try:
            self.validate_input(content=content)

            # Read content if path provided
            if isinstance(content, Path):
                if not content.exists():
                    raise ServiceError(f'File not found: {content}')
                content = content.read_text(encoding='utf-8')

            # Get analysis model and custom instructions from schema service
            analysis_model = self.analysis_schema_service.get_active_model()
            custom_instructions = self.analysis_schema_service.get_preset_instructions()
            
            # Analyze content
            self.logger.info(f'Analyzing content with LLM using schema: {self.analysis_schema_service.get_active_preset_name()}')
            self.llm_processor = LLMProcessor(
                llm_service=self.llm_service,
                model=self.config.llm_config.model,
                prompts_dir=self.config.prompts_dir,
                max_output_tokens=self.config.llm_config.max_output_tokens,
                max_context_length=self.config.llm_config.max_context_length,
                chunk_size=self.config.llm_config.chunk_size,
                chunk_overlap=self.config.llm_config.chunk_overlap,
                model_kwargs=self.config.llm_config.model_settings.model_dump(),
                analysis_model=analysis_model,
                custom_instructions=custom_instructions,
            )
            analysis = self.llm_processor.analyze_content(
                content,
                force_processing_strategy=force_strategy,
            )

            self.log_operation(
                'content_analyzed',
                strategy=force_strategy or 'auto',
            )

            return analysis

        except Exception as e:
            raise ServiceError(self.handle_error(e, 'analyzing content')) from e

    def analyze_document(self, markdown_path: Path) -> AnalysisResponse:
        """
        Analyze a markdown document.

        This is an alias for analyze_content for backward compatibility.

        Args:
            markdown_path: Path to the markdown file

        Returns:
            AnalysisResponse: Analysis results
        """
        return self.analyze_content(markdown_path)

    def _upload_file_to_mistral(self, pdf_path: Path) -> UploadFileOut:
        """Upload a PDF file to Mistral."""
        uploaded_file = self.mistral_client.files.upload(
            file={
                'file_name': pdf_path.stem,
                'content': pdf_path.read_bytes(),
            },
            purpose='ocr',
        )
        return uploaded_file

    def _call_mistral_ocr(self, signed_url: str) -> dict[str, Any]:
        """Call the Mistral OCR API."""
        response = self.mistral_client.ocr.process(
            document=DocumentURLChunk(document_url=signed_url),
            model='mistral-ocr-latest',
            include_image_base64=True,
        )
        return response

    def _join_markdown_pages(self, ocr_response: OCRResponse) -> str:
        """Join the markdown pages into a single markdown document without image references."""
        import re
        
        combined = '\n\n'.join(page.markdown for page in ocr_response.pages)
        
        # Strip image references: ![alt](url) or ![alt][ref]
        image_pattern = r'!\[[^\]]*\]\([^)]+\)|!\[[^\]]*\]\[[^\]]*\]'
        combined = re.sub(image_pattern, '', combined)
        
        # Clean up multiple consecutive newlines left by removed images
        combined = re.sub(r'\n{3,}', '\n\n', combined)
        
        return combined.strip()

    def _get_combined_markdown(self, ocr_response: OCRResponse) -> str:
        """Combine OCR text and images into a single markdown document."""
        markdowns: list[str] = []
        for page in ocr_response.pages:
            image_data = {}
            for img in page.images:
                image_data[img.id] = img.image_base64
            markdowns.append(
                self._replace_images_in_markdown(page.markdown, image_data)
            )
        return '\n\n'.join(markdowns)

    def _replace_images_in_markdown(self, markdown_str: str, images_dict: dict) -> str:
        """Replace image placeholders in markdown with base64-encoded images."""
        for img_name, base64_str in images_dict.items():
            markdown_str = markdown_str.replace(
                f'![{img_name}]({img_name})', f'![{img_name}]({base64_str})'
            )
        return markdown_str

    def _local_pdf_to_markdown(
        self, pdf_path: Path, output_dir: Path
    ) -> tuple[Path, Path]:
        """Fallback local PDF to markdown conversion using PyPDF."""
        reader = PdfReader(str(pdf_path))
        markdown_pages: list[str] = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ''
            markdown_pages.append(f'## Page {i}\n\n{text.strip()}')

        markdown_content = '\n\n'.join(markdown_pages).strip()
        output_path = output_dir / f'{pdf_path.stem}.md'
        output_path.write_text(markdown_content)

        no_images_output_path = output_dir / f'{pdf_path.stem}_no_images.md'
        no_images_output_path.write_text(markdown_content)

        return output_path, no_images_output_path

    def extract_metadata(
        self,
        content: str,
        metadata_type: str = 'basic',
    ) -> dict[str, Any]:
        """
        Extract metadata from document content.

        Args:
            content: Document content
            metadata_type: Type of metadata to extract

        Returns:
            dict[str, Any]: Extracted metadata

        Raises:
            ServiceError: If extraction fails
        """
        try:
            metadata = {}

            if metadata_type == 'basic':
                # Extract basic metadata using regex
                import re

                # Extract title (first heading)
                title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                if title_match:
                    metadata['title'] = title_match.group(1).strip()

                # Extract authors (common patterns)
                author_patterns = [
                    r'(?:Authors?|By):\s*(.+?)(?:\n|$)',
                    r'^\*\*Authors?\*\*:\s*(.+?)(?:\n|$)',
                ]
                for pattern in author_patterns:
                    author_match = re.search(
                        pattern, content, re.MULTILINE | re.IGNORECASE
                    )
                    if author_match:
                        authors_text = author_match.group(1)
                        # Split by common separators
                        authors = re.split(r'[,;]|\sand\s', authors_text)
                        metadata['authors'] = [a.strip() for a in authors if a.strip()]
                        break

                # Extract date
                date_match = re.search(
                    r'(?:Date|Published):\s*(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})',
                    content,
                    re.IGNORECASE,
                )
                if date_match:
                    metadata['date'] = date_match.group(1)

            elif metadata_type == 'full':
                # Use LLM for comprehensive metadata extraction
                # This would require a specific prompt and model
                pass

            self.log_operation(
                'metadata_extracted',
                type=metadata_type,
                fields=list(metadata.keys()),
            )

            return metadata

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f'extracting {metadata_type} metadata')
            ) from e

    def validate_analysis(
        self,
        analysis: AnalysisResponse,
        required_fields: list[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """
        Validate analysis results.

        Args:
            analysis: Analysis response to validate
            required_fields: List of required fields

        Returns:
            tuple[bool, list[str]]: (is_valid, missing_fields)
        """
        try:
            if required_fields is None:
                required_fields = ['abstract', 'summary', 'key_points']

            missing_fields = []
            for field in required_fields:
                value = getattr(analysis, field, None)
                if not value or (isinstance(value, str) and not value.strip()):
                    missing_fields.append(field)

            is_valid = len(missing_fields) == 0

            self.log_operation(
                'analysis_validated',
                valid=is_valid,
                missing_fields=missing_fields,
            )

            return is_valid, missing_fields

        except Exception as e:
            self.logger.error(self.handle_error(e, 'validating analysis'))
            return False, ['validation_error']

    def get_processing_stats(self) -> dict[str, Any]:
        """
        Get processing statistics.

        Returns:
            dict[str, Any]: Processing statistics
        """
        try:
            # This would aggregate stats from various sources
            stats = {
                'ocr_available': bool(self.config.api_keys.mistral_key),
                'llm_model': self.config.llm_config.model,
                'max_context_length': self.config.llm_config.max_context_length,
                'chunk_size': self.config.llm_config.chunk_size,
            }

            return stats

        except Exception as e:
            self.logger.error(self.handle_error(e, 'getting processing stats'))
            return {}

    def health_check(self) -> dict[str, str]:
        """Basic health status for the ProcessingService."""
        return super().health_check()
