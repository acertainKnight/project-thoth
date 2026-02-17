"""
File converter service for external knowledge documents.

Converts various file formats (PDF, MD, TXT, HTML, EPUB, DOCX) to markdown
for processing through the RAG pipeline.
"""

from pathlib import Path
from typing import Any

from loguru import logger

from thoth.config import Config


class FileConverter:
    """
    Convert various file formats to markdown.

    Supports:
    - PDF: routes through existing Mistral OCR pipeline
    - Markdown: pass-through
    - Plain text: minimal wrapping
    - HTML: convert via markdownify
    - EPUB: extract chapters and convert
    - DOCX: convert via mammoth
    """

    def __init__(self, config: Config | None = None):
        """
        Initialize the file converter.

        Args:
            config: Configuration object (optional, creates default if not provided)
        """
        self.config = config or Config()
        self._mistral_client = None

    def convert_to_markdown(
        self, file_path: Path, original_filename: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        """
        Convert a file to markdown.

        Args:
            file_path: Path to the file to convert
            original_filename: Original filename (if different from file_path.name)

        Returns:
            Tuple of (markdown_content, metadata_dict)

        Raises:
            ValueError: If file format is not supported
            FileNotFoundError: If file does not exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f'File not found: {file_path}')

        filename = original_filename or file_path.name
        suffix = file_path.suffix.lower()

        metadata = {
            'original_filename': filename,
            'file_type': suffix[1:] if suffix else 'unknown',
            'source_path': str(file_path),
        }

        if suffix == '.pdf':
            markdown, pdf_meta = self._convert_pdf(file_path)
            metadata.update(pdf_meta)
            return markdown, metadata
        elif suffix == '.md':
            return self._convert_markdown(file_path), metadata
        elif suffix == '.txt':
            return self._convert_text(file_path), metadata
        elif suffix in {'.html', '.htm'}:
            return self._convert_html(file_path), metadata
        elif suffix == '.epub':
            return self._convert_epub(file_path), metadata
        elif suffix == '.docx':
            return self._convert_docx(file_path), metadata
        else:
            raise ValueError(
                f'Unsupported file format: {suffix}. '
                f'Supported: .pdf, .md, .txt, .html, .htm, .epub, .docx'
            )

    def _convert_pdf(self, file_path: Path) -> tuple[str, dict[str, Any]]:
        """
        Convert PDF to markdown using Mistral OCR.

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (markdown_content, metadata)
        """
        if not self._mistral_client:
            try:
                from mistralai import Mistral

                api_key = (
                    self.config.api_keys.mistral_key
                    or self.config.secrets.mistral_api_key
                )
                if not api_key:
                    raise ValueError('MISTRAL_API_KEY not configured')
                self._mistral_client = Mistral(api_key=api_key)
            except ImportError as e:
                raise ImportError(
                    'mistralai package required for PDF conversion. '
                    'Install with: pip install thoth[pdf]'
                ) from e

        try:
            logger.info(f'Uploading PDF for OCR: {file_path.name}')

            uploaded_file = self._mistral_client.files.upload(
                file={
                    'file_name': file_path.stem,
                    'content': open(file_path, 'rb'),
                },
                purpose='ocr',
            )
            signed_url = self._mistral_client.files.get_signed_url(
                file_id=uploaded_file.id
            )

            logger.info(f'Running Mistral OCR: {file_path.name}')

            from mistralai import DocumentURLChunk

            ocr_response = self._mistral_client.ocr.process(
                document=DocumentURLChunk(document_url=signed_url.url),
                model='mistral-ocr-latest',
                include_image_base64=False,
            )

            # Combine page-level markdown from OCR response
            pages = ocr_response.pages if hasattr(ocr_response, 'pages') else []
            markdown = '\n\n'.join(
                page.markdown for page in pages if hasattr(page, 'markdown')
            )

            if not markdown:
                markdown = str(ocr_response)

            metadata = {
                'ocr_model': 'mistral-ocr-latest',
                'conversion_method': 'mistral_ocr',
                'page_count': len(pages),
            }

            logger.success(
                f'PDF converted: {file_path.name} '
                f'({len(pages)} pages, {len(markdown)} chars)'
            )

            return markdown, metadata

        except Exception as e:
            logger.error(f'Failed to convert PDF {file_path.name}: {e}')
            raise

    def _convert_markdown(self, file_path: Path) -> str:
        """
        Read markdown file (pass-through).

        Args:
            file_path: Path to markdown file

        Returns:
            Markdown content
        """
        return file_path.read_text(encoding='utf-8')

    def _convert_text(self, file_path: Path) -> str:
        """
        Convert plain text to markdown.

        Args:
            file_path: Path to text file

        Returns:
            Markdown content (text wrapped with title)
        """
        text = file_path.read_text(encoding='utf-8')
        title = file_path.stem.replace('_', ' ').replace('-', ' ').title()

        return f'# {title}\n\n{text}'

    def _convert_html(self, file_path: Path) -> str:
        """
        Convert HTML to markdown using markdownify.

        Args:
            file_path: Path to HTML file

        Returns:
            Markdown content
        """
        try:
            from markdownify import markdownify as md
        except ImportError as e:
            raise ImportError(
                'markdownify package required for HTML conversion. '
                'Install with: pip install thoth[knowledge]'
            ) from e

        html = file_path.read_text(encoding='utf-8')
        markdown = md(html, heading_style='ATX', bullets='-')

        return markdown

    def _convert_epub(self, file_path: Path) -> str:
        """
        Convert EPUB to markdown.

        Args:
            file_path: Path to EPUB file

        Returns:
            Markdown content (all chapters concatenated)
        """
        try:
            import ebooklib
            from ebooklib import epub
            from markdownify import markdownify as md
        except ImportError as e:
            raise ImportError(
                'ebooklib and markdownify packages required for EPUB conversion. '
                'Install with: pip install thoth[knowledge]'
            ) from e

        book = epub.read_epub(str(file_path))
        markdown_parts = []

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                html_content = item.get_content().decode('utf-8')
                chapter_markdown = md(html_content, heading_style='ATX', bullets='-')

                if chapter_markdown.strip():
                    markdown_parts.append(chapter_markdown)

        full_markdown = '\n\n---\n\n'.join(markdown_parts)

        return full_markdown

    def _convert_docx(self, file_path: Path) -> str:
        """
        Convert DOCX to markdown using mammoth.

        Args:
            file_path: Path to DOCX file

        Returns:
            Markdown content
        """
        try:
            import mammoth
            from markdownify import markdownify as md
        except ImportError as e:
            raise ImportError(
                'mammoth and markdownify packages required for DOCX conversion. '
                'Install with: pip install thoth[knowledge]'
            ) from e

        with open(file_path, 'rb') as docx_file:
            result = mammoth.convert_to_html(docx_file)
            html = result.value

        markdown = md(html, heading_style='ATX', bullets='-')

        if result.messages:
            logger.debug(
                f'DOCX conversion messages for {file_path.name}: {result.messages}'
            )

        return markdown

    @staticmethod
    def get_supported_extensions() -> set[str]:
        """
        Get set of supported file extensions.

        Returns:
            Set of extensions (including leading dot)
        """
        return {'.pdf', '.md', '.txt', '.html', '.htm', '.epub', '.docx'}

    @staticmethod
    def is_supported(file_path: Path) -> bool:
        """
        Check if file format is supported.

        Args:
            file_path: Path to check

        Returns:
            True if supported, False otherwise
        """
        return file_path.suffix.lower() in FileConverter.get_supported_extensions()
