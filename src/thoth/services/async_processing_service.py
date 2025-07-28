"""
Async processing service for managing document processing pipeline.

This module provides async versions of document processing operations including
OCR, content analysis, and citation extraction for improved I/O performance.
"""

import asyncio
import hashlib
from pathlib import Path
from typing import Any

import aiohttp
from loguru import logger
from pypdf import PdfReader

from thoth.services.base import BaseService, ServiceError
from thoth.services.llm_service import LLMService

# Optional import for aiofiles - will fallback to sync I/O if not available
try:
    import aiofiles

    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False
    logger.warning('aiofiles not available, falling back to synchronous file I/O')


class AsyncProcessingService(BaseService):
    """
    Async service for managing document processing operations.

    This service provides async versions of:
    - OCR processing for PDFs with concurrent API calls
    - Content analysis with LLM
    - Document format conversions
    - Caching for improved performance
    """

    def __init__(
        self,
        config=None,
        llm_service: LLMService | None = None,
        session: aiohttp.ClientSession | None = None,
    ):
        """
        Initialize the AsyncProcessingService.

        Args:
            config: Optional configuration object
            llm_service: Optional LLM service
            session: Optional aiohttp session for reuse
        """
        super().__init__(config)
        self._llm_service = llm_service
        self._session = session
        self._ocr_cache = {}  # Simple in-memory cache for OCR results
        self._semaphore = asyncio.Semaphore(3)  # Limit concurrent API calls

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=300)  # 5 minutes timeout
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    @property
    def llm_service(self) -> LLMService:
        """Get or create the LLM service."""
        if self._llm_service is None:
            self._llm_service = LLMService(self.config)
        return self._llm_service

    async def initialize(self) -> None:
        """Initialize the async processing service."""
        self.logger.info('Async processing service initialized')

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._session:
            await self._session.close()

    def _get_pdf_hash(self, pdf_path: Path) -> str:
        """Generate hash for PDF file for caching."""
        hasher = hashlib.md5()
        with pdf_path.open('rb') as f:
            # Read file in chunks to handle large files
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    async def ocr_convert_async(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
        use_cache: bool = True,
    ) -> tuple[Path, Path]:
        """
        Convert a PDF file to markdown using async OCR.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Optional output directory
            use_cache: Whether to use OCR result caching

        Returns:
            tuple[Path, Path]: Paths to the full markdown and no-images markdown

        Raises:
            ServiceError: If OCR conversion fails
        """
        try:
            self.validate_input(pdf_path=pdf_path)

            if not pdf_path.exists():
                raise ServiceError(f'PDF file not found: {pdf_path}')

            if output_dir is None:
                output_dir = self.config.markdown_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            # Check cache first
            pdf_hash = self._get_pdf_hash(pdf_path) if use_cache else None
            if pdf_hash and pdf_hash in self._ocr_cache:
                self.logger.info(f'Using cached OCR result for {pdf_path.name}')
                cached_result = self._ocr_cache[pdf_hash]
                return await self._write_cached_result(
                    cached_result, pdf_path, output_dir
                )

            if not self.config.api_keys.mistral_key:
                self.logger.info('Using local PDF to markdown conversion')
                result = await self._local_pdf_to_markdown_async(pdf_path, output_dir)
                if use_cache and pdf_hash:
                    self._cache_ocr_result(pdf_hash, result)
                return result

            # Use async Mistral OCR
            async with self._semaphore:  # Limit concurrent API calls
                result = await self._mistral_ocr_async(pdf_path, output_dir)
                if use_cache and pdf_hash:
                    self._cache_ocr_result(pdf_hash, result)
                return result

        except Exception as e:
            raise ServiceError(
                self.handle_error(e, f"Async OCR conversion of '{pdf_path}'")
            ) from e

    async def _mistral_ocr_async(
        self, pdf_path: Path, output_dir: Path
    ) -> tuple[Path, Path]:
        """Perform async Mistral OCR processing."""
        self.logger.info(f'Starting async OCR for {pdf_path.name}')

        # Upload file
        uploaded_file_id = await self._upload_file_to_mistral_async(pdf_path)

        # Get signed URL
        signed_url = await self._get_signed_url_async(uploaded_file_id)

        # Process OCR
        ocr_response = await self._call_mistral_ocr_async(signed_url)

        # Write results
        output_path = output_dir / f'{pdf_path.stem}.md'
        no_images_output_path = output_dir / f'{pdf_path.stem}_no_images.md'

        combined_markdown = self._get_combined_markdown(ocr_response)
        no_images_markdown = self._join_markdown_pages(ocr_response)

        # Write files asynchronously
        await asyncio.gather(
            self._write_file_async(output_path, combined_markdown),
            self._write_file_async(no_images_output_path, no_images_markdown),
        )

        self.log_operation(
            'async_ocr_completed',
            pdf=str(pdf_path),
            markdown=str(output_path),
            no_images=str(no_images_output_path),
        )

        return output_path, no_images_output_path

    async def _upload_file_to_mistral_async(self, pdf_path: Path) -> str:
        """Upload a PDF file to Mistral asynchronously."""
        self.logger.debug(f'Uploading {pdf_path.name} to Mistral')

        if AIOFILES_AVAILABLE:
            async with aiofiles.open(pdf_path, 'rb') as f:
                file_content = await f.read()
        else:
            # Fallback to sync I/O in thread pool
            loop = asyncio.get_event_loop()
            file_content = await loop.run_in_executor(None, pdf_path.read_bytes)

        data = aiohttp.FormData()
        data.add_field(
            'file', file_content, filename=pdf_path.name, content_type='application/pdf'
        )
        data.add_field('purpose', 'ocr')

        headers = {'Authorization': f'Bearer {self.config.api_keys.mistral_key}'}

        async with self.session.post(
            'https://api.mistral.ai/v1/files', data=data, headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ServiceError(f'Mistral file upload failed: {error_text}')

            result = await response.json()
            return result['id']

    async def _get_signed_url_async(self, file_id: str) -> str:
        """Get signed URL for uploaded file asynchronously."""
        headers = {
            'Authorization': f'Bearer {self.config.api_keys.mistral_key}',
            'Content-Type': 'application/json',
        }

        data = {'expiry': 1}

        async with self.session.post(
            f'https://api.mistral.ai/v1/files/{file_id}/signed-url',
            json=data,
            headers=headers,
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ServiceError(f'Failed to get signed URL: {error_text}')

            result = await response.json()
            return result['url']

    async def _call_mistral_ocr_async(self, signed_url: str) -> dict[str, Any]:
        """Call the Mistral OCR API asynchronously."""
        headers = {
            'Authorization': f'Bearer {self.config.api_keys.mistral_key}',
            'Content-Type': 'application/json',
        }

        data = {
            'document': {'document_url': signed_url},
            'model': 'mistral-ocr-latest',
            'include_image_base64': True,
        }

        async with self.session.post(
            'https://api.mistral.ai/v1/ocr', json=data, headers=headers
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                raise ServiceError(f'Mistral OCR failed: {error_text}')

            return await response.json()

    async def _local_pdf_to_markdown_async(
        self, pdf_path: Path, output_dir: Path
    ) -> tuple[Path, Path]:
        """Fallback local PDF to markdown conversion using PyPDF asynchronously."""
        self.logger.info(f'Converting {pdf_path.name} using local PyPDF')

        def extract_text():
            reader = PdfReader(str(pdf_path))
            markdown_pages = []
            for i, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ''
                markdown_pages.append(f'## Page {i}\n\n{text.strip()}')
            return '\n\n'.join(markdown_pages).strip()

        # Run CPU-bound extraction in thread pool
        loop = asyncio.get_event_loop()
        markdown_content = await loop.run_in_executor(None, extract_text)

        output_path = output_dir / f'{pdf_path.stem}.md'
        no_images_output_path = output_dir / f'{pdf_path.stem}_no_images.md'

        # Write files asynchronously
        await asyncio.gather(
            self._write_file_async(output_path, markdown_content),
            self._write_file_async(no_images_output_path, markdown_content),
        )

        return output_path, no_images_output_path

    async def _write_file_async(self, file_path: Path, content: str) -> None:
        """Write content to file asynchronously."""
        if AIOFILES_AVAILABLE:
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(content)
        else:
            # Fallback to sync I/O in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, file_path.write_text, content)

    def _cache_ocr_result(self, pdf_hash: str, result: tuple[Path, Path]) -> None:
        """Cache OCR result for future use."""
        self._ocr_cache[pdf_hash] = {
            'full_markdown': result[0].read_text(),
            'no_images_markdown': result[1].read_text(),
            'stem': result[0].stem,
        }
        self.logger.debug(f'Cached OCR result for hash {pdf_hash[:8]}...')

    async def _write_cached_result(
        self, cached_result: dict, pdf_path: Path, output_dir: Path
    ) -> tuple[Path, Path]:
        """Write cached OCR result to files."""
        output_path = output_dir / f'{pdf_path.stem}.md'
        no_images_output_path = output_dir / f'{pdf_path.stem}_no_images.md'

        await asyncio.gather(
            self._write_file_async(output_path, cached_result['full_markdown']),
            self._write_file_async(
                no_images_output_path, cached_result['no_images_markdown']
            ),
        )

        return output_path, no_images_output_path

    def _get_combined_markdown(self, ocr_response: dict) -> str:
        """Combine OCR text and images into a single markdown document."""
        markdowns = []
        for page in ocr_response.get('pages', []):
            image_data = {}
            for img in page.get('images', []):
                image_data[img['id']] = img['image_base64']
            markdowns.append(
                self._replace_images_in_markdown(page['markdown'], image_data)
            )
        return '\n\n'.join(markdowns)

    def _join_markdown_pages(self, ocr_response: dict) -> str:
        """Join the markdown pages into a single markdown document."""
        return '\n\n'.join(page['markdown'] for page in ocr_response.get('pages', []))

    def _replace_images_in_markdown(self, markdown_str: str, images_dict: dict) -> str:
        """Replace image placeholders in markdown with base64-encoded images."""
        for img_name, base64_str in images_dict.items():
            markdown_str = markdown_str.replace(
                f'![{img_name}]({img_name})', f'![{img_name}]({base64_str})'
            )
        return markdown_str

    async def batch_ocr_convert(
        self, pdf_paths: list[Path], output_dir: Path | None = None
    ) -> list[tuple[Path, Path]]:
        """
        Convert multiple PDFs to markdown concurrently.

        Args:
            pdf_paths: List of PDF paths to convert
            output_dir: Optional output directory

        Returns:
            list[tuple[Path, Path]]: List of (full_markdown, no_images_markdown) paths
        """
        self.logger.info(f'Starting batch OCR conversion of {len(pdf_paths)} PDFs')

        # Create semaphore to limit concurrent operations
        max_concurrent = min(len(pdf_paths), 3)  # Limit to 3 concurrent OCR operations

        tasks = []
        for pdf_path in pdf_paths:
            task = self.ocr_convert_async(pdf_path, output_dir)
            tasks.append(task)

        # Process with limited concurrency
        results = []
        for i in range(0, len(tasks), max_concurrent):
            batch_tasks = tasks[i : i + max_concurrent]
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    self.logger.error(f'Batch OCR error: {result}')
                    continue
                results.append(result)

        self.logger.info(
            f'Completed batch OCR: {len(results)}/{len(pdf_paths)} successful'
        )
        return results

    def health_check(self) -> dict[str, str]:
        """Basic health status for the AsyncProcessingService."""
        status = super().health_check()
        status['async_session'] = 'active' if self._session else 'not_created'
        status['cache_size'] = str(len(self._ocr_cache))
        return status
